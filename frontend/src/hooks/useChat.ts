import { useState, useCallback, useRef, useEffect } from 'react'

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  status: 'running' | 'complete' | 'error'
  result?: unknown
  error?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  toolCalls?: ToolCall[]
  reasoning?: string
  timestamp: Date
  isStreaming?: boolean
}

export interface ComposerState {
  model: string
  isStreaming: boolean
  contextTokens: number
}

interface StreamingEvent {
  type: string
  data: Record<string, unknown>
}

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [composerState, setComposerState] = useState<ComposerState>({
    model: 'unknown',
    isStreaming: false,
    contextTokens: 0,
  })
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const currentAssistantMessageRef = useRef<string>('')
  const currentToolCallsRef = useRef<Record<string, ToolCall>>({})
  // Client-side message cache: sessionId → messages
  const messageCacheRef = useRef<Map<string, ChatMessage[]>>(new Map())
  const prevSessionIdRef = useRef<string | null>(null)

  // On session switch: save previous session's messages, restore new session's
  useEffect(() => {
    const prevId = prevSessionIdRef.current

    // Save messages for the outgoing session
    if (prevId && prevId !== sessionId) {
      messageCacheRef.current.set(prevId, messages)
    }

    // Close any open stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    // Reset transient state
    setIsStreaming(false)
    setError(null)
    currentAssistantMessageRef.current = ''
    currentToolCallsRef.current = {}

    // Restore cached messages for the incoming session (or empty for new sessions)
    if (sessionId) {
      setMessages(messageCacheRef.current.get(sessionId) ?? [])
    } else {
      setMessages([])
    }

    prevSessionIdRef.current = sessionId
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Keep cache in sync with current messages as they arrive
  useEffect(() => {
    if (sessionId) {
      messageCacheRef.current.set(sessionId, messages)
    }
  }, [sessionId, messages])

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  const sendMessage = useCallback(async (content: string) => {
    if (!sessionId) {
      setError('No active session')
      return
    }

    setError(null)
    setIsStreaming(true)
    currentAssistantMessageRef.current = ''
    currentToolCallsRef.current = {}

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])

    // Create placeholder assistant message
    const assistantMessageId = `assistant-${Date.now()}`
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      toolCalls: [],
    }
    setMessages(prev => [...prev, assistantMessage])

    try {
      // First POST to send the message
      const response = await fetch(`/api/chat/sessions/${sessionId}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to send message')
      }

      // Then open SSE stream
      const eventSource = new EventSource(`/api/chat/sessions/${sessionId}/stream`)
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        const data: StreamingEvent = JSON.parse(event.data)

        switch (data.type) {
          case 'token':
            currentAssistantMessageRef.current += (data.data.text as string) || ''
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMessageId
                  ? { ...msg, content: currentAssistantMessageRef.current }
                  : msg
              )
            )
            break

          case 'tool_start':
            const toolId = data.data.id as string
            const toolName = data.data.name as string
            const toolArgs = data.data.arguments as Record<string, unknown>
            currentToolCallsRef.current[toolId] = {
              id: toolId,
              name: toolName,
              arguments: toolArgs,
              status: 'running',
            }
            updateAssistantToolCalls(assistantMessageId)
            break

          case 'tool_end':
            const endToolId = data.data.id as string
            const toolResult = data.data.result
            const toolError = data.data.error as string | undefined
            if (currentToolCallsRef.current[endToolId]) {
              currentToolCallsRef.current[endToolId].status = toolError ? 'error' : 'complete'
              currentToolCallsRef.current[endToolId].result = toolResult
              currentToolCallsRef.current[endToolId].error = toolError
            }
            updateAssistantToolCalls(assistantMessageId)
            break

          case 'reasoning':
            const reasoningContent = data.data.content as string
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMessageId
                  ? { ...msg, reasoning: reasoningContent }
                  : msg
              )
            )
            break

          case 'info':
            // TMUX mode info message
            console.log('Chat info:', data.data.message)
            break

          case 'done':
            setIsStreaming(false)
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMessageId
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            )
            eventSource.close()
            break

          case 'error':
            setError(data.data.message as string)
            setIsStreaming(false)
            setMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMessageId
                  ? { ...msg, isStreaming: false, content: msg.content || 'Error: ' + data.data.message }
                  : msg
              )
            )
            eventSource.close()
            break
        }
      }

      eventSource.onerror = () => {
        // Connection closed or error
        if (isStreaming) {
          setIsStreaming(false)
          setMessages(prev =>
            prev.map(msg =>
              msg.id === assistantMessageId
                ? { ...msg, isStreaming: false }
                : msg
            )
          )
        }
        eventSource.close()
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setIsStreaming(false)
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, isStreaming: false, content: msg.content || 'Error sending message' }
            : msg
        )
      )
    }
  }, [sessionId, isStreaming])

  const updateAssistantToolCalls = (assistantMessageId: string) => {
    const toolCalls = Object.values(currentToolCallsRef.current)
    setMessages(prev =>
      prev.map(msg =>
        msg.id === assistantMessageId
          ? { ...msg, toolCalls }
          : msg
      )
    )
  }

  const loadHistory = useCallback(async () => {
    // History is managed client-side via messageCacheRef.
    // The backend does not persist message history, so this is a no-op.
  }, [])

  const loadComposerState = useCallback(async () => {
    if (!sessionId) return

    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}/composer`)
      if (response.ok) {
        const state = await response.json()
        setComposerState({
          model: state.model,
          isStreaming: state.is_streaming,
          contextTokens: state.context_tokens,
        })
      }
    } catch (err) {
      console.error('Failed to load composer state:', err)
    }
  }, [sessionId])

  return {
    messages,
    isStreaming,
    composerState,
    error,
    sendMessage,
    loadHistory,
    loadComposerState,
  }
}

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

export function useChatSessions() {
  const [sessions, setSessions] = useState<Array<{ id: string; title: string; backend_type: string; is_active: boolean }>>([])
  const [loading, setLoading] = useState(false)

  const loadSessions = useCallback(async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/chat/sessions')
      if (response.ok) {
        const data = await response.json()
        setSessions(data)
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
