import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { useLocale } from '../lib/i18n'

export default function HealthPanel() {
  const { t } = useLocale()
  const { data, isLoading } = useApi('/health', 30000)

  if (isLoading && !data) {
    return <Panel title={t('tabs.health')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('loading')}</div></Panel>
  }

  const keys = data.keys || []
  const services = data.services || []

  return (
    <>
      <Panel title={t('health.apiKeys')} className="col-span-1">
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
          <span style={{ color: 'var(--hud-text-dim)' }}> {t('health.configured')} · </span>
          <span style={{ color: data.keys_missing > 0 ? 'var(--hud-error)' : 'var(--hud-text-dim)' }}>{data.keys_missing || 0}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}> {t('health.missing')}</span>
        </div>
      </Panel>

      <Panel title={t('health.services')} className="col-span-1">
        <div className="space-y-2 text-[13px]">
          {services.map((s: any, i: number) => (
            <div key={i} className="py-1 px-2" style={{ borderLeft: `2px solid ${s.running ? 'var(--hud-success)' : 'var(--hud-error)'}` }}>
              <div className="flex justify-between">
                <span>{s.name}</span>
                <span style={{ color: s.running ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                  {s.running ? t('health.running') : t('health.stopped')}
                </span>
              </div>
              {s.pid && <div style={{ color: 'var(--hud-text-dim)' }}>PID {s.pid}</div>}
              {s.note && <div style={{ color: 'var(--hud-text-dim)' }}>{s.note}</div>}
            </div>
          ))}
        </div>
        <div className="mt-3 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          <div>{t('health.provider')}: {data.config_provider || '-'}</div>
          <div>{t('health.model')}: {data.config_model || '-'}</div>
          <div>{t('health.db')}: {data.state_db_exists ? `${(data.state_db_size / 1048576).toFixed(1)}MB` : 'missing'}</div>
        </div>
      </Panel>
    </>
  )
}
