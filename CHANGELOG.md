# Changelog

All notable changes to hermes-hudui are documented here.

## [Unreleased]

---

## [0.11.0] — 2026-07-26

### Added
- **Agent compatibility diagnostics** — the Health tab now reports two drift checks: *Agent data layout* (flags pre-0.17 `~/.hermes/` paths the HUD no longer reads, e.g. `memory/` → `memories/`, root `jobs.json` → `cron/jobs.json`) and *Agent schema version* (compares the live `state.db` schema version against the HUD-verified baseline). Both degrade to `ok` when data is absent and only warn on positively-detected drift, turning silent blank tabs into an actionable warning. Verified against **Hermes Agent v0.17.0** (state.db schema v16); baseline lives in `backend/collectors/health.py` (`VERIFIED_AGENT_VERSION`, `TESTED_SCHEMA_VERSIONS`).

### Changed
- **Dependency update triage** — frontend Dependabot groups now combine only compatible minor and patch updates; major upgrades remain separate so ecosystem migrations can be reviewed and tested deliberately.

### Fixed
- **Fresh-install cost dashboard** — the Costs tab now renders a normal zero-usage report when `state.db` or its `sessions` table does not exist yet, and displays an error panel instead of crashing if cost data cannot be loaded.

### Security
- **Local path and process boundaries** — plugin mutations and Replay verification now enforce canonical configured roots, reject traversal and symlink escapes, and bound manifest/replay reads. Plugin installation and cron creation terminate option parsing before user-controlled values.
- **Gateway and profile probes** — gateway action files now use fixed allowlisted names, private no-follow file handling, atomic state writes, and bounded log reads. Local model health probes accept only literal loopback HTTP(S) hosts.
- **Error and integrity hardening** — Replay and gateway endpoints no longer expose unexpected exception details, malformed receipt signatures fail closed, and cache fingerprints use SHA-256.

### Verification
- `pytest` (173 passed)
- `cd frontend && npm run lint` (0 errors)
- `cd frontend && npm run build`
- Browser E2E across all 19 tabs, profile editing, cron creation, and a 390px mobile viewport.

---

## [0.10.0] — 2026-06-27

### Added
- **Replay remote publishing** — sync locally published replays to a static host (GitHub Pages or any git-backed site) from the new Remote Publishing panel. Builds a deployable gallery with relative links: public replays are indexed, unlisted replays live behind unguessable hash paths, and local filesystem paths/manifests are never shipped. Off by default; nothing is uploaded until the user configures a remote and explicitly syncs. Endpoints: `GET/PUT /api/replay/remote`, `POST /api/replay/remote/sync`.
- **Write-path test coverage** — added tests for the memory, profiles, and cron write endpoints, plus version-robust route tests.

### Fixed
- **Chat reasoning truncation** — the chat engine no longer truncates reasoning captured from `state.db` after a turn completes.
- **CI stability** — route tests are now version-robust and the frontend lockfile is kept in sync so CI passes deterministically.

### Changed
- **Repo cleanup** — removed stale docs, version drift, and dead code.

### Verification
- `pytest` (123 passed)
- `cd frontend && npm run build`

---

## [0.9.1] — 2026-06-11

### Fixed
- **Cross-session chat state bugs** — each chat session now owns its own AI SDK Chat instance, so switching sessions mid-stream no longer bleeds the streaming response into the other session's thread, persists it under the wrong localStorage key, or cancels the wrong backend process. Composer state no longer leaks across rapid session switches, and ended sessions can't resurrect deleted history.
- **Tool-calls health diagnostic** — the Health tab checked for a standalone `tool_calls` table, but hermes stores tool calls as a column on `messages`; the diagnostic always reported a false "table missing". It now checks the column (renamed to "tool calls column").
- **Hermes CLI discovery** — `~/.local/bin` and `/usr/local/bin` are appended to PATH at startup so the chat engine finds the hermes CLI when the server is launched from a minimal environment (systemd, cron, launchd).

### Added
- **Streaming session indicators** — sessions in the chat sidebar show a pulsing dot while their response is streaming, including sessions streaming in the background after a switch.
- **Stop backgrounded streams** — the streaming dot doubles as a stop control: hover swaps it to a stop icon, and clicking cancels that session's stream without switching away from the current one.

### Verification
- `pytest` (83 passed)
- `cd frontend && npm run build`
- Browser E2E coverage for mid-stream session switching, per-session localStorage persistence, background-stream indicators, and sidebar stream cancellation.

---

## [0.9.0] — 2026-05-09

