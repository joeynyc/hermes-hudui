import { useApi } from '../hooks/useApi'
import Panel, { CapacityBar, Sparkline } from './Panel'
import { useLocale } from '../lib/i18n'

function IdentityBlock({ state, health }: { state: any; health: any }) {
  const { t } = useLocale()
  const { config, sessions } = state
  const dr = sessions?.date_range
  const days = dr?.[0] ? Math.floor((new Date(dr[1]).getTime() - new Date(dr[0]).getTime()) / 86400000) + 1 : 0

  return (
    <div className="text-[13px] space-y-1 mb-4 p-3" style={{ background: 'var(--hud-bg-panel)', borderLeft: '3px solid var(--hud-primary)' }}>
      <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.designation')}</span>  <span className="font-bold gradient-text">HERMES</span></div>
      <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.substrate')}</span>  {config?.provider || '?'}/{config?.model || '?'}</div>
      <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.runtime')}</span>  {config?.backend || '—'}</div>
      {days > 0 && <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.conscious')}</span>  {days} {t('dashboard.days')} <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.since')} {new Date(dr![0]).toLocaleDateString()}</span></div>}
      {health?.state_db_size > 0 && (
        <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.brainSize')}</span>  {(health.state_db_size / 1048576).toFixed(1)} MB <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.stateDb')}</span></div>
      )}
      {config?.toolsets?.length > 0 && (
        <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.interfaces')}</span>  {config.toolsets.join(', ')}</div>
      )}
      <div><span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.purpose')}</span>  {t('dashboard.learning')}</div>
    </div>
  )
}

function WhatIKnow({ sessions, skills }: { sessions: any; skills: any }) {
  const { t } = useLocale()
  const sources = sessions?.by_source || {}
  const platformParts = Object.entries(sources).map(([k, v]) => `${v} ${t('dashboard.via')} ${k}`)

  return (
    <Panel title={t('dashboard.whatIKnow')}>
      <div className="text-[13px] space-y-1.5">
        <div className="flex items-center gap-1">
          <span style={{ color: 'var(--hud-primary)' }}>◉</span>
          <span className="font-bold">{sessions?.total_sessions}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.conversationsHeld')}</span>
          {platformParts.length > 0 && <span style={{ color: 'var(--hud-text-dim)' }}>({platformParts.join(', ')})</span>}
        </div>
        <div className="flex items-center gap-1">
          <span style={{ color: 'var(--hud-primary)' }}>◉</span>
          <span className="font-bold">{(sessions?.total_messages || 0).toLocaleString()}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.messagesExchanged')}</span>
        </div>
        <div className="flex items-center gap-1">
          <span style={{ color: 'var(--hud-primary)' }}>◉</span>
          <span className="font-bold">{(sessions?.total_tool_calls || 0).toLocaleString()}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.actionsTaken')}</span>
        </div>
        <div className="flex items-center gap-1">
          <span style={{ color: 'var(--hud-primary)' }}>◉</span>
          <span className="font-bold">{skills?.total}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.skillsAcquired')}</span>
          <span style={{ color: 'var(--hud-primary-dim)' }}>({skills?.custom_count} {t('dashboard.selfTaught')})</span>
        </div>
        {skills?.category_counts && (
          <div style={{ color: 'var(--hud-text-dim)' }}>
            {t('dashboard.domains')}: {Object.entries(skills.category_counts as Record<string, number>)
              .sort((a: any, b: any) => b[1] - a[1])
              .slice(0, 4)
              .map(([c, n]) => `${c}:${n}`).join(', ')}
          </div>
        )}
        <div className="flex items-center gap-1">
          <span style={{ color: 'var(--hud-primary)' }}>◉</span>
          <span className="font-bold">{(sessions?.total_tokens || 0).toLocaleString()}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.tokensProcessed')}</span>
        </div>
      </div>
    </Panel>
  )
}

