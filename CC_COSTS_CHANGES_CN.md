# CC Cost Tab — 改动说明

## 概述
为 hermes-hudui 新增 **CC Cost** 标签页，用于统计 Claude Code 的 token 消耗和成本。数据来源为 `~/.claude/projects/` 下的会话 JSONL 文件，通过读取 assistant 消息中的 `usage` 字段获取 token 数据，并复用 `token_costs.py` 的 `MODEL_PRICING` 定价表计算成本。

前端组件完全镜像 `TokenCostsPanel.tsx`，面板结构、交互逻辑、样式保持一致。

## 新增文件

### 1. `backend/api/cc_costs.py` — 后端 API
- 路由: `GET /api/cc-costs`
- 功能: 遍历 `~/.claude/projects/*/` 下所有 JSONL 文件，解析 `type=assistant` 消息的 `usage` 字段
- 提取字段: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`
- 工具调用统计: 遍历 assistant 消息的 `content` 数组，计数 `type=tool_use` 的 block
- 多模型支持: 单个 JSONL 文件内按 model 字段分别统计，避免多模型会话只显示一种
- 使用 `token_costs.py` 中的 `MODEL_PRICING` 计算预估成本
- 返回结构与 `/api/token-costs` 完全一致:
  - `today`: 今日统计（会话数、消息数、token 明细、成本）
  - `all_time`: 全部累计统计（含 tool_call_count）
  - `by_model`: 按模型分组（含 token 明细、成本、定价匹配）
  - `by_project`: 按项目分组
  - `top_sessions`: 成本最高的 10 个会话（含 tool_call_count）
  - `trend_summary`: 近 7 天 vs 前 7 天成本对比
  - `daily_trend`: 每日成本趋势
  - `pricing_table`: 模型定价表（供前端计算成本明细）

### 2. `frontend/src/components/CCCostsPanel.tsx` — 前端组件
- 完全复制 `TokenCostsPanel.tsx`，仅修改 API 端点（`/cc-costs`）和面板标题前缀（CC）
- 使用相同组件: `StatCard`, `DetailRow`, `DeltaBadge`, `ModelCard`, `Sparkline`
- 面板结构（与 Costs 页面一致）:
  1. **CC Today** — 今日统计卡片 + token 明细 + 成本
  2. **CC Total** — 全部统计卡片 + cache 节省 + 成本明细（Input/Output/Cache Read/Cache Write）+ 总成本
  3. **7-Day Trend** — 近 7 天 vs 前 7 天 + 差值 + cache 节省 + 实际覆盖率
  4. **Top CC Sessions** — Top 10 会话表格（Session/Model/Tokens/Tool Calls/Estimated/Actual/Billed）
  5. **By Model** — 模型卡片网格（含 Estimated/Actual/Delta/Billed 成本对比）
  6. **CC Daily Cost Trend** — 折线图 + 每日明细

### 3. `CC_COSTS_CHANGES.md` — 本文档

## 修改文件

### 4. `backend/main.py`
- 新增 `import cc_costs`
- 注册路由: `app.include_router(cc_costs.router, prefix="/api")`

### 5. `frontend/src/components/TopBar.tsx`
- TABS 数组新增: `{ id: 'cc-costs', labelKey: 'tab.cc-costs', key: null }`（位于 token-costs 之后）

### 6. `frontend/src/App.tsx`
- 新增 `import CCCostsPanel`
- TabContent switch 新增 `case 'cc-costs': return <CCCostsPanel />`
- GRID_CLASS 新增 `'cc-costs': 'grid-cols-1 lg:grid-cols-2'`

### 7. `frontend/src/i18n/translations.ts`
- Tab 标签:
  - 英文: `tab.cc-costs`: 'CC Cost'
  - 中文: `tab.cc-costs`: 'CC成本'
- 面板文本（英文）:
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
- 面板文本（中文）:
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

## 数据来源
- 路径: `~/.claude/projects/*/`
- 文件格式: JSONL（每行一个 JSON 对象）
- 解析逻辑: 筛选 `type=assistant` 的条目，提取 `message.usage` 中的 token 计数
- 工具调用: 从 assistant 消息的 `content` 数组中计数 `type=tool_use` 的 block
- 多模型: 单个 JSONL 文件内按 `message.model` 字段分别统计
- 时区处理: JSONL 中的时间戳带 `Z` 后缀（UTC），解析后转为本地时间（去掉 tzinfo）进行日期分组

## 与 TokenCostsPanel 的区别
- 数据来源不同: CC 读 `~/.claude/projects/` 下的 JSONL 文件，Hermes 读 `~/.hermes/state.db`
- CC 没有 `actual_cost_usd`（无实际账单），Estimated 和 Billed 相同
- CC 的 Top Sessions 表格显示 project 而非 title/source
- CC 的多模型会话拆分显示为 "2 models" 等
