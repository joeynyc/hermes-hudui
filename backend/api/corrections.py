"""Corrections endpoint."""

from fastapi import APIRouter

from backend.collectors.corrections import collect_corrections
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/corrections")
async def get_corrections(profile: str | None = None):
    return collect_with_profile(collect_corrections, profile)
