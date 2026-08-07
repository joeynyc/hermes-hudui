"""Run the first isolated ATLAS Beacon governance pilot.

No real Hermes files are touched. The target tree is a temporary directory and
only the requested report path is persisted.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.governance import EvidenceTruth, VerifiedFileActionAdapter
from backend.governance.progress import PlanProgressStore


def run_pilot() -> dict:
    with tempfile.TemporaryDirectory(prefix="atlas-beacon-pilot-") as temp:
        root = Path(temp)
        adapter = VerifiedFileActionAdapter(allowed_roots=[root])

        shadow_target = root / "shadow" / "MEMORY.md"
        shadow = adapter.shadow_one(
            shadow_target, b"shadow payload\n", action="pilot.shadow"
        )
        shadow_unchanged = not shadow_target.exists()
        shadow_truths = [item.truth.value for item in shadow.evidence]

        config = root / "profiles" / "pilot" / "config.yaml"
        soul = root / "profiles" / "pilot" / "SOUL.md"
        progress = PlanProgressStore(root)
        with progress.write_activity(
            plan_id="atlas-beacon",
            stage="phase-8-pilot",
            action="profile.update",
            next_gate="rollback_fault_injection",
        ):
            enforced = adapter.write_many(
                {config: b"model: pilot\n", soul: b"pilot soul\n"},
                action="pilot.profile.update",
            )

        first = root / "rollback" / "first"
        second = root / "rollback" / "second"
        adapter.write_many({first: b"before-first", second: b"before-second"})
        calls = 0

        def fail_second_replace(source, target) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("pilot_injected_replace_failure")
            Path(source).replace(target)

        fault_adapter = VerifiedFileActionAdapter(
            allowed_roots=[root], replace_fn=fail_second_replace
        )
        injected_failure_observed = False
        try:
            fault_adapter.write_many(
                {first: b"after-first", second: b"after-second"},
                action="pilot.rollback",
            )
        except OSError as exc:
            injected_failure_observed = "pilot_injected_replace_failure" in str(exc)

        rollback_restored = (
            first.read_bytes() == b"before-first"
            and second.read_bytes() == b"before-second"
        )
        final_progress = progress.read()
        progress_readable = (
            final_progress.state == "present"
            and final_progress.progress is not None
            and final_progress.progress.write_active is False
            and final_progress.progress.next_gate == "rollback_fault_injection"
            and final_progress.stale is False
        )
        no_temp_files = not any(
            ".atlas-stage-" in path.name or ".atlas-backup-" in path.name
            for path in root.rglob("*")
        )

        gates = {
            "shadow_did_not_mutate": shadow_unchanged,
            "shadow_postcondition_is_unknown": shadow_truths
            == [EvidenceTruth.TRUE.value, EvidenceTruth.UNKNOWN.value],
            "enforced_receipt_verified": enforced.verified,
            "enforced_files_match": config.read_bytes() == b"model: pilot\n"
            and soul.read_bytes() == b"pilot soul\n",
            "heartbeat_readable_and_inactive": progress_readable,
            "fault_was_injected": injected_failure_observed,
            "rollback_restored_both_files": rollback_restored,
            "no_stage_or_backup_leaks": no_temp_files,
        }
        return {
            "schema_version": 1,
            "pilot": "atlas-beacon-isolated-file-governance",
            "status": "PASS" if all(gates.values()) else "FAIL",
            "gates": gates,
            "shadow_evidence": [asdict(item) for item in shadow.evidence],
            "enforced_evidence": [asdict(item) for item in enforced.evidence],
            "progress_sequence": (
                final_progress.progress.sequence
                if final_progress.progress is not None
                else None
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = run_pilot()
    payload = (
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    writer = VerifiedFileActionAdapter(
        allowed_roots=[args.out.parent.resolve(strict=False)]
    )
    receipt = writer.write_one(args.out, payload, action="pilot.report.write")
    readback = json.loads(args.out.read_text(encoding="utf-8"))
    ok = receipt.verified and readback == report and report["status"] == "PASS"
    print(
        json.dumps(
            {"status": "PASS" if ok else "FAIL", "report": str(args.out)},
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
