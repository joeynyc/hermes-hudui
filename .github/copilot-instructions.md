# CLAUDE.md

## What This Is

Hermes HUD Web UI — the browser version of hermes-hud (TUI consciousness monitor). FastAPI backend + React frontend. Reads from `~/.hermes/` to display agent state.

## Running

```bash
# Full stack (production)
./install.sh && hermes-hudui

# Development
hermes-hudui --dev              # backend with auto-reload on :3001
cd frontend && npm run dev      # frontend dev server on :5173
```

Requires Python 3.11+ and Node 22.12+. The backend vendors its own collectors.

## Architecture

```
backend/main.py         FastAPI app, local-origin boundary, static files
backend/api/*.py        One route file per data domain
backend/api/serialize.py  Dataclass → JSON conversion
backend/static/         Built frontend (copied from frontend/dist)
frontend/src/           React + Vite + TypeScript + Tailwind
frontend/src/hooks/     Theme system (useTheme), SWR fetching (useApi)
frontend/src/components/ One panel component per tab/data source
frontend/src/index.css  Theme CSS variables, panel system, effects
```

**Data flow:** backend collectors → FastAPI endpoints → SWR fetch → React panels

## Key Patterns

- Backend owns collectors under `backend/collectors/`
- 6 themes as CSS custom properties on `[data-theme]` attribute
- Panel component with title-in-border pattern
- SWR for data fetching with configurable refresh intervals
- Keyboard shortcuts (1-9 tabs, t theme, r refresh)

## API Endpoints

All under `/api/`:
state, memory, sessions, skills, cron, projects, health, profiles, patterns, corrections, agents, timeline
