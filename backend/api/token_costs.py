"""Token cost endpoint — tracked billing plus hypothetical API-equivalent replay.

Primary source of truth for what the user was actually charged is the Hermes
session DB itself:
- actual_cost_usd / estimated_cost_usd
- cost_status / cost_source
- billing_provider / billing_mode

Separately, for selected models with public provider pricing, this endpoint can
also compute a hypothetical "API-equivalent" spend from the recorded token
buckets. This is useful for subscription-included routes such as openai-codex:
actual billing stays "included", while operators can still see what the same
usage would have cost on the public API.

Only when older rows lack persisted cost metadata do we fall back to a small
legacy pricing table for tracked-cost best-effort estimates.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from backend.collectors.utils import default_hermes_dir

router = APIRouter()

# Legacy fallback pricing per 1M tokens (USD). Use only for older rows that do
# not already carry persisted billing metadata.
LEGACY_MODEL_PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-opus-4-6": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
        "reasoning": 15.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
        "reasoning": 3.00,
    },
    "claude-haiku-3-5": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write": 1.00,
        "reasoning": 0.80,
    },
    # OpenAI
    "gpt-4o": {
        "input": 2.50,
        "output": 10.00,
        "cache_read": 1.25,
        "cache_write": 2.50,
        "reasoning": 2.50,
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
        "cache_read": 0.075,
        "cache_write": 0.15,
        "reasoning": 0.15,
    },
    "o1": {
        "input": 15.00,
        "output": 60.00,
        "cache_read": 7.50,
        "cache_write": 15.00,
        "reasoning": 15.00,
    },
    "o3-mini": {
        "input": 1.10,
        "output": 4.40,
        "cache_read": 0.55,
        "cache_write": 1.10,
        "reasoning": 1.10,
    },
    # DeepSeek
    "deepseek-v3": {
        "input": 0.27,
        "output": 1.10,
        "cache_read": 0.07,
        "cache_write": 0.27,
        "reasoning": 0.27,
    },
    "deepseek-r1": {
        "input": 0.55,
        "output": 2.19,
        "cache_read": 0.14,
        "cache_write": 0.55,
        "reasoning": 0.55,
    },
    # xAI
    "grok-3": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.75,
        "cache_write": 3.00,
        "reasoning": 3.00,
    },
    "grok-3-mini-fast": {
        "input": 0.30,
        "output": 0.50,
        "cache_read": 0.075,
        "cache_write": 0.30,
        "reasoning": 0.30,
    },
    # Google
    "gemini-2.5-pro": {
        "input": 1.25,
        "output": 10.00,
        "cache_read": 0.31,
        "cache_write": 4.50,
        "reasoning": 1.25,
    },
    # Local / free
    "local": {
        "input": 0.0,
        "output": 0.0,
        "cache_read": 0.0,
        "cache_write": 0.0,
        "reasoning": 0.0,
    },
}

# Official public API pricing snapshots used for hypothetical API-equivalent
# replay. Values are per 1M tokens unless noted. These are intentionally small,
# curated snapshots for models we have a verified public price for and want to
# visualize in HUD without making live network requests on every page load.
OFFICIAL_API_EQUIVALENT_PRICING: dict[str, dict[str, object]] = {
    "gpt-5.4": {
        "source_label": "OpenAI API official pricing snapshot",
        "source_url": "https://developers.openai.com/api/docs/pricing",
        "pricing_version": "openai-api-pricing-2026-04-12",
        "range_note": "range reflects OpenAI Standard short-context vs long-context pricing",
        "variants": [
            {
                "key": "openai-standard-short",
                "label": "OpenAI Standard · short context",
                "input": 2.50,
                "cache_read": 0.25,
                "output": 15.00,
            },
            {
                "key": "openai-standard-long",
                "label": "OpenAI Standard · long context",
                "input": 5.00,
                "cache_read": 0.50,
                "output": 22.50,
            },
        ],
    },
    "gpt-5.3-codex": {
        "source_label": "OpenAI API official pricing snapshot",
        "source_url": "https://developers.openai.com/api/docs/pricing",
        "pricing_version": "openai-api-pricing-2026-04-12",
        "range_note": "range reflects OpenAI Standard vs Priority service tier",
        "variants": [
            {
                "key": "openai-standard",
                "label": "OpenAI Standard",
                "input": 1.75,
                "cache_read": 0.175,
                "output": 14.00,
            },
            {
                "key": "openai-priority",
                "label": "OpenAI Priority",
                "input": 3.50,
                "cache_read": 0.35,
                "output": 28.00,
            },
        ],
    },
}

BASE_SESSION_COLUMNS = [
    "id",
    "source",
    "started_at",
    "model",
    "message_count",
    "tool_call_count",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
]

OPTIONAL_COST_COLUMNS = [
    "billing_provider",
    "billing_base_url",
    "billing_mode",
    "estimated_cost_usd",
    "actual_cost_usd",
    "cost_status",
    "cost_source",
    "pricing_version",
]


def _coerce_int(value) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0



def _coerce_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None



def _get_pricing(model: str | None) -> tuple[dict[str, float] | None, str | None, str, bool]:
    """Legacy fallback pricing lookup.

    Returns (pricing_dict, pricing_key, label, priced_bool).
    """
    if not model:
        return None, None, "unavailable", False
    if model in LEGACY_MODEL_PRICING:
        return LEGACY_MODEL_PRICING[model], model, model, True

    base = model.split("/")[-1] if "/" in model else model
    for key, pricing in LEGACY_MODEL_PRICING.items():
        if base.startswith(key):
            return pricing, key, key, True

    lower = model.lower()
    if any(kw in lower for kw in ("local", "localhost", "free", "9b", "7b", "13b", "4b", "3b")):
        return LEGACY_MODEL_PRICING["local"], "local", "local (free)", True

    return None, None, f"unavailable ({model})", False



def _calc_cost(tokens: dict[str, int], pricing: dict[str, float] | None) -> float:
    if pricing is None:
        return 0.0
    return sum(
        (tokens.get(bucket, 0) / 1_000_000) * pricing.get(bucket, 0.0)
        for bucket in ("input", "output", "cache_read", "cache_write", "reasoning")
    )



def _get_api_equivalent_reference(model: str | None) -> dict[str, object] | None:
    if not model:
        return None

    candidates = [model]
    base = model.split("/")[-1] if "/" in model else model
    if base not in candidates:
        candidates.append(base)

    for candidate in candidates:
        if candidate in OFFICIAL_API_EQUIVALENT_PRICING:
            return OFFICIAL_API_EQUIVALENT_PRICING[candidate]

    for key in sorted(OFFICIAL_API_EQUIVALENT_PRICING.keys(), key=len, reverse=True):
        if base.startswith(key):
            return OFFICIAL_API_EQUIVALENT_PRICING[key]

    return None



def _estimate_api_equivalent(model: str | None, tokens: dict[str, int]) -> dict:
    spec = _get_api_equivalent_reference(model)
    if not spec:
        return {
            "available": False,
            "lower_usd": 0.0,
            "upper_usd": 0.0,
            "label": None,
            "range_note": None,
            "source_url": None,
            "pricing_version": None,
        }

    variants = spec.get("variants") or []
    if not variants:
        return {
            "available": False,
            "lower_usd": 0.0,
            "upper_usd": 0.0,
            "label": None,
            "range_note": None,
            "source_url": None,
            "pricing_version": None,
        }

    amounts = [_calc_cost(tokens, variant) for variant in variants]
    lower = min(amounts)
    upper = max(amounts)

    return {
        "available": True,
        "lower_usd": lower,
        "upper_usd": upper,
        "label": spec.get("source_label"),
        "range_note": spec.get("range_note"),
        "source_url": spec.get("source_url"),
        "pricing_version": spec.get("pricing_version"),
    }



def _get_session_columns(cur: sqlite3.Cursor) -> set[str]:
    cur.execute("PRAGMA table_info(sessions)")
    return {row[1] for row in cur.fetchall()}



def _select_expression(column: str, available_columns: set[str]) -> str:
    if column in available_columns:
        return column
    return f"NULL AS {column}"



def _build_session_query(available_columns: set[str]) -> str:
    columns = [
        _select_expression(column, available_columns)
        for column in BASE_SESSION_COLUMNS + OPTIONAL_COST_COLUMNS
    ]
    return f"SELECT {', '.join(columns)} FROM sessions ORDER BY started_at ASC"



def _empty_bucket(*, date: str | None = None) -> dict:
    return {
        "date": date,
        "session_count": 0,
        "message_count": 0,
        "tool_call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "actual_cost_usd": 0.0,
        "estimated_cost_usd": 0.0,
        "derived_cost_usd": 0.0,
        "tracked_cost_usd": 0.0,
        "billable_session_count": 0,
        "actual_session_count": 0,
        "estimated_session_count": 0,
        "derived_session_count": 0,
        "included_session_count": 0,
        "unknown_session_count": 0,
        "has_fallback_estimates": False,
        "cost_is_partial": False,
        "cost_badge": "n/a",
        "cost_mode": "unknown",
        "cost_caption": "no tracked billing data",
        "total_tokens": 0,
        "api_equivalent_known_session_count": 0,
        "api_equivalent_unknown_session_count": 0,
        "api_equivalent_lower_usd": 0.0,
        "api_equivalent_upper_usd": 0.0,
        "api_equivalent_available": False,
        "api_equivalent_is_partial": False,
        "api_equivalent_badge": "n/a",
        "api_equivalent_caption": "no official API-equivalent pricing snapshot",
        "api_equivalent_label": None,
        "api_equivalent_range_note": None,
        "api_equivalent_source_url": None,
        "api_equivalent_pricing_version": None,
    }



def _bucket_status_parts(bucket: dict) -> list[str]:
    parts: list[str] = []
    if bucket["actual_session_count"]:
        parts.append(f"{bucket['actual_session_count']} actual")
    if bucket["estimated_session_count"]:
        parts.append(f"{bucket['estimated_session_count']} estimated")
    if bucket["derived_session_count"]:
        parts.append(f"{bucket['derived_session_count']} fallback")
    if bucket["included_session_count"]:
        parts.append(f"{bucket['included_session_count']} included")
    if bucket["unknown_session_count"]:
        parts.append(f"{bucket['unknown_session_count']} unknown")
    return parts



def _finalize_bucket(bucket: dict) -> dict:
    bucket["total_tokens"] = bucket["input_tokens"] + bucket["output_tokens"]

    for key in (
        "actual_cost_usd",
        "estimated_cost_usd",
        "derived_cost_usd",
        "tracked_cost_usd",
        "api_equivalent_lower_usd",
        "api_equivalent_upper_usd",
    ):
        bucket[key] = round(bucket[key], 2)

    parts = _bucket_status_parts(bucket)
    has_billable = bucket["billable_session_count"] > 0
    has_estimated = bucket["estimated_session_count"] > 0 or bucket["derived_session_count"] > 0
    has_included = bucket["included_session_count"] > 0
    has_unknown = bucket["unknown_session_count"] > 0

    if bucket["session_count"] == 0:
        bucket["cost_mode"] = "empty"
        bucket["cost_badge"] = "n/a"
        bucket["cost_caption"] = "no sessions"
    elif has_billable:
        bucket["cost_mode"] = "mixed" if (has_included or has_unknown) else ("estimated" if has_estimated else "actual")
        prefix = "~" if has_estimated else ""
        bucket["cost_badge"] = f"{prefix}${bucket['tracked_cost_usd']:.2f}"
        bucket["cost_caption"] = " · ".join(parts) if parts else "tracked cost"
        if has_unknown:
            bucket["cost_is_partial"] = True
    elif has_included and not has_unknown:
        bucket["cost_mode"] = "included"
        bucket["cost_badge"] = "included"
        bucket["cost_caption"] = "subscription included · no per-session USD charge"
    elif has_included and has_unknown:
        bucket["cost_mode"] = "mixed"
        bucket["cost_badge"] = "included"
        bucket["cost_caption"] = " · ".join(parts) if parts else "included + unknown"
        bucket["cost_is_partial"] = True
    else:
        bucket["cost_mode"] = "unknown"
        bucket["cost_badge"] = "n/a"
        bucket["cost_caption"] = " · ".join(parts) if parts else "pricing unavailable"
        bucket["cost_is_partial"] = True

    if bucket["api_equivalent_known_session_count"] > 0:
        bucket["api_equivalent_available"] = True
        bucket["api_equivalent_is_partial"] = bucket["api_equivalent_unknown_session_count"] > 0
        lower = bucket["api_equivalent_lower_usd"]
        upper = bucket["api_equivalent_upper_usd"]
        if abs(upper - lower) < 0.005:
            bucket["api_equivalent_badge"] = f"${lower:.2f}"
        else:
            bucket["api_equivalent_badge"] = f"${lower:.2f}–${upper:.2f}"

        caption_parts = ["aggregate token replay using official API pricing snapshot"]
        if bucket.get("api_equivalent_range_note"):
            caption_parts.append(bucket["api_equivalent_range_note"])
        caption_parts.append("exact per-request context split/tool-call mix is not stored")
        if bucket["api_equivalent_is_partial"]:
            caption_parts.append("models without official snapshot omitted")
        bucket["api_equivalent_caption"] = " · ".join(caption_parts)
    elif bucket["session_count"] == 0:
        bucket["api_equivalent_available"] = False
        bucket["api_equivalent_badge"] = "n/a"
        bucket["api_equivalent_caption"] = "no sessions"
    else:
        bucket["api_equivalent_available"] = False
        bucket["api_equivalent_is_partial"] = bucket["api_equivalent_unknown_session_count"] > 0
        bucket["api_equivalent_badge"] = "n/a"
        bucket["api_equivalent_caption"] = "no official API-equivalent pricing snapshot"

    return bucket



def _classify_session_cost(row: sqlite3.Row) -> dict:
    model = row["model"] or "unknown"
    provider = (row["billing_provider"] or "").strip().lower()
    billing_mode = (row["billing_mode"] or "").strip().lower()
    cost_status = (row["cost_status"] or "").strip().lower()
    cost_source = (row["cost_source"] or "").strip().lower() or "none"
    actual_cost = _coerce_float(row["actual_cost_usd"])
    estimated_cost = _coerce_float(row["estimated_cost_usd"])

    if actual_cost is not None:
        return {
            "kind": "actual",
            "amount_usd": actual_cost,
            "billing_label": cost_source if cost_source != "none" else "stored actual",
            "pricing_key": None,
            "derived": False,
        }

    if cost_status == "included" or billing_mode == "subscription_included" or provider == "openai-codex":
        return {
            "kind": "included",
            "amount_usd": 0.0,
            "billing_label": "subscription included",
            "pricing_key": None,
            "derived": False,
        }

    if estimated_cost is not None and (estimated_cost > 0 or cost_status in {"estimated", "actual"}):
        return {
            "kind": "estimated",
            "amount_usd": estimated_cost,
            "billing_label": cost_source if cost_source != "none" else "stored estimate",
            "pricing_key": None,
            "derived": False,
        }

    tokens = {
        "input": _coerce_int(row["input_tokens"]),
        "output": _coerce_int(row["output_tokens"]),
        "cache_read": _coerce_int(row["cache_read_tokens"]),
        "cache_write": _coerce_int(row["cache_write_tokens"]),
        "reasoning": _coerce_int(row["reasoning_tokens"]),
    }
    pricing, pricing_key, pricing_label, priced = _get_pricing(model)
    if priced:
        return {
            "kind": "estimated",
            "amount_usd": _calc_cost(tokens, pricing),
            "billing_label": f"fallback estimate · {pricing_label}",
            "pricing_key": pricing_key,
            "derived": True,
        }

    return {
        "kind": "unknown",
        "amount_usd": None,
        "billing_label": "pricing unavailable",
        "pricing_key": None,
        "derived": False,
    }



def _apply_row(bucket: dict, row: sqlite3.Row, cost_info: dict, api_equivalent: dict) -> None:
    bucket["session_count"] += 1
    bucket["message_count"] += _coerce_int(row["message_count"])
    bucket["tool_call_count"] += _coerce_int(row["tool_call_count"])
    bucket["input_tokens"] += _coerce_int(row["input_tokens"])
    bucket["output_tokens"] += _coerce_int(row["output_tokens"])
    bucket["cache_read_tokens"] += _coerce_int(row["cache_read_tokens"])
    bucket["cache_write_tokens"] += _coerce_int(row["cache_write_tokens"])
    bucket["reasoning_tokens"] += _coerce_int(row["reasoning_tokens"])

    if api_equivalent.get("available"):
        bucket["api_equivalent_known_session_count"] += 1
        bucket["api_equivalent_lower_usd"] += api_equivalent.get("lower_usd") or 0.0
        bucket["api_equivalent_upper_usd"] += api_equivalent.get("upper_usd") or 0.0
        if not bucket.get("api_equivalent_label") and api_equivalent.get("label"):
            bucket["api_equivalent_label"] = api_equivalent["label"]
        if not bucket.get("api_equivalent_range_note") and api_equivalent.get("range_note"):
            bucket["api_equivalent_range_note"] = api_equivalent["range_note"]
        if not bucket.get("api_equivalent_source_url") and api_equivalent.get("source_url"):
            bucket["api_equivalent_source_url"] = api_equivalent["source_url"]
        if not bucket.get("api_equivalent_pricing_version") and api_equivalent.get("pricing_version"):
            bucket["api_equivalent_pricing_version"] = api_equivalent["pricing_version"]
    else:
        bucket["api_equivalent_unknown_session_count"] += 1

    kind = cost_info["kind"]
    amount = cost_info["amount_usd"] or 0.0

    if kind == "actual":
        bucket["actual_session_count"] += 1
        bucket["actual_cost_usd"] += amount
        bucket["tracked_cost_usd"] += amount
        bucket["billable_session_count"] += 1
        return

    if kind == "estimated":
        if cost_info.get("derived"):
            bucket["derived_session_count"] += 1
            bucket["derived_cost_usd"] += amount
            bucket["has_fallback_estimates"] = True
        else:
            bucket["estimated_session_count"] += 1
            bucket["estimated_cost_usd"] += amount
        bucket["tracked_cost_usd"] += amount
        bucket["billable_session_count"] += 1
        return

    if kind == "included":
        bucket["included_session_count"] += 1
        return

    bucket["unknown_session_count"] += 1
    bucket["cost_is_partial"] = True


@router.get("/token-costs")
async def get_token_costs():
    """Token usage, tracked billing, and API-equivalent replay by model."""
    hermes_dir = default_hermes_dir()
    db_path = Path(hermes_dir) / "state.db"

    if not db_path.exists():
        return {"error": "state.db not found"}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        available_columns = _get_session_columns(cur)
        if not available_columns:
            return {"error": "sessions table not found"}

        query = _build_session_query(available_columns)
        cur.execute(query)
        rows = cur.fetchall()
    finally:
        conn.close()

    today = datetime.now().strftime("%Y-%m-%d")
    today_bucket = _empty_bucket(date=today)
    all_time_bucket = _empty_bucket()
    by_model: dict[str, dict] = {}
    daily: dict[str, dict] = {}

    for row in rows:
        model = row["model"] or "unknown"
        started_ts = row["started_at"]
        started = datetime.fromtimestamp(started_ts) if started_ts else None
        day = started.strftime("%Y-%m-%d") if started else "unknown"
        is_today = day == today

        cost_info = _classify_session_cost(row)
        tokens = {
            "input": _coerce_int(row["input_tokens"]),
            "output": _coerce_int(row["output_tokens"]),
            "cache_read": _coerce_int(row["cache_read_tokens"]),
            "cache_write": _coerce_int(row["cache_write_tokens"]),
            "reasoning": _coerce_int(row["reasoning_tokens"]),
        }
        api_equivalent = _estimate_api_equivalent(model, tokens)

        if model not in by_model:
            by_model[model] = _empty_bucket()
            by_model[model]["model"] = model
            by_model[model]["billing_label"] = cost_info["billing_label"]
            by_model[model]["pricing_key"] = cost_info["pricing_key"]
        model_bucket = by_model[model]
        if not model_bucket.get("billing_label") or model_bucket.get("billing_label") == "pricing unavailable":
            model_bucket["billing_label"] = cost_info["billing_label"]
        if not model_bucket.get("pricing_key") and cost_info.get("pricing_key"):
            model_bucket["pricing_key"] = cost_info["pricing_key"]

        _apply_row(model_bucket, row, cost_info, api_equivalent)
        _apply_row(all_time_bucket, row, cost_info, api_equivalent)

        if is_today:
            _apply_row(today_bucket, row, cost_info, api_equivalent)

        if day not in daily:
            daily[day] = _empty_bucket(date=day)
        _apply_row(daily[day], row, cost_info, api_equivalent)

    today_bucket = _finalize_bucket(today_bucket)
    all_time_bucket = _finalize_bucket(all_time_bucket)

    model_list = []
    for model_bucket in by_model.values():
        finalized = _finalize_bucket(model_bucket)
        finalized["cost"] = finalized["tracked_cost_usd"]
        finalized["priced"] = finalized["cost_mode"] != "unknown"
        finalized["matched_pricing"] = finalized.get("billing_label") or "pricing unavailable"
        model_list.append(finalized)

    model_list.sort(
        key=lambda item: (
            -item["tracked_cost_usd"],
            -item["api_equivalent_lower_usd"],
            -item["total_tokens"],
            item["model"],
        )
    )

    daily_trend = []
    for day in sorted(daily.keys()):
        finalized = _finalize_bucket(daily[day])
        daily_trend.append(
            {
                "date": day,
                "cost": finalized["tracked_cost_usd"],
                "cost_badge": finalized["cost_badge"],
                "cost_mode": finalized["cost_mode"],
                "tokens": finalized["total_tokens"],
                "sessions": finalized["session_count"],
                "included_session_count": finalized["included_session_count"],
                "unknown_session_count": finalized["unknown_session_count"],
                "api_equivalent_available": finalized["api_equivalent_available"],
                "api_equivalent_lower_usd": finalized["api_equivalent_lower_usd"],
                "api_equivalent_upper_usd": finalized["api_equivalent_upper_usd"],
                "api_equivalent_badge": finalized["api_equivalent_badge"],
            }
        )

    today_bucket["estimated_cost_usd"] = today_bucket["tracked_cost_usd"]
    all_time_bucket["estimated_cost_usd"] = all_time_bucket["tracked_cost_usd"]

    cost_summary = {
        "cost_is_partial": all_time_bucket["cost_is_partial"],
        "has_billable_sessions": all_time_bucket["billable_session_count"] > 0,
        "has_included_sessions": all_time_bucket["included_session_count"] > 0,
        "has_unknown_sessions": all_time_bucket["unknown_session_count"] > 0,
        "has_fallback_estimates": all_time_bucket["has_fallback_estimates"],
        "all_sessions_included": all_time_bucket["included_session_count"] == all_time_bucket["session_count"] and all_time_bucket["session_count"] > 0,
        "all_sessions_unknown": all_time_bucket["unknown_session_count"] == all_time_bucket["session_count"] and all_time_bucket["session_count"] > 0,
        "api_equivalent_available": all_time_bucket["api_equivalent_available"],
        "api_equivalent_is_partial": all_time_bucket["api_equivalent_is_partial"],
        "all_sessions_have_api_equivalent": all_time_bucket["api_equivalent_known_session_count"] == all_time_bucket["session_count"] and all_time_bucket["session_count"] > 0,
    }

    return {
        "today": today_bucket,
        "all_time": all_time_bucket,
        "by_model": model_list,
        "cost_is_partial": cost_summary["cost_is_partial"],
        "cost_summary": cost_summary,
        "daily_trend": daily_trend,
        "legacy_pricing_table": {
            key: {bucket: value for bucket, value in pricing.items()}
            for key, pricing in LEGACY_MODEL_PRICING.items()
        },
        "api_equivalent_pricing_table": OFFICIAL_API_EQUIVALENT_PRICING,
    }
