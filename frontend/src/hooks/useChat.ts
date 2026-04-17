import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { useChat as useAiChat } from '@ai-sdk/react'
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
}

// ── localStorage helpers ───────────────────────────────────────────────────

const MESSAGES_KEY = (id: string) => `hud-chat-msgs-${id}`
const SESSIONS_KEY = 'hud-chat-sessions'

export function saveMessages(sessionId: string, msgs: UIMessage[]) {
  try {
    localStorage.setItem(MESSAGES_KEY(sessionId), JSON.stringify(msgs))
  } catch { /* quota exceeded — silently skip */ }
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

export function clearSessionStorage(sessionId: string) {
  removeMessages(sessionId)
}

// ── useChat ────────────────────────────────────────────────────────────────

export function useChat(sessionId: string | null) {
  const { lang } = useI18n()

  // Refs stay current inside the transport without causing re-renders
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  const langRef = useRef(lang)
  langRef.current = lang

  // In-memory session message cache for fast switching
  const messageCacheRef = useRef<Map<string, UIMessage[]>>(new Map())
  const prevSessionIdRef = useRef<string | null>(null)

  // Transport created once — injects session ID and lang per request
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: '/api/chat/placeholder', // overridden by prepareSendMessagesRequest
        prepareSendMessagesRequest({ messages, body, id, trigger, messageId }) {
          const sid = sessionIdRef.current ?? ''
          return {
            api: `/api/chat/sessions/${sid}/message`,
            body: { id, messages, trigger, messageId, ...body, lang: langRef.current },
          }
        },
      }),
    [] // eslint-disable-line react-hooks/exhaustive-deps
  )

  const { messages, status, error, sendMessage, stop, setMessages, regenerate } = useAiChat({
    transport,
    experimental_throttle: 50,
    onFinish: ({ messages: finishedMessages }) => {
      const sid = sessionIdRef.current
      if (sid) saveMessages(sid, finishedMessages)
    },
  })

  // Handle session switching: save outgoing, restore incoming
  useEffect(() => {
    const prevId = prevSessionIdRef.current
    if (prevId && prevId !== sessionId) {
      messageCacheRef.current.set(prevId, messages)
    }
    if (sessionId) {
      setMessages(messageCacheRef.current.get(sessionId) ?? loadMessages(sessionId))
    } else {
      setMessages([])
    }
    prevSessionIdRef.current = sessionId
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Composer state (model name / streaming flag from backend)
  const [composerState, setComposerState] = useState<ComposerState>({
    model: 'unknown',
    isStreaming: false,
    contextTokens: 0,
  })

  const loadComposerState = useCallback(async () => {
    const sid = sessionIdRef.current
    if (!sid) return
    try {
      const response = await fetch(`/api/chat/sessions/${sid}/composer`)
      if (response.ok) {
        const state = await response.json()
        setComposerState({
          model: state.model,
          isStreaming: state.is_streaming,
          contextTokens: state.context_tokens,
        })
      }
    } catch { /* best effort */ }
  }, [])

  const cancelStream = useCallback(async () => {
    stop()
    const sid = sessionIdRef.current
    if (sid) {
      try {
        await fetch(`/api/chat/sessions/${sid}/cancel`, { method: 'POST' })
      } catch { /* best effort */ }
    }
  }, [stop])

  return {
    messages,
    isStreaming: status === 'streaming' || status === 'submitted',
    composerState,
    error: error?.message ?? null,
    sendMessage: (content: string) => sendMessage({ text: content }),
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
    loadSessions()
  }, [loadSessions])

  return { sessions, loading, createSession, endSession, refresh: loadSessions }
}
