"""Recoverable authenticated archive segments for decades of authorized history.

Seals plaintext in RAM with the existing BackupCipher (AES-256-GCM), writes
only ciphertext and an authenticated manifest to storage, and requires the
operator-held key to verify or recover. No content is promoted to memory.
"""
from __future__ import annotations

from base64 import b64encode, b64decode
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import hmac
import json
import os
import tempfile

from sofia.ops.backup import BackupCipher


_AAD = b"sofia-archive-segment-v2"


@dataclass(frozen=True, slots=True)
class SealedArchiveReceipt:
    ciphertext_sha256: str
    ciphertext_bytes: int
    key_id: str
    segment_path: Path
    manifest_path: Path


class SealedArchiveSegmentStore:
    """One content-addressed encrypted object with key-independent file paths."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def stage(
        self, *, plaintext: bytes, cipher: BackupCipher, key_id: str,
    ) -> SealedArchiveReceipt:
        if not isinstance(cipher, BackupCipher):
            raise TypeError("existing authenticated BackupCipher required")
        if not isinstance(key_id, str) or not key_id.strip() or len(key_id) > 128:
            raise ValueError("bounded external key identifier required")
        if not isinstance(plaintext, bytes) or not 1 <= len(plaintext) <= 64 * 1024 * 1024:
            raise ValueError("bounded source bytes required")
        nonce, ciphertext = cipher.encrypt(plaintext, aad=_AAD)
        digest = sha256(ciphertext).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("symlinked archive root is not allowed")
        binary = self.root / f"{digest}.sealed"
        manifest = self.root / f"{digest}.json"
        mac_path = self.root / f"{digest}.hmac"
        info = {
            "schema": "sofia.sealed-archive-segment-v2",
            "ciphertext_sha256": digest,
            "ciphertext_bytes": len(ciphertext),
            "encryption": "AES-256-GCM",
            "nonce_b64": b64encode(nonce).decode("ascii"),
            "aad": _AAD.decode("ascii"),
            "key_id": key_id,
            "plaintext_stored": False,
        }
        manifest_bytes = (
            json.dumps(info, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        mac_bytes = (cipher.manifest_mac(manifest_bytes) + "\n").encode("ascii")
        for path, data in (
            (binary, ciphertext), (manifest, manifest_bytes), (mac_path, mac_bytes),
        ):
            with tempfile.NamedTemporaryFile(
                dir=self.root, prefix=".sealed-staging-", delete=False,
            ) as handle:
                staged = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                if path.exists():
                    if path.read_bytes() != data:
                        raise ValueError("conflicting archive object already exists")
                else:
                    os.replace(staged, path)
            finally:
                staged.unlink(missing_ok=True)
        return SealedArchiveReceipt(
            digest, len(ciphertext), key_id, binary, manifest,
        )

    def recover(
        self, *, digest: str, cipher: BackupCipher,
    ) -> bytes:
        """Validate manifest MAC, ciphertext digest and GCM tag before release."""
        if (
            not isinstance(digest, str) or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest)
        ):
            raise ValueError("lowercase SHA-256 archive digest required")
        if not isinstance(cipher, BackupCipher):
            raise TypeError("recovery requires a trusted BackupCipher")
        manifest = (self.root / f"{digest}.json").read_bytes()
        mac = (self.root / f"{digest}.hmac").read_text(encoding="ascii")
        if not cipher.verify_manifest_mac(manifest, mac):
            raise ValueError("archive manifest authentication failed")
        document = json.loads(manifest.decode("utf-8"))
        ciphertext = (self.root / f"{digest}.sealed").read_bytes()
        if (
            document.get("schema") != "sofia.sealed-archive-segment-v2"
            or document.get("encryption") != "AES-256-GCM"
            or document.get("aad") != _AAD.decode("ascii")
            or document.get("ciphertext_sha256") != digest
            or document.get("ciphertext_bytes") != len(ciphertext)
            or not hmac.compare_digest(sha256(ciphertext).hexdigest(), digest)
        ):
            raise ValueError("sealed archive ciphertext does not match its manifest")
        nonce = b64decode(document["nonce_b64"], validate=True)
        if len(nonce) != 12:
            raise ValueError("AES-GCM nonce is not 96 bits")
        # AES-GCM authenticates content and AAD. Never return corrupted text.
        return cipher.decrypt(ciphertext, nonce=nonce, aad=_AAD)
