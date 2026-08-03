# LOGIS Brand, Chronometer, Pomodoro & Shell — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Hermes HUD `logis` theme first, then (when `e-LOGIS-Dashboard` is available) brand-sweep LOGIS and add chronometer, capacity ring, Pomodoro, top-right system radial, and a minimal widget registry.

**Architecture:** Keep Monitor (Hermes) and Channel (LOGIS) as separate apps. Unify design DNA via a shared cyan OLED `logis` theme on Hermes. On LOGIS, introduce a shared dial primitive and treat topbar meters as widgets with `localStorage` config. System radial is shell chrome only (no Command Matrix).

**Tech Stack:** Hermes — React 19, Vite, Tailwind v4, CSS variables, pytest static theme tests. LOGIS — vanilla HTML/CSS/JS + FastAPI `:8787` (paths confirmed after clone).

**Spec:** `docs/superpowers/specs/2026-08-03-logis-brand-chrono-design.md`

## Global Constraints

- Product brand string is **LOGIS**; never ship user-facing **JARVIS** / theme id `jarvis`.
- Hermes theme id must be exactly `logis`; picker label **LOGIS**.
- Chronometer placement **B** (before LEDs); month dial = `monthIndex / 12`.
- Clock: click = 12/24; double-click = local/UTC; client `Date`; `en-GB`.
- Pomodoro colours: cyan → soft amber → soft rose (not alarm red); break = sage green.
- System radial top-right: settings / HUD placeholder (C) / close; no command prefixes.
- Do not commit `.env`; respect LOGIS loopback ADR when touching networking.
- `npm run lint` must exit 0 on Hermes frontend changes; run relevant pytest.

**File map (Hermes — known):**
- `frontend/src/index.css` — theme CSS blocks
- `frontend/src/hooks/useTheme.tsx` — `ThemeId`, `THEMES`
- `frontend/src/i18n/translations.ts` — en + zh labels
- `frontend/src/main.tsx` — boot theme attribute (default stays `hermes-official`)
- `tests/test_frontend_themes.py` — static registration tests
- `CHANGELOG.md` — Unreleased note

**File map (LOGIS — confirm after clone):** inventory in Task 2; expect topbar/brand/LED markup under static or root HTML/CSS/JS plus FastAPI status endpoint.

---

### Task 1: Hermes `logis` theme (P0)

