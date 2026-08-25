from backend.api.replay import build_replay_run, router


def test_replay_routes_are_registered(registered_routes) -> None:
    paths = {path for _, path in registered_routes}

    assert "/api/replay/runs" in paths
    assert "/api/replay/runs/{session_id}" in paths
    assert "/api/replay/runs/{session_id}/build" in paths
    assert "/api/replay/runs/{session_id}/share-card" in paths
    assert "/api/replay/runs/{session_id}/publish" in paths
    assert "/api/replay/runs/{session_id}/view" in paths
    assert "/api/replay/runs/{session_id}/clip" in paths
    assert "/api/replay/settings" in paths
    assert "/api/replay/skills" in paths
    assert "/api/replay/gallery" in paths
    assert "/api/replay/verify" in paths
    assert ("DELETE", "/api/replay/runs/{session_id}/publish") in registered_routes


def test_build_endpoint_returns_serialized_replay(monkeypatch) -> None:
    from backend.models.replay import ReplayCounts, ReplayDetail, ReplayRun

    def fake_detail(session_id: str):
        return ReplayDetail(
            run=ReplayRun(
                replay_id="replay_123",
                source_session_id=session_id,
                title="Replay",
                status="unknown",
                counts=ReplayCounts(messages=0, tool_calls=0, skills_used=0),
            )
        )

    monkeypatch.setattr("backend.api.replay.get_replay_detail", fake_detail)

    response = build_replay_run("session-1")

    assert response["run"]["source_session_id"] == "session-1"


def test_replay_router_has_expected_export_endpoints() -> None:
    paths = {route.path for route in router.routes}
    methods = {(method, route.path) for route in router.routes for method in getattr(route, "methods", set())}

    assert "/replay/runs/{session_id}/export/json" in paths
    assert "/replay/runs/{session_id}/export/markdown" in paths
    assert "/replay/runs/{session_id}/export/html" in paths
    assert "/replay/runs/{session_id}/fork" in paths
    assert "/replay/settings" in paths
    assert "/replay/skills" in paths
    assert "/replay/gallery" in paths
    assert "/replay/verify" in paths
    assert "/replay/runs/{session_id}/publish" in paths
    assert "/replay/runs/{session_id}/clip" in paths
    assert "/replay/runs/{session_id}/view" in paths
    assert ("DELETE", "/replay/runs/{session_id}/publish") in methods
