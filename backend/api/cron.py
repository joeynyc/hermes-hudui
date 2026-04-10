"""Cron jobs endpoint."""

from .profile_scope import collect_with_profile

router = APIRouter()


@router.get("/cron")
async def get_cron(profile: str | None = None):
    return collect_with_profile(collect_cron, profile)
