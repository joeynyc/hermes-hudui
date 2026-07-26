# Hermes HUD — Roadmap

A record of everything built, day by day.

---

## Foundation (Pre-Day 1)

The initial release established the core architecture: a FastAPI backend reading `~/.hermes/` and a React + Vite + Tailwind frontend. No framework dependencies on hermes-agent internals — the HUD vendors its own collectors.

**What shipped:**
- Dashboard with identity, memory bars, service health, skills, projects, cron jobs, tool usage, daily sparkline
- 11 read-only tabs — Memory, Skills, Sessions, Cron, Projects, Health, Agents, Profiles, Costs, Corrections, Patterns
- WebSocket real-time updates — `watchfiles` watches `~/.hermes/` and broadcasts `data_changed` to all clients
- Smart mtime-based caching — avoids re-reading files that haven't changed
- Four themes — Neural Awakening, Blade Runner, fsociety, Anime
- CRT scanline overlay
- Command palette (`Ctrl+K`)
- Boot screen animation
- Keyboard shortcuts (`1`–`0` tabs, `t` theme cycle)

---

## Day 1 — Chat + Corrections + Patterns

Wired up the chat engine and surfaced two previously hidden tabs.

**What shipped:**
- Live chat with Hermes agent via `hermes chat -q <msg> -Q --source tool` subprocess
- Multiple independent sessions, each with isolated message history
- SSE streaming — responses appear in real time
- Corrections tab — corrections grouped by severity (critical / major / minor)
- Patterns tab — task clusters, hourly activity heatmap, repeated prompts
- CLI decoration filtering — box-drawing characters and system headers stripped from chat output
- HUD-generated sessions tagged `--source tool` so they stay out of the Sessions tab

---

## Day 2 — Chat Polish

Made chat output readable and interactive.

**What shipped:**
- Markdown rendering — headers, lists, tables, code blocks
- Syntax-highlighted code with hover copy button
- Stop button — cancels a response mid-stream by killing the subprocess
- Multi-line warning block filtering — context compression notices and other `⚠` warnings no longer bleed into responses
- Fixed chat session isolation — switching sessions no longer shows the wrong history

---

## Day 3 — Session Transcript Viewer + Search

Made the Sessions tab useful beyond a list.

**What shipped:**
- Session transcript modal — click any session to read the full conversation with markdown rendering and per-message token counts
- Session search — searches titles and full message content via FTS, results show match type and a content snippet
- HUD-generated sessions filtered from search results

---

## Day 4 — Tool Calls + Reasoning in Chat

Surfaced what the agent is actually doing while it thinks.

**What shipped:**
- Tool call cards — after a response finishes, cards show each tool used (web_search, terminal, etc.) with arguments and status
- Reasoning blocks — agent thinking/extended reasoning appears as a collapsible "Thinking" section
- Tool call data read from `state.db` post-completion using the hermes session ID captured from stdout

---

## Day 5 — Memory Editing

Added the first write capability — the HUD was previously read-only.

- Inline edit and delete entries in the Memory tab (Agent Memory and User Profile)
- Add new entries via expandable form
- Two-click delete confirmation
- File locking (`fcntl.flock`) + atomic writes (`tempfile.mkstemp` → `os.replace`) matching hermes-agent's own locking pattern
- No direct JSON writes — entries use hermes's `\n§\n` delimiter format

---

## Day 6 — Chat History Persistence + Bug Fixes + Speed

### Chat History Persistence
- Messages and sessions survive page refresh via localStorage
- In-memory Map as L1 cache, localStorage as L2 — debounced writes (1s) to avoid thrashing during streaming
- On server restart: ChatPanel detects missing backend sessions, re-creates them, migrates message keys from old to new IDs automatically

### Streaming Bug Fixes
- Fixed stuck streaming — warning block filter was swallowing the first response line (hermes outputs content immediately after the warning with no blank line separator)
- Fixed stale closure in SSE `onerror` handler — `isStreaming` captured at creation time meant cleanup never ran
- Heartbeat SSE comment every 15s keeps connections alive through proxies

### Speed Optimization
- Switched token emission from char-by-char to line-level — reduces SSE events from ~500 to ~20 per response, noticeably faster rendering

---

## Day 7 — Cron Job Management

Made the Cron tab interactive — jobs can now be controlled without touching the CLI or editing files by hand.

- **Pause** — suspends a scheduled job
- **Resume** — re-activates a paused job and recomputes the next run time
- **Run Now** — triggers immediate execution on the next scheduler tick
- **Delete** — removes the job permanently (two-click confirmation)
- Buttons adapt to job state: Pause/Resume toggle, Run hidden for completed/paused jobs
- Delegated to `hermes cron pause|resume|remove|run <job_id>` CLI — avoids racing with the scheduler's own file writes (hermes's `save_jobs()` has no file locking)
- End-to-end tested via Playwright against live jobs

---

## Day 8 — Sudo Tab

Surfaced sudo governance and command history, closing a community request (#14).

**What shipped:**
- **Sudo tab** (14th tab) — three panels: Configuration, Usage Statistics, Command History
- Configuration panel shows approval mode, timeout, command allowlist, and security flags (redact secrets, Tirith scanner) read from `config.yaml`
- Statistics panel shows total commands broken down by approved / failed / blocked, a daily sparkline, and top subcommand types (`systemctl`, `apt`, etc.)
- Command history panel mines `state.db` tool-output messages via FTS — extracts the sudo command text, classifies outcome from `exit_code` and error patterns, links each entry to its session
- Gateway log tailing supplements DB data with explicitly approved commands
- Shared `load_yaml()` utility extracted to `collectors/utils.py`, eliminating duplicate YAML parsing across `config.py` and `sudo.py`

---

## Day 9 — Chat Overhaul + Fixes

Replaced the custom SSE stack with the Vercel AI SDK, added regenerate, and squashed several platform-specific bugs.

**What shipped:**
- **Vercel AI SDK Data Stream Protocol** — replaced the hand-rolled SSE chat implementation with the AI SDK's data stream protocol; more robust streaming, better error recovery, and a foundation for future AI SDK features
- **Regenerate button** — re-runs the last user message; button appears after each completed assistant response using the AI SDK's regenerate helper
- **Chunked streaming perf** — switched backend to `read1()` for chunked reads and tightened the frontend render throttle, reducing perceived latency on long responses
- **macOS MallocStackLogging fix** — suppressed the noisy warning emitted when spawning subprocesses on macOS (#15)
- **Vite dev WebSocket proxy** — `/ws` now proxies correctly through the Vite dev server to the backend, restoring live HUD updates in dev mode
- **WebSocket / StaticFiles crash fix** — WebSocket upgrade scopes no longer fall through to the `StaticFiles` catch-all
- **zsh extras quoting** — `[tui]` and `[chat]` extras are now quoted in install hints and error messages to prevent zsh glob expansion (#10, #18)

---

## What's Next (Ideas)

These are possibilities, not commitments.

- **Memory search** — filter/search across memory entries in the HUD
- **Live token counter** — show context usage in real time during streaming
- **Mobile layout** — responsive polish for small screens
- **Dark/light mode** — fifth theme option using system preference
- **Multi-agent** — support for switching between multiple hermes profiles in the chat tab
