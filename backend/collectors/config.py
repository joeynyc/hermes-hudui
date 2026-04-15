"""Parse Hermes config.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .models import ConfigState
from .utils import default_hermes_dir, load_yaml


def collect_config(hermes_dir: str | None = None) -> ConfigState:
    """Collect configuration state."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    config_path = Path(hermes_dir) / "config.yaml"
    if not config_path.exists():
        return ConfigState()

    data = load_yaml(config_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        return ConfigState()

    model_section = data.get("model", {})
    agent_section = data.get("agent", {})
    terminal_section = data.get("terminal", {})
    compression_section = data.get("compression", {})
    checkpoints_section = data.get("checkpoints", {})
    memory_section = data.get("memory", {})
    skills_section = data.get("skills", {})

    return ConfigState(
        model=model_section.get("default", "") if isinstance(model_section, dict) else str(model_section),
        provider=model_section.get("provider", "") if isinstance(model_section, dict) else "",
        toolsets=data.get("toolsets", []),
        backend=terminal_section.get("backend", "") if isinstance(terminal_section, dict) else "",
        max_turns=agent_section.get("max_turns", 0) if isinstance(agent_section, dict) else 0,
        compression_enabled=compression_section.get("enabled", False) if isinstance(compression_section, dict) else False,
        checkpoints_enabled=checkpoints_section.get("enabled", False) if isinstance(checkpoints_section, dict) else False,
        memory_char_limit=memory_section.get("memory_char_limit", 2200) if isinstance(memory_section, dict) else 2200,
        user_char_limit=memory_section.get("user_char_limit", 1375) if isinstance(memory_section, dict) else 1375,
        external_skill_dirs=_parse_external_skill_dirs(skills_section, hermes_dir),
    )


def _parse_external_skill_dirs(skills_section: object, hermes_dir: str) -> list[str]:
    """Read `skills.external_dirs` from config.yaml and resolve each entry.

    - Drops anything that isn't a non-empty string.
    - Expands ``~`` and ``$VAR`` style references.
    - Resolves relative paths against the Hermes dir so they match the
      shape of the implicit ``<hermes_dir>/skills`` location.
    - Drops duplicates while preserving config order.
    """
    if not isinstance(skills_section, dict):
        return []
    raw = skills_section.get("external_dirs", [])
    if not isinstance(raw, list):
        return []

    resolved: list[str] = []
    seen: set[str] = set()
    base = Path(hermes_dir)
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            continue
        expanded = os.path.expandvars(os.path.expanduser(entry.strip()))
        path = Path(expanded)
        if not path.is_absolute():
            path = (base / path)
        absolute = str(path.resolve())
        if absolute in seen:
            continue
        seen.add(absolute)
        resolved.append(absolute)
    return resolved
