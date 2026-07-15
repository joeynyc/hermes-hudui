"""Health check collector — API keys, services, connectivity."""

from __future__ import annotations

import json
import os
import sqlite3

from .utils import default_hermes_dir
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class KeyStatus:
    name: str
    source: str  # env, auth.json, config
    present: bool = False
    note: str = ""


@dataclass
class ServiceStatus:
    name: str
    running: bool = False
    pid: Optional[int] = None
    note: str = ""


@dataclass
class DatabaseCheck:
    name: str
    present: bool = False
    note: str = ""


@dataclass
class HealthState:
    keys: list[KeyStatus] = field(default_factory=list)
    services: list[ServiceStatus] = field(default_factory=list)
    database: list[DatabaseCheck] = field(default_factory=list)
    config_model: str = ""
    config_provider: str = ""
    hermes_dir_exists: bool = False
    state_db_exists: bool = False
    state_db_size: int = 0

    @property
    def keys_ok(self) -> int:
        return sum(1 for k in self.keys if k.present)

    @property
    def keys_missing(self) -> int:
        return sum(1 for k in self.keys if not k.present)

    @property
    def services_ok(self) -> int:
        return sum(1 for s in self.services if s.running)

    @property
    def database_ok(self) -> int:
        return sum(1 for item in self.database if item.present)

    @property
    def database_missing(self) -> int:
        return sum(1 for item in self.database if not item.present)

    @property
    def all_healthy(self) -> bool:
        return (
            self.keys_missing == 0
            and all(s.running for s in self.services)
            and self.database_missing == 0
        )


# Known API keys to check
EXPECTED_KEYS = [
    ("ANTHROPIC_API_KEY", "env", "Primary LLM provider"),
    ("OPENROUTER_API_KEY", "env", "OpenRouter fallback provider"),
    ("FIREWORKS_API_KEY", "env", "Fireworks AI provider"),
    ("XAI_API_KEY", "env", "xAI / Grok API for X search"),
    ("TELEGRAM_BOT_TOKEN", "env", "Telegram gateway bot token"),
    ("ELEVENLABS_API_KEY", "env", "ElevenLabs TTS"),
]


def _load_dotenv_keys(dotenv_path: str) -> set[str]:
    """Load key names from a .env file (not values)."""
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
    """Get all key names from hermes .env files."""
    keys: set[str] = set()
    for env_path in [
        os.path.join(hermes_dir, ".env"),
        os.path.expanduser("~/.env"),
    ]:
        keys.update(_load_dotenv_keys(env_path))
    return keys


def _check_env_key(name: str, hermes_dir: str = "", dotenv_keys: set[str] | None = None) -> bool:
    """Check if a key is set in environment or .env files."""
    if os.environ.get(name, ""):
        return True
    if hermes_dir and dotenv_keys is not None:
        return name in dotenv_keys
    return False


def _check_process(name: str, pattern: str) -> ServiceStatus:
    """Check if a process matching pattern is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
        if pids:
            return ServiceStatus(name=name, running=True, pid=pids[0])
        return ServiceStatus(name=name, running=False)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return ServiceStatus(name=name, running=False, note="check failed")


def _check_pid_file(name: str, pid_file: Path) -> ServiceStatus:
    """Check if a PID file exists and the process is alive."""
    if not pid_file.exists():
        return ServiceStatus(name=name, running=False, note="no pid file")

    try:
        data = json.loads(pid_file.read_text())
        pid = data.get("pid")
        if pid:
            # Check if process is alive
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "pid="],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return ServiceStatus(name=name, running=True, pid=pid)
            return ServiceStatus(name=name, running=False, pid=pid, note="pid file exists but process dead")
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        pass

    return ServiceStatus(name=name, running=False, note="pid file unreadable")


def _check_systemd_service(name: str, service: str) -> ServiceStatus:
    """Check systemd user service status."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", service],
            capture_output=True, text=True, timeout=5,
        )
        is_active = result.stdout.strip() == "active"
        return ServiceStatus(name=name, running=is_active, note=result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ServiceStatus(name=name, running=False, note="systemctl unavailable")


def _collect_database_checks(db_path: Path) -> list[DatabaseCheck]:
    """Validate the Hermes state.db schema used by the HUD.

    Hermes stores tool-call payloads in ``messages.tool_calls``. There is no
    separate ``tool_calls`` table in current Hermes databases, so the health UI
    must check the column rather than reporting a missing table as broken.
    """
    checks = [
        DatabaseCheck("sessions table"),
        DatabaseCheck("messages table"),
        DatabaseCheck("messages.tool_calls column"),
    ]

    if not db_path.exists():
        for check in checks:
            check.note = "state.db missing"
        return checks

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name IN ('sessions', 'messages')
            """
        )
        tables = {row[0] for row in cursor.fetchall()}

        checks[0].present = "sessions" in tables
        checks[1].present = "messages" in tables

        if "messages" in tables:
            cursor.execute("PRAGMA table_info(messages)")
            columns = {row[1] for row in cursor.fetchall()}
            checks[2].present = "tool_calls" in columns
            checks[2].note = "stored on messages table" if checks[2].present else "missing column"
        else:
            checks[2].note = "messages table missing"

        for check in checks[:2]:
            if not check.present:
                check.note = "missing table"

    except sqlite3.Error as exc:
        for check in checks:
            check.note = f"schema check failed: {exc}"
    finally:
        if conn is not None:
            conn.close()

    return checks


def collect_health(hermes_dir: str | None = None) -> HealthState:
    """Collect health status."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    hermes_path = Path(hermes_dir)
    state = HealthState()

    # Directory checks
    state.hermes_dir_exists = hermes_path.exists()
    state_db = hermes_path / "state.db"
    state.state_db_exists = state_db.exists()
    if state.state_db_exists:
        try:
            state.state_db_size = state_db.stat().st_size
        except OSError:
            pass
    state.database = _collect_database_checks(state_db)

    # Config — reuse the config collector
    from .config import collect_config
    try:
        config = collect_config(hermes_dir)
        state.config_model = config.model
        state.config_provider = config.provider
    except Exception:
        pass

    # API keys
    dotenv_keys = _get_dotenv_keys(hermes_dir)

    known_names = {key_name for key_name, _, _ in EXPECTED_KEYS}
    for key_name, source, note in EXPECTED_KEYS:
        present = _check_env_key(key_name, hermes_dir, dotenv_keys)
        state.keys.append(KeyStatus(
            name=key_name,
            source=source,
            present=present,
            note=note if not present else "",
        ))

    # Auto-discover any additional API keys/tokens found in .env files
    for extra_key in sorted(dotenv_keys):
        if extra_key not in known_names:
            if any(extra_key.endswith(suffix) for suffix in ("_API_KEY", "_TOKEN", "_SECRET")):
                state.keys.append(KeyStatus(
                    name=extra_key,
                    source="env",
                    present=True,
                    note="discovered",
                ))

    # Services
    state.services.append(
        _check_pid_file("Telegram Gateway", hermes_path / "gateway.pid")
    )
    state.services.append(
        _check_systemd_service("Gateway (systemd)", "hermes-gateway")
    )
    state.services.append(
        _check_process("llama-server", "llama-server")
    )

    return state
