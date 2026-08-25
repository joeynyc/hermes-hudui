from pathlib import Path

from backend.cache import clear_cache, get_cache_stats, get_cached_or_compute
from backend.file_watcher import (
    FileWatcherService,
    _force_polling,
    _invalidate_cache_for,
)


def test_file_watcher_watches_hermes_root_once(tmp_path: Path) -> None:
    for name in (
        "skills",
        "profiles",
        "memories",
        "cron",
        "projects",
        "logs",
        "plugins",
    ):
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


def test_file_watcher_invalidates_only_affected_cache_prefixes() -> None:
    clear_cache()
    for key in ("sessions:test", "skills:test", "gateway:test"):
        get_cached_or_compute(key, lambda key=key: key)

    assert _invalidate_cache_for({"skills"}) == 1
    remaining = {entry["key"] for entry in get_cache_stats()["entries"]}
    assert remaining == {"sessions:test", "gateway:test"}

    assert _invalidate_cache_for({"state"}) == 2
    assert get_cache_stats()["total_entries"] == 0
