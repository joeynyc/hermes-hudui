import sqlite3
from pathlib import Path

from backend.collectors.sessions import _do_collect_sessions


def _make_state_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            started_at REAL,
            ended_at REAL,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0,
            model_config TEXT,
            model TEXT,
            parent_session_id TEXT,
            end_reason TEXT,
            profile_name TEXT,
            hidden INTEGER DEFAULT 0,
            pinned INTEGER DEFAULT 0,
            last_activity_at REAL,
            last_activity_description TEXT,
            handoff_state TEXT,
            handoff_platform TEXT,
            billing_provider TEXT,
            git_branch TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
            reasoning TEXT,
            timestamp REAL
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_session(path: Path, **values) -> None:
    defaults = {
        "id": "session",
        "source": "cli",
        "title": None,
        "started_at": 1_700_000_000,
        "ended_at": None,
        "message_count": 1,
        "tool_call_count": 0,
        "input_tokens": 10,
        "output_tokens": 20,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "estimated_cost_usd": 0.0,
        "model_config": None,
        "model": None,
        "parent_session_id": None,
        "end_reason": None,
        "profile_name": None,
        "hidden": 0,
        "pinned": 0,
        "last_activity_at": None,
        "last_activity_description": None,
        "handoff_state": None,
        "handoff_platform": None,
        "billing_provider": None,
        "git_branch": None,
    }
    defaults.update(values)
    columns = ", ".join(defaults)
    placeholders = ", ".join("?" for _ in defaults)
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"INSERT INTO sessions ({columns}) VALUES ({placeholders})",
            list(defaults.values()),
        )


def test_collect_sessions_projects_compression_root_to_tip(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    _insert_session(
        db_path,
        id="root",
        title="Root title",
        started_at=100,
        ended_at=200,
        message_count=3,
        end_reason="compression",
    )
    _insert_session(
        db_path,
        id="tip",
        title="Live continuation",
        started_at=201,
        message_count=7,
        parent_session_id="root",
        model="claude-sonnet-4-6",
    )

    state = _do_collect_sessions(str(db_path))

    assert [session.id for session in state.sessions] == ["tip"]
    assert state.sessions[0].title == "Live continuation"
    assert state.sessions[0].message_count == 7
    assert state.sessions[0].model == "claude-sonnet-4-6"


def test_collect_sessions_filters_internal_tool_source_case_insensitively(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    _insert_session(db_path, id="human", source="telegram", started_at=100)
    _insert_session(db_path, id="tool-lower", source="tool", started_at=101)
    _insert_session(db_path, id="tool-upper", source="TOOL", started_at=102)

    state = _do_collect_sessions(str(db_path))

    assert [session.id for session in state.sessions] == ["human"]
    assert state.daily_stats[0].sessions == 1


def test_collect_sessions_surfaces_current_row_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    _make_state_db(db_path)
    _insert_session(
        db_path,
        id="live",
        title="Live",
        profile_name="work",
        hidden=1,
        pinned=1,
        last_activity_at=1_700_000_100,
        last_activity_description="edited file",
        handoff_state="pending",
        handoff_platform="telegram",
        billing_provider="xai",
        git_branch="main",
        model="grok-4.6",
    )

    session = _do_collect_sessions(str(db_path)).sessions[0]
    assert session.profile_name == "work"
    assert session.hidden is True
    assert session.pinned is True
    assert session.last_activity_description == "edited file"
    assert session.handoff_state == "pending"
    assert session.handoff_platform == "telegram"
    assert session.billing_provider == "xai"
    assert session.git_branch == "main"
    assert session.model == "grok-4.6"
