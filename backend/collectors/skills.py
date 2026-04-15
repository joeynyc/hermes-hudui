"""Scan Hermes skills directory and extract metadata."""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

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


def _scan_skill_dir(skills_dir: Path, *, mark_external: bool) -> tuple[list[SkillInfo], list[int]]:
    """Scan a single SKILL.md tree.

    Returns the (skills, minute-rounded mtimes) so the caller can run a
    single bulk-install heuristic across all sources.
    """
    skills: list[SkillInfo] = []
    mtimes: list[int] = []

    for skill_md in skills_dir.rglob("SKILL.md"):
        try:
            stat = skill_md.stat()
        except OSError:
            continue
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

        skill = SkillInfo(
            name=meta.get("name", name),
            category=category,
            description=meta.get("description", ""),
            path=str(skill_md),
            modified_at=mtime,
            file_size=stat.st_size,
        )
        # Externally-mounted skills are by definition user-curated.
        if mark_external:
            skill.is_custom = True

        skills.append(skill)
        mtimes.append(mtime_minute)

    return skills, mtimes


def _do_collect_skills(
    skills_dir: Path,
    external_dirs: Iterable[Path] = (),
) -> SkillsState:
    """Scan the implicit `<hermes_dir>/skills` tree plus any external dirs.

    External skills are marked ``is_custom=True`` unconditionally — they
    were explicitly added by the user via `skills.external_dirs` in
    config.yaml.

    The bulk-install heuristic is only applied to the implicit tree,
    matching the previous behaviour. External roots are usually small,
    user-curated trees where every skill is interesting.
    """
    skills, mtimes = _scan_skill_dir(skills_dir, mark_external=False)

    # Detect bulk install timestamps inside the implicit tree only.
    if mtimes:
        counter = Counter(mtimes)
        bulk_timestamps = {t for t, count in counter.items() if count >= 5}
        for skill in skills:
            skill.is_custom = _detect_custom(skill, bulk_timestamps)

    seen_paths: set[str] = {s.path for s in skills}
    for ext_dir in external_dirs:
        ext_skills, _ = _scan_skill_dir(ext_dir, mark_external=True)
        for s in ext_skills:
            if s.path in seen_paths:
                continue
            seen_paths.add(s.path)
            skills.append(s)

    return SkillsState(skills=skills)


def collect_skills(
    hermes_dir: str | None = None,
    external_dirs: Iterable[str] = (),
) -> SkillsState:
    """Collect all skills metadata (cached, invalidates on directory changes).

    Parameters
    ----------
    hermes_dir:
        The Hermes installation root. ``<hermes_dir>/skills`` is scanned
        as the canonical skills tree.
    external_dirs:
        Additional directory paths to scan for ``SKILL.md`` files. Each
        is unioned into the result; skills already discovered under the
        canonical tree win, so an external dir cannot shadow built-ins.
        Sourced from ``ConfigState.external_skill_dirs`` in production
        use; passed explicitly here so tests can drive the loader
        without touching disk.
    """
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    skills_dir = Path(hermes_dir) / "skills"
    ext_paths = [Path(p) for p in external_dirs if p and Path(p).exists()]

    if not skills_dir.exists() and not ext_paths:
        return SkillsState()

    # Cache key + invalidation list both include the external dirs so a
    # config change picks up immediately on the next collect cycle.
    cache_key = "skills:" + hermes_dir + "|" + "|".join(sorted(str(p) for p in ext_paths))
    watched = [p for p in [skills_dir, *ext_paths] if p.exists()]

    if not skills_dir.exists():
        # Synthesise a non-existent base so _do_collect_skills returns []
        # for the implicit tree, then folds in the external dirs.
        empty_dir = Path(hermes_dir) / "skills"
        return get_cached_or_compute(
            cache_key=cache_key,
            compute_fn=lambda: _do_collect_skills(empty_dir, ext_paths),
            dir_paths=watched,
            ttl=60,
        )

    return get_cached_or_compute(
        cache_key=cache_key,
        compute_fn=lambda: _do_collect_skills(skills_dir, ext_paths),
        dir_paths=watched,
        ttl=60,
    )
