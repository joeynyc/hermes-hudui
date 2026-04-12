import { useApi } from '../hooks/useApi'
import Panel, { Sparkline } from './Panel'
import { formatTokens } from '../lib/utils'

function StatCard({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="text-center p-2" style={{ background: 'var(--hud-bg-panel)' }}>
      <div className="stat-value text-[18px]">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function toneForMode(mode: string) {
  if (mode === 'actual') return 'var(--hud-success)'
  if (mode === 'estimated' || mode === 'mixed') return 'var(--hud-accent)'
  if (mode === 'included') return 'var(--hud-primary)'
  return 'var(--hud-warning)'
}

function formatUsd(value: number) {
  return `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatUsdCompact(value: number) {
  const n = Number(value || 0)
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 10_000) return `$${(n / 1_000).toFixed(0)}k`
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}k`
  return `$${n.toFixed(0)}`
}

function headlineText(bucket: any) {
  const badge = bucket?.cost_badge || 'n/a'
  return badge === 'included' ? 'INCLUDED' : badge
}

function statusText(bucket: any) {
  let text = bucket?.cost_caption || 'pricing unavailable'
  if (bucket?.cost_is_partial) text += ' · unknown rows omitted from USD totals'
  return text
}

function apiEquivalentText(bucket: any) {
  if (!bucket?.api_equivalent_available) return 'n/a'
  const low = Number(bucket?.api_equivalent_lower_usd || 0)
  const high = Number(bucket?.api_equivalent_upper_usd || 0)
  if (Math.abs(high - low) < 0.005) return formatUsd(low)
  return `${formatUsd(low)}–${formatUsd(high)}`
}

function StatusBreakdown({ bucket }: { bucket: any }) {
  return (
    <div className="grid grid-cols-5 gap-2 mt-3">
      <StatCard value={bucket.actual_session_count || 0} label="actual" />
      <StatCard value={bucket.estimated_session_count || 0} label="stored est" />
      <StatCard value={bucket.derived_session_count || 0} label="fallback" />
      <StatCard value={bucket.included_session_count || 0} label="included" />
      <StatCard value={bucket.unknown_session_count || 0} label="unknown" />
    </div>
  )
}

function SpendBreakdown({ bucket }: { bucket: any }) {
  const hasTrackedSpend = (bucket.actual_cost_usd || 0) > 0 || (bucket.estimated_cost_usd || 0) > 0 || (bucket.derived_cost_usd || 0) > 0
  const hasAnyStatus = (bucket.included_session_count || 0) > 0 || (bucket.unknown_session_count || 0) > 0
  if (!hasTrackedSpend && !hasAnyStatus) return null

  return (
    <div className="text-[13px] space-y-0.5 mt-2 pt-2" style={{ borderTop: '1px solid var(--hud-border)' }}>
      {(bucket.actual_session_count || 0) > 0 && (
        <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Actual spend</span><span style={{ color: 'var(--hud-success)' }}>{formatUsd(bucket.actual_cost_usd || 0)}</span></div>
      )}
      {(bucket.estimated_session_count || 0) > 0 && (
        <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Stored estimates</span><span style={{ color: 'var(--hud-accent)' }}>{formatUsd(bucket.estimated_cost_usd || 0)}</span></div>
      )}
      {(bucket.derived_session_count || 0) > 0 && (
        <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Fallback estimates</span><span style={{ color: 'var(--hud-warning)' }}>{formatUsd(bucket.derived_cost_usd || 0)}</span></div>
      )}
      {(bucket.included_session_count || 0) > 0 && (
        <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Included sessions</span><span style={{ color: 'var(--hud-primary)' }}>{bucket.included_session_count}</span></div>
      )}
      {(bucket.unknown_session_count || 0) > 0 && (
        <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Unknown pricing</span><span style={{ color: 'var(--hud-warning)' }}>{bucket.unknown_session_count}</span></div>
      )}
    </div>
  )
}

function ApiEquivalentBlock({ bucket }: { bucket: any }) {
  if (!bucket?.api_equivalent_available && !bucket?.api_equivalent_is_partial) return null

  return (
    <div className="text-[13px] space-y-1 mt-2 pt-2" style={{ borderTop: '1px solid var(--hud-border)' }}>
      <div className="flex justify-between font-bold">
        <span style={{ color: 'var(--hud-text-dim)' }}>API-equivalent</span>
        <span style={{ color: 'var(--hud-warning)' }}>{apiEquivalentText(bucket)}</span>
      </div>
      <div style={{ color: 'var(--hud-text-dim)' }}>
        {bucket.api_equivalent_caption || 'no official API-equivalent pricing snapshot'}
      </div>
      {bucket.api_equivalent_label && (
        <div style={{ color: 'var(--hud-text-dim)' }}>
          Source: {bucket.api_equivalent_label}
        </div>
      )}
    </div>
  )
}

function ModelCard({ m }: { m: any }) {
  const tone = toneForMode(m.cost_mode)
  const badge = headlineText(m)

  return (
    <div className="p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="flex items-center justify-between mb-2 gap-2">
        <span className="font-bold text-[13px] break-all" style={{ color: 'var(--hud-primary)' }}>{m.model}</span>
        <span className="text-[13px] px-1.5 py-0.5 whitespace-nowrap" style={{ background: 'var(--hud-bg-hover)', color: tone }}>
          {badge}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[13px] mb-2">
        <div><span style={{ color: 'var(--hud-primary)' }}>{m.session_count}</span> <span style={{ color: 'var(--hud-text-dim)' }}>sess</span></div>
        <div><span style={{ color: 'var(--hud-primary)' }}>{(m.message_count || 0).toLocaleString()}</span> <span style={{ color: 'var(--hud-text-dim)' }}>msgs</span></div>
        <div><span style={{ color: 'var(--hud-primary)' }}>{formatTokens(m.total_tokens || 0)}</span> <span style={{ color: 'var(--hud-text-dim)' }}>tok</span></div>
      </div>

      <div className="text-[13px] space-y-0.5" style={{ color: 'var(--hud-text-dim)' }}>
        <div className="flex justify-between"><span>Input</span><span>{formatTokens(m.input_tokens || 0)}</span></div>
        <div className="flex justify-between"><span>Output</span><span>{formatTokens(m.output_tokens || 0)}</span></div>
        {(m.cache_read_tokens || 0) > 0 && (
          <div className="flex justify-between"><span>Cache read</span><span>{formatTokens(m.cache_read_tokens || 0)}</span></div>
        )}
      </div>

      <SpendBreakdown bucket={m} />
      <ApiEquivalentBlock bucket={m} />

      <div className="mt-2 pt-2 text-[13px]" style={{ borderTop: '1px solid var(--hud-border)', color: tone }}>
        {statusText(m)}
      </div>
      <div className="text-[13px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>
        Billing: {m.billing_label || 'pricing unavailable'}
      </div>
    </div>
  )
}

export default function TokenCostsPanel() {
  const { data, isLoading } = useApi('/token-costs', 60000)

  if (isLoading && !data) {
    return <Panel title="Token Costs" className="col-span-full"><div className="glow text-[13px] animate-pulse">Calculating tracked billing...</div></Panel>
  }

  if (!data) {
    return <Panel title="Token Costs" className="col-span-full"><div className="glow text-[13px] animate-pulse">Calculating tracked billing...</div></Panel>
  }

  const today = data.today || {}
  const allTime = data.all_time || {}
  const byModel = data.by_model || []
  const dailyTrend = data.daily_trend || []
  const summary = data.cost_summary || {}

  const trendUsesApiEquivalent = summary.api_equivalent_available && summary.all_sessions_included
  const trendUsesUsage = !trendUsesApiEquivalent && (summary.all_sessions_included || (!summary.has_billable_sessions && summary.has_included_sessions))
  const trendValues = trendUsesApiEquivalent
    ? dailyTrend.map((d: any) => d.api_equivalent_lower_usd || 0)
    : trendUsesUsage
      ? dailyTrend.map((d: any) => d.tokens || 0)
      : dailyTrend.map((d: any) => d.cost || 0)
  const trendLabel = trendUsesApiEquivalent
    ? 'API-equivalent/day (lower bound)'
    : trendUsesUsage
      ? 'Included usage/day'
      : 'Tracked USD/day'

  return (
    <>
      <Panel title={`Today — ${headlineText(today)}`}>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatCard value={today.session_count || 0} label="sessions" />
          <StatCard value={today.message_count || 0} label="messages" />
        </div>

        <div className="text-[13px] space-y-1">
          <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Input</span><span>{formatTokens(today.input_tokens || 0)}</span></div>
          <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Output</span><span>{formatTokens(today.output_tokens || 0)}</span></div>
          <div className="flex justify-between"><span style={{ color: 'var(--hud-text-dim)' }}>Cache read</span><span>{formatTokens(today.cache_read_tokens || 0)}</span></div>
          <div className="flex justify-between font-bold pt-1" style={{ borderTop: '1px solid var(--hud-border)' }}>
            <span>Total</span><span>{formatTokens(today.total_tokens || 0)}</span>
          </div>
        </div>

        <div className="mt-3 text-[20px] font-bold text-center" style={{ color: toneForMode(today.cost_mode || 'unknown') }}>
          {headlineText(today)}
        </div>
        <div className="text-[13px] text-center" style={{ color: 'var(--hud-text-dim)' }}>
          {statusText(today)}
        </div>

        <SpendBreakdown bucket={today} />
        <ApiEquivalentBlock bucket={today} />
        <StatusBreakdown bucket={today} />
      </Panel>

      <Panel title={`All Time — ${headlineText(allTime)}`}>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatCard value={allTime.session_count || 0} label="sessions" />
          <StatCard value={(allTime.message_count || 0).toLocaleString()} label="messages" />
          <StatCard value={formatTokens(allTime.total_tokens || 0)} label="total tokens" />
          <StatCard value={(allTime.tool_call_count || 0).toLocaleString()} label="tool calls" />
        </div>

        <div className="mt-1 text-[20px] font-bold text-center" style={{ color: toneForMode(allTime.cost_mode || 'unknown') }}>
          {headlineText(allTime)}
        </div>
        <div className="text-[13px] text-center" style={{ color: 'var(--hud-text-dim)' }}>
          {statusText(allTime)}
        </div>

        <SpendBreakdown bucket={allTime} />
        <ApiEquivalentBlock bucket={allTime} />
        <StatusBreakdown bucket={allTime} />

        {summary.has_fallback_estimates && (
          <div className="mt-3 text-[13px]" style={{ color: 'var(--hud-warning)' }}>
            Fallback estimates were used for older rows missing persisted billing metadata.
          </div>
        )}
      </Panel>

      {byModel.length > 0 && (
        <Panel title={`By Model — ${byModel.length} models`} className="col-span-full">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
            {byModel.map((m: any) => (
              <ModelCard key={m.model} m={m} />
            ))}
          </div>
        </Panel>
      )}

      {dailyTrend.length > 0 && (
        <Panel title={trendUsesApiEquivalent ? 'Daily API-equivalent' : trendUsesUsage ? 'Daily Included Usage' : 'Daily Tracked Spend'} className="col-span-full">
          <div className="mb-3">
            <div className="text-[13px] uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>
              {trendLabel}
            </div>
            <Sparkline values={trendValues} width={800} height={50} />
          </div>
          <div className="text-[13px] grid grid-cols-5 gap-1">
            {dailyTrend.slice(-10).map((d: any) => (
              <div key={d.date} className="text-center py-1" style={{ background: 'var(--hud-bg-panel)' }}>
                <div style={{ color: 'var(--hud-text-dim)' }}>{String(d.date || '').slice(5)}</div>
                <div style={{ color: trendUsesApiEquivalent ? 'var(--hud-warning)' : trendUsesUsage ? 'var(--hud-primary)' : toneForMode(d.cost_mode || 'unknown') }}>
                  {trendUsesApiEquivalent ? formatUsdCompact(d.api_equivalent_lower_usd || 0) : trendUsesUsage ? formatTokens(d.tokens || 0) : headlineText(d)}
                </div>
                <div className="text-[13px]">{(d.sessions || 0).toLocaleString()} sess</div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </>
  )
}
