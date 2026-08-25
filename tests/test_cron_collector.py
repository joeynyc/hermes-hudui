import json
import sqlite3
from pathlib import Path

from backend.collectors.cron import collect_cron


def test_collect_cron_reads_020_fields_and_sidecars(tmp_path: Path) -> None:
    cron_dir = tmp_path / "cron"
    cron_dir.mkdir()
    (cron_dir / "jobs.json").write_text(
        json.dumps({
            "updated_at": "2026-08-25T00:00:00Z",
            "jobs": [{
                "id": "job-1",
                "name": "digest",
                "prompt": "summarize",
                "schedule_display": "30m",
                "enabled": True,
                "state": "scheduled",
                "deliver": "local",
                "model": "grok-4.6",
                "provider": "xai",
                "continuity": True,
                "no_agent": False,
                "monitor_url": "https://example.com/status",
                "repeat": {"times": 5, "completed": 1},
            }],
        }),
        encoding="utf-8",
    )

    notepad = sqlite3.connect(cron_dir / "notepad.db")
    notepad.execute(
        """CREATE TABLE cron_notepad (
             job_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
             updated_at TEXT NOT NULL, PRIMARY KEY (job_id, key)
           )"""
    )
    notepad.execute(
        "INSERT INTO cron_notepad VALUES (?, ?, ?, ?)",
        ("job-1", "cursor", "42", "2026-08-25T00:00:00Z"),
    )
    notepad.commit()
    notepad.close()

    runs = sqlite3.connect(cron_dir / "executions.db")
    runs.execute(
        """CREATE TABLE executions (
             id TEXT PRIMARY KEY, job_id TEXT NOT NULL, source TEXT NOT NULL,
             process_id TEXT NOT NULL, pid INTEGER NOT NULL,
             status TEXT NOT NULL, claimed_at TEXT NOT NULL,
             finished_at TEXT, error TEXT
           )"""
    )
    runs.execute(
        """INSERT INTO executions
           (id, job_id, source, process_id, pid, status, claimed_at, finished_at, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("run-1", "job-1", "tick", "p", 1, "completed", "2026-08-25T01:00:00Z", "2026-08-25T01:01:00Z", None),
    )
    runs.commit()
    runs.close()

    state = collect_cron(str(tmp_path))
    job = state.jobs[0]
    assert job.continuity is True
    assert job.model == "grok-4.6"
    assert job.provider == "xai"
    assert job.monitor_url == "https://example.com/status"
    assert job.notepad_count == 1
    assert job.notepad[0].key == "cursor"
    assert job.recent_runs[0].status == "completed"


def test_collect_cron_treats_context_from_self_as_continuity(tmp_path: Path) -> None:
    cron_dir = tmp_path / "cron"
    cron_dir.mkdir()
    (cron_dir / "jobs.json").write_text(
        json.dumps({
            "jobs": [{
                "id": "job-2",
                "name": "loop",
                "prompt": "again",
                "enabled": True,
                "state": "scheduled",
                "context_from": ["self"],
            }],
        }),
        encoding="utf-8",
    )
    assert collect_cron(str(tmp_path)).jobs[0].continuity is True
