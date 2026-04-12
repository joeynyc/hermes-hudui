from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from backend.api import token_costs
from backend.collectors.cron import collect_cron
from backend.collectors.health import collect_health


def _write_jobs(tmp_path: Path, payload: dict) -> None:
    cron_dir = tmp_path / 'cron'
    cron_dir.mkdir(parents=True, exist_ok=True)
    (cron_dir / 'jobs.json').write_text(json.dumps(payload), encoding='utf-8')


def _init_state_db(db_path: Path, *, with_cost_columns: bool = False) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if with_cost_columns:
        cur.execute(
            '''
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                started_at REAL,
                model TEXT,
                message_count INTEGER,
                tool_call_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER,
                cache_write_tokens INTEGER,
                reasoning_tokens INTEGER,
                billing_provider TEXT,
                billing_base_url TEXT,
                billing_mode TEXT,
                estimated_cost_usd REAL,
                actual_cost_usd REAL,
                cost_status TEXT,
                cost_source TEXT,
                pricing_version TEXT
            )
            '''
        )
    else:
        cur.execute(
            '''
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                started_at REAL,
                model TEXT,
                message_count INTEGER,
                tool_call_count INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cache_read_tokens INTEGER,
                cache_write_tokens INTEGER,
                reasoning_tokens INTEGER
            )
            '''
        )
    conn.commit()
    conn.close()


def test_collect_cron_marks_past_next_run_as_overdue(tmp_path: Path):
    _write_jobs(
        tmp_path,
        {
            'jobs': [
                {
                    'id': 'job1',
                    'name': 'demo',
                    'prompt': 'demo prompt',
                    'schedule_display': 'every 180m',
                    'enabled': True,
                    'state': 'scheduled',
                    'created_at': '2026-04-11T11:22:56.819663+09:00',
                    'next_run_at': '2026-04-11T11:23:07.131246+09:00',
                    'last_run_at': None,
                    'deliver': 'origin',
                    'repeat': {'times': 16, 'completed': 0},
                }
            ],
            'updated_at': '2026-04-11T11:23:07.131426+09:00',
        },
    )

    state = collect_cron(str(tmp_path))

    assert len(state.jobs) == 1
    assert state.jobs[0].next_run_status == 'overdue'
    assert state.jobs[0].next_run_overdue is True


def test_collect_health_does_not_flag_missing_keys_for_openai_codex_profile(tmp_path: Path):
    config_text = '\n'.join(
        [
            'model:',
            '  provider: openai-codex',
            '  base_url: https://chatgpt.com/backend-api/codex',
            '  default: gpt-5.4',
        ]
    )
    (tmp_path / 'config.yaml').write_text(config_text, encoding='utf-8')
    (tmp_path / 'state.db').write_text('', encoding='utf-8')

    state = collect_health(str(tmp_path))

    assert state.config_provider == 'openai-codex'
    assert state.keys_missing == 0
    assert state.required_keys_missing == 0


def test_token_costs_marks_openai_codex_rows_as_included_and_computes_api_equivalent(tmp_path: Path, monkeypatch):
    db_path = tmp_path / 'state.db'
    _init_state_db(db_path, with_cost_columns=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO sessions (
            id, source, started_at, model, message_count, tool_call_count,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens,
            billing_provider, billing_base_url, billing_mode,
            estimated_cost_usd, actual_cost_usd, cost_status, cost_source, pricing_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'sess1', 'cli', 1775900000, 'gpt-5.4', 10, 3,
            1_000_000, 50_000, 250_000, 0, 0,
            'openai-codex', 'https://chatgpt.com/backend-api/codex', 'subscription_included',
            0.0, None, 'included', 'none', 'included-route',
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(token_costs, 'default_hermes_dir', lambda: str(tmp_path))

    result = asyncio.run(token_costs.get_token_costs())

    assert result['all_time']['cost_mode'] == 'included'
    assert result['all_time']['cost_badge'] == 'included'
    assert result['all_time']['included_session_count'] == 1
    assert result['by_model'][0]['billing_label'] == 'subscription included'
    assert result['cost_is_partial'] is False
    assert result['cost_summary']['all_sessions_included'] is True
    assert result['all_time']['api_equivalent_available'] is True
    assert result['all_time']['api_equivalent_lower_usd'] == 3.31
    assert result['all_time']['api_equivalent_upper_usd'] == 6.25
    assert result['all_time']['api_equivalent_badge'] == '$3.31–$6.25'


def test_token_costs_falls_back_to_reference_pricing_for_legacy_rows(tmp_path: Path, monkeypatch):
    db_path = tmp_path / 'state.db'
    _init_state_db(db_path, with_cost_columns=False)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO sessions (
            id, source, started_at, model, message_count, tool_call_count,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'sess1', 'cli', 1775900000, 'gpt-4o', 10, 3,
            1_000_000, 50_000, 250_000, 0, 0,
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(token_costs, 'default_hermes_dir', lambda: str(tmp_path))

    result = asyncio.run(token_costs.get_token_costs())

    assert result['all_time']['cost_mode'] == 'estimated'
    assert result['all_time']['tracked_cost_usd'] == 3.31
    assert result['all_time']['derived_session_count'] == 1
    assert result['cost_summary']['has_fallback_estimates'] is True
    assert result['by_model'][0]['billing_label'].startswith('fallback estimate')
    assert result['all_time']['api_equivalent_available'] is False


def test_token_costs_keeps_truly_unpriced_legacy_models_unknown(tmp_path: Path, monkeypatch):
    db_path = tmp_path / 'state.db'
    _init_state_db(db_path, with_cost_columns=False)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO sessions (
            id, source, started_at, model, message_count, tool_call_count,
            input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'sess1', 'cli', 1775900000, 'gpt-5.9-unknown', 10, 3,
            1_000_000, 50_000, 250_000, 0, 0,
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(token_costs, 'default_hermes_dir', lambda: str(tmp_path))

    result = asyncio.run(token_costs.get_token_costs())

    assert result['by_model'][0]['model'] == 'gpt-5.9-unknown'
    assert result['by_model'][0]['cost_mode'] == 'unknown'
    assert result['by_model'][0]['cost_badge'] == 'n/a'
    assert result['all_time']['tracked_cost_usd'] == 0.0
    assert result['cost_is_partial'] is True
    assert result['all_time']['api_equivalent_available'] is False
