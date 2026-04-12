import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { formatDur } from '../lib/utils'

const SOURCE_STYLES: Record<string, { color: string; label: string }> = {
  cli: { color: 'var(--hud-success)', label: 'cli' },
  telegram: { color: 'var(--hud-secondary)', label: 'tg' },
  cron: { color: 'var(--hud-warning)', label: 'cron' },
}

export default function AgentsPanel() {
  const { data, isLoading } = useApi('/agents', 15000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title="Agents" className="col-span-full"><div className="glow text-[13px] animate-pulse">Scanning processes...</div></Panel>
  }

  const processes = data.processes || []
  const live = processes.filter((p: any) => p.running)
  const idle = processes.filter((p: any) => !p.running)
  const recentSessions = data.recent_sessions || []
  const alerts = data.operator_alerts || []
  const tmuxPanes = data.tmux_panes || []
  const inFlightCount = recentSessions.filter((s: any) => s.in_flight).length

  return (
    <>
      <Panel title={`Live Agents — ${data.live_count} live, ${idle.length} idle`}>
        {alerts.length > 0 && (
          <div className="mb-3">
            <div className="text-[13px] font-bold mb-1" style={{ color: 'var(--hud-warning)' }}>
              OPERATOR QUEUE — {alerts.length} waiting
            </div>
            {alerts.map((a: any, i: number) => (
              <div key={i} className="py-1 text-[13px]" style={{ borderLeft: '2px solid var(--hud-warning)' }}>
                <span style={{ color: 'var(--hud-warning)' }}>⚠</span>
                <span className="font-bold ml-1">{a.agent_name}</span>
                <span className="ml-1 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>[{a.alert_type}]</span>
                <span className="ml-2">"{a.summary}"</span>
                {a.jump_hint && <span className="ml-1 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>→ {a.jump_hint}</span>}
              </div>
            ))}
          </div>
        )}

        <div className="space-y-2">
          {live.map((proc: any, i: number) => (
            <div key={`${proc.name}-${proc.pid}-${i}`} className="p-2" style={{ background: 'var(--hud-bg-panel)', borderLeft: '3px solid var(--hud-success)' }}>
              <div className="flex items-center gap-2 text-[13px] flex-wrap">
                <span style={{ color: 'var(--hud-success)' }}>▸</span>
                <span className="font-bold">{proc.name}</span>
                {proc.pid && <span className="text-[13px] tabular-nums" style={{ color: 'var(--hud-text-dim)' }}>[{proc.pid}]</span>}
                <span className="text-[13px]" style={{ color: 'var(--hud-success)' }}>alive</span>
                {proc.uptime && <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>up {proc.uptime}</span>}
                {proc.mem_mb && <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{proc.mem_mb} MB</span>}
                {proc.cwd && <span className="text-[13px] truncate" style={{ color: 'var(--hud-text-dim)' }}>{proc.cwd}</span>}
                {proc.tmux_jump_hint && <span className="text-[13px]" style={{ color: 'var(--hud-accent)' }}>→ {proc.tmux_jump_hint}</span>}
              </div>
              {proc.cmdline && (
                <div className="text-[13px] truncate ml-5 mt-0.5" style={{ color: 'var(--hud-text-dim)' }}>
                  {proc.cmdline}
                </div>
              )}
            </div>
          ))}

          {idle.length > 0 && (
            <div className="text-[13px] mt-2">
              <div className="text-[13px] uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>Not running</div>
              <div className="flex flex-wrap gap-2">
                {idle.map((proc: any, i: number) => (
                  <span key={`${proc.name}-${i}`} className="px-2 py-0.5" style={{ background: 'var(--hud-bg-panel)', color: 'var(--hud-text-dim)' }}>
                    {proc.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {data.has_tmux && tmuxPanes.length > 0 && (
          <div className="mt-3 text-[13px]">
            <div className="uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>
              tmux panes — {tmuxPanes.length} total, {data.matched_pane_count} mapped
            </div>
            {data.unmatched_interesting_panes?.map((pane: any, i: number) => (
              <div key={i} style={{ color: 'var(--hud-text-dim)' }}>
                {pane.pane_id}  {pane.session_name}:{pane.window_index}.{pane.pane_index}  {pane.current_command}  (unmatched)
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title={`Recent Activity — ${inFlightCount} in flight`}>
        <div className="space-y-1">
          {recentSessions.map((sess: any, i: number) => {
            const style = SOURCE_STYLES[sess.source] || { color: 'var(--hud-text-dim)', label: sess.source }
            return (
              <div key={sess.session_id || i} className="p-2 text-[13px]" style={{ background: 'var(--hud-bg-panel)', borderLeft: `3px solid ${sess.in_flight ? 'var(--hud-warning)' : style.color}` }}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-1.5 py-0.5 text-[13px] flex-shrink-0" style={{ background: 'var(--hud-bg-hover)', color: style.color }}>
                    {style.label}
                  </span>
                  <span className="truncate flex-1 font-bold">{sess.title || 'untitled'}</span>
                  {sess.model && <span style={{ color: 'var(--hud-accent)' }}>{sess.model}</span>}
                  <span style={{ color: sess.in_flight ? 'var(--hud-warning)' : 'var(--hud-text-dim)' }}>
                    {sess.in_flight ? 'in flight' : 'completed'}
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-wrap mt-0.5" style={{ color: 'var(--hud-text-dim)' }}>
                  <span>{sess.started_at ? `${sess.started_at.slice(5, 10)} ${sess.started_at.slice(11, 16)}` : ''}</span>
                  <span>{sess.message_count}m</span>
                  {sess.tool_call_count > 0 && <span>{sess.tool_call_count}t</span>}
                  {sess.duration_minutes && <span>{formatDur(sess.duration_minutes)}</span>}
                </div>
              </div>
            )
          })}
        </div>
      </Panel>
    </>
  )
}
