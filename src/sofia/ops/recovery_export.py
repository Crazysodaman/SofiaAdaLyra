"""Operator-approved, read-only portable original conversation export.

Consumes a *restored and verified* canonical SQLite snapshot. It does not
run Sofía, replay memories, call an LLM, write source rows or authorize any
other device/channel to display the output. JSONL is sensitive plaintext.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

from sofia.ops.state_mobility import _filesystem_kind, _unsafe_ancestor


_EXPORT_SCHEMA = "sofia.portable-conversations.v1"
_BATCH = 256


@dataclass(frozen=True, slots=True)
class PortableConversationExport:
    destination: Path
    message_count: int
    thread_count: int
    link_count: int
    content_sha256: str
    schema: str = _EXPORT_SCHEMA


def _append(output, digest, record: dict[str, object]) -> None:
    line = (
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    output.write(line)
    digest.update(line)


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def export_portable_conversations(
    *, state_path: Path, destination: Path,
    approve_sensitive_plaintext: bool,
) -> PortableConversationExport:
    """Export exact original source bytes and audience-tagged thread links.

    The caller must have already independently verified the encrypted backup
    and restored its SQLite snapshot into a disposable offline directory.
    The operator must deliberately accept that the result includes private
    and potentially adult original conversation text from *all* audiences.
    It is NOT authorized as a cross-channel messaging or retrieval API.
    """
    if approve_sensitive_plaintext is not True:
        raise PermissionError("explicit plaintext conversation export approval required")
    if not isinstance(state_path, Path) or not isinstance(destination, Path):
        raise TypeError("source and output must be Paths")
    if (
        not state_path.is_absolute() or not destination.is_absolute()
        or destination.suffix.lower() != ".jsonl"
    ):
        raise ValueError("absolute JSONL output and source paths required")
    if ".." in state_path.parts or ".." in destination.parts:
        raise ValueError("parent path traversal is not allowed")
    if not state_path.is_file():
        raise FileNotFoundError("verified offline SQLite snapshot is missing")
    if _unsafe_ancestor(state_path) or _unsafe_ancestor(destination):
        raise PermissionError("recovery paths must not follow symlinks or junctions")
    if (
        destination == state_path
        or state_path.parent == destination.parent
        or state_path.parent in destination.parents
    ):
        raise PermissionError("portable plaintext may not enter canonical state home")
    if not destination.parent.is_dir():
        raise FileNotFoundError("explicit plaintext destination directory missing")
    if _filesystem_kind(destination) != "local":
        raise PermissionError("plaintext recovery output requires proven local storage")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("portable conversation export must not overwrite a file")

    # Read-only snapshot, no auto-creation or implicit schema bootstrap.
    with closing(sqlite3.connect(
        state_path.as_uri() + "?mode=ro", uri=True, timeout=5.0,
    )) as db:
        db.row_factory = sqlite3.Row
        if not _has_table(db, "conversation_messages"):
            raise ValueError("snapshot lacks original conversation source table")
        if not _has_table(db, "social_session_principal"):
            raise ValueError("snapshot lacks authenticated audience-binding table")
        has_threads = _has_table(db, "lifelong_thread")
        has_links = _has_table(db, "lifelong_thread_event")
        if has_links and not has_threads:
            raise ValueError("thread links exist without canonical thread catalog")

        # O_EXCL is the final race-free no-overwrite publication gate for the
        # output file. Mode 0600 avoids world-readable offline chat on Unix.
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        digest = sha256()
        messages = threads = links = 0
        try:
            with os.fdopen(fd, "wb") as output:
                _append(output, digest, {
                    "record_type": "header", "schema": _EXPORT_SCHEMA,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "privacy": "ALL_AUDIENCES_SENSITIVE_PLAINTEXT",
                    "authority": "offline_operator_export_not_a_channel_grant",
                    "source": "verified_offline_canonical_sqlite",
                })
                after = 0
                while True:
                    rows = db.execute(
                        "SELECT m.rowid,m.id,m.session_id,m.role,m.content,"
                        "m.created_at,s.principal_id,s.audience_id,s.audience_kind "
                        "FROM conversation_messages AS m "
                        "LEFT JOIN social_session_principal AS s "
                        "ON s.session_id=m.session_id "
                        "WHERE m.rowid>? ORDER BY m.rowid LIMIT ?",
                        (after, _BATCH),
                    ).fetchall()
                    if not rows:
                        break
                    for row in rows:
                        _append(output, digest, {
                            "record_type": "original_message",
                            "message_id": row["id"],
                            "session_id": row["session_id"],
                            "role": row["role"], "content": row["content"],
                            "created_at": row["created_at"],
                            "binding": (
                                "currently_bound"
                                if row["principal_id"] is not None
                                else "unbound_not_authorized"
                            ),
                            "principal_id": row["principal_id"],
                            "audience_id": row["audience_id"],
                            "audience_kind": row["audience_kind"],
                        })
                        messages += 1
                    after = int(rows[-1]["rowid"])

                if has_threads:
                    after = ""
                    while True:
                        rows = db.execute(
                            "SELECT thread_id,owner_principal_id,kind,name,"
                            "created_at FROM lifelong_thread "
                            "WHERE thread_id>? ORDER BY thread_id LIMIT ?",
                            (after, _BATCH),
                        ).fetchall()
                        if not rows:
                            break
                        for row in rows:
                            _append(output, digest, {
                                "record_type": "thread",
                                **dict(row),
                                "access": "catalog_not_a_cross_channel_grant",
                            })
                            threads += 1
                        after = rows[-1]["thread_id"]

                if has_links:
                    # Links remain separate provenance references; never
                    # reconstruct a transcript by trusting stale indexes.
                    after = 0
                    while True:
                        rows = db.execute(
                            "SELECT e.rowid,e.thread_id,e.source_message_id,"
                            "e.source_session_id,e.source_audience_id,"
                            "e.visibility,e.linked_at,"
                            "m.id AS current_source_id,"
                            "s.principal_id AS current_principal_id,"
                            "s.audience_id AS current_audience_id,"
                            "s.audience_kind AS current_audience_kind "
                            "FROM lifelong_thread_event AS e "
                            "LEFT JOIN conversation_messages AS m "
                            "ON m.id=e.source_message_id "
                            "AND m.session_id=e.source_session_id "
                            "LEFT JOIN social_session_principal AS s "
                            "ON s.session_id=e.source_session_id "
                            "WHERE e.rowid>? ORDER BY e.rowid LIMIT ?",
                            (after, _BATCH),
                        ).fetchall()
                        if not rows:
                            break
                        for row in rows:
                            # A missing/rebound original stays explicitly
                            # marked for a human; never infer restored access.
                            _append(output, digest, {
                                "record_type": "thread_source_link",
                                "thread_id": row["thread_id"],
                                "source_message_id": row["source_message_id"],
                                "source_session_id": row["source_session_id"],
                                "source_audience_id": row["source_audience_id"],
                                "visibility": row["visibility"],
                                "linked_at": row["linked_at"],
                                "current_original_available": (
                                    row["current_source_id"] is not None
                                ),
                                "current_source_audience_matches": (
                                    row["current_source_id"] is not None
                                    and row["current_audience_id"]
                                    == row["source_audience_id"]
                                ),
                                "access": "reference_only_not_an_authorization",
                            })
                            links += 1
                        after = int(rows[-1]["rowid"])
                content_hash = digest.hexdigest()
                # Footer covers all preceding exact JSONL lines, not a claim
                # of signature or authorization; source backups remain
                # cryptographically authenticated by BackupEngine.
                footer = {
                    "record_type": "footer", "schema": _EXPORT_SCHEMA,
                    "original_message_count": messages,
                    "thread_count": threads,
                    "thread_source_link_count": links,
                    "preceding_lines_sha256": content_hash,
                }
                output.write((
                    json.dumps(
                        footer, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":"),
                    ) + "\n"
                ).encode("utf-8"))
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            # A partial plaintext transcript must not be mistaken for a
            # complete validated recovery export.
            destination.unlink(missing_ok=True)
            raise
    return PortableConversationExport(
        destination=destination, message_count=messages,
        thread_count=threads, link_count=links,
        content_sha256=content_hash,
    )
