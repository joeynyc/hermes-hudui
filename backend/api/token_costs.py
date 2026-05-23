"""Token cost endpoint — calculates estimated USD costs per model."""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from backend.collectors.utils import default_hermes_dir

try:
    router = APIRouter()
except TypeError:
    class _NoopRouter:
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

    router = _NoopRouter()

# ── Pricing per 1M tokens (USD) ──────────────────────────
# Source: https://www.anthropic.com/pricing (April 2026)
# Source: https://openai.com/api/pricing/ (April 2026)

# Shared pricing tiers (reused by aliases below)
_SONNET = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75, "reasoning": 3.00}
_GPT52 = {"input": 1.75, "output": 14.00, "cache_read": 0.88, "cache_write": 1.75, "reasoning": 1.75}
_O_MINI = {"input": 1.10, "output": 4.40, "cache_read": 0.55, "cache_write": 1.10, "reasoning": 1.10}
_DEEPSEEK_V3 = {"input": 0.27, "output": 1.10, "cache_read": 0.07, "cache_write": 0.27, "reasoning": 0.27}
_GROK_FAST = {"input": 0.30, "output": 0.50, "cache_read": 0.075, "cache_write": 0.30, "reasoning": 0.30}
_GEMINI_FLASH_OLD = {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10, "reasoning": 0.10}
_LLAMA = {"input": 0.10, "output": 0.10, "cache_read": 0.025, "cache_write": 0.10, "reasoning": 0.10}
_FREE = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0, "reasoning": 0.0}

MODEL_PRICING: dict[str, dict] = {
    # Anthropic
    "claude-opus-4-6": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75, "reasoning": 15.00},
    "claude-sonnet-4-6": _SONNET,
    "claude-haiku-3-5": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_write": 1.00, "reasoning": 0.80},
    "claude-4-sonnet": _SONNET,
    "claude-3-7-sonnet": _SONNET,
    "claude-3.7-sonnet": _SONNET,
    # Legacy Claude 3.x (date-suffixed names from Anthropic API, e.g. claude-3-5-sonnet-20241022)
    "claude-3-5-sonnet": _SONNET,
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00, "cache_read": 0.08, "cache_write": 1.00, "reasoning": 0.80},
    "claude-3-opus": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75, "reasoning": 15.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75, "reasoning": 3.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.03, "cache_write": 0.30, "reasoning": 0.25},
    # OpenAI
    "gpt-5.4-pro": {"input": 30.00, "output": 180.00, "cache_read": 15.00, "cache_write": 30.00, "reasoning": 30.00},
    "gpt-5.4": {"input": 2.50, "output": 15.00, "cache_read": 1.25, "cache_write": 2.50, "reasoning": 2.50},
    "gpt-5.5": _GPT52,
    "gpt-5.2-codex": _GPT52,
    "gpt-5.2": _GPT52,
    "gpt-4o": {"input": 2.50, "output": 10.00, "cache_read": 1.25, "cache_write": 2.50, "reasoning": 2.50},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cache_read": 0.075, "cache_write": 0.15, "reasoning": 0.15},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60, "cache_read": 0.20, "cache_write": 0.40, "reasoning": 0.40},
    "gpt-4.1": {"input": 2.00, "output": 8.00, "cache_read": 1.00, "cache_write": 2.00, "reasoning": 2.00},
    "o4-mini": _O_MINI,
    "o3-mini": _O_MINI,
    "o1": {"input": 15.00, "output": 60.00, "cache_read": 7.50, "cache_write": 15.00, "reasoning": 15.00},
    # DeepSeek
    "deepseek-v3": _DEEPSEEK_V3,
    "deepseek-chat": _DEEPSEEK_V3,
    "deepseek-r1": {"input": 0.55, "output": 2.19, "cache_read": 0.14, "cache_write": 0.55, "reasoning": 0.55},
    # xAI
    "grok-4": {"input": 2.00, "output": 6.00, "cache_read": 0.50, "cache_write": 2.00, "reasoning": 2.00},
    "grok-3": {"input": 3.00, "output": 15.00, "cache_read": 0.75, "cache_write": 3.00, "reasoning": 3.00},
    "grok-code-fast": _GROK_FAST,
    "grok-3-mini-fast": _GROK_FAST,
    # Google
    "gemini-3.1-pro": {"input": 2.00, "output": 12.00, "cache_read": 0.50, "cache_write": 2.00, "reasoning": 2.00},
    "gemini-3-flash": {"input": 0.50, "output": 3.00, "cache_read": 0.13, "cache_write": 0.50, "reasoning": 0.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "cache_read": 0.31, "cache_write": 4.50, "reasoning": 1.25},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "cache_read": 0.04, "cache_write": 0.15, "reasoning": 0.15},
    "gemini-2.0-flash": _GEMINI_FLASH_OLD,
    "gemini-flash": _GEMINI_FLASH_OLD,
    # Xiaomi
    "mimo-v2.5-pro": {"input": 1.00, "output": 3.00, "cache_read": 0.20, "cache_write": 1.00, "reasoning": 1.00},
    "mimo-v2-pro": {"input": 1.00, "output": 3.00, "cache_read": 0.20, "cache_write": 1.00, "reasoning": 1.00},
    # MiniMax
    "minimax-m2.7-highspeed": {"input": 0.60, "output": 2.40, "cache_read": 0.06, "cache_write": 0.375, "reasoning": 0.60},
    "minimax-m2.7": {"input": 0.30, "output": 1.20, "cache_read": 0.06, "cache_write": 0.375, "reasoning": 0.30},
    "minimax-m2.5-highspeed": {"input": 0.60, "output": 2.40, "cache_read": 0.03, "cache_write": 0.375, "reasoning": 0.60},
    "minimax-m2.5": {"input": 0.30, "output": 1.20, "cache_read": 0.03, "cache_write": 0.375, "reasoning": 0.30},
    # Meta
    "llama-3.3-70b": _LLAMA,
    "llama-4": _LLAMA,
    # Qwen
    "qwen3-coder": {"input": 0.15, "output": 0.80, "cache_read": 0.04, "cache_write": 0.15, "reasoning": 0.15},
    "qwen-3.5-plus": {"input": 0.26, "output": 1.56, "cache_read": 0.065, "cache_write": 0.26, "reasoning": 0.26},
    "qwen-3.5-flash": {"input": 0.065, "output": 0.26, "cache_read": 0.016, "cache_write": 0.065, "reasoning": 0.065},
    # Mistral
    "mistral-small": {"input": 0.15, "output": 0.60, "cache_read": 0.04, "cache_write": 0.15, "reasoning": 0.15},
    "devstral": {"input": 0.40, "output": 2.00, "cache_read": 0.10, "cache_write": 0.40, "reasoning": 0.40},
    # Local / free
    "local": _FREE,
}

