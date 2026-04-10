"""Agents endpoint."""

from fastapi import APIRouter

from backend.collectors.agents import collect_agents
from .serialize import to_dict
from .profile_scope import resolve_profile_scope

router = APIRouter()


@router.get("/agents")
async def get_agents(profile: str | None = None):
    profile_name, hermes_dir = resolve_profile_scope(profile)
    result = to_dict(collect_agents(hermes_dir, profile_name))
    result["profile"] = profile_name
    return result