**Files:**
- Modify: `frontend/src/hooks/useTheme.tsx`
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/i18n/translations.ts`
- Modify: `tests/test_frontend_themes.py`
- Modify: `CHANGELOG.md`
- Test: `tests/test_frontend_themes.py`

**Interfaces:**
- Consumes: existing `ThemeId` / `THEMES` / `[data-theme="…"]` pattern
- Produces: `ThemeId` includes `'logis'`; `THEMES` entry `{ id: 'logis', labelKey: 'theme.logis', icon: '⟐' }`; CSS `[data-theme="logis"]` with tokens below; i18n `theme.logis`

**Token values (from spec):**
- `--hud-bg-deep: #03060d`
- `--hud-bg-surface: #071018`
- `--hud-bg-panel: #0c1824`
- `--hud-bg-hover: #122030`
- `--hud-primary: #3de7ff`
- `--hud-primary-dim: #1aa8c4`
- `--hud-primary-glow: rgba(61, 231, 255, 0.4)`
- `--hud-secondary: #7af0ff`
- `--hud-accent: #e6b84d` (soft gold / amber)
- `--hud-text: #d7eef5`
- `--hud-text-dim: #6a8a9a`
- `--hud-border: rgba(61, 231, 255, 0.25)`
- `--hud-border-bright: rgba(61, 231, 255, 0.5)`
- `--hud-success: #6bcf8e`
- `--hud-warning: #e6b84d`
- `--hud-error: #e86a6a`
- `--hud-gradient-start: #1aa8c4`
- `--hud-gradient-end: #3de7ff`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_frontend_themes.py`:

```python
def test_logis_theme_is_registered_and_styled() -> None:
    theme_ts = (ROOT / "frontend/src/hooks/useTheme.tsx").read_text()
    css = (ROOT / "frontend/src/index.css").read_text()
    translations = (ROOT / "frontend/src/i18n/translations.ts").read_text()

    assert "'logis'" in theme_ts
    assert "theme.logis" in theme_ts
    assert "jarvis" not in theme_ts.lower()
    assert '[data-theme="logis"]' in css
    assert "--hud-bg-deep: #03060d;" in css
    assert "--hud-primary: #3de7ff;" in css
    assert "--hud-primary-glow: rgba(61, 231, 255, 0.4);" in css
    assert "--hud-accent: #e6b84d;" in css
    assert "'theme.logis': 'LOGIS'" in translations
    assert "jarvis" not in translations.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /workspace && python -m pytest tests/test_frontend_themes.py::test_logis_theme_is_registered_and_styled -v`  
Expected: FAIL (theme not registered)

- [ ] **Step 3: Implement theme registration + CSS + i18n**

In `useTheme.tsx`, extend:

```typescript
export type ThemeId = 'ai' | 'hermes-official' | 'blade-runner' | 'fsociety' | 'anime' | 'logis'
```

Add THEMES entry after `hermes-official` (or at end):

```typescript
{ id: 'logis', labelKey: 'theme.logis', icon: '⟐' },
```

In `index.css`, after the anime block, add `[data-theme="logis"] { … }` with the token values above. Update the file header comment from “5 themes” to “6 themes”.

In `translations.ts` en: `'theme.logis': 'LOGIS',`  
zh: `'theme.logis': 'LOGIS',` (brand untranslated)

In `CHANGELOG.md` under Unreleased → Added: LOGIS theme (cyan OLED palette aligned with the Channel dashboard).

- [ ] **Step 4: Run tests and lint**

Run:

```bash
cd /workspace && python -m pytest tests/test_frontend_themes.py -v
cd /workspace/frontend && npm run lint
```

Expected: pytest PASS; lint 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useTheme.tsx frontend/src/index.css frontend/src/i18n/translations.ts tests/test_frontend_themes.py CHANGELOG.md
git commit -m "feat(theme): add LOGIS cyan OLED theme to Hermes HUD"
```

---

### Task 2: Obtain LOGIS tree + brand inventory (blocker gate)

**Files:**
- Create: working copy of `e-LOGIS-Dashboard` (path TBD by environment; prefer `/home/ubuntu/repos/e-LOGIS-Dashboard` or multi-repo workspace root)
- Create: `/tmp/logis-jarvis-inventory.txt` (scratch; do not commit)

**Interfaces:**
- Consumes: readable git remote for LOGIS
- Produces: list of files containing `jarvis`/`JARVIS`; confirmed paths for topbar HTML/CSS/JS and status API

- [ ] **Step 1: Verify repo access**

```bash
gh repo view G6FX2032/e-LOGIS-Dashboard
# or clone the canonical URL once access exists
```

Expected: repo resolves. If 404, stop and report blocker (Tasks 3–8 cannot proceed).

- [ ] **Step 2: Inventory JARVIS strings**

```bash
rg -n -i 'jarvis' --glob '!**/node_modules/**' --glob '!**/.git/**' /path/to/e-LOGIS-Dashboard | tee /tmp/logis-jarvis-inventory.txt
```

- [ ] **Step 3: Record structural paths**

Locate and note absolute paths for: main HTML shell, CSS tokens (`:root` / `--cyan`), topbar markup (`.topbar`, `.brand`, `.leds`), main JS, FastAPI `/api/status` (or equivalent). Write them into the PR description for Tasks 3–8.

- [ ] **Step 4: Commit** only if inventory notes are added under `docs/` in Hermes or LOGIS; otherwise no commit — proceed to Task 3 on the LOGIS branch `g6fx/logis-brand-chrono-ui-7b52`.

