"""Run an authorized no-content-change transaction pilot on default profile files."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import profiles as profiles_api
from backend.collectors.utils import default_hermes_dir
from backend.governance import FilePresence, VerifiedFileActionAdapter, observe_file


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(output_path: Path) -> dict[str, object]:
    hermes_dir = Path(default_hermes_dir()).resolve()
    profile_dir = profiles_api._profile_dir("default").resolve()
    targets = [profile_dir / "config.yaml", profile_dir / "SOUL.md"]
    adapter = VerifiedFileActionAdapter(allowed_roots=[hermes_dir])

    def do_pilot():
        initial = {target: observe_file(target) for target in targets}
        for target, observation in initial.items():
            if observation.presence is not FilePresence.PRESENT:
                raise RuntimeError(
                    f"{target.name} is not safely present: {observation.reason}"
                )

        payloads = {target: target.read_bytes() for target in targets}
        modes = {target: target.stat().st_mode for target in targets}
        for target, payload in payloads.items():
            observation = initial[target]
            if (
                hashlib.sha256(payload).hexdigest() != observation.sha256
                or len(payload) != observation.size
            ):
                raise RuntimeError(f"{target.name} changed during locked read")

        receipt = adapter.write_many(
            payloads,
            action="atlas.live-pilot.default-profile-noop",
        )
        final = {target: observe_file(target) for target in targets}
        final_modes = {target: target.stat().st_mode for target in targets}
        return initial, receipt, final, modes, final_modes

    initial, receipt, final, modes, final_modes = profiles_api._with_profile_lock(
        profile_dir, do_pilot
    )

    records = []
    for target in targets:
        before = initial[target]
        after = final[target]
        artifacts = sorted(
            path.name for path in target.parent.glob(f".{target.name}.atlas-*-*")
        )
        records.append(
            {
                "target": target.name,
                "pre_state": before.presence.value,
                "post_state": after.presence.value,
                "pre_sha256": before.sha256,
                "post_sha256": after.sha256,
                "pre_size": before.size,
                "post_size": after.size,
                "content_unchanged": (
                    after.presence is FilePresence.PRESENT
                    and after.sha256 == before.sha256
                    and after.size == before.size
                ),
                "mode_unchanged": final_modes[target] == modes[target],
                "mtime_updated": before.mtime_ns != after.mtime_ns,
                "temporary_artifacts": artifacts,
            }
        )

    passed = receipt.verified and all(
        record["content_unchanged"]
        and record["mode_unchanged"]
        and not record["temporary_artifacts"]
        for record in records
    )
    report: dict[str, object] = {
        "schema_version": 1,
        "pilot": "atlas-beacon-live-default-profile-noop",
        "generated_at": _timestamp(),
        "status": "PASS" if passed else "FAIL",
        "action": receipt.action,
        "receipt_status": receipt.status,
        "receipt_verified": receipt.verified,
        "records": records,
        "evidence": [
            {
                "target": Path(item.target).name,
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
        action="atlas.live-pilot.default-profile-report",
    )
    if not report_receipt.verified:
        raise RuntimeError("profile pilot report failed verification")
    if json.loads(output_path.read_text(encoding="utf-8")) != report:
        raise RuntimeError("profile pilot report readback mismatch")
    if not passed:
        raise RuntimeError("live default profile no-op pilot failed verification")
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
                "targets": [record["target"] for record in report["records"]],
                "receipt_verified": report["receipt_verified"],
                "report": str(args.out.resolve()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
