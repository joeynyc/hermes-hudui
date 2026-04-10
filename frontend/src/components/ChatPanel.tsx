import { useState, useRef, useEffect, useCallback } from 'react'
import Panel from './Panel'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: number
}

interface ChatSession {
  id: string
  title: string
  started_at: number
  msg_count: number
}

interface ChatPanelProps {
  profile: string
}

export default function ChatPanel({ profile }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  
  const scrollRef = useRef<HTMLDivElement>(null)

  // States for error handling
  const [loadError, setLoadError] = useState<string | null>(null)

  // Load sessions
  const loadSessions = useCallback(async () => {
    setLoadError(null)
    try {
      const resp = await fetch(`/api/chat/sessions?profile=${profile}`)
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const data = await resp.json()
      // The new backend returns an array directly, but we handle both for safety
      setSessions(Array.isArray(data) ? data : data.sessions || [])
    } catch (e) {
      console.error('Failed to load sessions', e)
      setLoadError(e instanceof Error ? e.message : 'Connection failed')
    }
  }, [profile])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  // Load history if session selected
  useEffect(() => {
    if (currentSessionId) {
      fetch(`/api/chat/history?session_id=${currentSessionId}&profile=${profile}`)
        .then(r => r.json())
        .then(data => {
           // Handle direct array or wrapped object
           setMessages(Array.isArray(data) ? data : data.messages || [])
        })
        .catch(e => {
          console.error('History load failed', e)
          setMessages([{ role: 'system', content: `Failed to load history: ${e.message}` }])
        })
    } else {
      setMessages([])
    }
  }, [currentSessionId, profile])

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }

  useEffect(scrollToBottom, [messages])

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!input.trim() || isStreaming) return

    const userMsg: Message = { role: 'user', content: input }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setIsStreaming(true)

    // Add placeholder for assistant
    const assistantMsg: Message = { role: 'assistant', content: '' }
    setMessages([...newMessages, assistantMsg])

    try {
      const response = await fetch(`/api/chat/chat?profile=${profile}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: newMessages,
          stream: true,
          session_id: currentSessionId
        })
      })

      if (!response.body) throw new Error('No body')
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantContent = ''
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value, { stream: true })
        buffer += chunk
        
        const lines = buffer.split('\n')
        // Keep the last partial line in the buffer
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          const trimmedLine = line.trim()
          if (trimmedLine.startsWith('data: ')) {
            const dataStr = trimmedLine.slice(6)
            if (dataStr === '[DONE]') break
            
            try {
              const data = JSON.parse(dataStr)
              const content = data.choices?.[0]?.delta?.content
              if (content) {
                assistantContent += content
                setMessages(prev => {
                  const updated = [...prev]
                  const lastIdx = updated.length - 1
                  if (updated[lastIdx].role === 'assistant') {
                    updated[lastIdx] = { ...updated[lastIdx], content: assistantContent }
                  }
                  return updated
                })
              }
            } catch (e) {
              // Ignore partial JSON
            }
          }
        }
      }
    } catch (e) {
      console.error('Chat error', e)
      setMessages(prev => [...prev, { role: 'system', content: `Error: ${e instanceof Error ? e.message : String(e)}` }])
    } finally {
      setIsStreaming(false)
      loadSessions()
    }
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <Panel title="Chat" className="flex flex-col h-[700px] overflow-hidden p-0 border-0">
      <div className="flex flex-1 overflow-hidden h-full">
        {/* Sessions Sidebar */}
        <div className="w-56 bg-white/5 border-r border-white/10 flex flex-col shrink-0">
          <button 
            onClick={() => setCurrentSessionId(null)}
            className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors hover:bg-white/10 border-b border-white/10 ${!currentSessionId ? 'bg-indigo-600/20 text-indigo-400' : 'text-zinc-400'}`}
          >
            + New Chat
          </button>
          <div className="flex-1 overflow-y-auto">
            {loadError && (
              <div className="p-4 text-center">
                <p className="text-[10px] text-red-400 mb-2">Error: {loadError}</p>
                <button 
                  onClick={() => loadSessions()}
                  className="text-[10px] bg-white/5 hover:bg-white/10 px-2 py-1 rounded border border-white/10 transition-colors"
                >
                  Retry
                </button>
              </div>
            )}
            {!loadError && sessions.length === 0 && (
              <div className="p-4 text-center text-[10px] text-zinc-500 italic">
                No sessions found
              </div>
            )}
            {sessions.map(s => (
              <button
                key={s.id}
                onClick={() => setCurrentSessionId(s.id)}
                className={`w-full text-left px-4 py-3 text-xs border-b border-white/5 transition-colors hover:bg-white/5 ${currentSessionId === s.id ? 'bg-white/10' : ''}`}
              >
                <div className={`font-medium truncate mb-1 ${currentSessionId === s.id ? 'text-white' : 'text-zinc-400'}`}>
                  {s.title}
                </div>
                <div className="flex items-center justify-between opacity-50 text-[10px]">
                  <span>{new Date(s.started_at * 1000).toLocaleDateString()}</span>
                  <span>{s.msg_count} msgs</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col h-full bg-black/20">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-zinc-600 space-y-3 opacity-60">
                <div className="text-5xl">💬</div>
                <div className="text-center">
                  <p className="text-sm font-medium">Hermes HUD Chat</p>
                  <p className="text-xs">Profile: <span className="text-indigo-400">{profile}</span></p>
                </div>
              </div>
            )}
            
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} group animate-in fade-in slide-in-from-bottom-2`}>
                <div className={`relative max-w-[90%] rounded-xl px-4 py-3 text-sm shadow-xl ${
                  m.role === 'user' 
                    ? 'bg-indigo-600 text-white rounded-tr-none' 
                    : m.role === 'system'
                      ? 'bg-red-900/40 text-red-200 border border-red-800/50'
                      : 'bg-[#1e1e1e] text-zinc-200 border border-white/5 rounded-tl-none'
                }`}>
                  <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                  
                  {m.role !== 'system' && !isStreaming && (
                    <button 
                      onClick={() => handleCopy(m.content)}
                      className="absolute top-2 right-2 p-1 rounded bg-black/40 text-white/40 opacity-0 group-hover:opacity-100 transition-opacity hover:text-white"
                      title="Copy message"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            ))}
            {isStreaming && (
              <div className="flex justify-start">
                <div className="bg-[#1e1e1e] border border-white/5 text-zinc-500 rounded-xl px-4 py-3 text-xs animate-pulse flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  <span>Hermes is generating...</span>
                </div>
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="p-4 bg-black/40 border-t border-white/10">
            <div className="flex gap-2">
              <input
                type="text"
                autoFocus
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Message Hermes..."
                className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all placeholder:text-zinc-600"
                disabled={isStreaming}
              />
              <button 
                type="submit"
                disabled={isStreaming || !input.trim()}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:hover:bg-indigo-600 text-white px-5 rounded-lg text-sm font-medium transition-all shadow-lg active:scale-95 flex items-center gap-2"
              >
                <span>Send</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </form>
        </div>
      </div>
    </Panel>
  )
}
