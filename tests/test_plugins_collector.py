import json
from pathlib import Path

import pytest

from backend.collectors.plugins import (
    collect_plugins,
    install_plugin,
    set_dashboard_plugin_hidden,
    set_plugin_enabled,
    update_plugin,
)


def _write_dashboard_plugin(root: Path, name: str, label: str, *, hidden: bool = False) -> None:
    dashboard_dir = root / name / "dashboard"
    dashboard_dir.mkdir(parents=True)
    manifest = {
        "name": name,
        "label": label,
        "description": f"{label} dashboard",
        "icon": "Puzzle",
        "version": "1.2.3",
        "tab": {"path": f"/{name}", "position": "end", "hidden": hidden},
        "slots": ["sessions.after"],
        "entry": "dist/index.js",
        "css": "dist/style.css",
        "api": "plugin_api.py",
    }
    (dashboard_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _write_agent_plugin(root: Path, name: str, *, enabled: bool = True) -> None:
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.yaml").write_text(
        f"""
name: {name}
version: 0.4.0
description: Agent plugin for {name}
enabled: {str(enabled).lower()}
provides_tools:
  - {name}_tool
auth_required: true
auth_command: hermes auth {name}
""".strip(),
        encoding="utf-8",
    )


def test_collect_plugins_discovers_dashboard_and_agent_metadata(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    bundled_dir = tmp_path / "bundled"
    project_dir = tmp_path / "project"

    _write_dashboard_plugin(hermes_dir / "plugins", "alpha", "Alpha")
    _write_agent_plugin(hermes_dir / "plugins", "alpha", enabled=False)
    _write_dashboard_plugin(bundled_dir, "beta", "Beta")
    _write_agent_plugin(bundled_dir, "gamma")
    _write_dashboard_plugin(project_dir / ".hermes" / "plugins", "delta", "Delta", hidden=True)

    state = collect_plugins(
        hermes_dir=str(hermes_dir),
        bundled_plugins_dir=str(bundled_dir),
        project_dir=str(project_dir),
        include_project_plugins=True,
    )

    by_name = {plugin.name: plugin for plugin in state.plugins}

    assert state.total_plugins == 4
    assert state.dashboard_count == 3
    assert state.agent_count == 2
    assert state.hidden_count == 1
    assert by_name["alpha"].source == "user"
    assert by_name["alpha"].runtime_status == "disabled"
    assert by_name["alpha"].has_dashboard_manifest is True
    assert by_name["alpha"].has_api is True
    assert by_name["alpha"].provides_tools == ["alpha_tool"]
    assert by_name["alpha"].auth_required is True
    assert by_name["alpha"].auth_command == "hermes auth alpha"
    assert by_name["beta"].source == "bundled"
    assert by_name["gamma"].has_dashboard_manifest is False
    assert by_name["delta"].user_hidden is True


def test_collect_plugins_prefers_user_plugin_over_bundled_duplicate(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    bundled_dir = tmp_path / "bundled"

    _write_dashboard_plugin(hermes_dir / "plugins", "same", "User Same")
    _write_dashboard_plugin(bundled_dir, "same", "Bundled Same")

    state = collect_plugins(
        hermes_dir=str(hermes_dir),
        bundled_plugins_dir=str(bundled_dir),
    )

    assert [plugin.name for plugin in state.plugins] == ["same"]
    assert state.plugins[0].label == "User Same"
    assert state.plugins[0].source == "user"


def test_set_plugin_enabled_updates_user_manifest(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    _write_agent_plugin(hermes_dir / "plugins", "alpha", enabled=False)

    result = set_plugin_enabled("alpha", True, hermes_dir=str(hermes_dir))
    state = collect_plugins(hermes_dir=str(hermes_dir))

    assert result["ok"] is True
    assert state.plugins[0].runtime_status == "enabled"
    assert "enabled: true" in (hermes_dir / "plugins" / "alpha" / "plugin.yaml").read_text()


def test_set_dashboard_plugin_hidden_updates_user_manifest(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    _write_dashboard_plugin(hermes_dir / "plugins", "alpha", "Alpha")

    result = set_dashboard_plugin_hidden("alpha", True, hermes_dir=str(hermes_dir))
    manifest = json.loads(
        (hermes_dir / "plugins" / "alpha" / "dashboard" / "manifest.json").read_text()
    )

    assert result["ok"] is True
    assert manifest["tab"]["hidden"] is True


def test_install_plugin_clones_git_url_into_user_plugins(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    calls = []

    def fake_runner(cmd, **kwargs):
        calls.append((cmd, kwargs))
        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""
        return Result()

    result = install_plugin(
        "https://github.com/example/my-plugin.git",
        hermes_dir=str(hermes_dir),
        runner=fake_runner,
    )

    assert result["ok"] is True
    assert calls[0][0][:2] == ["git", "clone"]
    assert calls[0][0][2] == "--"
    assert calls[0][0][3] == "https://github.com/example/my-plugin.git"
    assert calls[0][0][4] == str(hermes_dir / "plugins" / "my-plugin")


def test_update_plugin_pulls_user_git_plugin(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    _write_agent_plugin(hermes_dir / "plugins", "alpha")
    (hermes_dir / "plugins" / "alpha" / ".git").mkdir()
    calls = []

    def fake_runner(cmd, **kwargs):
        calls.append((cmd, kwargs))
        class Result:
            returncode = 0
            stdout = "updated"
            stderr = ""
        return Result()

    result = update_plugin("alpha", hermes_dir=str(hermes_dir), runner=fake_runner)

    assert result["ok"] is True
    assert calls[0][0] == ["git", "pull", "--ff-only"]
    assert calls[0][1]["cwd"] == str(hermes_dir / "plugins" / "alpha")


@pytest.mark.parametrize("name", [".", "..", ".hidden", "../outside", "nested/plugin"])
def test_plugin_mutations_reject_unsafe_names(tmp_path: Path, name: str) -> None:
    hermes_dir = tmp_path / "hermes"

    with pytest.raises(ValueError, match="Invalid plugin name"):
        set_plugin_enabled(name, True, hermes_dir=str(hermes_dir))


def test_plugin_mutations_reject_symlink_escape(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    plugins_dir = hermes_dir / "plugins"
    outside = tmp_path / "outside"
    _write_agent_plugin(outside, "alpha")
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "alpha").symlink_to(outside / "alpha", target_is_directory=True)

    with pytest.raises(ValueError, match="escapes"):
        set_plugin_enabled("alpha", True, hermes_dir=str(hermes_dir))


def test_plugin_manifest_symlink_escape_is_rejected(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    plugin_dir = hermes_dir / "plugins" / "alpha"
    plugin_dir.mkdir(parents=True)
    outside_manifest = tmp_path / "outside.yaml"
    outside_manifest.write_text("name: outside\nenabled: false\n", encoding="utf-8")
    (plugin_dir / "plugin.yaml").symlink_to(outside_manifest)

    with pytest.raises(ValueError, match="escapes"):
        set_plugin_enabled("alpha", True, hermes_dir=str(hermes_dir))

    assert "enabled: false" in outside_manifest.read_text(encoding="utf-8")


def test_plugin_mutation_rejects_symlinked_plugin_root_escape(tmp_path: Path) -> None:
    hermes_dir = tmp_path / "hermes"
    outside = tmp_path / "outside"
    hermes_dir.mkdir()
    _write_agent_plugin(outside, "alpha")
    (hermes_dir / "plugins").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="Plugin directory escapes"):
        set_plugin_enabled("alpha", True, hermes_dir=str(hermes_dir))


def test_install_plugin_rejects_git_option_injection(tmp_path: Path) -> None:
    called = False

    def fake_runner(*args, **kwargs):
        nonlocal called
        called = True

    with pytest.raises(ValueError, match="Invalid plugin identifier"):
        install_plugin("--upload-pack=malicious", hermes_dir=str(tmp_path), runner=fake_runner)

    assert called is False
