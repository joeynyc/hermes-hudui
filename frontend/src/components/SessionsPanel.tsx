import { useApi } from '../hooks/useApi'
import Panel, { Sparkline } from './Panel'
import { profileName, withProfile } from '../lib/profile'

export default function SessionsPanel({ selectedProfile }: { selectedProfile: string }) {
  const { data, isLoading } = useApi(withProfile('/sessions', selectedProfile), 30000)

  if (isLoading || !data) {
    return <Panel title="Sessions" className="col-span-full"><div className="glow text-[13px] animate-pulse">Loading...</div></Panel>
  }

  const sessions = data.sessions || []
  const dailyStats = data.daily_stats || []
  const bySource = data.by_source || {}
  const dailyMessages = dailyStats.map((d: any) => d.messages)
  const dailySessions = dailyStats.map((d: any) => d.sessions)

  return (
    <>
      <Panel title={`Session Activity · ${profileName(data?.profile || selectedProfile)}`} className="col-span-2">
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

      <Panel title={`Recent Sessions · ${profileName(data?.profile || selectedProfile)}`}>
        <div className="space-y-0.5 text-[13px]">
          {sessions.slice(0, 15).map((s: any) => (
            <div key={s.id} className="flex items-center gap-2 py-0.5" style={{ borderBottom: '1px solid var(--hud-border)' }}>
              <span className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ background: s.source === 'telegram' ? 'var(--hud-accent)' : 'var(--hud-primary)' }} />
              <span className="flex-1 truncate">{s.title || s.id.slice(0, 8)}</span>
              <span className="tabular-nums" style={{ color: 'var(--hud-text-dim)' }}>
                {s.message_count}m {s.tool_call_count}t
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </>
  )
}
