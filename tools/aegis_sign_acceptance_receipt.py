"""Sign one Core acceptance receipt envelope with a disposable/owner Ed25519 key.

This is a development helper only.  It signs the canonical JSON bytes of the
receipt with the ``signature`` field removed and writes the resulting envelope.
The signature grants no acceptance authority; collectors must still receive the
matching trusted public key, its SHA-256 fingerprint and signer key ID.

Example:

    python -m tools.aegis_sign_acceptance_receipt \
      --receipt core-receipts.json \
      --private-key owner-key.pem \
      --signer-key-id owner-key-1 \
      --output core-receipts.signed.json
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_ROOT / "src"))
    sys.path.insert(0, str(_ROOT))

from sofia.sdk.cognition_json import loads_strict_model_json  # noqa: E402

_MAX_INPUT = 16 * 1024 * 1024
_MAX_KEY = 64 * 1024


class ReceiptSigningError(RuntimeError):
    """Raised when a receipt or key cannot be signed safely."""


def _read_regular(path: Path, limit: int) -> bytes:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ReceiptSigningError(f"input is not a regular file: {path}")
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise ReceiptSigningError(f"input is outside bounded size: {path}")
    return path.read_bytes()


def _canonical_payload(document: dict[str, Any]) -> bytes:
    payload = {
        key: value for key, value in document.items() if key != "signature"
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def sign_receipt(
    receipt: Path,
    private_key: Path,
    signer_key_id: str,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(signer_key_id, str) or not 1 <= len(signer_key_id) <= 500:
        raise ReceiptSigningError("bounded signer key ID required")
    try:
        document = loads_strict_model_json(
            _read_regular(receipt, _MAX_INPUT).decode("utf-8")
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ReceiptSigningError(f"invalid receipt JSON: {error}") from error
    if type(document) is not dict:
        raise ReceiptSigningError("receipt must be a JSON object")
    key_bytes = _read_regular(private_key, _MAX_KEY)
    try:
        key = serialization.load_pem_private_key(key_bytes, password=None)
    except (TypeError, ValueError) as error:
        raise ReceiptSigningError("unreadable private key") from error
    if not isinstance(key, Ed25519PrivateKey):
        raise ReceiptSigningError("private key must be Ed25519")
    signature = key.sign(_canonical_payload(document))
    signed = dict(document)
    signed["signature"] = {
        "algorithm": "Ed25519",
        "signer_key_id": signer_key_id,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }
    payload = json.dumps(signed, sort_keys=True, indent=2) + "\n"
    destination = Path(output) if output is not None else Path(receipt)
    destination.write_text(payload, encoding="utf-8")
    return {
        "result": "RECEIPT_SIGNED_NOT_ACCEPTED",
        "signer_key_id": signer_key_id,
        "signature_sha256": sha256(signature).hexdigest(),
        "output": str(destination),
        "production_authorized": False,
        "release_accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--signer-key-id", required=True)
    parser.add_argument(
        "--output", type=Path,
        help="Signed envelope path; defaults to overwriting --receipt.",
    )
    args = parser.parse_args(argv)
    try:
        print(json.dumps(sign_receipt(
            args.receipt, args.private_key, args.signer_key_id,
            output=args.output,
        ), sort_keys=True))
        return 0
    except (ReceiptSigningError, OSError) as error:
        print(json.dumps({
            "result": "RECEIPT_SIGNING_REFUSED",
            "reason": str(error),
            "production_authorized": False,
            "release_accepted": False,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
