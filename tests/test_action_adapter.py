from __future__ import annotations

from pathlib import Path

import pytest

from backend.governance import (
    EvidenceTruth,
    FileObservation,
    FilePresence,
    VerifiedFileActionAdapter,
    WritePreconditionError,
    WriteVerificationError,
    digest_evidence,
)


def test_adapter_rejects_target_outside_admitted_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    adapter = VerifiedFileActionAdapter(allowed_roots=[root])

    with pytest.raises(WritePreconditionError, match="outside_allowed_roots"):
        adapter.write_one(outside, b"blocked")
    assert not outside.exists()


def test_adapter_rejects_symlinked_parent_even_when_it_resolves_inside_root(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable in this Windows environment")
    adapter = VerifiedFileActionAdapter(allowed_roots=[tmp_path])

    with pytest.raises(WritePreconditionError, match="symlink_ancestor"):
        adapter.write_one(alias / "state", b"blocked")
    assert not (real / "state").exists()


def test_digest_evidence_is_explicitly_tristate(tmp_path: Path) -> None:
    target = tmp_path / "target"
    unknown = FileObservation(
        path=target,
        presence=FilePresence.UNKNOWN,
        reason="read_failed",
    )
    assert digest_evidence(target, unknown, "a" * 64).truth is EvidenceTruth.UNKNOWN

    absent = FileObservation(path=target, presence=FilePresence.ABSENT)
    assert digest_evidence(target, absent, "a" * 64).truth is EvidenceTruth.FALSE


def test_adapter_returns_verified_receipt_and_cleans_temps(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    adapter = VerifiedFileActionAdapter(allowed_roots=[tmp_path])

    receipt = adapter.write_one(target, b'{"state":"ok"}\n', action="state.update")

    assert target.read_bytes() == b'{"state":"ok"}\n'
    assert receipt.action == "state.update"
    assert receipt.status == "verified"
    assert receipt.verified is True
    assert [item.truth for item in receipt.evidence] == [EvidenceTruth.TRUE]
    assert list(tmp_path.glob(".*.atlas-*-*")) == []


def test_shadow_mode_records_unknown_evidence_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    adapter = VerifiedFileActionAdapter(allowed_roots=[tmp_path])

    receipt = adapter.shadow_one(target, b"would-write", action="state.shadow")

    assert receipt.status == "shadow"
    assert receipt.verified is False
    assert not target.exists()
    assert [item.truth for item in receipt.evidence] == [
        EvidenceTruth.TRUE,
        EvidenceTruth.UNKNOWN,
    ]


def test_shadow_mode_preserves_unknown_precondition(tmp_path: Path) -> None:
    target = tmp_path / "directory-target"
    target.mkdir()
    adapter = VerifiedFileActionAdapter(allowed_roots=[tmp_path])

    receipt = adapter.shadow_one(target, b"blocked")

    assert target.is_dir()
    assert receipt.evidence[0].truth is EvidenceTruth.UNKNOWN
    assert receipt.evidence[0].observed == "unknown"
    assert receipt.evidence[1].truth is EvidenceTruth.UNKNOWN


def test_multi_file_failure_rolls_back_existing_targets(tmp_path: Path) -> None:
    first = tmp_path / "config.yaml"
    second = tmp_path / "SOUL.md"
    first.write_bytes(b"before-config")
    second.write_bytes(b"before-soul")
    calls = 0

    def fail_second_replace(source, target) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second replace failure")
        Path(source).replace(target)

    adapter = VerifiedFileActionAdapter(
        allowed_roots=[tmp_path], replace_fn=fail_second_replace
    )

    with pytest.raises(OSError, match="injected"):
        adapter.write_many(
            {first: b"after-config", second: b"after-soul"},
            action="profile.update",
        )

    assert first.read_bytes() == b"before-config"
    assert second.read_bytes() == b"before-soul"
    assert list(tmp_path.glob(".*.atlas-*-*")) == []


def test_multi_file_failure_removes_new_target_during_rollback(tmp_path: Path) -> None:
    first = tmp_path / "new-config.yaml"
    second = tmp_path / "SOUL.md"
    second.write_bytes(b"before-soul")
    calls = 0

    def fail_second_replace(source, target) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second replace failure")
        Path(source).replace(target)

    adapter = VerifiedFileActionAdapter(
        allowed_roots=[tmp_path], replace_fn=fail_second_replace
    )

    with pytest.raises(OSError, match="injected"):
        adapter.write_many({first: b"new", second: b"after"})

    assert not first.exists()
    assert second.read_bytes() == b"before-soul"
    assert list(tmp_path.glob(".*.atlas-*-*")) == []


def test_rollback_failure_is_escalated_not_silenced(tmp_path: Path) -> None:
    first = tmp_path / "config.yaml"
    second = tmp_path / "SOUL.md"
    first.write_bytes(b"before-config")
    second.write_bytes(b"before-soul")
    calls = 0

    def fail_action_and_rollback(source, target) -> None:
        nonlocal calls
        calls += 1
        if calls in {2, 3}:
            raise OSError("injected replace failure")
        Path(source).replace(target)

    adapter = VerifiedFileActionAdapter(
        allowed_roots=[tmp_path], replace_fn=fail_action_and_rollback
    )

    with pytest.raises(WriteVerificationError, match="rollback_unverified"):
        adapter.write_many({first: b"after-config", second: b"after-soul"})
