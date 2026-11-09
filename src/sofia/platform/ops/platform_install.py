"""Hash-pinned cross-platform install, cache, recovery, and rollback contracts.

This module never decides authority.  A caller must supply a plan produced by
the existing Fleet bootstrap policy and an independently trusted installer.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import os
import re
import tempfile
import sqlite3
from typing import Protocol

from .bootstrap import InstallAuthority
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
    ensure_owner_private_directory, restrict_new_owner_private_path,
)
from sofia.platform.run.process_lock import StateProcessLock


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class PlatformKind(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"


class InstallOperation(str, Enum):
    INSTALL = "install"
    UPDATE = "update"
    REPAIR = "repair"
    ROLLBACK = "rollback"


class InstallOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True, slots=True)
class PlatformArtifact:
    artifact_id: str
    version: str
    platform: PlatformKind
    architecture: str
    sha256: str
    signer_key_id: str
    signature_verified: bool
    source: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.artifact_id, "artifact_id"), (self.version, "version"),
            (self.architecture, "architecture"), (self.signer_key_id, "signer_key_id"),
            (self.source, "source"),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError(f"{label} must be bounded text")
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("artifact requires lowercase SHA-256")
        if self.signature_verified is not True:
            raise ValueError("platform artifact requires verified signature evidence")


@dataclass(frozen=True, slots=True)
class PlatformInstallPlan:
    plan_id: str
    host_id: str
    artifact: PlatformArtifact
    operation: InstallOperation
    authority: InstallAuthority
    approval_id: str | None
    previous_version: str | None
    requested_at: datetime

    def __post_init__(self) -> None:
        if _ID.fullmatch(self.plan_id) is None or _ID.fullmatch(self.host_id) is None:
            raise ValueError("plan and host IDs must be canonical")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        if self.authority is InstallAuthority.NONE:
            raise PermissionError("platform installation requires explicit authority")
        if self.authority is InstallAuthority.OPERATOR_APPROVED and not self.approval_id:
            raise PermissionError("operator-approved installation requires approval_id")
        if self.operation is InstallOperation.ROLLBACK and not self.previous_version:
            raise ValueError("rollback requires an exact previous version")


@dataclass(frozen=True, slots=True)
class PlatformInstallReceipt:
    receipt_id: str
    plan_id: str
    host_id: str
    artifact_id: str
    version: str
    operation: InstallOperation
    outcome: InstallOutcome
    artifact_sha256: str
    signature_verified: bool
    health_verified: bool
    rollback_version: str | None
    started_at: datetime
    completed_at: datetime
    detail: str = ""

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("receipt timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if _SHA256.fullmatch(self.artifact_sha256) is None:
            raise ValueError("receipt requires artifact SHA-256")
        if self.outcome is InstallOutcome.SUCCEEDED and not (
            self.signature_verified and self.health_verified
        ):
            raise ValueError("successful install requires signature and health verification")


class TrustedPlatformInstaller(Protocol):
    def execute(self, plan: PlatformInstallPlan, artifact_path: Path) -> PlatformInstallReceipt: ...


def _same_cache_inode(before, after) -> bool:
    """Exact regular-file identity, including observed content mutation."""
    return (stat.S_ISREG(after.st_mode) and after.st_nlink == 1
            and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns))


class OfflineArtifactCache:
    """Managed content-addressed cache; importing always rechecks the digest."""

    def __init__(self, root: Path | str, *, max_bytes: int = 4 * 1024**3) -> None:
        self.root = Path(root).absolute()
        self.max_bytes = max_bytes
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        ensure_owner_private_directory(self.root)

    def _check_root(self):
        assert_no_redirected_components(self.root, include_leaf=True)
        assert_owner_private_path(self.root, directory=True)

    @staticmethod
    def _snapshot(path, *, include_data=False):
        path = Path(path).absolute()
        assert_no_redirected_components(path, include_leaf=True)
        return read_artifact_file(path, path.stat(follow_symlinks=False).st_size,
            include_data=include_data)

    @staticmethod
    def digest(path: Path) -> str:
        """Stream the whole immutable object without materializing its bytes.

        This remains compatible with small-artifact callers while allowing
        D028 signed parent objects >512MiB. Source path, inode, size, mtime
        and link count must remain unchanged through the verification read.
        """
        path = Path(path).absolute()
        assert_no_redirected_components(path, include_leaf=True)
        before = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(before.st_mode)
                or not 0 <= before.st_size <= 8 * 1024**3
                or before.st_nlink != 1):
            raise PermissionError("unsafe or unbounded cache digest source")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        digest = sha256()
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if not _same_cache_inode(before, opened):
                raise PermissionError("artifact inode changed before digest")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                remaining = before.st_size
                while remaining:
                    block = handle.read(min(65536, remaining))
                    if not block:
                        raise PermissionError("cache object truncated during digest")
                    digest.update(block)
                    remaining -= len(block)
                if handle.read(1):
                    raise PermissionError("cache object grew during digest")
            after = os.fstat(fd)
            final = path.stat(follow_symlinks=False)
            if (not _same_cache_inode(before, after)
                    or not _same_cache_inode(after, final)):
                raise PermissionError("cache object mutated during digest")
        finally:
            os.close(fd)
        return digest.hexdigest()

    def import_artifact(self, artifact: PlatformArtifact, source: Path | str) -> Path:
        """Bounded streaming import into the sole canonical B1 CAS.

        Exact publisher verification and owner SAFE admission remain the
        responsibility of the caller; this is NOT a new install authority.
        Copies in <=64KiB blocks, verifying source inode+mtime and final
        immutable SHA-256 before atomic no-replace publication.
        """
        if not isinstance(artifact, PlatformArtifact):
            raise TypeError("typed Platform artifact required")
        self._check_root()
        source_path = Path(source).absolute()
        assert_no_redirected_components(source_path, include_leaf=True)
        before = source_path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or not 1 <= before.st_size <= min(self.max_bytes, 8 * 1024**3)):
            if before.st_size > self.max_bytes:
                raise RuntimeError("offline artifact cache resource limit exceeded")
            raise PermissionError("unsafe or unbounded source artifact")
        lock = StateProcessLock(
            self.root / "cache", resource="platform-cache",
            lock_directory=self.root,
        )
        with lock:
            self._check_root()
            destination = self.root / artifact.sha256
            assert_no_redirected_components(destination, include_leaf=True)
            current_size = 0
            for item in self.root.iterdir():
                if item == lock.path:
                    continue
                assert_no_redirected_components(item, include_leaf=True)
                details = item.lstat()
                if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                    raise RuntimeError("offline artifact cache contains an unexpected entry")
                current_size += details.st_size
                if current_size > self.max_bytes:
                    raise RuntimeError("offline artifact cache resource limit exceeded")
            if current_size + before.st_size > self.max_bytes and not destination.exists():
                raise RuntimeError("offline artifact cache resource limit exceeded")
            descriptor, name = tempfile.mkstemp(prefix=".artifact-", dir=self.root)
            temporary = Path(name)
            descriptor_open = True
            try:
                restrict_new_owner_private_path(temporary, directory=False)
                digest = sha256()
                flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
                src_fd = os.open(source_path, flags)
                try:
                    opened = os.fstat(src_fd)
                    if not _same_cache_inode(before, opened):
                        raise PermissionError("source artifact substituted during import")
                    with os.fdopen(src_fd, "rb", closefd=False) as reader:
                        with os.fdopen(descriptor, "wb", closefd=False) as writer:
                            remaining = before.st_size
                            while remaining:
                                block = reader.read(min(65536, remaining))
                                if not block:
                                    raise PermissionError("source artifact truncated during import")
                                writer.write(block)
                                digest.update(block)
                                remaining -= len(block)
                            if reader.read(1):
                                raise PermissionError("source artifact grew during import")
                            writer.flush()
                            os.fsync(writer.fileno())
                    after = os.fstat(src_fd)
                    final = source_path.stat(follow_symlinks=False)
                    if (not _same_cache_inode(before, after)
                            or not _same_cache_inode(after, final)):
                        raise PermissionError("source artifact mutated during import")
                finally:
                    os.close(src_fd)
                    os.close(descriptor)
                    descriptor_open = False
                if digest.hexdigest() != artifact.sha256:
                    raise ValueError("artifact bytes do not match approved SHA-256")
                if self.digest(temporary) != artifact.sha256:
                    raise RuntimeError("cached artifact failed post-copy verification")
                self._check_root()
                if destination.exists() or destination.is_symlink():
                    return self.resolve(artifact)
                # Link only after complete source+temporary digest verification.
                # The final CAS must have exactly ONE name before resolve():
                # digest() explicitly refuses externally hardlinked artifacts.
                os.link(temporary, destination, follow_symlinks=False)
                try:
                    temporary.unlink()
                    if os.name != "nt":
                        directory = os.open(
                            self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                        )
                        try:
                            os.fsync(directory)
                        finally:
                            os.close(directory)
                    return self.resolve(artifact)
                except BaseException:
                    # A failed publish, durability barrier or resolve never
                    # leaves a silently accepted new CAS object behind.
                    destination.unlink(missing_ok=True)
                    raise
            finally:
                if descriptor_open:
                    os.close(descriptor)
                temporary.unlink(missing_ok=True)

    def resolve(self, artifact: PlatformArtifact) -> Path:
        if not isinstance(artifact, PlatformArtifact):
            raise TypeError("typed Platform artifact required")
        self._check_root()
        path = self.root / artifact.sha256
        if self.digest(path) != artifact.sha256:
            raise FileNotFoundError("approved artifact is absent or corrupt in offline cache")
        return path


class PlatformInstallStore:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS ops_platform_install_receipt (
                    receipt_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL UNIQUE,
                    host_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
                    version TEXT NOT NULL, operation TEXT NOT NULL,
                    outcome TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
                    signature_verified INTEGER NOT NULL,
                    health_verified INTEGER NOT NULL, rollback_version TEXT,
                    started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def record(self, receipt: PlatformInstallReceipt) -> None:
        if not isinstance(receipt, PlatformInstallReceipt):
            raise TypeError("PlatformInstallReceipt required")
        with closing(self._connect()) as db, db:
            row = db.execute(
                "SELECT * FROM ops_platform_install_receipt WHERE plan_id=?",
                (receipt.plan_id,),
            ).fetchone()
            payload = (
                receipt.receipt_id, receipt.plan_id, receipt.host_id,
                receipt.artifact_id, receipt.version, receipt.operation.value,
                receipt.outcome.value, receipt.artifact_sha256,
                int(receipt.signature_verified), int(receipt.health_verified),
                receipt.rollback_version,
                receipt.started_at.astimezone(timezone.utc).isoformat(),
                receipt.completed_at.astimezone(timezone.utc).isoformat(),
                receipt.detail[:2000],
            )
            if row is None:
                db.execute(
                    "INSERT INTO ops_platform_install_receipt VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    payload,
                )
            elif tuple(row) != payload:
                raise ValueError("install plan already has a different receipt")

    def for_plan(self, plan_id: str) -> PlatformInstallReceipt | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM ops_platform_install_receipt WHERE plan_id=?", (plan_id,)
            ).fetchone()
        if row is None:
            return None
        return PlatformInstallReceipt(
            receipt_id=row["receipt_id"], plan_id=row["plan_id"],
            host_id=row["host_id"], artifact_id=row["artifact_id"],
            version=row["version"], operation=InstallOperation(row["operation"]),
            outcome=InstallOutcome(row["outcome"]),
            artifact_sha256=row["artifact_sha256"],
            signature_verified=bool(row["signature_verified"]),
            health_verified=bool(row["health_verified"]),
            rollback_version=row["rollback_version"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]),
            detail=row["detail"],
        )


class PlatformInstallCoordinator:
    def __init__(self, cache: OfflineArtifactCache, store: PlatformInstallStore) -> None:
        self.cache, self.store = cache, store

    def execute(
        self, plan: PlatformInstallPlan, installer: TrustedPlatformInstaller,
    ) -> PlatformInstallReceipt:
        if not isinstance(plan, PlatformInstallPlan):
            raise TypeError("PlatformInstallPlan required")
        existing = self.store.for_plan(plan.plan_id)
        if existing is not None:
            return existing
        artifact_path = self.cache.resolve(plan.artifact)
        receipt = installer.execute(plan, artifact_path)
        if not isinstance(receipt, PlatformInstallReceipt):
            raise TypeError("installer must return PlatformInstallReceipt")
        if (
            receipt.plan_id != plan.plan_id
            or receipt.host_id != plan.host_id
            or receipt.artifact_id != plan.artifact.artifact_id
            or receipt.version != plan.artifact.version
            or receipt.artifact_sha256 != plan.artifact.sha256
            or receipt.operation is not plan.operation
        ):
            raise RuntimeError("installer receipt does not match the authorized plan")
        self.store.record(receipt)
        return receipt


@dataclass(frozen=True, slots=True)
class RecoveryBundle:
    platform: PlatformKind
    python_filename: str
    python_sha256: str
    sofia_filename: str
    sofia_sha256: str

    def __post_init__(self) -> None:
        for name in (self.python_filename, self.sofia_filename):
            if not name or Path(name).name != name or any(c in name for c in "\r\n\x00"):
                raise ValueError("recovery filenames must be safe basenames")
        if _SHA256.fullmatch(self.python_sha256) is None or _SHA256.fullmatch(
            self.sofia_sha256
        ) is None:
            raise ValueError("recovery artifacts require SHA-256")

    def render(self) -> str:
        """Return a no-network script that verifies pre-staged recovery bytes."""
        if self.platform is PlatformKind.LINUX:
            return f'''#!/bin/sh
set -eu
ROOT="${{1:?installation root required}}"
STAGE="${{2:?offline stage required}}"
printf '%s  %s\\n' '{self.python_sha256}' "$STAGE/{self.python_filename}" | sha256sum -c -
printf '%s  %s\\n' '{self.sofia_sha256}' "$STAGE/{self.sofia_filename}" | sha256sum -c -
mkdir -p "$ROOT/releases"
cp "$STAGE/{self.python_filename}" "$ROOT/releases/{self.python_filename}"
cp "$STAGE/{self.sofia_filename}" "$ROOT/releases/{self.sofia_filename}"
printf '%s\\n' 'verified recovery artifacts staged; platform installer must activate atomically'
'''
        return f'''param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Stage)
$ErrorActionPreference = "Stop"
$Python = Join-Path $Stage "{self.python_filename}"
$Sofia = Join-Path $Stage "{self.sofia_filename}"
if ((Get-FileHash -Algorithm SHA256 $Python).Hash.ToLowerInvariant() -ne "{self.python_sha256}") {{ throw "Python recovery artifact hash mismatch" }}
if ((Get-FileHash -Algorithm SHA256 $Sofia).Hash.ToLowerInvariant() -ne "{self.sofia_sha256}") {{ throw "Sofia recovery artifact hash mismatch" }}
New-Item -ItemType Directory -Force (Join-Path $Root "releases") | Out-Null
Copy-Item $Python (Join-Path $Root "releases\\{self.python_filename}") -Force
Copy-Item $Sofia (Join-Path $Root "releases\\{self.sofia_filename}") -Force
Write-Output "verified recovery artifacts staged; platform installer must activate atomically"
'''
