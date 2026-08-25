"""Snapshot history endpoint for growth delta."""

from fastapi import APIRouter

from backend.collectors.snapshot import load_snapshots

router = APIRouter()


@router.get("/snapshots")
def get_snapshots():
    """Return all historical snapshots for growth delta display."""
    snapshots = load_snapshots()
    return {"snapshots": snapshots, "total": len(snapshots)}
