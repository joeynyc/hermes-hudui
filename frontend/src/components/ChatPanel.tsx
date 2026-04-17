import { useState, useEffect, useCallback, useRef } from 'react'
import Panel from './Panel'
import { useChat, useChatAvailability, useChatSessions, loadSavedSessions, loadMessages, saveMessages, removeMessages } from '../hooks/useChat'
import SessionSidebar from './chat/SessionSidebar'
import MessageThread from './chat/MessageThread'
import Composer from './chat/Composer'

export default function ChatPanel() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const { available: chatAvailable, loading: checkingAvailability } = useChatAvailability()
  const { sessions, loading: loadingSessions, createSession, refresh: refreshSessions } = useChatSessions()
  const {
    messages,
    isStreaming,
    composerState,
    error,
    sendMessage,
    cancelStream,
    regenerate,
  } = useChat(activeSessionId)

  const handleCreateSession = useCallback(async () => {
    const session = await createSession()
    if (session) {
      setActiveSessionId(session.id)
    }
  }, [createSession])

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (activeSessionId) {
        await sendMessage(content)
      }
    },
    [activeSessionId, sendMessage]
  )

  const restoringRef = useRef(false)

  // Re-create backend sessions for persisted sessions lost on server restart
  useEffect(() => {
    if (checkingAvailability || !chatAvailable || loadingSessions || restoringRef.current) return

    const saved = loadSavedSessions()

    if (sessions.length === 0 && saved.length > 0) {
      // Backend lost sessions (server restart) — re-create and migrate messages
      restoringRef.current = true
      ;(async () => {
        try {
          const idMap: Array<{ oldId: string; newId: string }> = []
          for (const s of saved) {
            const created = await createSession()
            if (created) {
              idMap.push({ oldId: s.id, newId: created.id })
              // Migrate localStorage messages from old ID to new ID
              const msgs = loadMessages(s.id)
              if (msgs.length > 0) {
                saveMessages(created.id, msgs)
              }
              removeMessages(s.id)
            }
          }
          if (idMap.length > 0) {
            setActiveSessionId(idMap[0].newId)
          }
        } finally {
          restoringRef.current = false
        }
      })()
    } else if (sessions.length === 0 && saved.length === 0) {
      // Truly fresh — create initial session
      handleCreateSession()
    }
  }, [checkingAvailability, chatAvailable, sessions.length, loadingSessions, createSession, handleCreateSession])

  // Auto-select first session when sessions exist but none is active
  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) {
      setActiveSessionId(sessions[0].id)
    }
  }, [activeSessionId, sessions])

  // Show loading while checking availability
  if (checkingAvailability) {
    return (
      <Panel title="Chat" className="col-span-full h-full">
        <div className="h-full flex items-center justify-center">
          <div className="text-[13px] animate-pulse" style={{ color: 'var(--hud-text-dim)' }}>
            Checking chat availability...
          </div>
        </div>
      </Panel>
    )
  }

  // Show unavailable state
  if (!chatAvailable) {
    return (
      <Panel title="Chat" className="col-span-full h-full">
        <div className="h-full flex items-center justify-center p-4">
          <div className="text-center max-w-md">
            <div className="text-[14px] mb-2" style={{ color: 'var(--hud-error)' }}>
              Chat Not Available
            </div>
            <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
              To enable chat, either:
              <ul className="mt-2 space-y-1 text-left">
                <li>• Install hermes-agent: <code className="text-[var(--hud-primary)]">pip install hermes-agent</code></li>
                <li>• Or start Hermes in a tmux session: <code className="text-[var(--hud-primary)]">tmux new -s hermes</code></li>
              </ul>
            </div>
          </div>
        </div>
      </Panel>
    )
  }

  // Show error state
  if (error) {
    return (
      <Panel title="Chat" className="col-span-full h-full">
        <div className="h-full flex flex-col">
          <div className="p-2 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
            Error: {error}
          </div>
          <button
            onClick={refreshSessions}
            className="m-2 px-3 py-1.5 text-[12px] cursor-pointer"
            style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)' }}
          >
            Retry
          </button>
        </div>
      </Panel>
    )
  }

  return (
    <Panel title="Chat" className="h-full" noPadding>
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-48 shrink-0 overflow-hidden">
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={setActiveSessionId}
            onCreate={handleCreateSession}
            loading={loadingSessions}
          />
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {activeSessionId ? (
            <>
              <MessageThread messages={messages} isStreaming={isStreaming} onRegenerate={(id) => regenerate({ messageId: id })} />
              <Composer
                onSend={handleSendMessage}
                onCancel={cancelStream}
                isStreaming={isStreaming}
                model={composerState.model}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center" style={{ color: 'var(--hud-text-dim)' }}>
                <div className="text-[14px] mb-1">Select or create a session</div>
                <div className="text-[12px]">Choose from the sidebar to start chatting</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  )
}