### Added
- **Hermes Replay** — new Replay tab turns local Hermes sessions into redacted run receipts with normalized timelines, proof artifacts, redaction review, Safe Share Mode exports, local hashes, Ed25519 signatures, fork JSON, share-card PNGs, static HTML/Markdown/JSON exports, and local public/unlisted publish directories.
- **Replay launch assets** — README now documents local-only export behavior and includes the Replay tab screenshot plus an example redacted replay artifact.
- **Replay verification** — receipt verification now lives inside Replay as a collapsible export check instead of a separate top-level tab.
- **Chat latency diagnostics** — Chat now surfaces process spawn time, first-token latency, total turn time, resume state, and recent averages, with a local benchmark helper for comparing HUD streaming against the raw Hermes CLI.
- **GitHub Actions CI** — pushes and pull requests now run Python tests and the frontend production build.

### Changed
- **Replay layout polish** — the timeline now uses the main detail space beside Replay Runs, while receipt, proof score, redaction, export, share preview, settings, and verification are consolidated in the right column.
- **Replay export actions** — export controls are grouped as Prepare, Export, Share Images, and Publish so the right column is easier to scan.
- **Default theme** — Hermes Teal is now the default first-load theme, and the theme picker is visibly labeled and no longer clipped by the top bar.

### Verification
- `pytest`
- `cd frontend && npm run build`
- Browser E2E coverage for Replay redaction scan, JSON/Markdown/HTML exports, PNG generation, local publish, and receipt verification.

---

## [0.8.0] — 2026-05-05

### Added
- **Dashboard executive summary** — the Dashboard now leads with health, spend pulse, top model, provider/gateway risk, highest-cost session, and action items derived from health, model analytics, gateway, providers, and token-cost data.
- **Plugin Hub** — new dashboard view for installed user/system plugins, dashboard extension manifests, agent plugins, runtime status, auth requirements, and safe plugin actions.
- **Gateway managed-tool visibility** — the Gateway tab now shows routing state for web search, image generation, text-to-speech, and browser automation, including managed gateway access, direct credential fallback, missing config, diagnostics, and safe actions.
- **Model analytics upgrade** — the Model tab now includes rich per-model usage: provider, token split, actual vs estimated cost, API calls, tool calls, last used, average tokens/session, capabilities, sortable columns, and session drilldown.
- **Actionable Health diagnostics** — Health now exposes more specific checks, suggested fixes, and actions, including gateway, model analytics schema, cache, websocket, sudo, provider, and database signals.
- **Health live updates** — Health reacts to websocket `data_changed` events with throttled refresh behavior so the tab updates promptly without excessive CPU churn.
- **Official Hermes Teal theme** — added the canonical Nous Hermes dashboard palette as a selectable theme.
- **Fresh release screenshots** — README assets now show the executive dashboard, managed gateway tools, model analytics, plugin hub, and responsive top bar.

### Changed
- **Dashboard memory narrative** — the previous Status panel copy now lives inside "What I Remember" with compact stats and a stronger visual treatment.
- **Gateway update action hardening** — `Update hermes` now requires a second confirmation click, displays explanatory copy, and surfaces last-run time, log path, log tail, and success/failure exit code.
- **Responsive top navigation** — the tab bar now resizes with the browser, scrolls horizontally when needed, and keeps the active tab in view.
- **README refresh** — updated feature counts, theme list, feature descriptions, and screenshots for the current UI.

### Fixed
- **Session compression visibility** — sessions now surface compression-related metadata again where available.
- **Hermes Teal contrast** — fixed unreadable badge/card text by adding shared theme aliases and tuning the HUD error color for readable contrast on teal panels.
- **Gateway/Health/Model visual regression coverage** — added focused regression tests for dashboard summary aggregation, theme registration/contrast variables, responsive shell structure, and Gateway update confirmation/status behavior.

---

## [0.7.0] — 2026-04-29

### Added
- **Cron job creation UI** — `POST /api/cron` endpoint plus a "Create Job" drawer in the Cron tab. Supports interval presets (30m / 1h / 2h / 24h / custom) or raw cron expressions with a live schedule preview, optional name, prompt, repeat count, delivery target (local / origin / telegram / discord / signal / custom `platform:chat_id`), and an Advanced section for skills, script, and absolute workdir. Validation is mirrored client- and server-side: schedule required, `repeat` must be a positive integer, `workdir` must be absolute, and custom interval values must be non-empty. The hermes CLI is invoked via argv (no shell). E2E coverage in `tests/e2e/cron-create.js`.
- **Profile editing UI** — `GET /api/profiles/options`, `GET /api/profiles/{name}/edit`, and `PUT /api/profiles/{name}/edit` endpoints expose hermes profile config (model, providers, skills, soul, and runtime settings). The Profiles tab now includes an inline editor with atomic, lock-protected writes (`fcntl.flock` + `tempfile.mkstemp` + `os.replace`) matching the rest of the HUD's mutation pattern. E2E coverage in `tests/e2e/profile-edit.js`.