# Precomputed for _get_pricing (avoid sorting on every call)
DEFAULT_PRICING = _FREE
_SORTED_KEYS = sorted(MODEL_PRICING, key=len, reverse=True)
_SMALL_MODEL_RE = re.compile(r'[-_](?:1\.?[58]b|3b|4b|7b|8b|9b|13b|14b)\b')


def _get_pricing(model: str | None) -> tuple[dict, str]:
    """Return (pricing_dict, matched_key) for a model."""
    if not model:
        return DEFAULT_PRICING, "unpriced (unknown)"
    # Exact match (case-insensitive)
    lower_model = model.lower()
    if lower_model in MODEL_PRICING:
        return MODEL_PRICING[lower_model], lower_model
    # Partial match (strip provider prefix, try longest key first, case-insensitive)
    base = lower_model.split("/")[-1] if "/" in lower_model else lower_model
    for key in _SORTED_KEYS:
        if base.startswith(key):
            return MODEL_PRICING[key], key
    # Check if it's a local/inference/free model (zero cost)
    if any(kw in lower_model for kw in ("local", "localhost", ":free", "gemma", "nemotron", "mimo-free")):
        return _FREE, "local (free)"
    if _SMALL_MODEL_RE.search(lower_model):
        return _FREE, "local (free)"
    return DEFAULT_PRICING, f"unpriced ({model})"


def _calc_cost(tokens: dict, pricing: dict) -> float:
    return sum(
        (tokens.get(k, 0) / 1_000_000) * pricing.get(k, 0)
        for k in ("input", "output", "cache_read", "cache_write", "reasoning")
    )


def _round_money(value: float | None) -> float:
    return round(float(value or 0), 2)


def _pct(delta: float, base: float) -> float | None:
    if not base:
        return None
    return round((delta / base) * 100, 1)


def _cache_savings(tokens: dict, pricing: dict) -> float:
    full_price = (tokens.get("cache_read", 0) / 1_000_000) * pricing.get("input", 0)
    discounted = (tokens.get("cache_read", 0) / 1_000_000) * pricing.get("cache_read", 0)
    return max(0.0, full_price - discounted)


def _new_bucket() -> dict:
    return {
        "session_count": 0, "message_count": 0,
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_tokens": 0, "cache_write_tokens": 0,
        "reasoning_tokens": 0, "cost": 0.0,
        "estimated_cost": 0.0, "actual_cost": 0.0, "billed_cost": 0.0,
        "actual_estimated_cost": 0.0,
        "actual_session_count": 0, "cache_savings": 0.0,
    }


