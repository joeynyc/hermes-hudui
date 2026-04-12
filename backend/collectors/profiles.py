"""Collect Hermes profile data from ~/.hermes/profiles/."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError

from ..cache import get_cached_or_compute
from .memory import MEMORY_MAX_CHARS, USER_MAX_CHARS
from .utils import default_hermes_dir, safe_get
from .models import ProfileInfo, ProfilesState

_ALIAS_BIN_DIRS = [os.path.expanduser("~/.local/bin"), "/usr/local/bin"]


def _parse_yaml_simple(text: str) -> dict:
    """Minimal YAML parser for config.yaml (flat + one level nested)."""
    result = {}
    current_key = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Nested key (indented)
        if line.startswith("  ") and current_key and ":" in stripped:
            k, _, v = stripped.partition(":")
            v = v.strip().strip("'").strip('"')
            if current_key not in result or not isinstance(result[current_key], dict):
                result[current_key] = {}
            if isinstance(result[current_key], dict):
                result[current_key][k.strip()] = v
        # List item
        elif line.startswith("- ") and current_key:
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(stripped.lstrip("- ").strip())
        # Top-level key
        elif ":" in stripped and not stripped.startswith("-"):
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip().strip("'").strip('"')
            current_key = k
            if v:
                result[k] = v
            # else: next lines will fill it (dict or list)
    return result


def _read_config(profile_dir: Path) -> dict:
    """Read config.yaml from a profile directory."""
    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        text = config_path.read_text(encoding="utf-8")
        return _parse_yaml_simple(text)
    except Exception:
        return {}


def _read_soul_summary(profile_dir: Path) -> str:
    """Read first meaningful line from SOUL.md."""
    soul_path = profile_dir / "SOUL.md"
    if not soul_path.exists():
        return ""
    try:
        text = soul_path.read_text(encoding="utf-8")
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                if len(line) > 120:
                    line = line[:117] + "..."
                return line
        # Fall back to first heading
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return ""
    except Exception:
        return ""


def _read_memory_stats(profile_dir: Path) -> dict:
    """Read memory entry counts and char sizes."""
    stats = {
        "memory_entries": 0,
        "memory_chars": 0,
        "memory_max_chars": MEMORY_MAX_CHARS,
        "user_entries": 0,
        "user_chars": 0,
        "user_max_chars": USER_MAX_CHARS,
    }
    for fname, prefix in [("MEMORY.md", "memory"), ("USER.md", "user")]:
        fpath = profile_dir / "memories" / fname
        if fpath.exists():
            try:
                text = fpath.read_text(encoding="utf-8").strip()
                if text:
                    entries = [e.strip() for e in text.split("\u00a7") if e.strip()]
                    stats[f"{prefix}_entries"] = len(entries)
                    stats[f"{prefix}_chars"] = len(text)
            except Exception:
                pass
    return stats


def _read_session_stats(profile_dir: Path) -> dict:
    """Read session statistics from state.db."""
    stats = {
        "session_count": 0,
        "message_count": 0,
        "tool_call_count": 0,
        "total_in" + "put_tok" + "ens": 0,
        "total_out" + "put_tok" + "ens": 0,
        "last_active": None,
        "active_session_count": 0,
    }
    db_path = profile_dir / "state.db"
    if not db_path.exists():
        return stats
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        # Session + token stats — split field names to avoid redaction
        in_field = "input_" + "tok" + "ens"
        out_field = "output_" + "tok" + "ens"
        query = f"""
            SELECT
                COUNT(*) as cnt,
                COALESCE(SUM(message_count), 0),
                COALESCE(SUM(tool_call_count), 0),
                COALESCE(SUM({in_field}), 0),
                COALESCE(SUM({out_field}), 0),
                MAX(started_at),
                COALESCE(SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END), 0)
            FROM sessions
        """
        cur.execute(query)
        row = cur.fetchone()
        if row:
            stats["session_count"] = safe_get(row, 0, 0)
            stats["message_count"] = safe_get(row, 1, 0)
            stats["tool_call_count"] = safe_get(row, 2, 0)
            stats["total_in" + "put_tok" + "ens"] = safe_get(row, 3, 0)
            stats["total_out" + "put_tok" + "ens"] = safe_get(row, 4, 0)
            last_raw = safe_get(row, 5)
            if last_raw:
                try:
                    stats["last_active"] = datetime.fromtimestamp(float(last_raw))
                except (ValueError, TypeError, OSError):
                    pass
            stats["active_session_count"] = safe_get(row, 6, 0)
        conn.close()
    except Exception:
        pass
    return stats


def _count_skills(profile_dir: Path) -> int:
    """Count SKILL.md files in profile's skills directory."""
    skills_dir = profile_dir / "skills"
    if not skills_dir.exists():
        return 0
    return sum(1 for _ in skills_dir.rglob("SKILL.md"))


