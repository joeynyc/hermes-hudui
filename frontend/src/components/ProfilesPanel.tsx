import { useApi } from '../hooks/useApi'
import Panel, { CapacityBar } from './Panel'
import { timeAgo, formatTokens } from '../lib/utils'

function StatusDot({ status }: { status: string }) {
  const color = status === 'active' || status === 'running'
    ? 'var(--hud-success)'
    : status === 'inactive' || status === 'stopped' || status === 'idle'
    ? 'var(--hud-error)'
    : status === 'n/a'
    ? 'var(--hud-text-dim)'
    : 'var(--hud-warning)'

  return <span style={{ color }}>●</span>
}

function ProfileCard({ p }: { p: any }) {
  return (
    <div className="p-4" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <StatusDot status={p.activity_status} />
        <span className="font-bold text-[14px]" style={{ color: 'var(--hud-primary)' }}>
          {p.name}
        </span>
        {p.is_default && <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>(default)</span>}
        <span className="text-[13px] px-1.5 py-0.5 ml-auto"
          style={{ background: 'var(--hud-bg-hover)', color: p.is_local ? 'var(--hud-secondary)' : 'var(--hud-accent)' }}>
          {p.is_local ? 'local' : p.provider}
        </span>
        <span className="text-[13px]" style={{ color: p.activity_status === 'active' ? 'var(--hud-success)' : 'var(--hud-text-dim)' }}>
          {p.activity_status}
        </span>
      </div>

      <div className="space-y-1 text-[13px] mb-3">
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>Model</span>
          <span>
            <span className="font-bold">{p.model || 'not set'}</span>
            {p.provider && <span style={{ color: 'var(--hud-text-dim)' }}> via {p.provider}</span>}
          </span>
        </div>

        {p.base_url && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Backend</span>
            <span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{p.base_url}</span>
              {' '}<StatusDot status={p.server_status} />
            </span>
          </div>
        )}

        {p.context_length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Context</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.context_length.toLocaleString()} tokens</span>
          </div>
        )}

        {p.skin && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Skin</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.skin}</span>
          </div>
        )}

        {p.soul_summary && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Soul</span>
            <span className="italic" style={{ color: 'var(--hud-text)' }}>{p.soul_summary.slice(0, 80)}{p.soul_summary.length > 80 ? '...' : ''}</span>
          </div>
        )}
      </div>

      <div className="text-[13px] mb-3 py-2" style={{ borderTop: '1px solid var(--hud-border)', borderBottom: '1px solid var(--hud-border)' }}>
        <div className="grid grid-cols-3 gap-2 mb-2">
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.session_count}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> sessions</span>
          </div>
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.message_count.toLocaleString()}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> messages</span>
          </div>
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.tool_call_count.toLocaleString()}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> tools</span>
          </div>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>Tokens</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>
            {formatTokens(p.total_tokens)} total ({formatTokens(p.total_input_tokens)} in / {formatTokens(p.total_output_tokens)} out)
          </span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>Activity</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{p.activity_reason || timeAgo(p.last_active)}</span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>Sessions</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{p.active_session_count || 0} in flight · last active {timeAgo(p.last_active)}</span>
        </div>
      </div>

      <div className="mb-3">
        <CapacityBar value={p.memory_chars || 0} max={p.memory_max_chars || 2200} label="MEMORY" />
        <div className="text-[13px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
          {p.memory_entries} entries, {p.memory_chars}/{p.memory_max_chars} chars
        </div>
        <CapacityBar value={p.user_chars || 0} max={p.user_max_chars || 1375} label="USER" />
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          {p.user_entries} entries, {p.user_chars}/{p.user_max_chars} chars
        </div>
      </div>

      <div className="space-y-1 text-[13px]">
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>Skills</span>
          <span>
            <span className="font-bold">{p.skill_count}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> · Cron jobs </span>
            <span className="font-bold">{p.cron_job_count}</span>
          </span>
        </div>

        {p.toolsets?.length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Toolsets</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.toolsets.join(', ')}</span>
          </div>
        )}

        {p.compression_enabled && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Compress</span>
            <span>
              <span style={{ color: 'var(--hud-success)' }}>on</span>
              {p.compression_model && <span style={{ color: 'var(--hud-text-dim)' }}> · {p.compression_model}</span>}
            </span>
          </div>
        )}

        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>Services</span>
          <span>
            Gateway <StatusDot status={p.gateway_status} /> {p.gateway_status}
            <span className="ml-3">Server <StatusDot status={p.server_status} /> {p.server_status}</span>
          </span>
        </div>

        {p.api_keys?.length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Keys</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.api_keys.join(', ')}</span>
          </div>
        )}

        {p.has_alias && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>Alias</span>
            <span>
              <span style={{ color: 'var(--hud-success)' }}>{p.name}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> (on PATH)</span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ProfilesPanel() {
  const { data, isLoading } = useApi('/profiles', 30000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title="Profiles" className="col-span-full"><div className="glow text-[13px] animate-pulse">Loading...</div></Panel>
  }

  const profiles = data.profiles || []

  return (
    <Panel title={`Agent Profiles — ${data.total || 0} total, ${data.active_count || 0} active`} className="col-span-full">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {profiles.map((p: any) => (
          <ProfileCard key={p.name} p={p} />
        ))}
      </div>
    </Panel>
  )
}
