"""Agents endpoint."""

from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/agents")
async def get_agents(profile: str | None = None):
    return collect_with_profile(collect_agents, profile)
