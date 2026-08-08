"""Smoke tests for the CC Cost tab registration in the frontend shell."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cc_costs_tab_is_registered_in_top_bar() -> None:
    top_bar = (ROOT / "frontend/src/components/TopBar.tsx").read_text()
    assert "'cc-costs'" in top_bar
    assert "'tab.cc-costs'" in top_bar


def test_cc_costs_panel_is_lazy_imported_in_app() -> None:
    app = (ROOT / "frontend/src/App.tsx").read_text()
    assert "CCCostsPanel" in app
    assert "lazy(() => import('./components/CCCostsPanel'))" in app


def test_cc_costs_has_grid_layout_in_app() -> None:
    app = (ROOT / "frontend/src/App.tsx").read_text()
    assert "'cc-costs':" in app


def test_cc_costs_has_translations() -> None:
    t = (ROOT / "frontend/src/i18n/translations.ts").read_text()
    assert "'tab.cc-costs':" in t
    assert "'cc.title':" in t
    assert "'cc.today':" in t
    assert "'cc.total':" in t
    # Chinese translations
    assert "'CC成本'" in t
    assert "'CC今日'" in t


def test_cc_costs_panel_component_exists() -> None:
    panel = ROOT / "frontend/src/components/CCCostsPanel.tsx"
    assert panel.exists()
    content = panel.read_text()
    assert "export default function CCCostsPanel" in content
    assert "useApi('/cc-costs'" in content


def test_cc_costs_route_is_registered_in_backend() -> None:
    main_py = (ROOT / "backend/main.py").read_text()
    assert "cc_costs" in main_py
    assert 'cc_costs.router' in main_py
