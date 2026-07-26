import { useMemo, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { useI18n } from '../i18n'
import Panel from './Panel'

interface PluginInfo {
  name: string
  label: string
  description: string
  version: string
  source: string
  path: string
  runtime_status: string
  has_dashboard_manifest: boolean
  has_api: boolean
  user_hidden: boolean
  entry: string
  css?: string | null
  icon: string
  tab_path: string
  tab_position: string
  slots: string[]
  provides_tools: string[]
  auth_required: boolean
  auth_command: string
  can_update_git: boolean
}

interface PluginsState {
  plugins: PluginInfo[]
  total_plugins: number
  dashboard_count: number
  agent_count: number
  hidden_count: number
  by_source: Record<string, number>
}

function StatusBadge({ label, tone = 'neutral' }: { label: string; tone?: 'ok' | 'warn' | 'neutral' }) {
  const color = tone === 'ok' ? 'var(--hud-success)' : tone === 'warn' ? 'var(--hud-warning)' : 'var(--hud-text-dim)'
  return (
    <span
      className="px-1.5 py-0.5 text-[11px] uppercase tracking-widest"
      style={{ color, border: `1px solid ${color}` }}
    >
      {label}
    </span>
  )
}

function pluginTone(plugin: PluginInfo): 'ok' | 'warn' | 'neutral' {
  if (plugin.runtime_status === 'enabled') return 'ok'
  if (plugin.runtime_status === 'disabled' || plugin.user_hidden) return 'warn'
  return 'neutral'
}

export default function PluginsPanel() {
  const { t } = useI18n()
  const { data, isLoading, mutate } = useApi<PluginsState>('/plugins', 30000)
  const [installValue, setInstallValue] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const plugins = useMemo(() => data?.plugins ?? [], [data?.plugins])
  const dashboardPlugins = useMemo(
    () => plugins.filter(plugin => plugin.has_dashboard_manifest),
    [plugins]
  )
  const agentPlugins = useMemo(
    () => plugins.filter(plugin => plugin.provides_tools.length || plugin.runtime_status !== 'inactive'),
    [plugins]
  )
  const authPlugins = useMemo(
    () => plugins.filter(plugin => plugin.auth_required),
    [plugins]
  )

  async function runAction(key: string, path: string, body?: unknown) {
    setBusy(key)
    setError(null)
    try {
      const res = await fetch(`/api${path}`, {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!res.ok) {
        throw new Error(await res.text())
      }
      await mutate()
      if (key === 'install') setInstallValue('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  if (isLoading) {
    return <Panel title={t('plugins.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('plugins.loading')}</div></Panel>
  }

  return (
    <>
      <Panel title={t('plugins.overview')} className="col-span-full">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            [t('plugins.total'), data?.total_plugins || 0],
            [t('plugins.dashboard'), data?.dashboard_count || 0],
            [t('plugins.agent'), data?.agent_count || 0],
            [t('plugins.hidden'), data?.hidden_count || 0],
          ].map(([label, value]) => (
            <div key={String(label)} className="p-3 border" style={{ borderColor: 'var(--hud-border)' }}>
              <div className="text-[11px] uppercase tracking-widest" style={{ color: 'var(--hud-text-dim)' }}>{label}</div>
              <div className="text-2xl font-bold glow" style={{ color: 'var(--hud-primary)' }}>{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(data?.by_source || {}).map(([source, count]) => (
            <StatusBadge key={source} label={`${source}: ${count}`} />
          ))}
        </div>
        <div className="mt-4 flex flex-col md:flex-row gap-2">
          <input
            value={installValue}
            onChange={(event) => setInstallValue(event.target.value)}
            placeholder={t('plugins.installPlaceholder')}
            className="flex-1 px-2 py-1.5 text-[13px] outline-none"
            style={{ background: 'var(--hud-bg)', border: '1px solid var(--hud-border)', color: 'var(--hud-text)' }}
          />
          <button
            onClick={() => runAction('install', '/plugins/install', { identifier: installValue })}
            disabled={!installValue.trim() || busy === 'install'}
            className="px-3 py-1.5 text-[12px] uppercase tracking-widest cursor-pointer disabled:opacity-40"
            style={{ color: 'var(--hud-primary)', border: '1px solid var(--hud-primary)' }}
          >
            {busy === 'install' ? t('plugins.running') : t('plugins.install')}
          </button>
          <button
            onClick={() => runAction('rescan', '/plugins/rescan')}
            disabled={busy === 'rescan'}
            className="px-3 py-1.5 text-[12px] uppercase tracking-widest cursor-pointer disabled:opacity-40"
            style={{ color: 'var(--hud-text)', border: '1px solid var(--hud-border)' }}
          >
            {busy === 'rescan' ? t('plugins.running') : t('plugins.rescan')}
          </button>
        </div>
        {error && <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-error)' }}>{error}</div>}
      </Panel>

      <Panel title={`${t('plugins.title')} — ${plugins.length}`} className="col-span-full">
        {plugins.length === 0 ? (
          <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.none')}</div>
        ) : (
          <div className="space-y-2">
            {plugins.map(plugin => (
              <div key={plugin.name} className="p-3 border" style={{ borderColor: 'var(--hud-border)' }}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[15px] font-semibold" style={{ color: 'var(--hud-text)' }}>{plugin.label}</span>
                      <span className="text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>{plugin.version}</span>
                    </div>
                    <div className="text-[12px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>{plugin.description || plugin.name}</div>
                  </div>
                  <div className="flex flex-wrap gap-1 justify-end">
                    <StatusBadge label={plugin.source} />
                    <StatusBadge label={plugin.runtime_status} tone={pluginTone(plugin)} />
                    {plugin.has_dashboard_manifest && <StatusBadge label={t('plugins.dashboard')} tone="ok" />}
                    {plugin.has_api && <StatusBadge label={t('plugins.api')} tone="ok" />}
                    {plugin.user_hidden && <StatusBadge label={t('plugins.hidden')} tone="warn" />}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2 text-[12px]">
                  <div>
                    <span style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.tab')}</span>
                    <div style={{ color: 'var(--hud-text)' }}>{plugin.has_dashboard_manifest ? plugin.tab_path : t('plugins.noneShort')}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.tools')}</span>
                    <div style={{ color: 'var(--hud-text)' }}>{plugin.provides_tools.length ? plugin.provides_tools.join(', ') : t('plugins.noneShort')}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.slots')}</span>
                    <div style={{ color: 'var(--hud-text)' }}>{plugin.slots.length ? plugin.slots.join(', ') : t('plugins.noneShort')}</div>
                  </div>
                </div>
                {plugin.auth_required && (
                  <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-warning)' }}>
                    {t('plugins.authRequired')}: <span className="font-mono">{plugin.auth_command || `hermes auth ${plugin.name}`}</span>
                  </div>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  {plugin.source === 'user' && plugin.runtime_status !== 'enabled' && (
                    <button onClick={() => runAction(`enable:${plugin.name}`, `/plugins/${encodeURIComponent(plugin.name)}/enable`)} className="px-2 py-1 text-[11px] uppercase tracking-widest cursor-pointer" style={{ color: 'var(--hud-success)', border: '1px solid var(--hud-success)' }}>{t('plugins.enable')}</button>
                  )}
                  {plugin.source === 'user' && plugin.runtime_status === 'enabled' && (
                    <button onClick={() => runAction(`disable:${plugin.name}`, `/plugins/${encodeURIComponent(plugin.name)}/disable`)} className="px-2 py-1 text-[11px] uppercase tracking-widest cursor-pointer" style={{ color: 'var(--hud-warning)', border: '1px solid var(--hud-warning)' }}>{t('plugins.disable')}</button>
                  )}
                  {plugin.source === 'user' && plugin.has_dashboard_manifest && !plugin.user_hidden && (
                    <button onClick={() => runAction(`hide:${plugin.name}`, `/plugins/${encodeURIComponent(plugin.name)}/hide`)} className="px-2 py-1 text-[11px] uppercase tracking-widest cursor-pointer" style={{ color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}>{t('plugins.hide')}</button>
                  )}
                  {plugin.source === 'user' && plugin.has_dashboard_manifest && plugin.user_hidden && (
                    <button onClick={() => runAction(`show:${plugin.name}`, `/plugins/${encodeURIComponent(plugin.name)}/show`)} className="px-2 py-1 text-[11px] uppercase tracking-widest cursor-pointer" style={{ color: 'var(--hud-primary)', border: '1px solid var(--hud-primary)' }}>{t('plugins.show')}</button>
                  )}
                  {plugin.source === 'user' && plugin.can_update_git && (
                    <button onClick={() => runAction(`update:${plugin.name}`, `/plugins/${encodeURIComponent(plugin.name)}/update`)} className="px-2 py-1 text-[11px] uppercase tracking-widest cursor-pointer" style={{ color: 'var(--hud-text)', border: '1px solid var(--hud-border)' }}>{t('plugins.update')}</button>
                  )}
                </div>
                <div className="mt-2 truncate text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>{plugin.path}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title={t('plugins.dashboardExtensions')}>
        <div className="space-y-2">
          {dashboardPlugins.length ? dashboardPlugins.map(plugin => (
            <div key={plugin.name} className="flex items-center justify-between gap-2 text-[13px]">
              <span style={{ color: 'var(--hud-text)' }}>{plugin.label}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{plugin.entry || plugin.tab_path}</span>
            </div>
          )) : <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.none')}</div>}
        </div>
      </Panel>

      <Panel title={t('plugins.agentPlugins')}>
        <div className="space-y-2">
          {agentPlugins.length ? agentPlugins.map(plugin => (
            <div key={plugin.name} className="flex items-center justify-between gap-2 text-[13px]">
              <span style={{ color: 'var(--hud-text)' }}>{plugin.label}</span>
              <StatusBadge label={plugin.runtime_status} tone={pluginTone(plugin)} />
            </div>
          )) : <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.none')}</div>}
        </div>
      </Panel>

      <Panel title={t('plugins.authRequired')}>
        <div className="space-y-2">
          {authPlugins.length ? authPlugins.map(plugin => (
            <div key={plugin.name} className="text-[13px]">
              <div style={{ color: 'var(--hud-text)' }}>{plugin.label}</div>
              <div className="font-mono text-[12px]" style={{ color: 'var(--hud-warning)' }}>{plugin.auth_command || `hermes auth ${plugin.name}`}</div>
            </div>
          )) : <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('plugins.none')}</div>}
        </div>
      </Panel>
    </>
  )
}
