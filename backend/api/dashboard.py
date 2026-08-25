"""Consolidated dashboard endpoint — lean version for the overview narrative."""

from fastapi import APIRouter

from backend.collectors.collect import collect_all
from backend.collectors.cron import collect_cron
from backend.collectors.projects import collect_projects
from backend.collectors.health import collect_health
from backend.collectors.corrections import collect_corrections
from backend.collectors.gateway import collect_gateway_status
from backend.collectors.model_analytics import collect_model_analytics
from backend.collectors.providers import collect_providers
from backend.collectors.snapshot import load_snapshots
from .token_costs import get_token_costs
from .serialize import to_dict

try:
    router = APIRouter()
except TypeError:
    class _NoopRouter:
        def get(self, *_args, **_kwargs):
            return lambda fn: fn

    router = _NoopRouter()


def _money(value) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _top_model(model_analytics):
    models = getattr(model_analytics, "models", []) or []
    if not models:
        return None
    return max(models, key=lambda model: getattr(model, "total_tokens", 0))


def _diagnostic_actions(health) -> list[dict]:
    items = []
    for group in ("features", "readiness", "freshness", "database"):
        for item in getattr(health, group, []) or []:
            if getattr(item, "status", "") in {"broken", "warning"}:
                items.append({
                    "source": "health",
                    "label": getattr(item, "name", ""),
                    "severity": getattr(item, "status", "warning"),
                    "detail": getattr(item, "detail", ""),
                    "target": "health",
                })
    return items


def build_executive_summary(health, costs: dict, model_analytics, providers, gateway) -> dict:
    """Build compact dashboard signals from detailed tab data."""
    top_model = _top_model(model_analytics)
    top_session = (costs.get("top_sessions") or [{}])[0] if isinstance(costs, dict) else {}
    trend = costs.get("trend_summary") or {} if isinstance(costs, dict) else {}
    today = costs.get("today") or {} if isinstance(costs, dict) else {}
    provider_warnings = len(getattr(providers, "warnings", []) or []) + sum(
        len(getattr(provider, "warnings", []) or [])
        for provider in getattr(providers, "providers", []) or []
    )
    unavailable_tools = getattr(getattr(gateway, "managed_tools", None), "unavailable_count", 0) or 0
    actions = _diagnostic_actions(health)

    for warning in getattr(providers, "warnings", []) or []:
        actions.append({
            "source": "providers",
            "label": warning,
            "severity": "warning",
            "detail": "Provider configuration drift",
            "target": "providers",
        })
    for tool in getattr(getattr(gateway, "managed_tools", None), "tools", []) or []:
        if getattr(tool, "route", "") == "unavailable":
            actions.append({
                "source": "gateway",
                "label": getattr(tool, "label", getattr(tool, "key", "Gateway tool")),
                "severity": "warning",
                "detail": getattr(tool, "reason", ""),
                "target": "gateway",
            })

    severity_rank = {"broken": 0, "warning": 1, "ok": 2}
    actions = sorted(actions, key=lambda item: (severity_rank.get(item["severity"], 3), item["source"], item["label"]))[:8]

    return {
        "health": {
            "broken": getattr(health, "diagnostics_broken", 0),
            "warnings": getattr(health, "diagnostics_warnings", 0),
        },
        "spend": {
            "today_usd": _money(today.get("billed_cost_usd", today.get("estimated_cost_usd", 0))),
            "trend_delta_usd": _money(trend.get("delta_usd", 0)),
            "trend_delta_pct": trend.get("delta_pct"),
            "top_session": {
                "id": top_session.get("id", ""),
                "title": top_session.get("title", ""),
                "cost_usd": _money(top_session.get("billed_cost_usd", top_session.get("estimated_cost_usd", 0))),
            } if top_session else {},
        },
        "model": {
            "top_model": getattr(top_model, "model", "") if top_model else "",
            "top_provider": getattr(top_model, "provider", "") if top_model else "",
            "total_models": getattr(model_analytics, "total_models", 0),
            "total_sessions": getattr(model_analytics, "total_sessions", 0),
            "total_tokens": getattr(model_analytics, "total_tokens", 0),
        },
        "risks": {
            "provider_warnings": provider_warnings,
            "gateway_unavailable_tools": unavailable_tools,
            "gateway_state": getattr(gateway, "state", "unknown"),
        },
        "actions": actions,
    }


@router.get("/dashboard")
def get_dashboard():
    """Everything the overview narrative needs — trimmed to essentials."""

    state = collect_all()
    health = collect_health()
    corrections = collect_corrections()
    snapshots = load_snapshots()
    token_costs = get_token_costs()
    model_analytics = collect_model_analytics(days=7)
    providers = collect_providers()
    gateway = collect_gateway_status()

    # Trim state: only keep what the narrative sections need
    lean_state = {
        "config": to_dict(state.config),
        "memory": {
            "entries": to_dict(state.memory.entries),
            "total_chars": state.memory.total_chars,
            "max_chars": state.memory.max_chars,
            "capacity_pct": state.memory.capacity_pct,
            "entry_count": state.memory.entry_count,
            "count_by_category": state.memory.count_by_category(),
        },
        "user": {
            "entries": to_dict(state.user.entries),
            "total_chars": state.user.total_chars,
            "max_chars": state.user.max_chars,
            "capacity_pct": state.user.capacity_pct,
            "entry_count": state.user.entry_count,
        },
        "skills": {
            "total": state.skills.total,
            "custom_count": state.skills.custom_count,
            "category_counts": state.skills.category_counts(),
            "recently_modified": to_dict(state.skills.recently_modified(5)),
        },
        "sessions": {
            "total_sessions": state.sessions.total_sessions,
            "total_messages": state.sessions.total_messages,
            "total_tool_calls": state.sessions.total_tool_calls,
            "total_tokens": state.sessions.total_tokens,
            "by_source": state.sessions.by_source(),
            "tool_usage": dict(
                sorted(state.sessions.tool_usage.items(), key=lambda x: -x[1])[:12]
            ),
            "daily_stats": to_dict(state.sessions.daily_stats),
            "date_range": to_dict(state.sessions.date_range),
        },
        "timeline": to_dict(state.timeline),
    }

    # Cron: just jobs list
    cron = to_dict(collect_cron())

    # Projects: only active + dirty for the narrative
    projects_data = collect_projects()
    active_projects = [
        to_dict(p) for p in projects_data.projects
        if p.is_git and (p.activity_level == "active" or p.dirty_files > 0)
    ]
    projects = {
        "projects": active_projects,
        "total": projects_data.total,
        "git_repos": projects_data.git_repos,
        "active_count": projects_data.active_count,
        "dirty_count": projects_data.dirty_count,
        "projects_dir": projects_data.projects_dir,
    }

    return {
        "state": lean_state,
        "health": to_dict(health),
        "projects": projects,
        "cron": cron,
        "corrections": to_dict(corrections),
        "snapshots": snapshots,
        "executive_summary": build_executive_summary(
            health,
            token_costs if isinstance(token_costs, dict) else {},
            model_analytics,
            providers,
            gateway,
        ),
    }
