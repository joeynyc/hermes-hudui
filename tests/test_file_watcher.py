from pathlib import Path

from backend.file_watcher import FileWatcherService, _force_polling


def test_file_watcher_watches_hermes_root_once(tmp_path: Path) -> None:
    for name in ("skills", "profiles", "memories", "cron", "projects", "logs", "plugins"):
        (tmp_path / name).mkdir()

    watcher = FileWatcherService(str(tmp_path))

    assert watcher._get_watch_paths() == [tmp_path]


def test_file_watcher_uses_native_events_by_default(monkeypatch) -> None:
    monkeypatch.delenv("HERMES_HUD_FORCE_POLLING", raising=False)
    assert _force_polling() is False


def test_file_watcher_polling_can_be_enabled(monkeypatch) -> None:
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("HERMES_HUD_FORCE_POLLING", value)
        assert _force_polling() is True