def _add_usage(
    bucket: dict,
    row: sqlite3.Row,
    tokens: dict,
    estimated: float,
    actual: float | None,
    savings: float,
) -> None:
    billed = actual if actual is not None else estimated
    bucket["session_count"] += 1
    bucket["message_count"] += row["message_count"] or 0
    bucket["input_tokens"] += tokens["input"]
    bucket["output_tokens"] += tokens["output"]
    bucket["cache_read_tokens"] += tokens["cache_read"]
    bucket["cache_write_tokens"] += tokens["cache_write"]
    bucket["reasoning_tokens"] += tokens["reasoning"]
    bucket["cost"] += billed
    bucket["estimated_cost"] += estimated
    bucket["billed_cost"] += billed
    bucket["cache_savings"] += savings
    if actual is not None:
        bucket["actual_cost"] += actual
        bucket["actual_estimated_cost"] += estimated
        bucket["actual_session_count"] += 1


def _finalize_bucket(bucket: dict) -> dict:
    estimated = bucket["estimated_cost"]
    actual = bucket["actual_cost"]
    actual_estimated = bucket["actual_estimated_cost"]
    actual_delta = actual - actual_estimated
    total_tokens = bucket["input_tokens"] + bucket["output_tokens"]
    coverage = (
        bucket["actual_session_count"] / bucket["session_count"] * 100
        if bucket["session_count"] else 0
    )
    return {
        **bucket,
        "total_tokens": total_tokens,
        "cost": _round_money(bucket["cost"]),
        "estimated_cost": _round_money(estimated),
        "actual_cost": _round_money(actual),
        "billed_cost": _round_money(bucket["billed_cost"]),
        "actual_estimated_cost_usd": _round_money(actual_estimated),
        "estimated_cost_usd": _round_money(estimated),
        "actual_cost_usd": _round_money(actual),
        "billed_cost_usd": _round_money(bucket["billed_cost"]),
        "actual_delta_usd": _round_money(actual_delta),
        "actual_delta_pct": _pct(actual_delta, actual_estimated),
        "actual_coverage_pct": round(coverage, 1),
        "cache_savings_usd": _round_money(bucket["cache_savings"]),
    }


