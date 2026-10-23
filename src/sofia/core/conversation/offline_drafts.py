"""Device-local unsent text drafts, not a second Sofia state authority.

Works without network; cannot execute tools, issue SAFE grants, fabricate
messages, or mark receipt success. Synchronization imports require a separate
authenticated service and host-issued acknowledgement.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3
from uuid import uuid4
from typing import Callable


@dataclass(frozen=True, slots=True)
class OfflineDraft:
    draft_id: str
    device_id: str
    principal_id: str
    audience_id: str
    text: str
    digest: str
    composed_at: datetime


@dataclass(frozen=True, slots=True)
class CanonicalDraftReceipt:
    """Signed canonical-host acknowledgement, verified by the host adapter."""

    draft_id: str
    device_id: str
    principal_id: str
    audience_id: str
    ciphertext_sha256: str
    canonical_message_id: str
    canonical_host_id: str
    signature: bytes


class OfflineDraftJournal:
    """Local queue of drafts only. This is *not* a replicated canonical DB."""

    def __init__(
        self, local_draft_path: Path, *,
        seal: Callable[[bytes], bytes],
        unseal: Callable[[bytes], bytes],
    ) -> None:
        if not callable(seal) or not callable(unseal):
            raise TypeError("explicit authenticated encryption/decryption required")
        self.seal, self.unseal = seal, unseal
        self.path = Path(local_draft_path)
        if self.path.name == "sofia.db":
            raise ValueError("offline draft journal must not masquerade as canonical state")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS offline_draft("
                "draft_id TEXT PRIMARY KEY, device_id TEXT NOT NULL,"
                "principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,"
                "body BLOB NOT NULL, digest TEXT NOT NULL,"
                "composed_at TEXT NOT NULL, exported_at TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS offline_pending "
                "ON offline_draft(exported_at, composed_at, draft_id)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS offline_draft_ack("
                "draft_id TEXT PRIMARY KEY REFERENCES offline_draft(draft_id),"
                "canonical_message_id TEXT NOT NULL,"
                "canonical_host_id TEXT NOT NULL,"
                "acknowledged_at TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def compose(
        self, *, device_id: str, principal_id: str,
        audience_id: str, text: str,
    ) -> OfflineDraft:
        values = (device_id, principal_id, audience_id)
        if any(not isinstance(v, str) or not v.strip() or len(v) > 160 for v in values):
            raise ValueError("authenticated device/principal/audience identifiers required")
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 32_768:
            raise ValueError("bounded nonempty draft text required")
        now = datetime.now(timezone.utc)
        identifier = f"offline-draft:{uuid4().hex}"
        ciphertext = self.seal(text.encode("utf-8"))
        if not isinstance(ciphertext, bytes) or ciphertext == text.encode("utf-8"):
            raise ValueError("draft encryption did not produce protected ciphertext")
        digest = sha256(ciphertext).hexdigest()
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO offline_draft VALUES(?,?,?,?,?,?,?,NULL)",
                (identifier, *values, ciphertext, digest, now.isoformat()),
            )
        return OfflineDraft(identifier, *values, text, digest, now)

    def pending(
        self, *, device_id: str, principal_id: str,
        audience_id: str, limit: int = 50,
    ) -> tuple[OfflineDraft, ...]:
        """Read only current principal/audience drafts, checking sealed bytes."""
        if any(not isinstance(v, str) or not v.strip() for v in (
            device_id, principal_id, audience_id
        )):
            raise ValueError("exact device/principal/audience required")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded draft read required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM offline_draft "
                "WHERE device_id=? AND principal_id=? AND audience_id=? "
                "AND exported_at IS NULL ORDER BY composed_at,draft_id LIMIT ?",
                (device_id, principal_id, audience_id, limit),
            ).fetchall()
        drafts: list[OfflineDraft] = []
        for row in rows:
            encrypted = row["body"]
            if sha256(encrypted).hexdigest() != row["digest"]:
                raise ValueError("offline draft ciphertext digest mismatch")
            decoded = self.unseal(encrypted)
            if not isinstance(decoded, bytes):
                raise TypeError("authenticated draft unseal must return bytes")
            drafts.append(OfflineDraft(
                row["draft_id"], row["device_id"], row["principal_id"],
                row["audience_id"], decoded.decode("utf-8", "strict"),
                row["digest"], datetime.fromisoformat(row["composed_at"]),
            ))
        return tuple(drafts)

    def acknowledge(
        self, receipt: CanonicalDraftReceipt, *,
        verify_host_receipt: Callable[[CanonicalDraftReceipt], bool],
        at: datetime,
    ) -> bool:
        """Mark exported only after an independent trusted-host signature check.

        The verifier MUST use a pinned canonical host identity/key and a
        domain-separated signature over every typed receipt field. The
        journal neither owns that key nor trusts model-generated receipts.
        """
        if not isinstance(receipt, CanonicalDraftReceipt):
            raise TypeError("typed canonical receipt required")
        if not callable(verify_host_receipt):
            raise TypeError("trusted host receipt verifier required")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("aware acknowledgement timestamp required")
        identifiers = (
            receipt.draft_id, receipt.device_id, receipt.principal_id,
            receipt.audience_id, receipt.canonical_message_id,
            receipt.canonical_host_id,
        )
        if any(not isinstance(v, str) or not v.strip() or len(v) > 256 for v in identifiers):
            raise ValueError("canonical receipt identifiers missing or invalid")
        if (
            not isinstance(receipt.ciphertext_sha256, str)
            or len(receipt.ciphertext_sha256) != 64
            or any(c not in "0123456789abcdef" for c in receipt.ciphertext_sha256)
            or not isinstance(receipt.signature, bytes)
            or len(receipt.signature) < 32
        ):
            raise ValueError("canonical proof fields invalid")
        if verify_host_receipt(receipt) is not True:
            raise PermissionError("canonical host acknowledgement signature not verified")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT device_id,principal_id,audience_id,digest,exported_at "
                "FROM offline_draft WHERE draft_id=?",
                (receipt.draft_id,),
            ).fetchone()
            if row is None:
                raise LookupError("draft does not exist")
            if (
                (row["device_id"], row["principal_id"], row["audience_id"], row["digest"])
                != (receipt.device_id, receipt.principal_id,
                    receipt.audience_id, receipt.ciphertext_sha256)
            ):
                raise PermissionError("receipt does not match the original encrypted draft")
            existing = db.execute(
                "SELECT canonical_message_id,canonical_host_id FROM offline_draft_ack "
                "WHERE draft_id=?", (receipt.draft_id,),
            ).fetchone()
            if existing is not None:
                if (existing["canonical_message_id"], existing["canonical_host_id"]) != (
                    receipt.canonical_message_id, receipt.canonical_host_id,
                ):
                    raise PermissionError("conflicting canonical delivery receipt")
                return False
            if row["exported_at"] is not None:
                raise PermissionError("export timestamp present without canonical receipt")
            stamp = at.astimezone(timezone.utc).isoformat()
            db.execute(
                "INSERT INTO offline_draft_ack VALUES(?,?,?,?)",
                (receipt.draft_id, receipt.canonical_message_id,
                 receipt.canonical_host_id, stamp),
            )
            db.execute(
                "UPDATE offline_draft SET exported_at=? WHERE draft_id=?",
                (stamp, receipt.draft_id),
            )
        return True
