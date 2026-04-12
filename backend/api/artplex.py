"""ARTPLEX operations endpoint."""

from fastapi import APIRouter

from backend.collectors.artplex_ops import collect_artplex_ops
from .serialize import to_dict

router = APIRouter()


@router.get("/artplex")
async def get_artplex():
    return to_dict(collect_artplex_ops())
