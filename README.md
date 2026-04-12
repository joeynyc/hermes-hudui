# ☤ Hermes HUD — Web UI

A browser-based dashboard for [Hermes](https://github.com/nousresearch/hermes-agent), the AI agent with persistent memory.

Same data, same soul — now in your browser.

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

13 tabs covering everything your agent knows about itself — identity, memory, skills, sessions, cron jobs, projects, health, costs, patterns, corrections, and live chat.

Updates in real-time via WebSocket. No manual refresh needed.

## Themes

Four themes switchable with `t`: **Neural Awakening** (cyan), **Blade Runner** (amber), **fsociety** (green), **Anime** (purple). Optional CRT scanlines.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`–`9`, `0` | Switch tabs |
| `t` | Theme picker |
| `Ctrl+K` | Command palette |

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
