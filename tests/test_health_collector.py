import sqlite3
import time
from pathlib import Path

from backend.collectors.health import collect_health


def _make_state_db(
    path: Path,
    include_messages: bool = True,
    schema_version: int | None = None,
) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            started_at REAL,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0,
            actual_cost_usd REAL DEFAULT 0,
            model TEXT,
            billing_provider TEXT,
            model_config TEXT
        );
        """
    )
    if include_messages:
        conn.executescript(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                tool_calls TEXT,
                timestamp REAL
            );
            """
        )
    if schema_version is not None:
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (schema_version,))
    conn.execute(
        "INSERT INTO sessions (id, source, started_at, message_count, model, billing_provider) VALUES (?, ?, ?, ?, ?, ?)",
        ("s1", "cli", time.time() - 60, 2, "claude-sonnet-4-6", "anthropic"),
    )
    conn.commit()
    conn.close()


def _by_name(items):
    return {item.name: item for item in items}


def test_health_collects_readiness_freshness_and_feature_diagnostics(tmp_path: Path, monkeypatch) -> None:
    _make_state_db(tmp_path / "state.db")
    (tmp_path / "config.yaml").write_text("model:\n  provider: anthropic\n  default: claude-sonnet-4-6\n")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test\n")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "gateway.log").write_text("ok\n")
    (tmp_path / "models_dev_cache.json").write_text("{}")
    (tmp_path / "plugins").mkdir()

    monkeypatch.setattr("backend.collectors.health._check_pid_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_systemd_service", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_process", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._hermes_cli_info", lambda: ("ok", "/usr/bin/hermes", "hermes 1.2.3"))

    state = collect_health(str(tmp_path))

    readiness = _by_name(state.readiness)
    assert readiness["Hermes Home"].status == "ok"
    assert readiness["Config"].status == "ok"
    assert readiness["State Database"].status == "ok"
    assert readiness["Logs"].status == "ok"
    assert readiness["Model Cache"].status == "ok"

    freshness = _by_name(state.freshness)
    assert freshness["state.db"].status == "ok"
    assert freshness["models_dev_cache.json"].status == "ok"
    assert freshness["last session"].status == "ok"
    assert state.session_count == 1

    database = _by_name(state.database)
    assert database["sessions table"].status == "ok"
    assert database["messages table"].status == "ok"
    assert database["tool calls column"].status == "ok"
    assert database["model analytics columns"].status == "ok"

    features = _by_name(state.features)
    assert features["Chat"].status == "ok"
    assert "Hermes CLI" in features["Chat"].depends_on
    assert features["Chat"].suggested_fix
    assert any(action.name == "Recheck" and action.kind == "refresh" for action in features["Chat"].actions)
    assert features["Sessions"].status == "ok"
    assert features["Model Analytics"].status == "ok"
    assert any(action.name == "Clear HUD cache" and action.endpoint == "/api/cache/clear" for action in features["Model Analytics"].actions)
    assert features["Gateway"].status == "ok"
    assert any(action.name == "Restart gateway" and action.endpoint == "/api/gateway/restart" for action in features["Gateway"].actions)
    assert features["Plugins"].status == "ok"

    assert state.hermes_cli_status == "ok"
    assert state.hermes_cli_path == "/usr/bin/hermes"
    assert state.hermes_cli_version == "hermes 1.2.3"
    assert state.diagnostics_ok >= 1
    assert state.diagnostics_broken == 0


def test_health_reports_schema_drift_and_missing_inputs(tmp_path: Path, monkeypatch) -> None:
    _make_state_db(tmp_path / "state.db", include_messages=False)
    (tmp_path / "config.yaml").write_text("provider: anthropic\n")

    monkeypatch.setattr("backend.collectors.health._check_pid_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_systemd_service", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_process", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._hermes_cli_info", lambda: ("broken", "", "hermes CLI not found"))

    state = collect_health(str(tmp_path))

    readiness = _by_name(state.readiness)
    assert readiness["Environment"].status == "warning"
    assert readiness["Logs"].status == "warning"
    assert readiness["Model Cache"].status == "warning"

    database = _by_name(state.database)
    assert database["messages table"].status == "broken"

    features = _by_name(state.features)
    assert features["Chat"].status == "broken"
    assert "Open Health" not in [action.name for action in features["Chat"].actions]
    assert any(action.name == "Open Chat" and action.target == "chat" for action in features["Chat"].actions)
    assert features["Model Analytics"].status == "ok"

    assert state.hermes_cli_status == "broken"
    assert state.diagnostics_broken >= 1


def test_health_diagnostics_are_sorted_by_severity(tmp_path: Path, monkeypatch) -> None:
    _make_state_db(tmp_path / "state.db", include_messages=False)

    monkeypatch.setattr("backend.collectors.health._check_pid_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_systemd_service", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_process", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._hermes_cli_info", lambda: ("broken", "", "hermes CLI not found"))

    state = collect_health(str(tmp_path))

    for items in (state.readiness, state.freshness, state.database, state.features):
        severities = [item.status for item in items]
        assert severities == sorted(severities, key={"broken": 0, "warning": 1, "ok": 2}.get)


def test_health_accepts_current_agent_schema(tmp_path: Path, monkeypatch) -> None:
    _make_state_db(tmp_path / "state.db", schema_version=23)

    monkeypatch.setattr("backend.collectors.health._check_pid_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_systemd_service", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_process", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._hermes_cli_info", lambda: ("ok", "/usr/bin/hermes", "hermes 0.20.3"))

    state = collect_health(str(tmp_path))
    database = _by_name(state.database)

    assert database["Agent schema version"].status == "ok"
    assert "v23" in database["Agent schema version"].detail


def test_health_accepts_agent_schema_26(tmp_path: Path, monkeypatch) -> None:
    _make_state_db(tmp_path / "state.db", schema_version=26)

    monkeypatch.setattr("backend.collectors.health._check_pid_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_systemd_service", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_process", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._hermes_cli_info", lambda: ("ok", "/usr/bin/hermes", "hermes 0.20.3"))

    state = collect_health(str(tmp_path))
    database = _by_name(state.database)

    assert database["Agent schema version"].status == "ok"
    assert "v26" in database["Agent schema version"].detail


def test_health_warns_for_unverified_future_schema(tmp_path: Path, monkeypatch) -> None:
    _make_state_db(tmp_path / "state.db", schema_version=27)

    monkeypatch.setattr("backend.collectors.health._check_pid_file", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_systemd_service", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._check_process", lambda *args, **kwargs: None)
    monkeypatch.setattr("backend.collectors.health._hermes_cli_info", lambda: ("ok", "/usr/bin/hermes", "hermes 0.20.3"))

    state = collect_health(str(tmp_path))
    database = _by_name(state.database)

    assert database["Agent schema version"].status == "warning"
    assert "schema v27" in database["Agent schema version"].detail
    assert "v0.20.3" in database["Agent schema version"].suggested_fix
