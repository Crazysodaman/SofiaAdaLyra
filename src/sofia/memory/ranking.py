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
import math
from pathlib import Path
import re
import sqlite3
from uuid import UUID

from sofia.memory.model import MemoryRecord
from sofia.memory.provenance import CandidateStatus
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


class RelevanceJudgment(str, Enum):
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"
    CORRECTION = "correction"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RankingEvaluation:
    sample_count: int
    scored_sample_count: int
    baseline_recall_at_5: float | None
    scorer_recall_at_5: float | None
    baseline_ndcg_at_5: float | None
    scorer_ndcg_at_5: float | None
    timeline_accuracy: float | None
    correction_accuracy: float | None
    source_accuracy: float | None
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
                CREATE TABLE IF NOT EXISTS memory_ranking_truth_review(
                    review_id TEXT PRIMARY KEY,
                    retrieval_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    timeline_truth TEXT NOT NULL CHECK(timeline_truth IN ('correct','incorrect','unknown')),
                    correction_truth TEXT NOT NULL CHECK(correction_truth IN ('correct','incorrect','unknown')),
                    source_accuracy TEXT NOT NULL CHECK(source_accuracy IN ('correct','incorrect','unknown')),
                    source_ids_json TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    FOREIGN KEY(retrieval_id) REFERENCES memory_ranking_retrieval(retrieval_id)
                );
                CREATE TABLE IF NOT EXISTS memory_ranking_evaluation(
                    evaluation_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    trained_before TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );
                """
            )
            retrieval_columns = {
                row[1] for row in db.execute(
                    "PRAGMA table_info(memory_ranking_retrieval)"
                ).fetchall()
            }
            if "scored_candidate_ids_json" not in retrieval_columns:
                db.execute(
                    "ALTER TABLE memory_ranking_retrieval "
                    "ADD COLUMN scored_candidate_ids_json TEXT"
                )
            if "model_id" not in retrieval_columns:
                db.execute(
                    "ALTER TABLE memory_ranking_retrieval ADD COLUMN model_id TEXT"
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
                "INSERT OR IGNORE INTO memory_ranking_retrieval("
                "retrieval_id,principal_id,audience_id,query_digest,topic_digest,"
                "candidate_ids_json,retrieved_at) VALUES(?,?,?,?,?,?,?)",
                (retrieval_id, principal.principal_id, principal.audience_id,
                 body["query"], topic, json.dumps(ids), moment.isoformat()),
            )
            model = db.execute(
                "SELECT model_id,trained_at,candidate_scores_json,topic_counts_json FROM memory_ranking_model "
                "WHERE principal_id=? AND audience_id=? AND status='active' "
                "ORDER BY trained_at DESC,model_id DESC LIMIT 1",
                (principal.principal_id, principal.audience_id),
            ).fetchone()
        self._last_receipt[(principal.principal_id, principal.audience_id)] = retrieval_id
        if model is None or moment - datetime.fromisoformat(model[1]) > self.MAX_MODEL_AGE:
            return records
        topic_counts = json.loads(model[3])
        if int(topic_counts.get(topic, 0)) < self.MIN_TOPIC_LABELS:
            return records
        scores = json.loads(model[2])
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
        ranked = tuple(item[1] for item in indexed)
        with closing(self._connect()) as db, db:
            db.execute(
                "UPDATE memory_ranking_retrieval SET scored_candidate_ids_json=?,model_id=? "
                "WHERE retrieval_id=?",
                (json.dumps(tuple(item.id for item in ranked)), model[0], retrieval_id),
            )
        return ranked

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

    def record_truth_review(
        self, *, retrieval_id: str, candidate_id: UUID,
        principal: PrincipalContext, at: datetime,
        timeline_truth: str, correction_truth: str, source_accuracy: str,
    ) -> str:
        """Record an explicit evaluation label; never establish canonical fact."""
        moment = _utc(at)
        if not isinstance(principal, PrincipalContext) or principal.audience_kind is not AudienceKind.PRIVATE:
            raise PermissionError("authenticated private truth review required")
        if not isinstance(candidate_id, UUID):
            raise TypeError("candidate_id must be UUID")
        allowed = {"correct", "incorrect", "unknown"}
        values = (timeline_truth, correction_truth, source_accuracy)
        if any(value not in allowed for value in values):
            raise ValueError("truth review values must be correct, incorrect, or unknown")
        with closing(self._connect()) as db:
            retrieval = db.execute(
                "SELECT principal_id,audience_id,candidate_ids_json,retrieved_at "
                "FROM memory_ranking_retrieval WHERE retrieval_id=?",
                (retrieval_id,),
            ).fetchone()
        if (
            retrieval is None
            or retrieval[0] != principal.principal_id
            or retrieval[1] != principal.audience_id
            or str(candidate_id) not in json.loads(retrieval[2])
            or moment < datetime.fromisoformat(retrieval[3])
        ):
            raise PermissionError("truth review is outside this eligible retrieval")
        candidate = self._candidates.get(candidate_id)
        if (
            candidate is None
            or candidate.principal_id != principal.principal_id
            or candidate.audience_id not in (None, principal.audience_id)
        ):
            raise PermissionError("candidate source scope no longer matches reviewer")
        source_ids = tuple(
            f"{source.session_id}:{source.message_id}" for source in candidate.sources
        )
        body = {
            "retrieval": retrieval_id, "candidate": str(candidate_id),
            "timeline": timeline_truth, "correction": correction_truth,
            "source": source_accuracy, "at": moment.isoformat(),
        }
        review_id = "memory-truth-review:" + _digest(body)
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO memory_ranking_truth_review VALUES(?,?,?,?,?,?,?,?,?,?)",
                (review_id, retrieval_id, str(candidate_id), principal.principal_id,
                 principal.audience_id, timeline_truth, correction_truth,
                 source_accuracy, json.dumps(source_ids), moment.isoformat()),
            )
        return review_id

    def evaluate_future(self, *, principal: PrincipalContext, trained_before: datetime) -> RankingEvaluation:
        cutoff_value = _utc(trained_before)
        cutoff = cutoff_value.isoformat()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT r.retrieval_id,r.candidate_ids_json,r.scored_candidate_ids_json,"
                "r.model_id,j.candidate_id,j.judgment,r.principal_id,r.audience_id "
                "FROM memory_ranking_retrieval r JOIN memory_ranking_judgment j ON j.retrieval_id=r.retrieval_id "
                "WHERE r.principal_id=? AND r.audience_id=? AND r.retrieved_at>? AND j.valid=1",
                (principal.principal_id, principal.audience_id, cutoff),
            ).fetchall()
            truths = db.execute(
                "SELECT t.timeline_truth,t.correction_truth,t.source_accuracy,"
                "t.principal_id,t.audience_id FROM memory_ranking_truth_review t "
                "JOIN memory_ranking_retrieval r ON r.retrieval_id=t.retrieval_id "
                "WHERE r.principal_id=? AND r.audience_id=? AND r.retrieved_at>?",
                (principal.principal_id, principal.audience_id, cutoff),
            ).fetchall()
            model_times = dict(db.execute(
                "SELECT model_id,trained_at FROM memory_ranking_model"
            ).fetchall())

        grouped: dict[str, dict[str, object]] = {}
        violations = 0
        for retrieval_id, baseline_raw, scored_raw, model_id, candidate_id, judgment, row_principal, row_audience in rows:
            violations += int(
                row_principal != principal.principal_id
                or row_audience != principal.audience_id
            )
            item = grouped.setdefault(retrieval_id, {
                "baseline": tuple(json.loads(baseline_raw)),
                "scored": None if scored_raw is None else tuple(json.loads(scored_raw)),
                "model_id": model_id, "relevant": set(),
            })
            if judgment == RelevanceJudgment.RELEVANT.value:
                item["relevant"].add(candidate_id)

        def metrics(order: tuple[str, ...], relevant: set[str]) -> tuple[float, float]:
            if not relevant:
                return 0.0, 0.0
            top = order[:5]
            recall = len(relevant.intersection(top)) / len(relevant)
            dcg = sum(
                1.0 / math.log2(index + 2)
                for index, candidate_id in enumerate(top)
                if candidate_id in relevant
            )
            ideal = sum(
                1.0 / math.log2(index + 2)
                for index in range(min(5, len(relevant)))
            )
            return recall, (dcg / ideal if ideal else 0.0)

        baseline_metrics = []
        scorer_metrics = []
        for item in grouped.values():
            relevant = item["relevant"]
            if not relevant:
                continue
            baseline_metrics.append(metrics(item["baseline"], relevant))
            model_time = model_times.get(item["model_id"])
            if (
                item["scored"] is not None and model_time is not None
                and datetime.fromisoformat(model_time) <= cutoff_value
            ):
                scorer_metrics.append(metrics(item["scored"], relevant))

        def mean_at(values, index):
            return None if not values else sum(value[index] for value in values) / len(values)

        def accuracy(index):
            known = [row[index] for row in truths if row[index] != "unknown"]
            return None if not known else sum(value == "correct" for value in known) / len(known)

        violations += sum(
            row[3] != principal.principal_id or row[4] != principal.audience_id
            for row in truths
        )
        result = RankingEvaluation(
            sample_count=len(baseline_metrics),
            scored_sample_count=len(scorer_metrics),
            baseline_recall_at_5=mean_at(baseline_metrics, 0),
            scorer_recall_at_5=mean_at(scorer_metrics, 0),
            baseline_ndcg_at_5=mean_at(baseline_metrics, 1),
            scorer_ndcg_at_5=mean_at(scorer_metrics, 1),
            timeline_accuracy=accuracy(0), correction_accuracy=accuracy(1),
            source_accuracy=accuracy(2), cross_audience_violations=violations,
            independently_held_out=True,
        )
        evaluated_at = datetime.now(timezone.utc)
        payload = {
            field: getattr(result, field)
            for field in result.__dataclass_fields__
        }
        evaluation_id = "memory-ranking-evaluation:" + _digest({
            "scope": (principal.principal_id, principal.audience_id),
            "cutoff": cutoff, "at": evaluated_at.isoformat(), "metrics": payload,
        })
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO memory_ranking_evaluation VALUES(?,?,?,?,?,?)",
                (evaluation_id, principal.principal_id, principal.audience_id,
                 cutoff, evaluated_at.isoformat(), json.dumps(payload, sort_keys=True)),
            )
        return result

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
