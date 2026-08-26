import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from backend.api.token_costs import _SONNET_5_STANDARD, _get_pricing, get_token_costs


def _make_state_db(path: Path, *, include_actual_cost: bool = True) -> None:
    actual_cost = "actual_cost_usd REAL," if include_actual_cost else ""
    conn = sqlite3.connect(path)
    conn.executescript(
        f"""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            started_at REAL,
            model TEXT,
            message_count INTEGER DEFAULT 0,
            tool_call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            {actual_cost}
            estimated_cost_usd REAL DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


def _insert_session(path: Path, **values) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"INSERT INTO sessions ({columns}) VALUES ({placeholders})",
            list(values.values()),
        )


def test_token_costs_returns_empty_report_before_state_db_exists(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = get_token_costs()

    assert data["today"]["session_count"] == 0
    assert data["all_time"]["total_tokens"] == 0
    assert data["all_time"]["tool_call_count"] == 0
    assert data["by_model"] == []
    assert data["daily_trend"] == []
    assert data["trend_summary"]["direction"] == "flat"


def test_token_costs_returns_empty_report_before_sessions_table_exists(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    sqlite3.connect(hermes_dir / "state.db").close()
    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = get_token_costs()

    assert data["all_time"]["session_count"] == 0
    assert data["top_sessions"] == []


def test_token_costs_reports_actual_deltas_cache_savings_and_top_sessions(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    now = datetime.now()

    _insert_session(
        db_path,
        id="cheap",
        source="cli",
        title="Small request",
        started_at=(now - timedelta(days=9)).timestamp(),
        model="claude-sonnet-4-6",
        message_count=2,
        tool_call_count=1,
        input_tokens=100_000,
        output_tokens=10_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=10_000,
        reasoning_tokens=0,
        actual_cost_usd=0.99,
    )
    _insert_session(
        db_path,
        id="expensive",
        source="cli",
        title="Large request",
        started_at=now.timestamp(),
        model="claude-sonnet-4-6",
        message_count=4,
        tool_call_count=3,
        input_tokens=200_000,
        output_tokens=20_000,
        cache_read_tokens=2_000_000,
        cache_write_tokens=20_000,
        reasoning_tokens=10_000,
        actual_cost_usd=1.70,
    )
    _insert_session(
        db_path,
        id="estimated-only",
        source="cli",
        title="Estimated only",
        started_at=(now - timedelta(days=1)).timestamp(),
        model="gpt-4o-mini",
        message_count=1,
        input_tokens=1_000_000,
        output_tokens=100_000,
        actual_cost_usd=None,
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = get_token_costs()

    assert data["all_time"]["session_count"] == 3
    assert data["all_time"]["estimated_cost_usd"] == 2.6
    assert data["all_time"]["actual_cost_usd"] == 2.69
    assert data["all_time"]["billed_cost_usd"] == 2.90
    assert data["all_time"]["actual_estimated_cost_usd"] == 2.39
    assert data["all_time"]["actual_delta_usd"] == 0.3
    assert data["all_time"]["actual_coverage_pct"] == 66.7
    assert data["all_time"]["cache_savings_usd"] == 8.1
    assert data["top_sessions"][0]["id"] == "expensive"
    assert data["top_sessions"][0]["actual_cost_usd"] == 1.70
    assert data["top_sessions"][0]["estimated_cost_usd"] == 1.6
    assert data["top_sessions"][0]["billed_cost_usd"] == 1.70

    model = next(m for m in data["by_model"] if m["model"] == "claude-sonnet-4-6")
    assert model["estimated_cost_usd"] == 2.39
    assert model["actual_cost_usd"] == 2.69
    assert model["actual_delta_usd"] == 0.3
    assert model["cache_savings_usd"] == 8.1

    assert data["trend_summary"]["recent_7d_cost_usd"] == 1.91
    assert data["trend_summary"]["previous_7d_cost_usd"] == 0.99
    assert data["trend_summary"]["delta_usd"] == 0.92


def test_anthropic_opus_4x_and_fable5_pricing(tmp_path: Path, monkeypatch) -> None:
    """Opus 4.x models use $5/$25 tier; Fable 5 uses $10/$50 tier.

    Regression guard: claude-opus-4-6 was previously priced at the old $15/$75
    Opus 3 rate. Verify the corrected $5/$25 Opus 4.x rate and that Fable 5 and
    Sonnet 5 resolve to their own distinct tiers.
    """
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    now = datetime.now()

    # 1M input + 100k output with each model — easy math
    for model_id in ("claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-4-5"):
        _insert_session(
            db_path,
            id=f"opus-{model_id}",
            source="cli",
            title=f"Opus test {model_id}",
            started_at=(now.timestamp()),
            model=model_id,
            input_tokens=1_000_000,
            output_tokens=100_000,
            actual_cost_usd=None,
        )

    _insert_session(
        db_path,
        id="fable5",
        source="cli",
        title="Fable 5 test",
        started_at=now.timestamp(),
        model="claude-fable-5",
        input_tokens=1_000_000,
        output_tokens=100_000,
        actual_cost_usd=None,
    )

    _insert_session(
        db_path,
        id="sonnet5",
        source="cli",
        title="Sonnet 5 test",
        started_at=now.timestamp(),
        model="claude-sonnet-5",
        input_tokens=1_000_000,
        output_tokens=100_000,
        actual_cost_usd=None,
    )

    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))
    data = get_token_costs()

    # Opus 4.x: input=$5/MTok, output=$25/MTok -> 1M*5 + 0.1M*25 = 5.00 + 2.50 = 7.50 each
    opus_expected = 5.00 + 2.50
    for model_id in ("claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-opus-4-5"):
        model = next(m for m in data["by_model"] if m["model"] == model_id)
        assert model["estimated_cost_usd"] == opus_expected, (
            f"{model_id}: expected ${opus_expected} (Opus 4.x tier), got ${model['estimated_cost_usd']}"
        )

    # Fable 5: input=$10/MTok, output=$50/MTok -> 1M*10 + 0.1M*50 = 10.00 + 5.00 = 15.00
    fable = next(m for m in data["by_model"] if m["model"] == "claude-fable-5")
    assert fable["estimated_cost_usd"] == 15.00

    # Sonnet 5: input=$2/MTok, output=$10/MTok -> 1M*2 + 0.1M*10 = 2.00 + 1.00 = 3.00
    sonnet5 = next(m for m in data["by_model"] if m["model"] == "claude-sonnet-5")
    assert sonnet5["estimated_cost_usd"] == 3.00


def test_current_anthropic_models_are_all_priced() -> None:
    """No current Anthropic model may fall through to the unpriced ($0) default.

    Regression guard: before this was fixed, every model except claude-opus-4-6
    resolved to `unpriced`, silently reporting $0 in the Costs tab.
    """
    for model_id in (
        "claude-opus-5",
        "claude-fable-5",
        "claude-mythos-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-opus-4-5",
        "claude-sonnet-5",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    ):
        pricing, matched = _get_pricing(model_id)
        assert not matched.startswith("unpriced"), f"{model_id} resolved to {matched}"
        assert pricing["input"] > 0 and pricing["output"] > 0, f"{model_id} priced at $0"


def test_current_hermes_openai_models_are_all_priced() -> None:
    expected = {
        "gpt-5.6-sol": (4.00, 20.00),
        "gpt-5.6-terra": (2.00, 12.00),
        "gpt-5.6-luna": (0.20, 1.20),
        "gpt-5.6-cyber": (12.50, 75.00),
        "gpt-5.6": (4.00, 20.00),
        "gpt-5.5": (5.00, 30.00),
    }
    for model_id, (input_price, output_price) in expected.items():
        for candidate in (model_id, f"openai/{model_id}"):
            pricing, matched = _get_pricing(candidate)
            assert matched == model_id
            assert pricing["input"] == input_price
            assert pricing["output"] == output_price

    pricing, matched = _get_pricing("gpt-5.6-sol-pro")
    assert matched == "gpt-5.6-sol"
    assert pricing["input"] == 4.00


def test_model_pricing_lookup_is_case_insensitive_and_claude_dot_compatible() -> None:
    pricing, matched = _get_pricing("Anthropic/Claude-Opus-4.6-20260701")
    assert matched == "claude-opus-4-6"
    assert pricing["input"] == 5.00
    assert pricing["output"] == 25.00

    pricing, matched = _get_pricing("OpenAI/GPT-5.4")
    assert matched == "gpt-5.4"
    assert pricing["input"] == 2.50
    assert pricing["output"] == 15.00


def test_legacy_opus_keeps_the_15_75_tier() -> None:
    """Opus 4.1/4.0 predate the $5/$25 tier and must not be repriced downward."""
    for model_id in ("claude-opus-4-1", "claude-opus-4-0"):
        pricing, matched = _get_pricing(model_id)
        assert matched == model_id
        assert pricing["input"] == 15.00 and pricing["output"] == 75.00


def test_opus_5_uses_the_opus_5_25_tier() -> None:
    pricing, matched = _get_pricing("claude-opus-5")
    assert matched == "claude-opus-5"
    assert pricing["input"] == 5.00
    assert pricing["output"] == 25.00


def test_sonnet_5_keeps_the_2_10_standard_rate() -> None:
    """Anthropic made Sonnet 5's $2/$10 intro rate the permanent standard."""
    pricing, matched = _get_pricing("claude-sonnet-5")
    assert matched == "claude-sonnet-5"
    assert pricing["input"] == 2.00 and pricing["output"] == 10.00
    assert _SONNET_5_STANDARD["input"] == 3.00


def test_current_xai_google_and_deepseek_models_are_priced() -> None:
    expected = {
        "grok-4.6": (2.00, 6.00),
        "grok-4.5": (2.00, 6.00),
        "grok-4.3": (1.25, 2.50),
        "gemini-3.6-flash": (1.50, 7.50),
        "gemini-3.5-flash": (1.50, 9.00),
        "gemini-2.5-flash": (0.30, 2.50),
        "deepseek-v4-flash": (0.22, 0.66),
        "deepseek-v4-pro": (0.66, 1.98),
        "minimax-m3": (0.30, 1.20),
        "qwen3.8-max": (2.00, 6.00),
    }
    for model_id, (input_price, output_price) in expected.items():
        pricing, matched = _get_pricing(model_id)
        assert matched == model_id, f"{model_id} resolved to {matched}"
        assert pricing["input"] == input_price
        assert pricing["output"] == output_price

    pricing, matched = _get_pricing("xai/grok-4.6")
    assert matched == "grok-4.6"
    pricing, matched = _get_pricing("deepseek-v4-flash-0731")
    assert matched == "deepseek-v4-flash"


def test_token_costs_handles_old_schema_without_actual_cost(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path, include_actual_cost=False)
    _insert_session(
        db_path,
        id="legacy",
        source="cli",
        title="Legacy",
        started_at=datetime.now().timestamp(),
        model="gpt-4o-mini",
        input_tokens=1_000_000,
        output_tokens=100_000,
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = get_token_costs()

    assert data["all_time"]["estimated_cost_usd"] == 0.21
    assert data["all_time"]["actual_cost_usd"] == 0
    assert data["all_time"]["billed_cost_usd"] == 0.21
    assert data["all_time"]["actual_coverage_pct"] == 0
