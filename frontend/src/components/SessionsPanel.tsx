import { useState, useCallback } from 'react'
import { useApi } from '../hooks/useApi'
import Panel, { Sparkline } from './Panel'
import MessageBubble from './chat/MessageBubble'
import { useTranslation } from '../i18n'

function sourceColor(source: string) {
  return source === 'telegram' ? 'var(--hud-accent)' : 'var(--hud-primary)'
}

const hoverOn = (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.background = 'var(--hud-bg-hover)' }
const hoverOff = (e: React.MouseEvent<HTMLButtonElement>) => { e.currentTarget.style.background = 'transparent' }

// ── Transcript viewer ──────────────────────────────────────────────────────────

function TranscriptViewer({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const { t } = useTranslation()
  const { data, isLoading } = useApi(`/sessions/${sessionId}/messages`, 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div
        className="flex flex-col w-full max-w-3xl mx-4 rounded"
        style={{
          background: 'var(--hud-bg-panel)',
          border: '1px solid var(--hud-border)',
          maxHeight: '80vh',
          boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2 shrink-0 border-b"
          style={{ borderColor: 'var(--hud-border)' }}
        >
          <div>
            <span className="text-[13px] uppercase tracking-widest" style={{ color: 'var(--hud-primary)' }}>
              {data?.title || sessionId.slice(0, 8)}
            </span>
            {data?.source && (
              <span className="ml-2 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
                {data.source}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-[13px] px-2 py-0.5 cursor-pointer"
            style={{ color: 'var(--hud-text-dim)' }}
          >
            ✕ {t('sessions.close')}
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {isLoading && (
            <div className="text-[13px] animate-pulse" style={{ color: 'var(--hud-text-dim)' }}>
              {t('sessions.loadingTranscript')}
            </div>
          )}
          {!isLoading && data?.messages?.length === 0 && (
            <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
              {t('sessions.noMessages')}
            </div>
          )}
          {!isLoading && data?.messages?.map((msg: any) => (
            <div key={msg.id}>
              <MessageBubble role={msg.role} content={msg.content} />
              {msg.token_count > 0 && (
                <div className="text-[10px] mb-1 text-right" style={{ color: 'var(--hud-text-dim)', marginTop: '-8px' }}>
                  {msg.token_count.toLocaleString()} {t('sessions.tokens')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Search results ─────────────────────────────────────────────────────────────

function SearchResults({ query, onSelect }: { query: string; onSelect: (id: string) => void }) {
  const { data, isLoading } = useApi(`/sessions/search?q=${encodeURIComponent(query)}`, 0)

  if (isLoading) {
    return <div className="text-[13px] animate-pulse py-2" style={{ color: 'var(--hud-text-dim)' }}>Searching...</div>
  }

  const results = data || []

  if (!results.length) {
    return <div className="text-[13px] py-2" style={{ color: 'var(--hud-text-dim)' }}>No results for "{query}"</div>
  }

  return (
    <div className="space-y-0.5">
      {results.map((r: any) => (
        <button
          key={r.session_id}
          onClick={() => onSelect(r.session_id)}
          className="w-full text-left px-2 py-1.5 text-[13px] cursor-pointer"
          style={{
            borderBottom: '1px solid var(--hud-border)',
            background: 'transparent',
          }}
          onMouseEnter={hoverOn}
          onMouseLeave={hoverOff}
        >
          <div className="flex items-center gap-2">
            <span
              className="w-1.5 h-1.5 rounded-full flex-shrink-0"
              style={{ background: sourceColor(r.source) }}
            />
            <span className="flex-1 truncate">{r.title}</span>
            <span className="text-[11px] shrink-0" style={{ color: 'var(--hud-text-dim)' }}>
              {r.match_type === 'content' ? 'content' : 'title'}
            </span>
          </div>
          {r.snippet && (
            <div className="mt-0.5 ml-3.5 text-[11px] truncate" style={{ color: 'var(--hud-text-dim)' }}>
              {r.snippet}
            </div>
          )}
        </button>
      ))}
    </div>
  )
}

// ── Main panel ─────────────────────────────────────────────────────────────────

export default function SessionsPanel() {
  const { t } = useTranslation()
  const { data, isLoading } = useApi('/sessions', 30000)
  const [activeTranscript, setActiveTranscript] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')

  const handleSearch = useCallback((e: React.SyntheticEvent) => {
    e.preventDefault()
    setSubmittedQuery(searchQuery.trim())
  }, [searchQuery])

  const handleClearSearch = useCallback(() => {
    setSearchQuery('')
    setSubmittedQuery('')
  }, [])

  if (isLoading && !data) {
    return <Panel title={t('sessions.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('sessions.loading')}</div></Panel>
  }

  const sessions = data.sessions || []
  const dailyStats = data.daily_stats || []
  const bySource = data.by_source || {}
  const dailyMessages = dailyStats.map((d: any) => d.messages)
  const dailySessions = dailyStats.map((d: any) => d.sessions)

  const showSearch = submittedQuery.length > 0

  return (
    <>
      {/* Transcript modal */}
      {activeTranscript && (
        <TranscriptViewer
          sessionId={activeTranscript}
          onClose={() => setActiveTranscript(null)}
        />
      )}

      <Panel title="Session Activity" className="col-span-2">
        <div className="flex gap-6 mb-3 text-[13px]">
          <div>
            <span className="stat-value text-base">{data.total_sessions || 0}</span>
            <span className="stat-label ml-1">sessions</span>
          </div>
          <div>
            <span className="stat-value text-base">{(data.total_messages || 0).toLocaleString()}</span>
            <span className="stat-label ml-1">messages</span>
          </div>
          <div>
            <span className="stat-value text-base">{(data.total_tokens || 0).toLocaleString()}</span>
            <span className="stat-label ml-1">tokens</span>
          </div>
          {Object.entries(bySource).map(([src, count]: any) => (
            <div key={src}>
              <span style={{ color: 'var(--hud-accent)' }}>{count}</span>
              <span className="stat-label ml-1">{src}</span>
            </div>
          ))}
        </div>
        <div className="mb-2">
          <div className="text-[13px] uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>Messages/day</div>
          <Sparkline values={dailyMessages} width={500} height={50} />
        </div>
        <div>
          <div className="text-[13px] uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>Sessions/day</div>
          <Sparkline values={dailySessions} width={500} height={30} />
        </div>
      </Panel>

      <Panel title={t('sessions.title')}>
        {/* Search bar */}
        <form onSubmit={handleSearch} className="flex gap-1 mb-2">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder={t('sessions.searchSessions')}
            className="flex-1 px-2 py-1 text-[13px] outline-none"
            style={{
              background: 'var(--hud-bg-deep)',
              border: '1px solid var(--hud-border)',
              color: 'var(--hud-text)',
            }}
          />
          {submittedQuery ? (
            <button
              type="button"
              onClick={handleClearSearch}
              className="px-2 py-1 text-[12px] cursor-pointer"
              style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}
            >
              ✕
            </button>
          ) : (
            <button
              type="submit"
              disabled={!searchQuery.trim()}
              className="px-2 py-1 text-[12px] cursor-pointer disabled:opacity-40"
              style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }}
            >
              Search
            </button>
          )}
        </form>

        {/* Search results or session list */}
        {showSearch ? (
          <SearchResults query={submittedQuery} onSelect={id => { setActiveTranscript(id); handleClearSearch() }} />
        ) : (
          <div className="space-y-0.5 text-[13px]">
            {sessions.slice(0, 15).map((s: any) => (
              <button
                key={s.id}
                onClick={() => setActiveTranscript(s.id)}
                className="w-full flex items-center gap-2 py-0.5 text-left cursor-pointer"
                style={{ borderBottom: '1px solid var(--hud-border)', background: 'transparent' }}
                onMouseEnter={hoverOn}
                onMouseLeave={hoverOff}
                title="Click to read transcript"
              >
                <span className="w-2 h-2 rounded-full flex-shrink-0"
                  style={{ background: sourceColor(s.source) }} />
                <span className="flex-1 truncate">{s.title || s.id.slice(0, 8)}</span>
                <span className="tabular-nums" style={{ color: 'var(--hud-text-dim)' }}>
                  {s.message_count}m {s.tool_call_count}t
                </span>
              </button>
            ))}
          </div>
        )}
      </Panel>
    </>
  )
}
