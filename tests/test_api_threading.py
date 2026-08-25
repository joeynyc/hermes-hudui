import inspect

from backend.api import (
    agents,
    corrections,
    cron,
    dashboard,
    gateway,
    health,
    memory,
    model_info,
    patterns,
    plugins,
    profiles,
    projects,
    providers,
    sessions,
    skills,
    snapshots,
    state,
    sudo,
    timeline,
    token_costs,
    replay,
)


def test_blocking_read_handlers_are_sync_for_fastapi_threadpool() -> None:
    handlers = [
        state.get_state,
        health.get_health,
        projects.get_projects,
        patterns.get_patterns,
        dashboard.get_dashboard,
        agents.get_agents,
        corrections.get_corrections,
        timeline.get_timeline,
        skills.get_skills,
        sudo.get_sudo,
        providers.get_providers,
        model_info.get_model_info,
        model_info.get_model_analytics,
        snapshots.get_snapshots,
        memory.get_memory,
        profiles.get_profiles,
        cron.get_cron,
        token_costs.get_token_costs,
        gateway.get_gateway,
        plugins.get_plugins,
        sessions.get_sessions,
        sessions.search_sessions,
        sessions.get_session_messages,
        replay.get_replay_runs,
        replay.sync_remote_gallery,
        replay.export_replay_share_card,
        gateway.restart_gateway,
        plugins.install_plugin_endpoint,
    ]

    assert not [
        handler.__name__ for handler in handlers if inspect.iscoroutinefunction(handler)
    ]
