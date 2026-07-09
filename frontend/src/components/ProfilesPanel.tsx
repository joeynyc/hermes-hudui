import { useEffect, useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel, { CapacityBar } from './Panel'
import { timeAgo, formatTokens } from '../lib/utils'
import { useTranslation } from '../i18n'

interface Profile {
  name: string
  is_default?: boolean
  is_local?: boolean
  model?: string
  provider?: string
  base_url?: string
  context_length?: number
  skin?: string
  soul_summary?: string
  session_count?: number
  message_count?: number
  tool_call_count?: number
  total_tokens?: number
  total_input_tokens?: number
  total_output_tokens?: number
  last_active?: string | null
  memory_chars?: number
  memory_max_chars?: number
  memory_entries?: number
  user_chars?: number
  user_max_chars?: number
  user_entries?: number
  skill_count?: number
  cron_job_count?: number
  toolsets?: string[]
  compression_enabled?: boolean
  compression_model?: string
  gateway_status?: string
  server_status?: string
  api_keys?: string[]
  has_alias?: boolean
}

interface ProfilesResponse {
  profiles?: Profile[]
  total?: number
  active_count?: number
}

interface ProfileEdit {
  name: string
  model: {
    provider: string
    default: string
    base_url: string
    api_mode: string
    context_length: number | string | null
  }
  toolsets: string[]
  skin: string
  compression: {
    enabled: boolean
    summary_provider: string
    summary_model: string
  }
  soul: string
}

interface ProfileOptions {
  providers?: string[]
  provider_presets?: Record<string, {
    display_name?: string
    models?: Array<{
      id: string
      context_window?: number
      input_modalities?: string[]
      thinking?: string[]
    }>
    endpoints?: Array<{
      region: string
      openai_base_url: string
      anthropic_base_url: string
      docs_root?: string
    }>
  }>
  toolsets?: string[]
}

const inputStyle = {
  background: 'var(--hud-bg-deep)',
  border: '1px solid var(--hud-border)',
  color: 'var(--hud-text)',
}

function StatusDot({ status }: { status: string }) {
  const color = status === 'active' || status === 'running'
    ? 'var(--hud-success)'
    : status === 'inactive' || status === 'stopped'
    ? 'var(--hud-error)'
    : status === 'n/a'
    ? 'var(--hud-text-dim)'
    : 'var(--hud-warning)'

  return <span style={{ color }}>●</span>
}

function FieldLabel({ children }: { children: string }) {
  return (
    <label className="block uppercase tracking-wider text-[10px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
      {children}
    </label>
  )
}

async function fetchProfileEdit(profileName: string): Promise<ProfileEdit> {
  const res = await fetch(`/api/profiles/${encodeURIComponent(profileName)}/edit`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load profile')
  }
  return res.json()
}

async function saveProfileEdit(profileName: string, body: ProfileEdit): Promise<ProfileEdit> {
  const payload = {
    model: {
      provider: body.model.provider.trim(),
      default: body.model.default.trim(),
      base_url: body.model.base_url.trim(),
      api_mode: body.model.api_mode.trim(),
      context_length: body.model.context_length === '' || body.model.context_length == null
        ? null
        : Number(body.model.context_length),
    },
    toolsets: body.toolsets.map(t => t.trim()).filter(Boolean),
    skin: body.skin.trim(),
    compression: {
      enabled: body.compression.enabled,
      summary_provider: body.compression.summary_provider.trim(),
      summary_model: body.compression.summary_model.trim(),
    },
    soul: body.soul,
  }

  const res = await fetch(`/api/profiles/${encodeURIComponent(profileName)}/edit`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to save profile')
  }
  return res.json()
}

function ProfileEditor({
  profileName,
  options,
  onClose,
  onSaved,
}: {
  profileName: string
  options: ProfileOptions
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState<ProfileEdit | null>(null)
  const [newToolset, setNewToolset] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchProfileEdit(profileName)
      .then(data => {
        if (cancelled) return
        setForm({
          ...data,
          model: {
            ...data.model,
            context_length: data.model.context_length ?? '',
          },
        })
      })
      .catch(e => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Unknown error')
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [profileName])

  const updateModel = (patch: Partial<ProfileEdit['model']>) => {
    setForm(current => current ? ({ ...current, model: { ...current.model, ...patch } }) : current)
  }

  const updateCompression = (patch: Partial<ProfileEdit['compression']>) => {
    setForm(current => current ? ({ ...current, compression: { ...current.compression, ...patch } }) : current)
  }

  const providerPreset = form
    ? options.provider_presets?.[form.model.provider.trim().toLowerCase()]
    : undefined

  const toggleToolset = (toolset: string) => {
    setForm(current => {
      if (!current) return current
      const exists = current.toolsets.includes(toolset)
      return {
        ...current,
        toolsets: exists
          ? current.toolsets.filter(t => t !== toolset)
          : [...current.toolsets, toolset],
      }
    })
  }

  const addToolset = () => {
    const value = newToolset.trim()
    if (!value) return
    setForm(current => current && !current.toolsets.includes(value)
      ? ({ ...current, toolsets: [...current.toolsets, value] })
      : current)
    setNewToolset('')
  }

  const validate = () => {
    if (!form) return t('profiles.editLoadFirst')
    const context = form.model.context_length
    if (context !== '' && context != null && (!Number.isInteger(Number(context)) || Number(context) < 1)) {
      return t('profiles.editContextInvalid')
    }
    const baseUrl = form.model.base_url.trim()
    if (baseUrl && !baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
      return t('profiles.editBaseUrlInvalid')
    }
    return ''
  }

  const submit = async () => {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    if (!form) return
    setBusy(true)
    setError('')
    try {
      await saveProfileEdit(profileName, form)
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mb-3 p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="text-[13px] font-bold" style={{ color: 'var(--hud-primary)' }}>
          {t('profiles.editProfile')}: {profileName}
        </div>
        <button
          onClick={onClose}
          disabled={busy}
          className="px-2 py-0.5 text-[11px] cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}
        >
          {t('memory.cancel')}
        </button>
      </div>

      {busy && !form && (
        <div className="glow text-[13px] animate-pulse">{t('profiles.editLoading')}</div>
      )}

      {form && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <FieldLabel>{t('profiles.provider')}</FieldLabel>
              <input
                value={form.model.provider}
                list="profile-provider-options"
                onChange={e => updateModel({ provider: e.target.value })}
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
              <datalist id="profile-provider-options">
                {(options.providers || []).map(provider => <option key={provider} value={provider} />)}
              </datalist>
            </div>
            <div>
              <FieldLabel>{t('profiles.model')}</FieldLabel>
              <input
                value={form.model.default}
                list="profile-model-options"
                onChange={e => updateModel({ default: e.target.value })}
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
              <datalist id="profile-model-options">
                {(providerPreset?.models || []).map(model => <option key={model.id} value={model.id} />)}
              </datalist>
            </div>
            <div>
              <FieldLabel>{t('profiles.context')}</FieldLabel>
              <input
                value={form.model.context_length ?? ''}
                onChange={e => updateModel({ context_length: e.target.value.replace(/[^\d]/g, '') })}
                inputMode="numeric"
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
            </div>
            <div>
              <FieldLabel>{t('profiles.backend')}</FieldLabel>
              <input
                value={form.model.base_url}
                list="profile-base-url-options"
                onChange={e => updateModel({ base_url: e.target.value })}
                placeholder="https://..."
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
              <datalist id="profile-base-url-options">
                {(providerPreset?.endpoints || []).flatMap(endpoint => [
                  <option
                    key={`${endpoint.region}-openai`}
                    value={endpoint.openai_base_url}
                    label={`${endpoint.region} · OpenAI-compatible`}
                  />,
                  <option
                    key={`${endpoint.region}-anthropic`}
                    value={endpoint.anthropic_base_url}
                    label={`${endpoint.region} · Anthropic-compatible`}
                  />,
                ])}
              </datalist>
            </div>
            <div>
              <FieldLabel>{t('profiles.apiMode')}</FieldLabel>
              <input
                value={form.model.api_mode}
                onChange={e => updateModel({ api_mode: e.target.value })}
                placeholder="chat_completions"
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
            </div>
            <div>
              <FieldLabel>{t('profiles.skin')}</FieldLabel>
              <input
                value={form.skin}
                onChange={e => setForm(current => current ? ({ ...current, skin: e.target.value }) : current)}
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
            </div>
          </div>

          <div className="mt-3">
            <FieldLabel>{t('profiles.toolsets')}</FieldLabel>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {(options.toolsets || []).map(toolset => {
                const active = form.toolsets.includes(toolset)
                return (
                  <button
                    key={toolset}
                    onClick={() => toggleToolset(toolset)}
                    className="px-2 py-1 text-[11px] cursor-pointer"
                    style={{
                      background: active ? 'var(--hud-primary)' : 'transparent',
                      color: active ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                      border: '1px solid var(--hud-border)',
                    }}
                    type="button"
                  >
                    {toolset}
                  </button>
                )
              })}
            </div>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {form.toolsets
                .filter(toolset => !(options.toolsets || []).includes(toolset))
                .map(toolset => (
                  <button
                    key={toolset}
                    onClick={() => toggleToolset(toolset)}
                    className="px-2 py-1 text-[11px] cursor-pointer"
                    style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-accent)', border: '1px solid var(--hud-border)' }}
                    type="button"
                  >
                    {toolset} ×
                  </button>
                ))}
            </div>
            <div className="flex gap-1">
              <input
                value={newToolset}
                onChange={e => setNewToolset(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addToolset()
                  }
                }}
                placeholder={t('profiles.addToolset')}
                className="text-[13px] px-2 py-1 outline-none flex-1 min-w-[180px]"
                style={inputStyle}
              />
              <button
                onClick={addToolset}
                className="px-2 py-1 text-[11px] cursor-pointer"
                style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-primary)', border: '1px solid var(--hud-border)' }}
                type="button"
              >
                {t('memory.add')}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[160px_1fr_1fr] gap-3 mt-3">
            <label className="flex items-center gap-2 text-[13px]" style={{ color: 'var(--hud-text)' }}>
              <input
                type="checkbox"
                checked={form.compression.enabled}
                onChange={e => updateCompression({ enabled: e.target.checked })}
              />
              {t('profiles.compress')}
            </label>
            <div>
              <FieldLabel>{t('profiles.summaryProvider')}</FieldLabel>
              <input
                value={form.compression.summary_provider}
                onChange={e => updateCompression({ summary_provider: e.target.value })}
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
            </div>
            <div>
              <FieldLabel>{t('profiles.summaryModel')}</FieldLabel>
              <input
                value={form.compression.summary_model}
                onChange={e => updateCompression({ summary_model: e.target.value })}
                className="w-full text-[13px] px-2 py-1.5 outline-none"
                style={inputStyle}
              />
            </div>
          </div>

          <div className="mt-3">
            <FieldLabel>{t('profiles.soul')}</FieldLabel>
            <textarea
              value={form.soul}
              onChange={e => setForm(current => current ? ({ ...current, soul: e.target.value }) : current)}
              className="w-full text-[13px] p-2 outline-none resize-y font-mono"
              style={{ ...inputStyle, minHeight: '220px' }}
            />
            {!form.soul.trim() && (
              <div className="text-[12px] mt-1" style={{ color: 'var(--hud-warning)' }}>
                {t('profiles.emptySoulWarning')}
              </div>
            )}
          </div>
        </>
      )}

      {error && (
        <div className="mt-3 px-2 py-1.5 text-[12px]" style={{ color: 'var(--hud-error)', background: 'var(--hud-bg-surface)' }}>
          {error}
        </div>
      )}

      {form && (
        <div className="flex justify-end gap-2 mt-3">
          <button
            onClick={onClose}
            disabled={busy}
            className="px-2 py-1 text-[11px] cursor-pointer disabled:opacity-40"
            style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}
            type="button"
          >
            {t('memory.cancel')}
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="px-2 py-1 text-[11px] cursor-pointer disabled:opacity-40"
            style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }}
            type="button"
          >
            {busy ? '...' : t('memory.save')}
          </button>
        </div>
      )}
    </div>
  )
}