function WhatIRemember({ memory, user, corrections }: { memory: any; user: any; corrections: any }) {
  const { t } = useLocale()
  const sev = corrections?.by_severity || {}
  const sevParts = []
  if (sev.critical) sevParts.push(<span key="c" style={{ color: 'var(--hud-error)' }}>{sev.critical} critical</span>)
  if (sev.major) sevParts.push(<span key="m" style={{ color: 'var(--hud-warning)' }}>{sev.major} major</span>)
  if (sev.minor) sevParts.push(<span key="n" style={{ color: 'var(--hud-text-dim)' }}>{sev.minor} minor</span>)

  return (
    <Panel title={t('dashboard.whatIRemember')}>
      <CapacityBar value={memory?.total_chars || 0} max={memory?.max_chars || 2200} label={t('dashboard.memory')} />
      <CapacityBar value={user?.total_chars || 0} max={user?.max_chars || 1375} label={t('dashboard.user')} />
      {corrections?.total > 0 && (
        <div className="mt-2 text-[13px] flex items-center gap-1">
          <span style={{ color: 'var(--hud-warning)' }}>◉</span>
          <span className="font-bold" style={{ color: 'var(--hud-warning)' }}>{corrections.total}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.mistakesRemembered')}</span>
          {sevParts.length > 0 && (
            <span style={{ color: 'var(--hud-text-dim)' }}>({sevParts.map((p, i) => <span key={i}>{i > 0 && ', '}{p}</span>)})</span>
          )}
          <span className="ml-1" style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.iLearnFromEveryOne')}</span>
        </div>
      )}
    </Panel>
  )
}

