"""Timeline endpoint — chronological session list."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.collect import collect_all
from .profile_scope import resolve_profile_scope
from .serialize import to_dict

router = APIRouter()


def _get_timeline_data(hermes_dir: str):
    """Sync helper to get full state and extract timeline."""
    state = collect_all(hermes_dir)
    return to_dict(state.timeline)


@router.get("/timeline")
async def get_timeline(profile: str | None = None):
    profile_name, hermes_dir = resolve_profile_scope(profile)
    timeline_data = await run_in_threadpool(_get_timeline_data, hermes_dir)
    return {
        "profile": profile_name,
        "timeline": timeline_data
    }
