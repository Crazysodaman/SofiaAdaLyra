"""Encrypted backup/restore engine for canonical Sofía production state.

The engine snapshots SQLite online, captures protected/runtime projection files,
encrypts every payload with AES-256-GCM, records plaintext SHA-256 digests, and
restores only through a verified staging directory.

It does not infer that two filesystem paths are independent failure domains.
The caller must name the destination failure domain explicitly, and RecoveryGuard
can later enforce that a restore target is different from the backup domain.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sofia.config.defaults import production_storage_layout
from sofia.identity.model import IdentityBootstrapMode
from sofia.identity.store import IdentityStore
from sofia.ops.recovery import BackupEvidence, RestoreVerification
from sofia.state.component_schema import verify_production_component_schemas
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.constitution.store import (
    ConstitutionStore,
    canonical_constitution_text,
)


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BackupEntry:
    logical_path: str
    payload_name: str
    sha256: str
    size: int
    nonce_b64: str

    def __post_init__(self) -> None:
        logical = Path(self.logical_path)
        if (
            not self.logical_path
            or logical.is_absolute()
            or ".." in logical.parts
        ):
            raise ValueError("logical_path must be a safe relative path")
        payload = Path(self.payload_name)
        if (
            not self.payload_name
            or payload.name != self.payload_name
            or self.payload_name in {".", ".."}
        ):
            raise ValueError("payload_name must be a simple file name")
        if len(self.sha256) != 64:
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if type(self.size) is not int or self.size < 0:
            raise ValueError("size must be nonnegative")
        if not self.nonce_b64:
            raise ValueError("nonce_b64 required")


@dataclass(frozen=True, slots=True)
class BackupManifest:
    backup_id: str
    source_host_id: str
    failure_domain: str
    created_at: datetime
    entries: tuple[BackupEntry, ...]
    format_version: int = 1

    def __post_init__(self) -> None:
        if not self.backup_id.strip():
            raise ValueError("backup_id required")
        if not self.source_host_id.strip():
            raise ValueError("source_host_id required")
        if not self.failure_domain.strip():
            raise ValueError("failure_domain required")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if type(self.format_version) is not int or self.format_version != 1:
            raise ValueError("unsupported backup format version")
        if not isinstance(self.entries, tuple):
            raise TypeError("entries must be a tuple")
        logical = [entry.logical_path for entry in self.entries]
        payload = [entry.payload_name for entry in self.entries]
        if len(logical) != len(set(logical)):
            raise ValueError("backup logical paths must be unique")
        if len(payload) != len(set(payload)):
            raise ValueError("backup payload names must be unique")

    def canonical_bytes(self) -> bytes:
        document = {
            "backup_id": self.backup_id,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "entries": [
                {
                    "logical_path": item.logical_path,
                    "nonce_b64": item.nonce_b64,
                    "payload_name": item.payload_name,
                    "sha256": item.sha256,
                    "size": item.size,
                }
                for item in self.entries
            ],
            "failure_domain": self.failure_domain,
            "format_version": self.format_version,
            "source_host_id": self.source_host_id,
        }
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @property
    def digest(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_bytes(cls, raw: bytes) -> "BackupManifest":
        document = json.loads(raw.decode("utf-8"))
        return cls(
            backup_id=document["backup_id"],
            source_host_id=document["source_host_id"],
            failure_domain=document["failure_domain"],
            created_at=datetime.fromisoformat(document["created_at"]),
            format_version=int(document["format_version"]),
            entries=tuple(
                BackupEntry(
                    logical_path=item["logical_path"],
                    payload_name=item["payload_name"],
                    sha256=item["sha256"],
                    size=int(item["size"]),
                    nonce_b64=item["nonce_b64"],
                )
                for item in document["entries"]
            ),
        )


class BackupCipher:
    """AES-256-GCM payload cipher. Key storage is intentionally external."""

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("backup key must be exactly 32 bytes")
        self._key = key
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        return nonce, self._aes.encrypt(nonce, plaintext, aad)

    def decrypt(self, ciphertext: bytes, *, nonce: bytes, aad: bytes) -> bytes:
        return self._aes.decrypt(nonce, ciphertext, aad)

    def manifest_mac(self, manifest_bytes: bytes) -> str:
        if not isinstance(manifest_bytes, bytes):
            raise TypeError("manifest_bytes must be bytes")
        return hmac.new(
            self._key,
            b"sofia-backup-manifest-v1\0" + manifest_bytes,
            sha256,
        ).hexdigest()

    def verify_manifest_mac(
        self,
        manifest_bytes: bytes,
        expected: str,
    ) -> bool:
        if not isinstance(expected, str):
            raise TypeError("expected manifest MAC must be text")
        return hmac.compare_digest(
            self.manifest_mac(manifest_bytes),
            expected.strip().casefold(),
        )


def load_backup_key(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise TypeError("backup key path must be a Path")
    raw = path.read_bytes().strip()
    if len(raw) == 32:
        return raw
    try:
        decoded = b64decode(raw, validate=True)
    except Exception as exc:
        raise BackupError("backup key is neither raw 32-byte nor base64") from exc
    if len(decoded) != 32:
        raise BackupError("decoded backup key must be 32 bytes")
    return decoded


class BackupEngine:
    def __init__(self, cipher: BackupCipher) -> None:
        if not isinstance(cipher, BackupCipher):
            raise TypeError("cipher must be BackupCipher")
        self.cipher = cipher

    @staticmethod
    def _sqlite_snapshot(source: Path, target: Path) -> None:
        if not source.is_file():
            raise FileNotFoundError("canonical state database does not exist")
        with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
            row = dst.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise BackupError("SQLite backup failed integrity_check")

    @staticmethod
    def _collect_files(state_path: Path, sqlite_snapshot: Path) -> tuple[tuple[str, Path], ...]:
        layout = production_storage_layout(state_path=state_path)
        result: list[tuple[str, Path]] = [("sofia.db", sqlite_snapshot)]

        protected = layout.protected_root
        if protected.exists():
            for path in sorted(protected.rglob("*")):
                if path.is_symlink():
                    raise BackupError(f"protected state may not contain symlink: {path}")
                if path.is_file():
                    logical = Path("protected") / path.relative_to(protected)
                    result.append((logical.as_posix(), path))

        for path in (layout.personality_path, layout.avatar_path):
            if path.is_file():
                result.append((path.name, path))

        release_pointer = state_path.parent / "release-runtime" / "active-release.json"
        if release_pointer.is_file():
            result.append(("release-runtime/active-release.json", release_pointer))

        return tuple(result)

    def create(
        self,
        *,
        state_path: Path,
        destination_root: Path,
        source_host_id: str,
        failure_domain: str,
        now: datetime | None = None,
    ) -> tuple[Path, BackupEvidence]:
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("existing canonical state database required")
        if not isinstance(destination_root, Path):
            raise TypeError("destination_root must be a Path")
        if not source_host_id.strip() or not failure_domain.strip():
            raise ValueError("source_host_id and failure_domain are required")
        created_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        backup_id = (
            created_at.strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid4().hex[:12]
        )
        destination_root.mkdir(parents=True, exist_ok=True)
        final = destination_root / backup_id
        if final.exists():
            raise BackupError("backup destination already exists")

        with tempfile.TemporaryDirectory(
            prefix=f".{backup_id}.",
            dir=destination_root,
        ) as temp_dir:
            staging = Path(temp_dir)
            payload_dir = staging / "payload"
            payload_dir.mkdir()
            snapshot = staging / "sofia.db.snapshot"
            self._sqlite_snapshot(state_path, snapshot)

            entries: list[BackupEntry] = []
            for index, (logical, source) in enumerate(
                self._collect_files(state_path, snapshot)
            ):
                plaintext = source.read_bytes()
                digest = sha256(plaintext).hexdigest()
                payload_name = f"{index:04d}.bin"
                aad = f"{backup_id}:{logical}".encode("utf-8")
                nonce, encrypted = self.cipher.encrypt(plaintext, aad=aad)
                (payload_dir / payload_name).write_bytes(encrypted)
                entries.append(
                    BackupEntry(
                        logical_path=logical,
                        payload_name=payload_name,
                        sha256=digest,
                        size=len(plaintext),
                        nonce_b64=b64encode(nonce).decode("ascii"),
                    )
                )

            manifest = BackupManifest(
                backup_id=backup_id,
                source_host_id=source_host_id,
                failure_domain=failure_domain,
                created_at=created_at,
                entries=tuple(entries),
            )
            manifest_bytes = manifest.canonical_bytes()
            (staging / "manifest.json").write_bytes(manifest_bytes)
            (staging / "manifest.hmac").write_text(
                self.cipher.manifest_mac(manifest_bytes) + "\n",
                encoding="ascii",
            )
            os.replace(staging, final)

        return final, BackupEvidence(
            backup_id=backup_id,
            source_host_id=source_host_id,
            failure_domain=failure_domain,
            created_at=created_at,
            content_digest=manifest.digest,
        )

    def verify(self, backup_dir: Path) -> BackupManifest:
        if not isinstance(backup_dir, Path) or not backup_dir.is_dir():
            raise FileNotFoundError("backup directory does not exist")
        manifest_path = backup_dir / "manifest.json"
        manifest_mac_path = backup_dir / "manifest.hmac"
        if not manifest_path.is_file():
            raise BackupError("backup manifest is missing")
        if not manifest_mac_path.is_file():
            raise BackupError("backup manifest authentication is missing")
        manifest_bytes = manifest_path.read_bytes()
        if not self.cipher.verify_manifest_mac(
            manifest_bytes,
            manifest_mac_path.read_text(encoding="ascii"),
        ):
            raise BackupError("backup manifest authentication failed")
        manifest = BackupManifest.from_bytes(manifest_bytes)
        payload_dir = backup_dir / "payload"
        for entry in manifest.entries:
            payload = payload_dir / entry.payload_name
            if not payload.is_file():
                raise BackupError(f"backup payload missing: {entry.payload_name}")
            aad = f"{manifest.backup_id}:{entry.logical_path}".encode("utf-8")
            plaintext = self.cipher.decrypt(
                payload.read_bytes(),
                nonce=b64decode(entry.nonce_b64),
                aad=aad,
            )
            if len(plaintext) != entry.size:
                raise BackupError(f"backup size mismatch: {entry.logical_path}")
            if sha256(plaintext).hexdigest() != entry.sha256:
                raise BackupError(f"backup digest mismatch: {entry.logical_path}")
        return manifest

    def restore(
        self,
        *,
        backup_dir: Path,
        target_state_path: Path,
        verifier: str,
        replace_existing: bool = False,
        now: datetime | None = None,
    ) -> RestoreVerification:
        manifest = self.verify(backup_dir)
        if not isinstance(target_state_path, Path):
            raise TypeError("target_state_path must be a Path")
        target_root = target_state_path.parent
        target_root.mkdir(parents=True, exist_ok=True)
        if target_state_path.exists() and not replace_existing:
            raise BackupError(
                "target state database exists; explicit replace_existing required"
            )

        with tempfile.TemporaryDirectory(
            prefix=".sofia-restore.",
            dir=target_root,
        ) as temp_dir:
            staging = Path(temp_dir)
            payload_dir = backup_dir / "payload"
            for entry in manifest.entries:
                aad = f"{manifest.backup_id}:{entry.logical_path}".encode("utf-8")
                plaintext = self.cipher.decrypt(
                    (payload_dir / entry.payload_name).read_bytes(),
                    nonce=b64decode(entry.nonce_b64),
                    aad=aad,
                )
                if sha256(plaintext).hexdigest() != entry.sha256:
                    raise BackupError(
                        f"restore digest mismatch: {entry.logical_path}"
                    )
                target = staging / entry.logical_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(plaintext)

            staged_db = staging / "sofia.db"
            if not staged_db.is_file():
                raise BackupError("backup does not contain sofia.db")
            with sqlite3.connect(staged_db) as db:
                row = db.execute("PRAGMA integrity_check").fetchone()
                if row is None or row[0] != "ok":
                    raise BackupError("restored SQLite failed integrity_check")

            # Verify semantic protected state before replacing live files.
            verify_production_component_schemas(staged_db)
            SQLiteStatePlane(staged_db).schema_revision
            protected_root = staging / "protected"
            constitution = protected_root / "constitution.md"
            identity = protected_root / "identity.json"
            if constitution.is_file():
                loaded_constitution = ConstitutionStore(constitution).load()
                constitution_hash = protected_root / "constitution.sha256"
                if constitution_hash.is_file():
                    expected_hash = constitution_hash.read_text(
                        encoding="utf-8"
                    ).strip()
                    if expected_hash != loaded_constitution.content_hash:
                        raise BackupError(
                            "restored Constitution hash does not match protected digest"
                        )
            if identity.is_file():
                IdentityStore(
                    identity,
                    bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
                ).load()

            for source in sorted(staging.rglob("*")):
                if not source.is_file():
                    continue
                logical = source.relative_to(staging)
                destination = (
                    target_state_path
                    if logical.as_posix() == "sofia.db"
                    else target_root / logical
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                temp_target = destination.with_name(
                    f".{destination.name}.restore"
                )
                shutil.copy2(source, temp_target)
                os.replace(temp_target, destination)

        return RestoreVerification(
            backup_id=manifest.backup_id,
            verified_at=(now or datetime.now(timezone.utc)).astimezone(timezone.utc),
            verifier=verifier,
            succeeded=True,
        )


def rotate_backups(
    root: Path,
    *,
    keep: int,
) -> tuple[Path, ...]:
    if not isinstance(root, Path):
        raise TypeError("root must be a Path")
    if type(keep) is not int or keep < 1:
        raise ValueError("keep must be a positive integer")
    if not root.exists():
        return ()
    backups = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and (path / "manifest.json").is_file()
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    removed: list[Path] = []
    for path in backups[keep:]:
        shutil.rmtree(path)
        removed.append(path)
    return tuple(removed)
