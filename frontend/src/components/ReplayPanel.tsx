import { useMemo, useState } from 'react'
import Panel from './Panel'
import { useApi } from '../hooks/useApi'
import type { ReplayArtifact, ReplayDetail, ReplayEvent, ReplayRun, ReplayRunsResponse } from '../types/replay'
import VerifyPanel from './VerifyPanel'

type ReplayFilter = 'all' | 'successful' | 'failed' | 'tools' | 'files' | 'tests' | 'high-cost' | 'recent'

const RUN_FILTERS: Array<{ id: ReplayFilter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'successful', label: 'Successful' },
  { id: 'failed', label: 'Failed' },
  { id: 'tools', label: 'Has tools' },
  { id: 'files', label: 'File changes' },
  { id: 'tests', label: 'Tests' },
  { id: 'high-cost', label: 'High cost' },
  { id: 'recent', label: 'Recent' },
]

function formatDate(value?: string | null) {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleString()
}

function formatDuration(value?: number | null) {
  if (!value) return 'Unknown'
  const seconds = Math.round(value / 1000)
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return minutes ? `${minutes}m ${rest}s` : `${rest}s`
}

function formatCost(value?: number | null) {
  if (value === null || value === undefined) return 'Unknown'
  return `$${value.toFixed(4)}`
}

function compactDate(value?: string | null) {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function compactTime(value?: string | null) {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function runMatchesFilter(run: ReplayRun, filter: ReplayFilter) {
  if (filter === 'successful') return run.status === 'success'
  if (filter === 'failed') return run.status === 'failed'
  if (filter === 'tools') return run.counts.tool_calls > 0
  if (filter === 'files') return (run.counts.files_changed || 0) > 0
  if (filter === 'tests') return (run.counts.tests_passed || 0) > 0 || (run.counts.tests_failed || 0) > 0
  if (filter === 'high-cost') return (run.total_cost_usd || 0) >= 0.05
  if (filter === 'recent') {
    const raw = run.started_at || run.created_at
    if (!raw) return false
    const timestamp = new Date(raw).getTime()
    if (Number.isNaN(timestamp)) return false
    return Date.now() - timestamp <= 7 * 24 * 60 * 60 * 1000
  }
  return true
}

function eventColor(event: ReplayEvent) {
  if (event.status === 'failed') return 'var(--hud-error)'
  if (event.status === 'warning') return 'var(--hud-warning)'
  if (event.type === 'tool_call' || event.type === 'terminal_command') return 'var(--hud-accent)'
  if (event.type === 'completion') return 'var(--hud-success)'
  return 'var(--hud-primary)'
}

function RunList({
  runs,
  selectedId,
  onSelect,
}: {
  runs: ReplayRun[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <div className="space-y-1">
      {runs.map(run => (
        <button
          key={run.source_session_id}
          onClick={() => onSelect(run.source_session_id)}
          className="w-full text-left px-2 py-2 cursor-pointer transition-colors"
          style={{
            background: selectedId === run.source_session_id ? 'var(--hud-bg-hover)' : 'transparent',
            border: '1px solid var(--hud-border)',
            color: 'var(--hud-text)',
          }}
        >
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: run.status === 'success' ? 'var(--hud-success)' : 'var(--hud-warning)' }}
            />
            <span className="truncate flex-1 text-[13px]">{run.title}</span>
            <span className="text-[11px] uppercase tracking-wider shrink-0" style={{ color: 'var(--hud-text-dim)' }}>
              {run.status}
            </span>
          </div>
          <div className="mt-1 flex gap-3 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
            <span>{compactDate(run.started_at)}</span>
            <span>{formatDuration(run.duration_ms)}</span>
            <span>{formatCost(run.total_cost_usd)}</span>
          </div>
          <div className="mt-1 grid grid-cols-3 gap-x-2 gap-y-0.5 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
            <span>{run.primary_model || 'Unknown model'}</span>
            <span>{run.counts.tool_calls} tools</span>
            <span>{run.counts.skills_used || 0} skills</span>
            <span>{run.counts.files_changed ?? 'unknown'} files</span>
            <span>{(run.counts.tests_passed ?? 0) + (run.counts.tests_failed ?? 0)} tests</span>
            <span>{run.redaction_status.replaceAll('_', ' ')}</span>
          </div>
        </button>
      ))}
    </div>
  )
}

function ReceiptCard({ detail }: { detail: ReplayDetail }) {
  const { run, receipt } = detail
  return (
    <Panel title="Run Receipt">
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px]">
        <Metric label="Status" value={run.status} />
        <Metric label="Duration" value={formatDuration(run.duration_ms)} />
        <Metric label="Cost" value={formatCost(run.total_cost_usd)} />
        <Metric label="Model" value={run.primary_model || 'Unknown'} />
        <Metric label="Tool calls" value={String(run.counts.tool_calls)} />
        <Metric label="Messages" value={String(run.counts.messages)} />
        <Metric label="Skills" value={run.counts.skills_used ? String(run.counts.skills_used) : 'Unavailable'} />
        <Metric label="Redaction" value={run.redaction_status.replaceAll('_', ' ')} />
      </div>
      <div className="mt-3 pt-3 border-t text-[12px] space-y-1" style={{ borderColor: 'var(--hud-border)', color: 'var(--hud-text-dim)' }}>
        <div>Receipt hash: {receipt?.hashes?.receipt_hash || 'Pending'}</div>
        <div>Replay hash: {receipt?.hashes?.redacted_replay_hash || 'Pending'}</div>
      </div>
    </Panel>
  )
}

