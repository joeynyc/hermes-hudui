# LOGIS Brand, Chronometer, Pomodoro & Shell Unification — Design Spec

**Date:** 3 August 2026 (revised same day)  
**Status:** Awaiting user review before implementation plan  
**Repos:** `e-LOGIS-Dashboard` (primary UI work) + `e-Hermes-HUD-UI` (theme-first amalgamation)  
**IP posture:** Product branding is **LOGIS**. Visual language may be *inspired by* popular HUD motifs; never ship user-facing **JARVIS** labels, theme ids, aria text, docs headings or comments that present JARVIS as the product name.

---

## 1. Locked HITL decisions

| # | Topic | Decision |
|---|--------|----------|
| Env | Workspace | **A** — multi-repo Cloud environment including `e-LOGIS-Dashboard` |
| 1 | Chronometer placement | **B** — in `.topbar-right`, immediately before status LEDs / system radial |
| 2 | Chronometer ring | **Month dial** — arc fills `monthIndex / 12` (August → 8/12). Day-of-month remains centred in the ring for glanceable date. |
| 3 | Clock interaction | Click the time readout toggles **12h ↔ 24h**. Preference persists in `localStorage`. Secondary: double-click toggles **local ↔ UTC** (also persisted). |
| 4 | Time source | Client `new Date()` (browser local TZ; UTC mode uses UTC getters / `timeZone: 'UTC'`). |
| 5 | First build scope | Chronometer **+** capacity/power ring **+** Pomodoro dial **+** top-right system radial |
| 6 | Amalgamation depth | **Theme first** — add Hermes `logis` theme / shared tokens before Channel shell work |
| 7 | Radial app menu | **Top-right system radial** — settings / HUD switch / close (etc.). **Not** Command Matrix (commands stay left). See §5 |
| 7a | HUD switch behaviour | **C** — placeholder only until Monitor↔Channel amalgamation; no external HUD navigation in v1 |
| 8 | Brand sweep | **Everything** — UI copy, aria-labels, docs, ADRs, README, comments, theme ids, i18n keys, tests, screenshots alt text. Prefer `logis` over any `jarvis` identifier. |
| 9 | Pomodoro | Top-centre-ish dial; right-click → configure popup; custom focus/break durations; auto-start break on expiry; research-backed colour stages. See §6 |
| 10 | Customisation direction | Evolve toward a **Plasma-like widget panel** (show/hide, order, per-widget config). See §8 |

---

## 2. Goals

1. Establish **LOGIS** as the sole product trademark string in the dashboard and related Hermes theme naming.
2. Ship header **meters** (chronometer, capacity, Pomodoro) that feel native to the cyan OLED HUD.
3. Add a **top-right system radial** for shell chrome (settings, HUD switch, close) — keep left side for commands.
4. Land a Hermes HUD **`logis` theme** so Monitor and Channel share design DNA before any deeper merge.
5. Set an architecture path toward **user-configurable widgets** (Plasma-inspired), without boiling the ocean in v1.

Non-goals for this phase: full Monitor↔Channel shell merge, porting LOGIS panels into React, changing loopback/ADR security posture, shipping a real KDE Plasmoid binary, or wiring live Kokoro/gateway in Cloud VMs.

---

## 3. Architecture & topbar layout

```
LOGIS topbar (left → right)
┌──────────┬─────────────────────┬──────────────────────────────┐
│ Brand    │  Pomodoro (centre)  │  Chrono · Capacity · LEDs ·  │
│ reactor  │                     │  System radial (⚙⋯)          │
└──────────┴─────────────────────┴──────────────────────────────┘
Left column: Command Matrix (unchanged)
```

```
LOGIS (:8787)                          Hermes HUD (:5173 / :3001)
┌─────────────────────────────┐        ┌──────────────────────────┐
│ topbar widgets (panel-like) │        │ themes: … + logis        │
│ Command Matrix (left)       │        │ --hud-* ← LOGIS palette  │
│ Channel / Wayfinder·Kanban  │        │ Channel shell = later    │
└─────────────────────────────┘        └──────────────────────────┘
```

