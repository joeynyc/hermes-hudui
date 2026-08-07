"""Read-only file observation and fail-closed write state transitions.

The observer never mutates the target. A write may begin only from a PRESENT or
ABSENT observation. UNKNOWN is a first-class state and is never treated as an
empty or missing file.
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FilePresence(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class WritePhase(str, Enum):
    OBSERVED = "observed"
    READY = "ready"
    REJECTED_UNKNOWN = "rejected_unknown"
    REJECTED_PRECONDITION = "rejected_precondition"
    WRITE_ACTIVE = "write_active"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FAILED = "failed"


class GovernanceWriteError(RuntimeError):
    """Base error for fail-closed ATLAS write governance."""


class UnknownStateWriteError(GovernanceWriteError):
    pass


class WritePreconditionError(GovernanceWriteError):
    pass


class WriteVerificationError(GovernanceWriteError):
    pass


@dataclass(frozen=True)
class FileObservation:
    path: Path
    presence: FilePresence
    sha256: str | None = None
    size: int | None = None
    mtime_ns: int | None = None
    reason: str | None = None

    @property
    def known(self) -> bool:
        return self.presence is not FilePresence.UNKNOWN

    def same_version(self, other: "FileObservation") -> bool:
        if not self.known or not other.known:
            return False
        if self.path.resolve(strict=False) != other.path.resolve(strict=False):
            return False
        if self.presence is not other.presence:
            return False
        if self.presence is FilePresence.ABSENT:
            return True
        return (
            self.sha256 == other.sha256
            and self.size == other.size
            and self.mtime_ns == other.mtime_ns
        )


def _unknown(path: Path, reason: str) -> FileObservation:
    return FileObservation(path=path, presence=FilePresence.UNKNOWN, reason=reason)


def observe_file(path: str | Path) -> FileObservation:
    """Observe one regular file without changing it.

    Missing is a known ABSENT state. Permission, I/O, symlink, directory, and
    other ambiguous states are UNKNOWN and therefore cannot authorize a write.
    """

    target = Path(path)
    try:
        if target.is_symlink():
            return _unknown(target, "symlink_not_admitted")
        metadata = target.stat()
    except FileNotFoundError:
        return FileObservation(path=target, presence=FilePresence.ABSENT)
    except OSError as exc:
        return _unknown(target, f"stat_failed:{type(exc).__name__}:{exc.errno}")

    if not stat.S_ISREG(metadata.st_mode):
        return _unknown(target, "not_a_regular_file")

    digest = hashlib.sha256()
    try:
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        return _unknown(target, f"read_failed:{type(exc).__name__}:{exc.errno}")

    return FileObservation(
        path=target,
        presence=FilePresence.PRESENT,
        sha256=digest.hexdigest(),
        size=metadata.st_size,
        mtime_ns=metadata.st_mtime_ns,
    )


@dataclass
class WriteStateMachine:
    initial: FileObservation
    phase: WritePhase = field(init=False)
    reason: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.initial.presence is FilePresence.UNKNOWN:
            self.phase = WritePhase.REJECTED_UNKNOWN
            self.reason = self.initial.reason or "unknown_initial_state"
        else:
            self.phase = WritePhase.READY

    @property
    def can_write(self) -> bool:
        return self.phase is WritePhase.READY

    def require_writable(self) -> None:
        if self.phase is WritePhase.REJECTED_UNKNOWN:
            raise UnknownStateWriteError(self.reason or "unknown file state")
        if self.phase is not WritePhase.READY:
            raise WritePreconditionError(f"write is not ready: {self.phase.value}")

    def begin_write(self, current: FileObservation) -> None:
        self.require_writable()
        if current.presence is FilePresence.UNKNOWN:
            self.phase = WritePhase.REJECTED_UNKNOWN
            self.reason = current.reason or "unknown_current_state"
            raise UnknownStateWriteError(self.reason)
        if not self.initial.same_version(current):
            self.phase = WritePhase.REJECTED_PRECONDITION
            self.reason = "file_changed_after_observation"
            raise WritePreconditionError(self.reason)
        self.phase = WritePhase.WRITE_ACTIVE

    def begin_verification(self) -> None:
        if self.phase is not WritePhase.WRITE_ACTIVE:
            raise WritePreconditionError(
                f"cannot verify from phase: {self.phase.value}"
            )
        self.phase = WritePhase.VERIFYING

    def finish_verification(
        self, observed: FileObservation, expected_sha256: str
    ) -> None:
        if self.phase is not WritePhase.VERIFYING:
            raise WritePreconditionError(
                f"verification is not active: {self.phase.value}"
            )
        if observed.presence is FilePresence.UNKNOWN:
            self.phase = WritePhase.FAILED
            self.reason = observed.reason or "unknown_verification_state"
            raise WriteVerificationError(self.reason)
        if (
            observed.presence is not FilePresence.PRESENT
            or observed.sha256 != expected_sha256
        ):
            self.phase = WritePhase.FAILED
            self.reason = "post_write_digest_mismatch"
            raise WriteVerificationError(self.reason)
        self.phase = WritePhase.VERIFIED
        self.reason = None
