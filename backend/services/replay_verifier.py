"""Local Replay receipt/replay verification."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from backend.services.replay_exporter import default_replay_dir
from backend.services.replay_normalizer import _hash_payload
from backend.services.replay_signer import verify_signature

MAX_VERIFICATION_FILE_BYTES = 10 * 1024 * 1024
_REPLAY_ID_RE = re.compile(r"^replay_[a-f0-9]{12}$")
_VERIFICATION_FILENAMES = {
    "receipt": "receipt.json",
    "replay": "replay.redacted.json",
}


def _safe_replay_path(path: str, label: str) -> Path:
    root = default_replay_dir().expanduser().resolve()
    expected_filename = _VERIFICATION_FILENAMES[label]
    supplied = path.strip()
    if supplied.startswith("~/"):
        supplied = f"{Path.home()}/{supplied[2:]}"
    parts = supplied.split("/")
    if (
        len(parts) < 3
        or parts[-3] != "runs"
        or parts[-1] != expected_filename
        or not _REPLAY_ID_RE.fullmatch(parts[-2])
    ):
        raise ValueError(
            "Verification files must be inside the configured Replay directory"
        )

    replay_id = parts[-2]
    candidate = (root / "runs" / replay_id / expected_filename).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Verification files must be inside the configured Replay directory"
        ) from exc

    relative_path = f"runs/{replay_id}/{expected_filename}"
    if supplied not in {str(candidate), relative_path}:
        raise ValueError(
            "Verification files must be inside the configured Replay directory"
        )
    return candidate


def _load_json(path: str, label: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        safe_path = _safe_replay_path(path, label)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(safe_path, flags)
        try:
            size = os.fstat(descriptor).st_size
            if size > MAX_VERIFICATION_FILE_BYTES:
                return None, f"{label} is larger than {MAX_VERIFICATION_FILE_BYTES} bytes"
            with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
                descriptor = -1
                data = json.load(handle)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except ValueError as exc:
        return None, str(exc)
    except FileNotFoundError:
        return None, f"{label} file was not found"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {label}: line {exc.lineno}, column {exc.colno}"
    except (OSError, UnicodeError):
        return None, f"Could not read {label}"
    if not isinstance(data, dict):
        return None, f"Expected JSON object in {label}"
    return data, None


def _receipt_hash(receipt: dict[str, Any]) -> str:
    payload = dict(receipt)
    for key in ["signature_algorithm", "signature", "public_key", "signed_at"]:
        payload.pop(key, None)
    raw_hashes = payload.get("hashes")
    hashes = dict(raw_hashes) if isinstance(raw_hashes, dict) else {}
    hashes["receipt_hash"] = None
    payload["hashes"] = hashes
    return _hash_payload(payload)


def _verify_replay_files(receipt_path: str, replay_path: str) -> dict[str, Any]:
    receipt, receipt_error = _load_json(receipt_path, "receipt")
    replay_doc, replay_error = _load_json(replay_path, "replay")
    errors = [error for error in [receipt_error, replay_error] if error]
    warnings: list[str] = []

    if receipt is None or replay_doc is None:
        return {"ok": False, "errors": errors, "warnings": warnings}

    replay = replay_doc.get("replay")
    if not isinstance(replay, dict):
        errors.append("Replay JSON is missing replay object.")
        replay = {}

    run = replay.get("run") if isinstance(replay.get("run"), dict) else {}
    receipt_hashes = receipt.get("hashes") if isinstance(receipt.get("hashes"), dict) else {}
    run_hashes = run.get("hashes") if isinstance(run.get("hashes"), dict) else {}

    for field in ["schema_version", "receipt_id", "replay_id", "source_session_id", "hashes", "redaction"]:
        if field not in receipt:
            errors.append(f"Receipt missing required field: {field}")
    if replay_doc.get("schema_version") != "0.1":
        errors.append("Replay JSON schema_version must be 0.1.")
    if receipt.get("schema_version") != "0.1":
        errors.append("Receipt schema_version must be 0.1.")
    if receipt.get("replay_id") != run.get("replay_id"):
        errors.append("Receipt replay_id does not match replay run.")
    if receipt.get("source_session_id") != run.get("source_session_id"):
        errors.append("Receipt source_session_id does not match replay run.")

    expected_receipt_hash = receipt_hashes.get("receipt_hash")
    actual_receipt_hash = _receipt_hash(receipt)
    if expected_receipt_hash != actual_receipt_hash:
        errors.append("Receipt hash does not match receipt payload.")

    expected_replay_hash = receipt_hashes.get("redacted_replay_hash")
    if expected_replay_hash != run_hashes.get("redacted_replay_hash"):
        errors.append("Receipt redacted_replay_hash does not match replay run hash.")

    redaction = receipt.get("redaction") if isinstance(receipt.get("redaction"), dict) else {}
    if not redaction.get("mode"):
        errors.append("Receipt missing redaction mode.")
    if redaction.get("mode") == "raw":
        warnings.append("Receipt declares raw redaction mode.")

    signature = receipt.get("signature")
    public_key = receipt.get("public_key")
    if signature or public_key:
        if receipt.get("signature_algorithm") != "ed25519":
            errors.append("Unsupported signature algorithm.")
        elif not signature or not public_key:
            errors.append("Incomplete signature fields.")
        elif not verify_signature(str(expected_receipt_hash), str(expected_replay_hash), str(signature), str(public_key)):
            errors.append("Receipt signature is invalid.")
    else:
        warnings.append("No signature present; local hash verification only.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "receipt_hash": expected_receipt_hash,
        "redacted_replay_hash": expected_replay_hash,
        "redaction_mode": redaction.get("mode"),
        "signature_algorithm": receipt.get("signature_algorithm"),
        "signature_valid": bool(signature or public_key) and "Receipt signature is invalid." not in errors and "Unsupported signature algorithm." not in errors and "Incomplete signature fields." not in errors,
    }


def verify_replay_files(receipt_path: str, replay_path: str) -> dict[str, Any]:
    """Verify an exported Replay pair without allowing exceptions to escape."""
    try:
        return _verify_replay_files(receipt_path, replay_path)
    except Exception:
        return {
            "ok": False,
            "errors": ["Replay verification failed."],
            "warnings": [],
        }
