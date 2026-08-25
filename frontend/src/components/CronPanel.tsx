import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { timeAgo, truncate } from '../lib/utils'
import { useTranslation } from '../i18n'
import CronCreateDrawer from './CronCreateDrawer'

interface CronJob {
  id: string
  name?: string
  prompt?: string
  schedule?: string
  schedule_display?: string
  enabled?: boolean
  state?: string
  next_run_at?: string | null
  last_run_at?: string | null
  last_status?: string | null
  deliver?: string
  repeat_total?: number | null
  repeat_completed?: number | null
  skills?: string[]
  paused_reason?: string | null
  model?: string | null
  provider?: string | null
  continuity?: boolean
  no_agent?: boolean
  monitor_script?: string | null
  monitor_url?: string | null
  notepad_count?: number
  notepad?: { key: string; value: string }[]
  recent_runs?: { id: string; status: string; claimed_at?: string; error?: string }[]
}

type CronResponse = { jobs?: CronJob[] } | CronJob[]

async function cronAction(jobId: string, action: string | null, method = 'POST') {
  const url = action ? `/api/cron/${jobId}/${action}` : `/api/cron/${jobId}`
  const res = await fetch(url, { method })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `${action ?? 'delete'} failed`)
  }
}

export default function CronPanel() {
  const { t } = useTranslation()
  const { data, isLoading, mutate } = useApi<CronResponse>('/cron', 30000)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const act = async (jobId: string, action: string | null, method = 'POST') => {
    const busyAction = action ?? 'delete'
    setBusy(`${jobId}:${busyAction}`)
    setError(null)
    try {
      await cronAction(jobId, action, method)
      await mutate()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setBusy(null)
      setConfirming(null)
    }
  }

  if (isLoading && !data) {
    return <Panel title={t('cron.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('cron.loading')}</div></Panel>
  }

  const jobs = Array.isArray(data) ? data : data?.jobs || []
  const hasJobs = jobs.length > 0

  return (
    <Panel title={t('cron.title')} className="col-span-full">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
          {hasJobs ? `${jobs.length} ${jobs.length === 1 ? t('cron.job') : t('cron.jobs')}` : t('cron.noJobs')}
        </div>
        <button
          onClick={() => setCreating(open => !open)}
          className="px-2 py-1 text-[11px] cursor-pointer"
          style={{
            background: creating ? 'var(--hud-bg-hover)' : 'var(--hud-primary)',
            color: creating ? 'var(--hud-text-dim)' : 'var(--hud-bg-deep)',
            border: creating ? '1px solid var(--hud-border)' : 'none',
          }}
        >
          {creating ? t('memory.cancel') : `+ ${t('cron.createJob')}`}
        </button>
      </div>

      {creating && (
        <CronCreateDrawer
          onCancel={() => setCreating(false)}
          onCreate={async () => {
            setCreating(false)
            await mutate()
          }}
        />
      )}

      {error && (
        <div className="mb-3 px-2 py-1.5 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
          {error}
        </div>
      )}

      {!hasJobs ? (
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('cron.noJobs')}</div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job: CronJob) => {
            const isPaused = job.state === 'paused'
            const isCompleted = job.state === 'completed'
            const isActive = job.enabled && !isPaused && !isCompleted
            const isBusy = (action: string) => busy === `${job.id}:${action}`
            const isConfirming = confirming === job.id
            const monitor = job.monitor_script || job.monitor_url

            return (
              <div key={job.id} className="p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: isActive ? 'var(--hud-success)' : 'var(--hud-text-dim)' }} />
                  <span className="font-bold text-[13px]" style={{ color: 'var(--hud-primary)' }}>{job.name || job.id}</span>
                  <span className="text-[13px] px-1.5 py-0.5" style={{ background: 'var(--hud-bg-hover)', color: isActive ? 'var(--hud-success)' : 'var(--hud-text-dim)' }}>
                    {job.state || 'unknown'}
                  </span>
                  {job.continuity && <span className="text-[10px] uppercase" style={{ color: 'var(--hud-accent)' }}>{t('cron.continuity')}</span>}
                  {job.no_agent && <span className="text-[10px] uppercase" style={{ color: 'var(--hud-warning)' }}>{t('cron.noAgent')}</span>}
                  {monitor && <span className="text-[10px] uppercase" style={{ color: 'var(--hud-text-dim)' }}>{t('cron.monitor')}</span>}

                  <div className="ml-auto flex flex-wrap items-center gap-1.5">
                    {!isCompleted && (
                      isPaused ? (
                        <button onClick={() => act(job.id, 'resume')} disabled={!!busy} className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-success)', color: 'var(--hud-bg-deep)' }}>
                          {isBusy('resume') ? '...' : t('cron.resume')}
                        </button>
                      ) : (
                        <>
                          <button onClick={() => act(job.id, 'run')} disabled={!!busy} className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-accent)', color: 'var(--hud-bg-deep)' }}>
                            {isBusy('run') ? '...' : t('cron.run')}
                          </button>
                          <button onClick={() => act(job.id, 'pause')} disabled={!!busy} className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)' }}>
                            {isBusy('pause') ? '...' : t('cron.pause')}
                          </button>
                        </>
                      )
                    )}
                    {isConfirming ? (
                      <>
                        <button onClick={() => act(job.id, null, 'DELETE')} disabled={!!busy} className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-error)', color: 'var(--hud-bg-deep)' }}>
                          {isBusy('delete') ? '...' : t('cron.confirm')}
                        </button>
                        <button onClick={() => setConfirming(null)} className="px-2 py-0.5 text-[11px] cursor-pointer" style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)' }}>
                          {t('memory.cancel')}
                        </button>
                      </>
                    ) : (
                      <button onClick={() => setConfirming(job.id)} disabled={!!busy} className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40" style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-error)' }}>
                        {t('memory.delete')}
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[13px]">
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.schedule')}</div>
                    <div style={{ color: 'var(--hud-primary)' }}>{job.schedule_display || job.schedule || '-'}</div>
                  </div>
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.lastRun')}</div>
                    <div>
                      {timeAgo(job.last_run_at)}
                      {job.last_status && (
                        <span className="ml-1" style={{ color: job.last_status === 'ok' ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                          {job.last_status === 'ok' ? '✔' : '✗'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.nextRun')}</div>
                    <div>{job.next_run_at ? new Date(job.next_run_at).toLocaleString() : '-'}</div>
                  </div>
                  <div>
                    <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>{t('cron.deliver')}</div>
                    <div style={{ color: 'var(--hud-accent)' }}>{job.deliver || '-'}</div>
                  </div>
                </div>

                {(job.model || job.provider) && (
                  <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
                    {[job.provider, job.model].filter(Boolean).join(' / ')}
                  </div>
                )}

                {job.repeat_completed != null && (
                  <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
                    {t('cron.runsCompleted')}: {job.repeat_completed}{job.repeat_total ? ` / ${job.repeat_total}` : ''}
                    {!!job.skills?.length && <span className="ml-2">{t('cron.skills')}: {job.skills.join(', ')}</span>}
                  </div>
                )}

                {job.prompt && <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{truncate(job.prompt, 120)}</div>}
                {job.paused_reason && <div className="mt-1 text-[12px]" style={{ color: 'var(--hud-warning)' }}>{t('cron.pausedReason')}: {job.paused_reason}</div>}

                {(job.notepad_count || 0) > 0 && (
                  <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
                    {t('cron.notepad')}: {job.notepad?.map(note => note.key).join(', ') || job.notepad_count}
                  </div>
                )}

                {!!job.recent_runs?.length && (
                  <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
                    {t('cron.recentRuns')}: {job.recent_runs.map(run => run.status).join(', ')}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
