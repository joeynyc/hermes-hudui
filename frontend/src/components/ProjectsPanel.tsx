import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { useLocale } from '../lib/i18n'

function ProjectCard({ p }: { p: any }) {
  const { t } = useLocale()
  return (
    <div className="p-2.5 text-[13px]"
      style={{
        background: 'var(--hud-bg-panel)',
        borderLeft: `3px solid ${p.dirty_files > 0 ? 'var(--hud-warning)' : p.is_git ? 'var(--hud-primary)' : 'var(--hud-text-dim)'}`,
      }}>
      <div className="flex items-center justify-between mb-0.5">
        <span className="font-bold" style={{ color: 'var(--hud-primary)' }}>{p.name}</span>
        <span className="text-[13px]" style={{ color: p.dirty_files > 0 ? 'var(--hud-warning)' : 'var(--hud-success)' }}>
          {p.dirty_files > 0 ? `${p.dirty_files} ${t('projects.dirty')}` : t('projects.clean')}
        </span>
      </div>
      {p.is_git && (
        <>
          <div className="flex gap-3 mb-0.5" style={{ color: 'var(--hud-text-dim)' }}>
            {p.branch && <span>({p.branch})</span>}
            {p.total_commits != null && <span>{p.total_commits} commits</span>}
            {p.last_commit_ago && <span>{p.last_commit_ago}</span>}
          </div>
          {p.last_commit_msg && (
            <div className="truncate" style={{ color: 'var(--hud-text)' }}>{p.last_commit_msg}</div>
          )}
        </>
      )}
      <div className="flex gap-2 mt-1">
        {p.languages?.map((lang: string) => (
          <span key={lang} className="px-1.5 py-0.5" style={{ background: 'var(--hud-bg-hover)', fontSize: '9px' }}>{lang}</span>
        ))}
        {[p.has_readme && 'README', p.has_package_json && 'npm', (p.has_requirements || p.has_pyproject) && 'pip']
          .filter(Boolean).map((badge: any) => (
            <span key={badge} className="px-1.5 py-0.5" style={{ background: 'var(--hud-bg-hover)', fontSize: '9px', color: 'var(--hud-text-dim)' }}>{badge}</span>
          ))}
      </div>
    </div>
  )
}

export default function ProjectsPanel() {
  const { t } = useLocale()
  const { data, isLoading } = useApi('/projects', 60000)

  if (isLoading && !data) {
    return <Panel title={t('tabs.projects')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('loading')}</div></Panel>
  }

  const all = data.projects || data || []
  if (!Array.isArray(all) || all.length === 0) {
    return <Panel title={t('projects.projects')} className="col-span-full"><div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('projects.noProjectsFound')}</div></Panel>
  }

  const { gitRepos, active, recent, stale, noGit, dirtyCount } = all.reduce(
    (acc: any, p: any) => {
      if (p.is_git) {
        acc.gitRepos.push(p)
        if (p.activity_level === 'active') acc.active.push(p)
        else if (p.activity_level === 'recent') acc.recent.push(p)
        else if (p.activity_level === 'stale') acc.stale.push(p)
      } else {
        acc.noGit.push(p)
      }
      if (p.dirty_files > 0) acc.dirtyCount++
      return acc
    },
    { gitRepos: [] as any[], active: [] as any[], recent: [] as any[], stale: [] as any[], noGit: [] as any[], dirtyCount: 0 }
  )

  return (
    <Panel title={t('projects.projects')} className="col-span-full">
      <div className="text-[13px] mb-3">
        <span className="font-bold">{all.length}</span> {t('projects.projects')}
        <span className="mx-2" style={{ color: 'var(--hud-text-dim)' }}>│</span>
        <span className="font-bold">{gitRepos.length}</span> {t('projects.gitRepos')}
        <span className="mx-2" style={{ color: 'var(--hud-text-dim)' }}>│</span>
        <span style={{ color: 'var(--hud-success)' }}>{active.length} {t('projects.active')}</span>
        <span className="mx-2" style={{ color: 'var(--hud-text-dim)' }}>│</span>
        <span style={{ color: dirtyCount > 0 ? 'var(--hud-warning)' : 'var(--hud-text-dim)' }}>{dirtyCount} {t('projects.dirty')}</span>
      </div>
      {data.projects_dir && (
        <div className="text-[13px] mb-3" style={{ color: 'var(--hud-text-dim)' }}>{data.projects_dir}</div>
      )}

      {active.length > 0 && (
        <div className="mb-3">
          <div className="text-[13px] font-bold mb-2" style={{ color: 'var(--hud-success)' }}>▶ {t('projects.active').toUpperCase()}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {active.map((p: any) => <ProjectCard key={p.name} p={p} />)}
          </div>
        </div>
      )}

      {recent.length > 0 && (
        <div className="mb-3">
          <div className="text-[13px] font-bold mb-2" style={{ color: 'var(--hud-warning)' }}>◆ {t('projects.recent').toUpperCase()}</div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {recent.map((p: any) => <ProjectCard key={p.name} p={p} />)}
          </div>
        </div>
      )}

      {stale.length > 0 && (
        <div className="mb-3">
          <div className="text-[13px] mb-2" style={{ color: 'var(--hud-text-dim)' }}>◇ {t('projects.stale').toUpperCase()}</div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-1">
            {stale.map((p: any) => (
              <div key={p.name} className="text-[13px] py-0.5 truncate" style={{ color: 'var(--hud-text-dim)' }}>
                {p.name} ({p.branch}){p.dirty_files > 0 && <span style={{ color: 'var(--hud-error)' }}> ({p.dirty_files})</span>}
                {p.last_commit_ago && <span> — {p.last_commit_ago}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {noGit.length > 0 && (
        <div>
          <div className="text-[13px] mb-2" style={{ color: 'var(--hud-text-dim)' }}>─ {t('projects.noGit').toUpperCase()}</div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-1">
            {noGit.map((p: any) => (
              <div key={p.name} className="text-[13px] py-0.5 truncate" style={{ color: 'var(--hud-text-dim)' }}>
                {p.name}{p.languages?.length > 0 && <span> [{p.languages.join(', ')}]</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}
