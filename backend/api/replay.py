"""Replay endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.serialize import to_dict
from backend.collectors.replay import get_replay_detail, list_replay_runs
from backend.services.replay_exporter import (
    export_clip_html,
    export_fork_json,
    export_html,
    export_json,
    export_markdown,
    export_share_card_png,
    get_replay_gallery,
    get_replay_settings,
    get_skill_provenance_index,
    publish_replay,
    record_gallery_view,
    unpublish_replay,
    update_replay_settings,
)
from backend.services.replay_publisher import (
    PublishError,
    remote_status,
    sync_remote,
    update_remote_settings,
)
from backend.services.replay_redactor import apply_manual_redactions, scan_replay
from backend.services.replay_verifier import verify_replay_files

router = APIRouter()


class ManualRedactionRule(BaseModel):
    value: str = Field(default="", max_length=5000)
    replacement: str = Field(default="[REDACTED_CUSTOM]", max_length=200)


class ManualRedactionRequest(BaseModel):
    redactions: list[ManualRedactionRule] = Field(default_factory=list, max_length=100)


class ReplaySettingsRequest(BaseModel):
    safe_share_mode: bool = True
    include_raw_logs: bool = False
    include_screenshots: bool = False


class ReplayVerifyRequest(BaseModel):
    receipt_path: str = Field(min_length=1, max_length=4096)
    replay_path: str = Field(min_length=1, max_length=4096)


class ReplayPublishRequest(BaseModel):
    visibility: str = "unlisted"


class ReplayRemoteSettingsRequest(BaseModel):
    enabled: bool = False
    repo: str = Field(default="", max_length=300)
    branch: str = Field(default="gh-pages", max_length=100)
    base_url: str = Field(default="", max_length=300)


@router.get("/replay/runs")
def get_replay_runs(limit: int = Query(50, ge=1, le=500)):
    return {"runs": to_dict(list_replay_runs(limit=limit))}


@router.get("/replay/settings")
def get_settings():
    return get_replay_settings()


@router.get("/replay/skills")
def get_replay_skills():
    return get_skill_provenance_index()


@router.get("/replay/gallery")
def get_gallery():
    return get_replay_gallery()


@router.put("/replay/settings")
def put_settings(request: ReplaySettingsRequest):
    return update_replay_settings(request.model_dump())


@router.post("/replay/verify")
def verify_replay(request: ReplayVerifyRequest):
    return verify_replay_files(request.receipt_path, request.replay_path)


@router.get("/replay/remote")
def get_remote():
    return remote_status()


@router.put("/replay/remote")
def put_remote(request: ReplayRemoteSettingsRequest):
    update_remote_settings(request.model_dump())
    return remote_status()


@router.post("/replay/remote/sync")
def sync_remote_gallery():
    try:
        return sync_remote()
    except PublishError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/replay/runs/{session_id}")
def get_replay_run(session_id: str):
    replay = get_replay_detail(session_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return to_dict(replay)


def _detail_or_404(session_id: str):
    replay = get_replay_detail(session_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return replay


@router.post("/replay/runs/{session_id}/build")
def build_replay_run(session_id: str):
    return to_dict(_detail_or_404(session_id))


@router.post("/replay/runs/{session_id}/redact/scan")
def scan_replay_run(session_id: str):
    return to_dict(scan_replay(_detail_or_404(session_id)))


@router.post("/replay/runs/{session_id}/redact/apply")
def apply_replay_redactions(session_id: str, request: ManualRedactionRequest | None = None):
    rules = [rule.model_dump() for rule in request.redactions] if request else []
    return to_dict(apply_manual_redactions(_detail_or_404(session_id), rules))


@router.post("/replay/runs/{session_id}/export/json")
def export_replay_json(session_id: str):
    return to_dict(export_json(_detail_or_404(session_id)))


@router.post("/replay/runs/{session_id}/export/markdown")
def export_replay_markdown(session_id: str):
    return to_dict(export_markdown(_detail_or_404(session_id)))


@router.post("/replay/runs/{session_id}/export/html")
def export_replay_html(session_id: str):
    return to_dict(export_html(_detail_or_404(session_id)))


@router.post("/replay/runs/{session_id}/fork")
def export_replay_fork(session_id: str):
    return to_dict(export_fork_json(_detail_or_404(session_id)))


@router.post("/replay/runs/{session_id}/share-card")
def export_replay_share_card(session_id: str, card_format: str = Query("wide", pattern="^(wide|landscape|square|story)$")):
    try:
        return to_dict(export_share_card_png(_detail_or_404(session_id), card_format=card_format))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/replay/runs/{session_id}/clip")
def export_replay_clip(session_id: str):
    return to_dict(export_clip_html(_detail_or_404(session_id)))


@router.post("/replay/runs/{session_id}/publish")
def publish_replay_run(session_id: str, request: ReplayPublishRequest | None = None):
    visibility = request.visibility if request else "unlisted"
    return to_dict(publish_replay(_detail_or_404(session_id), visibility=visibility))


@router.delete("/replay/runs/{session_id}/publish")
def unpublish_replay_run(session_id: str, request: ReplayPublishRequest | None = None):
    visibility = request.visibility if request else "unlisted"
    return to_dict(unpublish_replay(_detail_or_404(session_id), visibility=visibility))


@router.post("/replay/runs/{session_id}/view")
def record_replay_view(session_id: str, request: ReplayPublishRequest | None = None):
    visibility = request.visibility if request else "unlisted"
    return to_dict(record_gallery_view(_detail_or_404(session_id), visibility=visibility))
