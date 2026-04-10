"""Token cost endpoint — calculates estimated USD costs per model."""

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from .profile_scope import resolve_profile_scope

router = APIRouter()

# ── Pricing per 1M tokens (USD) ──────────────────────────
# Source: https://www.anthropic.com/pricing (April 2026)
# Source: https://openai.com/api/pricing/ (April 2026)

MODEL_PRICING: dict[str, dict] = {
    # Anthropic
    "claude-opus-4-6": {
        "input": 15.00, "output": 75.00,
        "cache_read": 1.50, "cache_write": 18.75,
        "reasoning": 15.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.30, "cache_write": 3.75,
        "reasoning": 3.00,
    },
    "claude-haiku-3-5": {
        "input": 0.80, "output": 4.00,
        "cache_read": 0.08, "cache_write": 1.00,
        "reasoning": 0.80,
    },
    # OpenAI
    "gpt-4o": {
        "input": 2.50, "output": 10.00,
        "cache_read": 1.25, "cache_write": 2.50,
        "reasoning": 2.50,
    },
    "gpt-4o-mini": {
        "input": 0.15, "output": 0.60,
        "cache_read": 0.075, "cache_write": 0.15,
        "reasoning": 0.15,
    },
    "o1": {
        "input": 15.00, "output": 60.00,
        "cache_read": 7.50, "cache_write": 15.00,
        "reasoning": 15.00,
    },
    "o3-mini": {
        "input": 1.10, "output": 4.40,
        "cache_read": 0.55, "cache_write": 1.10,
        "reasoning": 1.10,
    },
    # DeepSeek
    "deepseek-v3": {
        "input": 0.27, "output": 1.10,
        "cache_read": 0.07, "cache_write": 0.27,
        "reasoning": 0.27,
    },
    "deepseek-r1": {
        "input": 0.55, "output": 2.19,
        "cache_read": 0.14, "cache_write": 0.55,
        "reasoning": 0.55,
    },
    # xAI
    "grok-3": {
        "input": 3.00, "output": 15.00,
        "cache_read": 0.75, "cache_write": 3.00,
        "reasoning": 3.00,
    },
    "grok-3-mini-fast": {
        "input": 0.30, "output": 0.50,
        "cache_read": 0.075, "cache_write": 0.30,
        "reasoning": 0.30,
    },
    # Google
    "gemini-2.5-pro": {
        "input": 1.25, "output": 10.00,
        "cache_read": 0.31, "cache_write": 4.50,
        "reasoning": 1.25,
    },
    # Local / free — zero cost
    "local": {
        "input": 0.0, "output": 0.0,
        "cache_read": 0.0, "cache_write": 0.0,
        "reasoning": 0.0,
    },
}

DEFAULT_PRICING = MODEL_PRICING["claude-opus-4-6"]


def _get_pricing(model: str | None) -> tuple[dict, str]:
    """Return (pricing_dict, matched_key) for a model."""
    if not model:
        return DEFAULT_PRICING, "default (claude-opus-4-6)"
    # Exact match
    if model in MODEL_PRICING:
        return MODEL_PRICING[model], model
    # Partial match (strip provider prefix)
    base = model.split("/")[-1] if "/" in model else model
    for key, pricing in MODEL_PRICING.items():
        if base.startswith(key):
            return pricing, key
    # Check if it's a local/inference model (zero cost)
    lower = model.lower()
    if any(kw in lower for kw in ("local", "localhost", "free", "9b", "7b", "13b", "4b", "3b")):
        return MODEL_PRICING["local"], "local (free)"
    return DEFAULT_PRICING, f"default ({model})"


def _calc_cost(tokens: dict, pricing: dict) -> float:
    return sum(
        (tokens.get(k, 0) / 1_000_000) * pricing.get(k, 0)
        for k in ("input", "output", "cache_read", "cache_write", "reasoning")
    )


