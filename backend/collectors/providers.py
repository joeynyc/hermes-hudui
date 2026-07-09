"""Collect OAuth provider auth status from ~/.hermes/auth.json."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..cache import get_cached_or_compute
from .models import ProviderAuth, ProvidersState
from .utils import default_hermes_dir, load_yaml, parse_timestamp

# Human-readable names for known provider IDs.
_DISPLAY_NAMES = {
    "nous": "Nous Portal",
    "openai-codex": "OpenAI Codex",
    "anthropic": "Anthropic Claude",
    "openrouter": "OpenRouter",
    "zai": "Z.AI",
    "google": "Google",
    "xai": "xAI Grok",
    "minimax": "MiniMax",
}

_PROVIDER_KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "openai-codex": ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "fireworks": ("FIREWORKS_API_KEY",),
    "google": ("GOOGLE_AI_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "xai": ("XAI_API_KEY",),
    "zai": ("ZAI_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
    "nous": ("NOUS_API_KEY",),
}


def _mask_token(token: Optional[str]) -> str:
    if not token or not isinstance(token, str):
        return ""
    token = token.strip()
    if len(token) <= 8:
        return "•" * len(token)
    return f"{token[:4]}…{token[-4:]}"


def _classify(expires_at: Optional[datetime], has_token: bool) -> str:
    if not has_token:
        return "missing"
    if expires_at is None:
        return "connected"  # no expiry recorded → assume ok
    now = datetime.now()
    if expires_at < now:
        return "expired"
    # expiring soon: within 7 days
    delta = (expires_at - now).total_seconds()
    if delta < 7 * 86400:
        return "expiring"
    return "connected"


def _read_config(hermes_path: Path) -> tuple[str, str]:
    path = hermes_path / "config.yaml"
    if not path.exists():
        return "", ""
    try:
        data = load_yaml(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    model_cfg = data.get("model")
    if isinstance(model_cfg, str):
        return "", model_cfg.strip()
    if not isinstance(model_cfg, dict):
        return "", ""
    provider = str(model_cfg.get("provider") or "").strip()
    model = str(model_cfg.get("default") or model_cfg.get("model") or "").strip()
    return provider, model


def _read_dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, PermissionError):
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value:
            values[key] = value
    return values


def _available_key_names(hermes_path: Path) -> set[str]:
    names = {key for key, value in os.environ.items() if value}
    names.update(_read_dotenv_values(hermes_path / ".env"))
    names.update(_read_dotenv_values(Path.home() / ".env"))
    return names


def _provider_has_key(provider: str, available_keys: set[str]) -> bool:
    aliases = _PROVIDER_KEYS.get(provider.lower(), ())
    return any(key in available_keys for key in aliases)


def _read_models_cache(hermes_path: Path) -> dict:
    path = hermes_path / "models_dev_cache.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _find_model_metadata(cache: dict, provider: str, model: str) -> tuple[Optional[str], Optional[dict]]:
    if not provider or not model:
        return None, None

    provider_entry = cache.get(provider) or cache.get(provider.lower())
    if isinstance(provider_entry, dict):
        models = provider_entry.get("models")
        if isinstance(models, dict):
            entry = models.get(model)
            if isinstance(entry, dict):
                return provider, entry

    for pid, provider_entry in cache.items():
        if not isinstance(provider_entry, dict):
            continue
        models = provider_entry.get("models")
        if not isinstance(models, dict):
            continue
        entry = models.get(model)
        if isinstance(entry, dict):
            return str(pid), entry
    return None, None


def _add_drift_warnings(
    providers: dict[str, ProviderAuth],
    active: Optional[str],
    config_provider: str,
    config_model: str,
    hermes_path: Path,
) -> list[str]:
    warnings: list[str] = []
    if not config_provider:
        return warnings

    configured = providers.get(config_provider)
    has_connected_oauth = configured is not None and configured.status in {"connected", "expiring"}
    has_key = _provider_has_key(config_provider, _available_key_names(hermes_path))

    if not has_connected_oauth and not has_key:
        warnings.append(f"No available key or OAuth token for configured provider '{config_provider}'")

    if configured and configured.status == "expired":
        configured.warnings.append("Configured provider OAuth is expired")
    elif configured and configured.status == "missing":
        configured.warnings.append("Configured provider OAuth token is missing")

    if active and active != config_provider:
        warnings.append(f"Configured provider is '{config_provider}' but active OAuth provider is '{active}'")

    if config_model:
        found_provider, metadata = _find_model_metadata(_read_models_cache(hermes_path), config_provider, config_model)
        if metadata is None:
            warnings.append(f"Configured model '{config_model}' was not found in models.dev metadata")
        elif found_provider and found_provider != config_provider:
            warnings.append(
                f"Configured model '{config_model}' is listed under provider '{found_provider}', not '{config_provider}'"
            )
        elif not bool(metadata.get("tool_call")):
            warnings.append(f"Configured model '{config_model}' does not advertise tool-call support in models.dev")

    return warnings


def _build_provider(pid: str, entry: dict, active_id: Optional[str]) -> ProviderAuth:
    name = _DISPLAY_NAMES.get(pid, pid.replace("-", " ").title())

    # Token can live under several keys depending on provider/flow.
    token = (
        entry.get("access_token")
        or entry.get("api_key")
        or entry.get("token")
        or (entry.get("tokens", {}) or {}).get("access_token")
        or entry.get("agent_key")
    )

    expires = parse_timestamp(
        entry.get("expires_at")
        or entry.get("expiry")
        or (entry.get("tokens", {}) or {}).get("expires_at")
        or entry.get("agent_key_expires_at")
    )
    obtained = parse_timestamp(
        entry.get("obtained_at")
        or entry.get("last_refresh")
        or entry.get("agent_key_obtained_at")
    )

    scope = entry.get("scope", "")
    if isinstance(scope, list):
        scope = " ".join(scope)

    auth_mode = entry.get("auth_mode") or entry.get("auth_type") or ("oauth" if token else "")

    return ProviderAuth(
        id=pid,
        name=name,
        status=_classify(expires, bool(token)),
        token_preview=_mask_token(token),
        expires_at=expires,
        obtained_at=obtained,
        scope=scope if isinstance(scope, str) else "",
        is_active=(pid == active_id),
        auth_mode=auth_mode if isinstance(auth_mode, str) else "",
    )


def _do_collect_providers(hermes_path: Path) -> ProvidersState:
    auth_path = hermes_path / "auth.json"
    anthropic_path = hermes_path / ".anthropic_oauth.json"

    providers: dict[str, ProviderAuth] = {}
    active: Optional[str] = None
    config_provider, config_model = _read_config(hermes_path)

    # auth.json — Nous + OpenAI-Codex via `providers`, plus `credential_pool` for the rest.
    if auth_path.exists():
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if isinstance(data, dict):
            active = data.get("active_provider")
            for pid, entry in (data.get("providers") or {}).items():
                if isinstance(entry, dict):
                    providers[pid] = _build_provider(pid, entry, active)
            for pid, entry in (data.get("credential_pool") or {}).items():
                if pid in providers:
                    continue
                # credential_pool values are lists of credential records — take
                # the highest-priority one (lowest priority number, typically 0).
                if isinstance(entry, list) and entry:
                    records = [r for r in entry if isinstance(r, dict)]
                    if records:
                        records.sort(key=lambda r: r.get("priority", 999))
                        providers[pid] = _build_provider(pid, records[0], active)
                elif isinstance(entry, dict):
                    providers[pid] = _build_provider(pid, entry, active)
                elif isinstance(entry, str) and entry:
                    providers[pid] = ProviderAuth(
                        id=pid,
                        name=_DISPLAY_NAMES.get(pid, pid.title()),
                        status="connected",
                        token_preview=_mask_token(entry),
                        auth_mode="api_key",
                        is_active=(pid == active),
                    )

    # Anthropic PKCE tokens live in their own file when present.
    if anthropic_path.exists() and "anthropic" not in providers:
        try:
            data = json.loads(anthropic_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        if isinstance(data, dict):
            providers["anthropic"] = _build_provider("anthropic", data, active)

    ordered = sorted(
        providers.values(),
        key=lambda p: (not p.is_active, p.status != "connected", p.name.lower()),
    )

    return ProvidersState(
        providers=ordered,
        active_provider=active,
        config_provider=config_provider,
        config_model=config_model,
        warnings=_add_drift_warnings(providers, active, config_provider, config_model, hermes_path),
    )


def collect_providers(hermes_dir: Optional[str] = None) -> ProvidersState:
    hermes_path = Path(default_hermes_dir(hermes_dir))
    return get_cached_or_compute(
        cache_key=f"providers:{hermes_path}",
        compute_fn=lambda: _do_collect_providers(hermes_path),
        file_paths=[
            hermes_path / "auth.json",
            hermes_path / ".anthropic_oauth.json",
            hermes_path / "config.yaml",
            hermes_path / ".env",
            hermes_path / "models_dev_cache.json",
        ],
        ttl=30,
    )
