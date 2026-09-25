import { lazy, Suspense, useState, useCallback, useMemo, useEffect } from 'react'
import { ThemeProvider } from './hooks/useTheme'
import { useWebSocket } from './hooks/useWebSocket'
import TopBar, { type TabId, TABS } from './components/TopBar'
import CommandPalette from './components/CommandPalette'
import BootScreen from './components/BootScreen'
import DashboardPanel from './components/DashboardPanel'
import { useI18n } from './i18n'

const MemoryPanel = lazy(() => import('./components/MemoryPanel'))
const SkillsPanel = lazy(() => import('./components/SkillsPanel'))
const SessionsPanel = lazy(() => import('./components/SessionsPanel'))
const ReplayPanel = lazy(() => import('./components/ReplayPanel'))
const CronPanel = lazy(() => import('./components/CronPanel'))
const ProjectsPanel = lazy(() => import('./components/ProjectsPanel'))
const HealthPanel = lazy(() => import('./components/HealthPanel'))
const AgentsPanel = lazy(() => import('./components/AgentsPanel'))
const ChatPanel = lazy(() => import('./components/ChatPanel'))
const ProfilesPanel = lazy(() => import('./components/ProfilesPanel'))
const TokenCostsPanel = lazy(() => import('./components/TokenCostsPanel'))
const CorrectionsPanel = lazy(() => import('./components/CorrectionsPanel'))
const PatternsPanel = lazy(() => import('./components/PatternsPanel'))
const SudoPanel = lazy(() => import('./components/SudoPanel'))
const ProvidersPanel = lazy(() => import('./components/ProvidersPanel'))
const GatewayPanel = lazy(() => import('./components/GatewayPanel'))
const ModelInfoPanel = lazy(() => import('./components/ModelInfoPanel'))
const PluginsPanel = lazy(() => import('./components/PluginsPanel'))

function PanelFallback() {
  return (
    <div className="p-4 text-[13px] animate-pulse" style={{ color: 'var(--hud-text-dim)' }}>
      Loading…
    </div>
  )
}

function TabContent({ tab }: { tab: TabId }) {
  switch (tab) {
    case 'dashboard': return <DashboardPanel />
    case 'memory': return <MemoryPanel />
    case 'skills': return <SkillsPanel />
    case 'sessions': return <SessionsPanel />
    case 'replay': return <ReplayPanel />
    case 'cron': return <CronPanel />
    case 'projects': return <ProjectsPanel />
    case 'health': return <HealthPanel />
    case 'agents': return <AgentsPanel />
    case 'chat': return <ChatPanel />
    case 'profiles': return <ProfilesPanel />
    case 'token-costs': return <TokenCostsPanel />
    case 'corrections': return <CorrectionsPanel />
    case 'patterns': return <PatternsPanel />
    case 'sudo': return <SudoPanel />
    case 'providers': return <ProvidersPanel />
    case 'gateway': return <GatewayPanel />
    case 'model-info': return <ModelInfoPanel />
    case 'plugins': return <PluginsPanel />
    default: return <DashboardPanel />
  }
}

// Grid layout per tab — responsive: 1 col on mobile, full on desktop
const GRID_CLASS: Record<TabId, string> = {
  dashboard: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  memory: 'grid-cols-1 sm:grid-cols-2',
  skills: 'grid-cols-1 lg:grid-cols-[2fr_1fr]',
  sessions: 'grid-cols-1 lg:grid-cols-[2fr_1fr]',
  replay: 'grid-cols-1 lg:grid-cols-[360px_1fr]',
  cron: 'grid-cols-1',
  projects: 'grid-cols-1',
  health: 'grid-cols-1 sm:grid-cols-2',
  agents: 'grid-cols-1 lg:grid-cols-2',
  chat: 'grid-cols-1',  // Full width for chat
  profiles: 'grid-cols-1',
  'token-costs': 'grid-cols-1 lg:grid-cols-2',
  corrections: 'grid-cols-1',
  patterns: 'grid-cols-1 lg:grid-cols-2',
  sudo: 'grid-cols-1 lg:grid-cols-2',
  providers: 'grid-cols-1',
  gateway: 'grid-cols-1',
  'model-info': 'grid-cols-1 lg:grid-cols-2',
  plugins: 'grid-cols-1 lg:grid-cols-2',
}

export default function App() {
  const { t } = useI18n()
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
      label: `${tab.labelKey}`,
      shortcut: tab.key as string,
      action: () => setActiveTab(tab.id),
    })),
    // Add tabs without keyboard shortcuts
    { id: 'token-costs', label: 'tab.token-costs', shortcut: '', action: () => setActiveTab('token-costs') },
    { id: 'replay', label: 'tab.replay', shortcut: '', action: () => setActiveTab('replay') },
    { id: 'plugins', label: 'tab.plugins', shortcut: '', action: () => setActiveTab('plugins') },
    { id: 'sudo', label: 'tab.sudo', shortcut: '', action: () => setActiveTab('sudo') },
  ], [])

  const handleCommandSelect = useCallback((id: string) => {
    setActiveTab(id as TabId)
  }, [])

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ tab?: string }>).detail
      const tab = detail?.tab as TabId | undefined
      if (tab && TABS.some(item => item.id === tab)) {
        setActiveTab(tab)
      }
    }
    window.addEventListener('hud:navigate', handler)
    return () => window.removeEventListener('hud:navigate', handler)
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
            <Suspense fallback={<PanelFallback />}>
              <TabContent tab={activeTab} />
            </Suspense>
          </div>
        </div>
      ) : (
        <div className="overflow-y-auto" style={{ flex: '1 1 0', height: 0, minHeight: 0 }}>
          <div className={`grid gap-2 p-2 ${GRID_CLASS[activeTab]}`}>
            <Suspense fallback={<PanelFallback />}>
              <TabContent tab={activeTab} />
            </Suspense>
          </div>
        </div>
      )}

      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-0.5 text-[13px] border-t shrink-0"
           style={{ borderColor: 'var(--hud-border)', color: 'var(--hud-text-dim)', background: 'var(--hud-bg-surface)' }}>
        <span className="flex items-center gap-2">
          ☤ {t('boot.version')} v0.12.0
          {/* WebSocket status indicator */}
          <span
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{
              background: wsStatus === 'connected' ? 'var(--hud-success)' :
                         wsStatus === 'connecting' ? 'var(--hud-warning)' : 'var(--hud-error)',
              color: 'var(--hud-bg-deep)',
              opacity: 0.8
            }}
            title={wsStatus === 'connected' ? t('status.live') : `WebSocket: ${wsStatus}`}
          >
            {wsStatus === 'connected' ? '● ' + t('status.live') : wsStatus}
          </span>
        </span>
        <span className="hidden sm:inline">
          <span className="opacity-40">Ctrl+K</span> {t('status.palette')}
          <span className="mx-2">·</span>
          <span className="opacity-40">1-9</span> {t('status.tabs')}
          <span className="mx-2">·</span>
          <span className="opacity-40">t</span> {t('status.theme')}
        </span>
        <span className="sm:hidden">
          <span className="opacity-40">Ctrl+K</span> {t('status.commands')}
        </span>
      </div>
    </ThemeProvider>
  )
}
