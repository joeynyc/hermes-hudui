"""Profiles endpoints."""

from __future__ import annotations

import fcntl
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.cache import clear_cache
from backend.collectors.profiles import collect_profiles
from backend.collectors.utils import default_hermes_dir, load_yaml
from .serialize import to_dict

router = APIRouter()

PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")

PROVIDER_OPTIONS = [
    "openai-codex",
    "anthropic",
    "openrouter",
    "zai",
    "google",
    "xai",
    "minimax",
    "custom",
]

PROVIDER_PRESETS = {
    "minimax": {
        "display_name": "MiniMax",
        "models": [
            {
                "id": "MiniMax-M3",
                "context_window": 1_000_000,
                "input_modalities": ["text", "image", "video"],
                "thinking": ["adaptive", "disabled"],
            },
            {
                "id": "MiniMax-M2.7",
                "context_window": 204_800,
                "input_modalities": ["text"],
                "thinking": ["always_on"],
            },
        ],
        "endpoints": [
            {
                "region": "global_en",
                "openai_base_url": "https://api.minimax.io/v1",
                "anthropic_base_url": "https://api.minimax.io/anthropic/v1",
                "docs_root": "https://platform.minimax.io/docs",
            },
            {
                "region": "cn_zh",
                "openai_base_url": "https://api.minimaxi.com/v1",
                "anthropic_base_url": "https://api.minimaxi.com/anthropic/v1",
                "docs_root": "https://platform.minimaxi.com/docs",
            },
        ],
    },
}

TOOLSET_OPTIONS = [
    "hermes-cli",
    "web",
    "browser",
    "terminal",
    "file",
    "code_execution",
    "vision",
    "image_gen",
    "skills",
    "todo",
    "memory",
    "session_search",
    "clarify",
    "delegation",
    "cronjob",
    "messaging",
]


class ProfileModelEdit(BaseModel):
    provider: str = ""
    default: str = ""
    base_url: str = ""
    api_mode: str = ""
    context_length: int | None = None


class ProfileCompressionEdit(BaseModel):
    enabled: bool = False
    summary_provider: str = ""
    summary_model: str = ""


class ProfileEditBody(BaseModel):
    model: ProfileModelEdit = Field(default_factory=ProfileModelEdit)
    toolsets: list[str] = Field(default_factory=list)
    skin: str = ""
    compression: ProfileCompressionEdit = Field(default_factory=ProfileCompressionEdit)
    soul: str = ""


def _profile_dir(profile_name: str) -> Path:
    hermes_dir = Path(default_hermes_dir())
    if profile_name == "default":
        return hermes_dir
    if not PROFILE_NAME_RE.match(profile_name) or profile_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="invalid profile name")
    path = hermes_dir / "profiles" / profile_name
    try:
        path.relative_to(hermes_dir / "profiles")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid profile name") from None
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="profile not found")
    return path


