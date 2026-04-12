"""Collect live agent processes, cron agents, and recent session activity."""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .utils import parse_timestamp, default_hermes_dir, safe_get


@dataclass
class AgentProcess:
    name: str           # hermes, claude, codex, opencode, llama-server
    binary: str         # actual binary name for pgrep
    running: bool = False
    pid: Optional[int] = None
    uptime: Optional[str] = None      # human-readable
    uptime_seconds: int = 0
    cwd: Optional[str] = None         # working directory
    cmdline: Optional[str] = None     # truncated command line
    cpu_pct: Optional[float] = None
    mem_mb: Optional[float] = None
    # tmux mapping fields
    tty: Optional[str] = None
    tmux_pane: Optional[str] = None
    tmux_jump_hint: Optional[str] = None


@dataclass
class RecentSession:
    session_id: str
    source: str         # cli, telegram, cron
    title: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    message_count: int = 0
    tool_call_count: int = 0
    model: Optional[str] = None
    duration_minutes: Optional[float] = None

    @property
    def in_flight(self) -> bool:
        return self.ended_at is None


@dataclass
class TmuxPane:
    pane_id: str            # e.g. "%0"
    session_name: str
    window_index: int
    pane_index: int
    tty: str                # e.g. "/dev/pts/3"
    current_command: str
    pane_pid: int
    # Derived after matching
    agent_pid: Optional[int] = None
    jump_hint: Optional[str] = None
    preview_lines: list[str] = field(default_factory=list)


@dataclass
class OperatorAlert:
    pane_id: str
    agent_name: str
    alert_type: str         # approval | question | error | stuck
    summary: str
    jump_hint: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentsState:
    processes: list[AgentProcess] = field(default_factory=list)
    recent_sessions: list[RecentSession] = field(default_factory=list)
    tmux_panes: list[TmuxPane] = field(default_factory=list)
    operator_alerts: list[OperatorAlert] = field(default_factory=list)

    @property
    def live_count(self) -> int:
        return sum(1 for p in self.processes if p.running)

    @property
    def total_processes(self) -> int:
        return len(self.processes)

    @property
    def has_tmux(self) -> bool:
        return len(self.tmux_panes) > 0

    @property
    def matched_pane_count(self) -> int:
        return sum(1 for p in self.tmux_panes if p.agent_pid is not None)

    @property
    def unmatched_interesting_panes(self) -> list[TmuxPane]:
        return [p for p in self.tmux_panes if p.agent_pid is None and p.current_command not in _SHELL_COMMANDS]

    def live(self) -> list[AgentProcess]:
        return [p for p in self.processes if p.running]

    def idle(self) -> list[AgentProcess]:
        return [p for p in self.processes if not p.running]


# Agent processes to scan for — add new entries as the ecosystem grows
AGENT_PROCESSES = [
    ("hermes", "hermes"),
    ("claude", "claude"),
    ("codex", "codex"),
    ("opencode", "opencode"),
    ("llama-server", "llama-server"),
    ("aider", "aider"),
    ("cursor", "cursor"),
    ("windsurf", "windsurf"),
]

# Shells — excluded from "interesting" unmatched pane display
_SHELL_COMMANDS = {"bash", "zsh", "sh", "fish", "dash", "tcsh", "csh"}

# Wait-state detection patterns
_ALERT_PATTERNS = [
    ("approval", re.compile(r"(?i)(allow|permit|approve|deny|yes.*no|proceed\?|continue\?)")),
    ("question", re.compile(r"(?i)(enter|input|type|answer|respond).*:")),
    ("error",    re.compile(r"(?i)(error|exception|traceback|failed|fatal)")),
]


def _shorten_home_path(path: str) -> str:
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home) else path


