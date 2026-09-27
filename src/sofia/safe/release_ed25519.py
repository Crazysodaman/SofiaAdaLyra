from __future__ import annotations

from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.dev.release import ReleaseManifest
from sofia.safe.release import ReleaseSignatureVerifier


class Ed25519ReleaseSignatureVerifier(ReleaseSignatureVerifier):
    """Verify release manifests against an explicit trusted Ed25519 keyring."""

    def __init__(
        self,
        trusted_keys: dict[str, Path | bytes],
    ) -> None:
        if not isinstance(trusted_keys, dict) or not trusted_keys:
            raise ValueError("at least one trusted release key is required")
        loaded: dict[str, Ed25519PublicKey] = {}
        for key_id, source in trusted_keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("release signer key IDs must be nonempty")
            if isinstance(source, Path):
                raw = source.read_bytes()
            elif isinstance(source, bytes):
                raw = source
            else:
                raise TypeError(
                    "trusted release keys must be Path or bytes values"
                )
            key = serialization.load_pem_public_key(raw)
            if not isinstance(key, Ed25519PublicKey):
                raise TypeError(
                    f"trusted release key {key_id!r} is not Ed25519"
                )
            loaded[key_id] = key
        self._keys = loaded

    def verify(
        self,
        *,
        manifest: ReleaseManifest,
        signature: bytes,
        signer_key_id: str,
    ) -> bool:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        if not isinstance(signature, bytes) or not signature:
            raise ValueError("signature must be nonempty bytes")
        key = self._keys.get(signer_key_id)
        if key is None:
            return False
        try:
            key.verify(signature, manifest.canonical_bytes())
        except InvalidSignature:
            return False
        return True
