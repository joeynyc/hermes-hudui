# Plan: Agent Chat with Tool Calling & Reasoning Display in HUD UI

## Goal

Add a new "Chat" tab to the Hermes HUD Web UI that displays full agent conversations — user messages, assistant responses, tool calls (with function names + arguments), tool results, and reasoning/thinking blocks. This gives a live transcript view of what the agent is actually doing, not just aggregates.

## Data Source

The `messages` table in `~/.hermes/state.db` has everything we need:

```
messages: id, session_id, role (user|assistant|tool), content, 
          tool_calls (JSON), tool_name, reasoning, reasoning_details, 
          timestamp, token_count
```

Current volume: ~12k messages across roles (5500 assistant, 5500 tool, 864 user).

Key data points per message:
- `role`: `user`, `assistant`, `tool` — drives the UI rendering type
- `tool_calls`: JSON array with `{function: {name, arguments}}` for assistant messages that invoke tools
- `tool_name`: name of the tool for `role=tool` messages (tool results)
- `reasoning` / `reasoning_details`: chain-of-thought or extended thinking text
- `content`: the actual message text
- `timestamp`: for ordering and grouping

## Proposed Architecture

### Backend Changes

**1. New collector: `backend/collectors/chat.py`**

Two functions:
- `collect_session_list()` — lightweight query returning sessions with message counts, used for the session selector sidebar. Reuses existing sessions collector data but adds last_message_at.
- `collect_session_messages(session_id, limit=200, offset=0)` — fetches messages for a single session ordered by timestamp. Parses `tool_calls` JSON. Returns list of `ChatMessage` dataclasses.

Query pattern:
```sql
SELECT id, session_id, role, content, tool_calls, tool_name, 
       reasoning, reasoning_details, timestamp, token_count
FROM messages WHERE session_id = ?
ORDER BY timestamp ASC LIMIT ? OFFSET ?
```

Caching: 10s TTL on messages (they're immutable once written, but new ones arrive). Session list cached 30s with db mtime invalidation (reuse existing pattern from `cache.py`).

**2. New dataclass in `backend/collectors/models.py`:**

```python
@dataclass
class ChatMessage:
    id: int
    session_id: str
    role: str          # user, assistant, tool
    content: str
    tool_calls: list   # parsed from JSON
    tool_name: Optional[str]
    reasoning: Optional[str]
    timestamp: datetime
    token_count: int

@dataclass
class ChatSession:
    id: str
    title: Optional[str]
    source: str
    message_count: int
    tool_call_count: int
    last_message_at: datetime
    model: Optional[str]

@dataclass
class ChatState:
    sessions: list[ChatSession]
    messages: list[ChatMessage]
    active_session_id: Optional[str]
```

**3. New API route: `backend/api/chat.py`**

```
GET  /api/chat/sessions          → list of sessions for sidebar
GET  /api/chat/messages/{sid}    → messages for session sid (query params: limit, offset)
```

Register in `main.py`:
```python
app.include_router(chat.router, prefix="/api")
```

### Frontend Changes

**4. New component: `frontend/src/components/ChatPanel.tsx`**

Layout: two-panel design
- **Left sidebar** (280px): session list sorted by last message time. Search/filter input at top. Each entry shows title (or id), source badge, message count, last active time.
- **Right main area**: message thread for selected session. Scrollable, auto-scrolls to bottom.

Message rendering by role:

| Role | Render as |
|------|-----------|
| `user` | Left-aligned bubble, `--hud-accent` border. Show content. |
| `assistant` | Full-width block, `--hud-primary` accent. Show content. If `tool_calls` present, show tool invocation cards below the text. |
| `tool` | Collapsed by default, expandable. Shows tool name, truncated content. `--hud-text-dim` styling. |

**Tool call cards**: Show function name in a header bar, arguments in a collapsible JSON block (syntax-highlighted via CSS monospace + key coloring). Tool result shown underneath as a collapsed block.

**Reasoning blocks**: Toggle-able section between user message and assistant response when `reasoning` is present. Rendered in a distinct style — `--hud-secondary` color, monospace, with a "thinking..." header that expands on click. Markdown-lite rendering for content.

**5. Register tab in `TopBar.tsx`:**
```typescript
{ id: 'chat', label: 'Chat', key: 'q' },  // or find available key
```

Add to `App.tsx`:
```typescript
case 'chat': return <ChatPanel />
```

Add grid class: `grid-cols-1` (the panel handles its own internal layout).

**6. Wire up WebSocket refresh:**
When `data_changed` events fire for `state.db`, revalidate the chat sessions list and current session messages via SWR mutation.

### Files to Create/Modify

| File | Action |
|------|--------|
| `backend/collectors/chat.py` | **Create** — session list + message collector |
| `backend/collectors/models.py` | **Modify** — add ChatMessage, ChatSession, ChatState dataclasses |
| `backend/api/chat.py` | **Create** — /api/chat/sessions and /api/chat/messages/{sid} |
| `backend/main.py` | **Modify** — register chat router |
| `frontend/src/components/ChatPanel.tsx` | **Create** — full chat panel component |
| `frontend/src/components/TopBar.tsx` | **Modify** — add chat tab |
| `frontend/src/App.tsx` | **Modify** — register ChatPanel + grid class |

### Implementation Order

1. Backend dataclass + collector (testable with terminal sqlite queries)
2. API route (testable with curl)
3. Frontend ChatPanel — session list sidebar
4. Frontend ChatPanel — message thread with role-based rendering
5. Tool call card rendering
6. Reasoning block rendering
7. WebSocket integration for live updates
8. Tab registration + wiring

### Verification

1. `curl localhost:3001/api/chat/sessions` — returns session list with counts
2. `curl localhost:3001/api/chat/messages/<session_id>` — returns message array
3. Browser: open Chat tab, select a session, verify messages render
4. Verify tool calls show function name + arguments
5. Verify reasoning blocks appear and are toggle-able
6. Verify WebSocket refreshes chat when new messages arrive

### Risks / Open Questions

- **Message volume**: Some sessions have 500+ messages. Pagination (limit/offset) is essential. Initial load of 200, scroll-up to load more.
- **tool_calls JSON format**: Varies across provider — OpenAI-style vs Anthropic-style. Need to handle both shapes. The existing data shows OpenAI-style `[{function: {name, arguments}}]`.
- **Reasoning content**: May be long. Collapsible with truncation at ~500 chars by default.
- **Tab key**: Currently 0-9 are taken. Need to pick an available keyboard shortcut or drop the shortcut entirely for Chat.
- **Performance**: 12k messages in the DB is fine. The per-session query is fast with the existing index on `(session_id, timestamp)`.
