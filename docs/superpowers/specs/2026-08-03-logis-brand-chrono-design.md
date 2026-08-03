# LOGIS Brand, Chronometer & Shell Unification — Design Spec

**Date:** 3 August 2026  
**Status:** Awaiting user review before implementation plan  
**Repos:** `e-LOGIS-Dashboard` (primary UI work) + `e-Hermes-HUD-UI` (theme-first amalgamation)  
**IP posture:** Product branding is **LOGIS**. Visual language may be *inspired by* popular HUD motifs; never ship user-facing **JARVIS** labels, theme ids, aria text, docs headings or comments that present JARVIS as the product name.

---

## 1. Locked HITL decisions

| # | Topic | Decision |
|---|--------|----------|
| Env | Workspace | **A** — multi-repo Cloud environment including `e-LOGIS-Dashboard` |
| 1 | Chronometer placement | **B** — in `.topbar-right`, immediately before status LEDs |
| 2 | Chronometer ring | **Month dial** — arc fills `monthIndex / 12` (August → 8/12). Day-of-month remains centred in the ring for glanceable date. |
| 3 | Clock interaction | Click the time readout toggles **12h ↔ 24h**. Preference persists in `localStorage`. Secondary: double-click toggles **local ↔ UTC** (also persisted). |
| 4 | Time source | Client `new Date()` (browser local TZ; UTC mode uses `Date` UTC getters / `timeZone: 'UTC'`). |
| 5 | First build scope | Chronometer **+** capacity/power ring |
| 6 | Amalgamation depth | **Theme first** — add Hermes `logis` theme / shared tokens before Channel shell work |
| 7 | Radial app menu | **Include** — see §5 |
| 8 | Brand sweep | **Everything** — UI copy, aria-labels, docs, ADRs, README, comments, theme ids, i18n keys, tests, screenshots alt text. Prefer `logis` over any `jarvis` identifier. |

---

## 2. Goals

1. Establish **LOGIS** as the sole product trademark string in the dashboard and related Hermes theme naming.
2. Ship a header **chronometer** and **capacity ring** that feel native to the existing cyan OLED HUD.
3. Add a **radial app menu** that surfaces Command Matrix actions without inventing a second navigation model.
4. Land a Hermes HUD **`logis` theme** so Monitor and Channel share design DNA before any deeper merge.

Non-goals for this phase: full Monitor↔Channel shell merge, porting LOGIS panels into React, changing loopback/ADR security posture, or wiring live Kokoro/gateway in Cloud VMs.

---

## 3. Architecture

```
LOGIS (:8787)                          Hermes HUD (:5173 / :3001)
┌─────────────────────────────┐        ┌──────────────────────────┐
│ topbar                      │        │ themes: … + logis        │
│  brand (reactor) ──radial   │        │ --hud-* ← LOGIS palette  │
│  … chrono + capacity … LEDs  │        │ (shared token mapping)   │
│ Command Matrix / Channel /  │        │ Channel shell = later    │
│ Wayfinder·Kanban            │        └──────────────────────────┘
└─────────────────────────────┘
```

Keep MECE surfaces: LOGIS = channel/act; Hermes = monitor/read. Unify chrome and tokens first.

---

## 4. Chronometer + capacity ring (LOGIS header)

### 4.1 Placement (decision B)

Inside `.topbar-right`, order left→right:

1. `.chrono` (month dial + time/date readout)  
2. `.capacity` (power/capacity ring)  
3. `.leds` (existing status LEDs)  
4. settings / close controls  

Thin `--line` dividers between chrono, capacity and LEDs. On `@media (max-width: 1100px)` allow wrap; chrono+capacity stay as one group before LEDs.

### 4.2 Chronometer behaviour

