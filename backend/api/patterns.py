"""Prompt patterns endpoint."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.patterns import collect_patterns
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/patterns")
async def get_patterns(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_patterns, profile)
