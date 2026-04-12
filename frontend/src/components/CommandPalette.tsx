import { useState, useEffect, useRef } from 'react'
import { useLocale } from '../lib/i18n'

interface Command {
  id: string
  label: string
  shortcut?: string
  action: () => void
}

interface CommandPaletteProps {
  commands: Command[]
  onSelect: (id: string) => void
}

export default function CommandPalette({ commands, onSelect }: CommandPaletteProps) {
  const { t } = useLocale()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(p => !p)
        if (!open) setQuery('')
      }
      if (e.key === 'Escape' && open) {
        e.preventDefault()
        setOpen(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open])

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus()
    }
  }, [open])

  const filtered = query
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        c.id.toLowerCase().includes(query.toLowerCase())
      )
    : commands

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0" style={{ background: 'rgba(0,0,0,0.6)' }} />

      {/* Palette */}
      <div
        className="relative w-[400px] max-h-[300px] overflow-hidden"
        style={{
          background: 'var(--hud-bg-surface)',
          border: '1px solid var(--hud-border-bright)',
          boxShadow: '0 0 30px var(--hud-primary-glow)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Input */}
        <div className="p-2" style={{ borderBottom: '1px solid var(--hud-border)' }}>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('commandPalette.navigateTo')}
            className="w-full bg-transparent outline-none text-[13px] py-1"
            style={{ color: 'var(--hud-text)' }}
          />
        </div>

        {/* Results */}
        <div className="overflow-y-auto max-h-[240px]">
          {filtered.map(cmd => (
            <button
              key={cmd.id}
              className="w-full text-left px-3 py-1.5 text-[13px] flex items-center justify-between transition-colors"
              style={{
                background: 'transparent',
                color: 'var(--hud-text)',
                borderBottom: '1px solid var(--hud-border)',
              }}
              onMouseEnter={e => (e.target as HTMLElement).style.background = 'var(--hud-bg-hover)'}
              onMouseLeave={e => (e.target as HTMLElement).style.background = 'transparent'}
              onClick={() => { onSelect(cmd.id); setOpen(false); setQuery('') }}
            >
              <span>{cmd.label}</span>
              {cmd.shortcut && (
                <span className="text-[13px] px-1.5 py-0.5" style={{ background: 'var(--hud-bg-panel)', color: 'var(--hud-text-dim)' }}>
                  {cmd.shortcut}
                </span>
              )}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-3 py-3 text-[13px] text-center" style={{ color: 'var(--hud-text-dim)' }}>
              {t('commandPalette.noResults')} "{query}"
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-3 py-1 text-[9px] flex justify-between" style={{ color: 'var(--hud-text-dim)', borderTop: '1px solid var(--hud-border)' }}>
          <span>{t('commandPalette.typeToFilter')}</span>
          <span>{t('commandPalette.escToClose')}</span>
        </div>
      </div>
    </div>
  )
}
