from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from backend.collectors.agents import _get_recent_sessions
from backend.collectors.profiles import collect_profiles
from backend.collectors.sessions import collect_sessions


def _init_state_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            model TEXT,
            model_config TEXT,
            started_at REAL NOT NULL,
            ended_at REAL,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0,
            title TEXT
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            tool_calls TEXT
        )
        '''
    )
    conn.commit()
    conn.close()


def test_collect_sessions_uses_model_column_and_exposes_active_counts(tmp_path: Path):
    db_path = tmp_path / 'state.db'
    _init_state_db(db_path)

    now = time.time()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany(
        '''
        INSERT INTO sessions (
            id, source, model, model_config, started_at, ended_at,
            message_count, tool_call_count,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens,
            estimated_cost_usd, title
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            (
                'sess_cli', 'cli', 'gpt-5.4', None, now - 60, None,
                12, 5,
                1000, 200, 300, 0, 50,
                0.0, 'CLI session',
            ),
            (
                'sess_tg', 'telegram', None, '{"model": "gpt-4o-mini"}', now - 3600, now - 1800,
                4, 1,
                500, 100, 0, 0, 0,
                0.0, 'Telegram session',
            ),
        ],
    )
    cur.execute(
        "INSERT INTO messages (session_id, role, tool_calls) VALUES (?, ?, ?)",
        ('sess_cli', 'assistant', '[{"function":{"name":"read_file"}}]'),
    )
    conn.commit()
    conn.close()

    state = collect_sessions(str(tmp_path))

    assert state.total_sessions == 2
    assert state.active_sessions_count == 1
    assert state.by_source == {'cli': 1, 'telegram': 1}
    assert state.sessions[0].model == 'gpt-5.4'
    assert state.sessions[0].in_flight is True
    assert state.sessions[0].full_token_footprint == 1550
    assert state.sessions[1].model == 'gpt-4o-mini'
    assert state.total_full_tokens == 2150
    assert state.tool_usage == {'read_file': 1}


def test_collect_profiles_marks_profile_active_from_inflight_sessions(tmp_path: Path, monkeypatch):
    (tmp_path / 'config.yaml').write_text(
        '\n'.join([
            'model:',
            '  provider: openai-codex',
            '  base_url: https://chatgpt.com/backend-api/codex',
            '  default: gpt-5.4',
            'display:',
            '  skin: default',
        ]),
        encoding='utf-8',
    )

    db_path = tmp_path / 'state.db'
    _init_state_db(db_path)
    now = time.time()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO sessions (
            id, source, model, started_at, ended_at,
            message_count, tool_call_count, input_tokens, output_tokens,
            cache_read_tokens, cache_write_tokens, reasoning_tokens, estimated_cost_usd, title
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'sess_active', 'cli', 'gpt-5.4', now - 30, None,
            8, 3, 1000, 200,
            100, 0, 20, 0.0, 'Active session',
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr('backend.collectors.profiles._check_gateway_status', lambda name: 'n/a')
    monkeypatch.setattr('backend.collectors.profiles._check_server_status', lambda base_url: 'n/a')

    state = collect_profiles(str(tmp_path))

    assert state.total == 1
    assert state.active_count == 1
    profile = state.profiles[0]
    assert profile.model == 'gpt-5.4'
    assert profile.gateway_status == 'n/a'
    assert profile.activity_status == 'active'
    assert profile.active_session_count == 1
    assert profile.activity_reason == '1 in-flight sessions'


def test_agents_recent_sessions_include_model_and_inflight(tmp_path: Path):
    db_path = tmp_path / 'state.db'
    _init_state_db(db_path)
    now = time.time()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany(
        '''
        INSERT INTO sessions (
            id, source, model, started_at, ended_at,
            message_count, tool_call_count, input_tokens, output_tokens,
            cache_read_tokens, cache_write_tokens, reasoning_tokens, estimated_cost_usd, title
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        [
            (
                'sess_active', 'cli', 'gpt-5.4', now - 20, None,
                0, 0, 0, 0,
                0, 0, 0, 0.0, 'Active',
            ),
            (
                'sess_done', 'cli', 'gpt-4o', now - 120, now - 60,
                0, 0, 0, 0,
                0, 0, 0, 0.0, 'Done',
            ),
        ],
    )
    cur.executemany(
        "INSERT INTO messages (session_id, role, tool_calls) VALUES (?, ?, ?)",
        [
            ('sess_active', 'user', None),
            ('sess_active', 'assistant', '[{"function":{"name":"read_file"}}]'),
            ('sess_done', 'user', None),
        ],
    )
    conn.commit()
    conn.close()

    sessions = _get_recent_sessions(str(tmp_path), limit=2)

    assert sessions[0].session_id == 'sess_active'
    assert sessions[0].model == 'gpt-5.4'
    assert sessions[0].in_flight is True
    assert sessions[1].session_id == 'sess_done'
    assert sessions[1].in_flight is False
