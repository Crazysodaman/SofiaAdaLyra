"""Candidate historical facts with separate observed and effective times.

Never promotes facts into authoritative memory. Only MEM review can accept
verified information and invalidate derived summaries.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TemporalCandidate:
    candidate_id: str
    principal_id: str
    audience_id: str
    subject_key: str
    assertion: str
    evidence_ref: str
    learned_at: datetime
    asserted_valid_at: datetime
    supersedes_candidate_id: str | None


class TemporalCandidateStore:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical sofia.db required")
        with closing(self._connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS memory_temporal_candidate("
                "candidate_id TEXT PRIMARY KEY, principal_id TEXT NOT NULL,"
                "audience_id TEXT NOT NULL, subject_key TEXT NOT NULL,"
                "assertion TEXT NOT NULL, evidence_ref TEXT NOT NULL,"
                "learned_at TEXT NOT NULL, asserted_valid_at TEXT NOT NULL,"
                "supersedes_candidate_id TEXT,"
                "review_state TEXT NOT NULL CHECK(review_state='candidate'))"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS memory_temporal_scope "
                "ON memory_temporal_candidate(principal_id,audience_id,subject_key,asserted_valid_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def propose(
        self, *, principal_id: str, audience_id: str, subject_key: str,
        assertion: str, evidence_ref: str,
        asserted_valid_at: datetime,
        supersedes_candidate_id: str | None = None,
    ) -> TemporalCandidate:
        vals = (principal_id, audience_id, subject_key, assertion, evidence_ref)
        if any(not isinstance(v, str) or not v.strip() for v in vals):
            raise ValueError("bounded source-backed fact candidate required")
        if any(len(v) > n for v,n in zip(vals, (160,160,200,2000,300))):
            raise ValueError("fact candidate exceeds length budget")
        if (
            not isinstance(asserted_valid_at, datetime)
            or asserted_valid_at.tzinfo is None or asserted_valid_at.utcoffset() is None
        ):
            raise ValueError("valid-at date must be timezone-aware")
        if supersedes_candidate_id is not None and not isinstance(supersedes_candidate_id, str):
            raise TypeError("supersedes_candidate_id must be a string or None")
        stamp = datetime.now(timezone.utc)
        identifier = f"temporal-candidate:{uuid4().hex}"
        with closing(self._connect()) as db, db:
            if supersedes_candidate_id is not None:
                prior = db.execute(
                    "SELECT candidate_id FROM memory_temporal_candidate "
                    "WHERE candidate_id=? AND principal_id=? AND audience_id=? AND subject_key=?",
                    (supersedes_candidate_id,principal_id,audience_id,subject_key),
                ).fetchone()
                if prior is None:
                    raise PermissionError("cannot supersede a different audience's candidate")
            db.execute(
                "INSERT INTO memory_temporal_candidate VALUES(?,?,?,?,?,?,?,?,?,?)",
                (identifier,principal_id,audience_id,subject_key,assertion,evidence_ref,
                 stamp.isoformat(),asserted_valid_at.astimezone(timezone.utc).isoformat(),
                 supersedes_candidate_id,"candidate"),
            )
        return TemporalCandidate(
            identifier, principal_id, audience_id, subject_key,
            assertion, evidence_ref, stamp, asserted_valid_at, supersedes_candidate_id,
        )

    def candidates(
        self, *, principal_id: str, audience_id: str,
        subject_key: str, limit: int = 50,
    ) -> tuple[TemporalCandidate, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("bounded candidate query required")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM memory_temporal_candidate "
                "WHERE principal_id=? AND audience_id=? AND subject_key=? "
                "ORDER BY asserted_valid_at DESC,candidate_id DESC LIMIT ?",
                (principal_id,audience_id,subject_key,limit),
            ).fetchall()
        return tuple(
            TemporalCandidate(
                r["candidate_id"],r["principal_id"],r["audience_id"],
                r["subject_key"],r["assertion"],r["evidence_ref"],
                datetime.fromisoformat(r["learned_at"]),
                datetime.fromisoformat(r["asserted_valid_at"]),
                r["supersedes_candidate_id"],
            ) for r in rows
        )
