import json
from pathlib import Path

from backend.cache import clear_cache
from backend.collectors.providers import collect_providers


def _write_config(hermes_dir: Path, provider: str, model: str) -> None:
    (hermes_dir / "config.yaml").write_text(
        f"model:\n  provider: {provider}\n  default: {model}\n",
        encoding="utf-8",
    )


def test_providers_warn_when_configured_provider_has_no_available_key(tmp_path: Path, monkeypatch) -> None:
    clear_cache()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _write_config(tmp_path, "anthropic", "claude-sonnet-4-6")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-openai\n", encoding="utf-8")
    (tmp_path / "models_dev_cache.json").write_text(
        json.dumps({"anthropic": {"models": {"claude-sonnet-4-6": {"tool_call": True}}}}),
        encoding="utf-8",
    )

    state = collect_providers(str(tmp_path))

    assert state.config_provider == "anthropic"
    assert state.config_model == "claude-sonnet-4-6"
    assert "No available key or OAuth token for configured provider 'anthropic'" in state.warnings


def test_providers_warn_for_expired_configured_oauth_and_active_provider_mismatch(tmp_path: Path, monkeypatch) -> None:
    clear_cache()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _write_config(tmp_path, "anthropic", "claude-sonnet-4-6")
    (tmp_path / "auth.json").write_text(
        json.dumps(
            {
                "active_provider": "openai-codex",
                "providers": {
                    "anthropic": {
                        "access_token": "expired-token",
                        "expires_at": "2000-01-01T00:00:00",
                    },
                    "openai-codex": {"access_token": "live-token"},
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "models_dev_cache.json").write_text(
        json.dumps({"anthropic": {"models": {"claude-sonnet-4-6": {"tool_call": True}}}}),
        encoding="utf-8",
    )

    state = collect_providers(str(tmp_path))
    anthropic = next(provider for provider in state.providers if provider.id == "anthropic")

    assert "Configured provider OAuth is expired" in anthropic.warnings
    assert "Configured provider is 'anthropic' but active OAuth provider is 'openai-codex'" in state.warnings


def test_providers_warn_when_model_metadata_belongs_to_different_provider(tmp_path: Path, monkeypatch) -> None:
    clear_cache()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    _write_config(tmp_path, "anthropic", "gpt-5")
    (tmp_path / "models_dev_cache.json").write_text(
        json.dumps({"openai": {"models": {"gpt-5": {"tool_call": True}}}}),
        encoding="utf-8",
    )

    state = collect_providers(str(tmp_path))

    assert "Configured model 'gpt-5' is listed under provider 'openai', not 'anthropic'" in state.warnings


def test_providers_warn_when_configured_model_lacks_tool_metadata(tmp_path: Path, monkeypatch) -> None:
    clear_cache()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    _write_config(tmp_path, "anthropic", "claude-text-only")
    (tmp_path / "models_dev_cache.json").write_text(
        json.dumps({"anthropic": {"models": {"claude-text-only": {"tool_call": False}}}}),
        encoding="utf-8",
    )

    state = collect_providers(str(tmp_path))

    assert "Configured model 'claude-text-only' does not advertise tool-call support in models.dev" in state.warnings


def test_providers_recognize_xai_oauth_config_via_xai_api_key(tmp_path: Path, monkeypatch) -> None:
    clear_cache()
    monkeypatch.setenv("XAI_API_KEY", "xai-key")
    _write_config(tmp_path, "xai-oauth", "grok-4.6")
    (tmp_path / "models_dev_cache.json").write_text(
        json.dumps({"xai": {"models": {"grok-4.6": {"tool_call": True}}}}),
        encoding="utf-8",
    )

    state = collect_providers(str(tmp_path))

    assert state.config_provider == "xai-oauth"
    assert not any("No available key" in warning for warning in state.warnings)
