import { useState, useEffect, useRef } from 'react'
import { useTheme, THEMES } from '../hooks/useTheme'
import { useI18n } from '../i18n'

export const TABS = [
  { id: 'dashboard', labelKey: 'tab.dashboard', key: '1' },
  { id: 'memory', labelKey: 'tab.memory', key: '2' },
  { id: 'skills', labelKey: 'tab.skills', key: '3' },
  { id: 'sessions', labelKey: 'tab.sessions', key: '4' },
  { id: 'replay', labelKey: 'tab.replay', key: null },
  { id: 'cron', labelKey: 'tab.cron', key: '5' },
  { id: 'projects', labelKey: 'tab.projects', key: '6' },
  { id: 'health', labelKey: 'tab.health', key: '7' },
  { id: 'agents', labelKey: 'tab.agents', key: '8' },
  { id: 'chat', labelKey: 'tab.chat', key: '9' },
  { id: 'profiles', labelKey: 'tab.profiles', key: '0' },
  { id: 'token-costs', labelKey: 'tab.token-costs', key: null },
  { id: 'cc-costs', labelKey: 'tab.cc-costs', key: null },
  { id: 'corrections', labelKey: 'tab.corrections', key: null },
  { id: 'patterns', labelKey: 'tab.patterns', key: null },
  { id: 'sudo', labelKey: 'tab.sudo', key: null },
  { id: 'providers', labelKey: 'tab.providers', key: null },
  { id: 'gateway', labelKey: 'tab.gateway', key: null },
  { id: 'model-info', labelKey: 'tab.model-info', key: null },
  { id: 'plugins', labelKey: 'tab.plugins', key: null },
] as const

export type TabId = typeof TABS[number]['id']

interface TopBarProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
}

export default function TopBar({ activeTab, onTabChange }: TopBarProps) {
  const { theme, setTheme, scanlines, setScanlines } = useTheme()
  const { t, lang, setLang } = useI18n()
  const [showThemePicker, setShowThemePicker] = useState(false)
  const [time, setTime] = useState(new Date())
  const tabRefs = useRef<Partial<Record<TabId, HTMLButtonElement>>>({})

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const scrollActiveTab = () => {
      tabRefs.current[activeTab]?.scrollIntoView({
        block: 'nearest',
        inline: 'nearest',
      })
    }
    scrollActiveTab()
    window.addEventListener('resize', scrollActiveTab)
    return () => window.removeEventListener('resize', scrollActiveTab)
  }, [activeTab])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
      if (e.metaKey || e.ctrlKey || e.altKey) return

      // 1-9 for tabs (only tabs with numeric keys)
      const num = parseInt(e.key)
      if (!isNaN(num) && num >= 1 && num <= 9) {
        const tab = TABS.find(t => t.key === String(num))
        if (tab) {
          onTabChange(tab.id)
          return
        }
      }
      // 0 for Profiles (10th tab with key '0')
      if (e.key === '0') {
        onTabChange('profiles')
        return
      }
      // T to toggle theme picker
      if (e.key === 't') {
        setShowThemePicker(p => !p)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onTabChange])

  return (
    <div
      data-testid="top-bar"
      className="flex items-center gap-1 px-3 py-1.5 border-b w-full min-w-0 overflow-visible relative z-40"
         style={{ borderColor: 'var(--hud-border)', background: 'var(--hud-bg-surface)' }}>
      {/* Logo */}
      <span className="gradient-text font-bold text-[13px] mr-3 tracking-wider cursor-pointer shrink-0"
            onClick={() => onTabChange('dashboard')}>☤ HERMES</span>

      {/* Tabs */}
      <div
        data-testid="top-tabs"
        className="flex gap-0.5 flex-1 min-w-0 overflow-x-auto overscroll-x-contain pb-1"
        style={{ scrollbarWidth: 'thin', WebkitOverflowScrolling: 'touch' }}
      >
        {TABS.map(tab => (
          <button
            key={tab.id}
            ref={(node) => {
              if (node) tabRefs.current[tab.id] = node
              else delete tabRefs.current[tab.id]
            }}
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

      {/* Theme picker */}
      <div className="relative shrink-0">
        <button
          onClick={() => setShowThemePicker(p => !p)}
          className="px-2 py-1.5 text-[12px] tracking-wider uppercase cursor-pointer flex items-center gap-1"
          style={{
            color: showThemePicker ? 'var(--hud-primary)' : 'var(--hud-text)',
            background: showThemePicker ? 'var(--hud-bg-panel)' : 'transparent',
            border: '1px solid var(--hud-border)',
            minHeight: '32px',
          }}
          title="Theme (t)"
          aria-label="Open theme picker"
          aria-expanded={showThemePicker}
        >
          <span aria-hidden="true">◆</span>
          <span className="hidden md:inline">Theme</span>
        </button>
        {showThemePicker && (
          <div className="absolute right-0 top-full mt-1 z-50 py-1 min-w-[180px]"
               style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
            {THEMES.map(themeItem => (
              <button
                key={themeItem.id}
                onClick={() => { setTheme(themeItem.id); setShowThemePicker(false) }}
                className="block w-full text-left px-3 py-2 text-[13px] transition-colors cursor-pointer"
                style={{
                  color: theme === themeItem.id ? 'var(--hud-primary)' : 'var(--hud-text)',
                  background: theme === themeItem.id ? 'var(--hud-bg-hover)' : 'transparent',
                  minHeight: '36px',
                }}
              >
                {themeItem.icon} {t(themeItem.labelKey as any)}
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
        {time.toLocaleTimeString('en-US', { hour12: false })}
      </span>

      <button
        onClick={() => setLang(lang === 'en' ? 'zh' : 'en')}
        className="ml-2 px-2 py-0.5 text-[12px] font-bold tracking-wider cursor-pointer shrink-0"
        style={{
          color: 'var(--hud-primary)',
          border: '1px solid var(--hud-primary)',
          background: 'transparent',
          minHeight: '24px',
        }}
        title={lang === 'en' ? 'Switch to Chinese' : '切换到英文'}
      >
        {lang === 'en' ? '中文' : 'EN'}
      </button>
    </div>
  )
}
