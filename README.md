# ☤ Hermes HUD — Web UI

A browser-based consciousness monitor for [Hermes](https://github.com/nousresearch/hermes-agent), the AI agent with persistent memory.

Same data, same soul, same dashboard that made the [TUI version](https://github.com/joeynyc/hermes-hud) popular — now in your browser.

![Token Costs](assets/dashboard-costs.png)

![Agent Profiles](assets/profiles.png)

## Quick Start

```bash
git clone https://github.com/joeynyc/hermes-hudui.git
cd hermes-hudui
./install.sh
hermes-hudui
```

Open http://localhost:3001

**Requirements:** Python 3.11+, Node.js 18+, a running Hermes agent with data in `~/.hermes/`

On future runs:
```bash
source venv/bin/activate && hermes-hudui
```

## What's Inside

14 tabs covering everything your agent knows about itself — identity, memory, skills, sessions, cron jobs, projects, health, costs, patterns, corrections, live chat, and an ARTPLEX operator view.

Updates in real-time via WebSocket. No manual refresh needed.

## Themes

Four themes switchable with `t`: **Neural Awakening** (cyan), **Blade Runner** (amber), **fsociety** (green), **Anime** (purple). Optional CRT scanlines.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`–`9`, `0` | Switch core tabs |
| `a` | Open ARTPLEX |
| `t` | Theme picker |
| `Ctrl+K` | Command palette |

## Architecture

```
React Frontend (Vite + SWR)
    ↓ /api/*
FastAPI Backend (Python)
    ↓ collectors/*.py
~/.hermes/ (agent data files)
```

Backend collectors read directly from `~/.hermes/` and return dataclasses. The frontend fetches from `/api/*` endpoints and renders one panel component per tab.

## Token Cost Pricing

The HUD now distinguishes:
- actual tracked billing
- stored estimates
- fallback estimates for legacy rows
- subscription-included usage
- hypothetical API-equivalent replay

Unknown or unpriced models are surfaced honestly instead of receiving fake fallback prices.

## Relationship to the TUI

This is the browser companion to [hermes-hud](https://github.com/joeynyc/hermes-hud). Both read from the same `~/.hermes/` data directory independently — use either one, or both at the same time.

The Web UI is fully standalone and adds features the TUI doesn't have: dedicated Memory, Skills, Sessions, Costs, and ARTPLEX tabs; per-model token cost tracking; command palette; live chat; theme switcher.

If you also have the TUI installed, you can enable it with `pip install hermes-hudui[tui]`.

## Platform Support

macOS · Linux · WSL

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
