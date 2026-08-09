"""Verified file action adapter for ATLAS Beacon governance.

Four enforced layers:
1. Scope policy: every target must stay inside an admitted root.
2. State precondition: PRESENT/ABSENT are writable; UNKNOWN is rejected.
3. Controlled execution: stage all payloads, recheck every precondition, then replace.
4. Evidence: verify every resulting SHA-256; multi-file failures are rolled back.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .state_observer import (
    FileObservation,
    FilePresence,
    WritePreconditionError,
    WriteStateMachine,
    WriteVerificationError,
    observe_file,
)


class EvidenceTruth(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvidenceRecord:
    predicate: str
    truth: EvidenceTruth
    target: str
    expected: str | None = None
    observed: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ActionReceipt:
    action: str
    status: str
    evidence: tuple[EvidenceRecord, ...]

    @property
    def verified(self) -> bool:
        return bool(self.evidence) and all(
            item.truth is EvidenceTruth.TRUE for item in self.evidence
        )


@dataclass(frozen=True)
class FileWrite:
    path: Path
    payload: bytes


@dataclass
class _PreparedWrite:
    request: FileWrite
    initial: FileObservation
    machine: WriteStateMachine
    expected_sha256: str
    staged_path: Path | None = None
    backup_path: Path | None = None


def digest_evidence(
    target: Path, observed: FileObservation, expected_sha256: str
) -> EvidenceRecord:
    if observed.presence is FilePresence.UNKNOWN:
        return EvidenceRecord(
            predicate="sha256_matches",
            truth=EvidenceTruth.UNKNOWN,
            target=str(target),
            expected=expected_sha256,
            reason=observed.reason or "unknown_observation",
        )
    if observed.presence is not FilePresence.PRESENT:
        return EvidenceRecord(
            predicate="sha256_matches",
            truth=EvidenceTruth.FALSE,
            target=str(target),
            expected=expected_sha256,
            reason="target_absent",
        )
    truth = (
        EvidenceTruth.TRUE
        if observed.sha256 == expected_sha256
        else EvidenceTruth.FALSE
    )
    return EvidenceRecord(
        predicate="sha256_matches",
        truth=truth,
        target=str(target),
        expected=expected_sha256,
        observed=observed.sha256,
        reason=None if truth is EvidenceTruth.TRUE else "digest_mismatch",
    )


class VerifiedFileActionAdapter:
    def __init__(
        self,
        *,
        allowed_roots: Iterable[str | Path],
        replace_fn: Callable[[str | Path, str | Path], None] = os.replace,
    ) -> None:
        roots = tuple(Path(root).resolve(strict=False) for root in allowed_roots)
        if not roots:
            raise ValueError("at least one allowed root is required")
        self._allowed_roots = roots
        self._replace = replace_fn

    def _admit(self, path: Path) -> None:
        lexical = Path(os.path.abspath(path))
        resolved = lexical.resolve(strict=False)
        for root in self._allowed_roots:
            try:
                relative = lexical.relative_to(root)
            except ValueError:
                continue
            current = root
            for part in relative.parts:
                current /= part
                if current.is_symlink():
                    raise WritePreconditionError("symlink_ancestor_not_admitted")
            try:
                resolved.relative_to(root)
            except ValueError:
                raise WritePreconditionError("target_outside_allowed_roots") from None
            return
        raise WritePreconditionError("target_outside_allowed_roots")

    @staticmethod
    def _stage(prepared: _PreparedWrite) -> None:
        target = prepared.request.path
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.atlas-stage-"
        )
        prepared.staged_path = Path(name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(prepared.request.payload)
                handle.flush()
                os.fsync(handle.fileno())
            mode = (
                prepared.initial.path.stat().st_mode
                if prepared.initial.presence is FilePresence.PRESENT
                else 0o600
            )
            os.chmod(prepared.staged_path, mode)
        except Exception:
            prepared.staged_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _backup(prepared: _PreparedWrite) -> None:
        if prepared.initial.presence is FilePresence.ABSENT:
            return
        target = prepared.request.path
        fd, name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.atlas-backup-"
        )
        prepared.backup_path = Path(name)
        try:
            with target.open("rb") as source, os.fdopen(fd, "wb") as backup:
                fd = -1
                shutil.copyfileobj(source, backup)
                backup.flush()
                os.fsync(backup.fileno())
            os.chmod(prepared.backup_path, target.stat().st_mode)
            backup = observe_file(prepared.backup_path)
            if (
                backup.presence is not FilePresence.PRESENT
                or backup.sha256 != prepared.initial.sha256
            ):
                raise WritePreconditionError("backup_digest_mismatch")
        except Exception:
            if fd >= 0:
                os.close(fd)
            prepared.backup_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _rollback_matches(prepared: _PreparedWrite) -> bool:
        observed = observe_file(prepared.request.path)
        if prepared.initial.presence is FilePresence.ABSENT:
            return observed.presence is FilePresence.ABSENT
        return (
            observed.presence is FilePresence.PRESENT
            and observed.sha256 == prepared.initial.sha256
            and observed.size == prepared.initial.size
        )

    def _rollback(self, replaced: list[_PreparedWrite]) -> None:
        failures: list[str] = []
        for prepared in reversed(replaced):
            try:
                if prepared.initial.presence is FilePresence.ABSENT:
                    prepared.request.path.unlink(missing_ok=True)
                elif prepared.backup_path is not None:
                    self._replace(prepared.backup_path, prepared.request.path)
                    prepared.backup_path = None
                else:
                    raise WriteVerificationError("missing_rollback_backup")
                if not self._rollback_matches(prepared):
                    failures.append(str(prepared.request.path))
            except Exception:
                failures.append(str(prepared.request.path))
        if failures:
            raise WriteVerificationError("rollback_unverified")

    @staticmethod
    def _cleanup(prepared: Iterable[_PreparedWrite]) -> None:
        for item in prepared:
            if item.staged_path is not None:
                item.staged_path.unlink(missing_ok=True)
            if item.backup_path is not None:
                item.backup_path.unlink(missing_ok=True)

    def write_many(
        self,
        writes: Mapping[str | Path, bytes] | Iterable[FileWrite],
        *,
        action: str = "file.write",
    ) -> ActionReceipt:
        requests = (
            [FileWrite(Path(path), payload) for path, payload in writes.items()]
            if isinstance(writes, Mapping)
            else list(writes)
        )
        if not requests:
            raise ValueError("at least one file write is required")

        resolved_targets: set[Path] = set()
        prepared: list[_PreparedWrite] = []
        for request in requests:
            self._admit(request.path)
            resolved = request.path.resolve(strict=False)
            if resolved in resolved_targets:
                raise WritePreconditionError("duplicate_target")
            resolved_targets.add(resolved)
            initial = observe_file(request.path)
            machine = WriteStateMachine(initial)
            machine.require_writable()
            prepared.append(
                _PreparedWrite(
                    request=request,
                    initial=initial,
                    machine=machine,
                    expected_sha256=hashlib.sha256(request.payload).hexdigest(),
                )
            )

        replaced: list[_PreparedWrite] = []
        try:
            for item in prepared:
                self._stage(item)
                self._backup(item)
            for item in prepared:
                self._admit(item.request.path)
                item.machine.begin_write(observe_file(item.request.path))
            for item in prepared:
                assert item.staged_path is not None
                self._replace(item.staged_path, item.request.path)
                item.staged_path = None
                replaced.append(item)
            evidence: list[EvidenceRecord] = []
            for item in prepared:
                item.machine.begin_verification()
                observed = observe_file(item.request.path)
                record = digest_evidence(
                    item.request.path, observed, item.expected_sha256
                )
                evidence.append(record)
                item.machine.finish_verification(observed, item.expected_sha256)
            return ActionReceipt(
                action=action,
                status="verified",
                evidence=tuple(evidence),
            )
        except Exception:
            if replaced:
                self._rollback(replaced)
            raise
        finally:
            self._cleanup(prepared)

    def write_one(
        self, path: str | Path, payload: bytes, *, action: str = "file.write"
    ) -> ActionReceipt:
        return self.write_many(
            [FileWrite(path=Path(path), payload=payload)], action=action
        )

    def shadow_many(
        self,
        writes: Mapping[str | Path, bytes] | Iterable[FileWrite],
        *,
        action: str = "file.write",
    ) -> ActionReceipt:
        """Evaluate policy and preconditions without mutating the filesystem."""

        requests = (
            [FileWrite(Path(path), payload) for path, payload in writes.items()]
            if isinstance(writes, Mapping)
            else list(writes)
        )
        if not requests:
            raise ValueError("at least one file write is required")

        resolved_targets: set[Path] = set()
        evidence: list[EvidenceRecord] = []
        for request in requests:
            self._admit(request.path)
            resolved = request.path.resolve(strict=False)
            if resolved in resolved_targets:
                raise WritePreconditionError("duplicate_target")
            resolved_targets.add(resolved)
            observed = observe_file(request.path)
            truth = (
                EvidenceTruth.UNKNOWN
                if observed.presence is FilePresence.UNKNOWN
                else EvidenceTruth.TRUE
            )
            evidence.append(
                EvidenceRecord(
                    predicate="precondition_known",
                    truth=truth,
                    target=str(request.path),
                    observed=observed.presence.value,
                    reason=observed.reason,
                )
            )
            evidence.append(
                EvidenceRecord(
                    predicate="sha256_matches",
                    truth=EvidenceTruth.UNKNOWN,
                    target=str(request.path),
                    expected=hashlib.sha256(request.payload).hexdigest(),
                    reason="shadow_mode_no_mutation",
                )
            )
        return ActionReceipt(
            action=action,
            status="shadow",
            evidence=tuple(evidence),
        )

    def shadow_one(
        self, path: str | Path, payload: bytes, *, action: str = "file.write"
    ) -> ActionReceipt:
        return self.shadow_many(
            [FileWrite(path=Path(path), payload=payload)], action=action
        )
