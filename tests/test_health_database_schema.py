import sqlite3

from backend.collectors.health import _collect_database_checks


def _create_state_db(path, include_tool_calls=True):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
    tool_calls_col = ", tool_calls TEXT" if include_tool_calls else ""
    conn.execute(f"CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT{tool_calls_col})")
    conn.commit()
    conn.close()


def test_health_checks_messages_tool_calls_column_not_tool_calls_table(tmp_path):
    db_path = tmp_path / "state.db"
    _create_state_db(db_path, include_tool_calls=True)

    checks = {check.name: check for check in _collect_database_checks(db_path)}

    assert checks["sessions table"].present
    assert checks["messages table"].present
    assert checks["messages.tool_calls column"].present
    assert checks["messages.tool_calls column"].note == "stored on messages table"
    assert "tool_calls table" not in checks


def test_health_reports_missing_messages_tool_calls_column(tmp_path):
    db_path = tmp_path / "state.db"
    _create_state_db(db_path, include_tool_calls=False)

    checks = {check.name: check for check in _collect_database_checks(db_path)}

    assert checks["sessions table"].present
    assert checks["messages table"].present
    assert not checks["messages.tool_calls column"].present
    assert checks["messages.tool_calls column"].note == "missing column"


def test_health_reports_missing_state_db(tmp_path):
    checks = _collect_database_checks(tmp_path / "state.db")

    assert all(not check.present for check in checks)
    assert {check.note for check in checks} == {"state.db missing"}