- **Ring fill:** `--month-frac = monthIndex / 12` where January = 1 … December = 12 (August → `8/12`). Conic-gradient arc in `--cyan` / `--hud-primary`.
- **Centre:** day-of-month (`en-GB` numeric), JetBrains Mono, minimal cyan glow.
- **Readout:** `HH:MM:SS` (or 12h with am/pm) as hero; weekday + month name underneath in existing `.eyebrow` style (gold, uppercase, letter-spaced).
- **Locale:** `en-GB` (`lang="en-GB"`).
- **Click target:** the `.chrono-readout` / `<time>` cluster (min 44×44px hit area). Click → toggle 12/24. Double-click → toggle local/UTC. Persist keys e.g. `logis.chrono.hour12`, `logis.chrono.utc`.
- **A11y:** semantic `<time datetime>`; **no** per-second `aria-live`. Update accessible name on minute change or on mode toggle only. Visible focus ring on `:focus-visible`.
- **Motion:** optional dashed outer spin gated by `prefers-reduced-motion: reduce` (clock still ticks).

### 4.3 Capacity / power ring

Sibling widget reusing the same ring primitive.

| Condition | Fill / colour |
|-----------|----------------|
| Gateway + Hermes healthy | Fill ≈ 1.0, success/cyan |
| Degraded (e.g. voice down, gateway up) | Fill ≈ 0.6–0.8, warning |
| Gateway / Hermes down | Fill ≈ 0.2–0.4, error/danger |
| Unknown / loading | Decorative low fill, muted |

Label under or beside ring: `POWER` / capacity percent text (never colour-alone — keep text + ring). Bind to existing `/api/status` (or equivalent LED sources) so the ring agrees with LED state. When status endpoints are unreachable in Cloud VMs, show honest degraded state (same as red LEDs today).

### 4.4 Illustrative markup

```html
<div class="topbar-meters" role="group" aria-label="Time and system capacity">
  <div class="chrono" role="group" aria-label="Local date and time">
    <div class="chrono-ring" style="--month-frac: 0.666">
      <span class="chrono-day" id="chrono-day">3</span>
    </div>
    <button type="button" class="chrono-readout" id="chrono-toggle"
            aria-label="Toggle 12-hour or 24-hour clock. Double-click to toggle local or UTC.">
      <time class="chrono-time" id="chrono-time" datetime="">--:--:--</time>
      <div class="chrono-date eyebrow" id="chrono-date">— · —</div>
    </button>
  </div>
  <div class="capacity" role="group" aria-label="System capacity">
    <div class="capacity-ring" style="--cap-frac: 0.25">
      <span class="capacity-pct" id="capacity-pct">25</span>
    </div>
    <div class="capacity-label eyebrow">POWER</div>
  </div>
</div>
```

---

## 5. Radial app menu (LOGIS)

