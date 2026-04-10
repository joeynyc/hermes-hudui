from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from backend.collectors.agents import collect_agents
from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/agents")
async def get_agents(profile: str | None = None):
    return await run_in_threadpool(collect_with_profile, collect_agents, profile)
