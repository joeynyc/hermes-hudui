from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from backend.governance.state_observer import (
    FileObservation,
    FilePresence,
    UnknownStateWriteError,
    WritePhase,
    WritePreconditionError,
    WriteStateMachine,
    WriteVerificationError,
    observe_file,
)


def test_observer_distinguishes_absent_present_and_unknown(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    absent = observe_file(target)
    assert absent.presence is FilePresence.ABSENT
    assert absent.known is True

    payload = b'{"ok":true}\n'
    target.write_bytes(payload)
    present = observe_file(target)
    assert present.presence is FilePresence.PRESENT
    assert present.sha256 == hashlib.sha256(payload).hexdigest()
    assert present.size == len(payload)

    directory = tmp_path / "directory"
    directory.mkdir()
    unknown = observe_file(directory)
    assert unknown.presence is FilePresence.UNKNOWN
    assert unknown.reason == "not_a_regular_file"


def test_observer_rejects_symlink_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("x", encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlinks are unavailable in this Windows environment")
    observed = observe_file(link)
    assert observed.presence is FilePresence.UNKNOWN
    assert observed.reason == "symlink_not_admitted"


def test_unknown_state_can_never_begin_write(tmp_path: Path) -> None:
    unknown = FileObservation(
        path=tmp_path / "x",
        presence=FilePresence.UNKNOWN,
        reason="permission_denied",
    )
    machine = WriteStateMachine(unknown)
    assert machine.phase is WritePhase.REJECTED_UNKNOWN
    assert machine.can_write is False
    with pytest.raises(UnknownStateWriteError, match="permission_denied"):
        machine.require_writable()


def test_changed_precondition_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "state"
    target.write_text("before", encoding="utf-8")
    machine = WriteStateMachine(observe_file(target))
    target.write_text("changed", encoding="utf-8")

    with pytest.raises(WritePreconditionError, match="file_changed"):
        machine.begin_write(observe_file(target))
    assert machine.phase is WritePhase.REJECTED_PRECONDITION


def test_verified_write_state_transition(tmp_path: Path) -> None:
    target = tmp_path / "state"
    initial = observe_file(target)
    machine = WriteStateMachine(initial)
    machine.begin_write(observe_file(target))
    assert machine.phase is WritePhase.WRITE_ACTIVE

    payload = b"written\n"
    target.write_bytes(payload)
    machine.begin_verification()
    machine.finish_verification(
        observe_file(target), hashlib.sha256(payload).hexdigest()
    )
    assert machine.phase is WritePhase.VERIFIED


def test_verification_digest_mismatch_fails(tmp_path: Path) -> None:
    target = tmp_path / "state"
    machine = WriteStateMachine(observe_file(target))
    machine.begin_write(observe_file(target))
    target.write_text("actual", encoding="utf-8")
    machine.begin_verification()

    with pytest.raises(WriteVerificationError, match="digest_mismatch"):
        machine.finish_verification(observe_file(target), "0" * 64)
    assert machine.phase is WritePhase.FAILED
