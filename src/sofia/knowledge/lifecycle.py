"""Durable document freshness/invalidation state separate from source content."""
from __future__ import annotations
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import sqlite3
from sofia.state.atomic_file import retire_legacy_file

class DocumentDisposition(str,Enum):
    ACTIVE="active"; SUPERSEDED="superseded"; INVALID="invalid"

@dataclass(frozen=True)
class DocumentStatus:
    document_id:str
    disposition:DocumentDisposition=DocumentDisposition.ACTIVE
    replaced_by:str|None=None

class SQLiteKnowledgeLifecycle:
    """Canonical SQLite document freshness/invalidation state."""

    def __init__(
        self,
        path: Path,
        *,
        legacy_path: Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._status: dict[str, DocumentStatus] = {}
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_document_lifecycle (
                    document_id TEXT PRIMARY KEY,
                    disposition TEXT NOT NULL,
                    replaced_by TEXT
                )
            """)
            for row in db.execute("""
                SELECT document_id,disposition,replaced_by
                FROM knowledge_document_lifecycle
                ORDER BY document_id
            """):
                status = DocumentStatus(
                    row[0],
                    DocumentDisposition(row[1]),
                    row[2],
                )
                self._status[status.document_id] = status
        if legacy_path is not None:
            self._migrate_legacy(Path(legacy_path))

    def register(self, document_id: str) -> DocumentStatus:
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("document_id required")
        existing = self._status.get(document_id)
        if existing is not None:
            return existing
        status = DocumentStatus(document_id)
        self._write(status)
        self._status[document_id] = status
        return status

    def supersede(self, old_id: str, new_id: str) -> None:
        if old_id == new_id:
            raise ValueError("replacement must be a different document")
        self.register(old_id)
        self.register(new_id)
        status = DocumentStatus(
            old_id,
            DocumentDisposition.SUPERSEDED,
            new_id,
        )
        self._write(status)
        self._status[old_id] = status

    def invalidate(self, document_id: str) -> None:
        self.register(document_id)
        status = DocumentStatus(
            document_id,
            DocumentDisposition.INVALID,
            None,
        )
        self._write(status)
        self._status[document_id] = status

    def status(self, document_id: str) -> DocumentStatus | None:
        return self._status.get(document_id)

    def active(self, document_id: str) -> bool:
        status = self._status.get(document_id)
        return (
            status is None
            or status.disposition is DocumentDisposition.ACTIVE
        )

    def _write(self, status: DocumentStatus) -> None:
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                INSERT INTO knowledge_document_lifecycle(
                    document_id,disposition,replaced_by
                )
                VALUES(?,?,?)
                ON CONFLICT(document_id) DO UPDATE SET
                    disposition=excluded.disposition,
                    replaced_by=excluded.replaced_by
            """,(
                status.document_id,
                status.disposition.value,
                status.replaced_by,
            ))
            db.commit()

    def _migrate_legacy(self, legacy_path: Path) -> None:
        if not legacy_path.is_file():
            return
        legacy = {}
        for raw in json.loads(legacy_path.read_text(encoding="utf-8")):
            status = DocumentStatus(raw["document_id"], DocumentDisposition(raw["disposition"]), raw.get("replaced_by"))
            legacy[status.document_id] = status
        for document_id in sorted(legacy):
            status = legacy[document_id]
            current = self._status.get(document_id)
            if current is not None and current != status:
                raise RuntimeError(
                    "legacy knowledge-lifecycle.json conflicts with "
                    "canonical sofia.db"
                )
            self._write(status)
            self._status[document_id] = status
        for document_id, status in legacy.items():
            if self._status.get(document_id) != status:
                raise RuntimeError(
                    "legacy knowledge lifecycle migration did not verify"
                )
        retire_legacy_file(legacy_path)
