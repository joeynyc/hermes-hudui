import json
import os
from datetime import datetime

from backend.collectors.models import SessionInfo
from backend.services.replay_exporter import export_json
from backend.services.replay_normalizer import normalize_session
from backend.services.replay_verifier import (
    MAX_VERIFICATION_FILE_BYTES,
    verify_replay_files,
)


def _detail():
    session = SessionInfo(
        id="session-verify",
        source="cli",
        title="Verify run",
        started_at=datetime.fromtimestamp(100),
        ended_at=datetime.fromtimestamp(120),
        message_count=1,
        tool_call_count=0,
        input_tokens=1,
        output_tokens=1,
    )
    return normalize_session(
        session,
        [{"id": 1, "role": "user", "content": "Verify this replay", "timestamp": 101}],
    )


def test_verify_replay_files_accepts_exported_receipt_and_replay(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)

    run_dir = tmp_path / "runs" / detail.run.replay_id
    result = verify_replay_files(str(run_dir / "receipt.json"), str(run_dir / "replay.redacted.json"))

    assert result["ok"] is True
    assert result["errors"] == []
    receipt = json.loads((run_dir / "receipt.json").read_text(encoding="utf-8"))
    assert result["receipt_hash"] == receipt["hashes"]["receipt_hash"]
    assert receipt["signature_algorithm"] == "ed25519"
    assert result["signature_algorithm"] == "ed25519"
    assert result["signature_valid"] is True


def test_verify_replay_files_rejects_tampered_receipt_hash(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)
    run_dir = tmp_path / "runs" / detail.run.replay_id
    receipt_path = run_dir / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["hashes"]["receipt_hash"] = "sha256:bad"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = verify_replay_files(str(receipt_path), str(run_dir / "replay.redacted.json"))

    assert result["ok"] is False
    assert "Receipt hash does not match receipt payload." in result["errors"]


def test_verify_replay_files_rejects_tampered_signature(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)
    run_dir = tmp_path / "runs" / detail.run.replay_id
    receipt_path = run_dir / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["signature"] = receipt["signature"][:-4] + "AAAA"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    result = verify_replay_files(str(receipt_path), str(run_dir / "replay.redacted.json"))

    assert result["ok"] is False
    assert "Receipt signature is invalid." in result["errors"]


def test_verify_replay_files_rejects_paths_outside_replay_root(tmp_path, monkeypatch) -> None:
    replay_root = tmp_path / "replays"
    outside = tmp_path / "outside.json"
    replay_root.mkdir()
    outside.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(replay_root))

    result = verify_replay_files(str(outside), str(outside))

    assert result["ok"] is False
    assert result["errors"] == [
        "Verification files must be inside the configured Replay directory",
        "Verification files must be inside the configured Replay directory",
    ]


def test_verify_replay_files_rejects_symlink_escape(tmp_path, monkeypatch) -> None:
    replay_root = tmp_path / "replays"
    replay_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    linked = replay_root / "linked.json"
    linked.symlink_to(outside)
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(replay_root))

    result = verify_replay_files(str(linked), str(linked))

    assert result["ok"] is False
    assert all("configured Replay directory" in error for error in result["errors"])


def test_verify_replay_files_rejects_oversized_input(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    run_dir = tmp_path / "runs" / "replay_0123456789ab"
    run_dir.mkdir(parents=True)
    receipt = run_dir / "receipt.json"
    replay = run_dir / "replay.redacted.json"
    for path in (receipt, replay):
        with path.open("wb") as handle:
            handle.truncate(MAX_VERIFICATION_FILE_BYTES + 1)

    result = verify_replay_files(str(receipt), str(replay))

    assert result["ok"] is False
    assert all("is larger than" in error for error in result["errors"])


def test_verify_replay_files_accepts_root_relative_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)

    replay_id = detail.run.replay_id
    result = verify_replay_files(
        f"runs/{replay_id}/receipt.json",
        f"runs/{replay_id}/replay.redacted.json",
    )

    assert result["ok"] is True


def test_verify_replay_files_accepts_windows_separators(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    detail = _detail()
    export_json(detail)

    replay_id = detail.run.replay_id
    separator = chr(92)
    result = verify_replay_files(
        f"runs{separator}{replay_id}{separator}receipt.json",
        f"runs{separator}{replay_id}{separator}replay.redacted.json",
    )

    assert result["ok"] is True


def test_verify_replay_files_rejects_traversal_and_unexpected_shapes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    replay_id = "replay_0123456789ab"
    invalid_paths = [
        f"runs/../runs/{replay_id}/receipt.json",
        "runs/not-a-replay-id/receipt.json",
        f"runs/{replay_id}/wrong.json",
        f"extra/runs/{replay_id}/receipt.json",
    ]

    for path in invalid_paths:
        result = verify_replay_files(path, path)
        assert result["ok"] is False
        assert all("configured Replay directory" in error for error in result["errors"])


def test_verify_replay_files_rejects_symlink_at_allowlisted_filename(tmp_path, monkeypatch) -> None:
    replay_root = tmp_path / "replays"
    run_dir = replay_root / "runs" / "replay_0123456789ab"
    run_dir.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (run_dir / "receipt.json").symlink_to(outside)
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(replay_root))

    result = verify_replay_files(
        "runs/replay_0123456789ab/receipt.json",
        "runs/replay_0123456789ab/receipt.json",
    )

    assert result["ok"] is False
    assert all("configured Replay directory" in error for error in result["errors"])


def test_verify_replay_files_rejects_parent_symlink_escape(tmp_path, monkeypatch) -> None:
    replay_root = tmp_path / "replays"
    runs_dir = replay_root / "runs"
    outside_run = tmp_path / "outside" / "replay_0123456789ab"
    runs_dir.mkdir(parents=True)
    outside_run.mkdir(parents=True)
    (outside_run / "receipt.json").write_text("{}", encoding="utf-8")
    linked_run = runs_dir / "replay_0123456789ab"
    try:
        linked_run.symlink_to(outside_run, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            import pytest

            pytest.skip("directory symlink creation is unavailable on this Windows host")
        raise
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(replay_root))

    result = verify_replay_files(
        "runs/replay_0123456789ab/receipt.json",
        "runs/replay_0123456789ab/receipt.json",
    )

    assert result["ok"] is False
    assert all("configured Replay directory" in error for error in result["errors"])
