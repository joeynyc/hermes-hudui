"""Tests for Claude Code cost parsing and estimation."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from backend.api.cc_costs import _parse_sessions, _get_pricing, _calc_cost, _cache_savings


# ── helpers ────────────────────────────────────────────


def _make_jsonl(path: Path, entries: list[dict]) -> None:
    """Write a list of message dicts as a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _assistant_msg(
    model: str = "claude-sonnet-4-6",
    inp: int = 1000,
    out: int = 500,
    cache_r: int = 0,
    cache_w: int = 0,
    *,
    timestamp: str | None = None,
    tool_use_blocks: int = 0,
) -> dict:
    content = []
    for _ in range(tool_use_blocks):
        content.append({"type": "tool_use", "id": "tu_1", "name": "read", "input": {}})
    content.append({"type": "text", "text": "Hello"})

    msg = {
        "type": "assistant",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": inp,
                "output_tokens": out,
                "cache_read_input_tokens": cache_r,
                "cache_creation_input_tokens": cache_w,
            },
            "content": content,
        },
    }
    if timestamp:
        msg["timestamp"] = timestamp
    return msg


# ── unit: pricing ──────────────────────────────────────


def test_get_pricing_known_model():
    pricing, matched = _get_pricing("claude-sonnet-4-6")
    assert matched == "claude-sonnet-4-6"
    assert pricing["input"] == 3.00
    assert pricing["output"] == 15.00


def test_get_pricing_unknown_model_falls_back():
    pricing, matched = _get_pricing("some-future-model-v99")
    assert matched.startswith("unpriced")
    assert pricing["input"] == 0.0


def test_get_pricing_none():
    pricing, matched = _get_pricing(None)
    assert "unpriced" in matched
    assert pricing["input"] == 0.0


def test_get_pricing_local_model():
    pricing, matched = _get_pricing("gemma-3-27b")
    assert "free" in matched
    assert pricing["input"] == 0.0


def test_calc_cost():
    tokens = {"input": 1_000_000, "output": 500_000, "cache_read": 100_000, "cache_write": 50_000}
    pricing = {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75}
    cost = _calc_cost(tokens, pricing)
    # (1M/1M)*3 + (500k/1M)*15 + (100k/1M)*0.30 + (50k/1M)*3.75
    # = 3 + 7.5 + 0.03 + 0.1875 = 10.7175
    assert round(cost, 4) == 10.7175


def test_cache_savings():
    tokens = {"input": 100, "output": 100, "cache_read": 1_000_000, "cache_write": 100}
    pricing = {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75}
    savings = _cache_savings(tokens, pricing)
    # full_price = (1M/1M)*3 = 3.0, discounted = (1M/1M)*0.30 = 0.30
    # savings = 3.0 - 0.30 = 2.70
    assert round(savings, 2) == 2.70


# ── integration: _parse_sessions ───────────────────────


def test_parse_sessions_no_claude_dir(tmp_path: Path, monkeypatch):
    """When ~/.claude/projects doesn't exist, return None."""
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", tmp_path / "nonexistent")
    result = _parse_sessions()
    assert result is None


def test_parse_sessions_empty_dir(tmp_path: Path, monkeypatch):
    """Empty project dir returns zeroed data."""
    claude_dir = tmp_path / "claude" / "projects"
    claude_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    result = _parse_sessions()
    assert result is not None
    assert result["today"]["session_count"] == 0
    assert result["all_time"]["session_count"] == 0
    assert result["by_model"] == []
    assert result["top_sessions"] == []
    assert result["daily_trend"] == []


def test_parse_single_session(tmp_path: Path, monkeypatch):
    """One session with known model — verify aggregation."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-myproject"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().isoformat()

    _make_jsonl(
        project_dir / "abc123.jsonl",
        [
            _assistant_msg("claude-sonnet-4-6", inp=100_000, out=10_000, timestamp=ts),
            _assistant_msg("claude-sonnet-4-6", inp=50_000, out=5_000, timestamp=ts),
        ],
    )

    result = _parse_sessions()
    assert result is not None

    # today
    assert result["today"]["session_count"] == 1
    assert result["today"]["message_count"] == 2
    assert result["today"]["input_tokens"] == 150_000
    assert result["today"]["output_tokens"] == 15_000

    # Estimated cost: (150k/1M)*3 + (15k/1M)*15 = 0.45 + 0.225 = 0.675
    assert abs(result["today"]["estimated_cost_usd"] - 0.68) <= 0.02
    assert abs(result["today"]["billed_cost_usd"] - 0.68) <= 0.02

    # all_time
    assert result["all_time"]["session_count"] == 1
    assert result["all_time"]["message_count"] == 2

    # by_model
    assert len(result["by_model"]) == 1
    assert result["by_model"][0]["model"] == "claude-sonnet-4-6"
    assert result["by_model"][0]["session_count"] == 1

    # daily_trend
    assert len(result["daily_trend"]) == 1
    assert result["daily_trend"][0]["date"] == today

    # top_sessions
    assert len(result["top_sessions"]) == 1
    assert result["top_sessions"][0]["id"] == "abc123"


def test_parse_multi_model_session(tmp_path: Path, monkeypatch):
    """Session using multiple models — per-model aggregation works."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-multi"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    ts = datetime.now().isoformat()

    _make_jsonl(
        project_dir / "multi.jsonl",
        [
            _assistant_msg("claude-sonnet-4-6", inp=100_000, out=10_000, timestamp=ts),
            _assistant_msg("claude-haiku-3-5", inp=10_000, out=1_000, timestamp=ts),
            _assistant_msg("claude-sonnet-4-6", inp=50_000, out=5_000, timestamp=ts),
        ],
    )

    result = _parse_sessions()
    assert result is not None

    models = {m["model"]: m for m in result["by_model"]}
    assert len(models) == 2
    assert models["claude-sonnet-4-6"]["message_count"] == 2
    assert models["claude-haiku-3-5"]["message_count"] == 1
    assert models["claude-sonnet-4-6"]["input_tokens"] == 150_000
    assert models["claude-haiku-3-5"]["input_tokens"] == 10_000


