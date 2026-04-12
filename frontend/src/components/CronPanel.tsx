import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { timeAgo, truncate } from '../lib/utils'

async function cronAction(jobId: string, action: string | null, method = 'POST') {
  const url = action ? `/api/cron/${jobId}/${action}` : `/api/cron/${jobId}`
  const res = await fetch(url, { method })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `${action ?? 'delete'} failed`)
  }
}

function jobTone(job: any) {
  if (job.next_run_status === 'overdue' || job.has_failed) return 'var(--hud-warning)'
  if (job.state === 'running') return 'var(--hud-accent)'
  if (job.enabled && job.state === 'scheduled') return 'var(--hud-success)'
  return 'var(--hud-text-dim)'
}

export default function CronPanel() {
  const { data, isLoading, mutate } = useApi('/cron', 30000)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const act = async (jobId: string, action: string | null, method = 'POST') => {
    setBusy(`${jobId}:${action}`)
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
    return <Panel title="Cron Jobs" className="col-span-full"><div className="glow text-[13px] animate-pulse">Loading...</div></Panel>
  }

  const jobs = data?.jobs || data || []
  if (!Array.isArray(jobs) || jobs.length === 0) {
    return <Panel title="Cron Jobs" className="col-span-full"><div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No cron jobs configured</div></Panel>
  }

  const total = data?.total ?? jobs.length
  const active = data?.active ?? jobs.filter((job: any) => job.enabled && job.state === 'scheduled').length
  const overdue = data?.overdue ?? jobs.filter((job: any) => job.next_run_status === 'overdue').length
  const running = data?.running ?? jobs.filter((job: any) => job.state === 'running').length
  const neverRan = data?.never_ran ?? jobs.filter((job: any) => job.never_ran).length

  return (
    <Panel title={`Cron Jobs — ${active} scheduled, ${overdue} overdue`} className="col-span-full">
      {error && (
        <div className="mb-3 px-2 py-1.5 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3 text-[13px]">
        <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}><span className="font-bold">{total}</span> total</div>
        <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}><span className="font-bold" style={{ color: 'var(--hud-success)' }}>{active}</span> scheduled</div>
        <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}><span className="font-bold" style={{ color: 'var(--hud-warning)' }}>{overdue}</span> overdue</div>
        <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}><span className="font-bold" style={{ color: 'var(--hud-accent)' }}>{running}</span> running</div>
        <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}><span className="font-bold" style={{ color: 'var(--hud-text-dim)' }}>{neverRan}</span> never-ran</div>
      </div>

      <div className="space-y-3">
        {jobs.map((job: any) => {
          const tone = jobTone(job)
          const isPaused = job.state === 'paused'
          const isCompleted = job.state === 'completed'
          const isActive = job.enabled && !isPaused && !isCompleted
          const isBusy = (action: string) => busy === `${job.id}:${action}`
          const isConfirming = confirming === job.id

          return (
            <div key={job.id} className="p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)', borderLeft: `3px solid ${tone}` }}>
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: tone }} />
                <span className="font-bold text-[13px]" style={{ color: 'var(--hud-primary)' }}>
                  {job.name || job.id}
                </span>
                {job.never_ran && <span style={{ color: 'var(--hud-text-dim)' }}>never ran</span>}
                {job.next_run_status === 'overdue' && <span style={{ color: 'var(--hud-warning)' }}>overdue</span>}
                {job.has_failed && <span style={{ color: 'var(--hud-error)' }}>failed</span>}
                <span className="text-[13px] px-1.5 py-0.5 ml-auto" style={{ background: 'var(--hud-bg-hover)', color: tone }}>
                  {job.state || 'unknown'}
                </span>

                <div className="flex items-center gap-1.5">
                  {!isCompleted && (
                    isPaused ? (
                      <button
                        onClick={() => act(job.id, 'resume')}
                        disabled={!!busy}
                        className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                        style={{ background: 'var(--hud-success)', color: 'var(--hud-bg-deep)' }}
                      >
                        {isBusy('resume') ? '...' : 'Resume'}
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={() => act(job.id, 'run')}
                          disabled={!!busy}
                          className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                          style={{ background: 'var(--hud-accent)', color: 'var(--hud-bg-deep)' }}
                        >
                          {isBusy('run') ? '...' : 'Run'}
                        </button>
                        <button
                          onClick={() => act(job.id, 'pause')}
                          disabled={!!busy}
                          className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)' }}
                        >
                          {isBusy('pause') ? '...' : 'Pause'}
                        </button>
                      </>
                    )
                  )}

                  {isConfirming ? (
                    <>
                      <button
                        onClick={() => act(job.id, null, 'DELETE')}
                        disabled={!!busy}
                        className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                        style={{ background: 'var(--hud-error)', color: 'var(--hud-bg-deep)' }}
                      >
                        {busy === `${job.id}:null` ? '...' : 'Confirm'}
                      </button>
                      <button
                        onClick={() => setConfirming(null)}
                        className="px-2 py-0.5 text-[11px] cursor-pointer"
                        style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)' }}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setConfirming(job.id)}
                      disabled={!!busy}
                      className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
                      style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-error)' }}
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[13px]">
                <div>
                  <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>Schedule</div>
                  <div style={{ color: 'var(--hud-primary)' }}>{job.schedule_display || job.schedule || '-'}</div>
                </div>
                <div>
                  <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>Last Run</div>
                  <div>
                    {job.last_run_at ? timeAgo(job.last_run_at) : 'never'}
                    {job.last_status && (
                      <span className="ml-1" style={{ color: job.last_status === 'ok' ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                        {job.last_status === 'ok' ? '✔' : '✗'}
                      </span>
                    )}
                  </div>
                </div>
                <div>
                  <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>Next Run</div>
                  <div style={{ color: job.next_run_status === 'overdue' ? 'var(--hud-warning)' : undefined }}>
                    {job.next_run_at
                      ? (job.next_run_status === 'overdue'
                          ? `OVERDUE · ${timeAgo(job.next_run_at)}`
                          : new Date(job.next_run_at).toLocaleString())
                      : '-'}
                  </div>
                </div>
                <div>
                  <div className="uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)', fontSize: '10px' }}>Deliver</div>
                  <div style={{ color: isActive ? 'var(--hud-accent)' : 'var(--hud-text-dim)' }}>{job.deliver || '-'}</div>
                </div>
              </div>

              {job.repeat_completed != null && (
                <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
                  Runs completed: {job.repeat_completed}{job.repeat_total ? ` / ${job.repeat_total}` : ''}
                  {job.skills?.length > 0 && <span className="ml-2">Skills: {job.skills.join(', ')}</span>}
                </div>
              )}

              {(job.last_error || job.last_delivery_error) && (
                <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-error)' }}>
                  {job.last_error || job.last_delivery_error}
                </div>
              )}

              {job.prompt && (
                <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
                  {truncate(job.prompt, 120)}
                </div>
              )}

              {job.paused_reason && (
                <div className="mt-1 text-[12px]" style={{ color: 'var(--hud-warning)' }}>
                  Paused: {job.paused_reason}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
