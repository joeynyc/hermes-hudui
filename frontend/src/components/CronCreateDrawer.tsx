import { useState } from 'react'
import { useTranslation } from '../i18n'
import {
  type CreateCronForm,
  type ScheduleMode,
  createCronJob,
  defaultCronForm,
  getSchedule,
} from '../lib/cronCreate'

const intervalPresets = ['30m', '1h', '2h', '24h']
const deliveryOptions = ['local', 'origin', 'telegram', 'discord', 'signal', 'custom']

function isValidCronExpr(value: string) {
  return value.trim().split(/\s+/).length === 5
}

function FieldLabel({ children }: { children: string }) {
  return (
    <label className="block uppercase tracking-wider text-[10px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
      {children}
    </label>
  )
}

export default function CronCreateDrawer({
  onCreate,
  onCancel,
}: {
  onCreate: () => void | Promise<void>
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState<CreateCronForm>(defaultCronForm)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const update = (patch: Partial<CreateCronForm>) => setForm(current => ({ ...current, ...patch }))
  const inputClass = 'w-full text-[13px] px-2 py-1.5 outline-none'
  const inputStyle = {
    background: 'var(--hud-bg-deep)',
    border: '1px solid var(--hud-border)',
    color: 'var(--hud-text)',
  }
  const schedule = getSchedule(form)

  const validate = () => {
    if (!schedule) return t('cron.createScheduleRequired')
    if (form.scheduleMode === 'interval' && form.intervalPreset === 'custom' && !form.intervalValue.trim()) {
      return t('cron.createIntervalInvalid')
    }
    if (form.scheduleMode === 'cron' && !isValidCronExpr(form.cronExpr)) {
      return t('cron.createCronInvalid')
    }
    if (form.repeat.trim() && (!Number.isInteger(Number(form.repeat)) || Number(form.repeat) < 1)) {
      return t('cron.createRepeatInvalid')
    }
    if (form.workdir.trim() && !form.workdir.trim().startsWith('/')) {
      return t('cron.createWorkdirInvalid')
    }
    if (form.noAgent && (form.monitorScript.trim() || form.monitorUrl.trim())) {
      return t('cron.createMonitorNoAgent')
    }
    if (form.monitorScript.trim() && form.monitorUrl.trim()) {
      return t('cron.createMonitorBoth')
    }
    if (form.monitorUrl.trim() && !/^https?:\/\//.test(form.monitorUrl.trim())) {
      return t('cron.createMonitorUrlInvalid')
    }
    return ''
  }

  const submit = async () => {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    setBusy(true)
    setError('')
    try {
      await createCronJob(form)
      setForm(defaultCronForm)
      await onCreate()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mb-4 p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <FieldLabel>{t('cron.createName')}</FieldLabel>
          <input value={form.name} onChange={e => update({ name: e.target.value })} placeholder={t('cron.createNamePlaceholder')} className={inputClass} style={inputStyle} />
        </div>
        <div>
          <FieldLabel>{t('cron.createDeliver')}</FieldLabel>
          <select value={form.deliver} onChange={e => update({ deliver: e.target.value })} className={inputClass} style={inputStyle}>
            {deliveryOptions.map(option => (
              <option key={option} value={option}>{option === 'custom' ? t('cron.createDeliverCustom') : option}</option>
            ))}
          </select>
        </div>
        <div>
          <FieldLabel>{t('cron.createRepeat')}</FieldLabel>
          <input value={form.repeat} onChange={e => update({ repeat: e.target.value.replace(/[^\d]/g, '') })} placeholder={t('cron.createRepeatPlaceholder')} inputMode="numeric" className={inputClass} style={inputStyle} />
        </div>
      </div>

      {form.deliver === 'custom' && (
        <div className="mt-3">
          <FieldLabel>{t('cron.createDeliverTarget')}</FieldLabel>
          <input value={form.customDeliver} onChange={e => update({ customDeliver: e.target.value })} placeholder="platform:chat_id" className={inputClass} style={inputStyle} />
        </div>
      )}

      <div className="mt-3">
        <FieldLabel>{t('cron.createSchedule')}</FieldLabel>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {(['interval', 'cron'] as ScheduleMode[]).map(mode => (
            <button
              key={mode}
              onClick={() => update({ scheduleMode: mode })}
              className="px-2 py-1 text-[11px] cursor-pointer"
              style={{
                background: form.scheduleMode === mode ? 'var(--hud-primary)' : 'var(--hud-bg-hover)',
                color: form.scheduleMode === mode ? 'var(--hud-bg-deep)' : 'var(--hud-text-dim)',
                border: '1px solid var(--hud-border)',
              }}
              type="button"
            >
              {mode === 'interval' ? t('cron.createInterval') : t('cron.createCronExpr')}
            </button>
          ))}
          <span className="text-[12px] self-center ml-auto" style={{ color: 'var(--hud-text-dim)' }}>
            {t('cron.createPreview')}: <span style={{ color: 'var(--hud-primary)' }}>{schedule || '-'}</span>
          </span>
        </div>

        {form.scheduleMode === 'interval' ? (
          <div className="flex flex-wrap gap-2">
            {intervalPresets.map(preset => (
              <button
                key={preset}
                onClick={() => update({ intervalPreset: preset })}
                className="px-2 py-1 text-[12px] cursor-pointer"
                style={{
                  background: form.intervalPreset === preset ? 'var(--hud-primary)' : 'transparent',
                  color: form.intervalPreset === preset ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                  border: '1px solid var(--hud-border)',
                }}
                type="button"
              >
                {preset}
              </button>
            ))}
            <button
              onClick={() => update({ intervalPreset: 'custom' })}
              className="px-2 py-1 text-[12px] cursor-pointer"
              style={{
                background: form.intervalPreset === 'custom' ? 'var(--hud-primary)' : 'transparent',
                color: form.intervalPreset === 'custom' ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                border: '1px solid var(--hud-border)',
              }}
              type="button"
            >
              {t('cron.createCustom')}
            </button>
            {form.intervalPreset === 'custom' && (
              <span className="flex gap-1">
                <input value={form.intervalValue} onChange={e => update({ intervalValue: e.target.value.replace(/[^\d]/g, '') })} className="w-20 text-[13px] px-2 py-1 outline-none" style={inputStyle} inputMode="numeric" />
                <select value={form.intervalUnit} onChange={e => update({ intervalUnit: e.target.value })} className="text-[13px] px-2 py-1 outline-none" style={inputStyle}>
                  <option value="m">{t('cron.createMinutes')}</option>
                  <option value="h">{t('cron.createHours')}</option>
                  <option value="d">{t('cron.createDays')}</option>
                </select>
              </span>
            )}
          </div>
        ) : (
          <input value={form.cronExpr} onChange={e => update({ cronExpr: e.target.value })} placeholder="0 9 * * *" className={inputClass} style={inputStyle} />
        )}
      </div>

      <div className="mt-3">
        <FieldLabel>{t('cron.createPrompt')}</FieldLabel>
        <textarea
          value={form.prompt}
          onChange={e => update({ prompt: e.target.value })}
          placeholder={t('cron.createPromptPlaceholder')}
          className="w-full text-[13px] p-2 outline-none resize-y"
          style={{ ...inputStyle, minHeight: '96px' }}
        />
      </div>

      <button onClick={() => setAdvancedOpen(open => !open)} className="mt-3 text-[11px] cursor-pointer" style={{ color: 'var(--hud-primary)' }} type="button">
        {advancedOpen ? t('cron.createHideAdvanced') : t('cron.createShowAdvanced')}
      </button>

      {advancedOpen && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-2">
          <div>
            <FieldLabel>{t('cron.createSkills')}</FieldLabel>
            <input value={form.skills} onChange={e => update({ skills: e.target.value })} placeholder="llm-wiki, research" className={inputClass} style={inputStyle} />
          </div>
          <div>
            <FieldLabel>{t('cron.createScript')}</FieldLabel>
            <input value={form.script} onChange={e => update({ script: e.target.value })} placeholder="digest.py" className={inputClass} style={inputStyle} />
          </div>
          <div>
            <FieldLabel>{t('cron.createWorkdir')}</FieldLabel>
            <input value={form.workdir} onChange={e => update({ workdir: e.target.value })} placeholder="/home/zerocool/project" className={inputClass} style={inputStyle} />
          </div>
          <div>
            <FieldLabel>{t('cron.createModel')}</FieldLabel>
            <input value={form.model} onChange={e => update({ model: e.target.value })} placeholder="grok-4.6" className={inputClass} style={inputStyle} />
          </div>
          <div>
            <FieldLabel>{t('cron.createProvider')}</FieldLabel>
            <input value={form.provider} onChange={e => update({ provider: e.target.value })} placeholder="xai" className={inputClass} style={inputStyle} />
          </div>
          <div>
            <FieldLabel>{t('cron.createMonitorScript')}</FieldLabel>
            <input value={form.monitorScript} onChange={e => update({ monitorScript: e.target.value })} placeholder="watch.py" className={inputClass} style={inputStyle} disabled={form.noAgent} />
          </div>
          <div>
            <FieldLabel>{t('cron.createMonitorUrl')}</FieldLabel>
            <input value={form.monitorUrl} onChange={e => update({ monitorUrl: e.target.value })} placeholder="https://example.com/status" className={inputClass} style={inputStyle} disabled={form.noAgent} />
          </div>
          <label className="flex items-center gap-2 text-[13px] mt-5" style={{ color: 'var(--hud-text)' }}>
            <input type="checkbox" checked={form.continuity} onChange={e => update({ continuity: e.target.checked })} />
            {t('cron.createContinuity')}
          </label>
          <label className="flex items-center gap-2 text-[13px] mt-5" style={{ color: 'var(--hud-text)' }}>
            <input type="checkbox" checked={form.noAgent} onChange={e => update({ noAgent: e.target.checked, monitorScript: '', monitorUrl: '' })} />
            {t('cron.createNoAgent')}
          </label>
        </div>
      )}

      {error && (
        <div className="mt-3 px-2 py-1.5 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
          {error}
        </div>
      )}

      <div className="flex justify-end gap-2 mt-3">
        <button onClick={onCancel} disabled={busy} className="px-2 py-1 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }} type="button">
          {t('memory.cancel')}
        </button>
        <button onClick={submit} disabled={busy} className="px-2 py-1 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }} type="button">
          {busy ? '...' : t('cron.createSubmit')}
        </button>
      </div>
    </div>
  )
}
