import { useState, useCallback, useMemo, useEffect } from 'react'
import { ThemeProvider } from './hooks/useTheme'
import { refreshAll } from './hooks/useApi'
import { getSelectedProfile, setSelectedProfile as saveSelectedProfile } from './lib/profile'
import TopBar, { type TabId, TABS } from './components/TopBar'
import CommandPalette from './components/CommandPalette'
import BootScreen from './components/BootScreen'
import DashboardPanel from './components/DashboardPanel'
import MemoryPanel from './components/MemoryPanel'
import SkillsPanel from './components/SkillsPanel'
import SessionsPanel from './components/SessionsPanel'
import CronPanel from './components/CronPanel'
import ProjectsPanel from './components/ProjectsPanel'
import HealthPanel from './components/HealthPanel'
import AgentsPanel from './components/AgentsPanel'
import ProfilesPanel from './components/ProfilesPanel'
import TokenCostsPanel from './components/TokenCostsPanel'

function TabContent({ tab }: { tab: TabId }) {
  switch (tab) {
    case 'dashboard': return <DashboardPanel />
    case 'memory': return <MemoryPanel />
    case 'skills': return <SkillsPanel />
    case 'sessions': return <SessionsPanel />
    case 'cron': return <CronPanel />
    case 'projects': return <ProjectsPanel />
    case 'health': return <HealthPanel />
    case 'agents': return <AgentsPanel />
    case 'profiles': return <ProfilesPanel />
    case 'token-costs': return <TokenCostsPanel />
    default: return <DashboardPanel />
  }
}

// Grid layout per tab — responsive: 1 col on mobile, full on desktop
const GRID_CLASS: Record<TabId, string> = {
  dashboard: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  memory: 'grid-cols-1 sm:grid-cols-2',
  skills: 'grid-cols-1 lg:grid-cols-[2fr_1fr]',
  sessions: 'grid-cols-1 lg:grid-cols-[2fr_1fr]',
  cron: 'grid-cols-1',
  projects: 'grid-cols-1',
  health: 'grid-cols-1 sm:grid-cols-2',
  agents: 'grid-cols-1 lg:grid-cols-2',
  profiles: 'grid-cols-1',
  'token-costs': 'grid-cols-1 lg:grid-cols-2',
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard')
  const [selectedProfile, setSelectedProfile] = useState(getSelectedProfile())
  const [booted, setBooted] = useState(() => {
    return sessionStorage.getItem('hud-booted') === 'true'
  })

  // Handle profile change
  const handleProfileChange = useCallback((profile: string) => {
    saveSelectedProfile(profile)
    setSelectedProfile(profile)
    // Small delay to ensure localStorage is committed before refreshing SWR keys
    setTimeout(refreshAll, 10)
  }, [])

  const handleBootComplete = useCallback(() => {
    setBooted(true)
    sessionStorage.setItem('hud-booted', 'true')
  }, [])

  // Command palette commands
  const commands = useMemo(() => [
    ...TABS.map(tab => ({
      id: tab.id,
      label: `${tab.label}`,
      shortcut: tab.key,
      action: () => setActiveTab(tab.id),
    })),
  ], [])

  const handleCommandSelect = useCallback((id: string) => {
    setActiveTab(id as TabId)
  }, [])

  return (
    <ThemeProvider>
      {!booted && <BootScreen onComplete={handleBootComplete} />}

      <CommandPalette
        commands={commands}
        onSelect={handleCommandSelect}
      />

      <TopBar 
        activeTab={activeTab} 
        onTabChange={setActiveTab} 
        onRefresh={refreshAll}
        selectedProfile={selectedProfile}
        onProfileChange={handleProfileChange}
      />

      <div className="overflow-y-auto" style={{ flex: '1 1 0', height: 0, minHeight: 0 }}>
        <div className={`grid gap-2 p-2 ${GRID_CLASS[activeTab]}`}>
          <TabContent tab={activeTab} />
        </div>
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-0.5 text-[13px] border-t shrink-0"
           style={{ borderColor: 'var(--hud-border)', color: 'var(--hud-text-dim)', background: 'var(--hud-bg-surface)' }}>
        <span>☤ hermes-hudui v0.1.0</span>
        <span className="hidden sm:inline">
          <span className="opacity-40">Ctrl+K</span> palette
          <span className="mx-2">·</span>
          <span className="opacity-40">1-9</span> tabs
          <span className="mx-2">·</span>
          <span className="opacity-40">t</span> theme
          <span className="mx-2">·</span>
          <span className="opacity-40">r</span> refresh
        </span>
        <span className="sm:hidden">
          <span className="opacity-40">Ctrl+K</span> commands
        </span>
      </div>
    </ThemeProvider>
  )
}
