"""Collect ARTPLEX operator data from the active artplex-uiux repo."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


CHANNEL_ALIASES = {
    'x': 'x',
    'twitter': 'x',
    'discord': 'discord',
    'blog_naver': 'naver_blog',
    'naver_blog': 'naver_blog',
    'naverblog': 'naver_blog',
    'onsite': 'onsite',
    'organic': 'onsite',
}

UNGATED_EXECUTION_CHANNELS = {'onsite'}


@dataclass
class ArtplexCampaign:
    campaign_id: str
    ip_name: str = ""
    store: str = ""
    goal: str = ""
    readiness: str = ""
    status: str = ""
    week1_mode: str = ""
    current_wave: str = ""
    main_channel: str = ""
    support_channels: list[str] = field(default_factory=list)
    primary_destination: str = ""
    primary_discovery_surface: str = ""
    primary_conversion_surface: str = ""
    fallback_destination: str = ""
    character_hooks: list[str] = field(default_factory=list)
    launch_conditions: list[str] = field(default_factory=list)
    no_go_conditions: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)

    @property
    def display_destination(self) -> str:
        return (
            self.primary_destination
            or self.primary_discovery_surface
            or self.primary_conversion_surface
            or self.fallback_destination
        )


@dataclass
class ArtplexChannelStatus:
    channel: str
    ready: bool = False
    reason: str = ""
    required: list[str] = field(default_factory=list)

    @property
    def canonical_channel(self) -> str:
        return _normalize_channel_name(self.channel)


@dataclass
class ArtplexQueueItem:
    asset_id: str
    campaign_id: str = ""
    ip_name: str = ""
    store: str = ""
    goal: str = ""
    channel: str = ""
    status: str = ""
    action_type: str = ""
    scheduled_for_kst: str = ""
    destination_url: str = ""
    tagged_url: str = ""
    publish_gate: str = ""
    metric_focus: list[str] = field(default_factory=list)
    channel_canonical: str = ""
    channel_ready: bool = False
    executable: bool = False
    execution_blocked: bool = False
    execution_reason: str = ""


@dataclass
class ArtplexMeasurementSlice:
    name: str
    total_events: int = 0
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass
class ArtplexStorefrontSurface:
    surface_id: str
    platform: str = ""
    ip_name: str = ""
    surface_type: str = ""
    url: str = ""
    http_status: int = 0
    title: str = ""
    search_form_action: str = ""
    visible_product_count_text: str = ""
    campaign_link_present: bool = False
    campaign_url: str = ""
    runtime_grade: str = ""
    launchable: bool = False
    external_hard_sell_safe: bool = False
    support_assets_safe: bool = False
    console_signatures: list[str] = field(default_factory=list)
    key_markers: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ArtplexArtifactSource:
    artifact_id: str
    label: str
    path: str = ""
    relative_path: str = ""
    exists: bool = False
    created_at: str = ""
    file_mtime_at: str = ""
    git_status: str = ""
    git_porcelain: str = ""
    is_freshest: bool = False
    freshness_delta_minutes: int = 0


@dataclass
class ArtplexOperatorBlocker:
    blocker_id: str
    title: str
    severity: str = "medium"
    domain: str = ""
    summary: str = ""
    recommended_action: str = ""
    linked_channels: list[str] = field(default_factory=list)
    linked_campaigns: list[str] = field(default_factory=list)
    linked_surfaces: list[str] = field(default_factory=list)


@dataclass
class ArtplexOperatorTask:
    task_id: str
    title: str
    priority: str = "P2"
    due_scope: str = "today"  # now, today, this_week
    domain: str = ""
    summary: str = ""
    next_step: str = ""
    success_criterion: str = ""
    expected_effect: str = ""
    linked_channels: list[str] = field(default_factory=list)
    linked_campaigns: list[str] = field(default_factory=list)
    linked_surfaces: list[str] = field(default_factory=list)
    source_kind: str = "generated"


@dataclass
class ArtplexOpsState:
    repo_path: str = ""
    repo_exists: bool = False
    repo_branch: str = ""
    repo_dirty_files: int = 0
    week: str = ""
    slate_created_at: str = ""
    readiness_created_at: str = ""
    queue_created_at: str = ""
    measurement_generated_at: str = ""
    campaigns: list[ArtplexCampaign] = field(default_factory=list)
    channels: list[ArtplexChannelStatus] = field(default_factory=list)
    live_channels_ready: list[str] = field(default_factory=list)
    live_channels_blocked: list[str] = field(default_factory=list)
    operator_capabilities_ready: list[str] = field(default_factory=list)
    operator_capabilities_blocked: list[str] = field(default_factory=list)
    packet_total: int = 0
    packet_ready: int = 0
    packet_hold: int = 0
    packet_conditional: int = 0
    packet_ready_executable: int = 0
    packet_ready_blocked: int = 0
    next_ready_actions: list[ArtplexQueueItem] = field(default_factory=list)
    executable_ready_actions: list[ArtplexQueueItem] = field(default_factory=list)
    blocked_ready_actions: list[ArtplexQueueItem] = field(default_factory=list)
    held_actions: list[ArtplexQueueItem] = field(default_factory=list)
    conditional_actions: list[ArtplexQueueItem] = field(default_factory=list)
    measurement_total_events: int = 0
    measurement_publish_attempted: int = 0
    measurement_publish_succeeded: int = 0
    measurement_publish_failed: int = 0
    measurement_publish_skipped: int = 0
    measurement_live_publishes: int = 0
    measurement_dry_run_publishes: int = 0
    measurement_mode: str = ""
    measurement_mode_reason: str = ""
    measurement_recent_publish_samples: list[str] = field(default_factory=list)
    measurement_platforms: list[ArtplexMeasurementSlice] = field(default_factory=list)
    measurement_stores: list[ArtplexMeasurementSlice] = field(default_factory=list)
    measurement_campaigns: list[ArtplexMeasurementSlice] = field(default_factory=list)
    storefront_audited_at: str = ""
    storefront_cafe24_status: str = ""
    storefront_shopify_status: str = ""
    storefront_primary_launch_surface: str = ""
    storefront_primary_conversion_surface: str = ""
    storefront_support_only_surfaces: list[str] = field(default_factory=list)
    storefront_console_signatures: list[str] = field(default_factory=list)
    storefront_root_cause_hypothesis: str = ""
    storefront_safe_next_action: str = ""
    storefront_local_bundle_prepared_at: str = ""
    storefront_local_verification: list[str] = field(default_factory=list)
    storefront_operator_decision: str = ""
    storefront_surfaces: list[ArtplexStorefrontSurface] = field(default_factory=list)
    artifact_sources: list[ArtplexArtifactSource] = field(default_factory=list)
    operator_blockers: list[ArtplexOperatorBlocker] = field(default_factory=list)
    operator_tasks: list[ArtplexOperatorTask] = field(default_factory=list)
    today_priorities: list[ArtplexOperatorTask] = field(default_factory=list)

    @property
    def total_campaigns(self) -> int:
        return len(self.campaigns)

    @property
    def launchable_campaigns(self) -> int:
        return sum(1 for campaign in self.campaigns if campaign.status == 'launchable')

    @property
    def gated_campaigns(self) -> int:
        return sum(1 for campaign in self.campaigns if campaign.status == 'gated')

    @property
    def staged_validation_campaigns(self) -> int:
        return sum(1 for campaign in self.campaigns if campaign.status == 'staged_validation')

    @property
    def has_data(self) -> bool:
        return self.repo_exists and (
            self.total_campaigns > 0
            or self.packet_total > 0
            or self.measurement_total_events > 0
            or bool(self.channels)
            or bool(self.storefront_surfaces)
        )

    @property
    def open_blocker_count(self) -> int:
        return len(self.operator_blockers)

    @property
    def task_count(self) -> int:
        return len(self.operator_tasks)

    @property
    def next_ready_action(self) -> Optional[ArtplexQueueItem]:
        return self.next_ready_actions[0] if self.next_ready_actions else None

    @property
    def next_executable_action(self) -> Optional[ArtplexQueueItem]:
        return self.executable_ready_actions[0] if self.executable_ready_actions else None

    @property
    def next_blocked_ready_action(self) -> Optional[ArtplexQueueItem]:
        return self.blocked_ready_actions[0] if self.blocked_ready_actions else None

    @property
    def primary_blockers(self) -> list[str]:
        blockers: list[str] = []
        seen: set[str] = set()

        for channel in self.channels:
            if channel.ready:
                continue
            reason = f"{channel.channel}: {channel.reason}" if channel.reason else channel.channel
            if reason not in seen:
                blockers.append(reason)
                seen.add(reason)

        for action in self.blocked_ready_actions:
            if action.execution_reason and action.execution_reason not in seen:
                blockers.append(action.execution_reason)
                seen.add(action.execution_reason)

        for action in [*self.held_actions, *self.conditional_actions]:
            gate = action.publish_gate.strip()
            if gate and gate.lower() != 'none' and gate not in seen:
                blockers.append(gate)
                seen.add(gate)

        for campaign in self.campaigns:
            if campaign.status not in {'gated', 'staged_validation'}:
                continue
            for condition in campaign.no_go_conditions[:2]:
                if condition and condition not in seen:
                    blockers.append(condition)
                    seen.add(condition)

        for signature in self.storefront_console_signatures[:3]:
            if signature and signature not in seen:
                blockers.append(signature)
                seen.add(signature)

        return blockers[:8]

    @property
    def operator_summary(self) -> str:
        if self.storefront_operator_decision:
            return self.storefront_operator_decision

        launchable = next((campaign for campaign in self.campaigns if campaign.status == 'launchable'), None)
        staged = self.staged_validation_campaigns
        if launchable and self.live_channels_blocked:
            blocked = ', '.join(self.live_channels_blocked[:3])
            if staged:
                return (
                    f"{launchable.ip_name} is the first launchable destination, but live channels ({blocked}) "
                    f"are still blocked; keep {staged} Cafe24 campaigns in staged validation / support-safe mode."
                )
            if self.gated_campaigns:
                return (
                    f"{launchable.ip_name} is the first launchable destination, but live channels ({blocked}) "
                    f"are still blocked; keep Cafe24 support-only."
                )
            return f"{launchable.ip_name} is launchable, but live channels ({blocked}) are still blocked."
        if launchable and staged:
            store_label = 'Shopify' if launchable.store == 'shp' else launchable.store.upper()
            return (
                f"Run the first live loop on {launchable.ip_name} ({store_label}) while "
                f"{staged} Cafe24 campaigns stay in staged validation / support-safe mode."
            )
        if launchable and self.gated_campaigns:
            store_label = 'Shopify' if launchable.store == 'shp' else launchable.store.upper()
            return (
                f"Run the first live loop on {launchable.ip_name} ({store_label}) while "
                f"{self.gated_campaigns} Cafe24 campaigns stay support-only."
            )
        if launchable:
            store_label = 'Shopify' if launchable.store == 'shp' else launchable.store.upper()
            return f"Run the first live loop on {launchable.ip_name} ({store_label})."
        if self.live_channels_blocked or staged or self.gated_campaigns:
            return "Stay in dry-run / packet mode until live channel credentials and storefront blockers clear."
        return "No launchable ARTPLEX campaign detected yet."

    @property
    def operator_focus_detail(self) -> str:
        next_executable = self.next_executable_action
        if next_executable:
            scheduled = next_executable.scheduled_for_kst or 'unscheduled'
            return (
                f"Next executable packet: {next_executable.channel} · {next_executable.ip_name or next_executable.campaign_id} · "
                f"{next_executable.action_type} · {scheduled}"
            )
        next_blocked = self.next_blocked_ready_action
        if next_blocked:
            scheduled = next_blocked.scheduled_for_kst or 'unscheduled'
            reason = next_blocked.execution_reason or 'blocked'
            return (
                f"Next planned packet is blocked: {next_blocked.channel} · {next_blocked.ip_name or next_blocked.campaign_id} · "
                f"{next_blocked.action_type} · {scheduled} · {reason}"
            )
        next_action = self.next_ready_action
        if next_action:
            scheduled = next_action.scheduled_for_kst or 'unscheduled'
            return (
                f"Next staged packet: {next_action.channel} · {next_action.ip_name or next_action.campaign_id} · "
                f"{next_action.action_type} · {scheduled}"
            )
        if self.primary_blockers:
            return f"Primary blockers: {', '.join(self.primary_blockers[:3])}"
        return "No staged packet available right now."



def _candidate_repo_paths(explicit: str | None = None) -> list[Path]:
    if explicit:
        return [Path(explicit)]
    env_path = os.environ.get('HERMES_HUD_ARTPLEX_DIR')
    if env_path:
        return [Path(env_path)]
    home = Path(os.path.expanduser('~'))
    return [home / 'artplex-uiux-1', home / 'artplex-uiux']



def _safe_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except Exception:
        return {}



def _safe_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}



def _git_output(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, timeout=5)
        return result.stdout.strip()
    except Exception:
        return ''



def _latest_file(directory: Path, pattern: str) -> Optional[Path]:
    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None



def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    text = str(value).strip()
    return [text] if text else []



def _timestamp_from(data: dict[str, Any], path: Path, *keys: str) -> str:
    for key in keys:
        raw = data.get(key, '')
        if isinstance(raw, datetime):
            return raw.isoformat()
        value = str(raw or '').strip()
        if value:
            return value
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        return ''



def _parse_sort_timestamp(value: str) -> float:
    if not value:
        return float('inf')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp()
    except Exception:
        return float('inf')



def _sort_queue(items: list[ArtplexQueueItem]) -> list[ArtplexQueueItem]:
    return sorted(items, key=lambda item: (_parse_sort_timestamp(item.scheduled_for_kst), item.asset_id))



def _measurement_slice(name: str, payload: dict[str, Any]) -> ArtplexMeasurementSlice:
    return ArtplexMeasurementSlice(
        name=name,
        total_events=int(payload.get('totalEvents', 0) or 0),
        attempted=int(payload.get('attempted', 0) or 0),
        succeeded=int(payload.get('succeeded', 0) or 0),
        failed=int(payload.get('failed', 0) or 0),
        skipped=int(payload.get('skipped', 0) or 0),
    )



def _storefront_surface(payload: dict[str, Any]) -> ArtplexStorefrontSurface:
    return ArtplexStorefrontSurface(
        surface_id=str(payload.get('surface_id', '') or ''),
        platform=str(payload.get('platform', '') or ''),
        ip_name=str(payload.get('ip_name', '') or ''),
        surface_type=str(payload.get('surface_type', '') or ''),
        url=str(payload.get('url', '') or ''),
        http_status=int(payload.get('http_status', 0) or 0),
        title=str(payload.get('title', '') or ''),
        search_form_action=str(payload.get('search_form_action', '') or ''),
        visible_product_count_text=str(payload.get('visible_product_count_text', '') or ''),
        campaign_link_present=bool(payload.get('campaign_link_present')),
        campaign_url=str(payload.get('campaign_url', '') or ''),
        runtime_grade=str(payload.get('runtime_grade', '') or ''),
        launchable=bool(payload.get('launchable')),
        external_hard_sell_safe=bool(payload.get('external_hard_sell_safe')),
        support_assets_safe=bool(payload.get('support_assets_safe')),
        console_signatures=_string_list(payload.get('console_signatures')),
        key_markers=_string_list(payload.get('key_markers')),
        notes=_string_list(payload.get('notes')),
    )



def _campaign_lookup(campaigns: list[ArtplexCampaign]) -> dict[str, ArtplexCampaign]:
    return {campaign.campaign_id: campaign for campaign in campaigns if campaign.campaign_id}



def _normalize_channel_name(value: str) -> str:
    raw = str(value or '').strip().lower()
    return CHANNEL_ALIASES.get(raw, raw)



def _relative_to_repo(repo: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except Exception:
        return str(path)



def _file_mtime_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    except Exception:
        return ''



def _git_porcelain(repo: Path, path: Path) -> str:
    relative = _relative_to_repo(repo, path)
    try:
        result = subprocess.run(
            ['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=all', '--', relative],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ''



def _git_status_label(porcelain: str, exists: bool) -> str:
    if not exists:
        return 'missing'
    if not porcelain:
        return 'clean'
    prefix = porcelain.split()[0]
    if prefix == '??':
        return 'untracked'
    if prefix == '!!':
        return 'ignored'
    return 'modified'



def _artifact_source(repo: Path, artifact_id: str, label: str, path: Optional[Path], created_at: str) -> ArtplexArtifactSource:
    if not path:
        return ArtplexArtifactSource(artifact_id=artifact_id, label=label, git_status='missing')
    exists = path.exists()
    porcelain = _git_porcelain(repo, path) if (repo / '.git').is_dir() and exists else ''
    return ArtplexArtifactSource(
        artifact_id=artifact_id,
        label=label,
        path=str(path),
        relative_path=_relative_to_repo(repo, path),
        exists=exists,
        created_at=created_at,
        file_mtime_at=_file_mtime_iso(path),
        git_status=_git_status_label(porcelain, exists),
        git_porcelain=porcelain,
    )



def _finalize_artifact_sources(sources: list[ArtplexArtifactSource]) -> list[ArtplexArtifactSource]:
    timestamp_pairs: list[tuple[ArtplexArtifactSource, float]] = []
    for source in sources:
        raw = source.created_at or source.file_mtime_at
        ts = _parse_sort_timestamp(raw)
        if ts != float('inf'):
            timestamp_pairs.append((source, ts))

    if not timestamp_pairs:
        return sources

    freshest_ts = max(ts for _, ts in timestamp_pairs)
    for source, ts in timestamp_pairs:
        delta_minutes = max(0, int(round((freshest_ts - ts) / 60)))
        source.freshness_delta_minutes = delta_minutes
        source.is_freshest = delta_minutes == 0
    return sources



def _collect_packet_queue_items(
    packets: list[dict[str, Any]],
    lookup: dict[str, ArtplexCampaign],
) -> list[ArtplexQueueItem]:
    items: list[ArtplexQueueItem] = []
    for packet in packets:
        campaign_id = str(packet.get('campaign_id', '') or '')
        campaign = lookup.get(campaign_id)
        channel = str(packet.get('channel', '') or '')
        items.append(
            ArtplexQueueItem(
                asset_id=str(packet.get('asset_id', '') or ''),
                campaign_id=campaign_id,
                ip_name=(campaign.ip_name if campaign else ''),
                store=(campaign.store if campaign else str(packet.get('store', '') or '')),
                goal=(campaign.goal if campaign else str(packet.get('goal', '') or '')),
                channel=channel,
                status=str(packet.get('status', packet.get('state', '')) or ''),
                action_type=str(packet.get('action_type', '') or ''),
                scheduled_for_kst=str(packet.get('scheduled_for_kst', '') or ''),
                destination_url=str(packet.get('destination_url', '') or ''),
                tagged_url=str(packet.get('tagged_url', '') or ''),
                publish_gate=str(packet.get('publish_gate', packet.get('gate', '')) or ''),
                metric_focus=_string_list(packet.get('metric_focus')),
                channel_canonical=_normalize_channel_name(channel),
            )
        )
    return _sort_queue(items)



def _channel_lookup(channels: list[ArtplexChannelStatus]) -> dict[str, ArtplexChannelStatus]:
    lookup: dict[str, ArtplexChannelStatus] = {}
    for channel in channels:
        lookup[channel.canonical_channel] = channel
    return lookup



def _classify_ready_action(item: ArtplexQueueItem, channel_lookup: dict[str, ArtplexChannelStatus]) -> ArtplexQueueItem:
    canonical = item.channel_canonical or _normalize_channel_name(item.channel)
    reasons: list[str] = []
    channel_ready = False

    channel_state = channel_lookup.get(canonical)
    if channel_state:
        channel_ready = channel_state.ready
        if not channel_state.ready:
            channel_reason = channel_state.reason or 'blocked'
            reasons.append(f"{canonical}: {channel_reason}")
    elif canonical in UNGATED_EXECUTION_CHANNELS:
        channel_ready = True
    else:
        reasons.append(f"{canonical}: no readiness status found")

    gate = item.publish_gate.strip()
    if gate and gate.lower() != 'none':
        reasons.append(f"publish gate: {gate}")

    item.channel_canonical = canonical
    item.channel_ready = channel_ready
    item.execution_blocked = len(reasons) > 0
    item.execution_reason = ' · '.join(reasons)
    item.executable = item.status == 'ready' and not item.execution_blocked
    return item



def _measurement_mode(
    measurement: dict[str, Any],
    attempted: int,
    succeeded: int,
    failed: int,
    skipped: int,
) -> tuple[str, str, int, int, list[str]]:
    recent_events = measurement.get('recentEvents') or measurement.get('recent_events') or []
    dry_run_count = 0
    live_event_count = 0
    samples: list[str] = []

    for event in recent_events:
        event_name = str(event.get('event', '') or '')
        if 'publish' not in event_name:
            continue
        properties = event.get('properties', {}) or {}
        platform = str(properties.get('platform', '') or '')
        campaign_id = str(properties.get('campaign_id', '') or '')
        dry_run = bool(properties.get('dry_run'))
        skipped_flag = bool(properties.get('skipped'))
        success_flag = bool(properties.get('success'))

        if dry_run:
            dry_run_count += 1
            outcome = 'dry-run skip' if skipped_flag else 'dry-run'
        else:
            live_event_count += 1
            if success_flag:
                outcome = 'live success'
            elif skipped_flag:
                outcome = 'live skipped'
            else:
                outcome = 'live attempt'

        if len(samples) < 5:
            label = ' · '.join(part for part in [platform, outcome, campaign_id] if part)
            if label:
                samples.append(label)

    live_publish_count = succeeded + failed
    if attempted == 0:
        return 'idle', 'no publish attempts were recorded in the latest measurement report', live_publish_count, 0, samples

    if live_publish_count > 0 and dry_run_count > 0:
        return 'mixed', 'the latest report contains both live publish outcomes and dry-run publish attempts', live_publish_count, dry_run_count, samples

    if live_publish_count > 0:
        return 'live', 'the latest report contains live publish outcomes', live_publish_count, 0, samples

    if dry_run_count > 0 and skipped == attempted:
        return 'dry_run', 'recent publish attempts were marked dry_run and all attempted publishes were skipped', live_publish_count, attempted, samples

    if skipped == attempted:
        return 'skipped_only', 'all attempted publishes were skipped and no live publish outcomes were recorded', live_publish_count, 0, samples

    if live_event_count > 0:
        return 'live', 'recent publish events were recorded without dry_run markers', max(live_publish_count, live_event_count), 0, samples

    return 'unknown', 'publish activity was recorded but the latest report does not clearly identify live vs dry-run execution', live_publish_count, dry_run_count, samples



def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = str(value or '').strip()
        if cleaned and cleaned not in seen:
            out.append(cleaned)
            seen.add(cleaned)
    return out



def _priority_rank(priority: str) -> int:
    return {'P0': 0, 'P1': 1, 'P2': 2}.get(priority, 9)



def _due_rank(due_scope: str) -> int:
    return {'now': 0, 'today': 1, 'this_week': 2}.get(due_scope, 9)



def _build_operator_tasks_and_blockers(state: ArtplexOpsState) -> None:
    blockers: list[ArtplexOperatorBlocker] = []
    tasks: list[ArtplexOperatorTask] = []

    blocked_channels = [channel for channel in state.channels if not channel.ready]
    if blocked_channels:
        blocked_channel_names = [channel.channel for channel in blocked_channels]
        blocked_campaigns = _unique_preserve([
            item.campaign_id for item in state.blocked_ready_actions if item.campaign_id
        ])
        required_keys = _unique_preserve([
            required for channel in blocked_channels for required in channel.required
        ])
        blockers.append(ArtplexOperatorBlocker(
            blocker_id='live-channel-credentials',
            title='Live publish channels are blocked',
            severity='critical',
            domain='publish',
            summary=f"{', '.join(blocked_channel_names)} cannot publish from the current local credential state.",
            recommended_action='Restore the required environment variables and regenerate the publish readiness artifact.',
            linked_channels=blocked_channel_names,
            linked_campaigns=blocked_campaigns,
        ))
        tasks.append(ArtplexOperatorTask(
            task_id='restore-live-channel-credentials',
            title=f"Acquire live publish credentials for {', '.join(blocked_channel_names)}",
            priority='P0',
            due_scope='now',
            domain='publish',
            summary=f"{len(blocked_channel_names)} channels are blocked and {state.packet_ready_blocked} ready packets are waiting behind credential gates.",
            next_step='Set and validate the required channel environment variables, then refresh the readiness artifact.',
            success_criterion='Blocked channels move to ready and blocked-ready packet count drops.',
            expected_effect='Enables the first real live publish loop and removes the main operator bottleneck.',
            linked_channels=blocked_channel_names,
            linked_campaigns=blocked_campaigns,
        ))
        if required_keys:
            tasks[-1].summary += f" Required keys include: {', '.join(required_keys[:6])}."

    if state.storefront_cafe24_status and state.storefront_cafe24_status != 'green':
        blockers.append(ArtplexOperatorBlocker(
            blocker_id='cafe24-runtime-amber',
            title='Cafe24 storefront is not yet green',
            severity='high',
            domain='storefront',
            summary=f"Cafe24 runtime is {state.storefront_cafe24_status} while {state.staged_validation_campaigns} campaigns remain in staged validation.",
            recommended_action=state.storefront_safe_next_action or 'Investigate the remaining Cafe24 runtime warnings and rerun the storefront audit.',
            linked_surfaces=state.storefront_support_only_surfaces,
            linked_campaigns=[campaign.campaign_id for campaign in state.campaigns if campaign.store == 'c24'],
        ))
        tasks.append(ArtplexOperatorTask(
            task_id='reduce-cafe24-runtime-risk',
            title=f"Move Cafe24 from {state.storefront_cafe24_status} toward green",
            priority='P1',
            due_scope='today',
            domain='storefront',
            summary='Cafe24 is still support-safe / staged-validation rather than a clean first live lane.',
            next_step=state.storefront_safe_next_action or 'Investigate residual Cafe24 runtime warnings and rerun the audit.',
            success_criterion='A fresh storefront audit reports Cafe24 green or materially reduces the blocking warning set.',
            expected_effect='Lets Cafe24 campaigns graduate from support-safe amber into launchable store surfaces.',
            linked_surfaces=state.storefront_support_only_surfaces,
            linked_campaigns=[campaign.campaign_id for campaign in state.campaigns if campaign.store == 'c24'],
        ))

    if state.next_executable_action:
        next_action = state.next_executable_action
        tasks.append(ArtplexOperatorTask(
            task_id='execute-next-safe-packet',
            title=f"Execute next safe packet: {next_action.ip_name or next_action.campaign_id} · {next_action.channel} · {next_action.action_type}",
            priority='P1',
            due_scope='today',
            domain='publish',
            summary=f"The next executable action is scheduled for {next_action.scheduled_for_kst or 'unscheduled'} and points to {next_action.destination_url or 'the active storefront surface'}.",
            next_step='Run the packet exactly as staged and confirm measurement captures the expected downstream event.',
            success_criterion='The packet executes without introducing new blockers and the expected operator/measurement trace appears.',
            expected_effect='Advances the cleanest currently executable store-support or launch action.',
            linked_channels=[next_action.channel],
            linked_campaigns=[next_action.campaign_id] if next_action.campaign_id else [],
        ))

    if state.measurement_mode == 'dry_run':
        blockers.append(ArtplexOperatorBlocker(
            blocker_id='measurement-dry-run-only',
            title='Measurement still reflects dry-run only',
            severity='high',
            domain='measurement',
            summary='Recent publish attempts were skipped in dry-run mode, so the dashboard does not yet have live publish truth.',
            recommended_action='After the live channel blockers are cleared, run one controlled live publish and verify that measurement shifts out of dry-run mode.',
            linked_channels=state.live_channels_blocked,
            linked_campaigns=_unique_preserve([item.campaign_id for item in state.next_ready_actions if item.campaign_id]),
        ))
        tasks.append(ArtplexOperatorTask(
            task_id='promote-measurement-to-live-validation',
            title='Promote measurement from dry-run to first live validation',
            priority='P1',
            due_scope='today',
            domain='measurement',
            summary=f"{state.measurement_publish_attempted} publish attempts were recorded, but all remained dry-run / skipped.",
            next_step='Once a live channel is unblocked, run one contained live publish and verify measurement records a live publish outcome.',
            success_criterion='Measurement mode becomes live or mixed with at least one real publish outcome.',
            expected_effect='Makes performance/attribution data trustworthy enough for true operator decision-making.',
            linked_channels=state.live_channels_blocked,
        ))

    stale_sources = [source for source in state.artifact_sources if source.freshness_delta_minutes >= 240]
    if stale_sources:
        stale_labels = [source.label for source in stale_sources]
        blockers.append(ArtplexOperatorBlocker(
            blocker_id='stale-operator-artifacts',
            title='Operator artifacts are stale',
            severity='medium',
            domain='artifacts',
            summary=f"{len(stale_sources)} artifacts are more than four hours behind the freshest source.",
            recommended_action='Refresh the slate/readiness/queue/measurement artifacts before treating this dashboard as the current source of truth.',
        ))
        tasks.append(ArtplexOperatorTask(
            task_id='refresh-stale-operator-artifacts',
            title=f"Refresh stale operator artifacts: {', '.join(stale_labels[:3])}",
            priority='P1',
            due_scope='today',
            domain='artifacts',
            summary='Critical ARTPLEX artifacts are materially older than the freshest storefront audit.',
            next_step='Regenerate the stale artifacts and rerun the relevant audits so the dashboard reflects current store reality.',
            success_criterion='Critical artifacts are refreshed and freshness deltas collapse toward the newest source.',
            expected_effect='Improves operator trust and reduces decisions based on stale local exports.',
        ))

    tasks.sort(key=lambda task: (_priority_rank(task.priority), _due_rank(task.due_scope), task.title))
    blockers.sort(key=lambda blocker: ({'critical': 0, 'high': 1, 'medium': 2}.get(blocker.severity, 9), blocker.title))

    state.operator_tasks = tasks
    state.operator_blockers = blockers
    state.today_priorities = [task for task in tasks if task.due_scope in {'now', 'today'}][:5]



def collect_artplex_ops(repo_path: str | None = None) -> ArtplexOpsState:
    repo = next((path for path in _candidate_repo_paths(repo_path) if path.exists()), None)
    if repo is None:
        return ArtplexOpsState()

    state = ArtplexOpsState(repo_path=str(repo), repo_exists=True)

    if (repo / '.git').is_dir():
        state.repo_branch = _git_output(repo, 'branch', '--show-current') or 'HEAD'
        status = _git_output(repo, 'status', '--porcelain')
        state.repo_dirty_files = len([line for line in status.splitlines() if line.strip()]) if status else 0

    ops_dir = repo / 'apps' / 'marketing-agent' / 'ops'
    generated_dir = repo / 'apps' / 'marketing-agent' / 'docs' / 'generated'

    slate_file = _latest_file(ops_dir, 'week1-campaign-slate-*.yaml') if ops_dir.exists() else None
    if slate_file:
        slate = _safe_yaml(slate_file)
        state.week = str(slate.get('week', '') or '')
        state.slate_created_at = _timestamp_from(slate, slate_file, 'created_at')
        state.artifact_sources.append(_artifact_source(repo, 'campaign_slate', 'campaign slate', slate_file, state.slate_created_at))
        for item in slate.get('campaigns', []) or []:
            state.campaigns.append(
                ArtplexCampaign(
                    campaign_id=str(item.get('campaign_id', '') or ''),
                    ip_name=str(item.get('ip_name', '') or ''),
                    store=str(item.get('store', '') or ''),
                    goal=str(item.get('goal', '') or ''),
                    readiness=str(item.get('readiness', '') or ''),
                    status=str(item.get('status', '') or ''),
                    week1_mode=str(item.get('week1_mode', '') or ''),
                    current_wave=str(item.get('current_wave', '') or ''),
                    main_channel=str(item.get('main_channel', '') or ''),
                    support_channels=_string_list(item.get('support_channels')),
                    primary_destination=str(item.get('primary_destination', '') or ''),
                    primary_discovery_surface=str(item.get('primary_discovery_surface', '') or ''),
                    primary_conversion_surface=str(item.get('primary_conversion_surface', '') or ''),
                    fallback_destination=str(item.get('fallback_destination', '') or ''),
                    character_hooks=_string_list(item.get('character_hooks')),
                    launch_conditions=_string_list(item.get('launch_conditions')),
                    no_go_conditions=_string_list(item.get('no_go_conditions')),
                    metrics=_string_list(item.get('metrics')),
                )
            )

    campaign_lookup = _campaign_lookup(state.campaigns)

    readiness_file = _latest_file(ops_dir, 'live-publish-readiness-*.yaml') if ops_dir.exists() else None
    if readiness_file:
        readiness = _safe_yaml(readiness_file)
        state.readiness_created_at = _timestamp_from(readiness, readiness_file, 'created_at')
        state.artifact_sources.append(_artifact_source(repo, 'live_publish_readiness', 'live publish readiness', readiness_file, state.readiness_created_at))
        state.operator_capabilities_ready = _string_list((readiness.get('operator_capabilities', {}) or {}).get('ready'))
        state.operator_capabilities_blocked = _string_list((readiness.get('operator_capabilities', {}) or {}).get('blocked'))
        for channel, details in (readiness.get('channels', {}) or {}).items():
            payload = details or {}
            channel_state = ArtplexChannelStatus(
                channel=str(channel),
                ready=bool(payload.get('ready')),
                reason=str(payload.get('reason', '') or ''),
                required=_string_list(payload.get('required')),
            )
            state.channels.append(channel_state)
            if channel_state.ready:
                state.live_channels_ready.append(channel_state.channel)
            else:
                state.live_channels_blocked.append(channel_state.channel)

    storefront_file = _latest_file(ops_dir, 'storefront-runtime-audit-*.yaml') if ops_dir.exists() else None
    if storefront_file:
        storefront = _safe_yaml(storefront_file)
        summary = storefront.get('summary', {}) or {}
        state.storefront_audited_at = _timestamp_from(storefront, storefront_file, 'audited_at')
        state.artifact_sources.append(_artifact_source(repo, 'storefront_runtime_audit', 'storefront runtime audit', storefront_file, state.storefront_audited_at))
        state.storefront_cafe24_status = str(summary.get('cafe24_runtime_status', '') or '')
        state.storefront_shopify_status = str(summary.get('shopify_runtime_status', '') or '')
        state.storefront_primary_launch_surface = str(summary.get('primary_launch_surface', '') or '')
        state.storefront_primary_conversion_surface = str(summary.get('primary_conversion_surface', '') or '')
        state.storefront_support_only_surfaces = _string_list(summary.get('cafe24_support_only'))
        state.storefront_console_signatures = _string_list(summary.get('repeated_cafe24_console_signatures'))
        state.storefront_root_cause_hypothesis = str(summary.get('root_cause_hypothesis', '') or '')
        state.storefront_safe_next_action = str(summary.get('safe_next_action', '') or '')
        state.storefront_local_bundle_prepared_at = _timestamp_from(summary, storefront_file, 'local_bundle_prepared_at')
        state.storefront_local_verification = _string_list(summary.get('local_verification'))
        state.storefront_operator_decision = str(summary.get('operator_decision', '') or '')
        state.storefront_surfaces = [_storefront_surface(item or {}) for item in (storefront.get('surfaces', []) or [])]
        if not state.week:
            state.week = str(storefront.get('week', '') or '')

    queue_file = _latest_file(ops_dir, 'week1-publish-queue-*.yaml') if ops_dir.exists() else None
    if queue_file:
        queue = _safe_yaml(queue_file)
        state.queue_created_at = _timestamp_from(queue, queue_file, 'created_at')
        state.artifact_sources.append(_artifact_source(repo, 'week1_publish_queue', 'week1 publish queue', queue_file, state.queue_created_at))
        if not state.week:
            state.week = str(queue.get('week', '') or '')

    packet_dir = generated_dir / 'publish-packets' / state.week if state.week else None
    packet_file = _latest_file(packet_dir, 'index.json') if packet_dir and packet_dir.exists() else None
    if packet_file:
        packet_data = _safe_json(packet_file)
        packet_created_at = _timestamp_from(packet_data, packet_file, 'generatedAt', 'createdAt', 'created_at')
        state.artifact_sources.append(_artifact_source(repo, 'packet_index', 'packet index', packet_file, packet_created_at))
        packets = packet_data.get('packets', []) or []
        grouped = packet_data.get('grouped', {}) or {}
        state.packet_total = len(packets)
        state.packet_ready = len(grouped.get('ready', []) or [])
        state.packet_hold = len(grouped.get('hold', []) or [])
        state.packet_conditional = len(grouped.get('conditional', []) or [])

        channel_lookup = _channel_lookup(state.channels)
        queue_items = [_classify_ready_action(item, channel_lookup) for item in _collect_packet_queue_items(packets, campaign_lookup)]
        state.next_ready_actions = [item for item in queue_items if item.status == 'ready'][:5]
        state.executable_ready_actions = [item for item in queue_items if item.status == 'ready' and item.executable][:5]
        state.blocked_ready_actions = [item for item in queue_items if item.status == 'ready' and item.execution_blocked][:5]
        state.held_actions = [item for item in queue_items if item.status == 'hold'][:5]
        state.conditional_actions = [item for item in queue_items if item.status == 'conditional'][:5]
        state.packet_ready_executable = len([item for item in queue_items if item.status == 'ready' and item.executable])
        state.packet_ready_blocked = len([item for item in queue_items if item.status == 'ready' and item.execution_blocked])

    measurement_file = _latest_file(generated_dir, 'measurement-operator-report-*.json') if generated_dir.exists() else None
    if measurement_file:
        measurement = _safe_json(measurement_file)
        state.measurement_generated_at = _timestamp_from(measurement, measurement_file, 'generatedAt')
        state.artifact_sources.append(_artifact_source(repo, 'measurement_report', 'measurement report', measurement_file, state.measurement_generated_at))
        state.measurement_total_events = int(measurement.get('totalEvents', 0) or 0)
        publish = measurement.get('publish', {}) or {}
        state.measurement_publish_attempted = int(publish.get('attempted', 0) or 0)
        state.measurement_publish_succeeded = int(publish.get('succeeded', 0) or 0)
        state.measurement_publish_failed = int(publish.get('failed', 0) or 0)
        state.measurement_publish_skipped = int(publish.get('skipped', 0) or 0)
        (
            state.measurement_mode,
            state.measurement_mode_reason,
            state.measurement_live_publishes,
            state.measurement_dry_run_publishes,
            state.measurement_recent_publish_samples,
        ) = _measurement_mode(
            measurement,
            state.measurement_publish_attempted,
            state.measurement_publish_succeeded,
            state.measurement_publish_failed,
            state.measurement_publish_skipped,
        )
        state.measurement_platforms = sorted(
            [_measurement_slice(name, payload or {}) for name, payload in (measurement.get('platforms', {}) or {}).items()],
            key=lambda item: (-item.attempted, item.name),
        )
        state.measurement_stores = sorted(
            [_measurement_slice(name, payload or {}) for name, payload in (measurement.get('stores', {}) or {}).items()],
            key=lambda item: (-item.attempted, item.name),
        )
        campaign_payloads = measurement.get('campaigns', []) or []
        state.measurement_campaigns = sorted(
            [_measurement_slice(str(item.get('campaignId', '') or ''), item or {}) for item in campaign_payloads],
            key=lambda item: (-item.attempted, item.name),
        )

    state.artifact_sources = _finalize_artifact_sources(state.artifact_sources)
    _build_operator_tasks_and_blockers(state)
    return state
