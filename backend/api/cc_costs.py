"""Claude Code cost endpoint — reads session data from ~/.claude/projects/."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from backend.api.token_costs import MODEL_PRICING, _FREE, _SORTED_KEYS, _SMALL_MODEL_RE

try:
    router = APIRouter()
except TypeError:
    class _NoopRouter:
        def get(self, *_args, **_kwargs):
            return lambda fn: fn
    router = _NoopRouter()

CLAUDE_DIR = Path.home() / ".claude" / "projects"


def _get_pricing(model: str | None) -> tuple[dict, str]:
    """Return (pricing_dict, matched_key) for a model."""
    if not model:
        return _FREE, "unpriced (unknown)"
    if model in MODEL_PRICING:
        return MODEL_PRICING[model], model
    base = model.split("/")[-1] if "/" in model else model
    for key in _SORTED_KEYS:
        if base.startswith(key):
            return MODEL_PRICING[key], key
    lower = model.lower()
    if any(kw in lower for kw in ("local", "localhost", ":free", "gemma", "nemotron", "mimo-free")):
        return _FREE, "local (free)"
    if _SMALL_MODEL_RE.search(lower):
        return _FREE, "local (free)"
    return _FREE, f"unpriced ({model})"


def _calc_cost(tokens: dict, pricing: dict) -> float:
    return sum(
        (tokens.get(k, 0) / 1_000_000) * pricing.get(k, 0)
        for k in ("input", "output", "cache_read", "cache_write")
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
        "session_count": 0, "message_count": 0, "tool_call_count": 0,
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_tokens": 0, "cache_write_tokens": 0,
        "cost": 0.0,
        "estimated_cost": 0.0, "cache_savings": 0.0,
    }


def _add_usage(bucket: dict, session_messages: int, tool_calls: int, tokens: dict, estimated: float, savings: float) -> None:
    bucket["session_count"] += 1
    bucket["message_count"] += session_messages
    bucket["tool_call_count"] += tool_calls
    bucket["input_tokens"] += tokens["input"]
    bucket["output_tokens"] += tokens["output"]
    bucket["cache_read_tokens"] += tokens["cache_read"]
    bucket["cache_write_tokens"] += tokens["cache_write"]
    bucket["cost"] += estimated
    bucket["estimated_cost"] += estimated
    bucket["cache_savings"] += savings


def _finalize_bucket(bucket: dict) -> dict:
    estimated = bucket["estimated_cost"]
    total_tokens = bucket["input_tokens"] + bucket["output_tokens"]
    return {
        **bucket,
        "total_tokens": total_tokens,
        "cost": _round_money(bucket["cost"]),
        "estimated_cost_usd": _round_money(estimated),
        "billed_cost_usd": _round_money(bucket["cost"]),
        "cache_savings_usd": _round_money(bucket["cache_savings"]),
    }


def _parse_sessions() -> dict | None:
    """Parse all Claude Code session JSONL files and aggregate token usage + costs."""
    if not CLAUDE_DIR.exists():
        return None

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    recent_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)

    by_model: dict[str, dict] = {}
    by_project: dict[str, dict] = {}
    daily: dict[str, dict] = {}
    top_sessions: list[dict] = []

    today_data = _new_bucket()
    all_bucket = _new_bucket()
    recent_7d_cost = 0.0
    previous_7d_cost = 0.0

    for project_dir in CLAUDE_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        raw_name = project_dir.name
        project_name = raw_name.lstrip("-").replace("-", "/")
        parts = project_name.split("/")
        if len(parts) >= 2:
            project_name = "/".join(parts[-2:])
        elif len(parts) == 1:
            project_name = parts[0]

        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            # Per-model tracking within this session file
            file_model_data: dict[str, dict] = {}
            file_total_messages = 0
            file_total_tool_calls = 0
            file_total_input = file_total_output = 0
            file_total_cache_r = file_total_cache_w = 0
            session_day = None
            session_timestamp = None

            try:
                with open(jsonl_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if entry.get("type") != "assistant":
                            continue

                        msg = entry.get("message", {})
                        usage = msg.get("usage", {})
                        if not usage:
                            continue

                        inp = usage.get("input_tokens", 0) or 0
                        out = usage.get("output_tokens", 0) or 0
                        cache_r = usage.get("cache_read_input_tokens", 0) or 0
                        cache_w = usage.get("cache_creation_input_tokens", 0) or 0

                        if inp == 0 and out == 0 and cache_r == 0 and cache_w == 0:
                            continue

                        model = msg.get("model", "unknown") or "unknown"

                        # Count tool_use blocks
                        tool_calls = 0
                        content = msg.get("content", [])
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                tool_calls += 1

                        # Track per-model within this file
                        if model not in file_model_data:
                            file_model_data[model] = {
                                "messages": 0, "tool_calls": 0,
                                "input": 0, "output": 0,
                                "cache_read": 0, "cache_write": 0,
                            }
                        md = file_model_data[model]
                        md["messages"] += 1
                        md["tool_calls"] += tool_calls
                        md["input"] += inp
                        md["output"] += out
                        md["cache_read"] += cache_r
                        md["cache_write"] += cache_w

                        file_total_messages += 1
                        file_total_tool_calls += tool_calls
                        file_total_input += inp
                        file_total_output += out
                        file_total_cache_r += cache_r
                        file_total_cache_w += cache_w

                        ts = entry.get("timestamp")
                        if ts:
                            try:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                session_day = dt.strftime("%Y-%m-%d")
                                session_timestamp = dt.replace(tzinfo=None)
                            except Exception:
                                pass
            except Exception:
                continue

            if file_total_messages == 0:
                continue

            is_today = session_day == today
            day = session_day or "unknown"
            session_primary_model = list(file_model_data.keys())[-1] if file_model_data else "unknown"

            # Aggregate per-model from this file
            for model, md in file_model_data.items():
                tokens = {
                    "input": md["input"],
                    "output": md["output"],
                    "cache_read": md["cache_read"],
                    "cache_write": md["cache_write"],
                }
                pricing, matched = _get_pricing(model)
                estimated = _calc_cost(tokens, pricing)
                savings = _cache_savings(tokens, pricing)

                # Per-model
                if model not in by_model:
                    by_model[model] = {
                        "model": model, "matched_pricing": matched,
                        **_new_bucket(),
                    }
                _add_usage(by_model[model], md["messages"], md["tool_calls"], tokens, estimated, savings)

                # Today
                if is_today:
                    _add_usage(today_data, md["messages"], md["tool_calls"], tokens, estimated, savings)

                # All-time
                _add_usage(all_bucket, md["messages"], md["tool_calls"], tokens, estimated, savings)

            # Per-project (aggregate all models in this file under the project)
            file_tokens = {
                "input": file_total_input,
                "output": file_total_output,
                "cache_read": file_total_cache_r,
                "cache_write": file_total_cache_w,
            }
            file_pricing, file_matched = _get_pricing(session_primary_model)
            file_estimated = _calc_cost(file_tokens, file_pricing)
            file_savings = _cache_savings(file_tokens, file_pricing)

            if project_name not in by_project:
                by_project[project_name] = {
                    "project": project_name, "matched_pricing": file_matched,
                    **_new_bucket(),
                }
            _add_usage(by_project[project_name], file_total_messages, file_total_tool_calls, file_tokens, file_estimated, file_savings)

            # Daily
            if day not in daily:
                daily[day] = {"cost": 0.0, "estimated_cost": 0.0, "tokens": 0, "sessions": 0, "cache_savings": 0.0}
            daily[day]["cost"] += file_estimated
            daily[day]["estimated_cost"] += file_estimated
            daily[day]["tokens"] += file_total_input + file_total_output
            daily[day]["sessions"] += 1
            daily[day]["cache_savings"] += file_savings

            if session_timestamp:
                if session_timestamp >= recent_start:
                    recent_7d_cost += file_estimated
                elif session_timestamp >= previous_start:
                    previous_7d_cost += file_estimated

            # Build model string for display
            model_names = list(file_model_data.keys())
            display_model = model_names[0] if len(model_names) == 1 else f"{len(model_names)} models"

            top_sessions.append({
                "id": session_id,
                "project": project_name,
                "date": day or "unknown",
                "model": display_model,
                "matched_pricing": file_matched,
                "message_count": file_total_messages,
                "tool_call_count": file_total_tool_calls,
                "input_tokens": file_total_input,
                "output_tokens": file_total_output,
                "cache_read_tokens": file_total_cache_r,
                "cache_write_tokens": file_total_cache_w,
                "total_tokens": file_total_input + file_total_output,
                "estimated_cost_usd": _round_money(file_estimated),
                "billed_cost_usd": _round_money(file_estimated),
                "cache_savings_usd": _round_money(file_savings),
            })

    model_list = sorted(by_model.values(), key=lambda m: -m["cost"])
    model_list = [_finalize_bucket(m) for m in model_list]
    project_list = sorted(by_project.values(), key=lambda p: -p["cost"])
    project_list = [_finalize_bucket(p) for p in project_list]
    today_final = _finalize_bucket(today_data)
    all_final = _finalize_bucket(all_bucket)

    sorted_days = sorted(daily.keys())
    delta = recent_7d_cost - previous_7d_cost

    return {
        "today": {
            "date": today,
            **today_final,
        },
        "all_time": {
            **all_final,
        },
        "by_model": model_list,
        "by_project": project_list,
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
                "billed_cost_usd": round(daily[day]["cost"], 2),
                "cache_savings_usd": round(daily[day]["cache_savings"], 2),
                "tokens": daily[day]["tokens"],
                "sessions": daily[day]["sessions"],
            }
            for day in sorted_days
        ],
        "pricing_table": {k: {kk: vv for kk, vv in v.items()} for k, v in MODEL_PRICING.items()},
    }


@router.get("/cc-costs")
async def get_cc_costs():
    """Claude Code token usage and estimated costs."""
    data = _parse_sessions()
    if data is None:
        return {"error": "~/.claude/projects not found"}
    return data
