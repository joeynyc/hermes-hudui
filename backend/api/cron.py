"""Cron jobs endpoints."""

from __future__ import annotations

import shutil
import subprocess

from fastapi import APIRouter, HTTPException

from backend.collectors.cron import collect_cron
from .serialize import to_dict

router = APIRouter()


def _hermes() -> str:
    path = shutil.which("hermes")
    if not path:
        raise HTTPException(status_code=503, detail="hermes CLI not found")
    return path


def _run(action: str, job_id: str) -> None:
    result = subprocess.run(
        [_hermes(), "cron", action, job_id],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() or f"hermes cron {action} failed"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/cron")
async def get_cron():
    return to_dict(collect_cron())


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
