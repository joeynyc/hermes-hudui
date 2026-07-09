"""Write-path tests for the profile editing API (backend/api/profiles.py).

``PUT /api/profiles/{name}/edit`` rewrites a profile's ``config.yaml`` and
``SOUL.md`` via an atomic write under a lock. These cover the corruption- and
safety-sensitive surface: round-trip persistence, valid YAML output, path
traversal / name validation, the "model/provider cannot be silently cleared"
guards, and that rejected edits never touch the on-disk config.

``default_hermes_dir()`` reads ``HERMES_HOME`` at call time, so the profile
tree is built under a tmp dir.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

import backend.collectors.profiles as profile_collector
from backend.api.profiles import (
    ProfileCompressionEdit,
    ProfileEditBody,
    ProfileModelEdit,
    get_profile_edit,
    profile_options,
    update_profile_edit,
)
from backend.collectors.utils import load_yaml


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _seed_profile(home: Path, name: str, config: dict) -> Path:
    profile_dir = home if name == "default" else home / "profiles" / name
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    return profile_dir


def test_get_profile_edit_reads_existing_config(hermes_home: Path) -> None:
    _seed_profile(hermes_home, "work", {"model": {"default": "m1"}, "toolsets": ["web"]})

    payload = get_profile_edit("work")
    assert payload["name"] == "work"
    assert payload["model"]["default"] == "m1"
    assert payload["toolsets"] == ["web"]


def test_update_round_trips_config_and_soul(hermes_home: Path) -> None:
    profile_dir = _seed_profile(
        hermes_home, "work", {"model": {"provider": "anthropic", "default": "claude-x"}}
    )

    body = ProfileEditBody(
        model=ProfileModelEdit(
            provider="anthropic", default="claude-opus", context_length=200000
        ),
        toolsets=["web", "file", "web"],  # duplicate is deduped
        skin="blade-runner",
        compression=ProfileCompressionEdit(
            enabled=True, summary_provider="anthropic", summary_model="haiku"
        ),
        soul="You are helpful.",
    )
    result = update_profile_edit("work", body)

    # response reflects the new state
    assert result["model"]["default"] == "claude-opus"
    assert result["model"]["context_length"] == 200000
    assert result["toolsets"] == ["web", "file"]
    assert result["skin"] == "blade-runner"
    assert result["compression"]["enabled"] is True
    assert result["soul"] == "You are helpful.\n"

    # config.yaml is valid YAML with the persisted values
    cfg = load_yaml((profile_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "claude-opus"
    assert cfg["toolsets"] == ["web", "file"]
    assert cfg["display"]["skin"] == "blade-runner"
    assert cfg["compression"]["enabled"] is True
    # SOUL.md written with a trailing newline
    assert (profile_dir / "SOUL.md").read_text(encoding="utf-8") == "You are helpful.\n"


def test_update_default_profile_writes_to_hermes_root(hermes_home: Path) -> None:
    _seed_profile(hermes_home, "default", {"model": {"default": "m"}})

    update_profile_edit(
        "default", ProfileEditBody(model=ProfileModelEdit(default="m2"), soul="hi")
    )

    cfg = load_yaml((hermes_home / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "m2"
    assert (hermes_home / "SOUL.md").read_text(encoding="utf-8") == "hi\n"


def test_invalid_profile_name_is_rejected(hermes_home: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        get_profile_edit("../evil")
    assert exc.value.status_code == 400


def test_unknown_profile_returns_404(hermes_home: Path) -> None:
    with pytest.raises(HTTPException) as exc:
        get_profile_edit("ghost")
    assert exc.value.status_code == 404


def test_cannot_clear_existing_model_default(hermes_home: Path) -> None:
    profile_dir = _seed_profile(
        hermes_home, "work", {"model": {"provider": "anthropic", "default": "claude-x"}}
    )

    body = ProfileEditBody(model=ProfileModelEdit(provider="anthropic", default=""))
    with pytest.raises(HTTPException) as exc:
        update_profile_edit("work", body)
    assert exc.value.status_code == 400

    # the original config must be untouched after a rejected edit
    cfg = load_yaml((profile_dir / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "claude-x"


def test_base_url_must_be_http(hermes_home: Path) -> None:
    _seed_profile(hermes_home, "work", {"model": {"default": "m"}})

    body = ProfileEditBody(model=ProfileModelEdit(default="m", base_url="ftp://nope"))
    with pytest.raises(HTTPException) as exc:
        update_profile_edit("work", body)
    assert exc.value.status_code == 400


def test_update_leaves_no_temp_files(hermes_home: Path) -> None:
    profile_dir = _seed_profile(hermes_home, "work", {"model": {"default": "m"}})

    update_profile_edit(
        "work", ProfileEditBody(model=ProfileModelEdit(default="m2"), soul="hi")
    )

    leftovers = [p.name for p in profile_dir.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_profile_edit_routes_are_registered(registered_routes) -> None:
    assert ("GET", "/api/profiles/{profile_name}/edit") in registered_routes
    assert ("PUT", "/api/profiles/{profile_name}/edit") in registered_routes


def test_profile_health_check_allows_literal_loopback_host(monkeypatch) -> None:
    calls = []

    class Response:
        status = 200

    def fake_urlopen(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(profile_collector, "urlopen", fake_urlopen)

    assert profile_collector._check_server_status("http://127.0.0.1:8080/v1") == "running"
    assert calls == [("http://127.0.0.1:8080/health", {"timeout": 2})]


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost.evil.example",
        "http://localhost@evil.example",
        "file://localhost/etc/passwd",
    ],
)
def test_profile_health_check_rejects_non_loopback_targets(
    monkeypatch, base_url: str
) -> None:
    monkeypatch.setattr(
        profile_collector,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("urlopen must not be called"),
    )

    assert profile_collector._check_server_status(base_url) == "n/a"


def test_profile_options_include_minimax_models_and_regional_endpoints() -> None:
    options = asyncio.run(profile_options())
    preset = options["provider_presets"]["minimax"]

    assert "minimax" in options["providers"]
    assert [model["id"] for model in preset["models"]] == ["MiniMax-M3", "MiniMax-M2.7"]
    assert [model["context_window"] for model in preset["models"]] == [1_000_000, 204_800]
    assert {endpoint["region"] for endpoint in preset["endpoints"]} == {"global_en", "cn_zh"}
    assert {endpoint["openai_base_url"] for endpoint in preset["endpoints"]} == {
        "https://api.minimax.io/v1",
        "https://api.minimaxi.com/v1",
    }
    assert {endpoint["anthropic_base_url"] for endpoint in preset["endpoints"]} == {
        "https://api.minimax.io/anthropic/v1",
        "https://api.minimaxi.com/anthropic/v1",
    }
