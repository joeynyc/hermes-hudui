# ☤ Hermes HUD — Web UI

A browser-based consciousness monitor for [Hermes](https://github.com/nousresearch/hermes-agent), the AI agent with persistent memory.

Same data, same soul, same dashboard that made the [TUI version](https://github.com/joeynyc/hermes-hud) popular — now in your browser.


![Token Costs](assets/dashboard-costs.png)

![Agent Profiles](assets/profiles.png)

## What It Shows

Everything your agent knows about itself:

- **Identity** — designation, substrate, runtime, days conscious, brain size
- **What I Know** — conversations held, messages exchanged, actions taken, skills acquired
- **What I Remember** — memory capacity bars, user profile state, corrections absorbed
- **What I See** — API keys (present/dark), service health (alive/silent)
- **What I'm Learning** — recently modified skills with categories
- **What I'm Working On** — active projects with dirty file status
- **What Runs While You Sleep** — scheduled cron jobs
- **How I Think** — tool usage patterns with gradient bars
- **My Rhythm** — daily activity sparkline
- **Growth Delta** — snapshot diffs showing what changed
- **Token Costs** — per-model USD cost estimates with daily trend

## Quick Start

```bash
git clone https://github.com/joeynyc/hermes-hudui.git
cd hermes-hudui
python3.11 -m venv venv
source venv/bin/activate
./install.sh
hermes-hudui
```

Open http://localhost:3001

On future runs, just activate and start:

```bash
source venv/bin/activate
hermes-hudui
```

## Requirements

- Python 3.11+
- Node.js 18+ (for building the frontend)
- A running Hermes agent with data in `~/.hermes/`

No other packages required — the Web UI reads directly from your agent's data directory.

## Manual Install

```bash
# 1. Create and activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Install this package
pip install -e .

# 3. Build the frontend
cd frontend
npm install
npm run build
cp -r dist/* ../backend/static/

# 4. Start the server
hermes-hudui
```

## Themes

Six color themes, switchable with `t` key or the theme picker:

| Theme | Key | Mood |
|-------|-----|------|
| **Neural Awakening** | `ai` | Cyan/blue on deep navy. Clean, clinical intelligence. |
| **Blade Runner** | `blade-runner` | Amber/orange on warm black. Neo-noir dystopia. |
| **fsociety** | `fsociety` | Green on pure black. Raw hacker aesthetic. |
| **Anime** | `anime` | Purple/violet on indigo. Psychic energy. |
| **Hermes White** | `hermes-white` | Royal blue on pale cool white — matches [hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/) light mode. |
| **Hermes Dark** | `hermes-dark` | Mint green accents on charcoal — matches the same site’s dark mode. |

Optional CRT scanline overlay — toggle via theme picker.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`-`9`, `0` | Switch tabs |
| `t` | Toggle theme picker |
| `r` | Refresh all data |
| `Ctrl+K` | Command palette |

## Architecture

```
React Frontend (Vite + SWR)
    ↓ /api/* (proxied in dev)
FastAPI Backend (Python)
    ↓ collectors/*.py
~/.hermes/ (agent data files)
```

Backend collectors read directly from `~/.hermes/` and return dataclasses. The frontend fetches from `/api/*` endpoints via SWR with auto-refresh and renders one panel component per tab.

## Token Cost Pricing

Costs are calculated from token counts using hardcoded per-model pricing. Supported models:

| Provider | Model | Input | Output | Cache Read |
|----------|-------|------:|-------:|-----------:|
| Anthropic | Claude Opus 4 | $15/M | $75/M | $1.50/M |
| Anthropic | Claude Sonnet 4 | $3/M | $15/M | $0.30/M |
| Anthropic | Claude Haiku 3.5 | $0.80/M | $4/M | $0.08/M |
| OpenAI | GPT-4o | $2.50/M | $10/M | $1.25/M |
| OpenAI | o1 | $15/M | $60/M | $7.50/M |
| DeepSeek | V3 | $0.27/M | $1.10/M | $0.07/M |
| xAI | Grok 3 | $3/M | $15/M | $0.75/M |
| Google | Gemini 2.5 Pro | $1.25/M | $10/M | $0.31/M |

Models not in the table fall back to Claude Opus pricing. Local/free models are detected and priced at $0.

## Relationship to the TUI

This is the browser companion to [hermes-hud](https://github.com/joeynyc/hermes-hud). Both read from the same `~/.hermes/` data directory independently. You can use either one, or both at the same time.

The Web UI is fully standalone — it ships its own data collectors and doesn't require the TUI package. It adds features the TUI doesn't have: dedicated Memory, Skills, and Sessions tabs; per-model token cost tracking; command palette; theme switcher with live preview.

If you also have the TUI installed (`pip install hermes-hud`), you can enable it with `pip install hermes-hudui[tui]`.

## Platform Support

- **macOS** — native, install via `./install.sh`
- **Linux** — native, install via `./install.sh`
- **Windows** — via WSL (Windows Subsystem for Linux)
- **WSL** — install script detects WSL automatically

## License

MIT — see [LICENSE](LICENSE).

## Star History

<a href="https://www.star-history.com/?repos=joeynyc%2Fhermes-hudui&type=date&logscale=&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=joeynyc/hermes-hudui&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=joeynyc/hermes-hudui&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=joeynyc/hermes-hudui&type=date&legend=top-left" />
 </picture>
</a>