Keep MECE surfaces: LOGIS = channel/act; Hermes = monitor/read. Unify chrome and tokens first. Treat the topbar as an early **widget containment** (Plasma analogy: a panel holding applets).

---

## 4. Chronometer + capacity ring (LOGIS header)

### 4.1 Placement (decision B)

Inside `.topbar-right`, order left→right:

1. `.chrono` (month dial + time/date readout)  
2. `.capacity` (power/capacity ring)  
3. `.leds` (existing status LEDs)  
4. **System radial trigger** (replaces/absorbs scattered settings/close affordances where sensible)  

Thin `--line` dividers between meter groups. On `@media (max-width: 1100px)` allow wrap; chrono+capacity stay grouped.

### 4.2 Chronometer behaviour

- **Ring fill:** `--month-frac = monthIndex / 12` (January = 1 … December = 12; August → `8/12`).
- **Centre:** day-of-month (`en-GB`), JetBrains Mono, minimal cyan glow.
- **Readout:** `HH:MM:SS` (or 12h + am/pm); weekday + month in `.eyebrow` style.
- **Click:** toggle 12/24. **Double-click:** toggle local/UTC. Persist `logis.chrono.hour12`, `logis.chrono.utc`.
- **A11y:** `<time datetime>`; no per-second `aria-live`; update name on minute change or mode toggle; `:focus-visible` ring.
- **Motion:** optional outer spin gated by `prefers-reduced-motion`.

### 4.3 Capacity / power ring

Sibling ring primitive bound to `/api/status` (or LED sources). Colour + text (never colour-alone). Degraded Cloud VM state stays honest when gateway/voice are down.

---

## 5. Top-right system radial (revised)

**Not** Command Matrix. Commands remain on the left.

**Anchor:** top-right control (gear / reactor-mini / existing settings cluster), opening a radial (or compact pie) of **shell chrome** actions:

| Item | Intent |
|------|--------|
| **Settings** | Open existing settings panel/drawer |
| **HUD switch** | **Placeholder in v1** (decision **C**): visible control, disabled or “Coming soon / Monitor↔Channel” affordance until amalgamation lands; then becomes the Monitor↔Channel toggle. Do not open an external Hermes URL yet. |
| **Close** | Close or minimise the LOGIS window/tab (confirm if destructive) |
| **Theme** (optional “etc.”) | Cycle or open theme/scanline controls if present |
| **Always-on-top** (optional) | Only if the host shell supports it; otherwise omit |

- Interaction: click to open/close; `Escape` / click-outside closes.  
- A11y: `aria-expanded`, `role="menu"` / `menuitem`, arrow keys, ≥44px targets.  
- Motion: 150–300ms; instant under `prefers-reduced-motion`.  
- Do **not** duplicate left-side prefixes (`/agent0`, `/wayfinder`, …).

---

## 6. Pomodoro widget

### 6.1 Placement & chrome

- **Top-centre-ish** in the topbar (between brand and `.topbar-right`), as another dial sibling to chrono/capacity.
- Compact representation: radial remaining-time arc + centre readout (`MM:SS` or `H:MM:SS` for long focuses) + small phase label (`FOCUS` / `BREAK`).
- **Primary click:** start / pause (or resume).  
- **Right-click (context menu):** open **Configure Pomodoro** popup (also reachable via a ⋯ inside the popup for keyboard users: Shift+F10 / menu key when focused).

### 6.2 Configure Pomodoro popup

Editable factors (persisted in `localStorage`, e.g. `logis.pomo.*`):

| Field | Default | Notes |
|-------|---------|--------|
| Focus duration | 25 min | Any positive duration (e.g. 30, 45, 90, **120** mins) — number + unit (min) |
| Break duration | 5 min | Same flexibility |
| Long break (optional v1.1) | 15 min | Every N focuses; can ship later |
| Auto-start break | on | When focus hits 0 → start break countdown |
| Auto-start next focus | off | Avoid surprise re-entry; user can enable |
| Sound / voice cue | off in v1 | Hook later to Kokoro if desired |

