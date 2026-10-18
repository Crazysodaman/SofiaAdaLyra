"""Explicit-feedback memory reranking after canonical MEM eligibility.

The scorer cannot retrieve, promote, or make a memory factual.  It receives
only the final eligible shortlist from ``MemorySystem`` and may reorder that
same set when there is enough fresh, audience-scoped owner feedback.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from uuid import UUID

from sofia.memory.model import MemoryRecord
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


class RelevanceJudgment(str, Enum):
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"
    CORRECTION = "correction"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RankingEvaluation:
    sample_count: int
    baseline_recall_at_5: float | None
    scorer_recall_at_5: float | None
    baseline_ndcg_at_5: float | None
    scorer_ndcg_at_5: float | None
    cross_audience_violations: int
    independently_held_out: bool


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("ranking time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(sorted({part.lower() for part in re.findall(r"[A-Za-z0-9À-ÿ']+", value) if len(part) > 1}))[:32]


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MemoryRankingService:
    MIN_LABELS = 8
    MIN_TOPIC_LABELS = 3
    MAX_MODEL_AGE = timedelta(days=90)

    def __init__(self, state_path: str | Path, candidates: DurableMemoryCandidateStore) -> None:
        if not isinstance(candidates, DurableMemoryCandidateStore):
            raise TypeError("canonical candidate store required")
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self._candidates = candidates
        self._last_receipt: dict[tuple[str, str], str] = {}
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_ranking_retrieval(
                    retrieval_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    query_digest TEXT NOT NULL,
                    topic_digest TEXT NOT NULL,
                    candidate_ids_json TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_ranking_judgment(
                    judgment_id TEXT PRIMARY KEY,
                    retrieval_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    judgment TEXT NOT NULL,
                    preferred_over_id TEXT,
                    source_ids_json TEXT NOT NULL,
                    judged_at TEXT NOT NULL,
                    valid INTEGER NOT NULL,
                    invalid_reason TEXT,
                    FOREIGN KEY(retrieval_id) REFERENCES memory_ranking_retrieval(retrieval_id)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_ranking_scope
                ON memory_ranking_judgment(principal_id,audience_id,valid,judged_at);
                CREATE TABLE IF NOT EXISTS memory_ranking_model(
                    model_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    trained_at TEXT NOT NULL,
                    judgment_ids_json TEXT NOT NULL,
                    candidate_scores_json TEXT NOT NULL,
                    topic_counts_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    invalid_reason TEXT
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return self._guard.connect(timeout=10)

    def rank(
        self, query: str, records: tuple[MemoryRecord, ...], *,
        principal: PrincipalContext, at: datetime,
    ) -> tuple[MemoryRecord, ...]:
        """Record a scoped retrieval and optionally reorder its existing set."""
        moment = _utc(at)
        if not records:
            return records
        ids = tuple(record.id for record in records)
        topic = _digest(_tokens(query))
        body = {"principal": principal.principal_id, "audience": principal.audience_id,
                "query": _digest(query), "ids": ids, "at": moment.isoformat()}
        retrieval_id = "memory-retrieval:" + _digest(body)
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO memory_ranking_retrieval VALUES(?,?,?,?,?,?,?)",
                (retrieval_id, principal.principal_id, principal.audience_id,
                 body["query"], topic, json.dumps(ids), moment.isoformat()),
            )
            model = db.execute(
                "SELECT trained_at,candidate_scores_json,topic_counts_json FROM memory_ranking_model "
                "WHERE principal_id=? AND audience_id=? AND status='active' "
                "ORDER BY trained_at DESC,model_id DESC LIMIT 1",
                (principal.principal_id, principal.audience_id),
            ).fetchone()
        self._last_receipt[(principal.principal_id, principal.audience_id)] = retrieval_id
        if model is None or moment - datetime.fromisoformat(model[0]) > self.MAX_MODEL_AGE:
            return records
        topic_counts = json.loads(model[2])
        if int(topic_counts.get(topic, 0)) < self.MIN_TOPIC_LABELS:
            return records
        scores = json.loads(model[1])
        # Reconcile lifecycle/source/privacy changes at the point of use. A
        # deleted original may make a promoted row ineligible without passing
        # through MemoryReviewService, so published influence must fail closed.
        invalid = []
        for raw_id in scores:
            try:
                candidate_id = UUID(raw_id)
                candidate = self._candidates.get(candidate_id)
                eligible = (
                    candidate is not None
                    and self._candidates.status(candidate_id) is CandidateStatus.PROMOTED
                    and self._candidates.is_recall_eligible(candidate_id)
                    and candidate.principal_id == principal.principal_id
                    and candidate.audience_id in (None, principal.audience_id)
                )
            except (TypeError, ValueError):
                eligible = False
                candidate_id = None
            if not eligible and candidate_id is not None:
                invalid.append(candidate_id)
        if invalid:
            for candidate_id in invalid:
                self.invalidate_candidate(
                    candidate_id,
                    reason="canonical memory lifecycle/source/privacy changed",
                    at=moment,
                )
            return records
        indexed = list(enumerate(records))
        indexed.sort(key=lambda item: (-float(scores.get(item[1].id, 0.0)), item[0]))
        return tuple(item[1] for item in indexed)

    def last_retrieval_id(self, principal: PrincipalContext) -> str | None:
        return self._last_receipt.get((principal.principal_id, principal.audience_id))

    def record_judgment(
        self, *, retrieval_id: str, candidate_id: UUID,
        judgment: RelevanceJudgment, principal: PrincipalContext,
        at: datetime, preferred_over_id: UUID | None = None,
    ) -> str:
        moment = _utc(at)
        if not isinstance(principal, PrincipalContext) or principal.audience_kind is not AudienceKind.PRIVATE:
            raise PermissionError("explicit authenticated private user feedback required")
        if not isinstance(candidate_id, UUID) or not isinstance(judgment, RelevanceJudgment):
            raise TypeError("typed candidate and relevance judgment required")
        with closing(self._connect()) as db:
            retrieval = db.execute(
                "SELECT principal_id,audience_id,candidate_ids_json FROM memory_ranking_retrieval WHERE retrieval_id=?",
                (retrieval_id,),
            ).fetchone()
        if retrieval is None or retrieval[0] != principal.principal_id or retrieval[1] != principal.audience_id:
            raise PermissionError("retrieval feedback is outside this principal/audience")
        eligible_ids = tuple(json.loads(retrieval[2]))
        if str(candidate_id) not in eligible_ids:
            raise PermissionError("candidate was not in the eligible retrieved set")
        if preferred_over_id is not None and str(preferred_over_id) not in eligible_ids:
            raise PermissionError("pairwise comparison must use the same eligible retrieval")
        if preferred_over_id == candidate_id:
            raise ValueError("pairwise preference requires two different candidates")
        candidate = self._candidates.get(candidate_id)
        if (candidate is None or self._candidates.status(candidate_id) is not CandidateStatus.PROMOTED
                or not self._candidates.is_recall_eligible(candidate_id)
                or candidate.principal_id != principal.principal_id
                or candidate.audience_id not in (None, principal.audience_id)):
            raise PermissionError("candidate is no longer eligible for feedback")
        source_ids = tuple(f"{source.session_id}:{source.message_id}" for source in candidate.sources)
        body = {"retrieval": retrieval_id, "candidate": str(candidate_id),
                "judgment": judgment.value, "preferred_over": None if preferred_over_id is None else str(preferred_over_id),
                "at": moment.isoformat()}
        judgment_id = "memory-judgment:" + _digest(body)
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO memory_ranking_judgment VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
                (judgment_id, retrieval_id, str(candidate_id), principal.principal_id,
                 principal.audience_id, judgment.value,
                 None if preferred_over_id is None else str(preferred_over_id),
                 json.dumps(source_ids), moment.isoformat(), 1),
            )
        return judgment_id

    def train(self, *, principal: PrincipalContext, at: datetime) -> str | None:
        moment = _utc(at)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT j.judgment_id,j.candidate_id,j.judgment,j.preferred_over_id,r.topic_digest "
                "FROM memory_ranking_judgment j JOIN memory_ranking_retrieval r ON r.retrieval_id=j.retrieval_id "
                "WHERE j.principal_id=? AND j.audience_id=? AND j.valid=1 "
                "AND j.judgment!='unknown' ORDER BY j.judged_at,j.judgment_id LIMIT 5000",
                (principal.principal_id, principal.audience_id),
            ).fetchall()
        if len(rows) < self.MIN_LABELS:
            return None
        stale_ids = []
        for row in rows:
            candidate_id = UUID(row[1])
            candidate = self._candidates.get(candidate_id)
            if (
                candidate is None
                or self._candidates.status(candidate_id) is not CandidateStatus.PROMOTED
                or not self._candidates.is_recall_eligible(candidate_id)
                or candidate.principal_id != principal.principal_id
                or candidate.audience_id not in (None, principal.audience_id)
            ):
                stale_ids.append(candidate_id)
        if stale_ids:
            for candidate_id in set(stale_ids):
                self.invalidate_candidate(
                    candidate_id,
                    reason="canonical memory became ineligible before training",
                    at=moment,
                )
            return None
        totals: dict[str, list[float]] = {}
        topics: dict[str, int] = {}
        for judgment_id, candidate_id, judgment, preferred_over, topic in rows:
            value = 1.0 if judgment == RelevanceJudgment.RELEVANT.value else -1.0
            if judgment == RelevanceJudgment.CORRECTION.value:
                value = -1.0
            totals.setdefault(candidate_id, []).append(value)
            if preferred_over is not None:
                totals.setdefault(candidate_id, []).append(0.5)
                totals.setdefault(preferred_over, []).append(-0.5)
            topics[topic] = topics.get(topic, 0) + 1
        scores = {key: max(-1.0, min(1.0, sum(values) / len(values))) for key, values in totals.items()}
        ids = tuple(row[0] for row in rows)
        body = {"scope": (principal.principal_id, principal.audience_id), "at": moment.isoformat(),
                "judgments": ids, "scores": scores, "topics": topics}
        model_id = "memory-ranker:" + _digest(body)
        with closing(self._connect()) as db, db:
            db.execute("UPDATE memory_ranking_model SET status='superseded' WHERE principal_id=? AND audience_id=? AND status='active'",
                       (principal.principal_id, principal.audience_id))
            db.execute("INSERT INTO memory_ranking_model VALUES(?,?,?,?,?,?,?,?,NULL)",
                       (model_id, principal.principal_id, principal.audience_id, moment.isoformat(),
                        json.dumps(ids), json.dumps(scores, sort_keys=True), json.dumps(topics, sort_keys=True), "active"))
        return model_id

    def invalidate_candidate(self, candidate_id: UUID, *, reason: str, at: datetime) -> int:
        _utc(at)
        if not isinstance(candidate_id, UUID) or not isinstance(reason, str) or not reason.strip():
            raise ValueError("typed candidate and invalidation reason required")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE memory_ranking_judgment SET valid=0,invalid_reason=? WHERE candidate_id=? AND valid=1",
                (reason[:240], str(candidate_id)),
            ).rowcount
            models = db.execute(
                "SELECT model_id,judgment_ids_json FROM memory_ranking_model WHERE status='active'"
            ).fetchall()
            affected = {row[0] for row in db.execute(
                "SELECT judgment_id FROM memory_ranking_judgment WHERE candidate_id=?", (str(candidate_id),)
            )}
            for model_id, raw in models:
                if affected.intersection(json.loads(raw)):
                    db.execute("UPDATE memory_ranking_model SET status='review_required',invalid_reason=? WHERE model_id=?",
                               (reason[:240], model_id))
        return changed

    def evaluate_future(self, *, principal: PrincipalContext, trained_before: datetime) -> RankingEvaluation:
        cutoff = _utc(trained_before).isoformat()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT r.candidate_ids_json,j.candidate_id,j.judgment,r.principal_id,r.audience_id "
                "FROM memory_ranking_retrieval r JOIN memory_ranking_judgment j ON j.retrieval_id=r.retrieval_id "
                "WHERE r.principal_id=? AND r.audience_id=? AND r.retrieved_at>? AND j.valid=1",
                (principal.principal_id, principal.audience_id, cutoff),
            ).fetchall()
        relevant = [row for row in rows if row[2] == RelevanceJudgment.RELEVANT.value]
        violations = sum(row[3] != principal.principal_id or row[4] != principal.audience_id for row in rows)
        if not relevant:
            return RankingEvaluation(0, None, None, None, None, violations, True)
        # Stored retrieval order is the deterministic baseline. A prospective
        # campaign must later compare scorer order; no unobserved gain is claimed.
        hits = sum(row[1] in json.loads(row[0])[:5] for row in relevant)
        baseline_recall = hits / len(relevant)
        dcg = sum(1.0 / (1.0 + json.loads(row[0])[:5].index(row[1]))
                  for row in relevant if row[1] in json.loads(row[0])[:5]) / len(relevant)
        return RankingEvaluation(len(relevant), baseline_recall, None, dcg, None, violations, True)

    def diagnostics(self, *, principal: PrincipalContext) -> dict[str, object]:
        with closing(self._connect()) as db:
            judgments = dict(db.execute(
                "SELECT judgment,COUNT(*) FROM memory_ranking_judgment WHERE principal_id=? AND audience_id=? AND valid=1 GROUP BY judgment",
                (principal.principal_id, principal.audience_id),
            ).fetchall())
            model = db.execute(
                "SELECT model_id,status,trained_at,invalid_reason FROM memory_ranking_model WHERE principal_id=? AND audience_id=? ORDER BY trained_at DESC LIMIT 1",
                (principal.principal_id, principal.audience_id),
            ).fetchone()
        return {"authority": False, "judgments": judgments, "model": None if model is None else {
            "model_id": model[0], "status": model[1], "trained_at": model[2], "invalid_reason": model[3],
        }}
