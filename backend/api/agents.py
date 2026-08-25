"""Agents endpoint."""

from fastapi import APIRouter

from backend.collectors.agents import collect_agents
from .serialize import to_dict

router = APIRouter()


@router.get("/agents")
def get_agents():
    return to_dict(collect_agents())