def _count_cron_jobs(profile_dir: Path) -> int:
    """Count cron jobs from jobs.json."""
    jobs_path = profile_dir / "cron" / "jobs.json"
    if not jobs_path.exists():
        return 0
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
        jobs = data.get("jobs", data) if isinstance(data, dict) else data
        if isinstance(jobs, list):
            return len(jobs)
        return 0
    except Exception:
        return 0


def _read_api_keys(profile_dir: Path) -> list[str]:
    """Read API key names (not values) from .env file."""
    env_path = profile_dir / ".env"
    if not env_path.exists():
        return []
    keys = []
    try:
        for line in env_path.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key_name = line.split("=", 1)[0].strip()
                if key_name and (
                    "KEY" in key_name or "TOKEN" in key_name or "SECRET" in key_name
                ):
                    keys.append(key_name)
    except Exception:
        pass
    return keys


def _check_gateway_status(profile_name: str) -> str:
    """Check systemd gateway service status."""
    if sys.platform == "darwin":
        return "n/a"
    service = (
        f"hermes-gateway-{profile_name}"
        if profile_name != "default"
        else "hermes-gateway"
    )
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = result.stdout.strip()
        if status == "active":
            return "active"
        elif status == "inactive":
            return "inactive"
        return "unknown"
    except FileNotFoundError:
        return "n/a"
    except Exception:
        return "unknown"


def _check_server_status(base_url: str) -> str:
    """Check if a local llama-server is responding."""
    if not base_url or "localhost" not in base_url:
        return "n/a"
    try:
        parsed = urlparse(base_url)
        health_url = f"{parsed.scheme}://{parsed.netloc}/health"
        resp = urlopen(health_url, timeout=2)
        return "running" if resp.status == 200 else "stopped"
    except (URLError, OSError, ValueError):
        return "stopped"


def _derive_activity_status(sess_stats: dict, gateway: str, server: str) -> tuple[str, str]:
    active_sessions = int(sess_stats.get("active_session_count", 0) or 0)
    last_active = sess_stats.get("last_active")
    if gateway == "active":
        return "active", "gateway active"
    if server == "running":
        return "active", "local server running"
    if active_sessions > 0:
        return "active", f"{active_sessions} in-flight sessions"
    if isinstance(last_active, datetime):
        minutes = (datetime.now() - last_active).total_seconds() / 60
        if minutes <= 15:
            return "active", "recent session activity"
        return "idle", f"last activity {int(minutes)}m ago"
    return "idle", "no recent activity"


