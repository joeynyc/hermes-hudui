from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from backend.collectors.sessions import collect_sessions
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/sessions")
async def get_sessions(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_sessions, profile)
