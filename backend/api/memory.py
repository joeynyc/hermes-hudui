"""Memory endpoints."""

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from backend.collectors.memory import collect_memory
from backend.collectors.config import collect_config
from .serialize import to_dict
from .profile_scope import resolve_profile_scope

router = APIRouter()


def _get_memory_data(hermes_dir: str):
    config = collect_config(hermes_dir)
    memory, user = collect_memory(
        hermes_dir,
        memory_char_limit=config.memory_char_limit,
        user_char_limit=config.user_char_limit,
    )
    return to_dict(memory), to_dict(user)


@router.get("/memory")
async def get_memory(profile: str | None = None):
    """Memory and user profile state."""
    profile_name, hermes_dir = resolve_profile_scope(profile)
    memory_data, user_data = await run_in_threadpool(_get_memory_data, hermes_dir)
    return {
        "profile": profile_name,
        "memory": memory_data,
        "user": user_data,
    }