def test_parse_skips_non_assistant_messages(tmp_path: Path, monkeypatch):
    """user and system messages are ignored."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-skip"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    ts = datetime.now().isoformat()

    _make_jsonl(
        project_dir / "skip.jsonl",
        [
            {"type": "user", "message": {"role": "user", "content": "Hello"}},
            _assistant_msg("claude-sonnet-4-6", inp=100_000, out=10_000, timestamp=ts),
            {"type": "system", "message": {"role": "system", "content": "Init"}},
        ],
    )

    result = _parse_sessions()
    assert result is not None
    assert result["today"]["message_count"] == 1
    assert result["today"]["input_tokens"] == 100_000


def test_parse_handles_tool_use_counting(tmp_path: Path, monkeypatch):
    """Tool use blocks in content are counted."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-tools"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    ts = datetime.now().isoformat()

    _make_jsonl(
        project_dir / "tools.jsonl",
        [
            _assistant_msg("claude-sonnet-4-6", inp=100_000, out=10_000, tool_use_blocks=3, timestamp=ts),
        ],
    )

    result = _parse_sessions()
    assert result is not None
    assert result["all_time"]["tool_call_count"] == 3


def test_parse_trend_7day_comparison(tmp_path: Path, monkeypatch):
    """7-day trend comparison groups sessions correctly."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-trend"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    now = datetime.now()

    # Recent session (within 7 days) — expensive
    _make_jsonl(
        project_dir / "recent.jsonl",
        [
            _assistant_msg(
                "claude-sonnet-4-6",
                inp=1_000_000, out=100_000,
                timestamp=(now - timedelta(days=2)).isoformat(),
            ),
        ],
    )

    # Old session (8-14 days ago) — cheap
    _make_jsonl(
        project_dir / "old.jsonl",
        [
            _assistant_msg(
                "claude-sonnet-4-6",
                inp=100_000, out=10_000,
                timestamp=(now - timedelta(days=10)).isoformat(),
            ),
        ],
    )

    result = _parse_sessions()
    assert result is not None

    ts = result["trend_summary"]
    # Recent: (1M/1M)*3 + (100k/1M)*15 = 3 + 1.5 = 4.50
    assert ts["recent_7d_cost_usd"] == 4.50
    # Previous: (100k/1M)*3 + (10k/1M)*15 = 0.30 + 0.15 = 0.45
    assert ts["previous_7d_cost_usd"] == 0.45
    assert ts["delta_usd"] == 4.05
    assert ts["direction"] == "up"


def test_parse_top_sessions_sorted_by_cost(tmp_path: Path, monkeypatch):
    """Top sessions are sorted descending by billed cost."""
    claude_dir = tmp_path / "claude" / "projects"
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    now = datetime.now()

    for i, (inp, out) in enumerate([(100_000, 10_000), (1_000_000, 100_000), (500_000, 50_000)]):
        proj_dir = claude_dir / f"test-user-proj{i}"
        proj_dir.mkdir(parents=True)
        _make_jsonl(
            proj_dir / f"session{i}.jsonl",
            [
                _assistant_msg(
                    "claude-sonnet-4-6", inp=inp, out=out,
                    timestamp=(now - timedelta(days=i)).isoformat(),
                ),
            ],
        )

    result = _parse_sessions()
    assert result is not None
    top = result["top_sessions"]
    assert len(top) == 3
    # Most expensive first
    assert top[0]["billed_cost_usd"] > top[1]["billed_cost_usd"]
    assert top[1]["billed_cost_usd"] > top[2]["billed_cost_usd"]


def test_parse_handles_malformed_jsonl(tmp_path: Path, monkeypatch):
    """Malformed lines are skipped gracefully."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-bad"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    ts = datetime.now().isoformat()

    _make_jsonl(
        project_dir / "bad.jsonl",
        [
            {"type": "user", "message": "not even json"},  # This IS valid JSON
            _assistant_msg("claude-sonnet-4-6", inp=100_000, out=10_000, timestamp=ts),
        ],
    )
    # Append a genuinely malformed line
    with open(project_dir / "bad.jsonl", "a") as f:
        f.write("this is not json\n")

    result = _parse_sessions()
    assert result is not None
    assert result["today"]["message_count"] == 1  # Only the valid assistant msg counted


def test_parse_handles_missing_tokens(tmp_path: Path, monkeypatch):
    """Messages with no usage are skipped."""
    claude_dir = tmp_path / "claude" / "projects"
    project_dir = claude_dir / "test-user-nousage"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.api.cc_costs.CLAUDE_DIR", claude_dir)

    ts = datetime.now().isoformat()

    _make_jsonl(
        project_dir / "nousage.jsonl",
        [
            {
                "type": "assistant",
                "message": {
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                    "content": [{"type": "text", "text": "no tokens"}],
                },
                "timestamp": ts,
            },
            _assistant_msg("claude-sonnet-4-6", inp=100_000, out=10_000, timestamp=ts),
        ],
    )

    result = _parse_sessions()
    assert result is not None
    assert result["today"]["message_count"] == 1


def test_cc_costs_route_registered(registered_routes):
    """GET /api/cc-costs is registered on the app."""
    assert ("GET", "/api/cc-costs") in registered_routes
