"""Health and system metrics endpoint."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.health import collect_health
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/health")
async def get_health(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_health, profile)