function proofScore(detail: ReplayDetail) {
  let score = 0
  const reasons: string[] = []
  if (detail.receipt?.hashes?.receipt_hash && detail.receipt.hashes.redacted_replay_hash) {
    score += 25
    reasons.push('local hashes')
  }
  if (detail.run.counts.tool_calls > 0) {
    score += 15
    reasons.push('tool trace')
  }
  if ((detail.run.counts.files_changed || 0) > 0 || detail.artifacts.some(artifact => artifact.type === 'git_diff')) {
    score += 15
    reasons.push('diff evidence')
  }
  if ((detail.run.counts.tests_passed || 0) > 0 || detail.artifacts.some(artifact => artifact.type === 'test_result')) {
    score += 15
    reasons.push('test evidence')
  }
  if (detail.run.counts.skills_used > 0) {
    score += 10
    reasons.push('skill provenance')
  }
  if (detail.run.redaction_status === 'redacted' || detail.run.redaction_status === 'safe_share') {
    score += 10
    reasons.push('redacted')
  }
  if (detail.events.length > 0 && detail.artifacts.length > 0) {
    score += 10
    reasons.push('timeline artifacts')
  }
  return { score: Math.min(score, 100), reasons }
}

function ProofScoreCard({ detail }: { detail: ReplayDetail }) {
  const proof = proofScore(detail)
  const color = proof.score >= 70 ? 'var(--hud-success)' : proof.score >= 40 ? 'var(--hud-warning)' : 'var(--hud-text-dim)'

  return (
    <Panel title="Proof Score">
      <div className="flex items-end gap-2">
        <div className="text-[34px] leading-none font-bold" style={{ color }}>{proof.score}</div>
        <div className="pb-1 text-[12px] uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)' }}>/ 100 local</div>
      </div>
      <div className="mt-2 h-1.5" style={{ background: 'var(--hud-bg-deep)' }}>
        <div className="h-full" style={{ width: `${proof.score}%`, background: color }} />
      </div>
      <div className="mt-2 text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
        {proof.reasons.length ? proof.reasons.join(' · ') : 'Needs exported hashes and proof artifacts.'}
      </div>
    </Panel>
  )
}

