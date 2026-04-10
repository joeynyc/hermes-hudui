"""Timeline endpoint — chronological session list."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.timeline import collect_timeline
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/timeline")
async def get_timeline(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_timeline, profile)
