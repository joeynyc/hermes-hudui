"""Model-info endpoint."""

from fastapi import APIRouter

from backend.collectors.model_analytics import collect_model_analytics
from backend.collectors.model_info import collect_model_info
from .serialize import to_dict

router = APIRouter()


@router.get("/model-info")
def get_model_info():
    return to_dict(collect_model_info())


@router.get("/model-analytics")
def get_model_analytics(days: int = 30):
    period = None if days <= 0 else days
    return to_dict(collect_model_analytics(days=period))
