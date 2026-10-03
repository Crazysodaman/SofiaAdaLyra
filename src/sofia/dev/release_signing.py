"""Offline Ed25519 signing helper for release manifests.

Private signing keys are inputs to the command and are never persisted by this
module. Production key custody belongs outside the repository/build artifact.
"""
from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.dev.release import ReleaseManifest


def load_ed25519_private_key(
    source: Path | bytes,
    *,
    password: bytes | None = None,
) -> Ed25519PrivateKey:
    if isinstance(source, Path):
        raw = source.read_bytes()
    elif isinstance(source, bytes):
        raw = source
    else:
        raise TypeError("private key source must be Path or bytes")
    key = serialization.load_pem_private_key(
        raw,
        password=password,
    )
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("release signing key must be Ed25519")
    return key


def sign_manifest(
    manifest: ReleaseManifest,
    *,
    private_key: Ed25519PrivateKey,
) -> bytes:
    if not isinstance(manifest, ReleaseManifest):
        raise TypeError("manifest must be ReleaseManifest")
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("private_key must be Ed25519PrivateKey")
    return private_key.sign(manifest.canonical_bytes())


def sign_manifest_file(
    manifest_path: Path,
    *,
    private_key_path: Path,
    signature_path: Path,
    password: bytes | None = None,
) -> bytes:
    if not isinstance(manifest_path, Path) or not manifest_path.is_file():
        raise FileNotFoundError("release manifest does not exist")
    manifest = ReleaseManifest.from_canonical_bytes(
        manifest_path.read_bytes()
    )
    key = load_ed25519_private_key(
        private_key_path,
        password=password,
    )
    signature = sign_manifest(manifest, private_key=key)
    signature_path.parent.mkdir(parents=True, exist_ok=True)
    signature_path.write_bytes(signature)
    return signature
