"""File watcher service for Hermes HUD.

Watches ~/.hermes/ directory for changes and broadcasts updates via WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from watchfiles import Change, DefaultFilter, watch

from .cache import clear_cache
from .collectors.utils import default_hermes_dir
from .websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Map file patterns to data types for targeted cache invalidation
FILE_PATTERNS = {
    "state.db": ["sessions", "patterns", "timeline", "messages", "chat"],
    "MEMORY.md": ["memory"],
    "USER.md": ["user", "memory"],
    "config.yaml": ["config", "profiles"],
    "SKILL.md": ["skills"],
    "jobs.json": ["cron"],
    ".env": ["health", "profiles"],
    "SOUL.md": ["profiles"],
}

# Directory patterns
DIR_PATTERNS = {
    "skills": ["skills"],
    "profiles": ["profiles"],
    "projects": ["projects"],
    "memories": ["memory", "user"],
    "cron": ["cron"],
}


def _detect_change_type(path: Path) -> list[str]:
    """Determine what data types changed based on file path."""
    path_str = str(path)
    name = path.name

    # Check file patterns
    if name in FILE_PATTERNS:
        return FILE_PATTERNS[name]

    # Check directory patterns
    for dir_name, data_types in DIR_PATTERNS.items():
        if f"/{dir_name}/" in path_str or path_str.endswith(f"/{dir_name}"):
            return data_types

    # Check for specific file types
    if name.endswith(".db"):
        return ["sessions", "patterns"]
    if name == "corrections.json":
        return ["corrections"]
    if name == "snapshots.json":
        return ["snapshots"]

    return ["state"]  # Generic fallback


def _should_ignore(path: Path) -> bool:
    """Check if file should be ignored."""
    name = path.name
    # Ignore temporary files, swap files, etc.
    ignore_patterns = (
        ".tmp",
        ".temp",
        ".swp",
        ".swo",
        ".~",
        ".lock",
        "__pycache__",
        ".pyc",
    )
    if any(name.endswith(p) or p in name for p in ignore_patterns):
        return True
    # Ignore hidden files
    if name.startswith(".") and name not in {".env", ".hermes"}:
        return True
    return False


class FileWatcherService:
    """Service that watches Hermes data directory for changes."""

    def __init__(self, hermes_dir: str | None = None):
        self.hermes_dir = Path(default_hermes_dir(hermes_dir))
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._on_change: Callable[[list[str], Path], None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def on_change(self, callback: Callable[[list[str], Path], None]) -> None:
        """Set callback for change events.

        Args:
            callback: Function receiving (data_types, changed_path)
        """
        self._on_change = callback

    async def start(self) -> None:
        """Start the file watcher in a background task."""
        if self._task is not None:
            return

        if not self.hermes_dir.exists():
            logger.warning(f"Hermes directory does not exist: {self.hermes_dir}")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(f"File watcher started for {self.hermes_dir}")

    async def stop(self) -> None:
        """Stop the file watcher."""
        if self._task is None:
            return

        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("File watcher stopped")

    def _get_watch_paths(self) -> list[Path]:
        """Get paths to watch - main dir and key subdirectories."""
        paths = [self.hermes_dir]

        # Add key subdirectories if they exist
        for subdir in ["skills", "profiles", "memories", "cron", "projects"]:
            path = self.hermes_dir / subdir
            if path.exists():
                paths.append(path)

        return paths

    def _run_sync_watcher(self) -> None:
        """Synchronous watcher to run in background thread."""
        import threading
        import time

        # Track last broadcast time per data type (throttle: max 1 broadcast per 5 seconds per type)
        last_broadcast: dict[str, float] = {}
        MIN_BROADCAST_INTERVAL = 5.0  # seconds

        def should_broadcast(data_types: set[str]) -> bool:
            now = time.time()
            for dt in data_types:
                last = last_broadcast.get(dt, 0)
                if now - last >= MIN_BROADCAST_INTERVAL:
                    return True
            return False

        def update_last_broadcast(data_types: set[str]) -> None:
            now = time.time()
            for dt in data_types:
                last_broadcast[dt] = now

        try:
            watch_paths = [str(p) for p in self._get_watch_paths()]

            # Use polling for reliability (scan every 2 seconds)
            for changes in watch(
                *watch_paths, stop_event=self._stop_event, force_polling=True
            ):
                if self._stop_event.is_set():
                    break

                # Process changes
                data_types_changed: set[str] = set()
                changed_files: list[Path] = []

                for change_type, path_str in changes:
                    path = Path(path_str)

                    if _should_ignore(path):
                        continue

                    data_types = _detect_change_type(path)
                    data_types_changed.update(data_types)
                    changed_files.append(path)
                    logger.debug(f"Detected {change_type.name}: {path} -> {data_types}")

                # Only broadcast if enough time has passed (throttle)
                if data_types_changed and should_broadcast(data_types_changed):
                    update_last_broadcast(data_types_changed)
                    # Schedule broadcast in main event loop
                    if self._loop and self._loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self._handle_changes(data_types_changed, changed_files),
                            self._loop,
                        )

        except Exception:
            logger.exception("File watcher error")

    async def _handle_changes(
        self, data_types_changed: set[str], changed_files: list[Path]
    ) -> None:
        """Handle detected changes (runs in main async loop)."""
        try:
            # Clear cache
            clear_cache()

            # Broadcast to WebSocket clients
            await ws_manager.broadcast(
                {
                    "type": "data_changed",
                    "data_types": list(data_types_changed),
                    "paths": [str(p) for p in changed_files[:5]],
                }
            )

            # Call custom handler if set
            if self._on_change:
                for dt in data_types_changed:
                    self._on_change(
                        [dt], changed_files[0] if changed_files else Path(".")
                    )
        except Exception:
            logger.exception("Error handling file changes")

    async def _watch_loop(self) -> None:
        """Main watch loop - runs sync watcher in thread."""
        import threading

        self._loop = asyncio.get_event_loop()

        try:
            # Run blocking watch in background thread
            thread = threading.Thread(target=self._run_sync_watcher, daemon=True)
            thread.start()

            # Wait until stopped
            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.debug("Watch loop cancelled")
            raise

    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._task is not None and not self._task.done()


# Global watcher instance
file_watcher = FileWatcherService()


async def start_watcher(hermes_dir: str | None = None) -> None:
    """Start the global file watcher."""
    global file_watcher
    if hermes_dir:
        file_watcher = FileWatcherService(hermes_dir)
    await file_watcher.start()


async def stop_watcher() -> None:
    """Stop the global file watcher."""
    await file_watcher.stop()
