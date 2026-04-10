import React, { useState, useCallback } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { timeAgo, formatSize } from '../lib/utils'

// Componente para mostrar detalles del skill en un modal/overlay
function SkillDetailModal({ skill, onClose }: { skill: any; onClose: () => void }) {
  if (!skill) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-[80%] max-w-3xl max-h-[80vh] overflow-y-auto rounded-lg border border-hud-border bg-hud-bg-surface p-4 shadow-2xl"
        onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="skill-detail-title"
      >
        {/* Header */}
        <div className="mb-6 flex items-start justify-between border-b border-hud-border pb-4">
          <div>
            <h2 id="skill-detail-title" className="text-xl font-bold text-hud-primary glow">
              {skill.name}
            </h2>
            <div className="mt-1.5 flex items-center gap-2 text-sm">
              {skill.is_custom && (
                <span className="px-1.5 py-0.5 rounded bg-hud-accent text-hud-bg-deep text-[11px] font-bold uppercase tracking-wider">
                  custom
                </span>
              )}
              <span className="text-hud-text-dim">
                Category: <span className="text-hud-text">{skill.category || 'N/A'}</span>
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-hud-bg-hover text-hud-text-dim hover:text-hud-primary transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Description */}
        <div className="mb-4">
          <h3 className="mb-1 text-sm font-semibold text-hud-primary">Description</h3>
          <p className="text-sm text-hud-text">
            {skill.description || 'No description available.'}
          </p>
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="p-2 rounded bg-hud-bg-panel">
            <div className="text-[11px] text-hud-text-dim uppercase tracking-wide">Modified at</div>
            <div className="text-sm font-medium text-hud-text">
              {skill.modified_at ? new Date(skill.modified_at).toLocaleString() : 'N/A'}
            </div>
          </div>
          <div className="p-2 rounded bg-hud-bg-panel">
            <div className="text-[11px] text-hud-text-dim uppercase tracking-wide">File size</div>
            <div className="text-sm font-medium text-hud-text">
              {formatSize(skill.file_size || 0)}
            </div>
          </div>
          <div className="p-2 rounded bg-hud-bg-panel">
            <div className="text-[11px] text-hud-text-dim uppercase tracking-wide">File path</div>
            <div className="text-sm font-medium text-hud-text truncate" title={skill.path || 'N/A'}>
              {skill.path || 'N/A'}
            </div>
          </div>
          <div className="p-2 rounded bg-hud-bg-panel">
            <div className="text-[11px] text-hud-text-dim uppercase tracking-wide">Type</div>
            <div className="text-sm font-medium text-hud-text">
              {skill.is_custom ? 'Custom' : 'Integrated'}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded text-sm font-medium transition-colors hover:bg-hud-bg-hover"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

// Componente para mostrar un skill individual con botón de ver detalles
function SkillItem({
  skill,
  variant,
  onOpenDetails,
}: {
  skill: any
  variant: 'category' | 'recent'
  onOpenDetails?: (skill: any) => void
}) {
  const descLimit = variant === 'category' ? 120 : 100

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      // Evitar propagación si hay un enlace o botón
      if (e.target instanceof HTMLElement && e.target.closest('button')) return

      if (onOpenDetails) {
        onOpenDetails(skill)
      }
    },
    [onOpenDetails, skill]
  )

  return (
    <div
      className={`py-2 px-2 text-[13px] rounded transition-colors cursor-pointer ${
        onOpenDetails ? 'hover:bg-hud-bg-hover' : ''
      }`}
      style={{ borderLeft: '2px solid var(--hud-border)' }}
      onClick={handleClick}
      role="button"
      tabIndex={onOpenDetails ? 0 : -1}
      aria-label={`Ver detalles de ${skill.name}`}
      title={onOpenDetails ? 'Click para ver detalles' : ''}
    >
      <div className="flex items-center gap-2 mb-0.5">
        <span className="font-bold text-hud-primary">
          {skill.name}
        </span>
        {variant === 'recent' && (
          <span className="text-[13px] px-1.5 rounded bg-hud-bg-panel text-hud-text-dim">
            {skill.category}
          </span>
        )}
        {skill.is_custom && (
          <span className="text-[13px] px-1.5 rounded bg-hud-accent text-hud-bg-deep font-semibold">
            custom
          </span>
        )}
        {variant === 'category' && (
          <span className="text-[13px] ml-auto tabular-nums opacity-60">
            {formatSize(skill.file_size || 0)}
          </span>
        )}
      </div>
      <div className="text-[13px] text-hud-text-dim">
        {skill.description?.slice(0, descLimit) || 'No description'}
        {skill.description?.length > descLimit ? '...' : ''}
      </div>
      <div className="text-[13px] mt-0.5 text-hud-text-dim opacity-50">
        {variant === 'category'
          ? `${skill.modified_at ? new Date(skill.modified_at).toLocaleDateString() : ''} · ${skill.path?.split(/[/\\]/).slice(-3).join('/')}`
          : skill.modified_at ? timeAgo(skill.modified_at) : ''}
      </div>
    </div>
  )
}

