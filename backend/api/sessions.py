"""Sessions endpoints."""

from fastapi import APIRouter

from backend.collectors.sessions import collect_sessions
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/sessions")
async def get_sessions(profile: str | None = None):
    return collect_with_profile(collect_sessions, profile)
