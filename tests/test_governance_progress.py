from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.governance import UnknownStateWriteError
from backend.governance.progress import PlanProgressStore


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def test_progress_absent_is_not_unknown(tmp_path: Path) -> None:
    store = PlanProgressStore(tmp_path)
    observed = store.read()
    assert observed.state == "absent"
    assert observed.stale is None
    assert observed.progress is None


def test_pulse_persists_sequence_and_stale_state(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 8, 7, 1, 0, tzinfo=timezone.utc))
    store = PlanProgressStore(tmp_path, stale_after_seconds=120, clock=clock)

    first = store.pulse(
        plan_id="atlas",
        stage="phase-7",
        status="running",
        next_gate="pilot",
        write_active=False,
    )
    assert first.sequence == 1
    observed = store.read()
    assert observed.state == "present"
    assert observed.stale is False
    assert observed.progress == first

    clock.now += timedelta(seconds=121)
    assert store.read().stale is True

    second = store.pulse(
        plan_id="atlas",
        stage="phase-7",
        status="running",
        next_gate="pilot",
        write_active=False,
    )
    assert second.sequence == 2
    assert store.read().stale is False


def test_corrupt_progress_is_unknown_and_cannot_be_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "state" / "atlas-beacon-plan.json"
    path.parent.mkdir()
    path.write_text("{not-json", encoding="utf-8")
    store = PlanProgressStore(tmp_path)

    observed = store.read()
    assert observed.state == "unknown"
    assert observed.reason == "artifact_parse_failed:JSONDecodeError"

    with pytest.raises(UnknownStateWriteError, match="artifact_parse_failed"):
        store.pulse(
            plan_id="atlas",
            stage="phase-7",
            status="running",
            next_gate="pilot",
            write_active=False,
        )
    assert path.read_text(encoding="utf-8") == "{not-json"


def test_wrong_progress_types_are_unknown_and_cannot_authorize_write(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state" / "atlas-beacon-plan.json"
    path.parent.mkdir()
    path.write_text(
        '{"schema_version":1,"plan_id":"atlas","stage":"pilot",'
        '"status":"running","next_gate":"verify","write_active":"false",'
        '"pid":1,"sequence":1,"heartbeat_at":"2026-08-07T00:00:00Z"}',
        encoding="utf-8",
    )
    store = PlanProgressStore(tmp_path)

    observed = store.read()
    assert observed.state == "unknown"
    assert observed.reason == "artifact_parse_failed:ValueError"
    with pytest.raises(UnknownStateWriteError, match="artifact_parse_failed"):
        store.pulse(
            plan_id="atlas",
            stage="pilot",
            status="running",
            next_gate="verify",
            write_active=False,
        )


def test_write_activity_records_active_then_verified_gate(tmp_path: Path) -> None:
    store = PlanProgressStore(tmp_path)

    with store.write_activity(
        plan_id="atlas",
        stage="phase-8",
        action="memory.shadow",
        next_gate="pilot_complete",
    ):
        active = store.read().progress
        assert active is not None
        assert active.write_active is True
        assert active.next_gate == "post_write_verification"

    finished = store.read().progress
    assert finished is not None
    assert finished.write_active is False
    assert finished.status == "running"
    assert finished.next_gate == "pilot_complete"
    assert finished.sequence == 2


def test_write_activity_records_failure_without_swallowing_error(tmp_path: Path) -> None:
    store = PlanProgressStore(tmp_path)

    with pytest.raises(ValueError, match="boom"):
        with store.write_activity(
            plan_id="atlas",
            stage="phase-8",
            action="profile.shadow",
            next_gate="pilot_complete",
        ):
            raise ValueError("boom")

    failed = store.read().progress
    assert failed is not None
    assert failed.write_active is False
    assert failed.status == "failed"
    assert failed.next_gate == "manual_review"
    assert failed.detail == "ValueError"


def test_governance_plan_route_is_registered() -> None:
    from backend.main import app

    methods = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("GET", "/api/governance/plan") in methods
    assert not any(
        path == "/api/governance/plan" and method != "GET"
        for method, path in methods
    )
