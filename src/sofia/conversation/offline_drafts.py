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
        self, *, device_id: str, audience_id: str, limit: int = 50
    ) -> tuple[OfflineDraft, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded draft read required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM offline_draft WHERE device_id=? AND audience_id=? "
                "AND exported_at IS NULL ORDER BY composed_at,draft_id LIMIT ?",
                (device_id, audience_id, limit),
            ).fetchall()
        return tuple(
            OfflineDraft(
                r["draft_id"], r["device_id"], r["principal_id"],
                r["audience_id"],
                self.unseal(r["body"]).decode("utf-8", "strict"),
                r["digest"], datetime.fromisoformat(r["composed_at"]),
            ) for r in rows
        )