def _get_process_info_linux(name: str, binary: str) -> list[AgentProcess]:
    """Find all processes matching the binary name using /proc (Linux)."""
    agents = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", binary],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            agents.append(AgentProcess(name=name, binary=binary, running=False))
            return agents

        pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]

        for pid in pids:
            agent = AgentProcess(name=name, binary=binary, running=True, pid=pid)

            # Get uptime from /proc
            try:
                stat_path = Path(f"/proc/{pid}/stat")
                if stat_path.exists():
                    stat_data = stat_path.read_text().split()
                    start_ticks = int(stat_data[21])
                    uptime_data = Path("/proc/uptime").read_text().split()
                    system_uptime = float(uptime_data[0])
                    clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                    process_start_seconds = start_ticks / clk_tck
                    age_seconds = system_uptime - process_start_seconds
                    agent.uptime_seconds = int(age_seconds)
                    agent.uptime = _format_uptime(int(age_seconds))
            except (OSError, ValueError, IndexError, KeyError):
                pass

            # Get working directory
            try:
                cwd_link = Path(f"/proc/{pid}/cwd")
                if cwd_link.exists():
                    agent.cwd = _shorten_home_path(str(cwd_link.resolve()))
            except (OSError, PermissionError):
                pass

            # Get command line (truncated)
            try:
                cmdline_path = Path(f"/proc/{pid}/cmdline")
                if cmdline_path.exists():
                    cmdline = cmdline_path.read_bytes().decode("utf-8", errors="replace")
                    cmdline = cmdline.replace("\x00", " ").strip()
                    if len(cmdline) > 80:
                        cmdline = cmdline[:77] + "..."
                    agent.cmdline = cmdline
            except (OSError, PermissionError):
                pass

            # Get memory from /proc/status
            try:
                status_path = Path(f"/proc/{pid}/status")
                if status_path.exists():
                    for line in status_path.read_text().split("\n"):
                        if line.startswith("VmRSS:"):
                            kb = int(line.split()[1])
                            agent.mem_mb = round(kb / 1024, 1)
                            break
            except (OSError, ValueError, PermissionError):
                pass

            agents.append(agent)

        return agents

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        agents.append(AgentProcess(name=name, binary=binary, running=False))
        return agents


def _parse_etime(etime: str) -> int:
    """Parse macOS/BSD ps etime format ([[DD-]HH:]MM:SS) into seconds."""
    try:
        days = 0
        hours = 0
        if "-" in etime:
            day_part, etime = etime.split("-", 1)
            days = int(day_part)
        parts = etime.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), int(parts[1])
        else:
            return 0
        return days * 86400 + hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        return 0


