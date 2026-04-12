import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { useLocale } from '../lib/i18n'
import { timeAgo } from '../lib/utils'

export default function CronPanel() {
  const { t } = useLocale()
  const { data, isLoading } = useApi('/cron', 30000)

  if (isLoading && !data) {
    return <Panel title={t('tabs.cron')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('loading')}</div></Panel>
  }

  const jobs = data.jobs || data || []
  if (!Array.isArray(jobs) || jobs.length === 0) {
    return <Panel title={t('cron.cronJobs')} className="col-span-full"><div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('cron.noCronJobsConfigured')}</div></Panel>
  }

  return (
    <Panel title={t('cron.cronJobs')} className="col-span-full">
      <div className="space-y-3">
        {jobs.map((job: any) => {
          const isActive = job.enabled && !job.paused_reason
          return (
            <div key={job.id} className="p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: isActive ? 'var(--hud-success)' : 'var(--hud-text-dim)' }} />
                <span className="font-bold text-[13px]" style={{ color: 'var(--hud-primary)' }}>
                  {job.name || job.id}
                </span>
                <span className="text-[13px] px-1.5 py-0.5 ml-auto"
                  style={{
                    background: 'var(--hud-bg-hover)',
                    color: job.state === 'scheduled' ? 'var(--hud-success)' : 'var(--hud-text-dim)'
                  }}>
                  {job.state || 'unknown'}
                </span>
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

              {job.repeat_completed != null && (
                <div className="mt-2 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
                  {t('cron.runsCompleted')} {job.repeat_completed}{job.repeat_total ? ` / ${job.repeat_total}` : ''}
                  {job.skills?.length > 0 && <span className="ml-2">{t('cron.skills')} {job.skills.join(', ')}</span>}
                </div>
              )}

              {job.prompt && (
                <div className="mt-2 text-[13px] truncate" style={{ color: 'var(--hud-text-dim)' }}>
                  {job.prompt.slice(0, 120)}...
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
