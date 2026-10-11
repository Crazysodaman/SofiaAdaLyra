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
from contextlib import closing
from dataclasses import dataclass
import errno
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import sqlite3
import stat
import sys
import tempfile
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from sofia.config.defaults import production_storage_layout
from sofia.identity.model import IdentityBootstrapMode
from sofia.identity.store import IdentityStore
from sofia.ops.recovery import BackupEvidence, RestoreVerification
from sofia.state.component_schema import verify_production_component_schemas
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.constitution.store import (
    ConstitutionStore,
    canonical_constitution_text,
)


_MAX_BACKUP_MANIFEST_BYTES = 16 * 1024 * 1024
_AESGCM_TAG_BYTES = 16


class BackupError(RuntimeError):
    pass


class RestorePublicationUncertain(BackupError):
    """Restored files were renamed but their directory durability is unknown."""


class BackupPublicationUncertain(BackupError):
    """Encrypted archive was published, but pathname durability is unknown."""


def _fsync_restored_linux_directories(directories: set[Path]) -> None:
    """Persist restored pathnames and newly created parent directory entries.

    Files were fsynced before rename. All ancestor entries are checked and
    flushed deepest-first, because a nested asset's parent may also have
    been created during the restore. Linux only: unsupported directory fsync
    fails closed rather than claiming a durable offline recovery.
    """
    parents: set[Path] = set()
    for directory in directories:
        parents.add(directory)
        parents.update(directory.parents)
    for directory in sorted(parents, key=lambda item: (-len(item.parts), str(item))):
        _reject_redirected_restore_path(directory)
        descriptor = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise BackupError("restored pathname parent is no longer a directory")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _durably_prepare_backup_archive(staging: Path) -> None:
    """Flush every encrypted payload/manifest and nested directory on Linux.

    Ordinary close() and rename() alone do not make an archive restart-safe.
    A failing fsync before publication denies the success receipt entirely.
    """
    if not sys.platform.startswith("linux"):
        return
    _reject_redirected_backup_input(staging)
    for item in sorted(staging.rglob("*")):
        _reject_redirected_backup_input(item)
        if not item.is_file():
            continue
        fd = os.open(
            item, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise BackupError("encrypted backup entry changed type before fsync")
            os.fsync(fd)
        finally:
            os.close(fd)
    directories = {staging}
    directories.update(
        item for item in staging.rglob("*") if item.is_dir()
    )
    _fsync_restored_linux_directories(directories)


def _publish_backup_archive_without_replacing(staging: Path, final: Path) -> None:
    """Publish the encrypted archive only at an unoccupied path.

    Linux uses RENAME_NOREPLACE instead of os.replace's overwrite semantics.
    Windows directory rename denies an occupied name; unsupported hosts fail
    closed. Crash durability is reported separately from name visibility.
    """
    _reject_redirected_backup_input(staging)
    _reject_redirected_backup_input(final)
    if final.exists() or final.is_symlink():
        raise FileExistsError("encrypted backup destination already exists")
    if sys.platform.startswith("linux"):
        import ctypes

        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
        except AttributeError as exc:
            raise BackupError(
                "atomic absence-only archive publication is unavailable"
            ) from exc
        renameat2.argtypes = (
            ctypes.c_int, ctypes.c_char_p,
            ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        if renameat2(
            -100, os.fsencode(staging), -100, os.fsencode(final), 1,
        ) != 0:
            err = ctypes.get_errno()
            if err == errno.EEXIST:
                raise FileExistsError(
                    err, "encrypted archive destination appeared during publish",
                    os.fspath(final),
                )
            raise OSError(err, os.strerror(err), os.fspath(final))
        try:
            _fsync_restored_linux_directories({final.parent})
        except OSError as exc:
            raise BackupPublicationUncertain(
                "encrypted archive was renamed but durable publication is "
                "uncertain; inspect and verify before retention or restore"
            ) from exc
        return
    if os.name == "nt":
        os.rename(staging, final)
        return
    raise BackupError("atomic archive publication unsupported on this platform")


def _reject_redirected_restore_path(path: Path) -> None:
    """No restored files may follow symlinks or Windows junctions."""
    for component in (path, *path.parents):
        if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
            raise BackupError(
                "restore destination includes a symbolic link or junction"
            )


def _reject_redirected_backup_input(path: Path) -> None:
    """Backup inputs must not escape their selected state/archive home.

    A protected-root junction, payload symlink, or archive-directory redirect
    can otherwise cause backup/verification to read unrelated host files.
    """
    for component in (path, *path.parents):
        if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
            raise BackupError(
                "backup source or archive contains a symbolic link or junction"
            )


@dataclass(frozen=True, slots=True)
class BackupEntry:
    logical_path: str
    payload_name: str
    sha256: str
    size: int
    nonce_b64: str

    def __post_init__(self) -> None:
        # Manifests are portable between Unix and Windows. Native Path()
        # alone cannot recognize a Windows drive or backslash traversal
        # when verification happens on Linux.
        logical = PurePosixPath(self.logical_path)
        windows = PureWindowsPath(self.logical_path)
        if (
            not self.logical_path or chr(0) in self.logical_path
            or chr(92) in self.logical_path
            or any(character in self.logical_path for character in '<>:"|?*')
            or logical.is_absolute() or windows.is_absolute()
            or windows.drive or ".." in logical.parts
            or "." in logical.parts
            or self.logical_path in {".", ".."}
            or logical.as_posix() != self.logical_path
            or any(
                not part or part != part.rstrip(" .")
                or any(ord(ch) < 32 for ch in part)
                or PureWindowsPath(part).is_reserved()
                for part in logical.parts
            )
        ):
            raise ValueError("logical_path must be a safe relative path")
        payload = PurePosixPath(self.payload_name)
        if (
            not self.payload_name or chr(0) in self.payload_name
            or chr(92) in self.payload_name
            or any(character in self.payload_name for character in '<>:"|?*')
            or payload.name != self.payload_name
            or self.payload_name in {".", ".."}
            or PureWindowsPath(self.payload_name).drive
            or self.payload_name != self.payload_name.rstrip(" .")
            or any(ord(ch) < 32 for ch in self.payload_name)
            or PureWindowsPath(self.payload_name).is_reserved()
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
        # Manifests may be created on a case-sensitive Linux host and later
        # restored on case-insensitive Windows storage. Two different source
        # names cannot safely resolve to the same recovery destination.
        if len(logical) != len({name.casefold() for name in logical}):
            raise ValueError("backup logical paths must be portable-unique")
        if len(payload) != len({name.casefold() for name in payload}):
            raise ValueError("backup payload names must be portable-unique")

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
    def _sqlite_snapshot(
        source: Path, target: Path, *, guard: CanonicalSQLiteGuard | None = None,
    ) -> None:
        # A mode=rw/default connection can silently create a new database after
        # source loss. Preserve the existing writer identity across the backup.
        source_guard = guard if guard is not None else CanonicalSQLiteGuard(source)
        if source_guard.canonical_path != source.absolute():
            raise BackupError("backup source does not match pinned canonical state")
        with (
            closing(source_guard.connect(timeout=10)) as src,
            closing(sqlite3.connect(target)) as dst,
        ):
            src.backup(dst)
            row = dst.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise BackupError("SQLite backup failed integrity_check")

    @staticmethod
    def _collect_files(state_path: Path, sqlite_snapshot: Path) -> tuple[tuple[str, Path], ...]:
        layout = production_storage_layout(state_path=state_path)
        result: list[tuple[str, Path]] = [("sofia.db", sqlite_snapshot)]

        protected = layout.protected_root
        # A protected directory can itself be a junction even though no
        # enumerated child is a symlink. Inspect the selected root first.
        _reject_redirected_backup_input(state_path)
        _reject_redirected_backup_input(protected)
        if protected.exists():
            for path in sorted(protected.rglob("*")):
                if path.is_symlink():
                    raise BackupError(f"protected state may not contain symlink: {path}")
                if path.is_file():
                    _reject_redirected_backup_input(path)
                    logical = Path("protected") / path.relative_to(protected)
                    result.append((logical.as_posix(), path))

        for path in (layout.personality_path, layout.avatar_path):
            _reject_redirected_backup_input(path)
            if path.is_file():
                result.append((path.name, path))

        release_pointer = state_path.parent / "release-runtime" / "active-release.json"
        _reject_redirected_backup_input(release_pointer)
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
        source_guard = CanonicalSQLiteGuard(state_path)
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
        _reject_redirected_backup_input(destination_root)
        destination_root.mkdir(parents=True, exist_ok=True)
        _reject_redirected_backup_input(destination_root)
        final = destination_root / backup_id
        if final.exists() or final.is_symlink():
            raise BackupError("backup destination already exists")

        with tempfile.TemporaryDirectory(
            prefix=f".{backup_id}.",
            dir=destination_root,
        ) as temp_dir:
            staging = Path(temp_dir)
            payload_dir = staging / "payload"
            payload_dir.mkdir()
            entries: list[BackupEntry] = []
            with tempfile.TemporaryDirectory(
                prefix=".sofia-cleartext-snapshot-", dir=state_path.parent,
            ) as offline_snapshot_dir:
                snapshot = Path(offline_snapshot_dir) / "sofia.db.snapshot"
                self._sqlite_snapshot(state_path, snapshot, guard=source_guard)
                for index, (logical, source) in enumerate(
                    self._collect_files(state_path, snapshot)
                ):
                    _reject_redirected_backup_input(source)
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
                    if logical == "sofia.db":
                        # The SQLite online backup is temporary cleartext input,
                        # not a member of the published encrypted archive. Remove
                        # it as soon as its authenticated ciphertext exists.
                        snapshot.unlink()
                if snapshot.exists() or snapshot.is_symlink():
                    raise BackupError(
                        "plaintext SQLite snapshot cannot enter encrypted archive"
                    )
            if (staging / "sofia.db.snapshot").exists():
                raise BackupError(
                    "plaintext SQLite snapshot was left in backup staging root"
                )
            manifest = BackupManifest(
                backup_id=backup_id,
                source_host_id=source_host_id,
                failure_domain=failure_domain,
                created_at=created_at,
                entries=tuple(entries),
            )
            manifest_bytes = manifest.canonical_bytes()
            if len(manifest_bytes) > _MAX_BACKUP_MANIFEST_BYTES:
                raise BackupError("backup manifest exceeds bounded archive size")
            (staging / "manifest.json").write_bytes(manifest_bytes)
            (staging / "manifest.hmac").write_text(
                self.cipher.manifest_mac(manifest_bytes) + "\n",
                encoding="ascii",
            )
            _durably_prepare_backup_archive(staging)
            _publish_backup_archive_without_replacing(staging, final)

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
        _reject_redirected_backup_input(backup_dir)
        manifest_path = backup_dir / "manifest.json"
        manifest_mac_path = backup_dir / "manifest.hmac"
        if not manifest_path.is_file():
            raise BackupError("backup manifest is missing")
        if not manifest_mac_path.is_file():
            raise BackupError("backup manifest authentication is missing")
        _reject_redirected_backup_input(manifest_path)
        _reject_redirected_backup_input(manifest_mac_path)
        if manifest_path.stat().st_size > _MAX_BACKUP_MANIFEST_BYTES:
            raise BackupError("backup manifest exceeds bounded archive size")
        # Even if a file grew after stat, the capped reader never allocates
        # unbounded memory from an untrusted/corrupted backup medium.
        with manifest_path.open("rb") as source:
            manifest_bytes = source.read(_MAX_BACKUP_MANIFEST_BYTES + 1)
        if len(manifest_bytes) > _MAX_BACKUP_MANIFEST_BYTES:
            raise BackupError("backup manifest exceeds bounded archive size")
        if manifest_mac_path.stat().st_size > 256:
            raise BackupError("backup manifest authentication record exceeds size limit")
        with manifest_mac_path.open("rb") as source:
            mac_bytes = source.read(257)
        if len(mac_bytes) > 256:
            raise BackupError("backup manifest authentication record exceeds size limit")
        if not self.cipher.verify_manifest_mac(
            manifest_bytes,
            mac_bytes.decode("ascii"),
        ):
            raise BackupError("backup manifest authentication failed")
        manifest = BackupManifest.from_bytes(manifest_bytes)
        payload_dir = backup_dir / "payload"
        for entry in manifest.entries:
            payload = payload_dir / entry.payload_name
            _reject_redirected_backup_input(payload)
            if not payload.is_file():
                raise BackupError(f"backup payload missing: {entry.payload_name}")
            # AES-GCM ciphertext is exactly plaintext bytes + 16-byte tag.
            # Refuse truncation/oversizing before materializing a payload.
            if payload.stat().st_size != entry.size + _AESGCM_TAG_BYTES:
                raise BackupError(
                    f"backup encrypted payload size mismatch: {entry.logical_path}"
                )
            aad = f"{manifest.backup_id}:{entry.logical_path}".encode("utf-8")
            with payload.open("rb") as source:
                ciphertext = source.read(entry.size + _AESGCM_TAG_BYTES + 1)
            if len(ciphertext) != entry.size + _AESGCM_TAG_BYTES:
                raise BackupError(
                    f"backup encrypted payload size mismatch: {entry.logical_path}"
                )
            plaintext = self.cipher.decrypt(
                ciphertext,
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
        erasure_journal: Path | None = None,
    ) -> RestoreVerification:
        # A backup can predate a live deletion by years. No restore may
        # publish state without the operator-held current deletion journal,
        # which is intentionally not embedded in older encrypted snapshots.
        from sofia.memory.deletion_ledger import (
            MemoryDeletionLedger, MemoryErasureError,
        )
        if not isinstance(erasure_journal, Path) or not erasure_journal.is_absolute():
            raise BackupError(
                "current external erasure_journal is required before any restore"
            )
        deletion_ledger = MemoryDeletionLedger(erasure_journal, self.cipher)
        try:
            signed_deletions_before_restore = deletion_ledger.entries()
        except MemoryErasureError as exc:
            raise BackupError("authenticated deletion journal is unavailable") from exc
        manifest = self.verify(backup_dir)
        if not isinstance(target_state_path, Path):
            raise TypeError("target_state_path must be a Path")
        target_root = target_state_path.parent
        journal = erasure_journal.absolute()
        root = target_root.absolute()
        source_root = backup_dir.absolute()
        if (
            journal == target_state_path.absolute()
            or journal == root or root in journal.parents
            or journal == source_root or source_root in journal.parents
        ):
            raise BackupError(
                "erasure journal must be outside restored state and backup snapshots"
            )
        # Authenticate destination locality and every archived target
        # before staging any file, including protected identity assets.
        _reject_redirected_restore_path(target_state_path)
        for entry in manifest.entries:
            dest = (
                target_state_path if entry.logical_path == "sofia.db"
                else target_root / entry.logical_path
            )
            _reject_redirected_restore_path(dest)
        target_root.mkdir(parents=True, exist_ok=True)
        if not replace_existing:
            for entry in manifest.entries:
                destination = (
                    target_state_path if entry.logical_path == "sofia.db"
                    else target_root / entry.logical_path
                )
                # An absent SQLite file does not mean the rest of an
                # existing owner home is safe to replace. Never destroy
                # protected identity or asset files on a default restore.
                if destination.exists() or destination.is_symlink():
                    raise BackupError(
                        "restore bundle target exists; explicit "
                        "replace_existing required"
                    )

        with tempfile.TemporaryDirectory(
            prefix=".sofia-restore.",
            dir=target_root,
        ) as temp_dir:
            staging = Path(temp_dir)
            payload_dir = backup_dir / "payload"
            for entry in manifest.entries:
                payload = payload_dir / entry.payload_name
                # Revalidate on the second read after verify(). Restore
                # never follows a payload that changed into a symlink.
                _reject_redirected_backup_input(payload)
                if payload.stat().st_size != entry.size + _AESGCM_TAG_BYTES:
                    raise BackupError(
                        f"restore encrypted payload size mismatch: {entry.logical_path}"
                    )
                aad = f"{manifest.backup_id}:{entry.logical_path}".encode("utf-8")
                with payload.open("rb") as source:
                    ciphertext = source.read(entry.size + _AESGCM_TAG_BYTES + 1)
                if len(ciphertext) != entry.size + _AESGCM_TAG_BYTES:
                    raise BackupError(
                        f"restore encrypted payload size mismatch: {entry.logical_path}"
                    )
                plaintext = self.cipher.decrypt(
                    ciphertext,
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
            with closing(sqlite3.connect(staged_db)) as db:
                row = db.execute("PRAGMA integrity_check").fetchone()
                if row is None or row[0] != "ok":
                    raise BackupError("restored SQLite failed integrity_check")

            # Authenticate and reapply EVERY deletion instruction to the
            # staged database before any restored byte becomes active.
            # This physical replay removes copied source text too, and
            # fails closed if the journal is missing or scope conflicts.
            try:
                deletion_ledger.apply_to_sqlite(staged_db)
                deletion_ledger.verify_applied(staged_db)
            except (MemoryErasureError, sqlite3.DatabaseError) as exc:
                raise BackupError(
                    "restored state failed authenticated memory-erasure replay"
                ) from exc
            # Verify semantic protected state after candidate erasure.
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
                    if expected_hash.casefold() != loaded_constitution.content_hash.casefold():
                        raise BackupError(
                            "restored Constitution hash does not match protected digest"
                        )
            if identity.is_file():
                IdentityStore(
                    identity,
                    bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
                ).load()

            # The same independent journal lock serializes signed deletion
            # append and the final file-by-file restore publication. Without
            # it, a deletion can arrive after the last freshness read while
            # older plaintext is still being published to the restored home.
            with deletion_ledger._exclusive():
                # The external journal might have gained an operator-approved
                # deletion while an old multi-gigabyte snapshot was decrypting.
                # Fail closed rather than publishing a snapshot with stale
                # erasure replay. The operator may restart the restore.
                try:
                    if deletion_ledger.entries() != signed_deletions_before_restore:
                        raise BackupError(
                            "external erasure journal changed during restore; repeat replay"
                        )
                except MemoryErasureError as exc:
                    raise BackupError(
                        "external erasure journal unavailable before restore publication"
                    ) from exc
                published_directories: set[Path] = set()
                published_any = False
                try:
                    for source in sorted(staging.rglob("*")):
                        if not source.is_file():
                            continue
                        logical = source.relative_to(staging)
                        destination = (
                            target_state_path
                            if logical.as_posix() == "sofia.db"
                            else target_root / logical
                        )
                        _reject_redirected_restore_path(destination)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        _reject_redirected_restore_path(destination)
                        # Never open a predictable ".<name>.restore" alias for
                        # writing: an existing symlink there could escape the
                        # destination even though its final pathname was validated.
                        # mkstemp provides O_EXCL creation and a held regular-file
                        # descriptor under this approved destination directory.
                        descriptor, temporary_name = tempfile.mkstemp(
                            prefix=f".{destination.name}.restore-",
                            suffix=".tmp", dir=destination.parent,
                        )
                        temp_target = Path(temporary_name)
                        try:
                            with (
                                os.fdopen(descriptor, "wb") as restored_file,
                                source.open("rb") as original_file,
                            ):
                                shutil.copyfileobj(original_file, restored_file)
                                restored_file.flush()
                                os.fsync(restored_file.fileno())
                            # File bytes are already durable. A default restore
                            # now uses create-if-absent publication for EVERY
                            # protected asset, not only the SQLite database. The
                            # hard link and temporary file share a filesystem;
                            # an unsupported hard-link filesystem fails closed.
                            _reject_redirected_restore_path(destination)
                            if replace_existing:
                                os.replace(temp_target, destination)
                            else:
                                try:
                                    os.link(temp_target, destination)
                                except FileExistsError as exc:
                                    raise BackupError(
                                        "restore target appeared during publication; "
                                        "never overwrite without explicit replace_existing"
                                    ) from exc
                            published_any = True
                            published_directories.add(destination.parent)
                        finally:
                            temp_target.unlink(missing_ok=True)
                except Exception as exc:
                    # The bundle is not an atomic *group* publication. One
                    # or more destination entries may already be visible
                    # even though a later copy, validation or link failed.
                    # Preserve those entries for offline review; never claim
                    # that the failed restore left a clean empty target.
                    if isinstance(exc, RestorePublicationUncertain):
                        raise
                    if published_any:
                        raise RestorePublicationUncertain(
                            "restore published part of the protected bundle "
                            "before failing; quarantine target and require "
                            "independent offline review before any activation"
                        ) from exc
                    raise
                if sys.platform.startswith("linux"):
                    try:
                        _fsync_restored_linux_directories(published_directories)
                    except OSError as exc:
                        # Some names may already be visible. Do not claim success,
                        # automatically undo a partial restore, or overwrite it.
                        raise RestorePublicationUncertain(
                            "restored files were published but directory durability "
                            "is uncertain; inspect offline state before activation"
                        ) from exc

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
    # Retention is a destructive operation, not a backup verifier.
    # A redirected root can point at an unrelated host directory, and a
    # malicious/surprised archive link must not be recursively deleted.
    _reject_redirected_backup_input(root)
    if not root.exists():
        return ()
    if not root.is_dir():
        raise BackupError("backup retention root must be a real directory")
    candidates: list[Path] = []
    for path in root.iterdir():
        _reject_redirected_backup_input(path)
        if path.is_dir():
            manifest = path / "manifest.json"
            _reject_redirected_backup_input(manifest)
            if manifest.is_file():
                candidates.append(path)
    backups = sorted(
        candidates, key=lambda path: path.name, reverse=True,
    )
    expired = backups[keep:]
    # Preflight ALL selected directories before the first destructive step.
    # A symlink/junction embedded in one archive makes the entire rotation
    # fail closed rather than deleting a partial generation of backups.
    for path in expired:
        _reject_redirected_backup_input(path)
        for child in path.rglob("*"):
            _reject_redirected_backup_input(child)
    removed: list[Path] = []
    for path in expired:
        _reject_redirected_backup_input(path)
        shutil.rmtree(path)
        removed.append(path)
    return tuple(removed)
