"""Collect project data from ~/projects/."""

from __future__ import annotations

import os

from .utils import default_projects_dir
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ProjectInfo:
    name: str
    path: str
    is_git: bool = False
    branch: Optional[str] = None
    last_commit_msg: Optional[str] = None
    last_commit_ago: Optional[str] = None
    last_commit_ts: Optional[float] = None
    dirty_files: int = 0
    total_commits: int = 0
    last_modified: Optional[datetime] = None
    has_readme: bool = False
    has_package_json: bool = False
    has_requirements: bool = False
    has_pyproject: bool = False
    languages: list[str] = field(default_factory=list)

    @property
    def status_label(self) -> str:
        if not self.is_git:
            return "no git"
        if self.dirty_files > 0:
            return f"{self.dirty_files} dirty"
        return "clean"

    @property
    def activity_level(self) -> str:
        """Rough activity bucket based on last commit time."""
        if not self.last_commit_ago:
            return "unknown"
        ago = self.last_commit_ago.lower()
        if any(x in ago for x in ["minute", "hour", "second"]):
            return "active"
        if "day" in ago:
            # Extract number
            try:
                days = int(ago.split()[0])
                if days <= 3:
                    return "active"
                elif days <= 14:
                    return "recent"
            except (ValueError, IndexError):
                pass
            return "recent"
        if "week" in ago:
            try:
                weeks = int(ago.split()[0])
                if weeks <= 2:
                    return "recent"
            except (ValueError, IndexError):
                pass
            return "stale"
        if any(x in ago for x in ["month", "year"]):
            return "stale"
        return "unknown"


@dataclass
class ProjectsState:
    projects: list[ProjectInfo] = field(default_factory=list)
    projects_dir: str = ""

    @property
    def total(self) -> int:
        return len(self.projects)

    @property
    def git_repos(self) -> int:
        return sum(1 for p in self.projects if p.is_git)

    @property
    def active_count(self) -> int:
        return sum(1 for p in self.projects if p.activity_level == "active")

    @property
    def dirty_count(self) -> int:
        return sum(1 for p in self.projects if p.dirty_files > 0)

    def by_activity(self) -> dict[str, list[ProjectInfo]]:
        groups: dict[str, list[ProjectInfo]] = {}
        for p in self.projects:
            level = p.activity_level if p.is_git else "no git"
            groups.setdefault(level, []).append(p)
        return groups

    def sorted_by_recent(self) -> list[ProjectInfo]:
        """Sort projects by activity: active first, then recent, then stale."""
        order = {"active": 0, "recent": 1, "stale": 2, "unknown": 3, "no git": 4}
        return sorted(self.projects, key=lambda p: (
            order.get(p.activity_level if p.is_git else "no git", 5),
            -(p.last_commit_ts or 0),
        ))


def _run_git(repo_path: str, args: list[str]) -> str:
    """Run a git command in a repo, return stdout or empty string."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path] + args,
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _detect_languages(path: Path) -> list[str]:
    """Quick heuristic language detection from file extensions."""
    langs = set()
    ext_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React", ".tsx": "React/TS", ".rs": "Rust",
        ".go": "Go", ".java": "Java", ".cpp": "C++", ".c": "C",
        ".rb": "Ruby", ".sh": "Shell", ".html": "HTML", ".css": "CSS",
        ".vue": "Vue", ".svelte": "Svelte",
    }

    try:
        for item in path.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                if ext in ext_map:
                    langs.add(ext_map[ext])
            elif item.is_dir() and item.name == "src":
                # Check src/ one level deep
                for sub in item.iterdir():
                    if sub.is_file():
                        ext = sub.suffix.lower()
                        if ext in ext_map:
                            langs.add(ext_map[ext])
    except PermissionError:
        pass

    return sorted(langs)[:5]  # Cap at 5


def _build_project_info(item: Path) -> ProjectInfo:
    is_git = (item / '.git').is_dir()
    proj = ProjectInfo(
        name=item.name,
        path=str(item),
        is_git=is_git,
        has_readme=(item / 'README.md').exists() or (item / 'readme.md').exists(),
        has_package_json=(item / 'package.json').exists(),
        has_requirements=(item / 'requirements.txt').exists(),
        has_pyproject=(item / 'pyproject.toml').exists(),
        languages=_detect_languages(item),
    )

    try:
        proj.last_modified = datetime.fromtimestamp(item.stat().st_mtime)
    except OSError:
        pass

    if is_git:
        proj.branch = _run_git(str(item), ['branch', '--show-current']) or 'HEAD'

        log_output = _run_git(str(item), ['log', '-1', '--format=%ar|%s|%ct'])
        if log_output and '|' in log_output:
            parts = log_output.split('|', 2)
            proj.last_commit_ago = parts[0]
            proj.last_commit_msg = parts[1] if len(parts) > 1 else None
            try:
                proj.last_commit_ts = float(parts[2]) if len(parts) > 2 else None
            except ValueError:
                pass

        status = _run_git(str(item), ['status', '--porcelain'])
        proj.dirty_files = len([l for l in status.split('\n') if l.strip()]) if status else 0

        count = _run_git(str(item), ['rev-list', '--count', 'HEAD'])
        try:
            proj.total_commits = int(count)
        except ValueError:
            pass

    return proj


def _discover_git_repos_fallback(home: Path) -> list[Path]:
    repos: list[Path] = []
    seen: set[Path] = set()
    skip_names = {'Library', 'Applications', 'Movies', 'Music', 'Pictures', 'Public', 'Downloads', '.Trash'}

    def maybe_add(repo_path: Path) -> None:
        repo_path = repo_path.resolve()
        if repo_path in seen:
            return
        if not (repo_path / '.git').is_dir():
            return
        seen.add(repo_path)
        repos.append(repo_path)

    try:
        for child in home.iterdir():
            if not child.is_dir() or child.name.startswith('.') or child.name in skip_names:
                continue
            maybe_add(child)
            try:
                for grandchild in child.iterdir():
                    if not grandchild.is_dir() or grandchild.name.startswith('.'):
                        continue
                    maybe_add(grandchild)
            except PermissionError:
                continue
    except PermissionError:
        return []

    return sorted(repos)


def collect_projects(projects_dir: str | None = None) -> ProjectsState:
    """Collect project data from the projects directory or a home-directory git fallback."""
    if projects_dir is None:
        projects_dir = default_projects_dir(projects_dir)

    projects_path = Path(projects_dir)
    project_dirs: list[Path] = []
    projects_dir_label = projects_dir

    if projects_path.exists():
        for item in sorted(projects_path.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith('.'):
                continue
            project_dirs.append(item)
    else:
        home = Path(os.path.expanduser('~'))
        project_dirs = _discover_git_repos_fallback(home)
        projects_dir_label = f"{home} (fallback scan)"

    projects = [_build_project_info(item) for item in project_dirs]
    return ProjectsState(projects=projects, projects_dir=projects_dir_label)
