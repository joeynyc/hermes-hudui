"""Gateway status + actions (restart / update hermes)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from ..cache import get_cached_or_compute
from .models import GatewayState, ManagedToolsState, ManagedToolStatus, PlatformStatus
from .utils import default_hermes_dir, load_yaml, parse_timestamp

# Maps a stable action name (used in URLs + state files) to the `hermes`
# argv to execute. Adding an action = adding one entry here.
ACTIONS: dict[str, list[str]] = {
    "gateway-restart": ["gateway", "restart"],
    "hermes-update": ["update"],
}
ACTION_NAMES = frozenset(ACTIONS)
_ACTION_FILE_NAMES = {
    "gateway-restart": ("gateway-restart.json", "gateway-restart.log"),
    "hermes-update": ("hermes-update.json", "hermes-update.log"),
}

# Bounded by len(ACTIONS); entries popped once we reap the child.
_action_procs: dict[str, subprocess.Popen] = {}
_MAX_ACTION_STATE_BYTES = 64 * 1024
_MAX_ACTION_LOG_BYTES = 256 * 1024

_MANAGED_TOOL_DEFS = [
    {
        "key": "web",
        "label": "Web Search",
        "section": "web",
        "gateway_service": "firecrawl",
        "direct_env_vars": ["FIRECRAWL_API_KEY", "EXA_API_KEY", "PARALLEL_API_KEY", "TAVILY_API_KEY"],
        "direct_label": "Firecrawl/Exa/Parallel/Tavily key",
    },
    {
        "key": "image_gen",
        "label": "Image Generation",
        "section": "image_gen",
        "gateway_service": "fal-queue",
        "direct_env_vars": ["FAL_KEY", "FAL_API_KEY"],
        "direct_label": "FAL key",
    },
    {
        "key": "tts",
        "label": "Text to Speech",
        "section": "tts",
        "gateway_service": "openai-audio",
        "direct_env_vars": ["OPENAI_API_KEY"],
        "direct_label": "OpenAI audio key",
    },
    {
        "key": "browser",
        "label": "Browser Automation",
        "section": "browser",
        "gateway_service": "browser-use",
        "direct_env_vars": ["BROWSER_USE_API_KEY", "BROWSERBASE_API_KEY"],
        "direct_label": "Browser Use/Browserbase key",
    },
]


def _pid_alive(pid: Optional[int]) -> bool:
    """Return True only if the pid is live AND not a zombie.

    `os.kill(pid, 0)` succeeds for zombies too, so for real liveness we also
    read /proc/<pid>/status on Linux. On non-Linux we fall back to os.kill.
    """
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    try:
        with open(f"/proc/{int(pid)}/status", "r") as f:
            for line in f:
                if line.startswith("State:"):
                    return "Z" not in line.split(":", 1)[1]
    except (OSError, ValueError):
        pass
    return True


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _load_config(hermes_path: Path) -> dict:
    path = hermes_path / "config.yaml"
    if not path.exists():
        return {}
    data = load_yaml(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _has_nous_auth(hermes_path: Path, env: dict[str, str]) -> bool:
    if env.get("NOUS_API_KEY") or env.get("NOUS_ACCESS_TOKEN"):
        return True
    for filename in ("auth.json", ".nous_oauth.json", "nous_auth.json"):
        path = hermes_path / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = json.dumps(data).lower()
        if "nous" in text and ("access_token" in text or "api_key" in text or "token" in text):
            return True
    return False


def collect_managed_tools(
    hermes_dir: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
) -> ManagedToolsState:
    """Collect managed Tool Gateway routing state for user-facing tools."""
    hermes_path = Path(default_hermes_dir(hermes_dir))
    env = env if env is not None else os.environ
    config = _load_config(hermes_path)
    nous_auth_present = _has_nous_auth(hermes_path, env)
    tools: list[ManagedToolStatus] = []

    for item in _MANAGED_TOOL_DEFS:
        section = config.get(item["section"], {})
        section = section if isinstance(section, dict) else {}
        use_gateway = _truthy(section.get("use_gateway"))
        configured_env = [name for name in item["direct_env_vars"] if env.get(name)]
        has_direct_credential = bool(configured_env)
        config_section = str(item["section"])
        direct_missing_label = f"direct {item['direct_label']}"
        missing_config: list[str] = []
        diagnostics = [
            f"Gateway opt-in {'enabled' if use_gateway else 'disabled'} in {config_section}.use_gateway.",
        ]
        safe_actions: list[str] = []

        if use_gateway:
            diagnostics.append(
                "Nous Portal auth is present." if nous_auth_present else "Nous Portal auth is missing."
            )
            safe_actions.append("gateway-restart")
            if not nous_auth_present:
                missing_config.append("Nous Portal auth")
        else:
            missing_config.append(f"{config_section}.use_gateway: true")

        if has_direct_credential:
            diagnostics.append(f"Direct credential configured: {configured_env[0]}.")
        else:
            diagnostics.append("No direct credential detected.")
            if not use_gateway or not nous_auth_present:
                missing_config.append(direct_missing_label)

        if use_gateway and nous_auth_present:
            route = "managed"
            available = True
            reason = "Routed through Nous Tool Gateway."
        elif configured_env:
            route = "direct"
            available = True
            reason = f"Using direct credential: {configured_env[0]}."
        else:
            route = "unavailable"
            available = False
            if use_gateway:
                reason = "Gateway is enabled, but Nous Portal auth is missing."
            else:
                reason = f"No gateway opt-in or direct {item['direct_label']} configured."

        tools.append(
            ManagedToolStatus(
                key=item["key"],
                label=item["label"],
                gateway_service=item["gateway_service"],
                enabled=available,
                available=available,
                route=route,
                config_section=config_section,
                gateway_enabled=use_gateway,
                has_direct_credential=has_direct_credential,
                direct_env_vars=list(item["direct_env_vars"]),
                configured_env_vars=configured_env,
                missing_config=missing_config if not available else [],
                diagnostics=diagnostics,
                safe_actions=safe_actions,
                reason=reason,
            )
        )

    return ManagedToolsState(tools=tools, nous_auth_present=nous_auth_present)


def _do_collect_gateway(hermes_path: Path) -> GatewayState:
    state_path = hermes_path / "gateway_state.json"
    if not state_path.exists():
        return GatewayState(managed_tools=collect_managed_tools(str(hermes_path)))

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return GatewayState(managed_tools=collect_managed_tools(str(hermes_path)))
    if not isinstance(data, dict):
        return GatewayState(managed_tools=collect_managed_tools(str(hermes_path)))

    pid = data.get("pid")
    platforms: list[PlatformStatus] = []
    for name, info in (data.get("platforms") or {}).items():
        if not isinstance(info, dict):
            continue
        platforms.append(
            PlatformStatus(
                name=name,
                state=str(info.get("state") or "unknown"),
                updated_at=parse_timestamp(info.get("updated_at")),
                error_code=info.get("error_code") or None,
                error_message=info.get("error_message") or None,
            )
        )
    platforms.sort(key=lambda p: p.name)

    return GatewayState(
        state=str(data.get("gateway_state") or "unknown"),
        pid=pid if isinstance(pid, int) else None,
        pid_alive=_pid_alive(pid),
        kind=str(data.get("kind") or ""),
        restart_requested=bool(data.get("restart_requested")),
        exit_reason=data.get("exit_reason"),
        updated_at=parse_timestamp(data.get("updated_at")),
        active_agents=int(data.get("active_agents") or 0),
        platforms=platforms,
        managed_tools=collect_managed_tools(str(hermes_path)),
    )


def collect_gateway_status(hermes_dir: Optional[str] = None) -> GatewayState:
    hermes_path = Path(default_hermes_dir(hermes_dir))
    return get_cached_or_compute(
        cache_key=f"gateway:{hermes_path}",
        compute_fn=lambda: _do_collect_gateway(hermes_path),
        file_paths=[hermes_path / "gateway_state.json"],
        ttl=5,
    )


# ── Actions: restart / update ──────────────────────────────────────────

def _action_paths(name: str, hermes_dir: Optional[str] = None) -> tuple[Path, Path]:
    if name not in ACTION_NAMES:
        raise ValueError(f"Unknown action: {name}")

    hermes_path = Path(default_hermes_dir(hermes_dir)).expanduser().resolve()
    log_dir = (hermes_path / "logs" / "hud").resolve(strict=False)
    try:
        log_dir.relative_to(hermes_path)
    except ValueError as exc:
        raise ValueError("Action log directory escapes the Hermes directory") from exc
    log_dir.mkdir(parents=True, exist_ok=True)
    log_dir = log_dir.resolve()
    try:
        log_dir.relative_to(hermes_path)
    except ValueError as exc:
        raise ValueError("Action log directory escapes the Hermes directory") from exc
    try:
        os.chmod(log_dir, 0o700)
    except OSError:
        pass
    state_name, log_name = _ACTION_FILE_NAMES[name]
    return log_dir / state_name, log_dir / log_name


def _write_state(path: Path, state: dict) -> None:
    descriptor, tmp_name = tempfile.mkstemp(
        prefix=f".{path.stem}-",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp = Path(tmp_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        else:
            os.chmod(tmp, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(state, handle)
        os.replace(tmp, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _read_state(path: Path) -> dict:
    try:
        if path.is_symlink():
            return {}
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            if os.fstat(descriptor).st_size > _MAX_ACTION_STATE_BYTES:
                return {}
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = -1
                data = json.load(handle)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError):
        return {}


def run_action(name: str, hermes_dir: Optional[str] = None) -> dict:
    """Spawn a detached hermes action. Returns a descriptor dict."""
    state_file, log_file = _action_paths(name, hermes_dir)

    hermes_bin = shutil.which("hermes")
    if not hermes_bin:
        raise RuntimeError("hermes CLI not found on PATH")

    argv_tail = ACTIONS[name]

    env = os.environ.copy()
    env["HERMES_NONINTERACTIVE"] = "1"

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    elif log_file.is_symlink():
        raise ValueError("Action log file must not be a symlink")
    descriptor = os.open(log_file, flags, 0o600)
    log_fh = os.fdopen(descriptor, "wb", buffering=0)
    try:
        proc = subprocess.Popen(
            [hermes_bin, *argv_tail],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            cwd=os.path.expanduser("~"),
            start_new_session=True,
        )
    finally:
        log_fh.close()
    _action_procs[name] = proc

    state = {
        "name": name,
        "pid": proc.pid,
        "started_at": time.time(),
        "log_path": str(log_file),
    }
    _write_state(state_file, state)
    return state


def _tail_lines(path: Path, max_lines: int = 200) -> list[str]:
    try:
        if path.is_symlink():
            return []
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            size = os.fstat(handle.fileno()).st_size
            handle.seek(max(0, size - _MAX_ACTION_LOG_BYTES))
            data = handle.read(_MAX_ACTION_LOG_BYTES)
    except (FileNotFoundError, OSError):
        return []
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-max_lines:]


def read_action_status(name: str, hermes_dir: Optional[str] = None) -> dict:
    state_file, log_file = _action_paths(name, hermes_dir)
    state = _read_state(state_file)

    pid = state.get("pid")
    exit_code: Optional[int] = state.get("exit_code")

    # If we spawned it in this process, reap it non-blockingly so the pid
    # doesn't linger as a zombie.
    proc = _action_procs.get(name)
    if proc is not None and proc.pid == pid:
        rc = proc.poll()
        if rc is not None:
            exit_code = rc
            _action_procs.pop(name, None)

    running = exit_code is None and _pid_alive(pid)

    return {
        "name": name,
        "pid": pid,
        "running": running,
        "exit_code": exit_code,
        "started_at": state.get("started_at"),
        "log_path": str(log_file),
        "lines": _tail_lines(log_file),
    }
