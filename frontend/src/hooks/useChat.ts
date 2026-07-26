import { useState, useCallback, useRef, useEffect, useMemo, useSyncExternalStore } from 'react'
import { Chat, useChat as useAiChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import type { UIMessage } from 'ai'
import { useI18n } from '../i18n'

// ── Types ─────────────────────────────────────────────────────────────────

export type { UIMessage }

export interface SessionSummary {
  id: string
  title: string
  backend_type: string
  is_active: boolean
}

export interface ComposerState {
  model: string
  isStreaming: boolean
  contextTokens: number
  status: string
  elapsedMs: number
  firstTokenMs: number | null
  totalMs: number | null
  processStartMs: number | null
  resumed: boolean
  recentFirstTokenAvgMs: number | null
  recentTotalAvgMs: number | null
  recentRuns: number
}

// ── localStorage helpers ───────────────────────────────────────────────────

const MESSAGES_KEY = (id: string) => `hud-chat-msgs-${id}`
const SESSIONS_KEY = 'hud-chat-sessions'

export function saveMessages(sessionId: string, msgs: UIMessage[]) {
  try {
    localStorage.setItem(MESSAGES_KEY(sessionId), JSON.stringify(msgs))
  } catch {
    console.warn(`Chat history for ${sessionId} not persisted (storage quota?)`)
  }
}

export function loadMessages(sessionId: string): UIMessage[] {
  try {
    const raw = localStorage.getItem(MESSAGES_KEY(sessionId))
    if (!raw) return []
    const parsed = JSON.parse(raw) as UIMessage[]
    // Guard against old format (ChatMessage had content not parts)
    if (!Array.isArray(parsed) || (parsed.length > 0 && !parsed[0].parts)) return []
    return parsed
  } catch { return [] }
}

export function removeMessages(sessionId: string) {
  localStorage.removeItem(MESSAGES_KEY(sessionId))
}

export function saveSessions(sessions: SessionSummary[]) {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
  } catch { /* quota exceeded */ }
}

