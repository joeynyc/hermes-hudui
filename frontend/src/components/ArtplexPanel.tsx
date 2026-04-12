import { useApi } from '../hooks/useApi'
import Panel from './Panel'

function humanize(value?: string) {
  if (!value) return '—'
  return value.replace(/_/g, ' ')
}

function formatTimestamp(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('sv-SE', { hour12: false })
}

function statusColor(status?: string) {
  if (status === 'launchable' || status === 'ready' || status === 'green' || status === 'live') return 'var(--hud-success)'
  if (status === 'conditional' || status === 'staged_validation' || status === 'mixed' || status === 'dry_run') return 'var(--hud-accent)'
  if (status === 'idle') return 'var(--hud-primary)'
  return 'var(--hud-warning)'
}

function priorityColor(priority?: string) {
  if (priority === 'P0') return 'var(--hud-error)'
  if (priority === 'P1') return 'var(--hud-warning)'
  return 'var(--hud-accent)'
}

function severityColor(severity?: string) {
  if (severity === 'critical') return 'var(--hud-error)'
  if (severity === 'high') return 'var(--hud-warning)'
  return 'var(--hud-accent)'
}

function shortUrl(value?: string) {
  if (!value) return '—'
  try {
    const url = new URL(value)
    return `${url.hostname}${url.pathname}${url.search}`
  } catch {
    return value
  }
}

function freshnessText(source: any) {
  const mins = Number(source?.freshness_delta_minutes || 0)
  if (source?.is_freshest) return 'freshest'
  if (mins < 60) return `${mins}m stale`
  const hours = mins / 60
  if (hours < 24) return `${hours.toFixed(hours < 10 ? 1 : 0)}h stale`
  return `${(hours / 24).toFixed(1)}d stale`
}

function provenanceColor(status?: string) {
  if (status === 'clean') return 'var(--hud-success)'
  if (status === 'untracked') return 'var(--hud-warning)'
  if (status === 'modified') return 'var(--hud-accent)'
  return 'var(--hud-text-dim)'
}

function measurementModeLabel(mode?: string) {
  if (mode === 'dry_run') return 'dry-run only'
  if (mode === 'live') return 'live publish'
  if (mode === 'mixed') return 'mixed live/dry-run'
  if (mode === 'skipped_only') return 'skipped only'
  if (mode === 'idle') return 'idle'
  return humanize(mode)
}

function attemptSummary(item: any) {
  const live = Number(item?.succeeded || 0) + Number(item?.failed || 0)
  const skipped = Number(item?.skipped || 0)
  if (live === 0 && skipped === 0) return `${item?.attempted || 0} attempts`
  return `${live} live · ${skipped} skipped`
}

function QueueCard({ item, accent, subtitle }: { item: any; accent: string; subtitle?: string }) {
  return (
    <div className="p-2" style={{ background: 'var(--hud-bg-panel)', borderLeft: `3px solid ${accent}` }}>
      <div className="flex items-center gap-2 flex-wrap">
        <span style={{ color: accent }}>◆</span>
        <span className="font-bold">{item.ip_name || item.campaign_id}</span>
        <span style={{ color: 'var(--hud-text-dim)' }}>{item.channel}</span>
        <span style={{ color: 'var(--hud-text-dim)' }}>{humanize(item.action_type)}</span>
      </div>
      <div style={{ color: 'var(--hud-text-dim)' }}>{item.scheduled_for_kst || 'unscheduled'} · {shortUrl(item.destination_url)}</div>
      {subtitle && <div style={{ color: 'var(--hud-warning)' }}>{subtitle}</div>}
    </div>
  )
}

