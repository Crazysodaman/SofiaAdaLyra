from __future__ import annotations
from contextlib import closing
import json
from pathlib import Path
from datetime import datetime
import sqlite3
from .model import KnowledgeDocument,KnowledgeFact,SourceKind

class KnowledgeStore:
    def __init__(self)->None:
        self._documents:dict[str,KnowledgeDocument]={}; self._facts:dict[str,KnowledgeFact]={}; self._by_document:dict[str,list[str]]={}
    def register_document(self, document:KnowledgeDocument)->None:
        old=self._documents.get(document.document_id)
        if old is not None and old != document: raise ValueError("document_id already registered with different provenance")
        self._documents[document.document_id]=document
    def record_fact(self,fact:KnowledgeFact)->None:
        if fact.document_id not in self._documents: raise KeyError("fact source document is not registered")
        old=self._facts.get(fact.fact_id)
        if old is not None and old != fact: raise ValueError("fact_id conflict")
        self._facts[fact.fact_id]=fact
        ids=self._by_document.setdefault(fact.document_id,[])
        if fact.fact_id not in ids: ids.append(fact.fact_id)
    def document(self,document_id:str): return self._documents.get(document_id)
    def fact(self,fact_id:str): return self._facts.get(fact_id)
    def facts_for(self,document_id:str)->tuple[KnowledgeFact,...]:
        return tuple(self._facts[x] for x in self._by_document.get(document_id,()))
    def documents(self)->tuple[KnowledgeDocument,...]:
        return tuple(self._documents[k] for k in sorted(self._documents))
    def facts(self)->tuple[KnowledgeFact,...]:
        return tuple(self._facts[k] for k in sorted(self._facts))
    def active_facts(self)->tuple[KnowledgeFact,...]:
        superseded={old for fact in self._facts.values() for old in fact.supersedes}
        return tuple(f for f in self.facts() if f.fact_id not in superseded)


def load_legacy_knowledge(path: Path) -> KnowledgeStore:
    """Read retired JSON evidence without creating a second writable owner."""
    data = json.loads(path.read_text(encoding="utf-8"))
    store = KnowledgeStore()
    for raw in data.get("documents", []):
        values = dict(raw)
        values["source_kind"] = SourceKind(values["source_kind"])
        values["retrieved_at"] = datetime.fromisoformat(values["retrieved_at"])
        store.register_document(KnowledgeDocument(**values))
    for raw in data.get("facts", []):
        values = dict(raw)
        values["observed_at"] = datetime.fromisoformat(values["observed_at"])
        values["supersedes"] = tuple(values.get("supersedes", ()))
        store.record_fact(KnowledgeFact(**values))
    return store


def retire_legacy_file(path: Path) -> None:
    destination = path.with_name(path.name + ".migrated")
    index = 1
    while destination.exists():
        destination = path.with_name(path.name + f".migrated.{index}")
        index += 1
    path.replace(destination)


class SQLiteKnowledgeStore(KnowledgeStore):
    """Canonical SQLite durability for trusted knowledge provenance."""

    def __init__(self, path: Path, *, legacy_path: Path | None = None) -> None:
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
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
        if old is not None:
            super().register_document(document)
            return
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
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
        super().register_document(document)

    def record_fact(self, fact: KnowledgeFact) -> None:
        old = self.fact(fact.fact_id)
        if fact.document_id not in self._documents:
            raise KeyError("fact source document is not registered")
        if old is not None:
            super().record_fact(fact)
            return
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
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
        super().record_fact(fact)

    def _migrate_legacy(self, legacy_path: Path) -> None:
        if not legacy_path.is_file():
            return
        legacy = load_legacy_knowledge(legacy_path)
        for document in legacy.documents():
            self.register_document(document)
        for fact in legacy.facts():
            self.record_fact(fact)
        if any(self.document(value.document_id) != value for value in legacy.documents()) or any(self.fact(value.fact_id) != value for value in legacy.facts()):
            raise RuntimeError(
                "legacy knowledge.json conflicts with canonical sofia.db"
            )
        retire_legacy_file(legacy_path)