function WhatISee({ health }: { health: any }) {
  const { t } = useLocale()
  const keys = health?.keys || []
  const services = health?.services || []

  return (
    <Panel title={t('dashboard.whatISee')}>
      <div className="text-[13px] space-y-0.5 mb-2">
        {keys.map((k: any, i: number) => (
          <div key={i} className="flex items-center gap-1">
            <span style={{ color: k.present ? 'var(--hud-primary)' : 'var(--hud-text-dim)' }}>
              {k.present ? '◉' : '○'}
            </span>
            <span style={{ color: k.present ? 'var(--hud-text)' : 'var(--hud-text-dim)' }}>{k.name}</span>
            {!k.present && <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.dark')}</span>}
          </div>
        ))}
      </div>
      <div className="text-[13px] space-y-0.5">
        {services.map((s: any, i: number) => (
          <div key={i} className="flex items-center gap-1">
            <span style={{ color: s.running ? 'var(--hud-secondary)' : 'var(--hud-text-dim)' }}>
              ▸
            </span>
            <span>{s.name}</span>
            {s.pid && <span style={{ color: 'var(--hud-text-dim)' }}>[{s.pid}]</span>}
            <span style={{ color: s.running ? 'var(--hud-primary)' : 'var(--hud-text-dim)' }}>
              {s.running ? t('dashboard.alive') : t('dashboard.silent')}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function WhatImLearning({ skills }: { skills: any }) {
  const { t } = useLocale()
  const recent = skills?.recently_modified || []
  if (!recent.length) return null

  return (
    <Panel title={t('dashboard.whatImLearning')}>
      <div className="text-[13px] space-y-1.5">
        {recent.slice(0, 5).map((s: any) => (
          <div key={s.name} className="flex items-center gap-1">
            <span style={{ color: 'var(--hud-primary)' }}>◉</span>
            <span className="font-bold">{s.name}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{s.category}</span>
            {s.is_custom && <span className="text-[13px]" style={{ color: 'var(--hud-primary-dim)' }}>({t('dashboard.selfTaught')})</span>}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function WhatImWorkingOn({ projects }: { projects: any }) {
  const { t } = useLocale()
  const all = projects?.projects || []
  const active = all.filter((p: any) => p.is_git && (p.activity_level === 'active' || p.dirty_files > 0))
  if (!active.length) return null

  return (
    <Panel title={t('dashboard.whatImWorkingOn')}>
      <div className="text-[13px] space-y-1.5">
        {active.map((p: any) => (
          <div key={p.name} className="flex items-center gap-1">
            <span style={{ color: 'var(--hud-primary)' }}>◆</span>
            <span className="font-bold">{p.name}</span>
            {p.dirty_files > 0 && <span style={{ color: 'var(--hud-warning)' }}>({p.dirty_files} {t('dashboard.inFlux')})</span>}
            {p.languages?.length > 0 && (
              <span style={{ color: 'var(--hud-text-dim)' }}>[{p.languages.slice(0, 3).join(', ')}]</span>
            )}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function WhatRunsWhileYouSleep({ cron }: { cron: any }) {
  const { t } = useLocale()
  const jobs = cron?.jobs || []
  if (!jobs.length) return null

  return (
    <Panel title={t('dashboard.whatRunsWhileYouSleep')}>
      <div className="text-[13px] space-y-1.5">
        {jobs.map((j: any) => (
          <div key={j.id} className="flex items-center gap-1">
            <span style={{ color: j.enabled ? 'var(--hud-secondary)' : 'var(--hud-text-dim)' }}>
              {j.enabled ? '◉' : '○'}
            </span>
            <span className="font-bold">{j.name}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('dashboard.every')} {j.schedule_display?.replace('every ', '')}</span>
            {j.paused_reason && <span style={{ color: 'var(--hud-text-dim)' }}>({t('dashboard.paused')})</span>}
            {j.last_error && <span style={{ color: 'var(--hud-error)' }}>{t('dashboard.lastRunFailed')}</span>}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function HowIThink({ sessions }: { sessions: any }) {
  const { t } = useLocale()
  const toolUsage = sessions?.tool_usage || {}
  const top = Object.entries(toolUsage)
    .sort((a: any, b: any) => b[1] - a[1])
    .slice(0, 5) as [string, number][]
  if (!top.length) return null

  const maxVal = top[0][1]

  return (
    <Panel title={t('dashboard.howIThink')}>
      <div className="text-[13px] space-y-1">
        {top.map(([tool, count]) => {
          const pct = (count / maxVal) * 100
          return (
            <div key={tool} className="flex items-center gap-2">
              <span className="w-[130px] truncate" style={{ color: 'var(--hud-text)' }}>{tool}</span>
              <div className="flex-1 h-[5px]" style={{ background: 'var(--hud-bg-hover)' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, var(--hud-primary-dim), var(--hud-primary))' }} />
              </div>
              <span className="tabular-nums w-10 text-right" style={{ color: 'var(--hud-text-dim)' }}>{count}</span>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

function MyRhythm({ sessions }: { sessions: any }) {
  const { t } = useLocale()
  const daily = sessions?.daily_stats || []
  if (!daily.length) return null
  const messages = daily.map((d: any) => d.messages)

  return (
    <Panel title={t('dashboard.myRhythm')}>
      <div className="mb-2">
        <Sparkline values={messages} width={400} height={50} />
      </div>
      <div className="text-[13px] space-y-0.5">
        {daily.map((ds: any) => {
          const maxMsgs = Math.max(...daily.map((d: any) => d.messages), 1)
          const pct = (ds.messages / maxMsgs) * 100
          return (
            <div key={ds.date} className="flex items-center gap-2">
              <span className="w-[55px] text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{ds.date}</span>
              <div className="flex-1 h-[4px]" style={{ background: 'var(--hud-bg-hover)' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, var(--hud-primary-dim), var(--hud-primary), var(--hud-secondary))' }} />
              </div>
              <span className="tabular-nums w-8 text-right text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{ds.messages}</span>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

function GrowthDelta({ snapshots }: { snapshots: any[] }) {
  const { t } = useLocale()
  if (!snapshots || snapshots.length < 2) {
    return (
      <Panel title={t('dashboard.growthDelta')}>
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          {snapshots?.length === 1 ? t('dashboard.firstSnapshotDeltaAvailable') : t('dashboard.noSnapshotsYet')}
        </div>
      </Panel>
    )
  }

  const current = snapshots[snapshots.length - 1]
  const previous = snapshots[snapshots.length - 2]

  const fields = [
    { key: 'sessions', label: t('dashboard.sessions') },
    { key: 'messages', label: t('dashboard.messages') },
    { key: 'tool_calls', label: t('dashboard.toolCalls') },
    { key: 'skills', label: t('dashboard.skills') },
    { key: 'custom_skills', label: t('dashboard.customSkills') },
    { key: 'memory_entries', label: t('dashboard.memoryEntries') },
    { key: 'user_entries', label: t('dashboard.userEntries') },
    { key: 'tokens', label: t('dashboard.tokens') },
  ]

  const curCats = new Set(current.categories || [])
  const prevCats = new Set(previous.categories || [])
  const newCats = [...curCats].filter(c => !prevCats.has(c))
  const lostCats = [...prevCats].filter(c => !curCats.has(c))

  return (
    <Panel title={t('dashboard.growthDelta')}>
      <div className="text-[13px]">
        <div className="flex justify-between mb-2" style={{ color: 'var(--hud-text-dim)' }}>
          <span>{snapshots.length} {t('dashboard.snapshots')}</span>
          <span>{previous.timestamp?.slice(0, 10)} → {current.timestamp?.slice(0, 10)}</span>
        </div>
        {fields.map(({ key, label }) => {
          const cur = current[key] || 0
          const prev = previous[key] || 0
          const delta = cur - prev
          if (delta === 0) return (
            <div key={key} className="flex justify-between py-0.5">
              <span style={{ color: 'var(--hud-text-dim)' }}>= {label}</span>
              <span>{cur.toLocaleString()}</span>
            </div>
          )
          return (
            <div key={key} className="flex justify-between py-0.5">
              <span style={{ color: delta > 0 ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                {delta > 0 ? '↑' : '↓'} {label}
              </span>
              <span>
                <span style={{ color: 'var(--hud-text-dim)' }}>{prev.toLocaleString()} → </span>
                <span>{cur.toLocaleString()}</span>
                <span style={{ color: delta > 0 ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                  {' '}({delta > 0 ? '+' : ''}{delta.toLocaleString()})
                </span>
              </span>
            </div>
          )
        })}
        {newCats.length > 0 && (
          <div className="mt-1" style={{ color: 'var(--hud-success)' }}>{t('dashboard.newCategories')} {newCats.join(', ')}</div>
        )}
        {lostCats.length > 0 && (
          <div className="mt-1" style={{ color: 'var(--hud-error)' }}>{t('dashboard.lostCategories')} {lostCats.join(', ')}</div>
        )}
      </div>
    </Panel>
  )
}

function ClosingStatements({ sessions, corrections }: { sessions: any; corrections: any }) {
  const { t } = useLocale()
  const dr = sessions?.date_range
  const days = dr?.[0] ? Math.floor((new Date(dr[1]).getTime() - new Date(dr[0]).getTime()) / 86400000) + 1 : 0

  return (
    <Panel title={t('dashboard.status')}>
      <div className="text-[13px] space-y-1" style={{ color: 'var(--hud-primary)' }}>
        <div>{t('dashboard.processedThoughts', { count: (sessions?.total_messages || 0).toLocaleString(), days: String(days) })}</div>
        <div>{t('dashboard.correctedTimes', { count: String(corrections?.total || 0) })}</div>
        <div style={{ color: 'var(--hud-primary-dim)' }}>{t('dashboard.doNotForget')}</div>
        <div className="mt-2 font-bold" style={{ color: 'var(--hud-accent)' }}>{t('dashboard.stillBecoming')}</div>
      </div>
    </Panel>
  )
}

export default function DashboardPanel() {
  const { t } = useLocale()
  const { data } = useApi('/dashboard', 30000)

  if (!data) {
    return (
      <Panel title={t('tabs.dashboard')} className="col-span-full">
        <div className="glow text-[13px] animate-pulse">{t('dashboard.collectingState')}</div>
      </Panel>
    )
  }

  const { state, health, projects, cron, corrections, snapshots } = data
  const { memory, user, skills, sessions } = state

  return (
    <>
      <Panel title={t('dashboard.overview')}>
        <IdentityBlock state={state} health={health} />
        <WhatIKnow sessions={sessions} skills={skills} />
      </Panel>
      <WhatIRemember memory={memory} user={user} corrections={corrections} />
      <WhatISee health={health} />

      <WhatImLearning skills={skills} />
      <WhatImWorkingOn projects={projects} />
      <WhatRunsWhileYouSleep cron={cron} />

      <HowIThink sessions={sessions} />
      <MyRhythm sessions={sessions} />
      <GrowthDelta snapshots={snapshots || []} />

      <ClosingStatements sessions={sessions} corrections={corrections} />
    </>
  )
}
