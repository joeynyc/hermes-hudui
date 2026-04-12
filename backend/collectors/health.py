"""Health check collector — API keys, services, connectivity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .utils import default_hermes_dir


@dataclass
class KeyStatus:
    name: str
    source: str  # env, auth.json, config
    present: bool = False
    note: str = ""
    required: bool = False


@dataclass
class ServiceStatus:
    name: str
    status: str = "unknown"  # running, stopped, unavailable, n/a, check_failed
    running: bool = False
    pid: Optional[int] = None
    note: str = ""
    required: bool = False


@dataclass
class HealthState:
    keys: list[KeyStatus] = field(default_factory=list)
    services: list[ServiceStatus] = field(default_factory=list)
    config_model: str = ""
    config_provider: str = ""
    hermes_dir_exists: bool = False
    state_db_exists: bool = False
    state_db_size: int = 0

    @property
    def keys_ok(self) -> int:
        return sum(1 for k in self.keys if k.required and k.present)

    @property
    def keys_missing(self) -> int:
        return sum(1 for k in self.keys if k.required and not k.present)

    @property
    def required_keys_missing(self) -> int:
        return self.keys_missing

    @property
    def optional_keys_present(self) -> int:
        return sum(1 for k in self.keys if not k.required and k.present)

    @property
    def services_ok(self) -> int:
        return sum(1 for s in self.services if s.running)

    @property
    def required_services_ok(self) -> int:
        return sum(1 for s in self.services if s.required and s.running)

    @property
    def required_services_missing(self) -> int:
        return sum(1 for s in self.services if s.required and not s.running)

    @property
    def optional_services_running(self) -> int:
        return sum(1 for s in self.services if not s.required and s.running)

    @property
    def unavailable_service_checks(self) -> int:
        return sum(1 for s in self.services if s.status in {'unavailable', 'n/a'})

    @property
    def all_healthy(self) -> bool:
        return self.keys_missing == 0 and self.required_services_missing == 0


PROVIDER_REQUIRED_KEYS = {
    "anthropic": [("ANTHROPIC_API_KEY", "env", "Primary LLM provider")],
    "openrouter": [("OPENROUTER_API_KEY", "env", "OpenRouter provider")],
    "fireworks": [("FIREWORKS_API_KEY", "env", "Fireworks AI provider")],
    "xai": [("XAI_API_KEY", "env", "xAI provider")],
}

OPTIONAL_KEYS = [
    ("TELEGRAM_BOT_TOKEN", "env", "Telegram gateway bot token"),
    ("ELEVENLABS_API_KEY", "env", "ElevenLabs TTS"),
]



def _load_dotenv_keys(dotenv_path: str) -> set[str]:
    keys = set()
    try:
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if key:
                        keys.add(key)
    except (OSError, PermissionError):
        pass
    return keys



def _get_dotenv_keys(hermes_dir: str) -> set[str]:
    keys: set[str] = set()
    for env_path in [
        os.path.join(hermes_dir, ".env"),
        os.path.expanduser("~/.env"),
    ]:
        keys.update(_load_dotenv_keys(env_path))
    return keys



def _check_env_key(name: str, hermes_dir: str = "", dotenv_keys: set[str] | None = None) -> bool:
    if os.environ.get(name, ""):
        return True
    if hermes_dir and dotenv_keys is not None:
        return name in dotenv_keys
    return False



def _check_process(name: str, pattern: str, required: bool = False) -> ServiceStatus:
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
        if pids:
            return ServiceStatus(name=name, status='running', running=True, pid=pids[0], required=required)
        return ServiceStatus(name=name, status='stopped', running=False, required=required)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return ServiceStatus(name=name, status='check_failed', running=False, required=required, note='check failed')



def _check_pid_file(name: str, pid_file: Path, required: bool = False) -> ServiceStatus:
    if not pid_file.exists():
        return ServiceStatus(name=name, status='stopped', running=False, required=required, note='no pid file')

    try:
        data = json.loads(pid_file.read_text())
        pid = data.get("pid")
        if pid:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "pid="],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return ServiceStatus(name=name, status='running', running=True, pid=pid, required=required)
            return ServiceStatus(name=name, status='stopped', running=False, pid=pid, required=required, note='pid file exists but process dead')
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        pass

    return ServiceStatus(name=name, status='check_failed', running=False, required=required, note='pid file unreadable')



def _check_systemd_service(name: str, service: str, required: bool = False) -> ServiceStatus:
    if sys.platform == 'darwin':
        return ServiceStatus(name=name, status='unavailable', running=False, required=required, note='systemctl unavailable on macOS')
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service],
            capture_output=True, text=True, timeout=5,
        )
        status = result.stdout.strip()
        if status == 'active':
            return ServiceStatus(name=name, status='running', running=True, required=required, note='active')
        if status:
            return ServiceStatus(name=name, status='stopped', running=False, required=required, note=status)
        return ServiceStatus(name=name, status='check_failed', running=False, required=required, note='empty systemctl response')
    except FileNotFoundError:
        return ServiceStatus(name=name, status='unavailable', running=False, required=required, note='systemctl unavailable')
    except subprocess.TimeoutExpired:
        return ServiceStatus(name=name, status='check_failed', running=False, required=required, note='systemctl timeout')



def _config_text(hermes_dir: str) -> str:
    try:
        return (Path(hermes_dir) / 'config.yaml').read_text(encoding='utf-8')
    except Exception:
        return ''



def _provider_needs_local_server(provider: str, hermes_dir: str) -> bool:
    provider_name = (provider or '').strip().lower()
    config_text = _config_text(hermes_dir).lower()
    if provider_name == 'local':
        return True
    if provider_name == 'custom' and any(token in config_text for token in ('localhost', '127.0.0.1', 'ollama', ':11434')):
        return True
    return False



def collect_health(hermes_dir: str | None = None) -> HealthState:
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    hermes_path = Path(hermes_dir)
    state = HealthState()

    state.hermes_dir_exists = hermes_path.exists()
    state_db = hermes_path / "state.db"
    state.state_db_exists = state_db.exists()
    if state.state_db_exists:
        try:
            state.state_db_size = state_db.stat().st_size
        except OSError:
            pass

    from .config import collect_config
    try:
        config = collect_config(hermes_dir)
        state.config_model = config.model
        state.config_provider = config.provider
    except Exception:
        pass

    dotenv_keys = _get_dotenv_keys(hermes_dir)

    provider_key_defs = PROVIDER_REQUIRED_KEYS.get(state.config_provider, [])
    known_names = {key_name for key_name, _, _ in provider_key_defs}
    known_names.update(key_name for key_name, _, _ in OPTIONAL_KEYS)

    for key_name, source, note in provider_key_defs:
        present = _check_env_key(key_name, hermes_dir, dotenv_keys)
        state.keys.append(KeyStatus(
            name=key_name,
            source=source,
            present=present,
            note=note if not present else "",
            required=True,
        ))

    for key_name, source, note in OPTIONAL_KEYS:
        present = _check_env_key(key_name, hermes_dir, dotenv_keys)
        if present:
            state.keys.append(KeyStatus(
                name=key_name,
                source=source,
                present=True,
                note=note,
                required=False,
            ))

    for extra_key in sorted(dotenv_keys):
        if extra_key not in known_names:
            if any(extra_key.endswith(suffix) for suffix in ("_API_KEY", "_TOKEN", "_SECRET")):
                state.keys.append(KeyStatus(
                    name=extra_key,
                    source="env",
                    present=True,
                    note="discovered",
                    required=False,
                ))

    telegram_configured = _check_env_key('TELEGRAM_BOT_TOKEN', hermes_dir, dotenv_keys)
    telegram_gateway = _check_pid_file('Telegram Gateway', hermes_path / 'gateway.pid', required=False)
    if not telegram_configured and not telegram_gateway.running:
        telegram_gateway.status = 'n/a'
        telegram_gateway.note = 'not configured'

    gateway_systemd = _check_systemd_service('Gateway (systemd)', 'hermes-gateway', required=False)
    if not telegram_configured and not gateway_systemd.running and gateway_systemd.status == 'stopped':
        gateway_systemd.status = 'n/a'
        gateway_systemd.note = 'not configured'

    llama_required = _provider_needs_local_server(state.config_provider, hermes_dir)
    llama_server = _check_process('llama-server', 'llama-server', required=llama_required)
    if not llama_required and not llama_server.running:
        llama_server.status = 'n/a'
        llama_server.note = 'not required for current provider'

    state.services.append(telegram_gateway)
    state.services.append(gateway_systemd)
    state.services.append(llama_server)

    return state