@router.get("/token-costs")
async def get_token_costs():
    """Token usage and estimated costs, broken down by model."""
    hermes_dir = default_hermes_dir()
    db_path = str(Path(hermes_dir) / "state.db")

    if not Path(db_path).exists():
        return {"error": "state.db not found"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute("PRAGMA table_info(sessions)")
    columns = {row["name"] for row in cur.fetchall()}
    title_column = "title" if "title" in columns else "id AS title"
    actual_cost_column = (
        "actual_cost_usd"
        if "actual_cost_usd" in columns else "NULL AS actual_cost_usd"
    )
    cur.execute(f"""
        SELECT id, source, {title_column}, started_at, model,
               message_count, tool_call_count,
               input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens,
               reasoning_tokens,
               {actual_cost_column}
        FROM sessions
        ORDER BY started_at ASC
    """)

    # Per-model aggregation
    by_model: dict[str, dict] = {}

    # Today aggregation
    today_data = _new_bucket()

    # All-time totals
    all_input = all_output = all_cache_r = all_cache_w = all_reasoning = 0
    all_messages = all_tool_calls = 0
    all_estimated_cost = 0.0
    all_actual_cost = 0.0
    all_actual_estimated_cost = 0.0
    all_billed_cost = 0.0
    all_cache_savings = 0.0
    actual_sessions = 0
    total_sessions = 0

    # Daily trend
    daily: dict[str, dict] = {}
    top_sessions: list[dict] = []
    recent_start = datetime.now() - timedelta(days=7)
    previous_start = datetime.now() - timedelta(days=14)
    recent_7d_cost = 0.0
    previous_7d_cost = 0.0

    for row in cur.fetchall():
        model = row["model"] or "unknown"
        started_ts = row["started_at"]
        started = datetime.fromtimestamp(started_ts) if started_ts else None
        day = started.strftime("%Y-%m-%d") if started else "unknown"
        is_today = day == today

        tokens = {
            "input": row["input_tokens"] or 0,
            "output": row["output_tokens"] or 0,
            "cache_read": row["cache_read_tokens"] or 0,
            "cache_write": row["cache_write_tokens"] or 0,
            "reasoning": row["reasoning_tokens"] or 0,
        }

        pricing, matched = _get_pricing(model)
        actual_cost = row["actual_cost_usd"]
        actual = float(actual_cost) if actual_cost is not None else None
        estimated = _calc_cost(tokens, pricing)
        cost = actual if actual is not None else estimated
        savings = _cache_savings(tokens, pricing)

        # Per-model
        if model not in by_model:
            by_model[model] = {
                "model": model, "matched_pricing": matched,
                **_new_bucket(),
            }
        m = by_model[model]
        _add_usage(m, row, tokens, estimated, actual, savings)

        # Today
        if is_today:
            _add_usage(today_data, row, tokens, estimated, actual, savings)

        # All-time
        total_sessions += 1
        all_messages += row["message_count"] or 0
        all_tool_calls += row["tool_call_count"] or 0
        all_input += tokens["input"]
        all_output += tokens["output"]
        all_cache_r += tokens["cache_read"]
        all_cache_w += tokens["cache_write"]
        all_reasoning += tokens["reasoning"]
        all_estimated_cost += estimated
        all_billed_cost += cost
        all_cache_savings += savings
        if actual is not None:
            all_actual_cost += actual
            all_actual_estimated_cost += estimated
            actual_sessions += 1

        # Daily
        if day not in daily:
            daily[day] = {
                "cost": 0.0,
                "estimated_cost": 0.0,
                "actual_cost": 0.0,
                "tokens": 0,
                "sessions": 0,
                "cache_savings": 0.0,
            }
        daily[day]["cost"] += cost
        daily[day]["estimated_cost"] += estimated
        if actual is not None:
            daily[day]["actual_cost"] += actual
        daily[day]["tokens"] += tokens["input"] + tokens["output"]
        daily[day]["sessions"] += 1
        daily[day]["cache_savings"] += savings

        if started:
            if started >= recent_start:
                recent_7d_cost += cost
            elif started >= previous_start:
                previous_7d_cost += cost

        top_sessions.append({
            "id": row["id"],
            "source": row["source"] or "unknown",
            "title": row["title"] or row["id"],
            "date": day,
            "model": model,
            "matched_pricing": matched,
            "message_count": row["message_count"] or 0,
            "tool_call_count": row["tool_call_count"] or 0,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cache_read_tokens": tokens["cache_read"],
            "cache_write_tokens": tokens["cache_write"],
            "reasoning_tokens": tokens["reasoning"],
            "total_tokens": tokens["input"] + tokens["output"],
            "estimated_cost_usd": _round_money(estimated),
            "actual_cost_usd": _round_money(actual),
            "billed_cost_usd": _round_money(cost),
            "actual_delta_usd": _round_money(
                (actual - estimated) if actual is not None else 0
            ),
            "cache_savings_usd": _round_money(savings),
        })

    conn.close()

    # Sort models by cost descending
    model_list = sorted(by_model.values(), key=lambda m: -m["cost"])

    model_list = [_finalize_bucket(m) for m in model_list]
    today_final = _finalize_bucket(today_data)

    sorted_days = sorted(daily.keys())
    delta = recent_7d_cost - previous_7d_cost

    return {
        "today": {
            "date": today,
            **today_final,
        },
        "all_time": {
            "session_count": total_sessions,
            "message_count": all_messages,
            "tool_call_count": all_tool_calls,
            "input_tokens": all_input,
            "output_tokens": all_output,
            "cache_read_tokens": all_cache_r,
            "cache_write_tokens": all_cache_w,
            "reasoning_tokens": all_reasoning,
            "total_tokens": all_input + all_output,
            "cost": _round_money(all_billed_cost),
            "estimated_cost_usd": _round_money(all_estimated_cost),
            "actual_cost_usd": _round_money(all_actual_cost),
            "actual_estimated_cost_usd": _round_money(all_actual_estimated_cost),
            "billed_cost_usd": _round_money(all_billed_cost),
            "actual_delta_usd": _round_money(all_actual_cost - all_actual_estimated_cost),
            "actual_delta_pct": _pct(
                all_actual_cost - all_actual_estimated_cost,
                all_actual_estimated_cost,
            ),
            "actual_session_count": actual_sessions,
            "actual_coverage_pct": round(
                (actual_sessions / total_sessions * 100) if total_sessions else 0,
                1,
            ),
            "cache_savings_usd": _round_money(all_cache_savings),
        },
        "by_model": model_list,
        "top_sessions": sorted(top_sessions, key=lambda s: -s["billed_cost_usd"])[:10],
        "trend_summary": {
            "recent_7d_cost_usd": _round_money(recent_7d_cost),
            "previous_7d_cost_usd": _round_money(previous_7d_cost),
            "delta_usd": _round_money(delta),
            "delta_pct": _pct(delta, previous_7d_cost),
            "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
        },
        "daily_trend": [
            {
                "date": day,
                "cost": round(daily[day]["cost"], 2),
                "estimated_cost_usd": round(daily[day]["estimated_cost"], 2),
                "actual_cost_usd": round(daily[day]["actual_cost"], 2),
                "billed_cost_usd": round(daily[day]["cost"], 2),
                "cache_savings_usd": round(daily[day]["cache_savings"], 2),
                "tokens": daily[day]["tokens"],
                "sessions": daily[day]["sessions"],
            }
            for day in sorted_days
        ],
        "pricing_table": {k: {kk: vv for kk, vv in v.items()} for k, v in MODEL_PRICING.items()},
    }