export function loadSavedSessions(): SessionSummary[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

// ── Per-session Chat instances ─────────────────────────────────────────────
//
// Each session owns a Chat instance, so streams, persistence, and cancel
// stay bound to the session they started in. Switching sessions swaps which
// instance useChat subscribes to; an in-flight stream keeps writing to its
// own instance in the background instead of bleeding into the new session.

const chatInstances = new Map<string, Chat<UIMessage>>()

// Streaming registry: the sidebar shows which sessions are busy — including
// backgrounded ones — without mounting a chat hook per session.
const streamingListeners = new Set<() => void>()
let streamingIds: string[] = []

function recomputeStreaming() {
  const ids: string[] = []
  for (const [id, c] of chatInstances) {
    if (c.status === 'streaming' || c.status === 'submitted') ids.push(id)
  }
  // Keep the snapshot reference stable when nothing changed
  if (ids.length === streamingIds.length && ids.every((v, i) => v === streamingIds[i])) return
  streamingIds = ids
  streamingListeners.forEach((l) => l())
}

const subscribeStreaming = (onChange: () => void) => {
  streamingListeners.add(onChange)
  return () => { streamingListeners.delete(onChange) }
}

export function useStreamingSessions(): string[] {
  return useSyncExternalStore(subscribeStreaming, () => streamingIds)
}

// Read at request time by every session transport; kept current by useChat.
const langRef = { current: 'en' }

function getOrCreateChat(sessionId: string): Chat<UIMessage> {
  let chat = chatInstances.get(sessionId)
  if (!chat) {
    chat = new Chat<UIMessage>({
      id: sessionId,
      messages: loadMessages(sessionId),
      transport: new DefaultChatTransport({
        api: `/api/chat/sessions/${sessionId}/message`,
        prepareSendMessagesRequest({ messages, body, id, trigger, messageId }) {
          return {
            api: `/api/chat/sessions/${sessionId}/message`,
            body: { id, messages, trigger, messageId, ...body, lang: langRef.current },
          }
        },
      }),
      // sessionId is captured at construction — a finished stream persists
      // under the session it belongs to even if the user switched away.
      // Evicted instances (ended sessions) must not resurrect deleted history.
      onFinish: ({ messages: finishedMessages }) => {
        if (chatInstances.get(sessionId) === chat) {
          saveMessages(sessionId, finishedMessages)
        }
      },
    })
    chat['~registerStatusCallback'](recomputeStreaming)
    chatInstances.set(sessionId, chat)
  }
  return chat
}

// Stop a session's stream and its backend process — works for backgrounded
// sessions, not just the one on screen.
export async function cancelSessionStream(sessionId: string) {
  const chat = chatInstances.get(sessionId)
  if (chat) await chat.stop().catch(() => { /* best effort */ })
  try {
    await fetch(`/api/chat/sessions/${sessionId}/cancel`, { method: 'POST' })
  } catch { /* best effort */ }
}

// Write-through seed: localStorage and any live instance stay in sync.
export function seedMessages(sessionId: string, msgs: UIMessage[]) {
  saveMessages(sessionId, msgs)
  const chat = chatInstances.get(sessionId)
  if (chat) chat.messages = msgs
}

export function clearSessionStorage(sessionId: string) {
  const chat = chatInstances.get(sessionId)
  if (chat) {
    chat.stop().catch(() => { /* best effort */ })
    chatInstances.delete(sessionId)
    recomputeStreaming()
  }
  removeMessages(sessionId)
}

// ── useChat ────────────────────────────────────────────────────────────────

const IDLE_COMPOSER: ComposerState = {
  model: 'unknown',
  isStreaming: false,
  contextTokens: 0,
  status: 'idle',
  elapsedMs: 0,
  firstTokenMs: null,
  totalMs: null,
  processStartMs: null,
  resumed: false,
  recentFirstTokenAvgMs: null,
  recentTotalAvgMs: null,
  recentRuns: 0,
}

export function useChat(sessionId: string | null) {
  const { lang } = useI18n()
  useEffect(() => {
    langRef.current = lang
  }, [lang])

  // Latest session ID — used to drop async responses that raced a switch
  const sessionIdRef = useRef(sessionId)
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  // Swap to the session's instance; useAiChat re-subscribes when it changes.
  // The null fallback is an inert placeholder (ChatPanel gates sends on an
  // active session).
  const chat = useMemo(
    () => (sessionId ? getOrCreateChat(sessionId) : new Chat<UIMessage>({ messages: [] })),
    [sessionId]
  )

  const { messages, status, error, sendMessage, regenerate } = useAiChat({
    chat,
    experimental_throttle: 16,
  })

  // Composer state (model name / streaming flag from backend)
  const [composerState, setComposerState] = useState<ComposerState>(IDLE_COMPOSER)

  // Don't show the previous session's composer data while a fetch is in flight
  const [composerSessionId, setComposerSessionId] = useState(sessionId)
  if (composerSessionId !== sessionId) {
    setComposerSessionId(sessionId)
    setComposerState(IDLE_COMPOSER)
  }

  const loadComposerState = useCallback(async () => {
    const sid = sessionId
    if (!sid) return
    try {
      const response = await fetch(`/api/chat/sessions/${sid}/composer`)
      // A response that raced a session switch must not clobber the new session
      if (sessionIdRef.current !== sid) return
      if (response.ok) {
        const state = await response.json()
        setComposerState({
          model: state.model,
          isStreaming: state.is_streaming,
          contextTokens: state.context_tokens,
          status: state.status ?? 'idle',
          elapsedMs: state.elapsed_ms ?? 0,
          firstTokenMs: state.first_token_ms ?? null,
          totalMs: state.total_ms ?? null,
          processStartMs: state.process_start_ms ?? null,
          resumed: state.resumed ?? false,
          recentFirstTokenAvgMs: state.recent_first_token_avg_ms ?? null,
          recentTotalAvgMs: state.recent_total_avg_ms ?? null,
          recentRuns: state.recent_runs ?? 0,
        })
      }
    } catch { /* best effort */ }
  }, [sessionId])

  const cancelStream = useCallback(async () => {
    if (sessionId) await cancelSessionStream(sessionId)
  }, [sessionId])

  return {
    messages,
    isStreaming: status === 'streaming' || status === 'submitted',
    composerState,
    error: error?.message ?? null,
    sendMessage: (content: string) =>
      sessionId ? sendMessage({ text: content }) : Promise.resolve(),
    cancelStream,
    loadComposerState,
    regenerate,
  }
}

// ── useChatAvailability ────────────────────────────────────────────────────

export function useChatAvailability() {
  const [availability, setAvailability] = useState({
    available: false,
    directImport: false,
    tmuxAvailable: false,
    tmuxPaneFound: false,
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const checkAvailability = async () => {
      try {
        const response = await fetch('/api/chat/available')
        if (response.ok) {
          const data = await response.json()
          setAvailability({
            available: data.available,
            directImport: data.direct_import,
            tmuxAvailable: data.tmux_available,
            tmuxPaneFound: data.tmux_pane_found,
          })
        }
      } catch (err) {
        console.error('Failed to check chat availability:', err)
      } finally {
        setLoading(false)
      }
    }

    checkAvailability()
  }, [])

  return { ...availability, loading }
}

// ── useChatSessions ────────────────────────────────────────────────────────

export function useChatSessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>(() => loadSavedSessions())
  const [loading, setLoading] = useState(false)

  const loadSessions = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/chat/sessions')
      if (response.ok) {
        const data = await response.json()
        setSessions(data)
        // Only persist non-empty lists — avoids clobbering saved sessions on server restart
        if (data.length > 0) {
          saveSessions(data)
        }
      }
    } catch (err) {
      console.error('Failed to load sessions:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const createSession = useCallback(async (profile?: string, model?: string) => {
    try {
      const response = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile, model }),
      })
      if (response.ok) {
        const session = await response.json()
        await loadSessions()
        return session
      }
    } catch (err) {
      console.error('Failed to create session:', err)
    }
    return null
  }, [loadSessions])

  const endSession = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}`, {
        method: 'DELETE',
      })
      if (response.ok) {
        clearSessionStorage(sessionId)
        await loadSessions()
        return true
      }
    } catch (err) {
      console.error('Failed to end session:', err)
    }
    return false
  }, [loadSessions])

  useEffect(() => {
    // Fetching the server-backed list on mount intentionally updates this hook.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadSessions()
  }, [loadSessions])

  return { sessions, loading, createSession, endSession, refresh: loadSessions }
}
