"""External, authenticated delete instructions for canonical memory candidates.

Option B: the live candidate and its copied source text are deleted now;
older encrypted snapshots expire under backup retention; the externally
held erasure journal MUST be replayed before restoring a snapshot.

The journal contains only stable candidate UUIDs and scoped ownership IDs,
never deleted memory text. It is NOT collected in backups of sofia.db. The
operator must preserve it across failure domains and validate its signed head.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Callable
from uuid import UUID

from sofia.platform.state.sqlite_uri import sqlite_file_uri

from sofia.ops.backup import BackupCipher


class MemoryErasureError(RuntimeError):
    """Fail closed: the erasure journal is missing, stale or unauthenticated."""


def _canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


class MemoryDeletionLedger:
    """Operator-protected authenticated journal OUTSIDE restored state homes."""

    def __init__(self, path: Path, cipher: BackupCipher) -> None:
        if not isinstance(path, Path) or not path.is_absolute():
            raise ValueError("absolute external memory deletion journal path required")
        if not isinstance(cipher, BackupCipher):
            raise TypeError("operator-held authenticated backup cipher required")
        self.path = path
        self.cipher = cipher

    def _check_path(self) -> None:
        for part in (self.path, *self.path.parents):
            if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
                raise MemoryErasureError("redirected deletion journal is forbidden")

    def initialize(self) -> None:
        """Explicit operator provisioning only; NEVER invoked by restore."""
        self._check_path()
        if self.path.exists():
            self.entries()  # existing journal must authenticate
            return
        if not self.path.parent.is_dir():
            raise FileNotFoundError("external journal parent must already exist")
        genesis = {
            "schema": "sofia.memory-deletion-v1", "sequence": 0,
            "previous_sha256": "0" * 64, "candidate_id": None,
            "principal_id": None, "audience_id": None,
            "authority_ref": None, "deleted_at": None,
        }
        first = dict(genesis)
        first["mac"] = self.cipher.manifest_mac(_canonical(genesis))
        try:
            descriptor = os.open(
                self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
            )
        except FileExistsError:
            self.entries()
            return
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical(first) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

    def entries(self) -> tuple[dict, ...]:
        """Authenticate the entire append chain BEFORE any erasure/recovery."""
        self._check_path()
        if not self.path.is_file():
            raise MemoryErasureError("external deletion journal is absent")
        if self.path.stat().st_size > 16 * 1024 * 1024:
            raise MemoryErasureError("bounded deletion journal size exceeded")
        previous = "0" * 64
        output = []
        with self.path.open("rb") as handle:
            for sequence, line in enumerate(handle):
                if not line.endswith(b"\n") or len(line) > 4096:
                    raise MemoryErasureError("truncated or unbounded journal record")
                try:
                    record = json.loads(line)
                    mac = record.pop("mac")
                    if (
                        record.get("schema") != "sofia.memory-deletion-v1"
                        or record.get("sequence") != sequence
                        or record.get("previous_sha256") != previous
                        or not isinstance(mac, str)
                        or not hmac.compare_digest(
                            mac, self.cipher.manifest_mac(_canonical(record)),
                        )
                    ):
                        raise ValueError("invalid erasure authentication")
                    if sequence:
                        UUID(record["candidate_id"])
                        if not all(isinstance(record.get(field), str)
                                   and record[field].strip()
                                   for field in (
                                       "principal_id", "audience_id",
                                       "authority_ref", "deleted_at",
                                   )):
                            raise ValueError("incomplete scoped erasure instruction")
                        datetime.fromisoformat(record["deleted_at"])
                    else:
                        if record.get("candidate_id") is not None:
                            raise ValueError("journal genesis was replaced")
                except (ValueError, TypeError, KeyError) as exc:
                    raise MemoryErasureError(
                        "external deletion journal authentication failed"
                    ) from exc
                previous = sha256(_canonical({**record, "mac": mac})).hexdigest()
                if sequence:
                    output.append(record)
        if previous == "0" * 64:
            raise MemoryErasureError("deletion journal lacks authenticated genesis")
        return tuple(output)

    @contextmanager
    def _exclusive(self):
        """Cross-process lock protecting the journal's HMAC chain append."""
        self._check_path()
        path = self.path.with_suffix(self.path.suffix + ".lock")
        for component in (path, *path.parents):
            if component.is_symlink() or getattr(
                component, "is_junction", lambda: False
            )():
                raise MemoryErasureError("redirected journal lock is forbidden")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            opened = os.fstat(descriptor)
            named = path.stat()
            if not stat.S_ISREG(opened.st_mode) or (
                opened.st_dev, opened.st_ino
            ) != (named.st_dev, named.st_ino):
                raise MemoryErasureError("journal lock changed during acquisition")
            if os.name == "nt":
                import msvcrt
                # msvcrt locks need one addressable byte on the file.
                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, bytes((0,)))
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def request(
        self, *, candidate_id: UUID, principal_id: str, audience_id: str,
        authority_ref: str, at: datetime,
        approve: Callable[[str, str, str, str], bool],
    ) -> bool:
        """Durably journal an independently approved erasure BEFORE deletion.

        A model's text is not an approval; caller provides trusted authority.
        Returns False when the same scoped candidate is already journaled.
        """
        if not isinstance(candidate_id, UUID):
            raise TypeError("original memory UUID required")
        if (
            not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None or not callable(approve)
            or not all(isinstance(v, str) and v.strip() and len(v) <= 200
                       for v in (principal_id, audience_id, authority_ref))
        ):
            raise ValueError("trusted scope, authority reference and time required")
        if approve(str(candidate_id), principal_id, audience_id, authority_ref) is not True:
            raise PermissionError("explicit memory erasure authority unavailable")
        with self._exclusive():
            entries = self.entries()
            for record in entries:
                if record["candidate_id"] == str(candidate_id):
                    if (
                        record["principal_id"] != principal_id
                        or record["audience_id"] != audience_id
                    ):
                        raise MemoryErasureError("candidate deletion scope conflict")
                    return False
            previous = "0" * 64
            with self.path.open("rb") as reader:
                for line in reader:
                    previous = sha256(line.rstrip(b"\n")).hexdigest()
            record = {
                "schema": "sofia.memory-deletion-v1",
                "sequence": len(entries) + 1,
                "previous_sha256": previous,
                "candidate_id": str(candidate_id),
                "principal_id": principal_id,
                "audience_id": audience_id,
                "authority_ref": authority_ref,
                "deleted_at": at.astimezone(timezone.utc).isoformat(),
            }
            encoded = dict(record)
            encoded["mac"] = self.cipher.manifest_mac(_canonical(record))
            payload = _canonical(encoded) + b"\n"
            if self.path.stat().st_size + len(payload) > 16 * 1024 * 1024:
                raise MemoryErasureError("bounded deletion journal is full")
            # A writer process needs an external single-writer lock/lease for
            # this separate failure-domain artifact, just as sofia.db does.
            # The consent witness checked before acquiring that lock may be
            # revoked during the lock wait or HMAC scan. Recheck it inside the
            # lock immediately before publishing a signed tombstone.
            if approve(
                str(candidate_id), principal_id, audience_id, authority_ref,
            ) is not True:
                raise PermissionError(
                    "independent memory erasure approval expired before append"
                )
            self._check_path()
            flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_CLOEXEC", 0)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.path, flags)
            try:
                opened = os.fstat(descriptor)
                named = self.path.stat()
                if not stat.S_ISREG(opened.st_mode) or (
                    opened.st_dev, opened.st_ino
                ) != (named.st_dev, named.st_ino):
                    raise MemoryErasureError(
                        "authenticated journal changed before append"
                    )
                with os.fdopen(descriptor, "ab") as handle:
                    descriptor = -1
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            return True

    def verify_applied(self, state_path: Path) -> dict[str, int]:
        """Read-only witness that signed deletions propagated into all owners.

        Verification uses exact candidate UUIDs, not a lexical memory search.
        A missing/invalid external journal or a surviving derived row fails
        closed before restored state can be published.
        """
        entries = self.entries()
        if (
            not isinstance(state_path, Path)
            or not state_path.is_file()
            or state_path.is_symlink()
        ):
            raise MemoryErasureError("source state unavailable for erasure verification")
        tables_to_check = (
            ("memory_candidate", "candidate_id"),
            ("memory_candidate_source", "candidate_id"),
            ("memory_candidate_source_review", "candidate_id"),
            ("memory_candidate_validity", "candidate_id"),
            ("memory_candidate_validity_event", "candidate_id"),
            ("memory_candidate_correction", "old_candidate_id"),
            ("memory_candidate_correction", "new_candidate_id"),
            ("neuro_association_weight", "candidate_id"),
            ("neuro_association_event", "candidate_id"),
        )
        examined = 0
        with closing(sqlite3.connect(
            sqlite_file_uri(state_path, read_only=True), uri=True, timeout=10,
        )) as db:
            present = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if entries and (
                "memory_candidate" not in present
                or "memory_deletion_guard" not in present
            ):
                raise MemoryErasureError("restore lacks active deletion guard schema")
            for record in entries:
                candidate_id = record["candidate_id"]
                guarded = db.execute(
                    "SELECT principal_id,audience_id FROM memory_deletion_guard "
                    "WHERE candidate_id=?", (candidate_id,),
                ).fetchone()
                if guarded != (
                    record["principal_id"], record["audience_id"],
                ):
                    raise MemoryErasureError(
                        "active deletion guard differs from original signed scope"
                    )
                for table, column in tables_to_check:
                    if table not in present:
                        continue
                    if db.execute(
                        f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1",
                        (candidate_id,),
                    ).fetchone() is not None:
                        raise MemoryErasureError(
                            "forgotten candidate or derived evidence is still readable"
                        )
                examined += 1
        return {"signed_deletions": len(entries), "verified_absent": examined}

    def apply_to_sqlite(self, state_path: Path) -> int:
        """Replay a fixed signed journal epoch under its append-owner lock.

        The external journal is the deletion source of truth. Another process
        must not append a new approved erasure between our authenticated scan
        and the canonical SQLite replay commit. This is a local cooperating
        lock, not a global cross-host lease for the external journal.
        """
        with self._exclusive():
            return self._apply_to_sqlite_under_lock(state_path)

    def _apply_to_sqlite_under_lock(self, state_path: Path) -> int:
        """Physical, idempotent removal of candidates and copied provenance.

        This is deliberately narrow: deleting a candidate does not delete
        independently stored conversation messages, files, or all lexical
        occurrences elsewhere. Broader erasure needs separately scoped IDs.
        """
        entries = self.entries()
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("existing target state required")
        if state_path.is_symlink():
            raise MemoryErasureError("redirected state may not be erased")
        removed = 0
        with closing(sqlite3.connect(state_path, timeout=10)) as db:
            # SQLite secure_delete overwrites deleted cell content in its
            # working pages; a live runtime must be stopped so no other
            # connection retains old plaintext or unread WAL snapshots.
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "memory_candidate" not in tables:
                if entries:
                    raise MemoryErasureError(
                        "restored database lacks required memory candidate schema"
                    )
                return 0
            # A signed external erasure instruction is authoritative. The
            # local guard is a derived index that prevents later importers
            # from reintroducing an identical candidate UUID between
            # journal replays. The guard contains no forgotten text.
            db.execute("""
                CREATE TABLE IF NOT EXISTS memory_deletion_guard (
                    candidate_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_deletion_reject_insert
                BEFORE INSERT ON memory_candidate
                WHEN EXISTS(
                    SELECT 1 FROM memory_deletion_guard AS g
                    WHERE g.candidate_id=NEW.candidate_id
                )
                BEGIN SELECT RAISE(ABORT,'candidate was deleted'); END
            """)
            db.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_deletion_reject_id_update
                BEFORE UPDATE OF candidate_id ON memory_candidate
                WHEN EXISTS(
                    SELECT 1 FROM memory_deletion_guard AS g
                    WHERE g.candidate_id=NEW.candidate_id
                )
                BEGIN SELECT RAISE(ABORT,'candidate was deleted'); END
            """)
            for record in entries:
                prior = db.execute(
                    "SELECT principal_id,audience_id FROM memory_deletion_guard "
                    "WHERE candidate_id=?", (record["candidate_id"],),
                ).fetchone()
                if prior is not None and prior != (
                    record["principal_id"], record["audience_id"],
                ):
                    raise MemoryErasureError(
                        "derived deletion guard conflicts with signed original scope"
                    )
                db.execute(
                    "INSERT OR IGNORE INTO memory_deletion_guard VALUES(?,?,?)",
                    (
                        record["candidate_id"], record["principal_id"],
                        record["audience_id"],
                    ),
                )
            for record in entries:
                candidate_id = record["candidate_id"]
                match = db.execute(
                    "SELECT principal_id,audience_id FROM memory_candidate "
                    "WHERE candidate_id=?", (candidate_id,),
                ).fetchone()
                if match is not None and match != (
                    record["principal_id"], record["audience_id"],
                ):
                    raise MemoryErasureError(
                        "candidate ID is present with conflicting private scope"
                    )
                # Continue deleting derived copies even when the primary
                # candidate is already gone. A crashed/stale importer can
                # have left an orphan review or NEURO row behind, and every
                # restore replay must heal it idempotently.
                for table, column in (
                    ("memory_candidate_correction", "new_candidate_id"),
                    ("memory_candidate_correction", "old_candidate_id"),
                    ("memory_candidate_validity_event", "candidate_id"),
                    ("memory_candidate_validity", "candidate_id"),
                    ("memory_candidate_source_review", "candidate_id"),
                    ("memory_candidate_source", "candidate_id"),
                    # NEURO association snapshots and exact teaching receipts
                    # are derived from this candidate and must not survive.
                    # Existing NEURO triggers may not be installed on an
                    # older restored backup, so clean these explicitly too.
                    ("neuro_association_weight", "candidate_id"),
                    ("neuro_association_event", "candidate_id"),
                ):
                    if table in tables:
                        db.execute(
                            f"DELETE FROM {table} WHERE {column}=?",
                            (candidate_id,),
                        )
                if match is not None:
                    db.execute(
                        "DELETE FROM memory_candidate WHERE candidate_id=?",
                        (candidate_id,),
                    )
                    removed += 1
            violations = db.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise MemoryErasureError("foreign key violation after replay")
            db.commit()  # publish the deletion before releasing the database
        return removed
