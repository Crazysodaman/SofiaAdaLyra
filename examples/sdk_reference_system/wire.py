"""Pure bounded JSON helpers for the SDK Core/Platform tutorial.

No identity, authentication, authority, secrets, network or persistence.
The same canonical encoding is used by both *example* peers, not a replacement
for the production SDK transport or cryptographic channel binding.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Mapping


def payload_digest(payload: Mapping[str, object]) -> str:
    """Calculate a bounded payload fingerprint, never an authorization proof."""
    if not isinstance(payload, Mapping) or len(payload) > 16:
        raise ValueError("bounded object payload required")
    try:
        data = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError) as exc:
        raise ValueError("payload must contain finite JSON") from exc
    if len(data) > 4096:
        raise ValueError("example payload exceeds 4096 bytes")
    return sha256(data).hexdigest()