def _get_process_info_macos(name: str, binary: str) -> list[AgentProcess]:
    """Find all processes matching the binary name using ps (macOS)."""
    agents = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", binary],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            agents.append(AgentProcess(name=name, binary=binary, running=False))
            return agents

        pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]

        for pid in pids:
            agent = AgentProcess(name=name, binary=binary, running=True, pid=pid)

            # Get rss, etime, tty, command via ps
            try:
                ps_result = subprocess.run(
                    ["ps", "-o", "rss=,etime=,tty=,command=", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5,
                )
                if ps_result.returncode == 0 and ps_result.stdout.strip():
                    parts = ps_result.stdout.strip().split(None, 3)
                    if len(parts) >= 1:
                        try:
                            agent.mem_mb = round(int(parts[0]) / 1024, 1)
                        except ValueError:
                            pass
                    if len(parts) >= 2:
                        age_seconds = _parse_etime(parts[1])
                        agent.uptime_seconds = age_seconds
                        agent.uptime = _format_uptime(age_seconds)
                    if len(parts) >= 3 and parts[2] != "??":
                        agent.tty = parts[2]
                    if len(parts) >= 4:
                        cmd = parts[3].strip()
                        if len(cmd) > 80:
                            cmd = cmd[:77] + "..."
                        agent.cmdline = cmd
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Try to get cwd via lsof (best-effort)
            try:
                lsof_result = subprocess.run(
                    ["lsof", "-p", str(pid), "-Fn"],
                    capture_output=True, text=True, timeout=3,
                )
                if lsof_result.returncode == 0:
                    for line in lsof_result.stdout.split("\n"):
                        if line.startswith("ncwd"):
                            agent.cwd = _shorten_home_path(line[4:].strip())
                            break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            agents.append(agent)

        return agents

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        agents.append(AgentProcess(name=name, binary=binary, running=False))
        return agents


def _get_process_info(name: str, binary: str) -> list[AgentProcess]:
    """Find all processes matching the binary name. Dispatches by platform."""
    if sys.platform == "darwin":
        return _get_process_info_macos(name, binary)
    return _get_process_info_linux(name, binary)


def _format_uptime(seconds: int) -> str:
    """Format seconds into human-readable uptime."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h{m}m" if m else f"{h}h"
    else:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}d{h}h" if h else f"{d}d"


def _get_tty_for_pid(pid: int) -> Optional[str]:
    """Return the TTY name (e.g. 'pts/3') for a process, or None. Cross-platform."""
    ttys = _get_ttys_for_pids([pid])
    return ttys.get(pid)


def _get_ttys_for_pids(pids: list[int]) -> dict[int, str]:
    """Return a {pid: tty} map for multiple PIDs in one ps call."""
    if not pids:
        return {}
    try:
        result = subprocess.run(
            ["ps", "-o", "pid=,tty=", "-p", ",".join(str(p) for p in pids)],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return {}
        mapping: dict[int, str] = {}
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "?":
                try:
                    mapping[int(parts[0])] = parts[1]
                except ValueError:
                    pass
        return mapping
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return {}


def _list_tmux_panes() -> list[TmuxPane]:
    """Discover all tmux panes across all sessions. Returns [] if tmux unavailable."""
    fmt = "#{pane_id}\t#{pane_tty}\t#{session_name}\t#{window_index}\t#{pane_index}\t#{pane_current_command}\t#{pane_pid}"
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", fmt],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        panes = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            pane_id, tty, session, win_idx, pane_idx, cmd, pane_pid = parts
            try:
                panes.append(TmuxPane(
                    pane_id=pane_id,
                    session_name=session,
                    window_index=int(win_idx),
                    pane_index=int(pane_idx),
                    tty=tty,
                    current_command=cmd,
                    pane_pid=int(pane_pid),
                ))
            except (ValueError, IndexError):
                continue
        return panes
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _match_processes_to_panes(
    processes: list[AgentProcess],
    panes: list[TmuxPane],
) -> None:
    """Match running AgentProcesses to TmuxPanes via TTY. Mutates both lists."""
    # pane_tty is e.g. "/dev/pts/3"; ps returns "pts/3" — normalize to the shorter form
    tty_to_pane: dict[str, TmuxPane] = {}
    for pane in panes:
        normalized = pane.tty[5:] if pane.tty.startswith("/dev/") else pane.tty
        tty_to_pane[normalized] = pane

    running_pids = [a.pid for a in processes if a.running and a.pid is not None]
    pid_to_tty = _get_ttys_for_pids(running_pids)

    for agent in processes:
        if not agent.running or agent.pid is None:
            continue
        tty = pid_to_tty.get(agent.pid)
        if not tty:
            continue
        agent.tty = tty
        pane = tty_to_pane.get(tty)
        if pane:
            jump = f"{pane.session_name}:{pane.window_index}.{pane.pane_index}"
            agent.tmux_pane = pane.pane_id
            agent.tmux_jump_hint = jump
            pane.agent_pid = agent.pid
            pane.jump_hint = jump


def _capture_pane_preview(pane_id: str, lines: int = 5) -> list[str]:
    """Capture the last N lines of a tmux pane. Returns [] on failure."""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return [ln for ln in result.stdout.split("\n") if ln.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return []


def _find_alert_in_lines(lines: list[str]) -> Optional[tuple[str, str]]:
    """Return (alert_type, summary) for the first matched line, or None."""
    for line in lines:
        for alert_type, pattern in _ALERT_PATTERNS:
            if pattern.search(line):
                summary = line.strip()
                if len(summary) > 60:
                    summary = summary[:57] + "..."
                return alert_type, summary
    return None


def _detect_operator_alerts(
    panes: list[TmuxPane],
    processes: list[AgentProcess],
) -> list[OperatorAlert]:
    """Scan matched pane previews for wait-states. One alert per pane max."""
    pid_to_agent: dict[int, AgentProcess] = {
        a.pid: a for a in processes if a.pid is not None
    }
    alerts: list[OperatorAlert] = []

    for pane in panes:
        if pane.agent_pid is None:
            continue
        agent = pid_to_agent.get(pane.agent_pid)
        if agent is None:
            continue

        found = _find_alert_in_lines(pane.preview_lines)
        if found:
            alert_type, summary = found
            alerts.append(OperatorAlert(
                pane_id=pane.pane_id,
                agent_name=agent.name,
                alert_type=alert_type,
                summary=summary,
                jump_hint=pane.jump_hint,
            ))
        elif not pane.preview_lines and agent.uptime_seconds > 300:
            alerts.append(OperatorAlert(
                pane_id=pane.pane_id,
                agent_name=agent.name,
                alert_type="stuck",
                summary="no recent output",
                jump_hint=pane.jump_hint,
            ))

    return alerts


def _get_recent_sessions(hermes_dir: str, limit: int = 10) -> list[RecentSession]:
    """Get recent sessions from state.db."""
    db_path = Path(hermes_dir) / "state.db"
    if not db_path.exists():
        return []

    sessions = []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                s.id,
                s.source,
                s.title,
                s.started_at,
                s.ended_at,
                s.model,
                COUNT(m.id) as msg_count,
                SUM(CASE WHEN m.tool_calls IS NOT NULL AND m.tool_calls != '[]' THEN 1 ELSE 0 END) as tool_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT ?
        """, (limit,))

        for row in cursor.fetchall():
            try:
                started = parse_timestamp(safe_get(row, "started_at"))
                duration = None
                if started:
                    ended = parse_timestamp(safe_get(row, "ended_at"))
                    if ended:
                        duration = round((ended - started).total_seconds() / 60, 1)

                sessions.append(RecentSession(
                    session_id=safe_get(row, "id", ""),
                    source=safe_get(row, "source", "unknown"),
                    title=safe_get(row, "title"),
                    started_at=started,
                    ended_at=ended,
                    message_count=safe_get(row, "msg_count", 0),
                    tool_call_count=safe_get(row, "tool_count", 0),
                    model=safe_get(row, "model"),
                    duration_minutes=duration,
                ))
            except Exception:
                continue

        conn.close()
    except Exception:
        pass

    return sessions