---

### Task 3: LOGIS full brand sweep (P1)

**Files:**
- Modify: every file from Task 2 inventory (exact list from inventory)

**Interfaces:**
- Consumes: inventory paths
- Produces: zero product-facing `jarvis`/`JARVIS` matches (allow historical changelog only if rewriting falsifies history)

- [ ] **Step 1: Failing check**

```bash
rg -i 'jarvis' /path/to/e-LOGIS-Dashboard --glob '!**/.git/**' | rg -v 'CHANGELOG' ; echo exit:$?
```

Expected: matches exist (non-empty) before sweep.

- [ ] **Step 2: Replace brand strings**

Replace user-facing and identifier uses with LOGIS/logis per spec §7. Theme/class names containing `jarvis` → `logis`. Update aria-labels, titles, docs, ADRs, comments, tests.

- [ ] **Step 3: Verify**

```bash
rg -i 'jarvis' /path/to/e-LOGIS-Dashboard --glob '!**/.git/**' --glob '!**/CHANGELOG*'
```

Expected: no matches.

- [ ] **Step 4: Commit on LOGIS branch**

```bash
git commit -m "chore(brand): replace JARVIS product labelling with LOGIS"
```

---

### Task 4: Shared dial primitive + chronometer (P2)

**Files:**
- Modify: LOGIS CSS (tokens + `.chrono*` / `.dial*`)
- Modify: LOGIS HTML topbar (insert meters group before LEDs)
- Modify: LOGIS JS (tick + 12/24 + local/UTC)
- Test: prefer a small Node or Playwright check if the repo already has one; otherwise a pytest/HTML fixture assertion that markup ids exist, matching Hermes’ static-test style

**Interfaces:**
- Consumes: `.topbar-right` / `.leds` structure from Task 2
- Produces: `#chrono-day`, `#chrono-time`, `#chrono-date`, `#chrono-toggle`; `localStorage` keys `logis.chrono.hour12`, `logis.chrono.utc`; `--month-frac`

- [ ] **Step 1: Add markup** in `.topbar-right` before `.leds` per spec §4.4 (chrono portion).

- [ ] **Step 2: Add CSS** for `.chrono`, `.chrono-ring` using `conic-gradient` and `--month-frac`, mono day centre, readout styles; respect `prefers-reduced-motion`.

- [ ] **Step 3: Add JS**

```javascript
const hour12 = () => localStorage.getItem('logis.chrono.hour12') === 'true';
const useUtc = () => localStorage.getItem('logis.chrono.utc') === 'true';
function tick() {
  const n = new Date();
  const monthIndex = useUtc() ? n.getUTCMonth() + 1 : n.getMonth() + 1;
  chronoRing.style.setProperty('--month-frac', String(monthIndex / 12));
  // format en-GB time/date; set day centre; set datetime attribute
}
chronoToggle.addEventListener('click', () => { /* toggle hour12 */ });
chronoToggle.addEventListener('dblclick', (e) => { e.preventDefault(); /* toggle utc */ });
tick(); setInterval(tick, 1000);
```

- [ ] **Step 4: Manual verify** at `http://localhost:8787` — August shows ~8/12 arc; click toggles 12/24; double-click toggles UTC.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(topbar): add LOGIS chronometer with month dial and 12/24 toggle"
```

---

### Task 5: Capacity / power ring (P3)

**Files:**
- Modify: same LOGIS HTML/CSS/JS as Task 4
- Modify: status polling against existing `/api/status` (or LED data source)

**Interfaces:**
- Consumes: dial primitive; status payload fields used by LEDs
- Produces: `#capacity-pct`, `--cap-frac`, `.capacity-label` POWER text; colour + text always paired

- [ ] **Step 1: Markup + CSS** for `.capacity` after `.chrono`.

