import { useEffect, useRef, useCallback, useState } from 'react'
import { mutate } from 'swr'

interface WebSocketMessage {
  type: 'data_changed' | 'cache_invalidate' | 'connected' | 'disconnected'
  data_types?: string[]
  data_type?: string
  keys?: string[]
  paths?: string[]
}

type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseWebSocketReturn {
  status: WebSocketStatus
  lastMessage: WebSocketMessage | null
  sendMessage: (data: string) => void
}

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`
const HEALTH_DEBOUNCE_MS = 750
const HEALTH_MIN_REFRESH_MS = 3000

export function useWebSocket(): UseWebSocketReturn {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected')
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const healthRefreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastHealthRefreshRef = useRef(0)
  // Reconnect calls back into `connect`; going through a ref keeps the callback
  // from referencing its own binding before it is declared.
  const connectRef = useRef<() => void>(() => {})

  const revalidateHealth = useCallback(() => {
    if (document.visibilityState === 'hidden') return

    const now = Date.now()
    const elapsed = now - lastHealthRefreshRef.current
    const delay = elapsed >= HEALTH_MIN_REFRESH_MS
      ? HEALTH_DEBOUNCE_MS
      : HEALTH_MIN_REFRESH_MS - elapsed

    if (healthRefreshTimeoutRef.current) {
      clearTimeout(healthRefreshTimeoutRef.current)
    }

    healthRefreshTimeoutRef.current = setTimeout(() => {
      lastHealthRefreshRef.current = Date.now()
      mutate(
        (key) => typeof key === 'string' && key.startsWith('/api/health'),
        undefined,
        {
          revalidate: true,
          rollbackOnError: true,
          populateCache: true,
        }
      )
    }, delay)
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connected')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        // Handle plain text messages (like "pong") - skip them
        if (!event.data.startsWith('{')) {
          return
        }
        const data: WebSocketMessage = JSON.parse(event.data)
        setLastMessage(data)

        // Handle data change notifications
        if (data.type === 'data_changed') {
          const changedTypes = data.data_types || (data.data_type ? [data.data_type] : [])
          if (!changedTypes.length) return

          // Map data types to API paths and trigger SWR revalidation
          const typeToPath: Record<string, string> = {
            sessions: '/sessions',
            skills: '/skills',
            memory: '/state',
            user: '/state',
            patterns: '/patterns',
            profiles: '/profiles',
            cron: '/cron',
            projects: '/projects',
            corrections: '/corrections',
            state: '/state',
            timeline: '/timeline',
            snapshots: '/snapshots',
            gateway: '/gateway',
            plugins: '/plugins',
            'model-info': '/model-info',
          }

          const healthTypes = new Set(['health', 'config', 'gateway', 'plugins', 'model-info'])

          // Silently revalidate matching SWR keys (keep stale data, update in background)
          changedTypes.forEach((dataType) => {
            if (healthTypes.has(dataType)) {
              revalidateHealth()
            }

            const path = typeToPath[dataType]
            if (path) {
              mutate(
                (key) => typeof key === 'string' && key.startsWith(`/api${path}`),
                undefined,
                {
                  revalidate: true,
                  rollbackOnError: true,
                  populateCache: true,
                }
              )
            }
          })

          // Also revalidate dashboard silently
          mutate(
            (key) => typeof key === 'string' && key.startsWith('/api/dashboard'),
            undefined,
            {
              revalidate: true,
              rollbackOnError: true,
              populateCache: true,
            }
          )
        }
      } catch (err) {
        console.warn('[WS] Failed to parse message:', err)
      }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      wsRef.current = null

      // Exponential backoff reconnect
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000)
      reconnectAttemptsRef.current++

      reconnectTimeoutRef.current = setTimeout(() => {
        connectRef.current()
      }, delay)
    }

    ws.onerror = () => {
      setStatus('error')
    }
  }, [revalidateHealth])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const sendMessage = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data)
    }
  }, [])

  useEffect(() => {
    connect()

    // Heartbeat to keep connection alive
    const heartbeat = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 30000)

    return () => {
      clearInterval(heartbeat)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (healthRefreshTimeoutRef.current) {
        clearTimeout(healthRefreshTimeoutRef.current)
      }
      wsRef.current?.close()
    }
  }, [connect])

  return { status, lastMessage, sendMessage }
}
