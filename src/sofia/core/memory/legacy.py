"""Legacy and incompatible memory-state inspection and quarantine.

Inspection is read-only. Quarantine copies the original SQLite image and its
sidecars into a separate owner-private receipt directory; it never imports,
rewrites, deletes, or promotes legacy rows. A caller must explicitly re-review
surviving originals through the existing authenticated owner workflow.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3

from sofia.core.memory.access import (
    LegacyMemoryState,
    MemoryStateCorrupt,
    MemoryStateIncompatible,
)
from sofia.platform.state.canonical_sqlite import require_existing_sqlite
from sofia.platform.state.private_file import (
    atomic_write_private_text,
    ensure_owner_private_directory,
)
from sofia.platform.state.sqlite_uri import sqlite_file_uri


MEMORY_SCHEMA_VERSION = 1
_SUPPORTED_SCHEMA_TABLE = "core_memory_schema"

_REQUIRED_COLUMNS = {
    "memory_candidate": {
        "candidate_id", "content", "created_at", "status",
        "principal_id", "audience_id",
    },
    "memory_candidate_source": {
        "candidate_id", "ordinal", "message_id", "session_id",
        "role", "content", "created_at", "position",
    },
    "memory_candidate_validity": {
        "candidate_id", "expires_at", "reviewed_at", "reviewed_by", "reason",
    },
    "memory_candidate_source_review": {
        "candidate_id", "source_session_id", "principal_id",
        "audience_id", "audience_kind", "reviewed_at",
    },
}

_VALID_STATUSES = {"proposed", "promoted", "rejected", "revoked"}


class MemoryStateKind(str, Enum):
    EMPTY = "empty"
    CURRENT = "current"
    LEGACY_UNATTESTED = "legacy_unattested"
    LEGACY_SCHEMA = "legacy_schema"
    INCOMPATIBLE = "incompatible"
    CORRUPT = "corrupt"


@dataclass(frozen=True, slots=True)
class MemoryStateReport:
    kind: MemoryStateKind
    schema_version: int | None = None
    candidate_count: int = 0
    reviewed_count: int = 0

    @property
    def requires_quarantine(self) -> bool:
        return self.kind in {
            MemoryStateKind.LEGACY_UNATTESTED,
            MemoryStateKind.LEGACY_SCHEMA,
            MemoryStateKind.INCOMPATIBLE,
            MemoryStateKind.CORRUPT,
        }


@dataclass(frozen=True, slots=True)
class MemoryQuarantineReceipt:
    source_state_path: Path
    quarantine_path: Path
    sha256: str
    kind: MemoryStateKind
    created_at: datetime

    def as_dict(self) -> dict:
        return {
            "source_state_path": str(self.source_state_path),
            "quarantine_path": str(self.quarantine_path),
            "sha256": self.sha256,
            "kind": self.kind.value,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
        }


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


def inspect_memory_state(path: Path | str) -> MemoryStateReport:
    """Classify memory state without mutating it or reading row content."""
    target, _identity = require_existing_sqlite(path)
    try:
        with closing(sqlite3.connect(
            sqlite_file_uri(target, read_only=True), uri=True, timeout=5,
        )) as db:
            db.execute("PRAGMA query_only=ON")
            integrity = db.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                return MemoryStateReport(MemoryStateKind.CORRUPT)
            tables = _tables(db)
            if "memory_candidate" not in tables:
                return MemoryStateReport(MemoryStateKind.EMPTY)
            for table, required in _REQUIRED_COLUMNS.items():
                if table not in tables:
                    return MemoryStateReport(MemoryStateKind.LEGACY_SCHEMA)
                if not required.issubset(_columns(db, table)):
                    return MemoryStateReport(MemoryStateKind.LEGACY_SCHEMA)
            schema_version: int | None = None
            if _SUPPORTED_SCHEMA_TABLE in tables:
                row = db.execute(
                    "SELECT version FROM core_memory_schema WHERE singleton=1"
                ).fetchone()
                if row is None or type(row[0]) is not int:
                    return MemoryStateReport(MemoryStateKind.INCOMPATIBLE)
                schema_version = row[0]
                if schema_version > MEMORY_SCHEMA_VERSION:
                    return MemoryStateReport(
                        MemoryStateKind.INCOMPATIBLE, schema_version,
                    )
            statuses = {
                row[0] for row in db.execute(
                    "SELECT DISTINCT status FROM memory_candidate"
                )
            }
            if not statuses.issubset(_VALID_STATUSES):
                return MemoryStateReport(
                    MemoryStateKind.INCOMPATIBLE, schema_version,
                )
            candidate_count = int(db.execute(
                "SELECT COUNT(*) FROM memory_candidate"
            ).fetchone()[0])
            reviewed_count = int(db.execute(
                "SELECT COUNT(*) FROM memory_candidate_source_review"
            ).fetchone()[0])
            promoted = int(db.execute(
                "SELECT COUNT(*) FROM memory_candidate WHERE status='promoted'"
            ).fetchone()[0])
            kind = (
                MemoryStateKind.LEGACY_UNATTESTED
                if promoted > reviewed_count
                else MemoryStateKind.CURRENT
            )
            return MemoryStateReport(
                kind, schema_version, candidate_count, reviewed_count,
            )
    except (sqlite3.DatabaseError, OSError) as exc:
        raise MemoryStateCorrupt(
            "canonical memory state is truncated or unreadable"
        ) from exc


def require_selectable_memory_state(path: Path | str) -> MemoryStateReport:
    """Refuse incompatible state while allowing an empty canonical database."""
    report = inspect_memory_state(path)
    if report.kind is MemoryStateKind.LEGACY_SCHEMA:
        raise LegacyMemoryState(
            "legacy memory schema requires quarantine; automatic import is refused"
        )
    if report.kind is MemoryStateKind.INCOMPATIBLE:
        raise MemoryStateIncompatible(
            "canonical memory state uses an unsupported schema"
        )
    if report.kind is MemoryStateKind.CORRUPT:
        raise MemoryStateCorrupt(
            "canonical memory state is truncated or unreadable"
        )
    return report


def require_writable_memory_state(path: Path | str) -> MemoryStateReport:
    """Refuse legacy unattested rows for implicit import/mutation.

    Unattested rows remain readable through the explicit compatibility path
    and the opt-in V1 policy. A writer may not silently adopt them.
    """
    report = require_selectable_memory_state(path)
    if report.kind is MemoryStateKind.LEGACY_UNATTESTED:
        raise LegacyMemoryState(
            "legacy unattested memory requires quarantine and owner re-review"
        )
    return report


def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quarantine_memory_state(
    path: Path | str,
    *,
    quarantine_root: Path | str,
    now: datetime | None = None,
) -> MemoryQuarantineReceipt:
    """Copy incompatible state aside without importing or mutating it."""
    target, _identity = require_existing_sqlite(path)
    report = inspect_memory_state(target)
    if not report.requires_quarantine:
        raise ValueError("memory state is current and does not require quarantine")
    root = Path(quarantine_root)
    ensure_owner_private_directory(root)
    digest = _digest_file(target)
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stem = f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{digest[:12]}"
    destination = root / stem
    suffix = 0
    while destination.exists():
        suffix += 1
        destination = root / f"{stem}-{suffix}"
    destination.mkdir(mode=0o700)
    if os.name != "nt":
        destination.chmod(0o700)
    copied: list[str] = []

    def copy_private(source: Path, copied_to: Path) -> None:
        shutil.copyfile(source, copied_to)
        if os.name != "nt":
            copied_to.chmod(0o600)

    try:
        copy_private(target, destination / target.name)
        copied.append(target.name)
        for sidecar in ("-wal", "-shm", "-journal"):
            source = Path(str(target) + sidecar)
            if source.is_file() and not source.is_symlink():
                copy_private(source, destination / (target.name + sidecar))
                copied.append(target.name + sidecar)
        receipt = MemoryQuarantineReceipt(
            source_state_path=target,
            quarantine_path=destination,
            sha256=digest,
            kind=report.kind,
            created_at=moment,
        )
        document = {
            **receipt.as_dict(),
            "schema_version": report.schema_version,
            "candidate_count": report.candidate_count,
            "reviewed_count": report.reviewed_count,
            "copied_files": copied,
            "policy": "quarantine_only_no_import_no_promotion",
        }
        atomic_write_private_text(
            destination / "quarantine.json",
            json.dumps(document, indent=2, sort_keys=True) + "\n",
        )
        return receipt
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
