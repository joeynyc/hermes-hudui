import { useCallback, useEffect, useRef, useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel from './Panel'
import { timeAgo } from '../lib/utils'
import { useTranslation } from '../i18n'
import type { TranslationKey } from '../i18n'
import { mutate } from 'swr'

interface GatewayData {
  state: string
  pid: number | null
  pid_alive: boolean
  kind: string
  restart_requested: boolean
  exit_reason: string | null
  updated_at: string | null
  active_agents: number
  platforms: {
    name: string
    state: string
    updated_at: string | null
    error_code: string | null
    error_message: string | null
  }[]
  managed_tools: {
    tools: {
      key: string
      label: string
      gateway_service: string
      enabled: boolean
      available: boolean
      route: 'managed' | 'direct' | 'unavailable'
      config_section: string
      gateway_enabled: boolean
      has_direct_credential: boolean
      direct_env_vars: string[]
      configured_env_vars: string[]
      missing_config: string[]
      diagnostics: string[]
      safe_actions: string[]
      reason: string
    }[]
    nous_auth_present: boolean
    managed_count: number
    direct_count: number
    unavailable_count: number
  }
}

interface ActionStatus {
  name: string
  pid: number | null
  running: boolean
  exit_code: number | null
  started_at: number | null
  log_path: string
  lines: string[]
}

function platformColor(state: string): string {
  if (state === 'connected' || state === 'running') return 'var(--hud-success)'
  if (state === 'connecting' || state === 'starting') return 'var(--hud-warning, #d4a017)'
  return 'var(--hud-error)'
}

function routeColor(route: string): string {
  if (route === 'managed') return 'var(--hud-primary)'
  if (route === 'direct') return 'var(--hud-success)'
  return 'var(--hud-error)'
}

const SAFE_ACTIONS: Record<string, { postPath: string; labelKey: TranslationKey }> = {
  'gateway-restart': { postPath: '/api/gateway/restart', labelKey: 'gateway.restart' },
}

type SafeAction = {
  name: string
  meta: { postPath: string; labelKey: TranslationKey }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function ActionRunner({
  actionName,
  postPath,
  label,
  description,
  confirmLabel,
  confirmPrompt,
  showLastStatus = false,
  onStateChange,
}: {
  actionName: string
  postPath: string
  label: string
  description?: string
  confirmLabel?: string
  confirmPrompt?: string
  showLastStatus?: boolean
  onStateChange: () => void
}) {
  const { t } = useTranslation()
  const [polling, setPolling] = useState(false)
  const [status, setStatus] = useState<ActionStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const timerRef = useRef<number | null>(null)
  const confirmTimerRef = useRef<number | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current)
        timerRef.current = null
      }
      if (confirmTimerRef.current !== null) {
        window.clearTimeout(confirmTimerRef.current)
        confirmTimerRef.current = null
      }
    }
  }, [])

  const pollOnce = useCallback(async function pollOnce() {
    try {
      const res = await fetch(`/api/actions/${actionName}/status`)
      if (!res.ok) throw new Error(`${res.status}`)
      const data: ActionStatus = await res.json()
      if (!mountedRef.current) return
      setStatus(data)
      if (data.running) {
        setPolling(true)
        timerRef.current = window.setTimeout(pollOnce, 1000)
      } else {
        setPolling(false)
        onStateChange()
      }
    } catch (e: unknown) {
      if (!mountedRef.current) return
      setError(errorMessage(e))
      setPolling(false)
    }
  }, [actionName, onStateChange])

  useEffect(() => {
    if (showLastStatus) {
      pollOnce()
    }
  }, [pollOnce, showLastStatus])

  const trigger = async () => {
    if (confirmPrompt && !confirming) {
      setConfirming(true)
      if (confirmTimerRef.current !== null) {
        window.clearTimeout(confirmTimerRef.current)
      }
      confirmTimerRef.current = window.setTimeout(() => {
        if (mountedRef.current) setConfirming(false)
      }, 6000)
      return
    }

    setConfirming(false)
    setError(null)
    setPolling(true)
    try {
      const res = await fetch(postPath, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      if (!mountedRef.current) return
      timerRef.current = window.setTimeout(pollOnce, 500)
    } catch (e: unknown) {
      if (!mountedRef.current) return
      setError(errorMessage(e))
      setPolling(false)
    }
  }

  return (
    <div>
      {description && (
        <div className="mb-1 text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
          {description}
        </div>
      )}
      <button
        onClick={trigger}
        disabled={polling}
        className="px-3 py-1.5 text-[13px] rounded"
        style={{
          background: polling
            ? 'var(--hud-panel-alt, transparent)'
            : confirming
              ? 'var(--hud-warning)'
              : 'var(--hud-primary)',
          color: polling ? 'var(--hud-text-dim)' : 'var(--hud-bg)',
          cursor: polling ? 'not-allowed' : 'pointer',
          border: '1px solid var(--hud-border)',
        }}
      >
        {polling ? t('gateway.running') : confirming ? (confirmLabel || label) : label}
      </button>
      {confirming && confirmPrompt && (
        <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-warning)' }}>
          {confirmPrompt}
        </div>
      )}
      {error && (
        <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-error)' }}>
          {error}
        </div>
      )}
      {status && showLastStatus && (
        <div className="mt-2 text-[11px] space-y-0.5" style={{ color: 'var(--hud-text-dim)' }}>
          <div>
            {t('gateway.lastRun')}: {status.started_at ? timeAgo(new Date(status.started_at * 1000).toISOString()) : t('gateway.neverRun')}
          </div>
          <div className="font-mono truncate">{status.log_path}</div>
        </div>
      )}
      {status && status.lines.length > 0 && (
        <pre
          className="mt-2 p-2 text-[11px] overflow-auto max-h-48 font-mono"
          style={{
            background: 'var(--hud-panel-alt, rgba(0,0,0,0.2))',
            border: '1px solid var(--hud-border)',
            color: 'var(--hud-text-dim)',
          }}
        >
          {status.lines.slice(-40).join('\n')}
        </pre>
      )}
      {status && !status.running && status.exit_code !== null && (
        <div className="mt-1 text-[11px]" style={{ color: status.exit_code === 0 ? 'var(--hud-success)' : 'var(--hud-error)' }}>
          {status.exit_code === 0 ? t('gateway.actionSucceeded') : t('gateway.actionFailed')} · {t('gateway.exitCode')}: {status.exit_code}
        </div>
      )}
    </div>
  )
}

