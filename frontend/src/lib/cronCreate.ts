export type ScheduleMode = 'interval' | 'cron'

export interface CreateCronForm {
  name: string
  prompt: string
  deliver: string
  customDeliver: string
  repeat: string
  scheduleMode: ScheduleMode
  intervalPreset: string
  intervalValue: string
  intervalUnit: string
  cronExpr: string
  skills: string
  script: string
  workdir: string
  model: string
  provider: string
  continuity: boolean
  noAgent: boolean
  monitorScript: string
  monitorUrl: string
}

export const defaultCronForm: CreateCronForm = {
  name: '',
  prompt: '',
  deliver: 'local',
  customDeliver: '',
  repeat: '',
  scheduleMode: 'interval',
  intervalPreset: '30m',
  intervalValue: '30',
  intervalUnit: 'm',
  cronExpr: '0 9 * * *',
  skills: '',
  script: '',
  workdir: '',
  model: '',
  provider: '',
  continuity: false,
  noAgent: false,
  monitorScript: '',
  monitorUrl: '',
}

export function getSchedule(form: CreateCronForm) {
  if (form.scheduleMode === 'cron') return form.cronExpr.trim()
  if (form.intervalPreset !== 'custom') return form.intervalPreset
  return `${form.intervalValue.trim()}${form.intervalUnit}`
}

export async function createCronJob(form: CreateCronForm) {
  const schedule = getSchedule(form)
  const deliver = form.deliver === 'custom' ? form.customDeliver.trim() : form.deliver
  const skills = form.skills.split(/[\n,]/).map(skill => skill.trim()).filter(Boolean)

  const payload = {
    schedule,
    prompt: form.prompt.trim() || undefined,
    name: form.name.trim() || undefined,
    deliver: deliver || undefined,
    repeat: form.repeat.trim() ? Number(form.repeat) : undefined,
    skills,
    script: form.script.trim() || undefined,
    workdir: form.workdir.trim() || undefined,
    model: form.model.trim() || undefined,
    provider: form.provider.trim() || undefined,
    continuity: form.continuity || undefined,
    no_agent: form.noAgent || undefined,
    monitor_script: form.monitorScript.trim() || undefined,
    monitor_url: form.monitorUrl.trim() || undefined,
  }

  const res = await fetch('/api/cron', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Create failed')
  }
}
