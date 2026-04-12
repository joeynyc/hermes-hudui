import { useApi } from '../hooks/useApi'
import Panel, { CapacityBar } from './Panel'
import { useLocale } from '../lib/i18n'
import { timeAgo, formatTokens } from '../lib/utils'

function StatusDot({ status }: { status: string }) {
  const color = status === 'active' || status === 'running'
    ? 'var(--hud-success)'
    : status === 'inactive' || status === 'stopped'
    ? 'var(--hud-error)'
    : status === 'n/a'
    ? 'var(--hud-text-dim)'
    : 'var(--hud-warning)'

  return <span style={{ color }}>●</span>
}

function ProfileCard({ p, t }: { p: any; t: (k: string) => string }) {
  return (
    <div className="p-4" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      {/* Header: name + badge + status */}
      <div className="flex items-center gap-2 mb-3">
        <StatusDot status={p.gateway_status} />
        <span className="font-bold text-[14px]" style={{ color: 'var(--hud-primary)' }}>
          {p.name}
        </span>
        {p.is_default && <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>({t('profiles.default')})</span>}
        <span className="text-[13px] px-1.5 py-0.5 ml-auto"
          style={{ background: 'var(--hud-bg-hover)', color: p.is_local ? 'var(--hud-secondary)' : 'var(--hud-accent)' }}>
          {p.is_local ? t('profiles.local') : p.provider}
        </span>
        {p.gateway_status === 'active' && (
          <span className="text-[13px]" style={{ color: 'var(--hud-success)' }}>{t('profiles.gatewayUp')}</span>
        )}
        {p.server_status === 'running' && (
          <span className="text-[13px]" style={{ color: 'var(--hud-success)' }}>{t('profiles.serverUp')}</span>
        )}
      </div>

      {/* Model & Backend */}
      <div className="space-y-1 text-[13px] mb-3">
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.model')}</span>
          <span>
            <span className="font-bold">{p.model || t('profiles.notSet')}</span>
            {p.provider && <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.via')} {p.provider}</span>}
          </span>
        </div>

        {p.base_url && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.backend')}</span>
            <span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{p.base_url}</span>
              {' '}<StatusDot status={p.server_status} />
            </span>
          </div>
        )}

        {p.context_length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.context')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.context_length.toLocaleString()} {t('profiles.tokens')}</span>
          </div>
        )}

        {p.skin && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.skin')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.skin}</span>
          </div>
        )}

        {p.soul_summary && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.soul')}</span>
            <span className="italic" style={{ color: 'var(--hud-text)' }}>{p.soul_summary.slice(0, 80)}{p.soul_summary.length > 80 ? '...' : ''}</span>
          </div>
        )}
      </div>

      {/* Usage stats */}
      <div className="text-[13px] mb-3 py-2" style={{ borderTop: '1px solid var(--hud-border)', borderBottom: '1px solid var(--hud-border)' }}>
        <div className="grid grid-cols-3 gap-2 mb-2">
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.session_count}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.sessionCount')}</span>
          </div>
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.message_count.toLocaleString()}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.messageCount')}</span>
          </div>
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.tool_call_count.toLocaleString()}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.toolCount')}</span>
          </div>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.tokens')}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>
            {formatTokens(p.total_tokens)} {t('profiles.total')} ({formatTokens(p.total_input_tokens)} {t('profiles.in')} / {formatTokens(p.total_output_tokens)} {t('profiles.out')})
          </span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.active')}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{timeAgo(p.last_active)}</span>
        </div>
      </div>

      {/* Memory */}
      <div className="mb-3">
        <CapacityBar value={p.memory_chars || 0} max={p.memory_max_chars || 2200} label={t('profiles.memory')} />
        <div className="text-[13px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
          {p.memory_entries} {t('profiles.entries2')}, {p.memory_chars}/{p.memory_max_chars} {t('profiles.chars')}
        </div>
        <CapacityBar value={p.user_chars || 0} max={p.user_max_chars || 1375} label={t('profiles.user2')} />
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          {p.user_entries} {t('profiles.entries2')}, {p.user_chars}/{p.user_max_chars} {t('profiles.chars')}
        </div>
      </div>

      {/* Skills, Cron, Toolsets */}
      <div className="space-y-1 text-[13px]">
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.skills')}</span>
          <span>
            <span className="font-bold">{p.skill_count}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> · {t('profiles.cronJobs2')} </span>
            <span className="font-bold">{p.cron_job_count}</span>
          </span>
        </div>

        {p.toolsets?.length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.toolsets')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.toolsets.join(', ')}</span>
          </div>
        )}

        {p.compression_enabled && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.compress')}</span>
            <span>
              <span style={{ color: 'var(--hud-success)' }}>{t('profiles.on')}</span>
              {p.compression_model && <span style={{ color: 'var(--hud-text-dim)' }}> · {p.compression_model}</span>}
            </span>
          </div>
        )}

        {/* Services */}
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.gateway')}</span>
          <span><StatusDot status={p.gateway_status} /> {p.gateway_status}
            <span className="ml-3">{t('profiles.server')} <StatusDot status={p.server_status} /> {p.server_status}</span>
          </span>
        </div>

        {/* API Keys */}
        {p.api_keys?.length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.keys')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.api_keys.join(', ')}</span>
          </div>
        )}

        {/* Alias */}
        {p.has_alias && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.alias')}</span>
            <span>
              <span style={{ color: 'var(--hud-success)' }}>{p.name}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.onPath')}</span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ProfilesPanel() {
  const { t } = useLocale()
  const { data, isLoading } = useApi('/profiles', 30000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title={t('profiles.profiles')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('profiles.loading')}</div></Panel>
  }

  const profiles = data.profiles || []

  return (
    <Panel title={`${t('profiles.agentProfiles')} — ${data.total || 0} ${t('profiles.total')}, ${data.active_count || 0} ${t('profiles.active')}`} className="col-span-full">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {profiles.map((p: any) => (
          <ProfileCard key={p.name} p={p} t={t} />
        ))}
      </div>
    </Panel>
  )
}
