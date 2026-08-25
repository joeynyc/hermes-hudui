"""Collect session data from Hermes state.db."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from ..cache import get_cached_or_compute
from .models import DailyStats, SessionInfo, SessionsState
from .utils import default_hermes_dir, safe_get

SESSION_LIST_LIMIT = 500
TOOL_USAGE_MESSAGE_LIMIT = 10_000


def _extract_tool_usage(
    db_path: str, message_limit: int = TOOL_USAGE_MESSAGE_LIMIT
) -> dict[str, int]:
    """Extract recent tool usage without loading the full messages table."""
    usage: dict[str, int] = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT tool_calls
               FROM messages
               WHERE tool_calls IS NOT NULL AND tool_calls != ''
               ORDER BY timestamp DESC
               LIMIT ?""",
            (message_limit,),
        )
        for (tc_json,) in cursor:
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


def _table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    """Return the column names for a SQLite table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cursor.fetchall()}


def _optional_column(columns: set[str], name: str, default: str = "NULL") -> str:
    return name if name in columns else f"{default} AS {name}"


def _human_session_where(columns: set[str]) -> str:
    """Filter to user-facing sessions, matching Hermes' current deny-list."""
    clauses = ["LOWER(COALESCE(source, '')) != 'tool'"]
    if {"parent_session_id", "end_reason"}.issubset(columns):
        clauses.append("""
            (
              parent_session_id IS NULL
              OR EXISTS (
                  SELECT 1 FROM sessions p
                  WHERE p.id = sessions.parent_session_id
                    AND p.end_reason = 'branched'
                    AND sessions.started_at >= p.ended_at
              )
            )
        """)
    return " AND ".join(clauses)


def _compression_tip(conn: sqlite3.Connection, session_id: str) -> str:
    """Mirror Hermes' compression-chain projection for session lists."""
    current = session_id
    for _ in range(100):
        row = conn.execute(
            """SELECT child.id
               FROM sessions parent
               JOIN sessions child ON child.parent_session_id = parent.id
               WHERE parent.id = ?
                 AND parent.end_reason = 'compression'
                 AND child.started_at >= COALESCE(parent.ended_at, 0)
               ORDER BY child.started_at DESC
               LIMIT 1""",
            (current,),
        ).fetchone()
        if row is None:
            return current
        current = row["id"]
    return current


def _parse_model(row: sqlite3.Row) -> str | None:
    """Prefer Hermes' direct model column, falling back to old model_config JSON."""
    model = safe_get(row, "model")
    if model:
        return model

    mc_raw = safe_get(row, "model_config")
    if mc_raw:
        try:
            mc = json.loads(mc_raw)
            return mc.get("model") or mc.get("default")
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _session_from_row(row: sqlite3.Row) -> SessionInfo:
    started_raw = safe_get(row, "started_at", 0)
    started = datetime.fromtimestamp(started_raw)
    ended_raw = safe_get(row, "ended_at")
    ended = datetime.fromtimestamp(ended_raw) if ended_raw else None

    return SessionInfo(
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
        model=_parse_model(row),
    )


def _do_collect_sessions(
    db_path: str, session_limit: int = SESSION_LIST_LIMIT
) -> SessionsState:
    """Actually read sessions from SQLite (internal, uncached)."""
    sessions: list[SessionInfo] = []
    daily_stats: list[DailyStats] = []
    aggregate_by_source: dict[str, int] = {}
    earliest_started_at: datetime | None = None
    latest_started_at: datetime | None = None

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        columns = _table_columns(cursor, "sessions")
        human_session_where = _human_session_where(columns)

        cursor.execute(
            """
            SELECT id, source, title, started_at, ended_at,
                   message_count, tool_call_count,
                   input_tokens, output_tokens,
                   cache_read_tokens, cache_write_tokens,
                   reasoning_tokens, estimated_cost_usd, model_config,
                   {model},
                   {parent_session_id},
                   {end_reason}
            FROM sessions
            WHERE {human_session_where}
            ORDER BY started_at DESC
            LIMIT ?
        """.format(
                model=_optional_column(columns, "model"),
                parent_session_id=_optional_column(columns, "parent_session_id"),
                end_reason=_optional_column(columns, "end_reason"),
                human_session_where=human_session_where,
            ),
            (session_limit,),
        )

        for row in cursor.fetchall():
            try:
                if safe_get(row, "end_reason") == "compression":
                    tip_id = _compression_tip(conn, safe_get(row, "id", ""))
                    if tip_id != safe_get(row, "id", ""):
                        tip = conn.execute(
                            """
                            SELECT id, source, title, started_at, ended_at,
                                   message_count, tool_call_count,
                                   input_tokens, output_tokens,
                                   cache_read_tokens, cache_write_tokens,
                                   reasoning_tokens, estimated_cost_usd,
                                   model_config,
                                   {model},
                                   {parent_session_id},
                                   {end_reason}
                            FROM sessions
                            WHERE id = ?
                            """.format(
                                model=_optional_column(columns, "model"),
                                parent_session_id=_optional_column(
                                    columns, "parent_session_id"
                                ),
                                end_reason=_optional_column(columns, "end_reason"),
                            ),
                            (tip_id,),
                        ).fetchone()
                        if tip:
                            row = tip

                sessions.append(_session_from_row(row))
            except Exception:
                logger.warning("Skipping unparseable session row", exc_info=True)
                continue

        cursor.execute(
            """
            SELECT source, COUNT(*) AS count,
                   MIN(started_at) AS earliest_started_at,
                   MAX(started_at) AS latest_started_at
            FROM sessions
            WHERE {human_session_where}
            GROUP BY source
        """.format(human_session_where=human_session_where)
        )
        for row in cursor.fetchall():
            source = safe_get(row, "source", "unknown")
            aggregate_by_source[source] = safe_get(row, "count", 0)
            earliest = safe_get(row, "earliest_started_at")
            latest = safe_get(row, "latest_started_at")
            if earliest:
                parsed = datetime.fromtimestamp(earliest)
                earliest_started_at = (
                    parsed
                    if earliest_started_at is None
                    else min(earliest_started_at, parsed)
                )
            if latest:
                parsed = datetime.fromtimestamp(latest)
                latest_started_at = (
                    parsed
                    if latest_started_at is None
                    else max(latest_started_at, parsed)
                )

        # Daily stats
        cursor.execute(
            """
            SELECT date(started_at, 'unixepoch') as day,
                   COUNT(*) as sessions,
                   SUM(message_count) as msgs,
                   SUM(tool_call_count) as tools,
                   SUM(input_tokens + output_tokens) as tokens
            FROM sessions
            WHERE {human_session_where}
            GROUP BY day
            ORDER BY day
        """.format(human_session_where=human_session_where)
        )

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
        aggregate_by_source=aggregate_by_source,
        earliest_started_at=earliest_started_at,
        latest_started_at=latest_started_at,
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
