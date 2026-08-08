# CC Cost Tab — Change Log

## Overview
Adds a **CC Cost** tab to hermes-hudui for tracking Claude Code token usage and costs. Data is sourced from session JSONL files under `~/.claude/projects/`, reading the `usage` field from assistant messages. Cost estimation reuses the `MODEL_PRICING` table from `token_costs.py`.

The frontend component is a direct copy of `TokenCostsPanel.tsx`, with only the API endpoint (`/cc-costs`) and panel title prefix (CC) changed. All panels, cards, table columns, and interactions are identical.

## New Files

### 1. `backend/api/cc_costs.py` — Backend API
- Route: `GET /api/cc-costs`
- Scans all JSONL files under `~/.claude/projects/*/`, parses `type=assistant` messages
- Extracted fields: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- Tool call counting: iterates `content` array in assistant messages, counts `type=tool_use` blocks
- Multi-model support: tracks per-model usage within a single JSONL file to handle sessions that switch models
- Uses `MODEL_PRICING` from `token_costs.py` for cost estimation
- Response structure matches `/api/token-costs`:
  - `today`: today's stats (sessions, messages, token breakdown, cost)
  - `all_time`: cumulative totals (includes `tool_call_count`)
  - `by_model`: grouped by model (token breakdown, cost, pricing match)
  - `by_project`: grouped by project
  - `top_sessions`: top 10 most expensive sessions (includes `tool_call_count`)
  - `trend_summary`: last 7 days vs previous 7 days cost comparison
  - `daily_trend`: daily cost trend
  - `pricing_table`: model pricing dict (used by frontend for cost breakdown calculations)

### 2. `frontend/src/components/CCCostsPanel.tsx` — Frontend Component
- Direct copy of `TokenCostsPanel.tsx` with API endpoint and labels changed
- Uses same components: `StatCard`, `DetailRow`, `DeltaBadge`, `ModelCard`, `Sparkline`
- Panel structure (identical to Costs page):
  1. **CC Today** — today's stat cards + token breakdown + cost
  2. **CC Total** — all-time stat cards + cache savings + cost breakdown (Input/Output/Cache Read/Cache Write) + total cost
  3. **7-Day Trend** — last 7d vs prev 7d + delta badge + cache savings + actual coverage
  4. **Top CC Sessions** — top 10 session table (Session/Model/Tokens/Tool Calls/Estimated/Actual/Billed)
  5. **By Model** — model card grid (with Estimated/Actual/Delta/Billed cost comparison)
  6. **CC Daily Cost Trend** — sparkline chart + daily breakdown

### 3. `CC_COSTS_CHANGES.md` — This document (Chinese version)

## Modified Files

### 4. `backend/main.py`
- Added `import cc_costs`
- Registered router: `app.include_router(cc_costs.router, prefix="/api")`

### 5. `frontend/src/components/TopBar.tsx`
- Added to TABS array: `{ id: 'cc-costs', labelKey: 'tab.cc-costs', key: null }` (after token-costs)

### 6. `frontend/src/App.tsx`
- Added `import CCCostsPanel`
- Added `case 'cc-costs': return <CCCostsPanel />` in TabContent switch
- Added `'cc-costs': 'grid-cols-1 lg:grid-cols-2'` in GRID_CLASS

### 7. `frontend/src/i18n/translations.ts`
- Tab label:
  - English: `tab.cc-costs`: 'CC Cost'
  - Chinese: `tab.cc-costs`: 'CC成本'
- Panel text (English):
  - `cc.title`: 'CC Cost'
  - `cc.loading`: 'Loading CC costs...'
  - `cc.today`: 'CC Today'
  - `cc.total`: 'CC Total'
  - `cc.byProject`: 'By Project'
  - `cc.dailyTrend`: 'CC Daily Cost Trend'
  - `cc.projects`: 'projects'
  - `cc.estimatedToday`: 'estimated today'
  - `cc.estimatedAllTime`: 'estimated all-time'
  - `cc.topSessions`: 'Top CC Sessions'
- Panel text (Chinese):
  - `cc.title`: 'CC成本'
  - `cc.loading`: '加载CC成本...'
  - `cc.today`: 'CC今日'
  - `cc.total`: 'CC总计'
  - `cc.byProject`: '按项目'
  - `cc.dailyTrend`: 'CC每日成本趋势'
  - `cc.projects`: '个项目'
  - `cc.estimatedToday`: '今日预估'
  - `cc.estimatedAllTime`: '总计预估'
  - `cc.topSessions`: 'CC最高成本会话'

## Data Source
- Path: `~/.claude/projects/*/`
- File format: JSONL (one JSON object per line)
- Parsing: filters `type=assistant` entries, extracts token counts from `message.usage`
- Tool calls: counts `type=tool_use` blocks in assistant message `content` array
- Multi-model: tracks per-model usage within a single file using `message.model` field
- Timezone: JSONL timestamps have `Z` suffix (UTC), converted to local time (tzinfo stripped) for date grouping

## Differences from TokenCostsPanel
- Data source: CC reads JSONL files from `~/.claude/projects/`, Hermes reads `~/.hermes/state.db`
- CC has no `actual_cost_usd` (no billing data), so Estimated and Billed are always equal
- CC Top Sessions show project name instead of title/source
- CC multi-model sessions display as "2 models" etc.
