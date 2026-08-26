import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from backend.collectors.models import SessionInfo
from backend.services.replay_exporter import publish_replay, unpublish_replay
from backend.services.replay_normalizer import normalize_session
from backend.services.replay_publisher import (
    PublishError,
    build_site,
    get_remote_settings,
    remote_status,
    sync_remote,
    update_remote_settings,
)


def _detail(session_id: str, title: str):
    session = SessionInfo(
        id=session_id,
        source="cli",
        title=title,
        started_at=datetime.fromtimestamp(100),
        ended_at=datetime.fromtimestamp(120),
        message_count=1,
        tool_call_count=0,
        input_tokens=1,
        output_tokens=1,
        model="gpt-test",
    )
    return normalize_session(
        session,
        [{"id": 1, "role": "user", "content": "Use /home/joey/app and email person@example.com", "timestamp": 101}],
    )


def _make_bare_remote(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", "-b", "main", str(path)], check=True, capture_output=True)
    return path


def _clone(remote: Path, target: Path) -> Path:
    subprocess.run(["git", "clone", str(remote), str(target)], check=True, capture_output=True)
    return target


def test_remote_settings_default_disabled_and_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))

    settings = get_remote_settings()
    assert settings["enabled"] is False
    assert settings["provider"] == "github-pages"

    updated = update_remote_settings({"enabled": True, "repo": "joeynyc/replays", "branch": "main", "base_url": ""})
    assert updated["enabled"] is True
    assert get_remote_settings()["repo"] == "joeynyc/replays"

    status = remote_status()
    assert status["base_url"] == "https://joeynyc.github.io/replays"
    assert status["settings"]["branch"] == "main"


def test_build_site_indexes_public_only_and_strips_local_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))
    publish_replay(_detail("session-public", "Public run"), visibility="public")
    publish_replay(_detail("session-unlisted", "Unlisted run"), visibility="unlisted")

    site = build_site()
    site_dir = Path(site["site_dir"])
    assert site["public_count"] == 1
    assert site["unlisted_count"] == 1
    assert (site_dir / ".nojekyll").exists()

    index = (site_dir / "index.html").read_text(encoding="utf-8")
    assert "Public run" in index
    assert "Unlisted run" not in index

    public_entry = next(e for e in site["entries"] if e["visibility"] == "public")
    unlisted_entry = next(e for e in site["entries"] if e["visibility"] == "unlisted")
    assert public_entry["path"].startswith("runs/")
    assert unlisted_entry["path"].startswith("u/")
    assert (site_dir / public_entry["path"]).exists()
    assert (site_dir / unlisted_entry["path"]).exists()

    for path in site_dir.rglob("*"):
        if path.is_file() and path.suffix != ".png":
            text = path.read_text(encoding="utf-8")
            assert "person@example.com" not in text
            assert "/home/joey" not in text
            assert str(tmp_path) not in text
        assert path.name != "publish.json"


def test_sync_remote_pushes_site_and_reports_urls(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path / "replays"))
    remote = _make_bare_remote(tmp_path / "remote.git")
    update_remote_settings(
        {"enabled": True, "repo": str(remote), "branch": "main", "base_url": "https://replays.example.com"}
    )
    publish_replay(_detail("session-public", "Public run"), visibility="public")

    status = sync_remote()
    assert status["ok"] is True
    assert status["up_to_date"] is False
    assert status["public_count"] == 1
    assert status["index_url"] == "https://replays.example.com/index.html"
    assert status["entries"][0]["url"].startswith("https://replays.example.com/runs/")

    checkout = _clone(remote, tmp_path / "checkout")
    assert (checkout / "index.html").exists()
    assert (checkout / ".nojekyll").exists()
    entry_path = status["entries"][0]["path"]
    assert (checkout / entry_path).exists()
    assert "person@example.com" not in (checkout / entry_path).read_text(encoding="utf-8")

    # Second sync with no changes is a no-op
    again = sync_remote()
    assert again["up_to_date"] is True
    assert again["commit"] == status["commit"]

    # last_sync surfaces through remote_status
    assert remote_status()["last_sync"]["commit"] == status["commit"]


def test_sync_remote_removes_unpublished_runs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path / "replays"))
    remote = _make_bare_remote(tmp_path / "remote.git")
    update_remote_settings({"enabled": True, "repo": str(remote), "branch": "main"})

    detail = _detail("session-public", "Public run")
    publish_replay(detail, visibility="public")
    first = sync_remote()
    entry_path = first["entries"][0]["path"]

    unpublish_replay(detail, visibility="public")
    second = sync_remote()
    assert second["public_count"] == 0

    checkout = _clone(remote, tmp_path / "checkout")
    assert not (checkout / entry_path).exists()
    assert "Public run" not in (checkout / "index.html").read_text(encoding="utf-8")


def test_sync_remote_requires_enabled_and_repo(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HUD_REPLAY_DIR", str(tmp_path))

    with pytest.raises(PublishError, match="disabled"):
        sync_remote()

    update_remote_settings({"enabled": True, "repo": ""})
    with pytest.raises(PublishError, match="repository"):
        sync_remote()
