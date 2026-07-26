from __future__ import annotations

from pathlib import Path

import pytest

import backend.collectors.gateway as gateway


class _FakeProcess:
    pid = 4242

    def poll(self):
        return None


def test_run_action_uses_allowlisted_argv_and_private_files(tmp_path: Path, monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(gateway.shutil, "which", lambda name: "/usr/bin/hermes")

    def fake_popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return _FakeProcess()

    monkeypatch.setattr(gateway.subprocess, "Popen", fake_popen)

    state = gateway.run_action("gateway-restart", hermes_dir=str(tmp_path / "hermes"))

    assert calls[0][0] == ["/usr/bin/hermes", "gateway", "restart"]
    assert state["pid"] == 4242
    assert Path(state["log_path"]).is_relative_to(tmp_path / "hermes")
    assert (tmp_path / "hermes" / "logs" / "hud" / "gateway-restart.json").exists()


def test_action_rejects_unknown_name_before_touching_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown action"):
        gateway.read_action_status("../../outside", hermes_dir=str(tmp_path / "hermes"))

    assert not (tmp_path / "hermes").exists()


def test_action_rejects_symlinked_log_directory_escape(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    outside = tmp_path / "outside"
    (hermes_dir / "logs").mkdir(parents=True)
    outside.mkdir()
    (hermes_dir / "logs" / "hud").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes"):
        gateway.read_action_status("gateway-restart", hermes_dir=str(hermes_dir))


def test_action_status_ignores_symlinked_state_and_log_files(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    log_dir = hermes_dir / "logs" / "hud"
    log_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text('{"pid": 999}', encoding="utf-8")
    (log_dir / "gateway-restart.json").symlink_to(outside)
    (log_dir / "gateway-restart.log").symlink_to(outside)

    result = gateway.read_action_status("gateway-restart", hermes_dir=str(hermes_dir))

    assert result["pid"] is None
    assert result["lines"] == []