export default function SkillsPanel() {
  const { data, isLoading } = useApi('/skills', 60000)
  const [selectedCat, setSelectedCat] = useState<string | null>(null)
  const [selectedSkill, setSelectedSkill] = useState<any>(null)

  if (isLoading || !data) {
    return (
      <Panel title="Skills" className="col-span-full">
        <div className="glow text-[13px] animate-pulse py-4">Scanning skill library...</div>
      </Panel>
    )
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
      <Panel title="Skill Library" className="col-span-1">
        <div className="flex flex-wrap gap-2 mb-4">
          <span className="text-[11px] px-2 py-0.5 rounded border border-hud-primary/30 bg-hud-primary/5 text-hud-primary font-bold uppercase tracking-wider">
            {data.total} TOTAL
          </span>
          <span className="text-[11px] px-2 py-0.5 rounded border border-hud-accent/30 bg-hud-accent/5 text-hud-accent font-bold uppercase tracking-wider">
            {data.custom_count} CUSTOM
          </span>
          <span className="text-[11px] py-0.5 text-hud-text-dim font-medium uppercase tracking-wider ml-auto">
            {sorted.length} CATS
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
                className="flex items-center gap-2 w-full py-1 px-2 text-left transition-colors rounded hover:bg-hud-bg-hover"
                style={{
                  background: isSelected ? 'var(--hud-bg-hover)' : 'transparent',
                  borderLeft: isSelected ? '2px solid var(--hud-primary)' : '2px solid transparent',
                }}
              >
                <span
                  className="w-[140px] truncate font-medium"
                  style={{
                    color: isSelected ? 'var(--hud-primary)' : 'var(--hud-text)',
                  }}
                >
                  {cat}
                </span>
                <div className="flex-1 h-[4px] rounded-full bg-hud-bg-deep/50 overflow-hidden relative">
                  <div
                    style={{
                      width: `${pct}%`,
                      height: '100%',
                      background: isSelected ? 'var(--hud-primary)' : 'var(--hud-primary-dim)',
                      boxShadow: isSelected ? '0 0 8px var(--hud-primary-glow)' : 'none',
                    }}
                    className="transition-all duration-500"
                  />
                </div>
                <span
                  className="tabular-nums w-8 text-right"
                  style={{
                    color: isSelected ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
                  }}
                >
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      </Panel>

      {/* Selected category skills OR recently modified */}
      {selectedCat ? (
        <Panel title={selectedCat} className="col-span-1">
          <div className="space-y-2">
            {catSkills.map((skill: any) => (
              <SkillItem
                key={skill.name}
                skill={skill}
                variant="category"
                onOpenDetails={() => setSelectedSkill(skill)}
              />
            ))}
            {catSkills.length === 0 && (
              <div className="text-[13px] text-hud-text-dim">No skills found</div>
            )}
          </div>
        </Panel>
      ) : (
        <Panel title="Recently Modified" className="col-span-1">
          <div className="space-y-2">
            {recentlyMod.map((skill: any) => (
              <SkillItem
                key={skill.name}
                skill={skill}
                variant="recent"
                onOpenDetails={() => setSelectedSkill(skill)}
              />
            ))}
            {recentlyMod.length === 0 && (
              <div className="text-[13px] text-hud-text-dim">
                No recent modifications
              </div>
            )}
          </div>
        </Panel>
      )}

      {/* Modal para detalles del skill */}
      {selectedSkill && (
        <SkillDetailModal skill={selectedSkill} onClose={() => setSelectedSkill(null)} />
      )}
    </>
  )
}