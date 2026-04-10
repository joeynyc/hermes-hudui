"""Consolidated dashboard endpoint — lean version for the overview narrative."""

from fastapi import APIRouter

from backend.collectors.collect import collect_all
from backend.collectors.cron import collect_cron
from backend.collectors.projects import collect_projects
from backend.collectors.health import collect_health
from backend.collectors.corrections import collect_corrections
from backend.collectors.snapshot import load_snapshots
from .serialize import to_dict
from .profile_scope import resolve_profile_scope

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(profile: str | None = None):
    """Everything the overview narrative needs — trimmed to essentials."""
    profile_name, hermes_dir = resolve_profile_scope(profile)

    state = collect_all(hermes_dir)
    health = collect_health()
    corrections = collect_corrections(hermes_dir)
    snapshots = load_snapshots(hermes_dir)

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
    cron = to_dict(collect_cron(hermes_dir))

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
        "profile": profile_name,
        "state": lean_state,
        "health": to_dict(health),
        "projects": projects,
        "cron": cron,
        "corrections": to_dict(corrections),
        "snapshots": snapshots,
    }
