import { useState, useEffect } from 'react'
import { useTheme, THEMES } from '../hooks/useTheme'
import { useLocale } from '../lib/i18n'

export const TABS = [
  { id: 'dashboard', labelKey: 'tabs.dashboard', key: '1' },
  { id: 'memory', labelKey: 'tabs.memory', key: '2' },
  { id: 'skills', labelKey: 'tabs.skills', key: '3' },
  { id: 'sessions', labelKey: 'tabs.sessions', key: '4' },
  { id: 'cron', labelKey: 'tabs.cron', key: '5' },
  { id: 'projects', labelKey: 'tabs.projects', key: '6' },
  { id: 'health', labelKey: 'tabs.health', key: '7' },
  { id: 'agents', labelKey: 'tabs.agents', key: '8' },
  { id: 'chat', labelKey: 'tabs.chat', key: '9' },
  { id: 'profiles', labelKey: 'tabs.profiles', key: '0' },
  { id: 'token-costs', labelKey: 'tabs.token-costs', key: null },
  { id: 'corrections', labelKey: 'tabs.corrections', key: null },
  { id: 'patterns', labelKey: 'tabs.patterns', key: null },
] as const

export type TabId = typeof TABS[number]['id']

interface TopBarProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
}

export default function TopBar({ activeTab, onTabChange }: TopBarProps) {
  const { theme, setTheme, scanlines, setScanlines } = useTheme()
  const { locale, setLocale, t } = useLocale()
  const [showThemePicker, setShowThemePicker] = useState(false)
  const [showLangPicker, setShowLangPicker] = useState(false)
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const t2 = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t2)
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
      if (e.metaKey || e.ctrlKey || e.altKey) return

      const num = parseInt(e.key)
      if (!isNaN(num) && num >= 1 && num <= 9) {
        const tab = TABS.find(tb => tb.key === String(num))
        if (tab) { onTabChange(tab.id); return }
      }
      if (e.key === '0') { onTabChange('profiles'); return }
      if (e.key === 't') setShowThemePicker(p => !p)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onTabChange])

  return (
    <div className="flex items-center gap-1 px-3 py-1.5 border-b"
         style={{ borderColor: 'var(--hud-border)', background: 'var(--hud-bg-surface)' }}>
      {/* Logo */}
      <span className="gradient-text font-bold text-[13px] mr-3 tracking-wider cursor-pointer shrink-0"
            onClick={() => onTabChange('dashboard')}>☤ HERMES</span>

      {/* Tabs */}
      <div className="flex gap-0.5 flex-1 overflow-x-auto" style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className="px-2 py-1.5 text-[13px] tracking-widest uppercase transition-all duration-150 shrink-0 cursor-pointer"
            style={{
              color: activeTab === tab.id ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
              background: activeTab === tab.id ? 'var(--hud-bg-panel)' : 'transparent',
              borderBottom: activeTab === tab.id ? '2px solid var(--hud-primary)' : '2px solid transparent',
              textShadow: activeTab === tab.id ? '0 0 8px var(--hud-primary-glow)' : 'none',
              minHeight: '32px',
            }}
          >
            {tab.key && <span className="opacity-40 mr-1">{tab.key}</span>}
            {t(tab.labelKey)}
          </button>
        ))}
      </div>

      {/* Language picker */}
      <div className="relative shrink-0">
        <button
          onClick={() => setShowLangPicker(p => !p)}
          className="px-2 py-1.5 text-[13px] tracking-wider uppercase cursor-pointer"
          style={{ color: 'var(--hud-text-dim)', minHeight: '32px' }}
          title={t('lang.language')}
        >
          {locale === 'zh' ? '中' : 'EN'}
        </button>
        {showLangPicker && (
          <div className="absolute right-0 top-full mt-1 z-50 py-1 min-w-[120px]"
               style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
            <button
              onClick={() => { setLocale('en'); setShowLangPicker(false) }}
              className="block w-full text-left px-3 py-2 text-[13px] cursor-pointer"
              style={{
                color: locale === 'en' ? 'var(--hud-primary)' : 'var(--hud-text)',
                background: locale === 'en' ? 'var(--hud-bg-hover)' : 'transparent',
                minHeight: '36px',
              }}
            >
              EN English
            </button>
            <button
              onClick={() => { setLocale('zh'); setShowLangPicker(false) }}
              className="block w-full text-left px-3 py-2 text-[13px] cursor-pointer"
              style={{
                color: locale === 'zh' ? 'var(--hud-primary)' : 'var(--hud-text)',
                background: locale === 'zh' ? 'var(--hud-bg-hover)' : 'transparent',
                minHeight: '36px',
              }}
            >
              中文
            </button>
          </div>
        )}
      </div>

      {/* Theme picker */}
      <div className="relative shrink-0">
        <button
          onClick={() => setShowThemePicker(p => !p)}
          className="px-2 py-1.5 text-[13px] tracking-wider uppercase cursor-pointer"
          style={{ color: 'var(--hud-text-dim)', minHeight: '32px' }}
          title="Theme (t)"
        >
          ◆
        </button>
        {showThemePicker && (
          <div className="absolute right-0 top-full mt-1 z-50 py-1 min-w-[180px]"
               style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
            {THEMES.map(th => (
              <button
                key={th.id}
                onClick={() => { setTheme(th.id); setShowThemePicker(false) }}
                className="block w-full text-left px-3 py-2 text-[13px] transition-colors cursor-pointer"
                style={{
                  color: theme === th.id ? 'var(--hud-primary)' : 'var(--hud-text)',
                  background: theme === th.id ? 'var(--hud-bg-hover)' : 'transparent',
                  minHeight: '36px',
                }}
              >
                {th.icon} {th.label}
              </button>
            ))}
            <div className="border-t my-1" style={{ borderColor: 'var(--hud-border)' }} />
            <button
              onClick={() => setScanlines(!scanlines)}
              className="block w-full text-left px-3 py-2 text-[13px] cursor-pointer"
              style={{ color: 'var(--hud-text-dim)', minHeight: '36px' }}
            >
              {scanlines ? '▣' : '□'} {t('theme.scanlines')}
            </button>
          </div>
        )}
      </div>

      {/* Clock */}
      <span className="text-[13px] ml-2 tabular-nums shrink-0 hidden sm:inline" style={{ color: 'var(--hud-text-dim)' }}>
        {time.toLocaleTimeString(locale === 'zh' ? 'zh-CN' : 'en-US', { hour12: false })}
      </span>
    </div>
  )
}
