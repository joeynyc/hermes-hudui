"""Snapshot history endpoint for growth delta."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.snapshot import load_snapshots
from .profile_scope import resolve_profile_scope

router = APIRouter()


def _get_snapshots_data(hermes_dir: str):
    return load_snapshots(hermes_dir)


@router.get("/snapshots")
async def get_snapshots(profile: str | None = None):
    """Return all historical snapshots for growth delta display."""
    profile_name, hermes_dir = resolve_profile_scope(profile)
    snapshots = await run_in_threadpool(_get_snapshots_data, hermes_dir)
    return {"snapshots": snapshots, "total": len(snapshots), "profile": profile_name}
