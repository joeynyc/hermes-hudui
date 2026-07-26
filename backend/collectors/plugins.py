"""Collect Hermes plugin and dashboard extension metadata."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .models import PluginInfo, PluginsState
from .utils import default_hermes_dir, load_yaml

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

_PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MAX_MANIFEST_BYTES = 1024 * 1024


def _safe_descendant(root: Path, *parts: str) -> Path:
    """Return a canonical path below root, rejecting traversal and symlinks out."""
    canonical_root = root.expanduser().resolve()
    candidate = canonical_root.joinpath(*parts).resolve(strict=False)
    try:
        candidate.relative_to(canonical_root)
    except ValueError as exc:
        raise ValueError("Plugin path escapes the configured plugin directory") from exc
    if candidate == canonical_root:
        raise ValueError("Plugin path must name a child of the plugin directory")
    return candidate


def _user_plugins_dir(hermes_dir: str | None = None) -> Path:
    hermes_root = Path(default_hermes_dir(hermes_dir)).expanduser().resolve()
    plugins_dir = (hermes_root / "plugins").resolve(strict=False)
    try:
        plugins_dir.relative_to(hermes_root)
    except ValueError as exc:
        raise ValueError("Plugin directory escapes the Hermes directory") from exc
    return plugins_dir


def _read_text(path: Path) -> str:
    if path.stat().st_size > _MAX_MANIFEST_BYTES:
        raise ValueError(f"Plugin manifest is larger than {_MAX_MANIFEST_BYTES} bytes")
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(_read_text(path))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, ValueError, TypeError):
        return {}


def _read_agent_manifest(plugin_dir: Path) -> dict[str, Any]:
    for filename in ("plugin.yaml", "plugin.yml"):
        path = _safe_descendant(plugin_dir, filename)
        if path.exists():
            return load_yaml(_read_text(path))
    path = _safe_descendant(plugin_dir, "manifest.json")
    if path.exists():
        return _read_json(path)
    return {}


def _runtime_status(manifest: dict[str, Any]) -> str:
    if not manifest:
        return "inactive"
    enabled = manifest.get("enabled")
    if enabled is False:
        return "disabled"
    if enabled is True:
        return "enabled"
    return "inactive"


def _list_tools(manifest: dict[str, Any]) -> list[str]:
    tools = manifest.get("provides_tools") or manifest.get("tools") or []
    if isinstance(tools, list):
        return [str(tool) for tool in tools if tool]
    return []


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    if _yaml:
        text = _yaml.safe_dump(data, sort_keys=False)
    else:
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            if isinstance(value, list):
                lines.append(f"{key}:")
                lines.extend(f"  - {item}" for item in value)
            else:
                lines.append(f"{key}: {value}")
        text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")


def _plugin_from_dir(plugin_dir: Path, source: str) -> PluginInfo | None:
    dashboard_manifest = _read_json(
        _safe_descendant(plugin_dir, "dashboard", "manifest.json")
    )
    agent_manifest = _read_agent_manifest(plugin_dir)
    if not dashboard_manifest and not agent_manifest:
        return None

    name = str(
        dashboard_manifest.get("name")
        or agent_manifest.get("name")
        or plugin_dir.name
    )
    label = str(dashboard_manifest.get("label") or agent_manifest.get("label") or name)
    description = str(
        dashboard_manifest.get("description")
        or agent_manifest.get("description")
        or ""
    )
    version = str(dashboard_manifest.get("version") or agent_manifest.get("version") or "")
    raw_tab = dashboard_manifest.get("tab", {}) if isinstance(dashboard_manifest.get("tab"), dict) else {}
    slots = dashboard_manifest.get("slots") or []

    return PluginInfo(
        name=name,
        label=label,
        description=description,
        version=version,
        source=source,
        path=str(plugin_dir),
        runtime_status=_runtime_status(agent_manifest),
        has_dashboard_manifest=bool(dashboard_manifest),
        has_api=bool(dashboard_manifest.get("api")),
        user_hidden=bool(raw_tab.get("hidden")),
        entry=str(dashboard_manifest.get("entry") or ""),
        css=dashboard_manifest.get("css") if isinstance(dashboard_manifest.get("css"), str) else None,
        icon=str(dashboard_manifest.get("icon") or "Puzzle"),
        tab_path=str(raw_tab.get("path") or f"/{name}"),
        tab_position=str(raw_tab.get("position") or "end"),
        slots=[str(slot) for slot in slots if isinstance(slot, str) and slot],
        provides_tools=_list_tools(agent_manifest),
        auth_required=bool(agent_manifest.get("auth_required")),
        auth_command=str(agent_manifest.get("auth_command") or ""),
        can_update_git=source == "user" and _safe_descendant(plugin_dir, ".git").exists(),
    )


def _candidate_dirs(
    hermes_dir: str,
    bundled_plugins_dir: str | None,
    project_dir: str | None,
    include_project_plugins: bool,
) -> list[tuple[Path, str]]:
    dirs: list[tuple[Path, str]] = [(Path(hermes_dir) / "plugins", "user")]

    if bundled_plugins_dir:
        bundled_root = Path(bundled_plugins_dir)
        dirs.extend([(bundled_root / "memory", "bundled"), (bundled_root, "bundled")])
    else:
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "plugins"
            if candidate.exists():
                dirs.extend([(candidate / "memory", "bundled"), (candidate, "bundled")])
                break

    if include_project_plugins and project_dir:
        dirs.append((Path(project_dir) / ".hermes" / "plugins", "project"))

    return dirs


def collect_plugins(
    hermes_dir: str | None = None,
    bundled_plugins_dir: str | None = None,
    project_dir: str | None = None,
    include_project_plugins: bool | None = None,
) -> PluginsState:
    """Discover installed plugin metadata.

    User plugins take precedence over bundled/project plugins with the same
    manifest name, matching Hermes' dashboard discovery behavior.
    """
    hermes_dir = default_hermes_dir(hermes_dir)
    if include_project_plugins is None:
        include_project_plugins = bool(os.environ.get("HERMES_ENABLE_PROJECT_PLUGINS"))
    if project_dir is None:
        project_dir = os.getcwd()

    plugins: list[PluginInfo] = []
    seen: set[str] = set()

    for root, source in _candidate_dirs(
        hermes_dir,
        bundled_plugins_dir,
        project_dir,
        include_project_plugins,
    ):
        root = root.expanduser().resolve()
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            try:
                plugin_dir = _safe_descendant(root, child.name)
            except ValueError:
                continue
            if not plugin_dir.is_dir():
                continue
            try:
                plugin = _plugin_from_dir(plugin_dir, source)
            except ValueError:
                continue
            if not plugin or plugin.name in seen:
                continue
            seen.add(plugin.name)
            plugins.append(plugin)

    return PluginsState(plugins=plugins)


def _validate_plugin_name(name: str) -> str:
    if not _PLUGIN_NAME_RE.fullmatch(name):
        raise ValueError("Invalid plugin name")
    return name


def _find_user_plugin(name: str, hermes_dir: str | None = None) -> Path:
    name = _validate_plugin_name(name)
    plugin_dir = _safe_descendant(_user_plugins_dir(hermes_dir), name)
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"User plugin not found: {name}")
    return plugin_dir


def set_plugin_enabled(
    name: str,
    enabled: bool,
    hermes_dir: str | None = None,
) -> dict[str, Any]:
    """Enable or disable a user plugin by updating its manifest."""
    plugin_dir = _find_user_plugin(name, hermes_dir)
    for filename in ("plugin.yaml", "plugin.yml"):
        path = _safe_descendant(plugin_dir, filename)
        if path.exists():
            data = load_yaml(_read_text(path))
            data["enabled"] = bool(enabled)
            _write_yaml(path, data)
            return {"ok": True, "name": name, "enabled": bool(enabled)}

    path = _safe_descendant(plugin_dir, "manifest.json")
    if path.exists():
        data = _read_json(path)
        data["enabled"] = bool(enabled)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "name": name, "enabled": bool(enabled)}

    raise FileNotFoundError(f"Plugin manifest not found: {name}")


def set_dashboard_plugin_hidden(
    name: str,
    hidden: bool,
    hermes_dir: str | None = None,
) -> dict[str, Any]:
    """Hide or show a user dashboard plugin tab by updating its manifest."""
    plugin_dir = _find_user_plugin(name, hermes_dir)
    path = _safe_descendant(plugin_dir, "dashboard", "manifest.json")
    if not path.exists():
        raise FileNotFoundError(f"Dashboard manifest not found: {name}")
    data = _read_json(path)
    tab = data.get("tab") if isinstance(data.get("tab"), dict) else {}
    tab["hidden"] = bool(hidden)
    data["tab"] = tab
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "name": name, "hidden": bool(hidden)}


def _plugin_name_from_identifier(identifier: str) -> str:
    raw = identifier.rstrip("/").rsplit("/", 1)[-1]
    raw = raw.removesuffix(".git")
    return _validate_plugin_name(raw)


def install_plugin(
    identifier: str,
    hermes_dir: str | None = None,
    runner=subprocess.run,
) -> dict[str, Any]:
    """Install a plugin from a git URL/path into ~/.hermes/plugins."""
    identifier = identifier.strip()
    if not identifier:
        raise ValueError("Plugin identifier is required")
    if len(identifier) > 2048:
        raise ValueError("Plugin identifier is too long")
    if identifier.startswith("-") or "\x00" in identifier:
        raise ValueError("Invalid plugin identifier")
    name = _plugin_name_from_identifier(identifier)
    plugins_dir = _user_plugins_dir(hermes_dir)
    plugins_dir.mkdir(parents=True, exist_ok=True)
    destination = _safe_descendant(plugins_dir, name)
    if destination.exists():
        raise FileExistsError(f"Plugin already exists: {name}")

    result = runner(
        ["git", "clone", "--", identifier, str(destination)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "git clone failed")
    return {"ok": True, "name": name, "path": str(destination)}


def update_plugin(
    name: str,
    hermes_dir: str | None = None,
    runner=subprocess.run,
) -> dict[str, Any]:
    """Update a user-installed git plugin with fast-forward pull."""
    plugin_dir = _find_user_plugin(name, hermes_dir)
    if not _safe_descendant(plugin_dir, ".git").exists():
        raise RuntimeError(f"Plugin is not git-backed: {name}")
    result = runner(
        ["git", "pull", "--ff-only"],
        cwd=str(plugin_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "git pull failed")
    return {"ok": True, "name": name, "path": str(plugin_dir), "output": result.stdout}
