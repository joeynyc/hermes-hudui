"""Health check collector — API keys, services, connectivity."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time

from .utils import default_hermes_dir
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
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
class HealthAction:
    name: str
    kind: str = "link"  # refresh, post, tab
    endpoint: str = ""
    target: str = ""
    destructive: bool = False


@dataclass
class DiagnosticStatus:
    name: str
    status: str = "ok"  # ok, warning, broken
    detail: str = ""
    category: str = ""
    updated_at: Optional[datetime] = None
    age_seconds: Optional[int] = None
    depends_on: list[str] = field(default_factory=list)
    suggested_fix: str = ""
    actions: list[HealthAction] = field(default_factory=list)


@dataclass
class HealthState:
    keys: list[KeyStatus] = field(default_factory=list)
    services: list[ServiceStatus] = field(default_factory=list)
    readiness: list[DiagnosticStatus] = field(default_factory=list)
    freshness: list[DiagnosticStatus] = field(default_factory=list)
    database: list[DiagnosticStatus] = field(default_factory=list)
    features: list[DiagnosticStatus] = field(default_factory=list)
    config_model: str = ""
    config_provider: str = ""
    hermes_dir_exists: bool = False
    state_db_exists: bool = False
    state_db_size: int = 0
    session_count: int = 0
    last_session_at: Optional[datetime] = None
    hermes_cli_status: str = "unknown"
    hermes_cli_path: str = ""
    hermes_cli_version: str = ""

    @property
    def verified_agent_version(self) -> str:
        return VERIFIED_AGENT_VERSION

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
    def all_healthy(self) -> bool:
        return self.keys_missing == 0 and all(s.running for s in self.services)

    @property
    def diagnostics_ok(self) -> int:
        return sum(1 for item in self._diagnostics() if item.status == "ok")

    @property
    def diagnostics_warnings(self) -> int:
        return sum(1 for item in self._diagnostics() if item.status == "warning")

    @property
    def diagnostics_broken(self) -> int:
        return sum(1 for item in self._diagnostics() if item.status == "broken")

    def _diagnostics(self) -> list[DiagnosticStatus]:
        return self.readiness + self.freshness + self.database + self.features


# --- Hermes Agent compatibility baseline -------------------------------------
# The HUD reads ~/.hermes/ and shells out to the `hermes` CLI, so it is coupled
# to the agent's on-disk schema and file layout. These constants record the
# agent version this release was verified against and the state.db schema
# version(s) known to be compatible. They drive the "Agent schema version" and
# "Agent data layout" health diagnostics — drift surfaces as a warning instead
# of a silently blank tab. Bump these when re-verifying against a newer agent.
VERIFIED_AGENT_VERSION = "0.19.0"  # hermes-agent v0.19.0 (2026.7.20)
TESTED_SCHEMA_VERSIONS = {16, 23}

# Pre-0.17 → current data-layout moves the HUD already follows. If an OLD path
# is present while its replacement is absent, the agent data predates what this
# HUD targets (label, old_relpath, new_relpath).
LAYOUT_MIGRATIONS = [
    ("memory", "memory", "memories"),
    ("cron jobs", "jobs.json", "cron/jobs.json"),
]


# Known API keys to check
EXPECTED_KEYS = [
    ("ANTHROPIC_API_KEY", "env", "Primary LLM provider"),
    ("OPENROUTER_API_KEY", "env", "OpenRouter fallback provider"),
    ("FIREWORKS_API_KEY", "env", "Fireworks AI provider"),
    ("XAI_API_KEY", "env", "xAI / Grok provider"),
    ("GOOGLE_AI_KEY", "env", "Google AI Studio / Gemini provider"),
    ("MINIMAX_API_KEY", "env", "MiniMax provider"),
    ("NOUS_API_KEY", "env", "Nous Portal provider"),
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


def _diag(
    name: str,
    status: str,
    detail: str,
    category: str,
    depends_on: list[str] | None = None,
    suggested_fix: str = "",
    actions: list[HealthAction] | None = None,
) -> DiagnosticStatus:
    return DiagnosticStatus(
        name=name,
        status=status,
        detail=detail,
        category=category,
        depends_on=depends_on or [],
        suggested_fix=suggested_fix,
        actions=actions or [HealthAction(name="Recheck", kind="refresh")],
    )


def _file_diag(name: str, path: Path, category: str, missing_status: str = "warning") -> DiagnosticStatus:
    if not path.exists():
        return _diag(
            name,
            missing_status,
            f"{path} missing",
            category,
            depends_on=[str(path)],
            suggested_fix=f"Create or restore {path}.",
        )
    if os.access(path, os.R_OK):
        return _diag(name, "ok", f"{path} readable", category, depends_on=[str(path)])
    return _diag(
        name,
        "broken",
        f"{path} not readable",
        category,
        depends_on=[str(path)],
        suggested_fix=f"Fix read permissions for {path}.",
    )


def _freshness_diag(name: str, path: Path, warning_after: int, broken_after: int) -> DiagnosticStatus:
    if not path.exists():
        return _diag(
            name,
            "warning",
            f"{path} missing",
            "freshness",
            depends_on=[str(path)],
            suggested_fix=f"Generate or restore {path}.",
        )
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _diag(name, "broken", f"{path} stat failed", "freshness", depends_on=[str(path)])
    age = int(time.time() - mtime)
    status = "ok"
    if age > broken_after:
        status = "broken"
    elif age > warning_after:
        status = "warning"
    return DiagnosticStatus(
        name=name,
        status=status,
        detail=f"updated {age}s ago",
        category="freshness",
        updated_at=datetime.fromtimestamp(mtime),
        age_seconds=age,
        depends_on=[str(path)],
        suggested_fix="Recheck after Hermes writes fresh data." if status != "ok" else "",
        actions=[HealthAction(name="Recheck", kind="refresh")],
    )


def _hermes_cli_info() -> tuple[str, str, str]:
    path = shutil.which("hermes")
    if not path:
        return "broken", "", "hermes CLI not found"
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = (result.stdout or result.stderr).strip()
        if result.returncode == 0:
            return "ok", path, version or "version unavailable"
        return "warning", path, version or "version check failed"
    except (OSError, subprocess.TimeoutExpired):
        return "warning", path, "version check failed"


def _db_tables_and_columns(
    db_path: Path,
) -> tuple[set[str], dict[str, set[str]], int, Optional[datetime], Optional[int]]:
    if not db_path.exists():
        return set(), {}, 0, None, None

    tables: set[str] = set()
    columns: dict[str, set[str]] = {}
    session_count = 0
    last_session_at: Optional[datetime] = None
    schema_version: Optional[int] = None
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {str(row[0]) for row in cursor.fetchall()}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns[table] = {str(row[1]) for row in cursor.fetchall()}
        if "sessions" in tables:
            cursor.execute("SELECT COUNT(*), MAX(started_at) FROM sessions")
            count, latest = cursor.fetchone()
            session_count = int(count or 0)
            if latest:
                last_session_at = datetime.fromtimestamp(float(latest))
        if "schema_version" in tables:
            cursor.execute("SELECT * FROM schema_version")
            row = cursor.fetchone()
            if row and isinstance(row[0], int):
                schema_version = row[0]
    finally:
        conn.close()
    return tables, columns, session_count, last_session_at, schema_version


def _schema_diag(
    name: str,
    tables: set[str],
    columns: dict[str, set[str]],
    table: str,
    required_columns: set[str] | None = None,
) -> DiagnosticStatus:
    if table not in tables:
        return _diag(
            name,
            "broken",
            f"{table} table missing",
            "database",
            depends_on=["state.db", table],
            suggested_fix="Run Hermes once or migrate/restore the state database.",
        )
    missing = sorted((required_columns or set()) - columns.get(table, set()))
    if missing:
        return _diag(
            name,
            "broken",
            f"missing columns: {', '.join(missing)}",
            "database",
            depends_on=["state.db", table],
            suggested_fix="Update Hermes or migrate/restore state.db so HUD can read the expected schema.",
        )
    return _diag(name, "ok", f"{table} ready", "database", depends_on=["state.db", table])


def _schema_version_diag(version: Optional[int]) -> DiagnosticStatus:
    """Compare the live state.db schema version against the verified baseline.

    Degrades to ``ok`` when the version cannot be read (older agents, or test
    fixtures without a schema_version table) so absence is never treated as a
    failure — only a positively-detected newer/unknown version warns.
    """
    tested = ", ".join(str(v) for v in sorted(TESTED_SCHEMA_VERSIONS))
    if version is None or version in TESTED_SCHEMA_VERSIONS:
        detail = (
            f"schema version not reported; HUD verified against schema {tested}"
            if version is None
            else f"schema v{version} matches verified baseline"
        )
        return _diag("Agent schema version", "ok", detail, "database", depends_on=["state.db"])
    return _diag(
        "Agent schema version",
        "warning",
        f"schema v{version} differs from HUD-verified schema {tested}; collectors may need updating",
        "database",
        depends_on=["state.db"],
        suggested_fix=(
            "Agent state.db schema drifted from the version this HUD was verified "
            f"against (v{VERIFIED_AGENT_VERSION}). Verify collectors against the new "
            "schema, then bump TESTED_SCHEMA_VERSIONS."
        ),
    )


def _layout_diag(hermes_path: Path) -> DiagnosticStatus:
    """Detect pre-0.17 ~/.hermes/ data layout the HUD no longer reads from.

    Only flags when an OLD path exists while its current replacement is absent —
    a fresh/empty dir (neither present) is reported ``ok`` so the check never
    fires spuriously on new installs or test fixtures.
    """
    drifted: list[str] = []
    for label, old_rel, new_rel in LAYOUT_MIGRATIONS:
        old_path = hermes_path / old_rel
        new_path = hermes_path / new_rel
        if old_path.exists() and not new_path.exists():
            drifted.append(f"{label}: found {old_rel}/, expected {new_rel}")
    if drifted:
        return _diag(
            "Agent data layout",
            "warning",
            "; ".join(drifted),
            "readiness",
            depends_on=["Hermes Home"],
            suggested_fix=(
                f"Agent data predates the layout this HUD targets (v{VERIFIED_AGENT_VERSION}). "
                "Update Hermes, or the affected tabs may read empty."
            ),
        )
    return _diag(
        "Agent data layout",
        "ok",
        f"matches verified layout (v{VERIFIED_AGENT_VERSION})",
        "readiness",
        depends_on=["Hermes Home"],
    )


def _feature_diag(
    name: str,
    ok: bool,
    detail: str,
    warn: bool = False,
    depends_on: list[str] | None = None,
    suggested_fix: str = "",
    actions: list[HealthAction] | None = None,
) -> DiagnosticStatus:
    status = "ok" if ok else ("warning" if warn else "broken")
    return _diag(
        name,
        status,
        detail,
        "features",
        depends_on=depends_on,
        suggested_fix=suggested_fix,
        actions=actions,
    )


def _sort_diagnostics(items: list[DiagnosticStatus]) -> list[DiagnosticStatus]:
    severity_rank = {"broken": 0, "warning": 1, "ok": 2}
    return sorted(items, key=lambda item: (severity_rank.get(item.status, 3), item.name.lower()))


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

    state.readiness.extend([
        _file_diag("Hermes Home", hermes_path, "readiness", "broken"),
        _file_diag("Config", hermes_path / "config.yaml", "readiness", "warning"),
        _file_diag("Environment", hermes_path / ".env", "readiness", "warning"),
        _file_diag("State Database", state_db, "readiness", "broken"),
        _file_diag("Logs", hermes_path / "logs", "readiness", "warning"),
        _file_diag("Model Cache", hermes_path / "models_dev_cache.json", "readiness", "warning"),
        _file_diag("Plugins", hermes_path / "plugins", "readiness", "warning"),
        _layout_diag(hermes_path),
    ])

    cli_status, cli_path, cli_version = _hermes_cli_info()
    state.hermes_cli_status = cli_status
    state.hermes_cli_path = cli_path
    state.hermes_cli_version = cli_version
    state.readiness.append(_diag("Hermes CLI", cli_status, cli_version, "readiness"))

    state.freshness.extend([
        _freshness_diag("state.db", state_db, warning_after=3600, broken_after=86400),
        _freshness_diag("models_dev_cache.json", hermes_path / "models_dev_cache.json", warning_after=86400 * 7, broken_after=86400 * 30),
    ])

    try:
        tables, columns, session_count, last_session_at, schema_version = _db_tables_and_columns(state_db)
    except sqlite3.DatabaseError as exc:
        tables, columns, session_count, last_session_at, schema_version = set(), {}, 0, None, None
        state.database.append(_diag(
            "state.db integrity",
            "broken",
            str(exc),
            "database",
            depends_on=[str(state_db)],
            suggested_fix="Restore state.db from a valid Hermes state database.",
        ))

    state.session_count = session_count
    state.last_session_at = last_session_at
    if last_session_at:
        age = int(time.time() - last_session_at.timestamp())
        state.freshness.append(DiagnosticStatus(
            name="last session",
            status="ok" if age <= 86400 * 7 else "warning",
            detail=f"{session_count} sessions; latest {age}s ago",
            category="freshness",
            updated_at=last_session_at,
            age_seconds=age,
        ))
    else:
        state.freshness.append(_diag(
            "last session",
            "warning",
            "no sessions recorded",
            "freshness",
            depends_on=["sessions"],
            suggested_fix="Start a Hermes session, then recheck health.",
            actions=[HealthAction(name="Open Chat", kind="tab", target="chat"), HealthAction(name="Recheck", kind="refresh")],
        ))

    session_columns = {
        "id", "source", "started_at", "message_count", "tool_call_count",
        "input_tokens", "output_tokens", "estimated_cost_usd",
    }
    model_columns = {"model", "billing_provider", "actual_cost_usd"}
    state.database.extend([
        _schema_diag("sessions table", tables, columns, "sessions", session_columns),
        _schema_diag("messages table", tables, columns, "messages", {"session_id", "role", "content"}),
        _schema_diag("tool calls column", tables, columns, "messages", {"tool_calls"}),
        _schema_diag("model analytics columns", tables, columns, "sessions", model_columns),
        _schema_version_diag(schema_version),
    ])

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
    state.services = [service for service in state.services if service is not None]

    db_ok = any(item.name == "sessions table" and item.status == "ok" for item in state.database)
    messages_ok = any(item.name == "messages table" and item.status == "ok" for item in state.database)
    model_ok = any(item.name == "model analytics columns" and item.status == "ok" for item in state.database)
    config_ok = bool(state.config_provider and state.config_model)
    logs_ok = any(item.name == "Logs" and item.status == "ok" for item in state.readiness)
    plugins_ok = any(item.name == "Plugins" and item.status == "ok" for item in state.readiness)
    gateway_ok = logs_ok or any(service.running for service in state.services)

    state.features.extend([
        _feature_diag(
            "Chat",
            cli_status != "broken" and config_ok and db_ok and messages_ok,
            "requires Hermes CLI, config, sessions, and messages",
            depends_on=["Hermes CLI", "Config", "sessions table", "messages table"],
            suggested_fix="Fix the broken dependency above, then retry chat.",
            actions=[HealthAction(name="Open Chat", kind="tab", target="chat"), HealthAction(name="Recheck", kind="refresh")],
        ),
        _feature_diag(
            "Sessions",
            db_ok,
            "requires sessions table",
            depends_on=["state.db", "sessions table"],
            suggested_fix="Restore or migrate state.db so the sessions table is available.",
            actions=[HealthAction(name="Open Sessions", kind="tab", target="sessions"), HealthAction(name="Recheck", kind="refresh")],
        ),
        _feature_diag(
            "Model Analytics",
            db_ok and model_ok,
            "requires model/cost columns in sessions",
            depends_on=["state.db", "sessions.model", "sessions.billing_provider", "sessions.actual_cost_usd"],
            suggested_fix="Update Hermes or migrate state.db to include model analytics columns.",
            actions=[
                HealthAction(name="Open Models", kind="tab", target="model-info"),
                HealthAction(name="Clear HUD cache", kind="post", endpoint="/api/cache/clear"),
                HealthAction(name="Recheck", kind="refresh"),
            ],
        ),
        _feature_diag(
            "Gateway",
            gateway_ok,
            "uses gateway logs or a running gateway service",
            warn=logs_ok,
            depends_on=["logs", "gateway service"],
            suggested_fix="Restart the gateway, then recheck health.",
            actions=[
                HealthAction(name="Open Gateway", kind="tab", target="gateway"),
                HealthAction(name="Restart gateway", kind="post", endpoint="/api/gateway/restart"),
                HealthAction(name="Recheck", kind="refresh"),
            ],
        ),
        _feature_diag(
            "Providers",
            bool(state.keys),
            "uses configured provider keys",
            depends_on=[".env", "auth.json", "config.yaml"],
            suggested_fix="Add the configured provider credentials, then recheck health.",
            actions=[HealthAction(name="Open Providers", kind="tab", target="providers"), HealthAction(name="Recheck", kind="refresh")],
        ),
        _feature_diag(
            "Plugins",
            plugins_ok,
            "requires plugins directory",
            warn=not plugins_ok,
            depends_on=["plugins"],
            suggested_fix="Create the Hermes plugins directory or install a plugin.",
            actions=[HealthAction(name="Open Plugins", kind="tab", target="plugins"), HealthAction(name="Recheck", kind="refresh")],
        ),
        _feature_diag(
            "Sudo",
            db_ok and messages_ok and logs_ok,
            "uses messages and gateway logs",
            warn=db_ok and messages_ok,
            depends_on=["messages table", "logs/gateway.log"],
            suggested_fix="Ensure gateway logs are readable so sudo approvals can be classified.",
            actions=[HealthAction(name="Open Sudo", kind="tab", target="sudo"), HealthAction(name="Recheck", kind="refresh")],
        ),
        _feature_diag(
            "Cron",
            cli_status != "broken",
            "uses Hermes CLI for cron actions",
            depends_on=["Hermes CLI"],
            suggested_fix="Install Hermes CLI or fix PATH.",
            actions=[HealthAction(name="Open Cron", kind="tab", target="cron"), HealthAction(name="Recheck", kind="refresh")],
        ),
    ])

    state.readiness = _sort_diagnostics(state.readiness)
    state.freshness = _sort_diagnostics(state.freshness)
    state.database = _sort_diagnostics(state.database)
    state.features = _sort_diagnostics(state.features)

    return state
