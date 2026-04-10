"""Corrections endpoint."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.corrections import collect_corrections
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/corrections")
async def get_corrections(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_corrections, profile)
