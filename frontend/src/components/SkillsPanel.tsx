import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { timeAgo, formatSize } from '../lib/utils'
import { profileName, withProfile } from '../lib/profile'

function SkillItem({ skill, variant }: { skill: any; variant: 'category' | 'recent' }) {
  const descLimit = variant === 'category' ? 120 : 100
  return (
    <div className="py-2 px-2 text-[13px]" style={{ borderLeft: '2px solid var(--hud-border)' }}>
      <div className="flex items-center gap-2 mb-0.5">
        <span className="font-bold" style={{ color: 'var(--hud-primary)' }}>{skill.name}</span>
        {variant === 'recent' && (
          <span className="text-[13px] px-1" style={{ background: 'var(--hud-bg-panel)', color: 'var(--hud-text-dim)' }}>
            {skill.category}
          </span>
        )}
        {skill.is_custom && (
          <span className="text-[13px] px-1" style={{ background: 'var(--hud-accent)', color: 'var(--hud-bg-deep)' }}>custom</span>
        )}
        {variant === 'category' && (
          <span className="text-[13px] ml-auto" style={{ color: 'var(--hud-text-dim)' }}>
            {formatSize(skill.file_size)}
          </span>
        )}
      </div>
      <div style={{ color: 'var(--hud-text-dim)' }}>
        {skill.description?.slice(0, descLimit)}{skill.description?.length > descLimit ? '...' : ''}
      </div>
      <div className="text-[13px] mt-0.5" style={{ color: 'var(--hud-text-dim)' }}>
        {variant === 'category'
          ? `${skill.modified_at ? new Date(skill.modified_at).toLocaleDateString() : ''} · ${skill.path?.split('/').slice(-3).join('/')}`
          : skill.modified_at ? timeAgo(skill.modified_at) : ''
        }
      </div>
    </div>
  )
}

export default function SkillsPanel({ selectedProfile }: { selectedProfile: string }) {
  const { data, isLoading } = useApi(withProfile('/skills', selectedProfile), 60000)
  const [selectedCat, setSelectedCat] = useState<string | null>(null)

  if (isLoading || !data) {
    return <Panel title="Skills" className="col-span-full"><div className="glow text-[13px] animate-pulse">Scanning skill library...</div></Panel>
  }

  const catCounts: Record<string, number> = data.category_counts || {}
  const byCategory: Record<string, any[]> = data.by_category || {}
  const recentlyMod = data.recently_modified || []

  // Sort categories by count descending
  const sorted = Object.entries(catCounts).sort((a: any, b: any) => b[1] - a[1])
  const maxCount = sorted.length > 0 ? sorted[0][1] : 1

  // Skills in selected category
  const catSkills = selectedCat ? byCategory[selectedCat] || [] : []

  return (
    <>
      {/* Category overview */}
      <Panel title={`Skill Library · ${profileName(data?.profile || selectedProfile)}`} className="col-span-1">
        <div className="flex gap-2 mb-3">
          <span className="text-[13px] px-2 py-0.5" style={{ background: 'var(--hud-bg-panel)', color: 'var(--hud-primary)' }}>
            {data.total} total
          </span>
          <span className="text-[13px] px-2 py-0.5" style={{ background: 'var(--hud-bg-panel)', color: 'var(--hud-accent)' }}>
            {data.custom_count} custom
          </span>
          <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
            {sorted.length} categories
          </span>
        </div>

        {/* Category bar chart — scannable at a glance */}
        <div className="space-y-1 text-[13px]">
          {sorted.map(([cat, count]) => {
            const pct = (count / maxCount) * 100
            const isSelected = selectedCat === cat
            return (
              <button
                key={cat}
                onClick={() => setSelectedCat(isSelected ? null : cat)}
                className="flex items-center gap-2 w-full py-1 px-2 text-left transition-colors"
                style={{
                  background: isSelected ? 'var(--hud-bg-hover)' : 'transparent',
                  borderLeft: isSelected ? '2px solid var(--hud-primary)' : '2px solid transparent',
                }}
              >
                <span className="w-[140px] truncate" style={{ color: isSelected ? 'var(--hud-primary)' : 'var(--hud-text)' }}>
                  {cat}
                </span>
                <div className="flex-1 h-[6px]" style={{ background: 'var(--hud-bg-panel)' }}>
                  <div
                    style={{
                      width: `${pct}%`,
                      height: '100%',
                      background: isSelected ? 'var(--hud-primary)' : 'var(--hud-primary-dim)',
                    }}
                  />
                </div>
                <span className="tabular-nums w-8 text-right" style={{ color: isSelected ? 'var(--hud-primary)' : 'var(--hud-text-dim)' }}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      </Panel>

      {/* Selected category skills OR recently modified */}
      {selectedCat ? (
        <Panel title={selectedCat}>
          <div className="space-y-2">
            {catSkills.map((skill: any) => (
              <SkillItem key={skill.name} skill={skill} variant="category" />
            ))}
            {catSkills.length === 0 && (
              <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No skills in this category</div>
            )}
          </div>
        </Panel>
      ) : (
        <Panel title="Recently Modified">
          <div className="space-y-2">
            {recentlyMod.map((skill: any) => (
              <SkillItem key={skill.name} skill={skill} variant="recent" />
            ))}
            {recentlyMod.length === 0 && (
              <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No recent modifications</div>
            )}
          </div>
        </Panel>
      )}
    </>
  )
}