@router.get("/token-costs")
async def get_token_costs(profile: str | None = None):
    """Token usage and estimated costs, broken down by model."""
    profile_name, hermes_dir = resolve_profile_scope(profile)
    db_path = str(Path(hermes_dir) / "state.db")

    if not Path(db_path).exists():
        return {"profile": profile_name, "error": "state.db not found"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    # Query all sessions with model column
    cur.execute("""
        SELECT id, source, started_at, model,
               message_count, tool_call_count,
               input_tokens, output_tokens,
               cache_read_tokens, cache_write_tokens,
               reasoning_tokens
        FROM sessions
        ORDER BY started_at ASC
    """)

    # Per-model aggregation
    by_model: dict[str, dict] = {}

    # Today aggregation
    today_data = {
        "session_count": 0, "message_count": 0,
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_tokens": 0, "cache_write_tokens": 0,
        "reasoning_tokens": 0, "cost": 0.0,
    }

    # All-time totals
    all_input = all_output = all_cache_r = all_cache_w = all_reasoning = 0
    all_messages = all_tool_calls = 0
    all_cost = 0.0
    total_sessions = 0

    # Daily trend
    daily: dict[str, dict] = {}

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
        cost = _calc_cost(tokens, pricing)

        # Per-model
        if model not in by_model:
            by_model[model] = {
                "model": model, "matched_pricing": matched,
                "session_count": 0, "message_count": 0,
                "input_tokens": 0, "output_tokens": 0,
                "cache_read_tokens": 0, "cache_write_tokens": 0,
                "reasoning_tokens": 0, "cost": 0.0,
            }
        m = by_model[model]
        m["session_count"] += 1
        m["message_count"] += row["message_count"] or 0
        m["input_tokens"] += tokens["input"]
        m["output_tokens"] += tokens["output"]
        m["cache_read_tokens"] += tokens["cache_read"]
        m["cache_write_tokens"] += tokens["cache_write"]
        m["reasoning_tokens"] += tokens["reasoning"]
        m["cost"] += cost

        # Today
        if is_today:
            today_data["session_count"] += 1
            today_data["message_count"] += row["message_count"] or 0
            today_data["input_tokens"] += tokens["input"]
            today_data["output_tokens"] += tokens["output"]
            today_data["cache_read_tokens"] += tokens["cache_read"]
            today_data["cache_write_tokens"] += tokens["cache_write"]
            today_data["reasoning_tokens"] += tokens["reasoning"]
            today_data["cost"] += cost

        # All-time
        total_sessions += 1
        all_messages += row["message_count"] or 0
        all_tool_calls += row["tool_call_count"] or 0
        all_input += tokens["input"]
        all_output += tokens["output"]
        all_cache_r += tokens["cache_read"]
        all_cache_w += tokens["cache_write"]
        all_reasoning += tokens["reasoning"]
        all_cost += cost

        # Daily
        if day not in daily:
            daily[day] = {"cost": 0.0, "tokens": 0, "sessions": 0}
        daily[day]["cost"] += cost
        daily[day]["tokens"] += tokens["input"] + tokens["output"]
        daily[day]["sessions"] += 1

    conn.close()

    # Sort models by cost descending
    model_list = sorted(by_model.values(), key=lambda m: -m["cost"])

    # Round costs
    for m in model_list:
        m["cost"] = round(m["cost"], 2)
    today_data["cost"] = round(today_data["cost"], 2)

    sorted_days = sorted(daily.keys())

    return {
        "profile": profile_name,
        "today": {
            "date": today,
            "session_count": today_data["session_count"],
            "message_count": today_data["message_count"],
            "input_tokens": today_data["input_tokens"],
            "output_tokens": today_data["output_tokens"],
            "cache_read_tokens": today_data["cache_read_tokens"],
            "cache_write_tokens": today_data["cache_write_tokens"],
            "reasoning_tokens": today_data["reasoning_tokens"],
            "total_tokens": today_data["input_tokens"] + today_data["output_tokens"],
            "estimated_cost_usd": today_data["cost"],
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
            "estimated_cost_usd": round(all_cost, 2),
        },
        "by_model": model_list,
        "daily_trend": [
            {
                "date": day,
                "cost": round(daily[day]["cost"], 2),
                "tokens": daily[day]["tokens"],
                "sessions": daily[day]["sessions"],
            }
            for day in sorted_days
        ],
        "pricing_table": {k: {kk: vv for kk, vv in v.items()} for k, v in MODEL_PRICING.items()},
    }