def collect_agents(hermes_dir: str | None = None) -> AgentsState:
    """Collect all agent data."""
    if hermes_dir is None:
        hermes_dir = default_hermes_dir(hermes_dir)

    # Scan for agent processes
    processes = []
    seen_pids = set()

    for name, binary in AGENT_PROCESSES:
        found = _get_process_info(name, binary)
        for agent in found:
            if agent.pid and agent.pid in seen_pids:
                continue
            if agent.pid:
                seen_pids.add(agent.pid)

                if agent.pid == os.getpid():
                    continue
                if agent.pid == os.getppid():
                    continue

            processes.append(agent)

    # tmux discovery
    panes = _list_tmux_panes()
    if panes:
        _match_processes_to_panes(processes, panes)
        matched = [p for p in panes if p.agent_pid is not None]
        if matched:
            with ThreadPoolExecutor(max_workers=min(len(matched), 4)) as pool:
                previews = pool.map(_capture_pane_preview, (p.pane_id for p in matched))
            for pane, preview in zip(matched, previews):
                pane.preview_lines = preview

    alerts = _detect_operator_alerts(panes, processes) if panes else []

    # Get recent sessions
    recent_sessions = _get_recent_sessions(hermes_dir)

    return AgentsState(
        processes=processes,
        recent_sessions=recent_sessions,
        tmux_panes=panes,
        operator_alerts=alerts,
    )
