import { useApi } from '../hooks/useApi'
import { useTranslation } from '../i18n'
import Panel from './Panel'

function heartbeatAge(value: string | undefined) {
  if (!value) return '—'
  const age = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (age < 60) return `${age}s`
  if (age < 3600) return `${Math.floor(age / 60)}m`
  return `${Math.floor(age / 3600)}h`
}

export default function GovernancePlanPanel() {
  const { t } = useTranslation()
  const { data, error } = useApi('/governance/plan', 5000)

  if (error) {
    return (
      <Panel title={t('governance.title')} className="col-span-full">
        <div className="text-[13px]" style={{ color: 'var(--hud-error)' }}>
          {t('governance.unavailable')}
        </div>
      </Panel>
    )
  }

  const progress = data?.progress
  const state = data?.state || 'loading'
  const blocked = state === 'unknown' || data?.stale
  const color = blocked
    ? 'var(--hud-error)'
    : progress?.write_active
      ? 'var(--hud-warning)'
      : state === 'present'
        ? 'var(--hud-success)'
        : 'var(--hud-text-dim)'

  return (
    <Panel title={t('governance.title')} className="col-span-full">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 text-[12px]">
        <Field label={t('governance.state')} value={state.toUpperCase()} color={color} />
        <Field label={t('governance.plan')} value={progress?.plan_id || '—'} />
        <Field label={t('governance.stage')} value={progress?.stage || '—'} />
        <Field label={t('governance.status')} value={progress?.status || '—'} color={color} />
        <Field label={t('governance.nextGate')} value={progress?.next_gate || '—'} />
        <Field label={t('governance.heartbeat')} value={heartbeatAge(progress?.heartbeat_at)} color={color} />
        <Field
          label={t('governance.writeActive')}
          value={progress?.write_active ? t('governance.yes') : t('governance.no')}
          color={progress?.write_active ? 'var(--hud-warning)' : 'var(--hud-success)'}
        />
      </div>
      {(state === 'unknown' || data?.stale || data?.reason) && (
        <div className="mt-2 text-[12px]" style={{ color }}>
          {state === 'unknown' ? t('governance.unknownBlocked') : data?.stale ? t('governance.stale') : data?.reason}
        </div>
      )}
    </Panel>
  )
}

function Field({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="p-2 border min-w-0" style={{ borderColor: 'var(--hud-border)' }}>
      <div className="uppercase tracking-wider text-[10px]" style={{ color: 'var(--hud-text-dim)' }}>{label}</div>
      <div className="font-semibold truncate" title={value} style={{ color: color || 'var(--hud-text)' }}>{value}</div>
    </div>
  )
}
