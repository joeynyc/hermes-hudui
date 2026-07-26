"""Tests for the cron mutation API (backend/api/cron.py).

Cron create/delete shell out to the ``hermes`` CLI rather than writing
``jobs.json`` directly, so the surface this module owns — and the part worth
guarding — is argv construction, input validation (non-empty schedule,
positive repeat, absolute workdir), and subprocess error propagation. The
``hermes`` binary is faked so nothing real is scheduled.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import backend.api.cron as cron
from backend.api.cron import CreateCronBody, create_job, delete_job


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stderr = stderr


@pytest.fixture
def captured_calls(monkeypatch):
    """Pretend the hermes CLI exists; capture each subprocess invocation."""
    monkeypatch.setattr(cron, "_HERMES_BIN", "/usr/bin/hermes")
    calls: list[tuple[list[str], dict]] = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return _FakeCompleted(returncode=0)

    monkeypatch.setattr(cron.subprocess, "run", fake_run)
    return calls


def test_create_builds_minimal_command(captured_calls) -> None:
    result = create_job(CreateCronBody(schedule="@daily"))
    assert result == {"status": "ok"}

    cmd, kwargs = captured_calls[0]
    assert cmd == ["/usr/bin/hermes", "cron", "create", "--", "@daily"]
    assert kwargs.get("timeout") == 10
    assert kwargs.get("capture_output") is True


def test_create_builds_full_command_in_order(captured_calls) -> None:
    create_job(
        CreateCronBody(
            schedule="0 9 * * *",
            prompt="do the thing",
            name="morning",
            deliver="email",
            repeat=3,
            skills=["seo", "  ", "social"],  # blank entry is dropped
            script="/opt/run.sh",
            workdir="/home/user/proj",
        )
    )

    cmd, _ = captured_calls[0]
    assert cmd == [
        "/usr/bin/hermes",
        "cron",
        "create",
        "--name=morning",
        "--deliver=email",
        "--repeat=3",
        "--skill=seo",
        "--skill=social",
        "--script=/opt/run.sh",
        "--workdir=/home/user/proj",
        "--",
        "0 9 * * *",
        "do the thing",
    ]


def test_create_rejects_empty_schedule(captured_calls) -> None:
    with pytest.raises(HTTPException) as exc:
        create_job(CreateCronBody(schedule="   "))
    assert exc.value.status_code == 400
    assert captured_calls == []  # never shelled out


def test_create_rejects_nonpositive_repeat(captured_calls) -> None:
    with pytest.raises(HTTPException) as exc:
        create_job(CreateCronBody(schedule="@daily", repeat=0))
    assert exc.value.status_code == 400
    assert captured_calls == []


def test_create_rejects_relative_workdir(captured_calls) -> None:
    with pytest.raises(HTTPException) as exc:
        create_job(CreateCronBody(schedule="@daily", workdir="relative/path"))
    assert exc.value.status_code == 400
    assert captured_calls == []


def test_create_propagates_cli_failure(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_HERMES_BIN", "/usr/bin/hermes")
    monkeypatch.setattr(
        cron.subprocess,
        "run",
        lambda cmd, **kw: _FakeCompleted(returncode=1, stderr=b"boom"),
    )
    with pytest.raises(HTTPException) as exc:
        create_job(CreateCronBody(schedule="@daily"))
    assert exc.value.status_code == 500
    assert "boom" in exc.value.detail


def test_delete_builds_remove_command(captured_calls) -> None:
    result = delete_job("job_42")
    assert result == {"status": "ok"}

    cmd, _ = captured_calls[0]
    assert cmd == ["/usr/bin/hermes", "cron", "remove", "--", "job_42"]


def test_delete_propagates_cli_failure(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_HERMES_BIN", "/usr/bin/hermes")
    monkeypatch.setattr(
        cron.subprocess,
        "run",
        lambda cmd, **kw: _FakeCompleted(returncode=2, stderr=b"no such job"),
    )
    with pytest.raises(HTTPException) as exc:
        delete_job("ghost")
    assert exc.value.status_code == 500
    assert "no such job" in exc.value.detail


def test_delete_rejects_option_injection(captured_calls) -> None:
    with pytest.raises(HTTPException) as exc:
        delete_job("--help")
    assert exc.value.status_code == 400
    assert captured_calls == []


def test_create_terminates_options_before_user_positionals(captured_calls) -> None:
    create_job(CreateCronBody(schedule="--help", prompt="--version"))

    cmd, _ = captured_calls[0]
    assert cmd[-3:] == ["--", "--help", "--version"]


def test_create_rejects_nul_bytes(captured_calls) -> None:
    with pytest.raises(HTTPException) as exc:
        create_job(CreateCronBody(schedule="@daily", prompt="hello\x00world"))
    assert exc.value.status_code == 400
    assert captured_calls == []


def test_missing_hermes_binary_returns_503(monkeypatch) -> None:
    monkeypatch.setattr(cron, "_HERMES_BIN", None)
    with pytest.raises(HTTPException) as exc:
        create_job(CreateCronBody(schedule="@daily"))
    assert exc.value.status_code == 503


def test_cron_mutation_routes_are_registered(registered_routes) -> None:
    assert ("POST", "/api/cron") in registered_routes
    assert ("DELETE", "/api/cron/{job_id}") in registered_routes
