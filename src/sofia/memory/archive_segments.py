"""Content-addressed encrypted archive segments with independently checkable bytes.

The archive never serializes raw conversations itself: the caller MUST encrypt
before passing ciphertext. Manifest metadata is not conversation text.
Deleting/forgetting requires a separate tombstone-aware retention coordinator.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import tempfile


@dataclass(frozen=True, slots=True)
class SealedArchiveReceipt:
    ciphertext_sha256: str
    ciphertext_bytes: int
    key_id: str
    segment_path: Path
    manifest_path: Path


class SealedArchiveSegmentStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def stage_encrypted(
        self, *, ciphertext: bytes, key_id: str,
        encryption: str = "AES-256-GCM",
    ) -> SealedArchiveReceipt:
        if encryption != "AES-256-GCM":
            raise ValueError("approved authenticated encryption required")
        if not isinstance(key_id, str) or not key_id.strip() or len(key_id) > 128:
            raise ValueError("bounded external recovery key identifier required")
        if not isinstance(ciphertext, bytes) or not 32 <= len(ciphertext) <= 64 * 1024 * 1024:
            raise ValueError("bounded sealed archive segment required")
        digest = sha256(ciphertext).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("archive root must not be a symbolic link")
        binary = self.root / f"{digest}.sealed"
        manifest = self.root / f"{digest}.json"
        info = {
            "schema": "sofia.sealed-archive-segment-v1",
            "ciphertext_sha256": digest,
            "ciphertext_bytes": len(ciphertext),
            "encryption": encryption,
            "key_id": key_id,
            "plaintext_in_manifest": False,
        }
        manifest_bytes = (json.dumps(info, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        if binary.exists():
            if sha256(binary.read_bytes()).hexdigest() != digest:
                raise ValueError("existing sealed archive digest mismatch")
            if manifest.is_file() and manifest.read_bytes() != manifest_bytes:
                raise ValueError("existing sealed archive manifest mismatch")
            # Crash after the blob rename but before its manifest must be
            # repairable from caller-supplied, digest-matching ciphertext.
            if not manifest.is_file():
                with tempfile.NamedTemporaryFile(
                    dir=self.root, prefix=".manifest-", delete=False
                ) as tmp:
                    repair_path = Path(tmp.name)
                    tmp.write(manifest_bytes)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                try:
                    os.replace(repair_path, manifest)
                finally:
                    repair_path.unlink(missing_ok=True)
        else:
            with tempfile.NamedTemporaryFile(dir=self.root, prefix=".staging-", delete=False) as tmp:
                temp = Path(tmp.name)
                tmp.write(ciphertext)
                tmp.flush()
                os.fsync(tmp.fileno())
            try:
                if binary.exists():
                    raise FileExistsError("raced with archive publisher")
                os.replace(temp, binary)
                with tempfile.NamedTemporaryFile(dir=self.root, prefix=".manifest-", delete=False) as tmp:
                    manifest_tmp = Path(tmp.name)
                    tmp.write(manifest_bytes)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(manifest_tmp, manifest)
            finally:
                temp.unlink(missing_ok=True)
        return SealedArchiveReceipt(digest, len(ciphertext), key_id, binary, manifest)

    def verify(self, digest: str) -> bool:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("lowercase sha256 required")
        binary = self.root / f"{digest}.sealed"
        manifest = self.root / f"{digest}.json"
        if not binary.is_file() or not manifest.is_file():
            return False
        info = json.loads(manifest.read_text(encoding="utf-8"))
        return (
            info.get("schema") == "sofia.sealed-archive-segment-v1"
            and info.get("ciphertext_sha256") == digest
            and info.get("ciphertext_bytes") == binary.stat().st_size
            and info.get("encryption") == "AES-256-GCM"
            and sha256(binary.read_bytes()).hexdigest() == digest
        )
