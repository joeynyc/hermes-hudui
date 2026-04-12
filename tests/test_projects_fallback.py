from __future__ import annotations

from pathlib import Path

from backend.collectors.projects import collect_projects


def _make_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / '.git').mkdir(exist_ok=True)
    (path / 'README.md').write_text('# demo\n', encoding='utf-8')


def test_collect_projects_falls_back_to_home_git_scan_when_projects_dir_missing(tmp_path: Path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()

    _make_git_repo(home / 'artplex-uiux-1')
    _make_git_repo(home / 'Hermes' / 'hermes-agent')

    monkeypatch.setenv('HOME', str(home))
    monkeypatch.delenv('HERMES_HUD_PROJECTS_DIR', raising=False)

    state = collect_projects(None)

    names = {project.name for project in state.projects}
    paths = {project.path for project in state.projects}

    assert 'artplex-uiux-1' in names
    assert 'hermes-agent' in names
    assert any(path.endswith('/artplex-uiux-1') for path in paths)
    assert any(path.endswith('/Hermes/hermes-agent') for path in paths)
    assert state.git_repos >= 2
