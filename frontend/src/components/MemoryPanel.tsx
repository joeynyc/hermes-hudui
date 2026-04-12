import { useApi } from '../hooks/useApi'
import Panel, { CapacityBar } from './Panel'
import { useLocale } from '../lib/i18n'

function MemoryEntries({ entries }: { entries: any[] }) {
  const { t } = useLocale()
  if (!entries?.length) return <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('memory.noEntries')}</div>

  return (
    <div className="space-y-1.5">
      {entries.map((e: any, i: number) => (
        <div key={i} className="text-[13px] py-1.5 px-2" style={{ background: 'var(--hud-bg-panel)', borderLeft: '2px solid var(--hud-border)' }}>
          <div className="flex justify-between mb-0.5">
            <span className="uppercase tracking-wider text-[13px] font-bold" style={{ color: 'var(--hud-primary)' }}>
              {e.category}
            </span>
            <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{e.char_count}c</span>
          </div>
          <div style={{ color: 'var(--hud-text)' }}>{e.text}</div>
        </div>
      ))}
    </div>
  )
}

export default function MemoryPanel() {
  const { t } = useLocale()
  const { data, isLoading } = useApi('/memory', 30000)

  if (isLoading && !data) {
    return <Panel title={t('tabs.memory')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('loading')}</div></Panel>
  }

  const { memory, user } = data

  return (
    <>
      <Panel title={t('memory.agentMemory')} className="col-span-1">
        <CapacityBar value={memory?.total_chars || 0} max={memory?.max_chars || 2200} label={t('memory.capacity')} />
        <div className="text-[13px] my-2" style={{ color: 'var(--hud-text-dim)' }}>
          {memory?.entry_count || 0} {t('memory.entries')} · {Object.entries(memory?.count_by_category || {}).map(([k,v]) => `${k}(${v})`).join(' ')}
        </div>
        <MemoryEntries entries={memory?.entries || []} />
      </Panel>

      <Panel title={t('memory.userProfile')} className="col-span-1">
        <CapacityBar value={user?.total_chars || 0} max={user?.max_chars || 1375} label={t('memory.capacity')} />
        <div className="text-[13px] my-2" style={{ color: 'var(--hud-text-dim)' }}>
          {user?.entry_count || 0} {t('memory.entries')}
        </div>
        <MemoryEntries entries={user?.entries || []} />
      </Panel>
    </>
  )
}
