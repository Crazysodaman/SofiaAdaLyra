"""SQLite FTS5 hybrid index and provenance-linked knowledge graph."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
from typing import Callable


EmbeddingProvider = Callable[[str], tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class KnowledgeSection:
    section_id: str
    document_id: str
    ordinal: int
    heading: str | None
    content: str
    locator: str
    content_hash: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class HybridKnowledgeHit:
    section: KnowledgeSection
    score: float
    lexical_score: float
    semantic_score: float
    exact_match: bool


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9_./:-]{2,}", value.casefold())))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    scale = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return 0.0 if scale == 0 else max(-1.0, min(1.0, dot / scale))


class KnowledgeIndex:
    """One canonical SQLite index; embeddings are optional, bounded hints."""

    def __init__(
        self,
        path: Path | str,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.path = Path(path)
        self.embedding_provider = embedding_provider
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_section (
                    section_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    heading TEXT,
                    content TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT,
                    UNIQUE(document_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_section_document
                ON knowledge_section(document_id, ordinal);
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_section_fts USING fts5(
                    section_id UNINDEXED, heading, content, locator,
                    tokenize='unicode61 tokenchars ''_./:-'''
                );
                CREATE TABLE IF NOT EXISTS knowledge_graph_edge (
                    entity TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    PRIMARY KEY(entity, relation, target, section_id)
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_graph_entity
                ON knowledge_graph_edge(entity);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def make_section(
        *,
        document_id: str,
        ordinal: int,
        heading: str | None,
        content: str,
        locator: str,
        metadata: dict[str, object] | None = None,
    ) -> KnowledgeSection:
        digest = sha256(content.encode("utf-8")).hexdigest()
        return KnowledgeSection(
            section_id=f"{document_id}:section:{ordinal}",
            document_id=document_id,
            ordinal=ordinal,
            heading=heading,
            content=content,
            locator=locator,
            content_hash=digest,
            metadata=dict(metadata or {}),
        )

    def has_document(self, document_id: str) -> bool:
        with closing(self._connect()) as db:
            return db.execute(
                "SELECT 1 FROM knowledge_section WHERE document_id=? LIMIT 1",
                (document_id,),
            ).fetchone() is not None

    def index(self, sections: tuple[KnowledgeSection, ...]) -> None:
        if not sections:
            return
        document_ids = {item.document_id for item in sections}
        if len(document_ids) != 1:
            raise ValueError("one index operation must contain one document")
        embeddings: dict[str, tuple[float, ...]] = {}
        if self.embedding_provider is not None:
            for item in sections:
                vector = self.embedding_provider(
                    ((item.heading or "") + "\n" + item.content).strip()
                )
                if not isinstance(vector, tuple) or any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(float(value)) for value in vector
                ):
                    raise ValueError("embedding provider returned an invalid vector")
                embeddings[item.section_id] = tuple(float(value) for value in vector)
        document_id = sections[0].document_id
        with closing(self._connect()) as db, db:
            old_ids = tuple(
                row[0] for row in db.execute(
                    "SELECT section_id FROM knowledge_section WHERE document_id=?",
                    (document_id,),
                ).fetchall()
            )
            db.executemany(
                "DELETE FROM knowledge_section_fts WHERE section_id=?",
                ((value,) for value in old_ids),
            )
            db.execute("DELETE FROM knowledge_graph_edge WHERE document_id=?", (document_id,))
            db.execute("DELETE FROM knowledge_section WHERE document_id=?", (document_id,))
            for item in sections:
                db.execute(
                    """INSERT INTO knowledge_section VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        item.section_id, item.document_id, item.ordinal,
                        item.heading, item.content, item.locator,
                        item.content_hash,
                        json.dumps(item.metadata, sort_keys=True, separators=(",", ":")),
                        None if item.section_id not in embeddings else json.dumps(embeddings[item.section_id]),
                    ),
                )
                db.execute(
                    "INSERT INTO knowledge_section_fts VALUES (?,?,?,?)",
                    (item.section_id, item.heading or "", item.content, item.locator),
                )
                self._index_graph(db, item)

    @staticmethod
    def _index_graph(db: sqlite3.Connection, section: KnowledgeSection) -> None:
        edges: set[tuple[str, str, str]] = set()
        if section.heading:
            edges.add((section.heading.casefold(), "defined_by", section.heading))
        for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", section.content):
            if label.strip() and target.strip():
                edges.add((label.strip().casefold(), "references", target.strip()))
        for entity, relation, target in edges:
            db.execute(
                "INSERT OR IGNORE INTO knowledge_graph_edge VALUES (?,?,?,?,?)",
                (entity, relation, target, section.document_id, section.section_id),
            )

    @staticmethod
    def _section(row: sqlite3.Row) -> KnowledgeSection:
        return KnowledgeSection(
            row["section_id"], row["document_id"], int(row["ordinal"]),
            row["heading"], row["content"], row["locator"],
            row["content_hash"], json.loads(row["metadata_json"]),
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        eligible_document_ids: frozenset[str] | None = None,
    ) -> tuple[HybridKnowledgeHit, ...]:
        if not isinstance(query, str) or not query.strip():
            return ()
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("knowledge search limit must be in 1..50")
        tokens = _tokens(query)
        if not tokens:
            return ()
        match = " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:16])
        candidates: dict[str, tuple[sqlite3.Row, float]] = {}
        with closing(self._connect()) as db:
            for row in db.execute(
                """SELECT s.*, bm25(knowledge_section_fts, 0.0, 2.0, 1.0, 0.5) AS rank
                FROM knowledge_section_fts JOIN knowledge_section s USING(section_id)
                WHERE knowledge_section_fts MATCH ? ORDER BY rank LIMIT 100""",
                (match,),
            ).fetchall():
                candidates[row["section_id"]] = (row, float(row["rank"]))
            exact_rows = db.execute(
                """SELECT *, 0.0 AS rank FROM knowledge_section
                WHERE instr(lower(content), lower(?)) > 0
                   OR instr(lower(COALESCE(heading,'')), lower(?)) > 0
                ORDER BY ordinal LIMIT 100""",
                (query.strip(), query.strip()),
            ).fetchall()
            for row in exact_rows:
                candidates.setdefault(row["section_id"], (row, 0.0))
            if self.embedding_provider is not None:
                for row in db.execute(
                    "SELECT *, 1000.0 AS rank FROM knowledge_section "
                    "ORDER BY section_id LIMIT 500"
                ).fetchall():
                    candidates.setdefault(row["section_id"], (row, float(row["rank"])))

        query_tokens = set(tokens)
        query_vector = (
            None if self.embedding_provider is None
            else self.embedding_provider(query.strip())
        )
        hits = []
        for row, rank in candidates.values():
            section = self._section(row)
            if (
                eligible_document_ids is not None
                and section.document_id not in eligible_document_ids
            ):
                continue
            haystack = ((section.heading or "") + "\n" + section.content).casefold()
            exact = query.strip().casefold() in haystack
            overlap = len(query_tokens & set(_tokens(haystack))) / len(query_tokens)
            lexical = 1.0 / (1.0 + max(0.0, rank))
            semantic = overlap
            raw_embedding = row["embedding_json"]
            if query_vector is not None and raw_embedding:
                semantic = max(semantic, _cosine(
                    tuple(float(value) for value in query_vector),
                    tuple(float(value) for value in json.loads(raw_embedding)),
                ))
            score = lexical * 0.45 + semantic * 0.35 + (0.2 if exact else 0.0)
            hits.append(HybridKnowledgeHit(section, score, lexical, semantic, exact))
        hits.sort(key=lambda item: (-item.score, item.section.section_id))
        return tuple(hits[:limit])

    def graph(self, entity: str, *, limit: int = 20) -> tuple[dict[str, str], ...]:
        if not entity.strip():
            return ()
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT entity,relation,target,document_id,section_id
                FROM knowledge_graph_edge WHERE entity=? ORDER BY relation,target LIMIT ?""",
                (entity.strip().casefold(), limit),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def graph_for_document(
        self, document_id: str, *, limit: int = 100
    ) -> tuple[dict[str, str], ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT entity,relation,target,document_id,section_id
                FROM knowledge_graph_edge WHERE document_id=?
                ORDER BY section_id,entity,relation,target LIMIT ?""",
                (document_id, limit),
            ).fetchall()
        return tuple(dict(row) for row in rows)
