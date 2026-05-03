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

Optional watcher override for awkward filesystems:
```bash
HERMES_HUD_WATCH_MODE=force-polling hermes-hudui
```

Supported watcher modes: `auto` (default), `force-polling`, `force-events`.

## What's Inside

17 tabs covering everything your agent knows about itself — identity, memory, skills, sessions, cron jobs, projects, health, costs, patterns, corrections, sudo governance, live chat, connected OAuth providers, gateway control, and live model capabilities.

Updates in real-time via WebSocket. No manual refresh needed.

## Language Support

English (default) and Chinese. Click the language toggle at the far right of the header bar to switch. The choice persists to localStorage. When set to Chinese, chat responses from your agent also come back in Chinese.

## Themes

Four themes switchable with `t`: **Neural Awakening** (cyan), **Blade Runner** (amber), **fsociety** (green), **Anime** (purple). Optional CRT scanlines.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`–`9`, `0` | Switch tabs |
| `t` | Theme picker |
| `Ctrl+K` | Command palette |

## Relationship to the TUI

This is the browser companion to [hermes-hud](https://github.com/joeynyc/hermes-hud). Both read from the same `~/.hermes/` data directory independently — use either one, or both at the same time.

The Web UI is fully standalone and adds features the TUI doesn't have: dedicated Memory, Skills, and Sessions tabs; per-model token cost tracking; command palette; live chat; theme switcher.

If you also have the TUI installed, you can enable it with `pip install 'hermes-hudui[tui]'`.

(Quotes around `'hermes-hudui[tui]'` are required in zsh, where the unquoted `[tui]` is interpreted as a glob pattern. Bash and fish accept the unquoted form, but the quoted form is safe everywhere.)

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