async function postReplayAction(sessionId: string, path: string, body?: unknown, method = 'POST') {
  const res = await fetch(`/api/replay/runs/${encodeURIComponent(sessionId)}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

function RedactionPanel({ sessionId }: { sessionId: string }) {
  const [detail, setDetail] = useState<ReplayDetail | null>(null)
  const [value, setValue] = useState('')
  const [replacement, setReplacement] = useState('[REDACTED_CUSTOM]')
  const [status, setStatus] = useState('Safe Share Mode has not been scanned in this view yet.')
  const [busy, setBusy] = useState(false)

  const scan = async () => {
    setBusy(true)
    setStatus('Scanning replay...')
    try {
      const result = await postReplayAction(sessionId, '/redact/scan') as ReplayDetail
      setDetail(result)
      setStatus(result.redactions?.length ? `${result.redactions.length} findings need review.` : 'No findings detected.')
    } catch (error) {
      setStatus(`Scan failed: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setBusy(false)
    }
  }

  const apply = async () => {
    if (!value.trim()) return
    setBusy(true)
    setStatus('Applying manual redaction preview...')
    try {
      const result = await postReplayAction(sessionId, '/redact/apply', {
        redactions: [{ value, replacement }],
      }) as ReplayDetail
      setDetail(result)
      setStatus(`Manual preview applied. ${result.redactions?.length || 0} findings tracked.`)
    } catch (error) {
      setStatus(`Manual redaction failed: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setBusy(false)
    }
  }

  const findings = detail?.redactions || []
  const findingCounts = findings.reduce<Record<string, number>>((counts, finding) => {
    counts[finding.type] = (counts[finding.type] || 0) + 1
    return counts
  }, {})

  return (
    <Panel title="Redaction">
      <div className="text-[13px] mb-2" style={{ color: 'var(--hud-text-dim)' }}>
        Safe Share Mode hides raw tool arguments, terminal output, reasoning, emails, token-like values, and local paths before export.
      </div>
      <div className="flex gap-1 mb-2">
        <button
          onClick={scan}
          disabled={busy}
          className="px-2 py-1 text-[12px] cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }}
        >
          {busy ? 'Working...' : 'Scan'}
        </button>
      </div>
      <div className="grid grid-cols-1 gap-1 mb-2">
        <input
          value={value}
          onChange={event => setValue(event.target.value)}
          placeholder="Exact value to redact"
          className="px-2 py-1 text-[12px] outline-none"
          style={{ background: 'var(--hud-bg-deep)', border: '1px solid var(--hud-border)', color: 'var(--hud-text)' }}
        />
        <div className="flex gap-1">
          <input
            value={replacement}
            onChange={event => setReplacement(event.target.value)}
            className="min-w-0 flex-1 px-2 py-1 text-[12px] outline-none"
            style={{ background: 'var(--hud-bg-deep)', border: '1px solid var(--hud-border)', color: 'var(--hud-text)' }}
          />
          <button
            onClick={apply}
            disabled={busy || !value.trim()}
            className="px-2 py-1 text-[12px] cursor-pointer disabled:opacity-40"
            style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text)', border: '1px solid var(--hud-border)' }}
          >
            Apply
          </button>
        </div>
      </div>
      <div className="text-[12px] mb-2" style={{ color: status.includes('failed') ? 'var(--hud-error)' : 'var(--hud-text-dim)' }}>{status}</div>
      <div className="grid grid-cols-2 gap-1 mb-2 text-[11px]">
        {['api_key', 'bearer_token', 'email', 'local_path', 'env_var', 'raw_field', 'tokenized_url', 'basic_auth_url'].map(type => (
          <div key={type} className="flex justify-between gap-2 px-2 py-1" style={{ border: '1px solid var(--hud-border)', color: 'var(--hud-text-dim)' }}>
            <span>{type.replaceAll('_', ' ')}</span>
            <span style={{ color: findingCounts[type] ? 'var(--hud-warning)' : 'var(--hud-text-dim)' }}>{findingCounts[type] || 0}</span>
          </div>
        ))}
      </div>
      {findings.length > 0 && (
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {findings.slice(0, 8).map(finding => (
            <div key={finding.finding_id} className="text-[12px] px-2 py-1" style={{ border: '1px solid var(--hud-border)' }}>
              <div className="uppercase tracking-wider" style={{ color: 'var(--hud-warning)' }}>{finding.type} · {finding.severity}</div>
              <div className="truncate" style={{ color: 'var(--hud-text-dim)' }}>{finding.field_path}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function ExportActions({ sessionId }: { sessionId: string }) {
  const [status, setStatus] = useState<string>('Safe Share Mode exports redact raw fields by default.')
  const [busy, setBusy] = useState<string | null>(null)

  const runAction = async (label: string, path: string, method = 'POST') => {
    setBusy(label)
    setStatus(`Running ${label}...`)
    try {
      const result = await postReplayAction(sessionId, path, undefined, method)
      setStatus(result.export_path ? `${label} created: ${result.export_path}` : `${label} complete.`)
    } catch (error) {
      setStatus(`${label} failed: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setBusy(null)
    }
  }

  const actionGroups = [
    {
      title: 'Prepare',
      actions: [
        ['Scan redactions', '/redact/scan'],
      ],
    },
    {
      title: 'Export',
      actions: [
        ['JSON', '/export/json'],
        ['Markdown', '/export/markdown'],
        ['HTML', '/export/html'],
        ['Fork JSON', '/fork'],
      ],
    },
    {
      title: 'Share Images',
      actions: [
        ['Default PNG', '/share-card'],
        ['Landscape PNG', '/share-card?card_format=landscape'],
        ['Square PNG', '/share-card?card_format=square'],
        ['Story PNG', '/share-card?card_format=story'],
      ],
    },
    {
      title: 'Publish',
      actions: [
        ['Publish', '/publish'],
        ['Unpublish', '/publish', 'DELETE'],
        ['Record View', '/view'],
        ['Clip', '/clip'],
      ],
    },
  ] as const

  return (
    <Panel title="Export">
      <div className="space-y-3">
        {actionGroups.map(group => (
          <div key={group.title}>
            <div className="mb-1 text-[10px] uppercase tracking-wider" style={{ color: 'var(--hud-text-dim)' }}>{group.title}</div>
            <div className="grid grid-cols-2 gap-1">
              {group.actions.map(([label, path, method]) => (
                <button
                  key={`${group.title}-${path}`}
                  onClick={() => runAction(label, path, method)}
                  disabled={busy !== null}
                  className="min-h-8 px-2 py-1 text-[12px] cursor-pointer disabled:opacity-40"
                  style={{
                    background: group.title === 'Prepare' ? 'var(--hud-bg-hover)' : 'var(--hud-primary)',
                    color: group.title === 'Prepare' ? 'var(--hud-text)' : 'var(--hud-bg-deep)',
                    border: '1px solid var(--hud-border)',
                  }}
                >
                  {busy === label ? 'Working...' : label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-2 text-[12px] break-words" style={{ color: status.includes('failed') ? 'var(--hud-error)' : 'var(--hud-text-dim)' }}>
        {status}
      </div>
    </Panel>
  )
}

function VerifyReplaySection() {
  const [open, setOpen] = useState(false)

  return (
    <Panel title="Verify Export">
      <div className="flex items-start justify-between gap-3">
        <div className="text-[12px] leading-relaxed" style={{ color: 'var(--hud-text-dim)' }}>
          Check a receipt against a redacted replay JSON when you need a portable proof check.
        </div>
        <button
          onClick={() => setOpen(value => !value)}
          className="shrink-0 px-2 py-1 text-[12px] cursor-pointer"
          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text)', border: '1px solid var(--hud-border)' }}
        >
          {open ? 'Hide' : 'Open'}
        </button>
      </div>
      {open && <VerifyPanel embedded className="mt-3" />}
    </Panel>
  )
}

function ShareCardPreview({ detail }: { detail: ReplayDetail }) {
  const { run } = detail
  const testsPassed = run.counts.tests_passed ?? 0
  const testsFailed = run.counts.tests_failed ?? 0
  const tests = testsPassed + testsFailed

  return (
    <Panel title="Share Card Preview">
      <div className="aspect-[1200/630] p-4 flex flex-col justify-between" style={{ background: 'var(--hud-bg-deep)', border: '1px solid var(--hud-border)' }}>
        <div>
          <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--hud-primary)' }}>Hermes Replay</div>
          <div className="mt-2 text-[18px] font-bold leading-tight line-clamp-2" style={{ color: 'var(--hud-text)' }}>{run.title}</div>
          <div className="mt-2 inline-block px-2 py-1 text-[11px] uppercase tracking-wider" style={{ border: '1px solid var(--hud-primary)', color: 'var(--hud-primary)' }}>
            {run.status}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[12px]">
          <Metric label="Duration" value={formatDuration(run.duration_ms)} />
          <Metric label="Cost" value={formatCost(run.total_cost_usd)} />
          <Metric label="Tools" value={String(run.counts.tool_calls)} />
          <Metric label="Skills" value={String(run.counts.skills_used || 0)} />
          <Metric label="Files" value={String(run.counts.files_changed ?? 'Unknown')} />
          <Metric label="Tests" value={tests ? `${testsPassed}/${tests} passed` : 'Unknown'} />
        </div>
        <div className="text-[10px] truncate" style={{ color: 'var(--hud-text-dim)' }}>
          Replay hash: {run.hashes.redacted_replay_hash || 'Pending'}
        </div>
      </div>
    </Panel>
  )
}

function ReplaySettingsPanel() {
  const { data, mutate } = useApi<any>('/replay/settings', 30000)
  const [busy, setBusy] = useState<string | null>(null)

  const update = async (key: string, value: boolean) => {
    if (!data) return
    setBusy(key)
    try {
      const res = await fetch('/api/replay/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, [key]: value }),
      })
      if (!res.ok) throw new Error(await res.text())
      await mutate(await res.json(), false)
    } finally {
      setBusy(null)
    }
  }

  if (!data) {
    return (
      <Panel title="Replay Settings">
        <div className="text-[13px] animate-pulse" style={{ color: 'var(--hud-text-dim)' }}>Loading settings...</div>
      </Panel>
    )
  }

  return (
    <Panel title="Replay Settings">
      <div className="space-y-2 text-[13px]">
        <div>
          <div className="uppercase tracking-wider text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>Export directory</div>
          <div className="truncate" style={{ color: 'var(--hud-primary)' }}>{data.export_dir}</div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span>Local only</span>
          <span style={{ color: 'var(--hud-success)' }}>{data.local_only ? 'On' : 'Off'}</span>
        </div>
        {(data.include_raw_logs || data.include_screenshots) && (
          <div className="px-2 py-1 text-[12px]" style={{ border: '1px solid var(--hud-warning)', color: 'var(--hud-warning)' }}>
            Raw logs and screenshots can expose private prompts, tool arguments, terminal output, paths, and secrets. Safe Share Mode remains on for default exports.
          </div>
        )}
        {[
          ['safe_share_mode', 'Safe Share Mode'],
          ['include_raw_logs', 'Include raw logs'],
          ['include_screenshots', 'Include screenshots'],
        ].map(([key, label]) => (
          <label key={key} className="flex items-center justify-between gap-2 cursor-pointer">
            <span>{label}</span>
            <input
              type="checkbox"
              checked={Boolean(data[key])}
              disabled={busy !== null || key === 'safe_share_mode'}
              onChange={event => update(key, event.target.checked)}
            />
          </label>
        ))}
      </div>
    </Panel>
  )
}

function RemotePublishPanel() {
  const { data, mutate } = useApi<any>('/replay/remote', 30000)
  const [draft, setDraft] = useState<{ repo: string; branch: string; base_url: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)

  const settings = data?.settings
  const form = draft ?? {
    repo: settings?.repo || '',
    branch: settings?.branch || 'gh-pages',
    base_url: settings?.base_url || '',
  }

  const save = async (enabled: boolean) => {
    setBusy(true)
    setStatus(null)
    try {
      const res = await fetch('/api/replay/remote', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled, ...form }),
      })
      if (!res.ok) throw new Error(await res.text())
      await mutate(await res.json(), false)
      setDraft(null)
      setStatus('Settings saved.')
    } catch (err) {
      setStatus(`Save failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBusy(false)
    }
  }

  const sync = async () => {
    setBusy(true)
    setStatus('Syncing to remote...')
    try {
      const res = await fetch('/api/replay/remote/sync', { method: 'POST' })
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'sync failed')
      setStatus(
        body.up_to_date
          ? 'Remote already up to date.'
          : `Pushed ${body.public_count} public, ${body.unlisted_count} unlisted → ${body.index_url}`
      )
      await mutate()
    } catch (err) {
      setStatus(`Sync failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBusy(false)
    }
  }

  if (!data) {
    return (
      <Panel title="Remote Publishing">
        <div className="text-[13px] animate-pulse" style={{ color: 'var(--hud-text-dim)' }}>Loading remote settings...</div>
      </Panel>
    )
  }

  const inputStyle = {
    background: 'var(--hud-bg-deep)',
    border: '1px solid var(--hud-border)',
    color: 'var(--hud-text)',
  }
  const lastSync = data.last_sync

  return (
    <Panel title="Remote Publishing">
      <div className="space-y-2 text-[13px]">
        <div className="text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
          Push published replays to a static host (GitHub Pages). Nothing is uploaded unless you sync.
        </div>
        {([
          ['repo', 'Repository (owner/name or git URL)', 'joeynyc/hermes-replays'],
          ['branch', 'Branch', 'gh-pages'],
          ['base_url', 'Base URL (optional, derived for GitHub Pages)', ''],
        ] as Array<[keyof typeof form, string, string]>).map(([key, label, placeholder]) => (
          <label key={key} className="block">
            <span className="uppercase tracking-wider text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>{label}</span>
            <input
              value={form[key]}
              placeholder={placeholder}
              onChange={event => setDraft({ ...form, [key]: event.target.value })}
              className="w-full mt-1 px-2 py-1 text-[13px] outline-none"
              style={inputStyle}
            />
          </label>
        ))}
        <div className="flex items-center gap-2">
          <button
            onClick={() => save(true)}
            disabled={busy || !form.repo.trim()}
            className="px-2 py-1 text-[12px] cursor-pointer"
            style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', opacity: busy || !form.repo.trim() ? 0.5 : 1 }}
          >
            {settings?.enabled ? 'Save' : 'Save & Enable'}
          </button>
          {settings?.enabled && (
            <>
              <button
                onClick={sync}
                disabled={busy || !data.git_available}
                className="px-2 py-1 text-[12px] cursor-pointer"
                style={{ border: '1px solid var(--hud-primary)', color: 'var(--hud-primary)', opacity: busy ? 0.5 : 1 }}
              >
                Sync now
              </button>
              <button
                onClick={() => save(false)}
                disabled={busy}
                className="px-2 py-1 text-[12px] cursor-pointer"
                style={{ border: '1px solid var(--hud-border)', color: 'var(--hud-text-dim)' }}
              >
                Disable
              </button>
            </>
          )}
        </div>
        {!data.git_available && (
          <div className="text-[12px]" style={{ color: 'var(--hud-warning)' }}>git is not available on PATH.</div>
        )}
        {status && <div className="text-[12px]" style={{ color: status.includes('failed') ? 'var(--hud-error)' : 'var(--hud-success)' }}>{status}</div>}
        {lastSync && (
          <div className="text-[12px] space-y-1" style={{ color: 'var(--hud-text-dim)' }}>
            <div>Last sync: {formatDate(lastSync.synced_at)} ({lastSync.public_count} public, {lastSync.unlisted_count} unlisted)</div>
            {lastSync.base_url && (
              <a href={lastSync.index_url} target="_blank" rel="noreferrer" className="block truncate" style={{ color: 'var(--hud-primary)' }}>
                {lastSync.index_url}
              </a>
            )}
          </div>
        )}
      </div>
    </Panel>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="uppercase tracking-wider text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>{label}</div>
      <div className="truncate" style={{ color: 'var(--hud-primary)' }}>{value}</div>
    </div>
  )
}

function Timeline({ events }: { events: ReplayEvent[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({})

  return (
    <Panel title="Timeline">
      <div className="space-y-1">
        {events.map(event => (
          <div key={event.event_id} style={{ border: '1px solid var(--hud-border)' }}>
            <button
              onClick={() => setOpen(prev => ({ ...prev, [event.event_id]: !prev[event.event_id] }))}
              className="w-full text-left px-2 py-2 cursor-pointer"
              style={{ background: 'transparent', color: 'var(--hud-text)' }}
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: eventColor(event) }} />
                <span className="text-[13px] flex-1 truncate">{event.title}</span>
                <span className="text-[11px] uppercase tracking-wider shrink-0" style={{ color: 'var(--hud-text-dim)' }}>
                  {event.type}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px]" style={{ color: 'var(--hud-text-dim)' }}>
                <span>{compactTime(event.timestamp)}</span>
                <span>{formatDuration(event.duration_ms)}</span>
                <span>Status: {event.status}</span>
                <span>Redaction: {event.redacted_content ? 'redacted' : 'summary only'}</span>
              </div>
              <div className="mt-1 text-[12px] truncate" style={{ color: 'var(--hud-text-dim)' }}>{event.summary}</div>
            </button>
            {open[event.event_id] && (
              <pre className="px-2 pb-2 text-[12px] whitespace-pre-wrap overflow-x-auto" style={{ color: 'var(--hud-text-dim)' }}>
                {event.redacted_content || event.raw_content || event.summary}
              </pre>
            )}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ProofArtifacts({ artifacts }: { artifacts: ReplayArtifact[] }) {
  const [filter, setFilter] = useState('all')
  const types = useMemo(() => ['all', ...Array.from(new Set(artifacts.map(artifact => artifact.type))).sort()], [artifacts])
  const visibleArtifacts = filter === 'all' ? artifacts : artifacts.filter(artifact => artifact.type === filter)

  return (
    <Panel title="Proof Artifacts" className="col-span-full">
      {artifacts.length ? (
        <>
          <div className="flex flex-wrap gap-1 mb-2">
            {types.map(type => (
              <button
                key={type}
                onClick={() => setFilter(type)}
                className="px-2 py-1 text-[11px] cursor-pointer"
                style={{
                  background: filter === type ? 'var(--hud-primary)' : 'var(--hud-bg-deep)',
                  color: filter === type ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                  border: '1px solid var(--hud-border)',
                }}
              >
                {type.replaceAll('_', ' ')}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {visibleArtifacts.map(artifact => (
            <div key={artifact.artifact_id} className="px-2 py-2" style={{ border: '1px solid var(--hud-border)' }}>
              <div className="text-[13px] truncate" style={{ color: 'var(--hud-primary)' }}>{artifact.title}</div>
              <div className="text-[11px] uppercase tracking-wider mt-0.5" style={{ color: 'var(--hud-text-dim)' }}>{artifact.type}</div>
              <div className="text-[12px] mt-2" style={{ color: 'var(--hud-text-dim)' }}>{artifact.summary || 'No summary.'}</div>
              {artifact.hash && (
                <div className="text-[11px] mt-2 truncate" style={{ color: 'var(--hud-text-dim)' }}>{artifact.hash}</div>
              )}
            </div>
          ))}
          </div>
        </>
      ) : (
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No proof artifacts detected.</div>
      )}
    </Panel>
  )
}

function RawTracePanel({ detail }: { detail: ReplayDetail }) {
  const [open, setOpen] = useState(false)
  const trace = useMemo(() => JSON.stringify({
    run: detail.run,
    events: detail.events.map(event => ({
      event_id: event.event_id,
      type: event.type,
      title: event.title,
      summary: event.summary,
      redacted_content: event.redacted_content,
      timestamp: event.timestamp,
      duration_ms: event.duration_ms,
      status: event.status,
      metadata: event.metadata,
    })),
    artifacts: detail.artifacts,
    receipt: detail.receipt,
    missing_data: detail.missing_data,
  }, null, 2), [detail])

  return (
    <Panel title="Raw Trace" className="col-span-full">
      <button
        onClick={() => setOpen(value => !value)}
        className="px-2 py-1 text-[12px] cursor-pointer"
        style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text)', border: '1px solid var(--hud-border)' }}
      >
        {open ? 'Hide normalized trace' : 'Show normalized trace'}
      </button>
      {open && (
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap text-[12px]" style={{ color: 'var(--hud-text-dim)' }}>
          {trace}
        </pre>
      )}
    </Panel>
  )
}

function SkillProvenancePanel() {
  const { data } = useApi<any>('/replay/skills', 30000)
  const skills = data?.skills || []

  return (
    <Panel title="Skill Provenance" className="col-span-full">
      {skills.length ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {skills.slice(0, 8).map((skill: any) => (
            <div key={skill.name} className="px-2 py-2" style={{ border: '1px solid var(--hud-border)' }}>
              <div className="text-[13px] truncate" style={{ color: 'var(--hud-primary)' }}>{skill.name}</div>
              <div className="text-[12px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>
                {skill.usage_count} runs · {skill.success_rate == null ? 'unknown' : `${Math.round(skill.success_rate * 100)}%`} success
              </div>
              <div className="text-[11px] mt-2" style={{ color: 'var(--hud-text-dim)' }}>
                version {skill.version || 'unavailable'} · hash {skill.hash || 'unavailable'}
              </div>
              <div className="text-[11px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>
                first {formatDate(skill.first_used_at)} · last {formatDate(skill.last_used_at)}
              </div>
              <div className="text-[11px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>
                mutation receipts {(skill.mutation_receipts || []).length}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No skill provenance indexed yet.</div>
      )}
    </Panel>
  )
}

function ReplayGalleryPanel() {
  const { data } = useApi<any>('/replay/gallery', 30000)
  const entries = data?.entries || []
  const galleryPath = entries[0]?.manifest_path ? String(entries[0].manifest_path).replace(/(public|unlisted)\/.*\/publish\.json$/, 'gallery.html') : null

  return (
    <Panel title="Published Gallery" className="col-span-full">
      {galleryPath && (
        <div className="mb-2 text-[12px] truncate" style={{ color: 'var(--hud-text-dim)' }}>
          Static index: {galleryPath}
        </div>
      )}
      {entries.length ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {entries.slice(0, 9).map((entry: any) => (
            <div key={entry.manifest_path} className="px-2 py-2" style={{ border: '1px solid var(--hud-border)' }}>
              <div className="text-[13px] truncate" style={{ color: 'var(--hud-primary)' }}>{entry.title || entry.replay_id}</div>
              <div className="text-[11px] uppercase tracking-wider mt-0.5" style={{ color: 'var(--hud-text-dim)' }}>{entry.visibility}</div>
              <div className="text-[12px] mt-2 truncate" style={{ color: 'var(--hud-text-dim)' }}>{entry.entry}</div>
              <div className="text-[11px] mt-2" style={{ color: 'var(--hud-text-dim)' }}>
                views {entry.view_count || 0} · forks {entry.fork_count || 0}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No locally published replays yet.</div>
      )}
    </Panel>
  )
}

export default function ReplayPanel() {
  const { data, isLoading, error } = useApi<ReplayRunsResponse>('/replay/runs?limit=50', 30000)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<ReplayFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const runs = useMemo(() => data?.runs ?? [], [data?.runs])
  const visibleRuns = useMemo(() => {
    const q = query.trim().toLowerCase()
    return runs.filter(run => {
      const matchesQuery = !q ||
        run.title.toLowerCase().includes(q) ||
        run.source_session_id.toLowerCase().includes(q) ||
        (run.primary_model || '').toLowerCase().includes(q)
      return matchesQuery && runMatchesFilter(run, filter)
    })
  }, [filter, query, runs])

  const activeId = selectedId || visibleRuns[0]?.source_session_id || null
  const { data: detail, isLoading: detailLoading } = useApi<ReplayDetail>(
    activeId ? `/replay/runs/${encodeURIComponent(activeId)}` : null,
    activeId ? 30000 : 0
  )

  if (isLoading && !data) {
    return <Panel title="Replay" className="col-span-full"><div className="glow text-[13px] animate-pulse">Loading replay runs...</div></Panel>
  }

  if (error) {
    return <Panel title="Replay" className="col-span-full"><div className="text-[13px]" style={{ color: 'var(--hud-error)' }}>Could not load replay runs.</div></Panel>
  }

  return (
    <>
      <Panel title="Replay Runs">
        <input
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="Search sessions, IDs, models"
          className="w-full mb-2 px-2 py-1 text-[13px] outline-none"
          style={{
            background: 'var(--hud-bg-deep)',
            border: '1px solid var(--hud-border)',
            color: 'var(--hud-text)',
          }}
        />
        <div className="flex flex-wrap gap-1 mb-2">
          {RUN_FILTERS.map(item => (
            <button
              key={item.id}
              onClick={() => setFilter(item.id)}
              className="px-2 py-1 text-[11px] cursor-pointer"
              style={{
                background: filter === item.id ? 'var(--hud-primary)' : 'var(--hud-bg-deep)',
                color: filter === item.id ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
                border: '1px solid var(--hud-border)',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        {visibleRuns.length ? (
          <RunList runs={visibleRuns} selectedId={activeId} onSelect={setSelectedId} />
        ) : (
          <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>No replay candidates found.</div>
        )}
      </Panel>

      {detailLoading && !detail ? (
        <Panel title="Replay Detail"><div className="glow text-[13px] animate-pulse">Building replay timeline...</div></Panel>
      ) : detail ? (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-2">
            <Timeline events={detail.events} />
            <div className="space-y-2">
              <ReceiptCard detail={detail} />
              <ProofScoreCard detail={detail} />
              <RedactionPanel sessionId={detail.run.source_session_id} />
              <ExportActions sessionId={detail.run.source_session_id} />
              <ShareCardPreview detail={detail} />
              <ReplaySettingsPanel />
              <RemotePublishPanel />
              <VerifyReplaySection />
              {detail.missing_data.length > 0 && (
                <Panel title="Missing Data">
                  <ul className="space-y-1 text-[13px]" style={{ color: 'var(--hud-warning)' }}>
                    {detail.missing_data.map(item => <li key={item}>{item}</li>)}
                  </ul>
                </Panel>
              )}
            </div>
          </div>
          <Panel title="Run Metadata" className="col-span-full">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[13px]">
              <Metric label="Session ID" value={detail.run.source_session_id} />
              <Metric label="Started" value={formatDate(detail.run.started_at)} />
              <Metric label="Ended" value={formatDate(detail.run.ended_at)} />
            </div>
          </Panel>
          <ProofArtifacts artifacts={detail.artifacts || []} />
          <SkillProvenancePanel />
          <ReplayGalleryPanel />
          <RawTracePanel detail={detail} />
        </>
      ) : (
        <Panel title="Replay Detail"><div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>Select a run to inspect its replay.</div></Panel>
      )}
    </>
  )
}
