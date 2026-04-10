"""Collect prompt pattern analytics from Hermes state.db."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from ..cache import get_cached_or_compute
from .models import (
    HourlyActivity,
    PatternsState,
    RepeatedPrompt,
    TaskCluster,
    ToolWorkflow,
)
from .utils import default_hermes_dir, parse_timestamp, safe_get

# First match wins
_CLUSTERS = [
    (
        "git ops",
        [
            "commit",
            "push",
            "pull",
            "merge",
            "branch",
            "rebase",
            " pr ",
            "pull request",
            "release",
            "tag",
            "stash",
        ],
    ),
    (
        "debugging",
        [
            "fix",
            "bug",
            "error",
            "broken",
            "failing",
            "crash",
            "traceback",
            "exception",
            "not work",
            "doesn't work",
        ],
    ),
    (
        "code gen",
        [
            "create",
            "implement",
            "add feature",
            "build",
            "write a",
            "new function",
            "new class",
            "generate",
        ],
    ),
    (
        "refactor",
        [
            "refactor",
            "rename",
            "clean up",
            "simplify",
            "extract",
            "reorganize",
            "restructure",
            "move",
        ],
    ),
    (
        "research",
        [
            "explain",
            "how does",
            "what is",
            "what are",
            "find",
            "search",
            "look at",
            "investigate",
            "understand",
        ],
    ),
    (
        "config/ops",
        [
            "install",
            "configure",
            "setup",
            "deploy",
            "env",
            "systemd",
            "cron",
            "docker",
            "service",
        ],
    ),
    ("docs", ["readme", "documentation", "comment", "docstring", "document"]),
]


def _classify(text: str) -> str:
    lower = text.lower()
    for label, keywords in _CLUSTERS:
        if any(kw in lower for kw in keywords):
            return label
    return "other"


def _normalize_prompt(text: str) -> str:
    return text.strip().lower()[:80]


def _top_trigrams(sequences: list[list[str]], n: int = 10) -> list[ToolWorkflow]:
    """Find the most common 3-tool subsequences across all sessions."""
    counts: Counter = Counter()
    for seq in sequences:
        for i in range(len(seq) - 2):
            trigram = (seq[i], seq[i + 1], seq[i + 2])
            counts[trigram] += 1
    return [
        ToolWorkflow(tool_sequence=list(trigram), count=count)
        for trigram, count in counts.most_common(n)
    ]


def _do_collect_patterns(db_path: str) -> PatternsState:
    """Actually collect pattern analytics (internal, uncached)."""
    cluster_buckets: dict[str, dict] = {
        label: {"count": 0, "msg_sum": 0, "tool_sum": 0, "titles": []}
        for label, _ in _CLUSTERS
    }
    cluster_buckets["other"] = {"count": 0, "msg_sum": 0, "tool_sum": 0, "titles": []}

    prompt_counts: Counter = Counter()
    prompt_last_seen: dict[str, datetime] = {}
    total_user_messages = 0
    session_tools: dict[str, list[str]] = defaultdict(list)

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Task clustering + repeated prompts via window function JOIN
        cur.execute("""
            SELECT s.id, s.title, s.message_count, s.tool_call_count, s.started_at,
                   fm.content AS first_msg
            FROM sessions s
            LEFT JOIN (
                SELECT session_id, content,
                       ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp ASC) AS rn
                FROM messages WHERE role = 'user'
            ) fm ON fm.session_id = s.id AND fm.rn = 1
            ORDER BY s.started_at DESC
        """)

        for row in cur:
            try:
                first_msg = safe_get(row, "first_msg") or ""
                title = safe_get(row, "title") or ""
                msg_count = safe_get(row, "message_count", 0)
                tool_count = safe_get(row, "tool_call_count", 0)
                started = parse_timestamp(safe_get(row, "started_at")) or datetime.now()

                combined = f"{first_msg} {title}"
                label = _classify(combined)
                bucket = cluster_buckets[label]
                bucket["count"] += 1
                bucket["msg_sum"] += msg_count
                bucket["tool_sum"] += tool_count
                if first_msg and len(bucket["titles"]) < 3:
                    bucket["titles"].append(title or first_msg[:50])

                if first_msg:
                    norm = _normalize_prompt(first_msg)
                    prompt_counts[norm] += 1
                    if norm not in prompt_last_seen or started > prompt_last_seen[norm]:
                        prompt_last_seen[norm] = started
            except Exception:
                continue

        # Total user messages
        cur.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'")
        row = cur.fetchone()
        if row:
            total_user_messages = safe_get(row, 0, 0)

        # Hourly activity
        cur.execute("""
            SELECT CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) as hour,
                   COUNT(*) as sessions,
                   COALESCE(SUM(message_count), 0) as messages
            FROM sessions
            GROUP BY hour
            ORDER BY hour
        """)
        hour_map: dict[int, HourlyActivity] = {}
        for row in cur:
            try:
                h = safe_get(row, "hour", 0)
                hour_map[h] = HourlyActivity(
                    hour=h,
                    sessions=safe_get(row, "sessions", 0),
                    messages=safe_get(row, "messages", 0),
                )
            except Exception:
                continue

        # Tool sequences (single connection, cursor iteration)
        cur.execute("""
            SELECT session_id, tool_calls
            FROM messages
            WHERE tool_calls IS NOT NULL AND tool_calls != ''
            ORDER BY session_id, timestamp ASC
        """)
        for row in cur:
            try:
                sid = safe_get(row, "session_id", "")
                tc_json = safe_get(row, "tool_calls", "")
                calls = json.loads(tc_json)
                if isinstance(calls, list):
                    for call in calls:
                        name = call.get("function", {}).get("name", "")
                        if name:
                            session_tools[sid].append(name)
            except Exception:
                continue

        conn.close()
    except Exception:
        return PatternsState()

    clusters = []
    for label, bucket in cluster_buckets.items():
        if bucket["count"] == 0:
            continue
        clusters.append(
            TaskCluster(
                label=label,
                count=bucket["count"],
                avg_messages=bucket["msg_sum"] / bucket["count"],
                avg_tool_calls=bucket["tool_sum"] / bucket["count"],
                example_titles=bucket["titles"],
            )
        )
    clusters.sort(key=lambda c: -c.count)

    repeated = []
    for norm, count in prompt_counts.most_common(15):
        if count < 2:
            break
        repeated.append(
            RepeatedPrompt(
                pattern=norm,
                count=count,
                last_seen=prompt_last_seen.get(norm, datetime.now()),
                could_be_skill=count >= 3,
            )
        )

    hourly = [
        hour_map.get(h, HourlyActivity(hour=h, sessions=0, messages=0))
        for h in range(24)
    ]
    workflows = _top_trigrams(list(session_tools.values()))

    return PatternsState(
        clusters=clusters,
        repeated_prompts=repeated,
        hourly_activity=hourly,
        tool_workflows=workflows,
        total_user_messages=total_user_messages,
    )


def collect_patterns(hermes_dir: str | None = None) -> PatternsState:
    """Collect prompt pattern analytics from state.db (cached)."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir()

    db_path = Path(hermes_dir) / "state.db"
    if not db_path.exists():
        return PatternsState()

    return get_cached_or_compute(
        cache_key=f"patterns:{hermes_dir}",
        compute_fn=lambda: _do_collect_patterns(str(db_path)),
        file_paths=[db_path],
        ttl=60,  # 60 second cache
    )