- [ ] **Step 2: Bind status** — map healthy → ~1.0 success; degraded → ~0.6–0.8 warning; down → ~0.2–0.4 error; unknown → muted.

- [ ] **Step 3: Verify** against LED colours in UI.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(topbar): add capacity power ring bound to status"
```

---

### Task 6: Pomodoro dial + configure popup (P4)

**Files:**
- Modify: LOGIS HTML/CSS/JS (centre topbar slot)
- Config keys: `logis.pomo.focusMin`, `logis.pomo.breakMin`, `logis.pomo.autoBreak`, `logis.pomo.autoFocus` in `localStorage`

**Interfaces:**
- Consumes: dial primitive + Pomodoro colour tokens from spec §6.4
- Produces: phase `idle|focus|break|paused`; right-click / Shift+F10 opens configure dialog

- [ ] **Step 1: Add colour tokens** `--pomo-focus-calm`, `--pomo-focus-progress`, `--pomo-focus-near`, `--pomo-break`, `--pomo-paused`.

- [ ] **Step 2: Markup** centre Pomodoro dial + hidden `<dialog>` configure form (focus min, break min, auto-start break checkbox, auto-start focus checkbox).

- [ ] **Step 3: Logic** — start/pause on primary click; countdown remaining/total arc; at 0 auto-start break if enabled; stage colours by remaining fraction (≥0.5 calm, 0.25–0.5 amber, ≤0.25 soft rose); break uses green; `aria-live` polite only on phase change.

- [ ] **Step 4: Verify** 25→5 default path; custom 120 min accepted; right-click opens dialog.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(topbar): add Pomodoro dial with configure popup and calm colour stages"
```

---

### Task 7: Top-right system radial (P5)

**Files:**
- Modify: LOGIS HTML/CSS/JS topbar-right end

**Interfaces:**
- Consumes: existing settings entry point
- Produces: radial/menu with Settings, HUD (disabled placeholder title “Monitor↔Channel — coming soon”), Close; **no** `/agent0` etc.

- [ ] **Step 1: Markup** button `#system-radial-btn` + menu items.

- [ ] **Step 2: Behaviour** — toggle menu; Esc/click-outside closes; Settings opens existing panel; HUD item `disabled` or `aria-disabled` with tooltip; Close calls `window.close()` or hides shell with confirm if needed.

- [ ] **Step 3: Verify** no command prefixes in menu DOM.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(topbar): add system radial for settings, HUD placeholder, and close"
```

---

### Task 8: Widget registry show/hide W1 (P6, optional same PR)

**Files:**
- Modify: LOGIS settings + JS registry

**Interfaces:**
- Consumes: widget ids `chrono`, `capacity`, `pomodoro`, `systemRadial`
- Produces: `localStorage` `logis.widgets.enabled` JSON array; settings checkboxes

- [ ] **Step 1: Registry object** mapping id → root element.

- [ ] **Step 2: Settings UI** toggles; persist; apply on load.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(widgets): allow show/hide for topbar meter widgets"
```

---

### Task 9: Verification pack

**Files:** artifacts under `/opt/cursor/artifacts/`

- [ ] **Step 1:** Hermes — select LOGIS theme; screenshot theme picker + dashboard.
- [ ] **Step 2:** LOGIS — screenshot topbar with chrono, capacity, Pomodoro, radial open; reduced-motion; ~1100px width.
- [ ] **Step 3:** Update PR bodies with artifact paths; run Hermes `pytest` + `npm run lint` + `npm run build`.

---

## Plan self-review

1. **Spec coverage:** P0 theme ✓; brand sweep ✓; chrono ✓; capacity ✓; Pomodoro + colours ✓; system radial + HUD C ✓; Plasma W1 ✓; full Plasma W2/W3 deferred (spec allows).  
2. **Placeholders:** LOGIS absolute paths deferred to Task 2 inventory by necessity (repo not mounted).  
3. **Naming:** `logis` theme id, `logis.*` localStorage prefix, no `jarvis`.