Validation: durations ≥ 1 minute; sensible max (e.g. 240 min) with a soft warning above 180.

### 6.3 Lifecycle

1. Idle → user starts focus.  
2. Focus counts down; arc = **remaining / total** (remaining-centric is less anxiety-framed than “how expired”).  
3. At 0: brief completion pulse → if auto-start break → **break** countdown with green stage colours.  
4. Break at 0 → idle (or auto-start next focus if enabled).  
5. Pause freezes remaining; config edits apply to the **next** segment unless user chooses “apply now & reset”.

### 6.4 Colour stages (research-backed — avoid alarm red)

**Design goal:** signal progress and phase without importing threat/anxiety semantics.

**Evidence (summary):**

- Cool hues (blue/green) associate with calm / positive affect; red/yellow more often with tension or negative affect in wait/loading contexts (e.g. Gorn, Chattopadhyay & Sengupta, *Journal of Marketing Research* — screen colour → relaxation → perceived wait; Design Society pupillometry loading-page study — blue/green positive, red/yellow more negative / higher arousal).
- Red priming can harm performance in evaluative contexts (classic Elliot colour-in-context findings; popular summaries in Verywell Mind’s colour psychology overview).
- Low-saturation blue–green workplace accents reduced stress/anxiety markers in an office RCT abstract (Schizophrenia Bulletin supplement, 2026; treat as supportive not gospel).
- UC Davis Color Lab: **amber** ambient light showed the strongest stress-mitigation effect among white/amber/green/blue/red after a social-stress protocol — useful as a mid-session “still OK / you’re progressing” cue rather than a warning orange.
- Saturations should stay **moderate**; lighter values ranked more positively in loading-page work.

**Recommended LOGIS Pomodoro palette (tokens):**

| Phase / remaining | Token | Hue intent | Meaning to the user |
|-------------------|--------|------------|---------------------|
| Focus, remaining ≥ 50% | `--pomo-focus-calm` | Bluish-cyan (LOGIS cyan family, slightly desaturated) | Settled focus |
| Focus, remaining 25–50% | `--pomo-focus-progress` | Soft **amber/gold** (not neon orange) | Progressing; keep going |
| Focus, remaining ≤ 25% | `--pomo-focus-near` | Soft **warm rose / peach** (low saturation) — **not** alarm red | Almost done / reward approaching |
| Break (any) | `--pomo-break` | Soft **sage / mint green** | Recovery |
| Paused | `--pomo-paused` | Muted slate + dashed arc | On hold |

Arc interpolates between stage stops (CSS or canvas). Optional gentle brightness pulse only in the final 10% of focus, gated by `prefers-reduced-motion`.

**Explicitly rejected:** traffic-light red at 90% elapsed as “urgency” — conflicts with the user’s brief and with threat-association findings.

### 6.5 A11y

- `role="timer"` / accessible name including phase + remaining.  
- Announce phase changes (focus→break→idle) via polite `aria-live` **once**, not every second.  
- Config popup: labelled fields, Esc closes, focus trap.

---

## 7. Brand sweep (everything)

Unchanged in intent: replace JARVIS/jarvis with LOGIS/logis across UI, aria, docs, ADRs, comments, theme id **`logis`**, i18n, tests. Historical changelog lines may stay if rewriting would falsify history.

---

## 8. Plasma-like customisation (direction)

Yes — the dashboard is drifting toward a **desktop panel**. KDE Plasma’s model is useful inspiration, not something to reimplement as Qt plasmoids in-browser.

### 8.1 Plasma concepts to borrow

