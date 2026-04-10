import { useState, useEffect, useRef } from 'react'
import { useTheme, THEMES } from '../hooks/useTheme'
import { useApi } from '../hooks/useApi'
import { profileName } from '../lib/profile'

export const TABS = [
  { id: 'dashboard', label: 'Dashboard', key: '1' },
  { id: 'memory', label: 'Memory', key: '2' },
  { id: 'skills', label: 'Skills', key: '3' },
  { id: 'sessions', label: 'Sessions', key: '4' },
  { id: 'cron', label: 'Cron', key: '5' },
  { id: 'projects', label: 'Projects', key: '6' },
  { id: 'health', label: 'Health', key: '7' },
  { id: 'agents', label: 'Agents', key: '8' },
  { id: 'profiles', label: 'Profiles', key: '9' },
  { id: 'token-costs', label: 'Costs', key: '0' },
] as const

export type TabId = typeof TABS[number]['id']

interface TopBarProps {
  activeTab: TabId
  onTabChange: (tab: TabId) => void
  selectedProfile: string
  onProfileChange: (profile: string) => void
  onRefresh?: () => void
}

export default function TopBar({ activeTab, onTabChange, selectedProfile, onProfileChange, onRefresh }: TopBarProps) {
  const { theme, setTheme, scanlines, setScanlines } = useTheme()
  const [showThemePicker, setShowThemePicker] = useState(false)
  const [showProfilePicker, setShowProfilePicker] = useState(false)
  const [time, setTime] = useState(new Date())
  const [refreshing, setRefreshing] = useState(false)
  const { data: profilesData } = useApi('/profiles', 60000)
  const profilePickerRef = useRef<HTMLDivElement | null>(null)
  const themePickerRef = useRef<HTMLDivElement | null>(null)

  const profiles = (profilesData?.profiles || []).map((p: any) => p.name)

  useEffect(() => {
    if (profiles.length > 0 && !profiles.includes(selectedProfile)) {
      onProfileChange('default')
    }
  }, [profilesData, profiles.length, selectedProfile, onProfileChange])

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node
      if (profilePickerRef.current && !profilePickerRef.current.contains(target)) {
        setShowProfilePicker(false)
      }
      if (themePickerRef.current && !themePickerRef.current.contains(target)) {
        setShowThemePicker(false)
      }
    }

    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
      if (e.metaKey || e.ctrlKey || e.altKey) return

      // 1-9 for tabs
      const num = parseInt(e.key)
      if (!isNaN(num) && num >= 1 && num <= TABS.length) {
        onTabChange(TABS[num - 1].id)
        return
      }
      // 0 for last tab
      if (e.key === '0') {
        onTabChange('token-costs')
        return
      }
      // R to refresh
      if (e.key === 'r') {
        setRefreshing(true)
        onRefresh?.()
        setTimeout(() => setRefreshing(false), 800)
        return
      }
      // T to toggle theme picker
      if (e.key === 't') {
        setShowThemePicker(p => !p)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onTabChange, onRefresh])

  return (
    <div className="flex items-center gap-1 px-3 py-1.5 border-b"
         style={{ borderColor: 'var(--hud-border)', background: 'var(--hud-bg-surface)' }}>
      {/* Profile selector (replacing logo) */}
      <div className="relative shrink-0 ml-2" ref={profilePickerRef}>
        <button
          onClick={() => {
            setShowProfilePicker(p => !p)
            setShowThemePicker(false)
          }}
          className="px-2 py-1.5 text-[13px] tracking-wider uppercase cursor-pointer flex items-center gap-2"
          style={{
            color: showProfilePicker ? 'var(--hud-primary)' : 'var(--hud-text)',
            background: showProfilePicker ? 'var(--hud-bg-panel)' : 'transparent',
            minHeight: '32px',
            border: showProfilePicker ? '1px solid var(--hud-border)' : '1px solid transparent',
            textShadow: '0 0 8px var(--hud-primary-glow)',
          }}
          title="Select profile scope"
        >
          <span className="gradient-text font-bold tracking-wider">☤ {profileName(selectedProfile)}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{showProfilePicker ? '▴' : '▾'}</span>
        </button>
        {showProfilePicker && (
          <div
            className="absolute left-0 top-full mt-1 z-50 py-1 min-w-[200px] max-w-[80vw]"
            style={{
              background: 'var(--hud-bg-panel)',
              border: '1px solid var(--hud-border)',
              boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
            }}
          >
            <div
              className="overflow-y-auto"
              style={{ maxHeight: 'min(60vh, 320px)', WebkitOverflowScrolling: 'touch' as any }}
            >
              {(profiles.length === 0 ? [selectedProfile] : profiles).map((profile: string) => {
                const isActive = profile === selectedProfile
                return (
                  <button
                    key={profile}
                    onClick={() => {
                      onProfileChange(profile)
                      setShowProfilePicker(false)
                    }}
                    className="block w-full text-left px-3 py-2 text-[13px] transition-colors cursor-pointer"
                    style={{
                      color: isActive ? 'var(--hud-primary)' : 'var(--hud-text)',
                      background: isActive ? 'var(--hud-bg-hover)' : 'transparent',
                      minHeight: '36px',
                    }}
                  >
                    <span style={{ color: isActive ? 'var(--hud-primary)' : 'var(--hud-text-dim)' }}>
                      {isActive ? '◉' : '○'}
                    </span>
                    <span className="ml-2 uppercase tracking-wider">{profileName(profile)}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 flex-1 overflow-x-auto min-w-0" style={{ scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
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
            <span className="opacity-40 mr-1">{tab.key}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Refresh button */}
      <button
        onClick={() => {
          setRefreshing(true)
          onRefresh?.()
          setTimeout(() => setRefreshing(false), 800)
        }}
        className="px-1.5 py-1.5 text-[13px] shrink-0 cursor-pointer transition-colors duration-200"
        style={{
          color: refreshing ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
          textShadow: refreshing ? '0 0 8px var(--hud-primary-glow)' : 'none',
          minHeight: '32px',
        }}
        title="Refresh data (r)"
      >
        {refreshing ? '↻' : '↺'}
      </button>

      {/* Theme picker */}
      <div className="relative shrink-0" ref={themePickerRef}>
        <button
          onClick={() => {
            setShowThemePicker(p => !p)
            setShowProfilePicker(false)
          }}
          className="px-2 py-1.5 text-[13px] tracking-wider uppercase cursor-pointer"
          style={{ color: 'var(--hud-text-dim)', minHeight: '32px' }}
          title="Theme (t)"
        >
          ◆
        </button>
        {showThemePicker && (
          <div className="absolute right-0 top-full mt-1 z-50 py-1 min-w-[180px]"
               style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
            {THEMES.map(t => (
              <button
                key={t.id}
                onClick={() => { setTheme(t.id); setShowThemePicker(false) }}
                className="block w-full text-left px-3 py-2 text-[13px] transition-colors cursor-pointer"
                style={{
                  color: theme === t.id ? 'var(--hud-primary)' : 'var(--hud-text)',
                  background: theme === t.id ? 'var(--hud-bg-hover)' : 'transparent',
                  minHeight: '36px',
                }}
              >
                {t.icon} {t.label}
              </button>
            ))}
            <div className="border-t my-1" style={{ borderColor: 'var(--hud-border)' }} />
            <button
              onClick={() => setScanlines(!scanlines)}
              className="block w-full text-left px-3 py-2 text-[13px] cursor-pointer"
              style={{ color: 'var(--hud-text-dim)', minHeight: '36px' }}
            >
              {scanlines ? '▣' : '□'} Scanlines
            </button>
          </div>
        )}
      </div>

      {/* Clock */}
      <span className="text-[13px] ml-2 tabular-nums shrink-0 hidden sm:inline" style={{ color: 'var(--hud-text-dim)' }}>
        {time.toLocaleTimeString('en-US', { hour12: false })}
      </span>
    </div>
  )
}
