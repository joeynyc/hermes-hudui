# ☤ Hermes HUD — Web UI

A browser-based consciousness monitor for [Hermes](https://github.com/nousresearch/hermes-agent), the AI agent with persistent memory.

Same data, same soul, same dashboard that made the [TUI version](https://github.com/joeynyc/hermes-hud) popular — now in your browser.

![Executive Dashboard](assets/dashboard-executive.png)

![Gateway Managed Tools](assets/gateway-tools.png)

![Model Analytics](assets/model-analytics.png)

![Plugin Hub](assets/plugin-hub.png)

## Quick Start

```bash
git clone https://github.com/joeynyc/hermes-hudui.git
cd hermes-hudui
./install.sh
hermes-hudui
```

Open http://localhost:3001

**Requirements:** Python 3.11+, Node.js 20.19+ or 22.12+ (required by Vite 8), a running Hermes agent with data in `~/.hermes/`

**Verified against Hermes Agent v0.17.0** (state.db schema v16). The HUD reads `~/.hermes/` and the `hermes` CLI directly, so it tracks the agent's on-disk layout. The Health tab's *Agent data layout* and *Agent schema version* checks flag when your agent's data drifts from this baseline.

On future runs:
```bash
source venv/bin/activate && hermes-hudui
```

### Windows (native)

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and [nvm-windows](https://github.com/coreybutler/nvm-windows). `install.ps1` installs Node.js 22 (LTS) via nvm — the frontend's Vite 8 toolchain requires Node 20.19+/22.12+, so Node 18 will not build it.

```powershell
git clone https://github.com/joeynyc/hermes-hudui.git
cd hermes-hudui
.\install.ps1
hermes-hudui
```

If PowerShell blocks script execution, run `install.ps1` via `powershell -ExecutionPolicy Bypass -File .\install.ps1`.

On future runs:
```powershell
.\.venv\Scripts\Activate.ps1
hermes-hudui
# or, without activating: uv run hermes-hudui
```

## What's Inside

19 tabs covering everything your agent knows about itself — executive dashboard, identity, memory, skills, sessions, replay, cron jobs, projects, health diagnostics, costs, model analytics, patterns, corrections, sudo governance, live chat, connected OAuth providers, gateway control, plugin management, and live model capabilities.

The Dashboard opens with an executive summary: health, spend pulse, top model, provider/gateway risk, highest-cost session, and action items. Health reacts to filesystem and WebSocket updates, while expensive refresh paths stay throttled.

Gateway visibility includes managed-tool routing for web search, image generation, text-to-speech, and browser automation. You can see whether each tool is routed through Nous Tool Gateway, a direct key, or is unavailable. The `Update hermes` action is deliberately two-click and shows last-run logs/status.

The Plugin Hub shows installed dashboard and agent plugins, extension entry points, runtime status, required auth commands, and safe enable/disable/update actions.

Updates in real time via WebSocket. No manual refresh needed.

## Hermes Replay

Hermes Replay turns agent runs into redacted, shareable proof artifacts.

![Hermes Replay tab](assets/replay-tab.png)

Open the Replay tab, choose a Hermes session, inspect the normalized timeline, review the run receipt, and export static artifacts for sharing or attaching to issues and PRs. The MVP exporter writes local files under `~/.hermes-hud/replays/` and does not upload anything by default.

Current local exports:

- Redacted JSON replay
- GitHub-ready Markdown
- Standalone HTML replay
- 1200 x 630 PNG share card
- Fork-safe `fork.json`

An example sanitized payload is included at [`assets/example-replay.redacted.json`](assets/example-replay.redacted.json).

Safe Share Mode is the default export posture. It redacts raw tool arguments, terminal output, assistant reasoning, token-like values, emails, local paths, and other sensitive fields before writing share artifacts. Exports include local hashes and Ed25519 signatures generated on this machine; they prove local artifact integrity, not external third-party attestation.

### Remote publishing (optional)

Locally published replays can be synced to a static host as a public gallery. In the Replay tab's Remote Publishing panel, configure a git repository (`owner/name` for GitHub Pages, or any git URL) and a branch, then press Sync now. The sync builds a static site from your published replays — public replays are listed on the gallery index; unlisted replays are reachable only through an unguessable hash path — and pushes it with your normal git credentials. Remote publishing is off by default, sync only happens when you trigger it, and only Safe-Share-Mode artifacts are ever included; local filesystem paths and publish manifests never leave the machine.

## Language Support

English (default) and Chinese. Click the language toggle at the far right of the header bar to switch. The choice persists to localStorage. When set to Chinese, chat responses from your agent also come back in Chinese.

## Themes

Five themes switchable with `t`: **Neural Awakening** (cyan), **Hermes Teal** (official Nous dashboard palette), **Blade Runner** (amber), **fsociety** (green), **Anime** (purple). Optional CRT scanlines.

The top tab bar is responsive: resize the browser and tabs stay reachable through horizontal scrolling, with the active tab kept in view.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`–`9`, `0` | Switch tabs |
| `t` | Theme picker |
| `Ctrl+K` | Command palette |

## Relationship to the TUI

This is the browser companion to [hermes-hud](https://github.com/joeynyc/hermes-hud). Both read from the same `~/.hermes/` data directory independently — use either one, or both at the same time.

The Web UI is fully standalone and adds features the TUI doesn't have: dedicated Memory, Skills, Sessions, Replay, Health, Providers, Gateway, Model, and Plugins tabs; per-model token and cost analytics; gateway managed-tool visibility; actionable diagnostics; command palette; live chat; theme switcher.

If you also have the TUI installed, you can enable it with `pip install 'hermes-hudui[tui]'`.

(Quotes around `'hermes-hudui[tui]'` are required in zsh, where the unquoted `[tui]` is interpreted as a glob pattern. Bash and fish accept the unquoted form, but the quoted form is safe everywhere.)

## Platform Support

macOS · Linux · Windows · WSL

## License

MIT — see [LICENSE](LICENSE).

---

<a href="https://www.star-history.com/?repos=joeynyc%2Fhermes-hudui&type=date&logscale=&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=joeynyc/hermes-hudui&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=joeynyc/hermes-hudui&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=joeynyc/hermes-hudui&type=date&legend=top-left" />
 </picture>
</a>