**Problem:** A free-floating radial launcher can fight the Command Matrix (ADR #104: prefixes are canonical).

**Resolution:** The **reactor / brand control** opens a radial menu whose items are the existing Command Matrix prefixes (`/agent0`, `/wayfinder`, `/deepdive`, `/kanban`, `/handover`, `/background`, `/new`, …). Selecting an item focuses the channel composer and inserts/selects that prefix — same contracts as the matrix, different chrome.

- Position: anchored on the brand reactor (top-left).  
- Interaction: click reactor to open/close; `Escape` closes; click-outside closes.  
- A11y: `aria-expanded`, `role="menu"` / `menuitem`, arrow-key navigation, 44px targets.  
- Motion: 150–300ms open; disabled under `prefers-reduced-motion` (instant show/hide).  
- Do **not** remove the Command Matrix grid in v1 — radial is an alternate affordance.

---

## 6. Brand sweep (everything)

Replace product-facing and identifier uses of JARVIS/jarvis with LOGIS/logis across:

- Visible UI strings and alt text  
- `aria-label` / `title` / `meta`  
- Markdown docs, ADRs, AGENTS.md, README, ROADMAP, changelog entries added in this work  
- CSS comments, JSDoc, Python docstrings  
- Theme id: Hermes theme is **`logis`** (never `jarvis`)  
- i18n keys: `theme.logis` / label **LOGIS**  
- Tests and fixtures that assert brand strings  
- Screenshot/artifact captions in docs  

Keep historical changelog lines that record past release notes only if rewriting would falsify history; new prose uses LOGIS. Code identifiers such as CSS classes that are purely structural need not change unless they contain `jarvis`.

---

## 7. Hermes theme-first (`logis`)

Add a sixth theme in `frontend/src/index.css`, `useTheme.tsx`, and `i18n/translations.ts`:

| Token | Value (from LOGIS OLED cyan) |
|-------|------------------------------|
| `--hud-bg-deep` | `#03060d` |
| `--hud-bg-surface` / panel / hover | stepped lifts from deep |
| `--hud-primary` | `#3de7ff` |
| `--hud-primary-glow` | `rgba(61, 231, 255, 0.4)` |
| `--hud-accent` | gold matching LOGIS eyebrow |
| status colours | map to LOGIS `--success` / `--amber` / `--danger` |

Label in theme picker: **LOGIS**. This is the amalgamation proof: Hermes can wear the LOGIS skin before Channel is ported.

Optional follow-up (same phase if cheap): document a shared token mapping table in `docs/` so LOGIS `:root` and Hermes `--hud-*` stay aligned.

---

## 8. Implementation phasing

| Phase | Repo | Deliverable |
|-------|------|-------------|
| **P0** | Hermes HUD | `logis` theme + i18n + theme picker entry; lint/build |
| **P1** | LOGIS | Full JARVIS→LOGIS brand sweep |
| **P2** | LOGIS | Chronometer (month dial, 12/24 + local/UTC) at placement B |
| **P3** | LOGIS | Capacity/power ring bound to status |
| **P4** | LOGIS | Radial app menu on reactor → Command Matrix prefixes |
| **P5** | Both | Screenshots, reduced-motion + narrow-width checks, PR notes |

P0 can proceed in this Hermes-only workspace. P1–P4 require `e-LOGIS-Dashboard` on the agent filesystem.

---

## 9. Environment blocker (decision A)

The prior setup run cloned `G6FX2032/e-LOGIS-Dashboard` into a multi-repo workspace. **This agent run cannot resolve that repository** (GitHub API/git clone → 404 / not found for the cloud token). There is also **no linked Cursor environment** on this run (`environment: null`), so multi-repo checkout is not active.

Unblock options (human):

1. Attach the existing multi-repo Cloud environment (Hermes + LOGIS + Kokoro + UI-UX-Pro-Max) to the next agent run, **or**  
2. Grant this cloud token read access and confirm the canonical repo URL, **or**  
3. Explicitly ask the agent to `trigger-environment-build` with a multi-repo `environment_json` once the LOGIS repo is readable.

Until then, only **P0** (Hermes `logis` theme) is implementable here.

---

## 10. Testing / acceptance

- Chronometer: August shows ~8/12 arc; day centre correct; click flips 12↔24 and persists; double-click flips local↔UTC; no SR spam every second.  
- Capacity: agrees with LED/status semantics; colour + text.  
- Radial: opens from reactor; inserts a real matrix prefix; keyboard + Escape.  
- Brand: ripgrep for `jarvis`/`JARVIS` in LOGIS tree is empty (except intentional historical changelog if any).  
- Hermes: theme picker shows LOGIS; `data-theme="logis"` paints cyan OLED tokens; `npm run lint` clean; `npm run build` succeeds.  
- `prefers-reduced-motion` and ~1100px / mobile widths checked via browser screenshots.

---

## 11. Open items closed by this spec

- Ring meaning → **month / 12** (not day-of-month arc).  
- Theme name → **`logis`**, not `jarvis`.  
- Radial → **yes**, anchored on brand reactor, wired to Command Matrix.  
- Capacity → **in first LOGIS UI PR** with chronometer.

---

## 12. Spec self-review

- No TBD placeholders for locked HITL items.  
- Radial placement specified (reactor) to avoid a second nav system.  
- Scope split so Hermes P0 is not blocked by LOGIS access.  
- Double-click UTC is the explicit interpretation of “12/24, etc.” — change on review if you want click-cycle of four modes instead.
