from __future__ import annotations

import json
import subprocess
from pathlib import Path

from backend.collectors.artplex_ops import collect_artplex_ops


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init'], cwd=path, check=True, capture_output=True)
    (path / 'README.md').write_text('# demo\n', encoding='utf-8')


def test_collect_artplex_ops_reads_repo_and_operator_artifacts(tmp_path: Path):
    repo = tmp_path / 'artplex-uiux-1'
    _init_git_repo(repo)

    ops_dir = repo / 'apps' / 'marketing-agent' / 'ops'
    ops_dir.mkdir(parents=True, exist_ok=True)
    generated_dir = repo / 'apps' / 'marketing-agent' / 'docs' / 'generated'
    generated_dir.mkdir(parents=True, exist_ok=True)
    packet_dir = generated_dir / 'publish-packets' / '2026w15'
    packet_dir.mkdir(parents=True, exist_ok=True)

    (ops_dir / 'week1-campaign-slate-2026w15.yaml').write_text(
        '\n'.join([
            'version: 1',
            'week: 2026w15',
            'created_at: 2026-04-11T18:00:00+09:00',
            'campaigns:',
            '  - campaign_id: c24-rev-arknights-sched-2026w15-main',
            '    ip_name: 명일방주',
            '    store: c24',
            '    goal: rev',
            '    readiness: amber',
            '    status: staged_validation',
            '    current_wave: 2026 만우절 시리즈',
            '    main_channel: x',
            '    support_channels: [discord, blog_naver]',
            '    week1_mode: prepare_verify_then_execute',
            '    no_go_conditions: [alpine_plugin_warning_present, loading_state_undefined]',
            '  - campaign_id: shp-rev-genshin-sched-2026w15-main',
            '    ip_name: 원신',
            '    store: shp',
            '    goal: rev',
            '    readiness: green',
            '    status: launchable',
            '    current_wave: New Moon Blessing / Columbina',
            '    main_channel: x',
            '    support_channels: [onsite]',
            '    week1_mode: execute_full_loop',
            '    launch_conditions: [campaign_page_live, collection_page_live]',
            '    primary_discovery_surface: https://www.artplex.store/pages/campaign-genshin',
        ]),
        encoding='utf-8'
    )

    (ops_dir / 'live-publish-readiness-2026w15.yaml').write_text(
        '\n'.join([
            'version: 1',
            'week: 2026w15',
            'created_at: 2026-04-11T19:45:00+09:00',
            'channels:',
            '  x:',
            '    required: [TWITTER_CONSUMER_KEY, TWITTER_ACCESS_TOKEN]',
            '    ready: false',
            '    reason: missing credentials',
            '  discord:',
            '    required: [DISCORD_WEBHOOK_MAIN]',
            '    ready: false',
            '    reason: missing webhook',
            '  naver_blog:',
            '    required: [NAVER_CLIENT_ID]',
            '    ready: true',
            '    reason: token available',
            'operator_capabilities:',
            '  ready: [copy_generation, measurement_reporting]',
            '  blocked: [live_x_publish, live_discord_publish]',
        ]),
        encoding='utf-8'
    )

    (ops_dir / 'storefront-runtime-audit-2026w15.yaml').write_text(
        '\n'.join([
            'version: 1',
            'week: 2026w15',
            'audited_at: 2026-04-12T00:50:42+09:00',
            'summary:',
            '  cafe24_runtime_status: amber',
            '  shopify_runtime_status: launchable',
            '  primary_launch_surface: https://www.artplex.store/pages/campaign-genshin',
            '  primary_conversion_surface: https://www.artplex.store/collections/genshin-impact',
            '  cafe24_support_only: [c24_arknights_list, c24_bluearchive_list]',
            '  repeated_cafe24_console_signatures: [searchSeries_undefined, filteredSeriesList_undefined, worker_fallback_active]',
            '  root_cause_hypothesis: live Cafe24 HTML/JS bundle is out of sync with the newer local skin16 source',
            '  local_bundle_prepared_at: 2026-04-12T01:02:33+09:00',
            '  local_verification: [npm_run_minify_passed, local_smoke_test_passed]',
            '  safe_next_action: upload layout/basic/layout.html plus product/list.html and s16-filter-state.js/.min.js together',
            '  operator_decision: keep Cafe24 campaign pushes in support-only mode; use Shopify Genshin as the first storefront-safe launch destination once live channel credentials exist.',
            'surfaces:',
            '  - surface_id: c24_arknights_list',
            '    platform: cafe24',
            '    ip_name: 명일방주',
            '    surface_type: list_discovery',
            '    url: https://artplex.co.kr/product/list.html?ip_name=arknights',
            '    http_status: 200',
            '    title: 명일방주 - 아트플렉스 | 게임/애니메이션 굿즈 전문몰',
            '    search_form_action: /product/list.html',
            '    visible_product_count_text: 2,075개 상품을 찾았습니다',
            '    campaign_link_present: true',
            '    runtime_grade: amber_red',
            '    launchable: false',
            '    external_hard_sell_safe: false',
            '    support_assets_safe: true',
            '    console_signatures: [searchSeries_undefined, filteredSeriesList_undefined]',
            '  - surface_id: shp_genshin_collection',
            '    platform: shopify',
            '    ip_name: 원신',
            '    surface_type: collection_conversion',
            '    url: https://www.artplex.store/collections/genshin-impact',
            '    http_status: 200',
            '    title: Genshin Impact – Artplex',
            '    visible_product_count_text: 1874 items',
            '    runtime_grade: green',
            '    launchable: true',
            '    external_hard_sell_safe: true',
            '    support_assets_safe: true',
            '    key_markers: [1874 items, Availability, Price]',
        ]),
        encoding='utf-8'
    )

    (ops_dir / 'week1-publish-queue-2026w15.yaml').write_text(
        '\n'.join([
            'version: 1',
            'week: 2026w15',
            'created_at: 2026-04-11T18:30:00+09:00',
            'queue:',
            '  - asset_id: x-shp-rev-genshin-sched-2026w15-main-coll-01',
            '    campaign_id: shp-rev-genshin-sched-2026w15-main',
            '    channel: x',
            '    status: ready',
            '    action_type: awareness_launch',
            '    scheduled_for_kst: 2026-04-13T21:00:00+09:00',
            '  - asset_id: x-c24-rev-arknights-sched-2026w15-main-countdown-02',
            '    campaign_id: c24-rev-arknights-sched-2026w15-main',
            '    channel: x',
            '    status: hold',
            '    action_type: conversion_launch',
            '    scheduled_for_kst: 2026-04-16T20:30:00+09:00',
            '    publish_gate: cafe24_runtime_green',
        ]),
        encoding='utf-8'
    )

    (packet_dir / 'index.json').write_text(json.dumps({
        'week': '2026w15',
        'packets': [
            {
                'asset_id': 'discord-c24-rev-bluearchive-sched-2026w15-main-char-01',
                'campaign_id': 'c24-rev-arknights-sched-2026w15-main',
                'channel': 'discord',
                'status': 'ready',
                'action_type': 'community_poll',
                'scheduled_for_kst': '2026-04-13T19:00:00+09:00',
                'publish_gate': 'none',
                'destination_url': 'https://artplex.co.kr/product/list.html?ip_name=arknights'
            },
            {
                'asset_id': 'x-shp-rev-genshin-sched-2026w15-main-coll-01',
                'campaign_id': 'shp-rev-genshin-sched-2026w15-main',
                'channel': 'x',
                'status': 'ready',
                'action_type': 'awareness_launch',
                'scheduled_for_kst': '2026-04-13T21:00:00+09:00',
                'publish_gate': 'none',
                'destination_url': 'https://www.artplex.store/pages/campaign-genshin'
            },
            {
                'asset_id': 'blog-c24-rev-arknights-sched-2026w15-main-countdown-01',
                'campaign_id': 'c24-rev-arknights-sched-2026w15-main',
                'channel': 'blog_naver',
                'status': 'ready',
                'action_type': 'searchable_support',
                'scheduled_for_kst': '2026-04-14T11:30:00+09:00',
                'publish_gate': 'none',
                'destination_url': 'https://artplex.co.kr/product/list.html?ip_name=arknights'
            },
            {
                'asset_id': 'x-c24-rev-arknights-sched-2026w15-main-countdown-02',
                'campaign_id': 'c24-rev-arknights-sched-2026w15-main',
                'channel': 'x',
                'status': 'hold',
                'action_type': 'conversion_launch',
                'scheduled_for_kst': '2026-04-16T20:30:00+09:00',
                'publish_gate': 'cafe24_runtime_green',
                'destination_url': 'https://artplex.co.kr/product/list.html?ip_name=arknights'
            },
            {
                'asset_id': 'x-shp-rev-genshin-sched-2026w15-main-coll-02',
                'campaign_id': 'shp-rev-genshin-sched-2026w15-main',
                'channel': 'x',
                'status': 'conditional',
                'action_type': 'recap_reinforce',
                'scheduled_for_kst': '2026-04-16T21:00:00+09:00',
                'publish_gate': 'positive_first_wave_signal',
                'destination_url': 'https://www.artplex.store/collections/genshin-impact'
            }
        ],
        'grouped': {
            'ready': [{}, {}, {}],
            'hold': [{}],
            'conditional': [{}]
        }
    }), encoding='utf-8')

    (generated_dir / 'measurement-operator-report-2026-04-11.json').write_text(json.dumps({
        'generatedAt': '2026-04-11T09:13:25.839Z',
        'totalEvents': 30,
        'publish': {
            'attempted': 15,
            'succeeded': 0,
            'failed': 0,
            'skipped': 15,
            'totalEvents': 15,
        },
        'platforms': {
            'x': {'totalEvents': 16, 'attempted': 8, 'succeeded': 0, 'failed': 0, 'skipped': 8},
            'blog_naver': {'totalEvents': 10, 'attempted': 5, 'succeeded': 0, 'failed': 0, 'skipped': 5}
        },
        'stores': {
            'c24': {'totalEvents': 20, 'attempted': 10, 'succeeded': 0, 'failed': 0, 'skipped': 10},
            'shp': {'totalEvents': 10, 'attempted': 5, 'succeeded': 0, 'failed': 0, 'skipped': 5}
        },
        'campaigns': [
            {'campaignId': 'c24-rev-arknights-sched-2026w15-main', 'totalEvents': 12, 'attempted': 6, 'succeeded': 0, 'failed': 0, 'skipped': 6},
            {'campaignId': 'shp-rev-genshin-sched-2026w15-main', 'totalEvents': 4, 'attempted': 2, 'succeeded': 0, 'failed': 0, 'skipped': 2}
        ],
        'recentEvents': [
            {
                'event': 'marketing_publish_attempted',
                'properties': {
                    'platform': 'x',
                    'campaign_id': 'shp-rev-genshin-sched-2026w15-main',
                    'success': False,
                    'skipped': True,
                    'dry_run': True
                }
            },
            {
                'event': 'marketing_publish_attempted',
                'properties': {
                    'platform': 'blog_naver',
                    'campaign_id': 'c24-rev-arknights-sched-2026w15-main',
                    'success': False,
                    'skipped': True,
                    'dry_run': True
                }
            }
        ]
    }), encoding='utf-8')

    state = collect_artplex_ops(str(repo))

    assert state.repo_exists is True
    assert state.repo_path.endswith('artplex-uiux-1')
    assert state.week == '2026w15'
    assert state.slate_created_at == '2026-04-11T18:00:00+09:00'
    assert state.readiness_created_at == '2026-04-11T19:45:00+09:00'
    assert state.queue_created_at == '2026-04-11T18:30:00+09:00'
    assert state.measurement_generated_at == '2026-04-11T09:13:25.839Z'
    assert state.storefront_audited_at == '2026-04-12T00:50:42+09:00'
    assert state.storefront_cafe24_status == 'amber'
    assert state.storefront_shopify_status == 'launchable'
    assert state.storefront_primary_launch_surface == 'https://www.artplex.store/pages/campaign-genshin'
    assert state.storefront_primary_conversion_surface == 'https://www.artplex.store/collections/genshin-impact'
    assert state.storefront_support_only_surfaces == ['c24_arknights_list', 'c24_bluearchive_list']
    assert state.storefront_console_signatures == ['searchSeries_undefined', 'filteredSeriesList_undefined', 'worker_fallback_active']
    assert state.storefront_root_cause_hypothesis == 'live Cafe24 HTML/JS bundle is out of sync with the newer local skin16 source'
    assert state.storefront_local_bundle_prepared_at == '2026-04-12T01:02:33+09:00'
    assert state.storefront_local_verification == ['npm_run_minify_passed', 'local_smoke_test_passed']
    assert state.storefront_safe_next_action == 'upload layout/basic/layout.html plus product/list.html and s16-filter-state.js/.min.js together'
    assert len(state.storefront_surfaces) == 2
    assert state.storefront_surfaces[0].search_form_action == '/product/list.html'
    assert state.storefront_surfaces[1].visible_product_count_text == '1874 items'

    assert state.total_campaigns == 2
    assert state.launchable_campaigns == 1
    assert state.staged_validation_campaigns == 1
    assert state.gated_campaigns == 0
    assert state.operator_summary.startswith('keep Cafe24 campaign pushes in support-only mode')
    assert state.campaigns[0].current_wave == '2026 만우절 시리즈'
    assert state.campaigns[1].display_destination == 'https://www.artplex.store/pages/campaign-genshin'

    assert [channel.channel for channel in state.channels] == ['x', 'discord', 'naver_blog']
    assert state.channels[0].required == ['TWITTER_CONSUMER_KEY', 'TWITTER_ACCESS_TOKEN']
    assert state.live_channels_blocked == ['x', 'discord']
    assert state.live_channels_ready == ['naver_blog']
    assert state.operator_capabilities_ready == ['copy_generation', 'measurement_reporting']
    assert state.operator_capabilities_blocked == ['live_x_publish', 'live_discord_publish']

    assert state.packet_total == 5
    assert state.packet_ready == 3
    assert state.packet_hold == 1
    assert state.packet_conditional == 1
    assert state.packet_ready_executable == 1
    assert state.packet_ready_blocked == 2
    assert state.next_ready_action is not None
    assert state.next_ready_action.asset_id == 'discord-c24-rev-bluearchive-sched-2026w15-main-char-01'
    assert state.next_executable_action is not None
    assert state.next_executable_action.asset_id == 'blog-c24-rev-arknights-sched-2026w15-main-countdown-01'
    assert state.next_executable_action.channel_canonical == 'naver_blog'
    assert state.blocked_ready_actions[0].asset_id == 'discord-c24-rev-bluearchive-sched-2026w15-main-char-01'
    assert state.blocked_ready_actions[0].execution_reason == 'discord: missing webhook'
    assert state.blocked_ready_actions[1].execution_reason == 'x: missing credentials'
    assert state.held_actions[0].publish_gate == 'cafe24_runtime_green'
    assert state.conditional_actions[0].publish_gate == 'positive_first_wave_signal'
    assert 'Next executable packet' in state.operator_focus_detail

    assert 'x: missing credentials' in state.primary_blockers
    assert 'discord: missing webhook' in state.primary_blockers
    assert 'cafe24_runtime_green' in state.primary_blockers
    assert 'Shopify Genshin' in state.operator_summary
    assert 'support-only' in state.operator_summary

    assert state.measurement_total_events == 30
    assert state.measurement_publish_attempted == 15
    assert state.measurement_publish_succeeded == 0
    assert state.measurement_publish_failed == 0
    assert state.measurement_publish_skipped == 15
    assert state.measurement_mode == 'dry_run'
    assert state.measurement_live_publishes == 0
    assert state.measurement_dry_run_publishes == 15
    assert state.measurement_recent_publish_samples[0].startswith('x · dry-run skip')
    assert state.measurement_platforms[0].name == 'x'
    assert state.measurement_stores[0].name == 'c24'
    assert state.measurement_campaigns[0].name == 'c24-rev-arknights-sched-2026w15-main'

    assert [source.label for source in state.artifact_sources] == [
        'campaign slate',
        'live publish readiness',
        'storefront runtime audit',
        'week1 publish queue',
        'packet index',
        'measurement report',
    ]
    assert all(source.git_status == 'untracked' for source in state.artifact_sources)
    freshest = [source for source in state.artifact_sources if source.is_freshest]
    assert len(freshest) == 1
    assert freshest[0].label == 'packet index'

    assert state.open_blocker_count >= 3
    assert state.task_count >= 4
    assert state.today_priorities[0].priority == 'P0'
    assert state.today_priorities[0].title.startswith('Acquire live publish credentials')
    assert {'x', 'discord'} <= set(state.today_priorities[0].linked_channels)
    assert any(task.task_id == 'execute-next-safe-packet' for task in state.operator_tasks)
    assert any(task.task_id == 'reduce-cafe24-runtime-risk' for task in state.operator_tasks)
    assert any(task.task_id == 'promote-measurement-to-live-validation' for task in state.operator_tasks)
    assert any(blocker.blocker_id == 'live-channel-credentials' and blocker.severity == 'critical' for blocker in state.operator_blockers)
    assert any(blocker.blocker_id == 'measurement-dry-run-only' for blocker in state.operator_blockers)