def _read_config(profile_dir: Path) -> dict[str, Any]:
    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        data = load_yaml(config_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except OSError:
        raise HTTPException(status_code=500, detail="failed to read config.yaml") from None


def _read_soul(profile_dir: Path) -> str:
    soul_path = profile_dir / "SOUL.md"
    if not soul_path.exists():
        return ""
    try:
        return soul_path.read_text(encoding="utf-8")
    except OSError:
        raise HTTPException(status_code=500, detail="failed to read SOUL.md") from None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else None
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=f".{path.name}_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _with_profile_lock(profile_dir: Path, fn):
    lock_path = profile_dir / ".hud-profile-edit.lock"
    lock_path.touch(exist_ok=True)
    with open(lock_path, "r", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return fn()


def _clean_list(values: list[str]) -> list[str]:
    seen = set()
    cleaned = []
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def _clean_model(body: ProfileModelEdit) -> dict[str, Any]:
    model: dict[str, Any] = {}
    provider = body.provider.strip()
    default = body.default.strip()
    base_url = body.base_url.strip()
    api_mode = body.api_mode.strip()

    if base_url and not (base_url.startswith("http://") or base_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="base_url must start with http:// or https://")
    if body.context_length is not None and body.context_length < 1:
        raise HTTPException(status_code=400, detail="context_length must be a positive integer")

    if provider:
        model["provider"] = provider
    if default:
        model["default"] = default
    if base_url:
        model["base_url"] = base_url
    if api_mode:
        model["api_mode"] = api_mode
    if body.context_length is not None:
        model["context_length"] = body.context_length

    return model


def _profile_edit_payload(profile_name: str, profile_dir: Path) -> dict[str, Any]:
    config = _read_config(profile_dir)
    model_cfg = config.get("model", {})
    if isinstance(model_cfg, str):
        model_cfg = {"default": model_cfg}
    if not isinstance(model_cfg, dict):
        model_cfg = {}

    display_cfg = config.get("display", {})
    if not isinstance(display_cfg, dict):
        display_cfg = {}

    compression_cfg = config.get("compression", {})
    if not isinstance(compression_cfg, dict):
        compression_cfg = {}

    toolsets = config.get("toolsets", [])
    if isinstance(toolsets, str):
        toolsets = [toolsets]
    if not isinstance(toolsets, list):
        toolsets = []

    return {
        "name": profile_name,
        "model": {
            "provider": str(model_cfg.get("provider") or ""),
            "default": str(model_cfg.get("default") or model_cfg.get("model") or ""),
            "base_url": str(model_cfg.get("base_url") or ""),
            "api_mode": str(model_cfg.get("api_mode") or ""),
            "context_length": model_cfg.get("context_length"),
        },
        "toolsets": [str(t) for t in toolsets],
        "skin": str(display_cfg.get("skin") or ""),
        "compression": {
            "enabled": bool(compression_cfg.get("enabled", False)),
            "summary_provider": str(compression_cfg.get("summary_provider") or ""),
            "summary_model": str(compression_cfg.get("summary_model") or ""),
        },
        "soul": _read_soul(profile_dir),
    }


@router.get("/profiles")
async def get_profiles():
    return to_dict(collect_profiles())


@router.get("/profiles/options")
async def profile_options():
    return {
        "providers": PROVIDER_OPTIONS,
        "provider_presets": PROVIDER_PRESETS,
        "toolsets": TOOLSET_OPTIONS,
    }


@router.get("/profiles/{profile_name}/edit")
def get_profile_edit(profile_name: str):
    profile_dir = _profile_dir(profile_name)
    return _profile_edit_payload(profile_name, profile_dir)


@router.put("/profiles/{profile_name}/edit")
def update_profile_edit(profile_name: str, body: ProfileEditBody):
    profile_dir = _profile_dir(profile_name)

    def do_update():
        config = _read_config(profile_dir)
        existing = _profile_edit_payload(profile_name, profile_dir)

        model = _clean_model(body.model)
        if existing["model"].get("default") and not body.model.default.strip():
            raise HTTPException(status_code=400, detail="model cannot be cleared")
        if existing["model"].get("provider") and not body.model.provider.strip():
            raise HTTPException(status_code=400, detail="provider cannot be cleared")
        config["model"] = model
        config["toolsets"] = _clean_list(body.toolsets)

        display = config.get("display", {})
        if not isinstance(display, dict):
            display = {}
        skin = body.skin.strip()
        if skin:
            display["skin"] = skin
        else:
            display.pop("skin", None)
        config["display"] = display

        compression = config.get("compression", {})
        if not isinstance(compression, dict):
            compression = {}
        compression["enabled"] = body.compression.enabled
        summary_provider = body.compression.summary_provider.strip()
        summary_model = body.compression.summary_model.strip()
        if summary_provider:
            compression["summary_provider"] = summary_provider
        else:
            compression.pop("summary_provider", None)
        if summary_model:
            compression["summary_model"] = summary_model
        else:
            compression.pop("summary_model", None)
        config["compression"] = compression

        yaml_text = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
        _atomic_write(profile_dir / "config.yaml", yaml_text)
        soul = body.soul
        if soul and not soul.endswith("\n"):
            soul += "\n"
        _atomic_write(profile_dir / "SOUL.md", soul)
        clear_cache()
        return _profile_edit_payload(profile_name, profile_dir)

    try:
        return _with_profile_lock(profile_dir, do_update)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to update profile: {exc}") from exc
