from __future__ import annotations
import json,os
from pathlib import Path
from datetime import datetime
import sqlite3
from .model import KnowledgeDocument,KnowledgeFact,SourceKind
from .store import KnowledgeStore

class JsonKnowledgeStore(KnowledgeStore):
    """Atomic durable provenance store; successful mutations are persisted."""
    def __init__(self,path:Path)->None:
        super().__init__(); self.path=path; self._loading=True
        if path.exists(): self._load()
        self._loading=False
    def _load(self)->None:
        data=json.loads(self.path.read_text(encoding="utf-8"))
        for d in data.get("documents",[]):
            d["source_kind"]=SourceKind(d["source_kind"]); d["retrieved_at"]=datetime.fromisoformat(d["retrieved_at"])
            super().register_document(KnowledgeDocument(**d))
        for raw in data.get("facts",[]):
            raw["observed_at"]=datetime.fromisoformat(raw["observed_at"]); raw["supersedes"]=tuple(raw.get("supersedes",()))
            super().record_fact(KnowledgeFact(**raw))
    def register_document(self,document:KnowledgeDocument)->None:
        super().register_document(document)
        if not self._loading: self.flush()
    def record_fact(self,fact:KnowledgeFact)->None:
        super().record_fact(fact)
        if not self._loading: self.flush()
    def flush(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data={"documents":[dict(document_id=d.document_id,source_kind=d.source_kind.value,source_uri=d.source_uri,version=d.version,retrieved_at=d.retrieved_at.isoformat(),content_hash=d.content_hash,trusted_for_reference=d.trusted_for_reference) for d in self._documents.values()],
              "facts":[dict(fact_id=x.fact_id,document_id=x.document_id,statement=x.statement,locator=x.locator,observed_at=x.observed_at.isoformat(),supersedes=list(x.supersedes)) for x in self._facts.values()]}
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        with tmp.open("w",encoding="utf-8") as fh:
            json.dump(data,fh,sort_keys=True,indent=2); fh.flush(); os.fsync(fh.fileno())
        tmp.replace(self.path)


class SQLiteKnowledgeStore(KnowledgeStore):
    """Canonical SQLite durability for trusted knowledge provenance."""

    def __init__(self, path: Path, *, legacy_path: Path | None = None) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=10.0) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_document (
                    document_id TEXT PRIMARY KEY,
                    source_kind TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    version TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    trusted_for_reference INTEGER NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_fact (
                    fact_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    supersedes_json TEXT NOT NULL
                )
            """)
            rows = db.execute("""
                SELECT document_id,source_kind,source_uri,version,retrieved_at,
                       content_hash,trusted_for_reference
                FROM knowledge_document
                ORDER BY document_id
            """).fetchall()
            for row in rows:
                super().register_document(KnowledgeDocument(
                    document_id=row[0],
                    source_kind=SourceKind(row[1]),
                    source_uri=row[2],
                    version=row[3],
                    retrieved_at=datetime.fromisoformat(row[4]),
                    content_hash=row[5],
                    trusted_for_reference=bool(row[6]),
                ))
            facts = db.execute("""
                SELECT fact_id,document_id,statement,locator,observed_at,
                       supersedes_json
                FROM knowledge_fact
                ORDER BY fact_id
            """).fetchall()
            for row in facts:
                super().record_fact(KnowledgeFact(
                    fact_id=row[0],
                    document_id=row[1],
                    statement=row[2],
                    locator=row[3],
                    observed_at=datetime.fromisoformat(row[4]),
                    supersedes=tuple(json.loads(row[5])),
                ))
        if legacy_path is not None:
            self._migrate_legacy(Path(legacy_path))

    def register_document(self, document: KnowledgeDocument) -> None:
        old = self.document(document.document_id)
        super().register_document(document)
        if old is not None:
            return
        with sqlite3.connect(self.path, timeout=10.0) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                INSERT INTO knowledge_document(
                    document_id,source_kind,source_uri,version,retrieved_at,
                    content_hash,trusted_for_reference
                ) VALUES(?,?,?,?,?,?,?)
            """,(
                document.document_id,
                document.source_kind.value,
                document.source_uri,
                document.version,
                document.retrieved_at.isoformat(),
                document.content_hash,
                1 if document.trusted_for_reference else 0,
            ))
            db.commit()

    def record_fact(self, fact: KnowledgeFact) -> None:
        old = self.fact(fact.fact_id)
        super().record_fact(fact)
        if old is not None:
            return
        with sqlite3.connect(self.path, timeout=10.0) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                INSERT INTO knowledge_fact(
                    fact_id,document_id,statement,locator,observed_at,
                    supersedes_json
                ) VALUES(?,?,?,?,?,?)
            """,(
                fact.fact_id,
                fact.document_id,
                fact.statement,
                fact.locator,
                fact.observed_at.isoformat(),
                json.dumps(list(fact.supersedes), separators=(",", ":")),
            ))
            db.commit()

    def _migrate_legacy(self, legacy_path: Path) -> None:
        if not legacy_path.is_file():
            return
        legacy = JsonKnowledgeStore(legacy_path)
        for document in legacy.documents():
            self.register_document(document)
        for fact in legacy.facts():
            self.record_fact(fact)
        if self.documents() != legacy.documents() or self.facts() != legacy.facts():
            raise RuntimeError(
                "legacy knowledge.json conflicts with canonical sofia.db"
            )
        destination = legacy_path.with_name(legacy_path.name + ".migrated")
        index = 1
        while destination.exists():
            destination = legacy_path.with_name(
                legacy_path.name + f".migrated.{index}"
            )
            index += 1
        legacy_path.replace(destination)