export default function GatewayPanel() {
  const { t } = useTranslation()
  const { data, isLoading } = useApi<GatewayData>('/gateway', 10000)

  const refresh = useCallback(() => {
    mutate('/api/gateway')
  }, [])

  if (isLoading && !data) {
    return (
      <Panel title={t('gateway.title')} className="col-span-full">
        <div className="glow text-[13px] animate-pulse">{t('gateway.loading')}</div>
      </Panel>
    )
  }

  const healthy = data?.state === 'running' && data?.pid_alive

  return (
    <>
    <Panel title={t('gateway.title')} className="col-span-full">
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <div className="text-[13px] space-y-1">
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('gateway.state')}</span>
              <span style={{ color: healthy ? 'var(--hud-success)' : 'var(--hud-error)' }}>
                ● {data?.state ?? 'unknown'}
              </span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('gateway.pid')}</span>
              <span>{data?.pid ?? '—'}{data && !data.pid_alive && data.pid ? ` (${t('gateway.dead')})` : ''}</span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('gateway.activeAgents')}</span>
              <span>{data?.active_agents ?? 0}</span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--hud-text-dim)' }}>{t('gateway.updated')}</span>
              <span>{timeAgo(data?.updated_at)}</span>
            </div>
            {data?.exit_reason && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--hud-text-dim)' }}>{t('gateway.exitReason')}</span>
                <span style={{ color: 'var(--hud-error)' }}>{data.exit_reason}</span>
              </div>
            )}
          </div>

          <div className="mt-4">
            <div className="text-[12px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
              {t('gateway.platforms')}
            </div>
            {(data?.platforms ?? []).length === 0 && (
              <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>—</div>
            )}
            {(data?.platforms ?? []).map((p) => (
              <div key={p.name} className="flex justify-between text-[13px] py-0.5">
                <span>{p.name}</span>
                <span style={{ color: platformColor(p.state) }}>● {p.state}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <div className="text-[12px] mb-2" style={{ color: 'var(--hud-text-dim)' }}>
              {t('gateway.actions')}
            </div>
            <div className="space-y-3">
              <ActionRunner
                actionName="gateway-restart"
                postPath="/api/gateway/restart"
                label={t('gateway.restart')}
                onStateChange={refresh}
              />
              <ActionRunner
                actionName="hermes-update"
                postPath="/api/hermes/update"
                label={t('gateway.update')}
                description={t('gateway.updateDescription')}
                confirmLabel={t('gateway.confirmUpdate')}
                confirmPrompt={t('gateway.updateConfirmPrompt')}
                showLastStatus
                onStateChange={refresh}
              />
            </div>
          </div>
        </div>
      </div>
    </Panel>
    <Panel title={t('gateway.managedTools')} className="col-span-full">
      <div className="flex flex-wrap gap-2 mb-3 text-[12px]">
        <span style={{ color: 'var(--hud-text-dim)' }}>{t('gateway.nousAuth')}: </span>
        <span style={{ color: data?.managed_tools?.nous_auth_present ? 'var(--hud-success)' : 'var(--hud-error)' }}>
          {data?.managed_tools?.nous_auth_present ? t('gateway.present') : t('gateway.missing')}
        </span>
        <span style={{ color: 'var(--hud-primary)' }}>{t('gateway.managed')}: {data?.managed_tools?.managed_count ?? 0}</span>
        <span style={{ color: 'var(--hud-success)' }}>{t('gateway.direct')}: {data?.managed_tools?.direct_count ?? 0}</span>
        <span style={{ color: 'var(--hud-error)' }}>{t('gateway.unavailable')}: {data?.managed_tools?.unavailable_count ?? 0}</span>
      </div>
      <div className="grid md:grid-cols-2 gap-2">
        {(data?.managed_tools?.tools ?? []).map((tool) => {
          const safeActions = tool.safe_actions.reduce<SafeAction[]>((actions, name) => {
            const meta = SAFE_ACTIONS[name]
            if (meta) actions.push({ name, meta })
            return actions
          }, [])

          return (
          <div key={tool.key} className="p-3 border" style={{ borderColor: 'var(--hud-border)' }}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[14px] font-semibold" style={{ color: 'var(--hud-text)' }}>{tool.label}</div>
                <div className="text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>{tool.gateway_service}</div>
              </div>
              <span className="px-1.5 py-0.5 text-[11px] uppercase tracking-widest" style={{ color: routeColor(tool.route), border: `1px solid ${routeColor(tool.route)}` }}>
                {tool.route}
              </span>
            </div>
            <div className="mt-2 text-[12px]" style={{ color: tool.available ? 'var(--hud-text-dim)' : 'var(--hud-error)' }}>
              {tool.reason}
            </div>
            <div className="mt-3 grid sm:grid-cols-2 gap-3 text-[11px]">
              <div>
                <div className="uppercase tracking-widest mb-1" style={{ color: 'var(--hud-text-dim)' }}>
                  {t('gateway.diagnostics')}
                </div>
                <ul className="space-y-1">
                  {tool.diagnostics.map((diagnostic) => (
                    <li key={diagnostic} style={{ color: 'var(--hud-text-dim)' }}>
                      {diagnostic}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="uppercase tracking-widest mb-1" style={{ color: 'var(--hud-text-dim)' }}>
                  {t('gateway.missingConfig')}
                </div>
                {tool.missing_config.length > 0 ? (
                  <ul className="space-y-1">
                    {tool.missing_config.map((item) => (
                      <li key={item} style={{ color: 'var(--hud-error)' }}>
                        {item}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ color: 'var(--hud-success)' }}>{t('gateway.none')}</div>
                )}
              </div>
            </div>
            {tool.configured_env_vars.length > 0 && (
              <div className="mt-2 text-[11px] font-mono" style={{ color: 'var(--hud-success)' }}>
                {tool.configured_env_vars.join(', ')}
              </div>
            )}
            {safeActions.length > 0 && (
              <div className="mt-3">
                <div className="uppercase tracking-widest mb-2 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
                  {t('gateway.safeActions')}
                </div>
                <div className="space-y-2">
                  {safeActions.map((action) => (
                    <ActionRunner
                      key={action.name}
                      actionName={action.name}
                      postPath={action.meta.postPath}
                      label={t(action.meta.labelKey)}
                      onStateChange={refresh}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
          )
        })}
      </div>
    </Panel>
    </>
  )
}