function ProfileCard({ p, onEdit }: { p: Profile; onEdit: (name: string) => void }) {
  const { t } = useTranslation()
  const gatewayStatus = p.gateway_status || 'unknown'
  const serverStatus = p.server_status || 'unknown'
  return (
    <div className="p-4" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <StatusDot status={gatewayStatus} />
        <span className="font-bold text-[14px]" style={{ color: 'var(--hud-primary)' }}>
          {p.name}
        </span>
        {p.is_default && <span className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>({t('profiles.default')})</span>}
        <span className="text-[13px] px-1.5 py-0.5 ml-auto"
          style={{ background: 'var(--hud-bg-hover)', color: p.is_local ? 'var(--hud-secondary)' : 'var(--hud-accent)' }}>
          {p.is_local ? t('profiles.local') : p.provider}
        </span>
        <button
          onClick={() => onEdit(p.name)}
          className="px-2 py-0.5 text-[11px] cursor-pointer"
          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-primary)', border: '1px solid var(--hud-border)' }}
        >
          {t('memory.edit')}
        </button>
        {gatewayStatus === 'active' && (
          <span className="text-[13px]" style={{ color: 'var(--hud-success)' }}>{t('profiles.gatewayUp')}</span>
        )}
        {serverStatus === 'running' && (
          <span className="text-[13px]" style={{ color: 'var(--hud-success)' }}>{t('profiles.serverUp')}</span>
        )}
      </div>

      <div className="space-y-1 text-[13px] mb-3">
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.model')}</span>
          <span>
            <span className="font-bold">{p.model || t('profiles.notSet')}</span>
            {p.provider && <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.via')} {p.provider}</span>}
          </span>
        </div>

        {p.base_url && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.backend')}</span>
            <span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{p.base_url}</span>
              {' '}<StatusDot status={serverStatus} />
            </span>
          </div>
        )}

        {!!p.context_length && p.context_length > 0 && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.context')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.context_length.toLocaleString()} {t('profiles.tokens')}</span>
          </div>
        )}

        {p.skin && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.skin')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.skin}</span>
          </div>
        )}

        {p.soul_summary && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.soul')}</span>
            <span className="italic" style={{ color: 'var(--hud-text)' }}>{p.soul_summary.slice(0, 80)}{p.soul_summary.length > 80 ? '...' : ''}</span>
          </div>
        )}
      </div>

      <div className="text-[13px] mb-3 py-2" style={{ borderTop: '1px solid var(--hud-border)', borderBottom: '1px solid var(--hud-border)' }}>
        <div className="grid grid-cols-3 gap-2 mb-2">
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{p.session_count || 0}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.sessions')}</span>
          </div>
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{(p.message_count || 0).toLocaleString()}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.messages')}</span>
          </div>
          <div>
            <span style={{ color: 'var(--hud-primary)' }} className="font-bold">{(p.tool_call_count || 0).toLocaleString()}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> {t('profiles.tools')}</span>
          </div>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.tokensLabel')}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>
            {formatTokens(p.total_tokens || 0)} {t('profiles.totalTokens')} ({formatTokens(p.total_input_tokens || 0)} {t('profiles.in')} / {formatTokens(p.total_output_tokens || 0)} {t('profiles.out')})
          </span>
        </div>
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.active')}</span>
          <span style={{ color: 'var(--hud-text-dim)' }}>{timeAgo(p.last_active)}</span>
        </div>
      </div>

      <div className="mb-3">
        <CapacityBar value={p.memory_chars || 0} max={p.memory_max_chars || 2200} label={t('profiles.memory')} />
        <div className="text-[13px] mb-1" style={{ color: 'var(--hud-text-dim)' }}>
          {p.memory_entries || 0} {t('profiles.entries')}, {p.memory_chars || 0}/{p.memory_max_chars || 2200} {t('profiles.chars')}
        </div>
        <CapacityBar value={p.user_chars || 0} max={p.user_max_chars || 1375} label={t('profiles.user')} />
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          {p.user_entries || 0} {t('profiles.entries')}, {p.user_chars || 0}/{p.user_max_chars || 1375} {t('profiles.chars')}
        </div>
      </div>

      <div className="space-y-1 text-[13px]">
        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.skills')}</span>
          <span>
            <span className="font-bold">{p.skill_count || 0}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}> · {t('profiles.cronJobs')} </span>
            <span className="font-bold">{p.cron_job_count || 0}</span>
          </span>
        </div>

        {!!p.toolsets?.length && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.toolsets')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.toolsets.join(', ')}</span>
          </div>
        )}

        {p.compression_enabled && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.compress')}</span>
            <span>
              <span style={{ color: 'var(--hud-success)' }}>{t('profiles.on')}</span>
              {p.compression_model && <span style={{ color: 'var(--hud-text-dim)' }}> · {p.compression_model}</span>}
            </span>
          </div>
        )}

        <div className="grid grid-cols-[80px_1fr] gap-1">
          <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.gateway')}</span>
          <span><StatusDot status={gatewayStatus} /> {gatewayStatus}
            <span className="ml-3">{t('profiles.server')} <StatusDot status={serverStatus} /> {serverStatus}</span>
          </span>
        </div>

        {!!p.api_keys?.length && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.keys')}</span>
            <span style={{ color: 'var(--hud-text-dim)' }}>{p.api_keys.join(', ')}</span>
          </div>
        )}

        {p.has_alias && (
          <div className="grid grid-cols-[80px_1fr] gap-1">
            <span style={{ color: 'var(--hud-text-dim)' }}>{t('profiles.alias')}</span>
            <span>
              <span style={{ color: 'var(--hud-success)' }}>{p.name}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> ({t('profiles.onPath')})</span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ProfilesPanel() {
  const { t } = useTranslation()
  const { data, isLoading, mutate } = useApi<ProfilesResponse>('/profiles', 30000)
  const { data: options } = useApi<ProfileOptions>('/profiles/options', 60000)
  const [editing, setEditing] = useState<string | null>(null)

  if (isLoading && !data) {
    return <Panel title={t('profiles.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('profiles.loading')}</div></Panel>
  }

  const profiles = data?.profiles || []

  return (
    <Panel title={`${t('profiles.panelTitle')} — ${data?.total || 0} ${t('profiles.total')}, ${data?.active_count || 0} ${t('profiles.activeCount')}`} className="col-span-full">
      {editing && (
        <ProfileEditor
          key={editing}
          profileName={editing}
          options={options || {}}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null)
            await mutate()
          }}
        />
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {profiles.map(profile => (
          <ProfileCard key={profile.name} p={profile} onEdit={setEditing} />
        ))}
      </div>
    </Panel>
  )
}
