#!/usr/bin/env python3
"""Benchmark /api/token-costs with deterministic local SQLite data."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def _seed_database(path: Path, session_count: int) -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
    models = ("claude-sonnet-4-6", "gpt-4o-mini", "unknown-model")
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                started_at REAL,
                model TEXT,
                message_count INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                actual_cost_usd REAL,
                estimated_cost_usd REAL DEFAULT 0
            );
            """
        )
        conn.executemany(
            """INSERT INTO sessions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                (
                    f"session-{i:08d}",
                    None if i % 13 == 0 else "cli",
                    None if i % 17 == 0 else f"Synthetic session {i}",
                    now - (session_count - i) * 60,
                    None if i % 29 == 0 else models[i % len(models)],
                    i % 25,
                    i % 8,
                    1_000 + (i % 10_000) * 10,
                    100 + (i % 2_000) * 3,
                    (i % 500) * 100,
                    (i % 200) * 10,
                    (i % 100) * 20,
                    None if i % 5 == 0 else (i % 1_000) * 0.0001 + (i % 7) * 0.0002,
                    0.0,
                )
                for i in range(session_count)
            ),
        )


def _request(url: str) -> tuple[float, bytes]:
    started = time.perf_counter_ns()
    with urlopen(url, timeout=60) as response:
        body = response.read()
    return (time.perf_counter_ns() - started) / 1_000_000, body


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server_env(root: Path, hermes_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_dir)
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _measure_batch(
    root: Path,
    hermes_dir: Path,
    warmup_count: int,
    request_count: int,
    concurrency: int,
) -> tuple[list[float], bytes]:
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "critical",
            "--no-access-log",
        ],
        cwd=root,
        env=_server_env(root, hermes_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}/api/token-costs"
    try:
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError(f"Uvicorn exited during startup:\n{process.stdout.read()}")
            try:
                _request(url)
                break
            except URLError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Timed out waiting for Uvicorn to serve /api/token-costs")
                time.sleep(0.1)

        for _ in range(warmup_count):
            _request(url)

        if concurrency == 1:
            measured = [_request(url) for _ in range(request_count)]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                measured = list(pool.map(lambda _: _request(url), range(request_count)))
        latencies, response_bodies = zip(*measured)
        first_body = response_bodies[0]
        if any(body != first_body for body in response_bodies[1:]):
            raise RuntimeError("Response bodies differed within a benchmark batch")
        return list(latencies), first_body
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _profile(root: Path, hermes_dir: Path) -> str:
    profile_code = """
import cProfile
import pstats
from backend.api.token_costs import get_token_costs
profile = cProfile.Profile()
profile.runcall(get_token_costs)
pstats.Stats(profile).strip_dirs().sort_stats("cumtime").print_stats(15)
"""
    result = subprocess.run(
        [sys.executable, "-c", profile_code],
        cwd=root,
        env=_server_env(root, hermes_dir),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def _summarize(samples: list[float], body: bytes) -> dict[str, object]:
    return {
        "sample_count": len(samples),
        "p95_ms": round(_nearest_rank(samples, 0.95), 3),
        "p99_ms": round(_nearest_rank(samples, 0.99), 3),
        "response_sha256": hashlib.sha256(body).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--sessions", type=int, default=10_000)
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    roots = {"baseline": args.baseline_root.resolve()}
    if args.candidate_root:
        roots["candidate"] = args.candidate_root.resolve()
    if args.sessions < 1 or args.requests < 1 or args.repeats < 1 or args.concurrency < 1:
        parser.error("sessions, requests, repeats, and concurrency must be positive")
    for root in roots.values():
        if not root.is_dir():
            parser.error(f"source root does not exist: {root}")

    with tempfile.TemporaryDirectory(prefix="hermes-hudui-token-costs-") as temp_dir:
        hermes_dir = Path(temp_dir) / "hermes"
        hermes_dir.mkdir()
        db_path = hermes_dir / "state.db"
        _seed_database(db_path, args.sessions)

        results: dict[str, list[float]] = {label: [] for label in roots}
        bodies: dict[str, bytes] = {}
        order: list[str] = []
        batch_summaries: list[dict[str, object]] = []
        labels = list(roots)
        for repeat in range(args.repeats):
            batch_order = labels if repeat % 2 == 0 else list(reversed(labels))
            for label in batch_order:
                samples, body = _measure_batch(
                    roots[label],
                    hermes_dir,
                    args.warmup,
                    args.requests,
                    args.concurrency,
                )
                results[label].extend(samples)
                if label in bodies and body != bodies[label]:
                    raise RuntimeError(
                        f"{label} response differed between benchmark batches"
                    )
                bodies[label] = body
                batch_summaries.append({
                    "repeat": repeat + 1,
                    "label": label,
                    **_summarize(samples, body),
                })
                order.append(label)

        profile_output = {
            label: _profile(root, hermes_dir) for label, root in roots.items()
        }
        summary = {
            label: _summarize(results[label], bodies[label])
            for label in roots
        }
        response_equal = (
            bodies["baseline"] == bodies["candidate"]
            if "candidate" in bodies else None
        )
        print(f"Python: {sys.version.split()[0]}")
        print(f"SQLite DB size: {db_path.stat().st_size} bytes ({args.sessions} sessions)")
        print(
            json.dumps(
                {
                    "configuration": {
                        "warmup_per_batch": args.warmup,
                        "requests_per_batch": args.requests,
                        "concurrency": args.concurrency,
                        "repeats": args.repeats,
                        "batch_order": order,
                        "percentile_method": "nearest rank",
                    },
                    "results": summary,
                    "per_batch": batch_summaries,
                    "response_equal": response_equal,
                },
                indent=2,
                sort_keys=True,
            )
        )
        for label, output in profile_output.items():
            print(f"--- cProfile: {label} ---")
            print(output, end="")
        if response_equal is False:
            print("ERROR: baseline and candidate response bodies differed", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
