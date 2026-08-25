#!/usr/bin/env python3
"""Benchmark HUD chat streaming latency vs raw hermes CLI."""

import json
import subprocess
import time
import urllib.request

BASE = "http://localhost:3001/api/chat"
PROMPT = "count from 1 to 20, one number per line"
TRIALS = 5


def get_or_create_session() -> str:
    with urllib.request.urlopen(f"{BASE}/sessions") as r:
        sessions = json.loads(r.read())
    if sessions:
        return sessions[0]["id"]
    req = urllib.request.Request(
        f"{BASE}/sessions",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["id"]


def bench_hud(session_id: str) -> dict:
    payload = json.dumps({
        "messages": [{"role": "user", "parts": [{"type": "text", "text": PROMPT}]}]
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/sessions/{session_id}/message",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    t0 = time.perf_counter()
    t_first_byte = None
    t_first_text = None
    t_done = None
    total_bytes = 0

    with urllib.request.urlopen(req, timeout=120) as resp:
        buf = b""
        while True:
            chunk = resp.read(256)
            if not chunk:
                break
            now = time.perf_counter()
            total_bytes += len(chunk)
            if t_first_byte is None:
                t_first_byte = now - t0
            buf += chunk
            while b"\n\n" in buf:
                line, buf = buf.split(b"\n\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                raw = line[5:].strip()
                if raw == b"[DONE]":
                    t_done = time.perf_counter() - t0
                    break
                try:
                    evt = json.loads(raw)
                except Exception:
                    continue
                if evt.get("type") == "text-delta" and t_first_text is None:
                    t_first_text = time.perf_counter() - t0
            if t_done:
                break

    return {
        "t_first_byte": round(t_first_byte or 0, 3),
        "t_first_text": round(t_first_text or 0, 3),
        "t_done": round(t_done or 0, 3),
        "bytes": total_bytes,
    }


def bench_cli() -> dict:
    cmd = ["hermes", "chat", "-q", PROMPT, "-Q", "--source", "tool"]
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=__import__("os").path.expanduser("~"))
    t_first_text = None
    total_bytes = 0
    for line in iter(proc.stdout.readline, b""):
        total_bytes += len(line)
        if t_first_text is None and line.strip():
            t_first_text = time.perf_counter() - t0
    proc.wait()
    t_done = time.perf_counter() - t0
    return {
        "t_first_text": round(t_first_text or 0, 3),
        "t_done": round(t_done or 0, 3),
        "bytes": total_bytes,
    }


def median(vals):
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def run(label, fn, *args):
    print(f"\n{'='*50}")
    print(f"  {label}  ({TRIALS} trials)")
    print(f"{'='*50}")
    results = []
    for i in range(TRIALS):
        print(f"  trial {i+1}...", end=" ", flush=True)
        r = fn(*args)
        results.append(r)
        print(r)
        time.sleep(2)

    for key in ["t_first_text", "t_done"]:
        vals = [r[key] for r in results if r.get(key)]
        if vals:
            print(f"  median {key}: {median(vals):.3f}s")
    return results


if __name__ == "__main__":
    sid = get_or_create_session()
    print(f"Session: {sid}")
    print(f"Prompt: {PROMPT!r}")

    cli_results = run("hermes CLI (raw)", bench_cli)
    hud_results = run("HUD chat (:3001)", bench_hud, sid)

    cli_med = median([r["t_first_text"] for r in cli_results])
    hud_med = median([r["t_first_text"] for r in hud_results])
    overhead = hud_med - cli_med
    print(f"\n--- SUMMARY ---")
    print(f"  CLI t_first_text  median: {cli_med:.3f}s")
    print(f"  HUD t_first_text  median: {hud_med:.3f}s")
    print(f"  HUD overhead:           +{overhead:.3f}s")
