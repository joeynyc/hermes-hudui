"""Collect all Hermes HUD data into a single state object."""

from __future__ import annotations


from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from .models import HUDState
from .memory import collect_memory
from .skills import collect_skills
from .sessions import collect_sessions
from .config import collect_config
from .timeline import build_timeline


def collect_all(hermes_dir: str | None = None) -> HUDState:
    """Collect all data sources into a unified HUD state."""
    # Config must run first so memory limits are known before parsing memory files
    config = collect_config(hermes_dir)

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_mem = pool.submit(
            collect_memory, hermes_dir,
            config.memory_char_limit, config.user_char_limit,
        )
        f_skills = pool.submit(
            collect_skills, hermes_dir, config.external_skill_dirs,
        )
        f_sessions = pool.submit(collect_sessions, hermes_dir)

    memory, user = f_mem.result()
    skills = f_skills.result()
    sessions = f_sessions.result()

    state = HUDState(
        memory=memory,
        user=user,
        skills=skills,
        sessions=sessions,
        config=config,
        collected_at=datetime.now(),
    )

    state.timeline = build_timeline(state)

    return state


def print_summary(state: HUDState):
    """Quick text dump for testing."""
    print(f"=== Hermes HUD State (collected {state.collected_at:%Y-%m-%d %H:%M:%S}) ===\n")

    print(f"◆ Config: {state.config.provider}/{state.config.model} | backend={state.config.backend}")
    print(f"  toolsets: {', '.join(state.config.toolsets)}")
    print()

    print(f"◆ Memory: {state.memory.entry_count} entries, {state.memory.total_chars}/{state.memory.max_chars} chars ({state.memory.capacity_pct:.0f}%)")
    cats = state.memory.count_by_category()
    print(f"  categories: {cats}")
    print()

    print(f"◆ User Profile: {state.user.entry_count} entries, {state.user.total_chars}/{state.user.max_chars} chars ({state.user.capacity_pct:.0f}%)")
    cats = state.user.count_by_category()
    print(f"  categories: {cats}")
    print()

    print(f"◆ Skills: {state.skills.total} total ({state.skills.custom_count} custom)")
    cat_counts = state.skills.category_counts()
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"  recently modified:")
    for s in state.skills.recently_modified(5):
        print(f"    {s.modified_at:%Y-%m-%d %H:%M} | {s.name} ({s.category})")
    print()

    print(f"◆ Sessions: {state.sessions.total_sessions} total, {state.sessions.total_messages} messages, {state.sessions.total_tool_calls} tool calls")
    date_range = state.sessions.date_range
    if date_range[0]:
        print(f"  date range: {date_range[0]:%Y-%m-%d} → {date_range[1]:%Y-%m-%d}")
    sources = state.sessions.by_source()
    print(f"  platforms: {sources}")
    print(f"  daily activity:")
    for ds in state.sessions.daily_stats:
        bar = "█" * min(ds.messages // 5, 40)
        print(f"    {ds.date} | {bar} {ds.messages} msgs")
    print()

    if state.sessions.tool_usage:
        print(f"◆ Top Tools:")
        for tool, count in sorted(state.sessions.tool_usage.items(), key=lambda x: -x[1])[:10]:
            print(f"    {tool}: {count}")
        print()

    print(f"◆ Timeline: {len(state.timeline)} events")
    # Show milestones and recent events
    milestones = [e for e in state.timeline if e.event_type == "milestone"]
    for m in milestones:
        print(f"  {m.icon} {m.timestamp:%Y-%m-%d} {m.title}: {m.detail}")


if __name__ == "__main__":
    state = collect_all()
    print_summary(state)
