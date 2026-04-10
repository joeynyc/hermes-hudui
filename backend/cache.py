"""Intelligent caching for Hermes HUD collectors.

Caches expensive operations with automatic invalidation based on file mtimes.
"""

from __future__ import annotations

import functools
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# In-memory cache storage: key -> (result, mtime_hash, timestamp)
_cache_store: dict[str, tuple[Any, str, float]] = {}
DEFAULT_TTL = 30  # seconds


def _get_file_mtime(path: str | Path) -> float:
    """Get file modification time, return 0 if not exists."""
    try:
        return os.path.getmtime(path)
    except (OSError, FileNotFoundError):
        return 0


def _get_dir_mtime(path: str | Path) -> float:
    """Get most recent mtime from directory contents (recursive)."""
    path = Path(path)
    if not path.exists():
        return 0

    max_mtime = _get_file_mtime(path)
    try:
        for item in path.rglob("*"):
            if item.is_file():
                max_mtime = max(max_mtime, _get_file_mtime(item))
    except (OSError, PermissionError):
        pass
    return max_mtime


def _compute_mtime_hash(*mtimes: float) -> str:
    """Create hash from mtimes for cache key validation."""
    data = ",".join(f"{m:.6f}" for m in mtimes)
    return hashlib.md5(data.encode()).hexdigest()[:16]


def cache_with_mtime(
    *file_paths: str | Path,
    ttl: int = DEFAULT_TTL,
    dir_paths: tuple[str | Path, ...] = (),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that caches function results, invalidating when files change.

    Args:
        *file_paths: Files to monitor for changes
        ttl: Cache time-to-live in seconds (even if files unchanged)
        *dir_paths: Directories to monitor recursively

    Example:
        @cache_with_mtime("~/.hermes/state.db", ttl=60)
        def collect_sessions(hermes_dir: str) -> SessionsState:
            ...

        @cache_with_mtime(dir_paths=("~/.hermes/skills",), ttl=300)
        def collect_skills(hermes_dir: str) -> SkillsState:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key from function name + args
            args_key = str(args) + str(sorted(kwargs.items()))
            cache_key = (
                f"{func.__name__}:{hashlib.md5(args_key.encode()).hexdigest()[:16]}"
            )

            # Expand paths and get current mtimes
            expanded_files = [os.path.expanduser(p) for p in file_paths]
            expanded_dirs = [os.path.expanduser(p) for p in dir_paths]

            file_mtimes = [_get_file_mtime(p) for p in expanded_files]
            dir_mtimes = [_get_dir_mtime(p) for p in expanded_dirs]

            current_mtime_hash = _compute_mtime_hash(*file_mtimes, *dir_mtimes)
            now = time.time()

            # Check cache
            if cache_key in _cache_store:
                result, stored_hash, timestamp = _cache_store[cache_key]
                # Valid if mtimes match AND ttl not expired
                if stored_hash == current_mtime_hash and (now - timestamp) < ttl:
                    return result

            # Cache miss or invalid - compute and store
            result = func(*args, **kwargs)
            _cache_store[cache_key] = (result, current_mtime_hash, now)
            return result

        # Expose cache management for testing/debugging
        wrapper._cache_key_prefix = func.__name__  # type: ignore
        wrapper._cache_clear = lambda: _clear_prefix(func.__name__)  # type: ignore

        return wrapper

    return decorator


def _clear_prefix(prefix: str) -> int:
    """Clear all cache entries with given prefix. Returns count cleared."""
    global _cache_store
    to_remove = [k for k in _cache_store if k.startswith(f"{prefix}:")]
    for k in to_remove:
        del _cache_store[k]
    return len(to_remove)


def clear_cache() -> int:
    """Clear entire cache. Returns count cleared."""
    global _cache_store
    count = len(_cache_store)
    _cache_store.clear()
    return count


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics for monitoring."""
    now = time.time()
    entries = []
    for key, (_, _, timestamp) in _cache_store.items():
        entries.append(
            {
                "key": key,
                "age_seconds": now - timestamp,
            }
        )
    return {
        "total_entries": len(_cache_store),
        "entries": sorted(entries, key=lambda x: x["age_seconds"], reverse=True),
    }


def get_cached_or_compute(
    cache_key: str,
    compute_fn: Callable[[], T],
    file_paths: list[str | Path] = None,
    dir_paths: list[str | Path] = None,
    ttl: int = DEFAULT_TTL,
) -> T:
    """Get cached result or compute it. For use with dynamic paths.

    Args:
        cache_key: Unique key for this cache entry
        compute_fn: Function that returns the computed value
        file_paths: Files to monitor for changes
        dir_paths: Directories to monitor recursively
        ttl: Cache time-to-live in seconds

    Example:
        def collect_sessions(hermes_dir: str) -> SessionsState:
            db_path = Path(hermes_dir) / "state.db"

            def _compute() -> SessionsState:
                # ... expensive SQLite queries ...
                return SessionsState(...)

            return get_cached_or_compute(
                f"sessions:{hermes_dir}",
                _compute,
                file_paths=[db_path],
                ttl=30
            )
    """
    file_paths = file_paths or []
    dir_paths = dir_paths or []

    file_mtimes = [_get_file_mtime(p) for p in file_paths]
    dir_mtimes = [_get_dir_mtime(p) for p in dir_paths]

    current_mtime_hash = _compute_mtime_hash(*file_mtimes, *dir_mtimes)
    now = time.time()

    # Check cache
    if cache_key in _cache_store:
        result, stored_hash, timestamp = _cache_store[cache_key]
        if stored_hash == current_mtime_hash and (now - timestamp) < ttl:
            return result

    # Cache miss - compute and store
    result = compute_fn()
    _cache_store[cache_key] = (result, current_mtime_hash, now)
    return result
