"""Scan Hermes skills directory and extract metadata."""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from ..cache import get_cached_or_compute
from .models import SkillInfo, SkillsState
from .utils import default_hermes_dir


def _parse_skill_md(path: Path) -> dict:
    """Extract frontmatter fields from a SKILL.md file."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    info = {}

    # Extract YAML frontmatter between --- markers
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm = fm_match.group(1)
        for line in fm.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip().strip("'\"")
                if key in ("name", "description", "version", "author"):
                    info[key] = val

    # Fallback: extract description from first markdown paragraph
    if "description" not in info:
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("---")
            ):
                info["description"] = stripped[:120]
                break

    return info


def _detect_custom(skill: SkillInfo, bulk_timestamps: set[int]) -> bool:
    """Heuristic: a skill is 'custom' if its mtime doesn't match a bulk install timestamp."""
    # Round to nearest minute for comparison
    skill_minute = int(skill.modified_at.timestamp()) // 60
    return skill_minute not in bulk_timestamps


def _do_collect_skills(skills_dir: Path) -> SkillsState:
    """Actually scan skills directory (internal, uncached)."""
    skills: list[SkillInfo] = []
    mtimes: list[int] = []

    for skill_md in skills_dir.rglob("SKILL.md"):
        stat = skill_md.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime)
        mtime_minute = int(stat.st_mtime) // 60

        # Derive category from directory structure
        rel = skill_md.relative_to(skills_dir)
        parts = rel.parts[:-1]  # remove SKILL.md
        if len(parts) >= 2:
            category = parts[0]
            name = parts[-1]
        elif len(parts) == 1:
            category = "uncategorized"
            name = parts[0]
        else:
            continue

        meta = _parse_skill_md(skill_md)

        skills.append(
            SkillInfo(
                name=meta.get("name", name),
                category=category,
                description=meta.get("description", ""),
                path=str(skill_md),
                modified_at=mtime,
                file_size=stat.st_size,
            )
        )
        mtimes.append(mtime_minute)

    # Detect bulk install timestamps (most common minute-rounded mtimes)
    if mtimes:
        counter = Counter(mtimes)
        # Any timestamp shared by 5+ skills is likely a bulk install
        bulk_timestamps = {t for t, count in counter.items() if count >= 5}

        for skill in skills:
            skill.is_custom = _detect_custom(skill, bulk_timestamps)

    return SkillsState(skills=skills)


def collect_skills(hermes_dir: str | None = None) -> SkillsState:
    """Collect all skills metadata (cached, invalidates on directory changes)."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    skills_dir = Path(hermes_dir) / "skills"
    if not skills_dir.exists():
        return SkillsState()

    return get_cached_or_compute(
        cache_key=f"skills:{hermes_dir}",
        compute_fn=lambda: _do_collect_skills(skills_dir),
        dir_paths=[skills_dir],
        ttl=60,  # 60 second cache even if unchanged
    )
