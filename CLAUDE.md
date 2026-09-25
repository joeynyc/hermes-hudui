# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Hermes HUD Web UI — a browser-based dashboard for monitoring the Hermes AI agent. It reads agent data from `~/.hermes/` and displays identity, memory, skills, sessions, cron jobs, projects, costs, activity patterns, corrections, sudo governance, live chat, OAuth providers, gateway control, and live model capabilities across 19 tabs.

## Commands

### Development Setup (one-time)
```bash
./install.sh        # Builds frontend, installs Python package
```

### Full-Stack Dev
```bash
hermes-hudui --dev          # Terminal 1: backend on :3001 (auto-reload)
cd frontend && npm run dev  # Terminal 2: frontend on :5173 (proxies /api → :3001)
```

### Frontend
```bash
cd frontend
npm run dev      # Dev server on :5173
npm run build    # Production build (runs tsc first)
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Backend CLI
```bash
hermes-hudui                         # Serve on :3001
hermes-hudui --port 8080             # Custom port
hermes-hudui --hermes-dir /path      # Override ~/.hermes/ location
```

### Release Workflow
```bash
# 1. Bump version in: pyproject.toml, App.tsx, BootScreen.tsx, CHANGELOG.md
# 2. Build + deploy static assets:
cd frontend && npm run build && cd ..
rm -rf backend/static/assets/* && cp -r frontend/dist/* backend/static/
# 3. Commit, tag, push:
git add -f backend/static/assets/ && git commit && git tag v0.X.Y && git push --tags
# 4. GitHub release:
gh release create v0.X.Y --title "v0.X.Y" --notes "..."
```

## Architecture

```
React Frontend (Vite + Tailwind)
    ↓ /api/* (proxied in dev)
FastAPI Backend (Python)
    ↓ collectors/*.py        ↓ chat/engine.py
~/.hermes/ (agent data)     hermes CLI (subprocess)
```

### Backend (`backend/`)

- **`main.py`** — FastAPI app + CLI entry point. Sets `HERMES_HOME`, starts Uvicorn.
- **`collectors/`** — One module per data domain (memory, skills, sessions, cron, projects, patterns, sudo). Each reads `~/.hermes/` and returns dataclasses from `collectors/models.py`.
- **`collectors/models.py`** — All dataclasses (`HUDState`, `MemoryState`, `SkillsState`, etc.). `@property` fields are included in serialization.
- **`models/replay.py`** — Replay dataclasses (`ReplayRun`, `ReplayEvent`, `RunReceipt`, …), kept out of `collectors/models.py` because Replay owns its own schema.
- **`services/`** — Replay pipeline: `replay_normalizer.py`, `replay_redactor.py`, `replay_exporter.py`, `replay_signer.py`, `replay_verifier.py`, `replay_publisher.py`.
- **`api/serialize.py`** — `to_dict()` recursively converts dataclasses to JSON-safe dicts.
- **`api/`** — FastAPI route handlers that call collectors and return serialized data. One module per tab/domain.
- **`api/memory.py`** — CRUD endpoints for memory editing. Uses `fcntl.flock` + atomic writes (`tempfile.mkstemp` → `os.replace`) matching hermes-agent's `MemoryStore` locking pattern.
- **`api/sessions.py`** — Session search (title + FTS). Filters `source != 'tool'` to exclude HUD-generated sessions.
- **`api/chat.py`** — Chat session CRUD, SSE streaming endpoint, cancel endpoint.
- **`chat/engine.py`** — Singleton `ChatEngine` spawning `hermes chat -q <msg> -Q --source tool` per message. Captures `hermes_session_id` from stdout, queries `state.db` post-completion for tool calls and reasoning.
- **`chat/streamer.py`** — SSE event emitter (`emit_token`, `emit_tool_start`, `emit_tool_end`, `emit_reasoning`, `emit_done`).
- **`cache.py`** — Mtime-based cache invalidation (sessions 30s, skills 60s, patterns 60s, profiles 45s). Exposed by `api/cache.py` as `GET /api/cache/stats`, `POST /api/cache/clear`.
- **`file_watcher.py`** — Watches `~/.hermes/` via `watchfiles` and maps changed paths to data types.
- **`websocket_manager.py`** — Broadcasts `data_changed` events to connected clients. Frontend auto-refreshes via SWR mutation.

### Frontend (`frontend/src/`)

- **`App.tsx`** — Root: tab manager, theme provider, command palette. Chat tab uses fixed-height container; other tabs scroll normally.
- **`hooks/useApi.ts`** — SWR wrapper with auto-refresh, 5s dedup, 3 retries.
- **`hooks/useChat.ts`** — Chat state: SSE streaming, session CRUD, per-session message cache (in-memory `Map` + localStorage persistence). Restores messages on session switch and page refresh.
- **`components/Panel.tsx`** — Shared panel wrapper (title, border, glow). Exports `CapacityBar`, `Sparkline`. `noPadding` prop for ChatPanel.
- **`components/chat/`** — `SessionSidebar`, `MessageThread`, `MessageBubble`, `Composer`, `ToolCallCard`, `ReasoningBlock`.
- **`components/MemoryPanel.tsx`** — Inline editing with hover-reveal controls, two-click delete, expandable add form.
- **`lib/utils.ts`** — `timeAgo()`, `formatDur()`, `formatTokens()`, `formatSize()`, `truncate()`.

## Key Conventions

**Adding a tab:** Create collector in `backend/collectors/`, dataclass in `backend/collectors/models.py`, route module in `backend/api/` (register its router in `main.py`), panel component with `useApi`, register in `TopBar.tsx` TABS + `App.tsx` TabContent/GRID_CLASS.

**Chat engine:** Stateless per-message subprocess. No backend message persistence — history lives in localStorage. On server restart, ChatPanel re-creates backend sessions and migrates localStorage keys to new IDs.

**Memory editing:** Sync `def` endpoints (not `async`) so FastAPI auto-threads blocking I/O. File locking via `fcntl.flock` on `.lock` files. Atomic writes via `tempfile.mkstemp` + `os.replace`. Entries delimited by `\n§\n`.

**Styling:** Tailwind for layout, CSS variables (`var(--hud-*)`) for theming. Funnel Sans font. Five themes: `ai`, `hermes-official`, `blade-runner`, `fsociety`, `anime`.

**TypeScript:** Use `any` for API response types — schema owned by backend. `@typescript-eslint/no-explicit-any` is turned off in `frontend/eslint.config.js` for exactly this reason; don't re-enable it without typing the API surface first.

**Linting:** `cd frontend && npm run lint` must exit clean (0 errors). Remaining `react-refresh/only-export-components` and `react-hooks/exhaustive-deps` findings are warnings by design. CI runs lint on every PR — run it before committing frontend changes.

**Version strings:** Must stay in sync across `pyproject.toml`, `App.tsx` status bar, `BootScreen.tsx`, and `CHANGELOG.md`.

**Token costs:** Hardcoded `MODEL_PRICING` in `backend/api/token_costs.py`. Unknown models fall back to `DEFAULT_PRICING` (`_FREE`) and are labelled `unpriced (<model>)` — they report **$0**, not an approximation. Adding a model means adding an entry; `test_current_anthropic_models_are_all_priced` guards against new models silently reading as free.

**Sudo collector:** `backend/collectors/sudo.py` mines `state.db` tool-output messages via FTS for sudo command executions, parses `config.yaml` for approval/security settings, and tails `logs/gateway.log` for explicitly approved commands. Outcome classification: `exit_code=-1` + "approval" in error = blocked; password error in output = failed; `exit_code=0` = success.

**Shared YAML loader:** `backend/collectors/utils.py` exports `load_yaml(text)` — tries `yaml.safe_load`, falls back to a minimal line parser. Used by `config.py` and `sudo.py`.
