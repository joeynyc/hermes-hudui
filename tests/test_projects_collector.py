import sqlite3
from pathlib import Path

from backend.collectors.projects import collect_projects


def test_collect_projects_prefers_agent_db(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "projects.db")
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            board_slug TEXT,
            primary_path TEXT,
            created_at INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE project_folders (
            project_id TEXT NOT NULL,
            path TEXT NOT NULL,
            label TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0,
            added_at INTEGER NOT NULL,
            PRIMARY KEY (project_id, path)
        );
        """
    )
    conn.execute(
        """INSERT INTO projects
           (id, slug, name, description, board_slug, primary_path, created_at, archived)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("p_1", "hud", "Hermes HUD", "operator monitor", "ops", "/tmp/hud", 1_700_000_000, 0),
    )
    conn.execute(
        "INSERT INTO project_folders VALUES (?, ?, ?, ?, ?)",
        ("p_1", "/tmp/hud", "app", 1, 1_700_000_000),
    )
    conn.execute(
        """INSERT INTO projects
           (id, slug, name, description, board_slug, primary_path, created_at, archived)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("p_old", "archived", "Old", None, None, None, 1, 1),
    )
    conn.commit()
    conn.close()

    folders = tmp_path / "projects"
    folders.mkdir()
    (folders / "ignored-folder").mkdir()

    state = collect_projects(projects_dir=str(folders), hermes_dir=str(tmp_path))
    assert [p.name for p in state.projects] == ["Hermes HUD"]
    project = state.projects[0]
    assert project.slug == "hud"
    assert project.source == "agent"
    assert project.board_slug == "ops"
    assert project.folder_count == 1
    assert project.description == "operator monitor"


def test_collect_projects_falls_back_to_folder_scan(tmp_path: Path) -> None:
    folders = tmp_path / "projects"
    folders.mkdir()
    (folders / "alpha").mkdir()
    (folders / "alpha" / "README.md").write_text("hi")

    state = collect_projects(projects_dir=str(folders), hermes_dir=str(tmp_path))
    assert [p.name for p in state.projects] == ["alpha"]
    assert state.projects[0].source == "folder"
    assert state.projects[0].has_readme is True
