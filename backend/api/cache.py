"""Cache management endpoints."""

from fastapi import APIRouter

from backend.cache import get_cache_stats, clear_cache

router = APIRouter()


@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics for monitoring."""
    return get_cache_stats()


@router.post("/cache/clear")
async def cache_clear():
    """Clear all caches. Returns count of entries cleared."""
    count = clear_cache()
    return {"cleared": count}
