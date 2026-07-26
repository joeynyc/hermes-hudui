"""Local Ed25519 signing for Replay receipts."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _message(receipt_hash: str, redacted_replay_hash: str) -> bytes:
    return f"{receipt_hash}\n{redacted_replay_hash}".encode("utf-8")


def _private_key_path(root: Path) -> Path:
    return root / "ed25519_private.pem"


def _load_or_create_private_key(root: Path) -> Ed25519PrivateKey:
    root.mkdir(parents=True, exist_ok=True)
    path = _private_key_path(root)
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    path.chmod(0o600)
    return key


def sign_receipt_hashes(receipt_hash: str, redacted_replay_hash: str, root: Path) -> dict[str, str]:
    key = _load_or_create_private_key(root)
    public_key = key.public_key()
    signature = key.sign(_message(receipt_hash, redacted_replay_hash))
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "signature_algorithm": "ed25519",
        "signature": base64.b64encode(signature).decode("ascii"),
        "public_key": base64.b64encode(public_bytes).decode("ascii"),
        "signed_at": datetime.now().isoformat(),
    }


def verify_signature(receipt_hash: str, redacted_replay_hash: str, signature: str, public_key: str) -> bool:
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key))
        public.verify(base64.b64decode(signature), _message(receipt_hash, redacted_replay_hash))
        return True
    except (InvalidSignature, ValueError, TypeError, binascii.Error):
        return False
