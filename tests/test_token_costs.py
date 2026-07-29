import asyncio
import sqlite3
from datetime import date, datetime, timedelta
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

    data = asyncio.run(get_token_costs())

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

    data = asyncio.run(get_token_costs())

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

    data = asyncio.run(get_token_costs())

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
    data = asyncio.run(get_token_costs())

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
        "gpt-5.6-sol": (5.00, 30.00),
        "gpt-5.6-terra": (2.50, 15.00),
        "gpt-5.6-luna": (1.00, 6.00),
    }
    for model_id, (input_price, output_price) in expected.items():
        for candidate in (model_id, f"openai/{model_id}", f"{model_id}-pro"):
            pricing, matched = _get_pricing(candidate)
            assert matched == model_id
            assert pricing["input"] == input_price
            assert pricing["output"] == output_price


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


def test_sonnet_5_intro_pricing_expires_2026_09_01() -> None:
    """Tripwire: fails once Sonnet 5's introductory rate lapses.

    The $2/$10 rate is introductory through 2026-08-31; the standard tier is
    $3/$15. A static table can't tell the two eras apart, so this test forces
    the switch to be a deliberate edit rather than silent drift.
    """
    pricing, _ = _get_pricing("claude-sonnet-5")
    if date.today() < date(2026, 9, 1):
        assert pricing["input"] == 2.00 and pricing["output"] == 10.00
    else:
        assert pricing == _SONNET_5_STANDARD, (
            "Sonnet 5 introductory pricing expired 2026-08-31 — point "
            "MODEL_PRICING['claude-sonnet-5'] at _SONNET_5_STANDARD ($3/$15)."
        )


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

    data = asyncio.run(get_token_costs())

    assert data["all_time"]["estimated_cost_usd"] == 0.21
    assert data["all_time"]["actual_cost_usd"] == 0
    assert data["all_time"]["billed_cost_usd"] == 0.21
    assert data["all_time"]["actual_coverage_pct"] == 0


def test_token_costs_prices_minimax_models(tmp_path: Path, monkeypatch) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    _insert_session(
        db_path,
        id="minimax-m3",
        source="cli",
        title="MiniMax M3 request",
        started_at=datetime.now().timestamp(),
        model="MiniMax-M3",
        input_tokens=500_000,
        output_tokens=1_000_000,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )
    _insert_session(
        db_path,
        id="minimax-m2-7",
        source="cli",
        title="MiniMax M2.7 request",
        started_at=datetime.now().timestamp(),
        model="MiniMax-M2.7",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=1_000_000,
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = asyncio.run(get_token_costs())

    m3 = next(m for m in data["by_model"] if m["model"] == "MiniMax-M3")
    m27 = next(m for m in data["by_model"] if m["model"] == "MiniMax-M2.7")
    assert m3["matched_pricing"] == "minimax-m3"
    assert m3["estimated_cost_usd"] == 2.70
    assert m27["matched_pricing"] == "minimax-m2.7"
    assert m27["estimated_cost_usd"] == 1.94
    m3_pricing = data["pricing_table"]["minimax-m3"]
    assert m3_pricing["input"] == 0.60
    assert m3_pricing["output"] == 2.40
    assert m3_pricing["cache_read"] == 0.12
    assert m3_pricing["cache_write"] is None
    assert m3_pricing["reasoning"] == 0.60
    assert "pricing_tiers" not in m3_pricing
    assert data["pricing_table"]["minimax-m2.7"] == {
        "input": 0.30,
        "output": 1.20,
        "cache_read": 0.06,
        "cache_write": 0.375,
        "reasoning": 0.30,
    }


def test_token_costs_prices_large_minimax_m3_prompt(
    tmp_path: Path, monkeypatch
) -> None:
    hermes_dir = tmp_path / "hermes"
    hermes_dir.mkdir()
    db_path = hermes_dir / "state.db"
    _make_state_db(db_path)
    _insert_session(
        db_path,
        id="minimax-m3-large",
        source="cli",
        title="Large MiniMax M3 request",
        started_at=datetime.now().timestamp(),
        model="MiniMax-M3",
        input_tokens=513_000,
        output_tokens=1_000_000,
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_dir))

    data = asyncio.run(get_token_costs())

    m3 = next(m for m in data["by_model"] if m["model"] == "MiniMax-M3")
    assert m3["estimated_cost_usd"] == 2.71
