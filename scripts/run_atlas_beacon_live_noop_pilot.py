"""Run an explicitly authorized no-content-change write pilot on MEMORY.md."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import memory as memory_api
from backend.collectors.utils import default_hermes_dir
from backend.governance import FilePresence, VerifiedFileActionAdapter, observe_file


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(output_path: Path) -> dict[str, object]:
    hermes_dir = Path(default_hermes_dir()).resolve()
    target = hermes_dir / "memories" / "MEMORY.md"
    adapter = VerifiedFileActionAdapter(allowed_roots=[hermes_dir])

    def do_pilot():
        initial = observe_file(target)
        if initial.presence is not FilePresence.PRESENT:
            raise RuntimeError(f"MEMORY.md is not safely present: {initial.reason}")

        payload = target.read_bytes()
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        if payload_sha256 != initial.sha256 or len(payload) != initial.size:
            raise RuntimeError("MEMORY.md changed between observation and locked read")

        initial_mode = target.stat().st_mode
        receipt = adapter.write_one(
            target,
            payload,
            action="atlas.live-pilot.memory-noop",
        )
        final = observe_file(target)
        final_mode = target.stat().st_mode
        return initial, receipt, final, initial_mode, final_mode

    initial, receipt, final, initial_mode, final_mode = memory_api._with_lock(
        "memory", do_pilot
    )
    temp_artifacts = sorted(
        path.name for path in target.parent.glob(f".{target.name}.atlas-*-*")
    )
    content_unchanged = (
        receipt.verified
        and final.presence is FilePresence.PRESENT
        and final.sha256 == initial.sha256
        and final.size == initial.size
    )
    mode_unchanged = final_mode == initial_mode
    passed = content_unchanged and mode_unchanged and not temp_artifacts

    report: dict[str, object] = {
        "schema_version": 1,
        "pilot": "atlas-beacon-live-memory-noop",
        "generated_at": _timestamp(),
        "status": "PASS" if passed else "FAIL",
        "target": "memories/MEMORY.md",
        "action": receipt.action,
        "receipt_status": receipt.status,
        "receipt_verified": receipt.verified,
        "pre_state": initial.presence.value,
        "post_state": final.presence.value,
        "pre_sha256": initial.sha256,
        "post_sha256": final.sha256,
        "pre_size": initial.size,
        "post_size": final.size,
        "content_unchanged": content_unchanged,
        "mode_unchanged": mode_unchanged,
        "mtime_updated": initial.mtime_ns != final.mtime_ns,
        "temporary_artifacts": temp_artifacts,
        "evidence": [
            {
                "predicate": item.predicate,
                "truth": item.truth.value,
                "expected": item.expected,
                "observed": item.observed,
                "reason": item.reason,
            }
            for item in receipt.evidence
        ],
    }

    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    report_adapter = VerifiedFileActionAdapter(allowed_roots=[output_path.parent])
    report_receipt = report_adapter.write_one(
        output_path,
        encoded,
        action="atlas.live-pilot.report",
    )
    if not report_receipt.verified:
        raise RuntimeError("pilot report failed verification")
    readback = json.loads(output_path.read_text(encoding="utf-8"))
    if readback != report:
        raise RuntimeError("pilot report readback mismatch")
    if not passed:
        raise RuntimeError("live no-op pilot failed verification")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.out.resolve())
    print(
        json.dumps(
            {
                "status": report["status"],
                "target": report["target"],
                "content_unchanged": report["content_unchanged"],
                "receipt_verified": report["receipt_verified"],
                "report": str(args.out.resolve()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
