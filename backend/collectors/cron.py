"""Collect Hermes cron job data."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .utils import default_hermes_dir

_NOTEPAD_PREVIEW = 4
_RUN_PREVIEW = 3


@dataclass
class CronNotepadEntry:
    key: str
    value: str
    updated_at: Optional[str] = None


@dataclass
class CronRun:
    id: str
    status: str
    source: str = ""
    claimed_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CronJob:
    id: str
    name: str
    prompt: str
    schedule_display: str
    enabled: bool
    state: str  # scheduled, running, paused, completed
    created_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    deliver: str = "local"
    repeat_total: Optional[int] = None
    repeat_completed: int = 0
    model: Optional[str] = None
    provider: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    paused_reason: Optional[str] = None
    script: Optional[str] = None
    workdir: Optional[str] = None
    continuity: bool = False
    no_agent: bool = False
    monitor_script: Optional[str] = None
    monitor_url: Optional[str] = None
    notepad_count: int = 0
    notepad: list[CronNotepadEntry] = field(default_factory=list)
    recent_runs: list[CronRun] = field(default_factory=list)


@dataclass
class CronState:
    jobs: list[CronJob] = field(default_factory=list)
    updated_at: Optional[str] = None
    output_dir: str = ""

    @property
    def total(self) -> int:
        return len(self.jobs)

    @property
    def active(self) -> int:
        return sum(1 for j in self.jobs if j.enabled and j.state == "scheduled")

    @property
    def paused(self) -> int:
        return sum(1 for j in self.jobs if not j.enabled or j.state == "paused")

    @property
    def has_errors(self) -> bool:
        return any(j.last_error for j in self.jobs)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _context_has_self(value) -> bool:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return False
    return any(str(item).strip().lower() == "self" for item in items)


def _load_notepad(cron_dir: Path) -> dict[str, list[CronNotepadEntry]]:
    path = cron_dir / "notepad.db"
    if not path.exists():
        return {}
    notes: dict[str, list[CronNotepadEntry]] = {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT job_id, key, value, updated_at FROM cron_notepad ORDER BY key"
        ):
            notes.setdefault(str(row["job_id"]), []).append(
                CronNotepadEntry(
                    key=str(row["key"]),
                    value=str(row["value"]),
                    updated_at=row["updated_at"],
                )
            )
        conn.close()
    except sqlite3.Error:
        return {}
    return notes


def _load_runs(cron_dir: Path) -> dict[str, list[CronRun]]:
    path = cron_dir / "executions.db"
    if not path.exists():
        return {}
    runs: dict[str, list[CronRun]] = {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            """SELECT id, job_id, status, source, claimed_at, finished_at, error
               FROM executions
               ORDER BY claimed_at DESC, id DESC"""
        ):
            job_id = str(row["job_id"])
            bucket = runs.setdefault(job_id, [])
            if len(bucket) >= _RUN_PREVIEW:
                continue
            bucket.append(
                CronRun(
                    id=str(row["id"]),
                    status=str(row["status"]),
                    source=str(row["source"] or ""),
                    claimed_at=row["claimed_at"],
                    finished_at=row["finished_at"],
                    error=row["error"],
                )
            )
        conn.close()
    except sqlite3.Error:
        return {}
    return runs


def collect_cron(hermes_dir: str | None = None) -> CronState:
    """Collect cron job data from jobs.json plus notepad/execution ledgers."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    cron_dir = Path(hermes_dir) / "cron"
    jobs_file = cron_dir / "jobs.json"
    output_dir = cron_dir / "output"

    if not jobs_file.exists():
        return CronState()

    try:
        data = json.loads(jobs_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return CronState()

    notepad = _load_notepad(cron_dir)
    runs = _load_runs(cron_dir)
    jobs = []
    for j in data.get("jobs", []):
        repeat = j.get("repeat", {})
        schedule = j.get("schedule", {})
        job_id = j.get("id", "")
        notes = notepad.get(job_id, [])
        jobs.append(CronJob(
            id=job_id,
            name=j.get("name", "unnamed"),
            prompt=j.get("prompt", ""),
            schedule_display=j.get("schedule_display", schedule.get("display", "unknown")),
            enabled=j.get("enabled", True),
            state=j.get("state", "unknown"),
            created_at=j.get("created_at"),
            next_run_at=j.get("next_run_at"),
            last_run_at=j.get("last_run_at"),
            last_status=j.get("last_status"),
            last_error=j.get("last_error"),
            deliver=j.get("deliver", "local"),
            repeat_total=repeat.get("times") if isinstance(repeat, dict) else None,
            repeat_completed=repeat.get("completed", 0) if isinstance(repeat, dict) else 0,
            model=j.get("model"),
            provider=j.get("provider"),
            skills=j.get("skills", []),
            paused_reason=j.get("paused_reason"),
            script=j.get("script"),
            workdir=j.get("workdir"),
            continuity=_as_bool(j.get("continuity")) or _context_has_self(j.get("context_from")),
            no_agent=_as_bool(j.get("no_agent")),
            monitor_script=j.get("monitor_script"),
            monitor_url=j.get("monitor_url"),
            notepad_count=len(notes),
            notepad=notes[:_NOTEPAD_PREVIEW],
            recent_runs=runs.get(job_id, []),
        ))

    return CronState(
        jobs=jobs,
        updated_at=data.get("updated_at"),
        output_dir=str(output_dir),
    )
