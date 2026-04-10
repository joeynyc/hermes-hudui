"""Collect session data from Hermes state.db."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from ..cache import get_cached_or_compute
from .models import DailyStats, SessionInfo, SessionsState
from .utils import default_hermes_dir, safe_get


def _extract_tool_usage(db_path: str) -> dict[str, int]:
    """Extract tool usage counts from tool_calls JSON in messages."""
    usage: dict[str, int] = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tool_calls FROM messages WHERE tool_calls IS NOT NULL AND tool_calls != ''"
        )
        for (tc_json,) in cursor.fetchall():
            try:
                calls = json.loads(tc_json)
                if isinstance(calls, list):
                    for call in calls:
                        fn = call.get("function", {})
                        name = fn.get("name", "unknown")
                        usage[name] = usage.get(name, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        conn.close()
    except Exception:
        logger.debug("Could not read tool usage from state.db", exc_info=True)
    return usage


def _do_collect_sessions(db_path: str) -> SessionsState:
    """Actually read sessions from SQLite (internal, uncached)."""
    sessions: list[SessionInfo] = []
    daily_stats: list[DailyStats] = []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch all sessions
        cursor.execute("""
            SELECT id, source, title, started_at, ended_at,
                   message_count, tool_call_count,
                   input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens,
                   reasoning_tokens, estimated_cost_usd, model_config
            FROM sessions
            ORDER BY started_at DESC
        """)

        for row in cursor.fetchall():
            try:
                started_raw = safe_get(row, "started_at", 0)
                started = datetime.fromtimestamp(started_raw)
                ended_raw = safe_get(row, "ended_at")
                ended = datetime.fromtimestamp(ended_raw) if ended_raw else None

                # Try to extract model from model_config JSON
                model = None
                mc_raw = safe_get(row, "model_config")
                if mc_raw:
                    try:
                        mc = json.loads(mc_raw)
                        model = mc.get("model") or mc.get("default")
                    except (json.JSONDecodeError, TypeError):
                        pass

                sessions.append(
                    SessionInfo(
                        id=safe_get(row, "id", ""),
                        source=safe_get(row, "source", "unknown"),
                        title=safe_get(row, "title"),
                        started_at=started,
                        ended_at=ended,
                        message_count=safe_get(row, "message_count", 0),
                        tool_call_count=safe_get(row, "tool_call_count", 0),
                        input_tokens=safe_get(row, "input_tokens", 0),
                        output_tokens=safe_get(row, "output_tokens", 0),
                        cache_read_tokens=safe_get(row, "cache_read_tokens", 0),
                        cache_write_tokens=safe_get(row, "cache_write_tokens", 0),
                        reasoning_tokens=safe_get(row, "reasoning_tokens", 0),
                        estimated_cost_usd=safe_get(row, "estimated_cost_usd", 0.0),
                        model=model,
                    )
                )
            except Exception:
                logger.warning("Skipping unparseable session row", exc_info=True)
                continue

        # Daily stats
        cursor.execute("""
            SELECT date(started_at, 'unixepoch') as day,
                   COUNT(*) as sessions,
                   SUM(message_count) as msgs,
                   SUM(tool_call_count) as tools,
                   SUM(input_tokens + output_tokens) as tokens
            FROM sessions
            GROUP BY day
            ORDER BY day
        """)

        for row in cursor.fetchall():
            try:
                daily_stats.append(
                    DailyStats(
                        date=safe_get(row, "day", ""),
                        sessions=safe_get(row, "sessions", 0),
                        messages=safe_get(row, "msgs", 0),
                        tool_calls=safe_get(row, "tools", 0),
                        tokens=safe_get(row, "tokens", 0),
                    )
                )
            except Exception:
                logger.warning("Skipping unparseable daily stats row", exc_info=True)
                continue

        conn.close()
    except Exception:
        logger.warning("Error reading sessions from state.db", exc_info=True)

    # Tool usage
    tool_usage = _extract_tool_usage(db_path)

    return SessionsState(
        sessions=sessions,
        daily_stats=daily_stats,
        tool_usage=tool_usage,
    )


def collect_sessions(hermes_dir: str | None = None) -> SessionsState:
    """Collect session data from state.db (cached, invalidates on db change)."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    db_path = Path(hermes_dir) / "state.db"
    if not db_path.exists():
        return SessionsState()

    return get_cached_or_compute(
        cache_key=f"sessions:{hermes_dir}",
        compute_fn=lambda: _do_collect_sessions(str(db_path)),
        file_paths=[db_path],
        ttl=30,  # 30 second cache even if file unchanged
    )
