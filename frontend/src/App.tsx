import { useState, useCallback, useMemo } from 'react'
import { ThemeProvider } from './hooks/useTheme'
import { useWebSocket } from './hooks/useWebSocket'
import TopBar, { type TabId, TABS } from './components/TopBar'
import CommandPalette from './components/CommandPalette'
import BootScreen from './components/BootScreen'
import DashboardPanel from './components/DashboardPanel'
import ArtplexPanel from './components/ArtplexPanel'
import MemoryPanel from './components/MemoryPanel'
import SkillsPanel from './components/SkillsPanel'
import SessionsPanel from './components/SessionsPanel'
import CronPanel from './components/CronPanel'
import ProjectsPanel from './components/ProjectsPanel'
import HealthPanel from './components/HealthPanel'
import AgentsPanel from './components/AgentsPanel'
import ChatPanel from './components/ChatPanel'
import ProfilesPanel from './components/ProfilesPanel'
import TokenCostsPanel from './components/TokenCostsPanel'
import CorrectionsPanel from './components/CorrectionsPanel'
import PatternsPanel from './components/PatternsPanel'

function TabContent({ tab }: { tab: TabId }) {
  switch (tab) {
    case 'dashboard': return <DashboardPanel />
    case 'artplex': return <ArtplexPanel />
    case 'memory': return <MemoryPanel />
    case 'skills': return <SkillsPanel />
    case 'sessions': return <SessionsPanel />
    case 'cron': return <CronPanel />
    case 'projects': return <ProjectsPanel />
    case 'health': return <HealthPanel />
    case 'agents': return <AgentsPanel />
    case 'chat': return <ChatPanel />
    case 'profiles': return <ProfilesPanel />
    case 'token-costs': return <TokenCostsPanel />
    case 'corrections': return <CorrectionsPanel />
    case 'patterns': return <PatternsPanel />
    default: return <DashboardPanel />
  }
}

// Grid layout per tab — responsive: 1 col on mobile, full on desktop
const GRID_CLASS: Record<TabId, string> = {
  dashboard: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  artplex: 'grid-cols-1 lg:grid-cols-2',
  memory: 'grid-cols-1 sm:grid-cols-2',
  skills: 'grid-cols-1 lg:grid-cols-[2fr_1fr]',
  sessions: 'grid-cols-1 lg:grid-cols-[2fr_1fr]',
  cron: 'grid-cols-1',
  projects: 'grid-cols-1',
  health: 'grid-cols-1 sm:grid-cols-2',
  agents: 'grid-cols-1 lg:grid-cols-2',
  chat: 'grid-cols-1',  // Full width for chat
  profiles: 'grid-cols-1',
  'token-costs': 'grid-cols-1 lg:grid-cols-2',
  corrections: 'grid-cols-1',
  patterns: 'grid-cols-1 lg:grid-cols-2',
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard')
  const [booted, setBooted] = useState(() => {
    return sessionStorage.getItem('hud-booted') === 'true'
  })
  
  // WebSocket for real-time updates
  const { status: wsStatus } = useWebSocket()

  const handleBootComplete = useCallback(() => {
    setBooted(true)
    sessionStorage.setItem('hud-booted', 'true')
  }, [])

  // Command palette commands (only include tabs with keyboard shortcuts)
  const commands = useMemo(() => [
    ...TABS.filter(tab => tab.key !== null).map(tab => ({
      id: tab.id,
      label: `${tab.label}`,
      shortcut: tab.key as string,
      action: () => setActiveTab(tab.id),
    })),
    // Add Costs tab without shortcut
    { id: 'token-costs', label: 'Costs', shortcut: '', action: () => setActiveTab('token-costs') },
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

      <TopBar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Chat tab: fixed-height, no page scroll — message thread scrolls internally */}
      {activeTab === 'chat' ? (
        <div style={{ flex: '1 1 0', height: 0, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div className="p-2 h-full">
            <TabContent tab={activeTab} />
          </div>
        </div>
      ) : (
        <div className="overflow-y-auto" style={{ flex: '1 1 0', height: 0, minHeight: 0 }}>
          <div className={`grid gap-2 p-2 ${GRID_CLASS[activeTab]}`}>
            <TabContent tab={activeTab} />
          </div>
        </div>
      )}

      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-0.5 text-[13px] border-t shrink-0"
           style={{ borderColor: 'var(--hud-border)', color: 'var(--hud-text-dim)', background: 'var(--hud-bg-surface)' }}>
        <span className="flex items-center gap-2">
          ☤ hermes-hudui v0.3.1
          {/* WebSocket status indicator */}
          <span 
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{ 
              background: wsStatus === 'connected' ? 'var(--hud-success)' : 
                         wsStatus === 'connecting' ? 'var(--hud-warning)' : 'var(--hud-error)',
              color: 'var(--hud-bg-deep)',
              opacity: 0.8
            }}
            title={wsStatus === 'connected' ? 'Live updates active' : `WebSocket: ${wsStatus}`}
          >
            {wsStatus === 'connected' ? '● live' : wsStatus}
          </span>
        </span>
        <span className="hidden sm:inline">
          <span className="opacity-40">Ctrl+K</span> palette
          <span className="mx-2">·</span>
          <span className="opacity-40">1-9/0</span> tabs
          <span className="mx-2">·</span>
          <span className="opacity-40">a</span> artplex
          <span className="mx-2">·</span>
          <span className="opacity-40">t</span> theme
        </span>
        <span className="sm:hidden">
          <span className="opacity-40">Ctrl+K</span> commands
        </span>
      </div>
    </ThemeProvider>
  )
}
