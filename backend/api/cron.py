"""Cron jobs endpoints."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.collectors.cron import collect_cron

from .serialize import to_dict

router = APIRouter()

_HERMES_BIN: str | None = shutil.which("hermes")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def _hermes() -> str:
    if not _HERMES_BIN:
        raise HTTPException(status_code=503, detail="hermes CLI not found")
    return _HERMES_BIN


def _run(action: str, job_id: str) -> None:
    if not _JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(status_code=400, detail="invalid cron job id")
    result = subprocess.run(
        [_hermes(), "cron", action, "--", job_id],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or f"hermes cron {action} failed"
        raise HTTPException(status_code=500, detail=detail)


class CreateCronBody(BaseModel):
    schedule: str = Field(min_length=1, max_length=256)
    prompt: str | None = Field(default=None, max_length=50_000)
    name: str | None = Field(default=None, max_length=200)
    deliver: str | None = Field(default=None, max_length=500)
    repeat: int | None = None
    skills: list[str] = Field(default_factory=list, max_length=64)
    script: str | None = Field(default=None, max_length=1024)
    workdir: str | None = Field(default=None, max_length=4096)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _reject_nul(label: str, value: str | None) -> None:
    if value is not None and "\x00" in value:
        raise HTTPException(
            status_code=400,
            detail=f"{label} contains an invalid character",
        )


def _run_create(body: CreateCronBody) -> None:
    schedule = _clean_optional(body.schedule)
    if not schedule:
        raise HTTPException(status_code=400, detail="schedule cannot be empty")

    prompt = _clean_optional(body.prompt)
    name = _clean_optional(body.name)
    deliver = _clean_optional(body.deliver)
    script = _clean_optional(body.script)
    workdir = _clean_optional(body.workdir)
    skills = [skill.strip() for skill in body.skills if skill.strip()]

    for label, value in (
        ("schedule", schedule),
        ("prompt", prompt),
        ("name", name),
        ("deliver", deliver),
        ("script", script),
        ("workdir", workdir),
    ):
        _reject_nul(label, value)
    for skill in skills:
        _reject_nul("skill", skill)
        if len(skill) > 200:
            raise HTTPException(status_code=400, detail="skill name is too long")

    if body.repeat is not None and body.repeat < 1:
        raise HTTPException(status_code=400, detail="repeat must be a positive integer")

    if workdir and not Path(workdir).is_absolute():
        raise HTTPException(status_code=400, detail="workdir must be an absolute path")

    cmd = [_hermes(), "cron", "create"]
    if name:
        cmd.append(f"--name={name}")
    if deliver:
        cmd.append(f"--deliver={deliver}")
    if body.repeat is not None:
        cmd.append(f"--repeat={body.repeat}")
    for skill in skills:
        cmd.append(f"--skill={skill}")
    if script:
        cmd.append(f"--script={script}")
    if workdir:
        cmd.append(f"--workdir={workdir}")
    # Explicitly terminate option parsing before user-controlled positionals.
    cmd.extend(["--", schedule])
    if prompt:
        cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or "hermes cron create failed"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/cron")
async def get_cron():
    return to_dict(collect_cron())


@router.post("/cron")
def create_job(body: CreateCronBody):
    # Trust boundary: creating cron jobs can schedule Hermes to run in arbitrary workdirs.
    # Keep this HUD API bound to trusted localhost-only access.
    _run_create(body)
    return {"status": "ok"}


@router.post("/cron/{job_id}/pause")
def pause_job(job_id: str):
    _run("pause", job_id)
    return {"status": "ok"}


@router.post("/cron/{job_id}/resume")
def resume_job(job_id: str):
    _run("resume", job_id)
    return {"status": "ok"}


@router.post("/cron/{job_id}/run")
def run_job(job_id: str):
    _run("run", job_id)
    return {"status": "ok"}


@router.delete("/cron/{job_id}")
def delete_job(job_id: str):
    _run("remove", job_id)
    return {"status": "ok"}