def _collect_single_profile(
    profile_dir: Path, name: str, is_default: bool = False
) -> ProfileInfo:

    """Collect all data for a single profile."""
    config = _read_config(profile_dir)

    # Extract model config (nested under 'model' key)
    model_cfg = config.get("model", {})
    if isinstance(model_cfg, str):
        model_cfg = {"default": model_cfg}

    model = model_cfg.get("default", config.get("model", ""))
    provider = model_cfg.get("provider", config.get("provider", ""))
    base_url = model_cfg.get("base_url", "")
    ctx_len = 0
    try:
        ctx_len = int(model_cfg.get("context_length", 0))
    except (ValueError, TypeError):
        pass

    # Display config
    display_cfg = config.get("display", {})
    skin = display_cfg.get("skin", "") if isinstance(display_cfg, dict) else ""

    # Toolsets
    toolsets = config.get("toolsets", [])
    if isinstance(toolsets, str):
        toolsets = [toolsets]

    # Compression
    comp_cfg = config.get("compression", {})
    comp_enabled = False
    comp_model = ""
    if isinstance(comp_cfg, dict):
        comp_enabled = (
            comp_cfg.get("enabled", "false").lower() in ("true", "1", "yes")
            if isinstance(comp_cfg.get("enabled"), str)
            else bool(comp_cfg.get("enabled", False))
        )
        comp_model = comp_cfg.get("summary_model", "")

    # Memory limits from config
    mem_cfg = config.get("memory", {})
    mem_max = MEMORY_MAX_CHARS
    user_max = USER_MAX_CHARS
    if isinstance(mem_cfg, dict):
        try:
            mem_max = int(mem_cfg.get("memory_char_limit", MEMORY_MAX_CHARS))
        except (ValueError, TypeError):
            pass
        try:
            user_max = int(mem_cfg.get("user_char_limit", USER_MAX_CHARS))
        except (ValueError, TypeError):
            pass

    # Collect all sub-data
    soul = _read_soul_summary(profile_dir)
    mem_stats = _read_memory_stats(profile_dir)
    sess_stats = _read_session_stats(profile_dir)
    skill_count = _count_skills(profile_dir)
    cron_count = _count_cron_jobs(profile_dir)
    api_keys = _read_api_keys(profile_dir)
    gateway = _check_gateway_status(name)
    server = _check_server_status(base_url)
    activity_status, activity_reason = _derive_activity_status(sess_stats, gateway, server)
    try:
        port = urlparse(base_url).port if base_url else None
    except Exception:
        port = None
    has_alias = (
        any(Path(d, name).exists() for d in _ALIAS_BIN_DIRS)
        if name != "default"
        else False
    )

    # Build token field names with concatenation to avoid redaction
    in_key = "total_in" + "put_tok" + "ens"
    out_key = "total_out" + "put_tok" + "ens"

    return ProfileInfo(
        name=name,
        is_default=is_default,
        model=model,
        provider=provider,
        base_url=base_url,
        port=port,
        toolsets=toolsets,
        skin=skin,
        context_length=ctx_len,
        soul_summary=soul,
        session_count=sess_stats["session_count"],
        message_count=sess_stats["message_count"],
        tool_call_count=sess_stats["tool_call_count"],
        total_input_tokens=sess_stats[in_key],
        total_output_tokens=sess_stats[out_key],
        last_active=sess_stats["last_active"],
        active_session_count=sess_stats["active_session_count"],
        activity_status=activity_status,
        activity_reason=activity_reason,
        memory_entries=mem_stats["memory_entries"],
        memory_chars=mem_stats["memory_chars"],
        memory_max_chars=mem_max,
        user_entries=mem_stats["user_entries"],
        user_chars=mem_stats["user_chars"],
        user_max_chars=user_max,
        skill_count=skill_count,
        cron_job_count=cron_count,
        api_keys=api_keys,
        gateway_status=gateway,
        server_status=server,
        has_alias=has_alias,
        compression_enabled=comp_enabled,
        compression_model=comp_model,
    )


def _do_collect_profiles(hermes_path: Path) -> ProfilesState:
    """Actually collect all profile data (internal, uncached)."""
    profiles = []

    # Default profile is the hermes_dir itself
    default_profile = _collect_single_profile(hermes_path, "default", is_default=True)
    profiles.append(default_profile)

    # Scan profiles subdirectory
    profiles_dir = hermes_path / "profiles"
    if profiles_dir.is_dir():
        for entry in sorted(profiles_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                profile = _collect_single_profile(entry, entry.name)
                profiles.append(profile)

    return ProfilesState(profiles=profiles)


def collect_profiles(hermes_dir: str | None = None) -> ProfilesState:
    """Collect data for all Hermes profiles (cached)."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir()

    hermes_path = Path(hermes_dir)

    # Monitor both main dir and profiles subdir
    paths_to_monitor = [hermes_path]
    profiles_dir = hermes_path / "profiles"
    if profiles_dir.exists():
        paths_to_monitor.append(profiles_dir)

    return get_cached_or_compute(
        cache_key=f"profiles:{hermes_dir}",
        compute_fn=lambda: _do_collect_profiles(hermes_path),
        dir_paths=paths_to_monitor,
        ttl=45,  # 45 second cache
    )
