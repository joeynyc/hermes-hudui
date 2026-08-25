"""Collect Hermes projects from projects.db, with a ~/projects/ fallback."""

from __future__ import annotations

import sqlite3

from .utils import default_hermes_dir, default_projects_dir
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
    slug: Optional[str] = None
    description: Optional[str] = None
    board_slug: Optional[str] = None
    folder_count: int = 0
    source: str = "folder"
    archived: bool = False

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


def _enrich_git(proj: ProjectInfo, item: Path) -> None:
    """Fill git + language badges for a folder that exists on disk."""
    proj.has_readme = (item / "README.md").exists() or (item / "readme.md").exists()
    proj.has_package_json = (item / "package.json").exists()
    proj.has_requirements = (item / "requirements.txt").exists()
    proj.has_pyproject = (item / "pyproject.toml").exists()
    proj.languages = _detect_languages(item)
    try:
        proj.last_modified = datetime.fromtimestamp(item.stat().st_mtime)
    except OSError:
        pass
    proj.is_git = (item / ".git").is_dir() or (item / ".git").is_file()
    if not proj.is_git:
        return
    proj.branch = _run_git(str(item), ["branch", "--show-current"]) or "HEAD"
    log_output = _run_git(str(item), ["log", "-1", "--format=%ar|%s|%ct"])
    if log_output and "|" in log_output:
        parts = log_output.split("|", 2)
        proj.last_commit_ago = parts[0]
        proj.last_commit_msg = parts[1] if len(parts) > 1 else None
        try:
            proj.last_commit_ts = float(parts[2]) if len(parts) > 2 else None
        except ValueError:
            pass
    status = _run_git(str(item), ["status", "--porcelain"])
    proj.dirty_files = len([line for line in status.split("\n") if line.strip()]) if status else 0
    count = _run_git(str(item), ["rev-list", "--count", "HEAD"])
    try:
        proj.total_commits = int(count)
    except ValueError:
        pass


def _collect_agent_projects(hermes_dir: str) -> list[ProjectInfo]:
    db_path = Path(hermes_dir) / "projects.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = list(conn.execute(
            """SELECT id, slug, name, description, board_slug, primary_path,
                      created_at, archived
               FROM projects
               WHERE COALESCE(archived, 0) = 0
               ORDER BY name"""
        ))
        folders: dict[str, list[str]] = {}
        try:
            for folder in conn.execute(
                "SELECT project_id, path, is_primary FROM project_folders"
            ):
                folders.setdefault(str(folder["project_id"]), []).append(
                    str(folder["path"])
                )
        except sqlite3.Error:
            pass
        conn.close()
    except sqlite3.Error:
        return []

    projects: list[ProjectInfo] = []
    for row in rows:
        paths = folders.get(str(row["id"]), [])
        primary = row["primary_path"] or (paths[0] if paths else "")
        proj = ProjectInfo(
            name=row["name"] or row["slug"] or "unnamed",
            path=str(primary or ""),
            slug=row["slug"],
            description=row["description"],
            board_slug=row["board_slug"],
            folder_count=len(paths) or (1 if primary else 0),
            source="agent",
            archived=bool(row["archived"]),
        )
        if primary and Path(primary).exists():
            _enrich_git(proj, Path(primary))
        elif row["created_at"]:
            try:
                proj.last_modified = datetime.fromtimestamp(float(row["created_at"]))
            except (TypeError, ValueError, OSError):
                pass
        projects.append(proj)
    return projects


def collect_projects(
    projects_dir: str | None = None,
    hermes_dir: str | None = None,
) -> ProjectsState:
    """Collect Agent projects.db first, then fall back to ~/projects/."""
    if projects_dir is None:
        projects_dir = default_projects_dir(projects_dir)

    agent_projects = _collect_agent_projects(default_hermes_dir(hermes_dir))
    if agent_projects:
        return ProjectsState(projects=agent_projects, projects_dir=projects_dir)

    projects_path = Path(projects_dir)
    if not projects_path.exists():
        return ProjectsState(projects_dir=projects_dir)

    projects: list[ProjectInfo] = []

    for item in sorted(projects_path.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue

        proj = ProjectInfo(name=item.name, path=str(item), source="folder")
        _enrich_git(proj, item)
        projects.append(proj)

    return ProjectsState(projects=projects, projects_dir=projects_dir)
