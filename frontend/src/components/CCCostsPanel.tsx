import type { ReactNode } from 'react'
import { useApi } from '../hooks/useApi'
import Panel, { Sparkline } from './Panel'
import { formatTokens } from '../lib/utils'
import { useTranslation } from '../i18n'

function StatCard({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="text-center p-2" style={{ background: 'var(--hud-bg-panel)' }}>
      <div className="stat-value text-[18px]">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function money(value: number | null | undefined) {
  return `$${(value || 0).toFixed(2)}`
}

function DeltaBadge({ value, pct }: { value: number; pct?: number | null }) {
  const color = value > 0 ? 'var(--hud-warning)' : value < 0 ? 'var(--hud-success)' : 'var(--hud-text-dim)'
  const sign = value > 0 ? '+' : ''
  return (
    <span style={{ color }}>
      {sign}{money(value)}{pct !== null && pct !== undefined ? ` (${sign}${pct.toFixed(1)}%)` : ''}
    </span>
  )
}

function DetailRow({ label, value, tone }: { label: string; value: ReactNode; tone?: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span style={{ color: 'var(--hud-text-dim)' }}>{label}</span>
      <span className="text-right" style={{ color: tone || 'inherit' }}>{value}</span>
    </div>
  )
}

function ModelCard({ m }: { m: any }) {
  const { t } = useTranslation()
  const isFree = m.matched_pricing?.includes('local') || m.matched_pricing?.includes('free')
  const pricingColor = isFree ? 'var(--hud-success)' : 'var(--hud-accent)'

  return (
    <div className="p-3" style={{ background: 'var(--hud-bg-panel)', border: '1px solid var(--hud-border)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-[13px]" style={{ color: 'var(--hud-primary)' }}>{m.model}</span>
        <span className="text-[13px] px-1.5 py-0.5" style={{ background: 'var(--hud-bg-hover)', color: pricingColor }}>
          {isFree ? t('tokenCosts.free') : money(m.billed_cost_usd ?? m.cost)}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-[13px] mb-2">
        <div><span style={{ color: 'var(--hud-primary)' }}>{m.session_count}</span> <span style={{ color: 'var(--hud-text-dim)' }}>{t('tokenCosts.sess')}</span></div>
        <div><span style={{ color: 'var(--hud-primary)' }}>{m.message_count.toLocaleString()}</span> <span style={{ color: 'var(--hud-text-dim)' }}>{t('tokenCosts.msgs')}</span></div>
        <div><span style={{ color: 'var(--hud-primary)' }}>{formatTokens(m.input_tokens + m.output_tokens)}</span> <span style={{ color: 'var(--hud-text-dim)' }}>{t('tokenCosts.tok')}</span></div>
      </div>
      <div className="text-[13px] space-y-0.5" style={{ color: 'var(--hud-text-dim)' }}>
        <DetailRow label={t('tokenCosts.input')} value={formatTokens(m.input_tokens)} />
        <DetailRow label={t('tokenCosts.output')} value={formatTokens(m.output_tokens)} />
        {m.cache_read_tokens > 0 && (
          <DetailRow label={t('tokenCosts.cacheRead')} value={formatTokens(m.cache_read_tokens)} />
        )}
        {m.cache_savings_usd > 0 && (
          <DetailRow label={t('tokenCosts.cacheSaved')} value={money(m.cache_savings_usd)} tone="var(--hud-success)" />
        )}
      </div>
      {!isFree && (
        <div className="mt-2 pt-2 text-[13px] space-y-0.5" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <DetailRow label={t('tokenCosts.estimated')} value={money(m.estimated_cost_usd)} />
          <DetailRow label={t('tokenCosts.actual')} value={money(m.actual_cost_usd)} />
          <DetailRow label={t('tokenCosts.delta')} value={<DeltaBadge value={m.actual_delta_usd || 0} pct={m.actual_delta_pct} />} />
          <div className="font-bold">
            <DetailRow label={t('tokenCosts.billed')} value={money(m.billed_cost_usd)} tone="var(--hud-accent)" />
          </div>
        </div>
      )}
      {isFree && (
        <div className="mt-2 pt-2 text-[13px]" style={{ borderTop: '1px solid var(--hud-border)', color: 'var(--hud-success)' }}>
          {t('tokenCosts.localModel')}
        </div>
      )}
      <div className="text-[13px] mt-1" style={{ color: 'var(--hud-text-dim)' }}>
        {t('tokenCosts.pricing')}: {m.matched_pricing}
      </div>
    </div>
  )
}

export default function CCCostsPanel() {
  const { t } = useTranslation()
  const { data, isLoading } = useApi('/cc-costs', 60000)

  if (isLoading && !data) {
    return <Panel title={t('cc.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('cc.loading')}</div></Panel>
  }

  const {
    today,
    all_time: allTime,
    by_model: byModel,
    daily_trend: dailyTrend,
    top_sessions: topSessions = [],
    trend_summary: trendSummary = {},
  } = data
  const costValues = dailyTrend.map((d: any) => d.billed_cost_usd ?? d.cost)

  // Compute cost breakdown across all models
  let totalInputCost = 0, totalOutputCost = 0, totalCacheRCost = 0, totalCacheWCost = 0
  for (const m of byModel) {
    const p = data.pricing_table?.[m.model] || data.pricing_table?.[m.matched_pricing?.split(' ')[0]]
    if (p) {
      totalInputCost += (m.input_tokens / 1_000_000) * p.input
      totalOutputCost += (m.output_tokens / 1_000_000) * p.output
      totalCacheRCost += (m.cache_read_tokens / 1_000_000) * p.cache_read
      totalCacheWCost += (m.cache_write_tokens / 1_000_000) * p.cache_write
    }
  }

  return (
    <>
      {/* Today */}
      <Panel title={`${t('cc.today')} — ${money(today.billed_cost_usd ?? today.estimated_cost_usd)}`}>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatCard value={today.session_count} label={t('tokenCosts.sessions')} />
          <StatCard value={today.message_count} label={t('tokenCosts.messages')} />
        </div>
        <div className="text-[13px] space-y-1">
          <DetailRow label={t('tokenCosts.input')} value={formatTokens(today.input_tokens)} />
          <DetailRow label={t('tokenCosts.output')} value={formatTokens(today.output_tokens)} />
          <DetailRow label={t('tokenCosts.cacheRead')} value={formatTokens(today.cache_read_tokens)} />
          <div className="font-bold pt-1" style={{ borderTop: '1px solid var(--hud-border)' }}>
            <DetailRow label={t('tokenCosts.total')} value={formatTokens(today.total_tokens)} />
          </div>
        </div>
        <div className="mt-3 text-[20px] font-bold text-center" style={{ color: 'var(--hud-accent)' }}>
          {money(today.billed_cost_usd ?? today.estimated_cost_usd)}
        </div>
        <div className="text-[13px] text-center" style={{ color: 'var(--hud-text-dim)' }}>{t('tokenCosts.billedToday')}</div>
      </Panel>

      {/* All time */}
      <Panel title={`${t('cc.total')} — ${money(allTime.billed_cost_usd ?? allTime.estimated_cost_usd)}`}>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatCard value={allTime.session_count} label={t('tokenCosts.sessions')} />
          <StatCard value={(allTime.message_count || 0).toLocaleString()} label={t('tokenCosts.messages')} />
          <StatCard value={formatTokens(allTime.total_tokens)} label={t('tokenCosts.totalTokens')} />
          <StatCard value={(allTime.tool_call_count || 0).toLocaleString()} label={t('tokenCosts.toolCalls')} />
        </div>

        <div className="text-[13px] space-y-0.5 mt-2 pt-2" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <DetailRow label={t('tokenCosts.estimated')} value={money(allTime.estimated_cost_usd)} />
          <DetailRow label={t('tokenCosts.cacheSaved')} value={money(allTime.cache_savings_usd)} tone="var(--hud-success)" />
        </div>

        {/* Cost by type */}
        <div className="text-[13px] space-y-0.5 mt-2 pt-2" style={{ borderTop: '1px solid var(--hud-border)' }}>
          <DetailRow label={t('tokenCosts.inputCost')} value={money(totalInputCost)} tone="var(--hud-primary)" />
          <DetailRow label={t('tokenCosts.outputCost')} value={money(totalOutputCost)} tone="var(--hud-accent)" />
          <DetailRow label={t('tokenCosts.cacheRead')} value={money(totalCacheRCost)} tone="var(--hud-success)" />
          <DetailRow label={t('tokenCosts.cacheWrite')} value={money(totalCacheWCost)} tone="var(--hud-warning)" />
        </div>

        <div className="mt-3 text-[20px] font-bold text-center" style={{ color: 'var(--hud-accent)' }}>
          {money(allTime.billed_cost_usd ?? allTime.estimated_cost_usd)}
        </div>
        <div className="text-[13px] text-center" style={{ color: 'var(--hud-text-dim)' }}>
          {t('cc.estimatedAllTime')} ({byModel.length} {t('tokenCosts.models')})
        </div>
      </Panel>

      {/* Trend summary */}
      <Panel title={t('tokenCosts.trend')}>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatCard value={money(trendSummary.recent_7d_cost_usd)} label={t('tokenCosts.last7Days')} />
          <StatCard value={money(trendSummary.previous_7d_cost_usd)} label={t('tokenCosts.prev7Days')} />
        </div>
        <div className="text-[13px] space-y-1">
          <DetailRow label={t('tokenCosts.change')} value={<DeltaBadge value={trendSummary.delta_usd || 0} pct={trendSummary.delta_pct} />} />
          <DetailRow label={t('tokenCosts.cacheSaved')} value={money(allTime.cache_savings_usd)} tone="var(--hud-success)" />
          <DetailRow label={t('tokenCosts.actualCoverage')} value={`${allTime.actual_coverage_pct || 0}%`} />
        </div>
      </Panel>

      {/* Top sessions */}
      {topSessions.length > 0 && (
        <Panel title={t('cc.topSessions')} className="col-span-full">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead style={{ color: 'var(--hud-text-dim)' }}>
                <tr className="text-left" style={{ borderBottom: '1px solid var(--hud-border)' }}>
                  <th className="py-2 pr-3 font-normal">{t('tokenCosts.session')}</th>
                  <th className="py-2 pr-3 font-normal">{t('tokenCosts.model')}</th>
                  <th className="py-2 pr-3 font-normal text-right">{t('tokenCosts.tokens')}</th>
                  <th className="py-2 pr-3 font-normal text-right">{t('tokenCosts.toolCalls')}</th>
                  <th className="py-2 pr-3 font-normal text-right">{t('tokenCosts.estimated')}</th>
                  <th className="py-2 pr-3 font-normal text-right">{t('tokenCosts.actual')}</th>
                  <th className="py-2 font-normal text-right">{t('tokenCosts.billed')}</th>
                </tr>
              </thead>
              <tbody>
                {topSessions.map((s: any) => (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--hud-border)' }}>
                    <td className="py-2 pr-3 max-w-[260px]">
                      <div className="truncate" style={{ color: 'var(--hud-primary)' }}>{s.project || s.title || s.id}</div>
                      <div style={{ color: 'var(--hud-text-dim)' }}>{s.date}</div>
                    </td>
                    <td className="py-2 pr-3">{s.model}</td>
                    <td className="py-2 pr-3 text-right">{formatTokens(s.total_tokens)}</td>
                    <td className="py-2 pr-3 text-right">{(s.tool_call_count || 0).toLocaleString()}</td>
                    <td className="py-2 pr-3 text-right">{money(s.estimated_cost_usd)}</td>
                    <td className="py-2 pr-3 text-right">{s.actual_cost_usd > 0 ? money(s.actual_cost_usd) : '—'}</td>
                    <td className="py-2 text-right font-bold" style={{ color: 'var(--hud-accent)' }}>{money(s.billed_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Per-model breakdown */}
      {byModel.length > 0 && (
        <Panel title={`${t('tokenCosts.byModel')} — ${byModel.length} ${t('tokenCosts.models')}`} className="col-span-full">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
            {byModel.map((m: any) => (
              <ModelCard key={m.model} m={m} />
            ))}
          </div>
        </Panel>
      )}

      {/* Daily trend */}
      {dailyTrend.length > 0 && (
        <Panel title={t('cc.dailyTrend')} className="col-span-full">
          <div className="mb-3">
            <div className="text-[13px] uppercase tracking-wider mb-1" style={{ color: 'var(--hud-text-dim)' }}>
              {t('tokenCosts.costPerDay')}
            </div>
            <Sparkline values={costValues} width={800} height={50} />
          </div>
          <div className="text-[13px] grid grid-cols-5 gap-1">
            {dailyTrend.slice(-10).map((d: any) => (
              <div key={d.date} className="text-center py-1" style={{ background: 'var(--hud-bg-panel)' }}>
                <div style={{ color: 'var(--hud-text-dim)' }}>{d.date.slice(5)}</div>
                <div style={{ color: 'var(--hud-accent)' }}>{money(d.billed_cost_usd ?? d.cost)}</div>
                <div className="text-[13px]">{formatTokens(d.tokens)}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </>
  )
}