### Fixed
- **Delete-button busy state on the Cron tab** — busy key for `DELETE /api/cron/{id}` was previously `id:null`, so the spinner never matched `isBusy('delete')`. The action key now resolves to `'delete'` and the spinner renders correctly.

### Notes
- Both new mutation endpoints inherit the HUD's localhost-trusted threat model. If you expose hermes-hudui beyond loopback, treat `POST /api/cron` and `PUT /api/profiles/{name}/edit` as RCE-equivalent surfaces (they spawn `hermes` and write profile files respectively).

---

## [0.6.0] — 2026-04-24

### Added
- **Providers tab** — read-only view of connected OAuth and API-key providers from `~/.hermes/auth.json` (Nous, Anthropic, OpenAI Codex, OpenRouter, Z.AI, and any others hermes writes). Shows per-provider status (connected / expiring / expired / missing), masked token preview, expires/obtained relative time, scope, auth mode, and an ACTIVE badge for the currently selected provider.
- **Gateway tab** — live gateway status pulled from `~/.hermes/gateway_state.json` (state, PID with liveness + zombie detection, active agents, per-platform connection state, exit reason) plus two action buttons wired end-to-end: "Restart gateway" shells out to `hermes gateway restart`, "Update hermes" to `hermes update`. Each action spawns detached via `subprocess.Popen`, tees output to `~/.hermes/logs/hud/<action>.log`, and the frontend polls `GET /api/actions/<name>/status` every second, streaming the log tail and final exit code.
- **Model tab** — live capabilities for the current model, derived from `~/.hermes/models_dev_cache.json` + `config.yaml`. Capability badges (Tools / Vision / Reasoning / Structured Output), context window breakdown (auto from models.dev vs config override vs effective), max output tokens, per-1M-token pricing, release date, and knowledge cutoff.

### Changed
- **Sessions panel now shows model names again** — hermes v0.10+ moved the model ID from `model_config` JSON to a dedicated `model` column, so the collector now reads it directly (with a fallback to `model_config` for older DB rows).
- **Chat tool calls and reasoning are captured again** — hermes v0.10+ prints `session_id` to stderr instead of stdout, so the chat engine now drains stderr concurrently via a background thread. Non-session-id stderr lines are surfaced as error output on non-zero exit.
- **`collectors.utils.parse_timestamp`** now handles millisecond-epoch values and strips timezone info so naive-local datetimes compare cleanly against `datetime.now()`. Two collector-local duplicates of that logic have been removed.

### Fixed
- **gpt-5.5 pricing entry** — previously fell back to the $0/$0 "unpriced" default. Now maps to the Codex OAuth tier so session costs render non-zero. Follow-up: the models.dev entry lists $5/$30/1M for gpt-5.5; the HUD pricing table could be re-synced to models.dev as a later pass.

### Notes
- All three new tabs are read/observer-first — no session-token middleware yet. Action endpoints (`POST /api/gateway/restart`, `POST /api/hermes/update`) bind to `127.0.0.1` by default, matching the rest of the HUD's risk model.
- Interactive OAuth flows (PKCE browser redirect, device-code polling) are out of scope for this release and planned for v0.7.

---

## [0.5.1] — 2026-04-24

### Fixed
- **High CPU from file watcher** — watchfiles polled every 300ms over the entire `~/.hermes/` tree, which pegged a core when `state.db` is large and actively written by a running agent. Bumped `poll_delay_ms` to 2000ms (aligned with the 5s broadcast throttle) and excluded `state.db` / `state.db-wal` / `state.db-shm` / `state.db-journal` via a dedicated filter. `force_polling=True` is retained so NFS / WSL1 / VM / Docker-bind-mount setups keep working. Thanks to @louie0609c for the root-cause analysis. Closes #22.
- **Broken `install.sh` version print** — replaced the invalid `node -version` with `node --version` (thanks @CrayonL).

---

## [0.5.0] — 2026-04-17

### Added
- **Sudo tab** — surfaces sudo governance and command history from existing data. Shows approval mode, timeout, command allowlist, and security settings (from `config.yaml`); usage statistics broken down by approved/failed/blocked with a daily sparkline and subcommand type breakdown; scrollable command history extracted from `state.db` tool-output messages via FTS. Closes #14.
- **Regenerate button** — re-run the last message in chat using the AI SDK's regenerate helper; button appears after each completed assistant response.
- **Vercel AI SDK Data Stream Protocol** — replaced the custom SSE chat implementation with the AI SDK's data stream protocol for more robust streaming and future-proofing.

