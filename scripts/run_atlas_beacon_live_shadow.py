"""Observe real Hermes memory/profile write targets without mutating them."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.collectors.utils import default_hermes_dir
from backend.governance import (
    EvidenceTruth,
    FilePresence,
    VerifiedFileActionAdapter,
    observe_file,
)


def _targets(root: Path) -> list[Path]:
    targets = [
        root / "config.yaml",
        root / "SOUL.md",
        root / "memories" / "MEMORY.md",
        root / "memories" / "USER.md",
    ]
    profiles = root / "profiles"
    if profiles.is_dir():
        for profile in sorted(path for path in profiles.iterdir() if path.is_dir()):
            targets.extend([profile / "config.yaml", profile / "SOUL.md"])
    return targets


def run_shadow(root: Path) -> dict:
    adapter = VerifiedFileActionAdapter(allowed_roots=[root])
    records = []
    all_safe = True
    for target in _targets(root):
        before = observe_file(target)
        receipt = adapter.shadow_one(
            target, b"", action="atlas.live-shadow-observation"
        )
        after = observe_file(target)
        unchanged = before.same_version(after)
        precondition = receipt.evidence[0]
        safe = (
            precondition.truth is EvidenceTruth.TRUE
            and before.presence in {FilePresence.PRESENT, FilePresence.ABSENT}
            and unchanged
        )
        all_safe = all_safe and safe
        records.append(
            {
                "target": target.relative_to(root).as_posix(),
                "presence": before.presence.value,
                "size": before.size,
                "sha256": before.sha256,
                "reason": before.reason,
                "precondition": precondition.truth.value,
                "unchanged": unchanged,
            }
        )
    return {
        "schema_version": 1,
        "mode": "read-only-shadow",
        "root_label": "HERMES_HOME",
        "status": "PASS" if all_safe else "BLOCKED",
        "target_count": len(records),
        "unknown_count": sum(
            item["presence"] == FilePresence.UNKNOWN.value for item in records
        ),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(args.hermes_dir or default_hermes_dir()).resolve(strict=False)
    report = run_shadow(root)
    payload = (
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    writer = VerifiedFileActionAdapter(
        allowed_roots=[args.out.parent.resolve(strict=False)]
    )
    receipt = writer.write_one(args.out, payload, action="shadow.report.write")
    readback = json.loads(args.out.read_text(encoding="utf-8"))
    ok = receipt.verified and readback == report and report["status"] == "PASS"
    print(
        json.dumps(
            {
                "status": "PASS" if ok else "BLOCKED",
                "targets": report["target_count"],
                "unknown": report["unknown_count"],
                "report": str(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
