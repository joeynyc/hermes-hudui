from __future__ import annotations

import json
from pathlib import Path

from backend.collectors.cron import collect_cron
from backend.collectors.health import collect_health


def _write_jobs(tmp_path: Path, payload: dict) -> None:
    cron_dir = tmp_path / 'cron'
    cron_dir.mkdir(parents=True, exist_ok=True)
    (cron_dir / 'jobs.json').write_text(json.dumps(payload), encoding='utf-8')


def test_collect_health_marks_systemd_unavailable_on_macos_openai_codex(tmp_path: Path, monkeypatch):
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

    monkeypatch.setattr('backend.collectors.health._check_process', lambda name, pattern, required=False: __import__('backend.collectors.health', fromlist=['ServiceStatus']).ServiceStatus(name=name, status='stopped', running=False, required=required, note='not running'))

    state = collect_health(str(tmp_path))

    systemd = next(service for service in state.services if service.name == 'Gateway (systemd)')
    llama = next(service for service in state.services if service.name == 'llama-server')

    assert state.config_provider == 'openai-codex'
    assert state.required_keys_missing == 0
    assert systemd.status == 'unavailable'
    assert systemd.required is False
    assert llama.required is False
    assert state.required_services_missing == 0


def test_collect_health_requires_local_model_server_for_local_provider(tmp_path: Path):
    config_text = '\n'.join(
        [
            'model:',
            '  provider: custom',
            '  base_url: http://localhost:11434/v1',
            '  default: local-model',
        ]
    )
    (tmp_path / 'config.yaml').write_text(config_text, encoding='utf-8')
    (tmp_path / 'state.db').write_text('', encoding='utf-8')

    state = collect_health(str(tmp_path))

    llama = next(service for service in state.services if service.name == 'llama-server')
    assert llama.required is True
    assert llama.status in {'running', 'stopped', 'check_failed'}


def test_collect_cron_counts_overdue_and_never_ran_jobs(tmp_path: Path):
    _write_jobs(
        tmp_path,
        {
            'jobs': [
                {
                    'id': 'job1',
                    'name': 'overdue-never-run',
                    'prompt': 'demo prompt',
                    'schedule_display': 'every 180m',
                    'enabled': True,
                    'state': 'scheduled',
                    'created_at': '2026-04-11T11:22:56.819663+09:00',
                    'next_run_at': '2026-04-11T11:23:07.131246+09:00',
                    'last_run_at': None,
                    'deliver': 'origin',
                    'repeat': {'times': 16, 'completed': 0},
                },
                {
                    'id': 'job2',
                    'name': 'paused-job',
                    'prompt': 'demo prompt',
                    'schedule_display': '0 9 * * *',
                    'enabled': False,
                    'state': 'paused',
                    'created_at': '2026-04-11T11:22:56.819663+09:00',
                    'next_run_at': None,
                    'last_run_at': '2026-04-11T10:23:07.131246+09:00',
                    'last_status': 'ok',
                    'deliver': 'origin',
                    'repeat': {'times': 16, 'completed': 1},
                },
            ],
            'updated_at': '2026-04-11T11:23:07.131426+09:00',
        },
    )

    state = collect_cron(str(tmp_path))

    assert state.total == 2
    assert state.active == 1
    assert state.overdue == 1
    assert state.never_ran == 1
    assert state.running == 0
    assert state.failed == 0
    assert state.jobs[0].next_run_status == 'overdue'
    assert state.jobs[0].never_ran is True
