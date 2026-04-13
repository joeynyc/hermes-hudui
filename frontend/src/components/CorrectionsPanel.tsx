import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { useTranslation } from '../i18n'

const SEVERITY: Record<string, { color: string; icon: string }> = {
  critical: { color: 'var(--hud-error)', icon: '⚠' },
  major: { color: 'var(--hud-warning)', icon: '✦' },
  minor: { color: 'var(--hud-text-dim)', icon: '·' },
}

export default function CorrectionsPanel() {
  const { t } = useTranslation()
  const { data, isLoading } = useApi('/corrections', 60000)

  // Only show loading on initial load
  if (isLoading && !data) {
    return <Panel title={t('corrections.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('corrections.loading')}</div></Panel>
  }

  const corrections = data.corrections || []
  const bySeverity: Record<string, any[]> = {}
  for (const c of corrections) {
    const s = c.severity || 'minor'
    if (!bySeverity[s]) bySeverity[s] = []
    bySeverity[s].push(c)
  }

  return (
    <Panel title={`${t('corrections.title')} — ${corrections.length} total`} className="col-span-full">
      {/* Summary */}
      <div className="flex gap-4 text-[13px] mb-3">
        {['critical', 'major', 'minor'].map(sev => {
          const count = bySeverity[sev]?.length || 0
          if (count === 0) return null
          const s = SEVERITY[sev]
          return (
            <span key={sev}>
              <span style={{ color: s.color }}>{s.icon} {count} {sev}</span>
            </span>
          )
        })}
        {corrections.length === 0 && (
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('corrections.noCorrections')}</span>
        )}
      </div>

      {/* Explanation */}
      {corrections.length > 0 && (
        <div className="text-[13px] italic mb-3" style={{ color: 'var(--hud-text-dim)' }}>
          These are moments where I was wrong, corrected, or learned something the hard way. Critical = user caught a concrete error. Major = gotcha/pitfall absorbed. Minor = limitation noted.
        </div>
      )}

      {/* Grouped by severity */}
      {['critical', 'major', 'minor'].map(sev => {
        const items = bySeverity[sev] || []
        if (items.length === 0) return null
        const s = SEVERITY[sev]

        return (
          <div key={sev} className="mb-4">
            <div className="text-[13px] font-bold mb-2" style={{ color: s.color }}>
              {s.icon} {sev.toUpperCase()} ({items.length})
            </div>
            <div className="space-y-2">
              {items.map((cor: any, i: number) => (
                <div key={i} className="p-2" style={{ background: 'var(--hud-bg-panel)', borderLeft: `2px solid ${s.color}` }}>
                  <div className="flex items-center gap-2 text-[13px] mb-1">
                    <span>{s.icon}</span>
                    {cor.timestamp && (
                      <span style={{ color: 'var(--hud-text-dim)' }}>
                        {new Date(cor.timestamp).toLocaleDateString()} {new Date(cor.timestamp).toLocaleTimeString()}
                      </span>
                    )}
                    {cor.source && <span style={{ color: 'var(--hud-text-dim)' }}>({cor.source})</span>}
                  </div>
                  <div className="text-[13px]" style={{ color: s.color }}>{cor.detail}</div>
                  {cor.session_title && (
                    <div className="text-[13px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>↳ session: {cor.session_title}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </Panel>
  )
}