### Fixed
- **WebSocket / StaticFiles mount crash** — WebSocket upgrade scopes no longer fall through to the `StaticFiles` catch-all, preventing a startup crash on certain deployment configurations.
- **Vite dev proxy for `/ws`** — WebSocket connections are now correctly proxied through the Vite dev server to the backend (`:3001`), so live-reload and HUD updates work in dev mode.
- **macOS MallocStackLogging warning** — suppressed the noisy `MallocStackLogging` warning emitted on macOS when spawning subprocesses. Closes #15.
- **zsh extras install hint** — `[tui]` and `[chat]` extras are now quoted in install instructions and error messages to prevent zsh glob expansion.
- **ChatNotAvailableError message** — tightened to a single clear line.

### Performance
- **Chat streaming** — switched to `read1()` for chunked reads and tightened the frontend render throttle, reducing perceived latency on long responses.

---

## [0.4.0] — 2026-04-14

### Added
- **i18n — English + Chinese language support** — every UI string across all 13 tabs is translated. A language toggle button in the header bar switches instantly; choice persists to localStorage.
- **Chat responds in selected language** — when the UI is set to Chinese, chat messages include a language hint so the agent responds in Chinese.
- **Language toggle** — bordered button after the clock in the header, always visible regardless of tab overflow.

### Changed
- Default host binding changed from `0.0.0.0` to `127.0.0.1` for security (contributed by @shivanraptor).

---

## [0.3.1] — 2026-04-12

### Added
- **Chat history persistence** — messages and sessions survive page refresh via localStorage. On server restart, backend sessions are re-created and message history migrated automatically.

### Fixed
- **Corrections tab — session corrections were always empty** — a dead REGEXP loop in the collector fired a `cursor.execute()` that SQLite can't handle (no built-in REGEXP support), throwing an `OperationalError` that silently aborted the function before the LIKE-based queries could run. Fixed by removing the dead loop, collapsing the 8 individual LIKE queries into one OR query, and moving `conn.close()` into a `finally` block.

---

## [0.3.0] — 2026-04-12

### Added
- **Tool call visibility** — chat responses now show tool call cards (web_search, terminal, etc.) with arguments after the response finishes
- **Reasoning display** — agent thinking/reasoning blocks appear as collapsible "Thinking" sections in chat
- **Memory editing** — inline edit, delete, and add entries directly in the Memory tab (both Agent Memory and User Profile)
- **Session transcript viewer** — click any session in the Sessions tab to read the full conversation in a modal with markdown rendering and per-message token counts
- **Session search** — search bar searches session titles and full message content (FTS), results show match type and a content snippet

### Fixed
- HUD-generated chat sessions (`--source tool`) no longer appear in the Sessions tab or search results

---

## [0.2.0] — Chat + New Tabs

### Added
- **Chat tab** — Live chat with your Hermes agent
  - Multiple sessions, each with independent message history
  - Responses stream in real time (SSE)
  - Markdown rendering — headers, lists, tables, code blocks
  - Syntax-highlighted code with a copy button on hover
  - Stop button cancels a response mid-stream
  - Tool call cards and reasoning display (when agent uses tools)
- **Corrections tab** — View corrections grouped by severity (critical / major / minor)
- **Patterns tab** — Task clusters, hourly activity heatmap, repeated prompts

### Fixed
- Chat system warnings (context compression notices) no longer appear in responses
- Chat sessions are fully independent — switching sessions no longer shows the same messages
- Chat output preserves formatting and line breaks

---

## [0.1.0] — Initial Release

### Added
- **Dashboard** — Identity, stats, memory bars, service health, skills, projects, cron jobs, tool usage, daily sparkline
- **Memory** — Agent memory and user profile with capacity bars
- **Skills** — Category chart, skill details, custom skill badges
- **Sessions** — Session history with message/token counts and sparklines
- **Cron** — Scheduled jobs with schedule, status, and prompt preview
- **Projects** — Repos grouped by activity, branch info, language detection
- **Health** — API key status, service health with PIDs
- **Agents** — Live processes, operator alerts, recent session history
- **Profiles** — Full profile cards with model, provider, soul summary, toolsets
- **Costs** — Per-model USD estimates, daily trend, token breakdown
- **Real-time updates** — WebSocket broadcasts changes instantly, no manual refresh
- **Smart caching** — Automatic cache invalidation when agent files change
- **Four themes** — Neural Awakening, Blade Runner, fsociety, Anime
- **CRT scanlines** — Optional overlay
- **Command palette** — `Ctrl+K` to jump anywhere
- **Boot screen** — One-time animated startup sequence
- **Keyboard shortcuts** — `1`–`9`, `0` for tabs; `t` for themes