function MissionControl({ artplex }: { artplex: any }) {
  return (
    <Panel title="ARTPLEX Mission Control" className="lg:col-span-2">
      <div className="space-y-3 text-[13px]">
        <div className="space-y-1.5 p-3" style={{ background: 'var(--hud-bg-panel)', borderLeft: '3px solid var(--hud-primary)' }}>
          <div className="font-bold" style={{ color: 'var(--hud-primary)' }}>{artplex.operator_summary}</div>
          <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.operator_focus_detail}</div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
          <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
            <div style={{ color: 'var(--hud-text-dim)' }}>repo</div>
            <div className="font-bold break-all">{artplex.repo_path}</div>
            <div style={{ color: 'var(--hud-text-dim)' }}>branch {artplex.repo_branch || '—'} · {artplex.repo_dirty_files > 0 ? `${artplex.repo_dirty_files} dirty` : 'clean'}</div>
          </div>
          <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
            <div style={{ color: 'var(--hud-text-dim)' }}>week posture</div>
            <div className="font-bold">{artplex.week || '—'}</div>
            <div>
              <span style={{ color: 'var(--hud-success)' }}>{artplex.launchable_campaigns} launchable</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> · </span>
              <span style={{ color: 'var(--hud-accent)' }}>{artplex.staged_validation_campaigns || 0} staged validation</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> · </span>
              <span style={{ color: 'var(--hud-warning)' }}>{artplex.gated_campaigns} gated</span>
            </div>
          </div>
          <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
            <div style={{ color: 'var(--hud-text-dim)' }}>storefront runtime</div>
            <div>
              <span style={{ color: statusColor(artplex.storefront_shopify_status) }}>Shopify {humanize(artplex.storefront_shopify_status)}</span>
            </div>
            <div>
              <span style={{ color: statusColor(artplex.storefront_cafe24_status) }}>Cafe24 {humanize(artplex.storefront_cafe24_status)}</span>
            </div>
          </div>
          <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
            <div style={{ color: 'var(--hud-text-dim)' }}>publish packet state</div>
            <div className="font-bold">{artplex.packet_total} packets</div>
            <div>
              <span style={{ color: 'var(--hud-success)' }}>{artplex.packet_ready_executable || 0} executable</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> · </span>
              <span style={{ color: 'var(--hud-warning)' }}>{artplex.packet_ready_blocked || 0} blocked-ready</span>
            </div>
            <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.packet_hold} hold · {artplex.packet_conditional} conditional</div>
          </div>
          <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
            <div style={{ color: 'var(--hud-text-dim)' }}>operator queue</div>
            <div className="font-bold">{artplex.task_count || 0} tasks</div>
            <div>
              <span style={{ color: 'var(--hud-warning)' }}>{artplex.today_priorities?.length || 0} today</span>
              <span style={{ color: 'var(--hud-text-dim)' }}> · </span>
              <span style={{ color: 'var(--hud-error)' }}>{artplex.open_blocker_count || 0} blockers</span>
            </div>
          </div>
          <div className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
            <div style={{ color: 'var(--hud-text-dim)' }}>measurement</div>
            <div className="font-bold" style={{ color: statusColor(artplex.measurement_mode) }}>{measurementModeLabel(artplex.measurement_mode)}</div>
            <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.measurement_live_publishes || 0} live · {artplex.measurement_dry_run_publishes || 0} dry-run</div>
            <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.measurement_publish_attempted} attempts · {artplex.measurement_publish_skipped} skipped</div>
          </div>
        </div>

        <div className="grid gap-2 lg:grid-cols-2">
          <div>
            <div className="mb-1 font-bold">artifact provenance & freshness</div>
            <div className="space-y-1">
              {(artplex.artifact_sources || []).length > 0 ? (
                (artplex.artifact_sources || []).map((source: any) => (
                  <div key={source.artifact_id} className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold">{source.label}</span>
                      <span style={{ color: source.is_freshest ? 'var(--hud-success)' : 'var(--hud-accent)' }}>{freshnessText(source)}</span>
                      <span style={{ color: provenanceColor(source.git_status) }}>{source.git_status || 'unknown'}</span>
                    </div>
                    <div style={{ color: 'var(--hud-text-dim)' }}>{source.relative_path || source.path || '—'}</div>
                    <div style={{ color: 'var(--hud-text-dim)' }}>{formatTimestamp(source.created_at || source.file_mtime_at)}</div>
                  </div>
                ))
              ) : (
                <div style={{ color: 'var(--hud-text-dim)' }}>No artifact provenance available.</div>
              )}
            </div>
          </div>
          <div>
            <div className="mb-1 font-bold">primary blockers</div>
            <div className="space-y-1">
              {(artplex.primary_blockers || []).length > 0 ? (
                (artplex.primary_blockers || []).slice(0, 6).map((item: string) => (
                  <div key={item} style={{ color: 'var(--hud-warning)' }}>• {humanize(item)}</div>
                ))
              ) : (
                <div style={{ color: 'var(--hud-success)' }}>No active blockers surfaced from the current artifacts.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function TodayPriorities({ artplex }: { artplex: any }) {
  const priorities = artplex.today_priorities || []
  return (
    <Panel title={`Today Priorities — ${priorities.length}`}>
      <div className="space-y-2 text-[13px]">
        {priorities.length > 0 ? priorities.map((task: any) => (
          <div key={task.task_id} className="p-3" style={{ background: 'var(--hud-bg-panel)', borderLeft: `3px solid ${priorityColor(task.priority)}` }}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold" style={{ color: priorityColor(task.priority) }}>{task.priority}</span>
              <span className="font-bold">{task.title}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{task.domain}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{humanize(task.due_scope)}</span>
            </div>
            {task.summary && <div style={{ color: 'var(--hud-text-dim)' }}>{task.summary}</div>}
            {task.next_step && <div><span style={{ color: 'var(--hud-warning)' }}>next</span> <span style={{ color: 'var(--hud-text-dim)' }}>{task.next_step}</span></div>}
            {task.expected_effect && <div><span style={{ color: 'var(--hud-success)' }}>effect</span> <span style={{ color: 'var(--hud-text-dim)' }}>{task.expected_effect}</span></div>}
          </div>
        )) : (
          <div style={{ color: 'var(--hud-text-dim)' }}>No generated operator priorities yet.</div>
        )}
      </div>
    </Panel>
  )
}

function BlockerBoard({ artplex }: { artplex: any }) {
  const blockers = artplex.operator_blockers || []
  return (
    <Panel title={`Blocker Board — ${blockers.length}`} className="lg:col-span-2">
      <div className="space-y-2 text-[13px]">
        {blockers.length > 0 ? blockers.map((blocker: any) => (
          <div key={blocker.blocker_id} className="p-3" style={{ background: 'var(--hud-bg-panel)', borderLeft: `3px solid ${severityColor(blocker.severity)}` }}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold" style={{ color: severityColor(blocker.severity) }}>{blocker.severity}</span>
              <span className="font-bold">{blocker.title}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{blocker.domain}</span>
            </div>
            {blocker.summary && <div style={{ color: 'var(--hud-text-dim)' }}>{blocker.summary}</div>}
            {blocker.recommended_action && <div><span style={{ color: 'var(--hud-warning)' }}>action</span> <span style={{ color: 'var(--hud-text-dim)' }}>{blocker.recommended_action}</span></div>}
            {(blocker.linked_channels || []).length > 0 && <div style={{ color: 'var(--hud-text-dim)' }}>channels: {(blocker.linked_channels || []).join(', ')}</div>}
            {(blocker.linked_campaigns || []).length > 0 && <div style={{ color: 'var(--hud-text-dim)' }}>campaigns: {(blocker.linked_campaigns || []).join(', ')}</div>}
          </div>
        )) : (
          <div style={{ color: 'var(--hud-success)' }}>No generated operator blockers right now.</div>
        )}
      </div>
    </Panel>
  )
}

function ReadinessMatrix({ artplex }: { artplex: any }) {
  return (
    <Panel title="Channel Readiness">
      <div className="space-y-2 text-[13px]">
        <div>
          <div className="font-bold mb-1">publish channels</div>
          <div className="space-y-1">
            {(artplex.channels || []).map((channel: any) => (
              <div key={channel.channel} className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span style={{ color: channel.ready ? 'var(--hud-success)' : 'var(--hud-warning)' }}>{channel.ready ? '◉' : '◆'}</span>
                  <span className="font-bold">{channel.channel}</span>
                  <span style={{ color: channel.ready ? 'var(--hud-success)' : 'var(--hud-warning)' }}>{channel.ready ? 'ready' : 'blocked'}</span>
                </div>
                {channel.reason && <div style={{ color: 'var(--hud-text-dim)' }}>{channel.reason}</div>}
                {channel.required?.length > 0 && (
                  <div style={{ color: 'var(--hud-text-dim)' }}>needs {channel.required.join(', ')}</div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="font-bold mb-1">operator capabilities</div>
          <div className="space-y-1">
            {(artplex.operator_capabilities_ready || []).map((item: string) => (
              <div key={item} style={{ color: 'var(--hud-success)' }}>+ {humanize(item)}</div>
            ))}
            {(artplex.operator_capabilities_blocked || []).map((item: string) => (
              <div key={item} style={{ color: 'var(--hud-warning)' }}>- {humanize(item)}</div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  )
}

function QueuePulse({ artplex }: { artplex: any }) {
  return (
    <Panel title="Queue Pulse">
      <div className="space-y-3 text-[13px]">
        <div className="space-y-1">
          <div className="font-bold">next executable packets</div>
          {(artplex.executable_ready_actions || []).length > 0 ? (
            (artplex.executable_ready_actions || []).slice(0, 5).map((item: any) => (
              <QueueCard key={item.asset_id} item={item} accent="var(--hud-success)" />
            ))
          ) : (
            <div style={{ color: 'var(--hud-text-dim)' }}>No ready packets are executable from the current readiness and gate state.</div>
          )}
        </div>

        <div className="space-y-1">
          <div className="font-bold">ready but blocked packets</div>
          {(artplex.blocked_ready_actions || []).length > 0 ? (
            (artplex.blocked_ready_actions || []).slice(0, 5).map((item: any) => (
              <QueueCard key={item.asset_id} item={item} accent="var(--hud-warning)" subtitle={item.execution_reason || 'blocked'} />
            ))
          ) : (
            <div style={{ color: 'var(--hud-success)' }}>No ready packets are currently blocked.</div>
          )}
        </div>

        <div className="space-y-1">
          <div className="font-bold">held / conditional gates</div>
          {[...(artplex.held_actions || []).slice(0, 3), ...(artplex.conditional_actions || []).slice(0, 2)].length > 0 ? (
            [...(artplex.held_actions || []).slice(0, 3), ...(artplex.conditional_actions || []).slice(0, 2)].map((item: any) => (
              <div key={item.asset_id} className="p-2" style={{ background: 'var(--hud-bg-panel)' }}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span style={{ color: statusColor(item.status) }}>◆</span>
                  <span className="font-bold">{item.ip_name || item.campaign_id}</span>
                  <span style={{ color: statusColor(item.status) }}>{item.status}</span>
                  <span style={{ color: 'var(--hud-text-dim)' }}>{item.channel}</span>
                </div>
                <div style={{ color: 'var(--hud-text-dim)' }}>{humanize(item.publish_gate || 'none')} · {item.scheduled_for_kst || 'unscheduled'}</div>
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--hud-success)' }}>No held or conditional packet gates in the current packet export.</div>
          )}
        </div>
      </div>
    </Panel>
  )
}

function CampaignBoard({ artplex }: { artplex: any }) {
  return (
    <Panel title="Campaign Board" className="lg:col-span-2">
      <div className="space-y-2 text-[13px]">
        {(artplex.campaigns || []).map((campaign: any) => (
          <div key={campaign.campaign_id} className="p-3" style={{ background: 'var(--hud-bg-panel)' }}>
            <div className="flex items-center gap-2 flex-wrap">
              <span style={{ color: statusColor(campaign.status) }}>◆</span>
              <span className="font-bold">{campaign.ip_name || campaign.campaign_id}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{campaign.store}</span>
              <span style={{ color: statusColor(campaign.status) }}>{campaign.status}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{campaign.readiness}</span>
            </div>
            <div className="mt-1 grid gap-2 lg:grid-cols-2">
              <div className="space-y-1">
                <div><span style={{ color: 'var(--hud-text-dim)' }}>wave</span> {campaign.current_wave || '—'}</div>
                <div><span style={{ color: 'var(--hud-text-dim)' }}>mode</span> {humanize(campaign.week1_mode)}</div>
                <div><span style={{ color: 'var(--hud-text-dim)' }}>main</span> {campaign.main_channel || '—'} <span style={{ color: 'var(--hud-text-dim)' }}>support</span> {(campaign.support_channels || []).join(', ') || '—'}</div>
                <div><span style={{ color: 'var(--hud-text-dim)' }}>destination</span> {shortUrl(campaign.display_destination)}</div>
              </div>
              <div className="space-y-1">
                {(campaign.launch_conditions || []).length > 0 && (
                  <div>
                    <span style={{ color: 'var(--hud-success)' }}>launch when</span>
                    <span style={{ color: 'var(--hud-text-dim)' }}> {(campaign.launch_conditions || []).slice(0, 3).map(humanize).join(', ')}</span>
                  </div>
                )}
                {(campaign.no_go_conditions || []).length > 0 && (
                  <div>
                    <span style={{ color: 'var(--hud-warning)' }}>no-go if</span>
                    <span style={{ color: 'var(--hud-text-dim)' }}> {(campaign.no_go_conditions || []).slice(0, 3).map(humanize).join(', ')}</span>
                  </div>
                )}
                {(campaign.metrics || []).length > 0 && (
                  <div>
                    <span style={{ color: 'var(--hud-text-dim)' }}>metrics</span>
                    <span style={{ color: 'var(--hud-text-dim)' }}> {(campaign.metrics || []).slice(0, 4).map(humanize).join(', ')}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function StorefrontRuntimeAudit({ artplex }: { artplex: any }) {
  const surfaces = artplex.storefront_surfaces || []
  if (!surfaces.length) return null

  return (
    <Panel title="Storefront Runtime Audit" className="lg:col-span-2">
      <div className="space-y-3 text-[13px]">
        <div className="space-y-1.5 p-3" style={{ background: 'var(--hud-bg-panel)', borderLeft: '3px solid var(--hud-primary)' }}>
          <div className="font-bold" style={{ color: 'var(--hud-primary)' }}>{artplex.storefront_operator_decision || 'No storefront operator decision recorded.'}</div>
          <div style={{ color: 'var(--hud-text-dim)' }}>audited {formatTimestamp(artplex.storefront_audited_at)}</div>
          <div style={{ color: 'var(--hud-text-dim)' }}>primary launch {shortUrl(artplex.storefront_primary_launch_surface)} · conversion {shortUrl(artplex.storefront_primary_conversion_surface)}</div>
          {artplex.storefront_root_cause_hypothesis && <div style={{ color: 'var(--hud-text-dim)' }}>root cause {artplex.storefront_root_cause_hypothesis}</div>}
          {artplex.storefront_local_bundle_prepared_at && <div style={{ color: 'var(--hud-text-dim)' }}>local bundle prepared {formatTimestamp(artplex.storefront_local_bundle_prepared_at)}</div>}
          {(artplex.storefront_local_verification || []).length > 0 && <div style={{ color: 'var(--hud-text-dim)' }}>local verification {(artplex.storefront_local_verification || []).map(humanize).join(', ')}</div>}
          {artplex.storefront_safe_next_action && <div style={{ color: 'var(--hud-warning)' }}>next action {artplex.storefront_safe_next_action}</div>}
        </div>

        {surfaces.map((surface: any) => (
          <div key={surface.surface_id} className="p-3" style={{ background: 'var(--hud-bg-panel)' }}>
            <div className="flex items-center gap-2 flex-wrap">
              <span style={{ color: statusColor(surface.runtime_grade) }}>◆</span>
              <span className="font-bold">{surface.ip_name || surface.surface_id}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{surface.platform}</span>
              <span style={{ color: 'var(--hud-text-dim)' }}>{humanize(surface.surface_type)}</span>
              <span style={{ color: statusColor(surface.runtime_grade) }}>{humanize(surface.runtime_grade)}</span>
              <span style={{ color: surface.launchable ? 'var(--hud-success)' : 'var(--hud-warning)' }}>{surface.launchable ? 'launchable' : 'gated'}</span>
            </div>
            <div className="mt-1 grid gap-2 lg:grid-cols-2">
              <div className="space-y-1">
                <div><span style={{ color: 'var(--hud-text-dim)' }}>url</span> {shortUrl(surface.url)}</div>
                <div><span style={{ color: 'var(--hud-text-dim)' }}>title</span> {surface.title || '—'}</div>
                <div><span style={{ color: 'var(--hud-text-dim)' }}>http</span> {surface.http_status || '—'} {surface.visible_product_count_text ? `· ${surface.visible_product_count_text}` : ''}</div>
                {surface.search_form_action && <div><span style={{ color: 'var(--hud-text-dim)' }}>search action</span> {surface.search_form_action}</div>}
                {surface.campaign_url && <div><span style={{ color: 'var(--hud-text-dim)' }}>campaign</span> {shortUrl(surface.campaign_url)}</div>}
              </div>
              <div className="space-y-1">
                <div>
                  <span style={{ color: surface.external_hard_sell_safe ? 'var(--hud-success)' : 'var(--hud-warning)' }}>hard-sell {surface.external_hard_sell_safe ? 'safe' : 'unsafe'}</span>
                  <span style={{ color: 'var(--hud-text-dim)' }}> · </span>
                  <span style={{ color: surface.support_assets_safe ? 'var(--hud-success)' : 'var(--hud-warning)' }}>support assets {surface.support_assets_safe ? 'safe' : 'unsafe'}</span>
                </div>
                {surface.console_signatures?.length > 0 && (
                  <div>
                    <span style={{ color: 'var(--hud-warning)' }}>console</span>
                    <span style={{ color: 'var(--hud-text-dim)' }}> {surface.console_signatures.slice(0, 5).map(humanize).join(', ')}</span>
                  </div>
                )}
                {surface.key_markers?.length > 0 && (
                  <div>
                    <span style={{ color: 'var(--hud-text-dim)' }}>markers</span>
                    <span style={{ color: 'var(--hud-text-dim)' }}> {surface.key_markers.slice(0, 4).join(', ')}</span>
                  </div>
                )}
              </div>
            </div>
            {surface.notes?.length > 0 && (
              <div className="mt-2 space-y-1">
                {surface.notes.map((note: string) => (
                  <div key={note} style={{ color: 'var(--hud-text-dim)' }}>• {note}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function MeasurementPulse({ artplex }: { artplex: any }) {
  return (
    <Panel title="Measurement Pulse">
      <div className="space-y-3 text-[13px]">
        <div className="space-y-1.5 p-3" style={{ background: 'var(--hud-bg-panel)', borderLeft: `3px solid ${statusColor(artplex.measurement_mode)}` }}>
          <div className="font-bold" style={{ color: statusColor(artplex.measurement_mode) }}>{measurementModeLabel(artplex.measurement_mode)}</div>
          <div style={{ color: 'var(--hud-text-dim)' }}>{formatTimestamp(artplex.measurement_generated_at)}</div>
          {artplex.measurement_mode_reason && <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.measurement_mode_reason}</div>}
          <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.measurement_publish_attempted} attempts · {artplex.measurement_publish_succeeded} succeeded · {artplex.measurement_publish_failed} failed · {artplex.measurement_publish_skipped} skipped</div>
          <div style={{ color: 'var(--hud-text-dim)' }}>{artplex.measurement_live_publishes || 0} live publishes · {artplex.measurement_dry_run_publishes || 0} dry-run publish events</div>
        </div>

        {(artplex.measurement_recent_publish_samples || []).length > 0 && (
          <div>
            <div className="font-bold mb-1">recent publish samples</div>
            <div className="space-y-1">
              {(artplex.measurement_recent_publish_samples || []).slice(0, 5).map((item: string) => (
                <div key={item} style={{ color: 'var(--hud-text-dim)' }}>• {humanize(item)}</div>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="font-bold mb-1">platforms</div>
          <div className="space-y-1">
            {(artplex.measurement_platforms || []).slice(0, 5).map((item: any) => (
              <div key={item.name} className="flex items-center justify-between gap-2">
                <span>{item.name}</span>
                <span style={{ color: 'var(--hud-text-dim)' }}>{attemptSummary(item)}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="font-bold mb-1">stores</div>
          <div className="space-y-1">
            {(artplex.measurement_stores || []).slice(0, 5).map((item: any) => (
              <div key={item.name} className="flex items-center justify-between gap-2">
                <span>{item.name}</span>
                <span style={{ color: 'var(--hud-text-dim)' }}>{attemptSummary(item)}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="font-bold mb-1">top campaigns</div>
          <div className="space-y-1">
            {(artplex.measurement_campaigns || []).slice(0, 5).map((item: any) => (
              <div key={item.name} className="flex items-center justify-between gap-2">
                <span className="truncate">{item.name}</span>
                <span style={{ color: 'var(--hud-text-dim)' }}>{attemptSummary(item)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  )
}

export default function ArtplexPanel() {
  const { data, isLoading } = useApi('/artplex', 30000)

  if (isLoading || !data) {
    return (
      <Panel title="ARTPLEX" className="col-span-full">
        <div className="glow text-[13px] animate-pulse">Reading ARTPLEX operating artifacts...</div>
      </Panel>
    )
  }

  if (!data.has_data) {
    return (
      <Panel title="ARTPLEX" className="col-span-full">
        <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
          No ARTPLEX operating artifacts were found in the active repo search paths.
        </div>
      </Panel>
    )
  }

  return (
    <>
      <MissionControl artplex={data} />
      <TodayPriorities artplex={data} />
      <BlockerBoard artplex={data} />
      <ReadinessMatrix artplex={data} />
      <QueuePulse artplex={data} />
      <CampaignBoard artplex={data} />
      <StorefrontRuntimeAudit artplex={data} />
      <MeasurementPulse artplex={data} />
    </>
  )
}
