"""Durable ATLAS Beacon plan heartbeat and stage progress artifact."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from backend.collectors.utils import default_hermes_dir

from .action_adapter import VerifiedFileActionAdapter
from .state_observer import (
    FilePresence,
    UnknownStateWriteError,
    observe_file,
)


@dataclass(frozen=True)
class PlanProgress:
    schema_version: int
    plan_id: str
    stage: str
    status: str
    next_gate: str
    write_active: bool
    pid: int
    sequence: int
    heartbeat_at: str
    action: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class PlanProgressObservation:
    state: str
    progress: PlanProgress | None
    stale: bool | None
    reason: str | None = None


class PlanProgressStore:
    def __init__(
        self,
        hermes_dir: str | Path | None = None,
        *,
        stale_after_seconds: int = 120,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        root = Path(hermes_dir or default_hermes_dir()).resolve(strict=False)
        self.root = root
        self.path = root / "state" / "atlas-beacon-plan.json"
        self.stale_after_seconds = stale_after_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._adapter = VerifiedFileActionAdapter(allowed_roots=[root])

    def _parse(self, payload: object) -> PlanProgress:
        if not isinstance(payload, dict):
            raise ValueError("progress payload must be an object")
        required = {
            "schema_version",
            "plan_id",
            "stage",
            "status",
            "next_gate",
            "write_active",
            "pid",
            "sequence",
            "heartbeat_at",
        }
        if not required.issubset(payload):
            raise ValueError("progress payload is missing required fields")
        if payload["schema_version"] != 1:
            raise ValueError("unsupported progress schema")
        for key in ("pid", "sequence"):
            if not isinstance(payload[key], int) or isinstance(payload[key], bool):
                raise ValueError(f"{key} must be an integer")
        if payload["sequence"] < 1:
            raise ValueError("sequence must be positive")
        if not isinstance(payload["write_active"], bool):
            raise ValueError("write_active must be a boolean")
        for key in ("plan_id", "stage", "status", "next_gate", "heartbeat_at"):
            if not isinstance(payload[key], str) or not payload[key].strip():
                raise ValueError(f"{key} must be a non-empty string")
        for key in ("action", "detail"):
            if payload.get(key) is not None and not isinstance(payload[key], str):
                raise ValueError(f"{key} must be a string or null")
        return PlanProgress(
            schema_version=payload["schema_version"],
            plan_id=payload["plan_id"],
            stage=payload["stage"],
            status=payload["status"],
            next_gate=payload["next_gate"],
            write_active=payload["write_active"],
            pid=payload["pid"],
            sequence=payload["sequence"],
            heartbeat_at=payload["heartbeat_at"],
            action=payload.get("action"),
            detail=payload.get("detail"),
        )

    def read(self) -> PlanProgressObservation:
        observed = observe_file(self.path)
        if observed.presence is FilePresence.ABSENT:
            return PlanProgressObservation(
                state="absent", progress=None, stale=None, reason="artifact_absent"
            )
        if observed.presence is FilePresence.UNKNOWN:
            return PlanProgressObservation(
                state="unknown",
                progress=None,
                stale=None,
                reason=observed.reason or "artifact_unreadable",
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            progress = self._parse(payload)
            heartbeat = datetime.fromisoformat(
                progress.heartbeat_at.replace("Z", "+00:00")
            )
            if heartbeat.tzinfo is None:
                raise ValueError("heartbeat must include timezone")
            age = (self._clock() - heartbeat.astimezone(timezone.utc)).total_seconds()
            return PlanProgressObservation(
                state="present",
                progress=progress,
                stale=age > self.stale_after_seconds,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return PlanProgressObservation(
                state="unknown",
                progress=None,
                stale=None,
                reason=f"artifact_parse_failed:{type(exc).__name__}",
            )

    def pulse(
        self,
        *,
        plan_id: str,
        stage: str,
        status: str,
        next_gate: str,
        write_active: bool,
        action: str | None = None,
        detail: str | None = None,
    ) -> PlanProgress:
        current = self.read()
        if current.state == "unknown":
            raise UnknownStateWriteError(current.reason or "unknown progress state")
        sequence = (
            current.progress.sequence + 1
            if current.progress is not None
            else 1
        )
        now = self._clock().astimezone(timezone.utc)
        progress = PlanProgress(
            schema_version=1,
            plan_id=plan_id,
            stage=stage,
            status=status,
            next_gate=next_gate,
            write_active=write_active,
            pid=os.getpid(),
            sequence=sequence,
            heartbeat_at=now.isoformat().replace("+00:00", "Z"),
            action=action,
            detail=detail,
        )
        payload = (
            json.dumps(asdict(progress), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        ).encode("utf-8")
        self._adapter.write_one(
            self.path, payload, action="governance.plan-heartbeat"
        )
        return progress

    @contextmanager
    def write_activity(
        self,
        *,
        plan_id: str,
        stage: str,
        action: str,
        next_gate: str,
    ) -> Iterator[None]:
        self.pulse(
            plan_id=plan_id,
            stage=stage,
            status="running",
            next_gate="post_write_verification",
            write_active=True,
            action=action,
        )
        try:
            yield
        except Exception as exc:
            self.pulse(
                plan_id=plan_id,
                stage=stage,
                status="failed",
                next_gate="manual_review",
                write_active=False,
                action=action,
                detail=type(exc).__name__,
            )
            raise
        else:
            self.pulse(
                plan_id=plan_id,
                stage=stage,
                status="running",
                next_gate=next_gate,
                write_active=False,
                action=action,
            )
