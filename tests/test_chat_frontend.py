from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_panel_refreshes_backend_composer_state() -> None:
    panel = (ROOT / "frontend/src/components/ChatPanel.tsx").read_text()

    assert "loadComposerState" in panel
    assert "loadComposerState()" in panel
    assert "window.setInterval(loadComposerState, 1000)" in panel
    assert "[selectedSessionId, isStreaming, loadComposerState]" in panel
    assert "status={composerState.status}" in panel
    assert "firstTokenMs={composerState.firstTokenMs}" in panel
    assert "<ChatDiagnostics" in panel
    assert "recentFirstTokenAvgMs={composerState.recentFirstTokenAvgMs}" in panel


def test_chat_composer_shows_stage_and_latency() -> None:
    composer = (ROOT / "frontend/src/components/chat/Composer.tsx").read_text()
    hook = (ROOT / "frontend/src/hooks/useChat.ts").read_text()

    assert "starting Hermes" in composer
    assert "connecting model" in composer
    assert "first token" in composer
    assert "status: state.status" in hook
    assert "firstTokenMs: state.first_token_ms" in hook
    assert "recentFirstTokenAvgMs: state.recent_first_token_avg_ms" in hook


def test_chat_diagnostics_panel_shows_latency_breakdown() -> None:
    diagnostics = (ROOT / "frontend/src/components/chat/ChatDiagnostics.tsx").read_text()

    assert "Spawn" in diagnostics
    assert "First Token" in diagnostics
    assert "Resume" in diagnostics
    assert "recentFirstTokenAvgMs" in diagnostics
    assert "recentTotalAvgMs" in diagnostics
