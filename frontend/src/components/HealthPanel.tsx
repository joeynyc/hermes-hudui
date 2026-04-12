import { useApi } from '../hooks/useApi'
import Panel from './Panel'

function serviceTone(status?: string) {
  if (status === 'running') return 'var(--hud-success)'
  if (status === 'stopped') return 'var(--hud-error)'
  if (status === 'unavailable' || status === 'n/a') return 'var(--hud-text-dim)'
  return 'var(--hud-warning)'
}

function serviceLabel(status?: string) {
  if (status === 'running') return 'RUNNING'
  if (status === 'stopped') return 'STOPPED'
  if (status === 'unavailable') return 'UNAVAILABLE'
  if (status === 'n/a') return 'N/A'
  if (status === 'check_failed') return 'CHECK FAILED'
  return (status || 'unknown').toUpperCase()
}

export default function HealthPanel() {
  const { data, isLoading } = useApi('/health', 30000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title="Health" className="col-span-full"><div className="glow text-[13px] animate-pulse">Loading...</div></Panel>
  }

  const keys = data.keys || []
  const services = data.services || []

  return (
    <>
      <Panel title="API Keys" className="col-span-1">
        {keys.length === 0 ? (
          <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
            No required API keys detected for the current provider.
          </div>
        ) : (
          <div className="space-y-1 text-[13px]">
            {keys.map((k: any, i: number) => (
              <div key={i} className="flex justify-between py-0.5 gap-2">
                <span className="truncate mr-2">{k.name}{k.required ? '' : ' (optional)'}</span>
                <span style={{ color: k.present ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                  {k.present ? '●' : '○'}
                </span>
              </div>
            ))}
          </div>
        )}
        <div className="mt-2 pt-2 text-[13px]" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <span style={{ color: 'var(--hud-success)' }}>{data.keys_ok || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> required ready · </span>
          <span style={{ color: data.required_keys_missing > 0 ? 'var(--hud-error)' : 'var(--hud-text-dim)' }}>{data.required_keys_missing || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> required missing</span>
          {typeof data.optional_keys_present === 'number' && (
            <>
              <span style={{ color: 'var(--hud-text-dim)' }}> · </span>
              <span style={{ color: 'var(--hud-accent)' }}>{data.optional_keys_present}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> optional present</span>
            </>
          )}
        </div>
      </Panel>

      <Panel title="Services" className="col-span-1">
        <div className="mb-3 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          <div>Required healthy: {data.required_services_ok || 0}</div>
          <div>Required missing: {data.required_services_missing || 0}</div>
          <div>Optional running: {data.optional_services_running || 0}</div>
          <div>Unavailable / N/A checks: {data.unavailable_service_checks || 0}</div>
        </div>
        <div className="space-y-2 text-[13px]">
          {services.map((s: any, i: number) => (
            <div key={i} className="py-1 px-2" style={{ borderLeft: `2px solid ${serviceTone(s.status)}` }}>
              <div className="flex justify-between gap-3">
                <span>{s.name}{s.required ? ' (required)' : ''}</span>
                <span style={{ color: serviceTone(s.status) }}>
                  {serviceLabel(s.status)}
                </span>
              </div>
              {s.pid && <div style={{ color: 'var(--hud-text-dim)' }}>PID {s.pid}</div>}
              {s.note && <div style={{ color: 'var(--hud-text-dim)' }}>{s.note}</div>}
            </div>
          ))}
        </div>
        <div className="mt-3 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          <div>Provider: {data.config_provider || '-'}</div>
          <div>Model: {data.config_model || '-'}</div>
          <div>DB: {data.state_db_exists ? `${(data.state_db_size / 1048576).toFixed(1)}MB` : 'missing'}</div>
        </div>
      </Panel>
    </>
  )
}
