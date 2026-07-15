import { useApi } from '../hooks/useApi'
import Panel from './Panel'

export default function HealthPanel() {
  const { data, isLoading } = useApi('/health', 30000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title="Health" className="col-span-full"><div className="glow text-[13px] animate-pulse">Loading...</div></Panel>
  }

  const keys = data.keys || []
  const services = data.services || []
  const database = data.database || []

  return (
    <>
      <Panel title="API Keys" className="col-span-1">
        <div className="space-y-1 text-[13px]">
          {keys.map((k: any, i: number) => (
            <div key={i} className="flex justify-between py-0.5">
              <span className="truncate mr-2">{k.name}</span>
              <span style={{ color: k.present ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                {k.present ? '●' : '○'}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 pt-2 text-[13px]" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <span style={{ color: 'var(--hud-success)' }}>{data.keys_ok || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> configured · </span>
          <span style={{ color: data.keys_missing > 0 ? 'var(--hud-error)' : 'var(--hud-text-dim)' }}>{data.keys_missing || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> missing</span>
        </div>
      </Panel>

      <Panel title="Services" className="col-span-1">
        <div className="space-y-2 text-[13px]">
          {services.map((s: any, i: number) => (
            <div key={i} className="py-1 px-2" style={{ borderLeft: `2px solid ${s.running ? 'var(--hud-success)' : 'var(--hud-error)'}` }}>
              <div className="flex justify-between">
                <span>{s.name}</span>
                <span style={{ color: s.running ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                  {s.running ? 'RUNNING' : 'STOPPED'}
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

      <Panel title="Database Schema" className="col-span-full">
        <div className="space-y-1 text-[13px]">
          {database.map((item: any, i: number) => (
            <div key={i} className="flex justify-between gap-4 py-0.5">
              <span className="truncate">{item.name}</span>
              <span className="text-right" style={{ color: item.present ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                {item.present ? 'OK' : 'MISSING'}
              </span>
            </div>
          ))}
        </div>
        {database.some((item: any) => item.note) && (
          <div className="mt-2 pt-2 space-y-1 text-[12px]" style={{ borderTop: '1px solid var(--hud-border)', color: 'var(--hud-text-dim)' }}>
            {database.filter((item: any) => item.note).map((item: any, i: number) => (
              <div key={i}>{item.name}: {item.note}</div>
            ))}
          </div>
        )}
        <div className="mt-2 pt-2 text-[13px]" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <span style={{ color: data.database_missing > 0 ? 'var(--hud-error)' : 'var(--hud-success)' }}>
            {data.database_ok || 0}/{database.length || 0}
          </span>
          <span style={{ color: 'var(--hud-text-dim)' }}> schema checks passing</span>
        </div>
      </Panel>
    </>
  )
}