| Plasma idea | LOGIS analogue |
|-------------|----------------|
| **Containment** (panel/desktop) | Topbar + optional side docks as containments |
| **Applet / plasmoid** | Widget (chrono, capacity, Pomodoro, system radial, future clocks, notes, …) |
| **Compact vs full representation** | Dial in bar vs right-click / click-out config popup |
| **Per-applet config schema** | `logis.widgets.<id>.config` in `localStorage` (later optional server file under `~/.hermes/` or LOGIS config) |
| **Add / remove / reorder** | Widget catalogue + enabled list + order index |

### 8.2 Phased delivery (do not build all at once)

| Phase | Deliverable |
|-------|-------------|
| **W0 (this build)** | Ship chrono, capacity, Pomodoro, system radial as **first-class widgets** with stable ids; shared dial primitive; configs in `localStorage`. |
| **W1** | Widget registry + **show/hide** toggles in Settings; persist order. |
| **W2** | Drag-reorder in the topbar; denser “panel edit mode” (Plasma-like edit affordance). |
| **W3** | Declarative widget manifests (JSON schema) so new dials can be added without rewriting the shell; optional user CSS tokens. |
| **Later** | True Plasmoid packaging is out of scope unless you explicitly want a native KDE companion; the web panel stays the product. |

This keeps Kubuntu/`plasma.desktop` muscle memory (widgets you can add, configure, tuck away) without pretending the browser is plasmashell.

---

## 9. Hermes theme-first (`logis`)

Add sixth theme in `frontend/src/index.css`, `useTheme.tsx`, `i18n/translations.ts`:

| Token | Value (LOGIS OLED cyan) |
|-------|-------------------------|
| `--hud-bg-deep` | `#03060d` |
| `--hud-primary` | `#3de7ff` |
| `--hud-primary-glow` | `rgba(61, 231, 255, 0.4)` |
| `--hud-accent` | soft gold / amber (shared with Pomodoro progress stage) |
| status | map to LOGIS success / amber / danger |

Picker label: **LOGIS**.

---

## 10. Implementation phasing

| Phase | Repo | Deliverable |
|-------|------|-------------|
| **P0** | Hermes HUD | `logis` theme + i18n + picker; lint/build |
| **P1** | LOGIS | Full JARVIS→LOGIS brand sweep |
| **P2** | LOGIS | Shared dial primitive + chronometer (month/12) at placement B |
| **P3** | LOGIS | Capacity/power ring |
| **P4** | LOGIS | Pomodoro dial + configure popup + colour stages |
| **P5** | LOGIS | Top-right system radial (settings / HUD / close / …) |
| **P6** | LOGIS | W1 widget registry show/hide (if schedule allows; else follow-up PR) |
| **P7** | Both | Screenshots, reduced-motion + narrow-width checks |

P0 can proceed in the Hermes-only workspace. P1–P6 need `e-LOGIS-Dashboard` mounted.

---

## 11. Environment blocker (decision A)

This agent run still cannot resolve `G6FX2032/e-LOGIS-Dashboard` (404) and has **no linked Cursor environment**. Unblock by attaching the multi-repo environment, granting repo read access, or explicitly requesting a draft `trigger-environment-build` once the repo is readable.

---

## 12. Testing / acceptance

- Chronometer: August ~8/12 arc; 12/24 + local/UTC persist; no SR spam.  
- Capacity: matches LED/status semantics.  
- Pomodoro: custom durations (incl. 120); break auto-starts; colours follow calm→amber→soft rose→green; right-click opens configure; pause works.  
- System radial: top-right; settings / HUD / close; **no** command prefixes.  
- Brand: no product-facing `jarvis`/`JARVIS` left in LOGIS tree (except intentional history).  
- Hermes: `data-theme="logis"`; lint/build clean.  
- Motion and ~1100px widths checked.

---

## 13. Spec self-review

- Radial relocated top-right; command coupling removed.  
- Pomodoro + research-backed palette documented with citations (summary).  
- Plasma path scoped as phased widget containments — not a native plasmashell port.  
- Double-click UTC interpretation retained unless you prefer a four-mode click cycle.  
- **HUD switch** locked as **C** (placeholder until Monitor↔Channel amalgamation).
