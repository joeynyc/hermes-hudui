import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { formatDur } from '../lib/utils'
import { useLocale } from '../lib/i18n'

const SOURCE_STYLES: Record<string, { color: string; label: string }> = {
  cli: { color: 'var(--hud-success)', label: 'cli' },
  telegram: { color: 'var(--hud-secondary)', label: 'tg' },
  cron: { color: 'var(--hud-warning)', label: 'cron' },
}

export default function AgentsPanel() {
  const { t } = useLocale()
  const { data, isLoading } = useApi('/agents', 15000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title={t('agents.agents')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('agents.scanningProcesses')}</div></Panel>
  }

  const processes = data.processes || []
  const live = processes.filter((p: any) => p.running)
  const idle = processes.filter((p: any) => !p.running)
  const recentSessions = data.recent_sessions || []
  const alerts = data.operator_alerts || []
  const tmuxPanes = data.tmux_panes || []

  return (
    <>
      {/* Live processes */}
      <Panel title={`${t('agents.liveAgents')} — ${t('agents.liveCount', { count: data.live_count, idle: idle.length })}`}>
        {/* Operator alerts */}
        {alerts.length > 0 && (
          <div className="mb-3">
            <div className="text-[13px] font-bold mb-1" style={{ color: 'var(--hud-warning)' }}>
              {t('agents.operatorQueue')} — {alerts.length} {t('agents.waiting')}
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

        {/* Live agents */}
        <div className="space-y-2">
          {live.map((proc: any, i: number) => (
            <div key={`${proc.name}-${proc.pid}-${i}`} className="p-2" style={{ background: 'var(--hud-bg-panel)', borderLeft: '3px solid var(--hud-success)' }}>
              <div className="flex items-center gap-2 text-[13px]">
                <span style={{ color: 'var(--hud-success)' }}>▸</span>
                <span className="font-bold">{proc.name}</span>
                {proc.pid && <span className="text-[13px] tabular-nums" style={{ color: 'var(--hud-text-dim)' }}>[{proc.pid}]</span>}
                <span className="text-[13px]" style={{ color: 'var(--hud-success)' }}>{t('agents.alive')}</span>
                {proc.uptime && <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('agents.up')} {proc.uptime}</span>}
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

          {/* Idle agents */}
          {idle.length > 0 && (
            <div className="text-[13px] mt-2">
              <div className="text-[13px] uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>{t('agents.notRunning')}</div>
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

        {/* tmux panes if present */}
        {data.has_tmux && tmuxPanes.length > 0 && (
          <div className="mt-3 text-[13px]">
            <div className="uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>
              {t('agents.tmuxPanesTotalMapped', { total: tmuxPanes.length, mapped: data.matched_pane_count })}
            </div>
            {data.unmatched_interesting_panes?.map((pane: any, i: number) => (
              <div key={i} style={{ color: 'var(--hud-text-dim)' }}>
                {pane.pane_id}  {pane.session_name}:{pane.window_index}.{pane.pane_index}  {pane.current_command}  ({t('agents.unmatched')})
              </div>
            ))}
          </div>
        )}
      </Panel>

      {/* Recent sessions */}
      <Panel title={t('agents.recentActivityLast', { count: recentSessions.length })}>
        <div className="space-y-0.5">
          {recentSessions.map((sess: any, i: number) => {
            const style = SOURCE_STYLES[sess.source] || { color: 'var(--hud-text-dim)', label: sess.source }
            return (
              <div key={sess.session_id || i} className="flex items-center gap-2 py-1 text-[13px]"
                style={{ borderBottom: '1px solid var(--hud-border)' }}>
                <span className="text-[13px] tabular-nums w-[80px] flex-shrink-0" style={{ color: 'var(--hud-text-dim)' }}>
                  {sess.started_at ? `${sess.started_at.slice(5, 10)} ${sess.started_at.slice(11, 16)}` : ''}
                </span>
                <span className="px-1.5 py-0.5 text-[13px] flex-shrink-0" style={{ background: 'var(--hud-bg-panel)', color: style.color }}>
                  {style.label}
                </span>
                <span className="truncate flex-1">
                  {sess.title || t('agents.untitled')}
                </span>
                <span className="text-[13px] flex-shrink-0 tabular-nums" style={{ color: 'var(--hud-text-dim)' }}>
                  {sess.message_count}{t('agents.msg')}
                  {sess.tool_call_count > 0 && <> {sess.tool_call_count}{t('agents.tool')}</>}
                  {sess.duration_minutes && <span className="ml-1">{formatDur(sess.duration_minutes)}</span>}
                </span>
              </div>
            )
          })}
        </div>
      </Panel>
    </>
  )
}
