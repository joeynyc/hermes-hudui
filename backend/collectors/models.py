"""Data models for Hermes HUD."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ── Memory ──────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    text: str
    category: str  # environment, correction, preference, project, todo, other
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class MemoryState:
    entries: list[MemoryEntry] = field(default_factory=list)
    total_chars: int = 0
    max_chars: int = 0
    source: str = ""  # "memory" or "user"

    @property
    def capacity_pct(self) -> float:
        return (self.total_chars / self.max_chars * 100) if self.max_chars > 0 else 0

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    def count_by_category(self) -> dict[str, int]:
        return dict(Counter(e.category for e in self.entries))


# ── Skills ──────────────────────────────────────────────────

@dataclass
class SkillInfo:
    name: str
    category: str
    description: str
    path: str
    modified_at: datetime
    file_size: int = 0
    is_custom: bool = False  # heuristic: modified recently and not in a bulk timestamp


@dataclass
class SkillsState:
    skills: list[SkillInfo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.skills)

    @property
    def custom_count(self) -> int:
        return sum(1 for s in self.skills if s.is_custom)

    def by_category(self) -> dict[str, list[SkillInfo]]:
        cats: dict[str, list[SkillInfo]] = {}
        for s in self.skills:
            cats.setdefault(s.category, []).append(s)
        return cats

    def category_counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.by_category().items()}

    def recently_modified(self, n: int = 5) -> list[SkillInfo]:
        return sorted(self.skills, key=lambda s: s.modified_at, reverse=True)[:n]


# ── Sessions ────────────────────────────────────────────────

@dataclass
class SessionInfo:
    id: str
    source: str  # cli, telegram
    title: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    message_count: int
    tool_call_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def full_token_footprint(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens + self.reasoning_tokens

    @property
    def in_flight(self) -> bool:
        return self.ended_at is None

    @property
    def duration_minutes(self) -> Optional[float]:
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds() / 60
        return None


@dataclass
class DailyStats:
    date: str
    sessions: int
    messages: int
    tool_calls: int
    tokens: int = 0


@dataclass
class SessionsState:
    sessions: list[SessionInfo] = field(default_factory=list)
    daily_stats: list[DailyStats] = field(default_factory=list)
    tool_usage: dict[str, int] = field(default_factory=dict)  # tool_name -> count

    @property
    def total_sessions(self) -> int:
        return len(self.sessions)

    @property
    def total_messages(self) -> int:
        return sum(s.message_count for s in self.sessions)

    @property
    def total_tool_calls(self) -> int:
        return sum(s.tool_call_count for s in self.sessions)

    @property
    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.sessions)

    @property
    def total_full_tokens(self) -> int:
        return sum(s.full_token_footprint for s in self.sessions)

    @property
    def active_sessions_count(self) -> int:
        return sum(1 for s in self.sessions if s.in_flight)

    @property
    def date_range(self) -> tuple[Optional[datetime], Optional[datetime]]:
        if not self.sessions:
            return None, None
        return (
            min(s.started_at for s in self.sessions),
            max(s.started_at for s in self.sessions),
        )

    @property
    def by_source(self) -> dict[str, int]:
        return dict(Counter(s.source for s in self.sessions))


# ── Prompt Patterns ─────────────────────────────────────────

@dataclass
class TaskCluster:
    label: str
    count: int
    avg_messages: float
    avg_tool_calls: float
    example_titles: list[str] = field(default_factory=list)


@dataclass
class RepeatedPrompt:
    pattern: str
    count: int
    last_seen: datetime
    could_be_skill: bool


@dataclass
class HourlyActivity:
    hour: int
    sessions: int
    messages: int


@dataclass
class ToolWorkflow:
    tool_sequence: list[str]
    count: int


@dataclass
class PatternsState:
    clusters: list[TaskCluster] = field(default_factory=list)
    repeated_prompts: list[RepeatedPrompt] = field(default_factory=list)
    hourly_activity: list[HourlyActivity] = field(default_factory=list)
    tool_workflows: list[ToolWorkflow] = field(default_factory=list)
    total_user_messages: int = 0

    @property
    def total_sessions(self) -> int:
        return sum(c.count for c in self.clusters)

    @property
    def peak_hour(self) -> Optional[int]:
        if not self.hourly_activity:
            return None
        return max(self.hourly_activity, key=lambda h: h.sessions).hour

    @property
    def skill_candidates(self) -> list[RepeatedPrompt]:
        return [r for r in self.repeated_prompts if r.could_be_skill]


# ── Config ──────────────────────────────────────────────────

@dataclass
class ConfigState:
    model: str = ""
    provider: str = ""
    toolsets: list[str] = field(default_factory=list)
    backend: str = ""
    max_turns: int = 0
    compression_enabled: bool = False
    checkpoints_enabled: bool = False
    memory_char_limit: int = 2200
    user_char_limit: int = 1375


# ── Timeline Events ────────────────────────────────────────

@dataclass
class TimelineEvent:
    timestamp: datetime
    event_type: str  # session, memory_change, skill_modified, config_change, milestone
    title: str
    detail: str = ""
    icon: str = "◆"


# ── Snapshot (for diff tracking) ───────────────────────────

@dataclass
class HUDSnapshot:
    timestamp: datetime
    memory_entry_count: int
    memory_chars: int
    user_entry_count: int
    user_chars: int
    skill_count: int
    custom_skill_count: int
    session_count: int
    total_messages: int
    total_tool_calls: int
    total_tokens: int
    categories: list[str] = field(default_factory=list)


# ── Profiles ───────────────────────────────────────────────

@dataclass
class ProfileInfo:
    name: str
    is_default: bool = False
    # Config
    model: str = ""
    provider: str = ""
    base_url: str = ""
    port: Optional[int] = None
    toolsets: list[str] = field(default_factory=list)
    skin: str = ""
    context_length: int = 0
    # Personality
    soul_summary: str = ""  # first meaningful line of SOUL.md
    # Usage stats (from state.db)
    session_count: int = 0
    message_count: int = 0
    tool_call_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    last_active: Optional[datetime] = None
    active_session_count: int = 0
    activity_status: str = "idle"   # active, idle
    activity_reason: str = ""
    # Memory
    memory_entries: int = 0
    memory_chars: int = 0
    memory_max_chars: int = 2200
    user_entries: int = 0
    user_chars: int = 0
    user_max_chars: int = 1375
    # Skills & cron
    skill_count: int = 0
    cron_job_count: int = 0
    # API keys configured (names only)
    api_keys: list[str] = field(default_factory=list)
    # Status
    gateway_status: str = "unknown"    # active, inactive, unknown, n/a
    server_status: str = "unknown"     # running, stopped, unknown, n/a
    has_alias: bool = False
    # Compression
    compression_enabled: bool = False
    compression_model: str = ""

    @property
    def memory_capacity_pct(self) -> float:
        return (self.memory_chars / self.memory_max_chars * 100) if self.memory_max_chars > 0 else 0

    @property
    def user_capacity_pct(self) -> float:
        return (self.user_chars / self.user_max_chars * 100) if self.user_max_chars > 0 else 0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def is_local(self) -> bool:
        return self.provider == "custom" or "localhost" in self.base_url


@dataclass
class ProfilesState:
    profiles: list[ProfileInfo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.profiles)

    @property
    def active_count(self) -> int:
        return sum(1 for p in self.profiles if p.activity_status == "active")

    def local_profiles(self) -> list[ProfileInfo]:
        return [p for p in self.profiles if p.is_local]

    def api_profiles(self) -> list[ProfileInfo]:
        return [p for p in self.profiles if not p.is_local]


# ── Full HUD State ─────────────────────────────────────────

@dataclass
class HUDState:
    memory: MemoryState = field(default_factory=MemoryState)
    user: MemoryState = field(default_factory=MemoryState)
    skills: SkillsState = field(default_factory=SkillsState)
    sessions: SessionsState = field(default_factory=SessionsState)
    config: ConfigState = field(default_factory=ConfigState)
    timeline: list[TimelineEvent] = field(default_factory=list)
    collected_at: datetime = field(default_factory=datetime.now)
