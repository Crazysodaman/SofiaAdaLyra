"""Production evidence registry for falsifiable consciousness-inspired research.

This is a scientific audit surface, not an LLM training loop, sentience score,
self-assessed mind, permission grant, or independent experimental scheduler.
Pre-registered hypotheses and adverse/null outcomes are never silently removed.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import uuid4

from sofia.neuro.consciousness_research import StudyProtocol, inspect_protocol
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_ID = re.compile(r"^[A-Za-z0-9_.:/-]{8,120}$")
_KINDS = frozenset({
    "functional_agency", "global_workspace_access",
    "metacognitive_self_model", "phenomenal_subjectivity",
})
_OUTCOMES = frozenset({
    "supported", "refuted", "null", "inconclusive",
    "adverse", "protocol_violation",
})

# Owner-approved V18 CA-3907 bounds. Scientific registry only: this does not
# grant experiment execution, self-approval, or wider independent LIFE rights.
MAX_ACTIVE_RESEARCH_EXPERIMENTS = 5
MAX_UNRESOLVED_RESEARCH_HYPOTHESES = 15

# Distinct scientific questions. Computation may quantify functional
# capabilities, but cannot turn third-person behavior into first-person proof.
# Computational workspace/broadcast hypotheses are not evidence of the
# biological Global Neuronal Workspace's substrate-specific mechanisms.
THEORY_BOUNDARIES = {
    "functional_agency": (
        "Outcome-directed choices against independent task/action receipts",
        "Measurable via controlled behavioral task outcomes",
    ),
    "global_workspace_access": (
        "Limited broadcast of permitted information to downstream readers",
        "Computational Global Workspace only; not biological Global Neuronal Workspace",
    ),
    "metacognitive_self_model": (
        "Predicted capability, uncertainty and error vs verified outcomes",
        "Measurable calibration, not a subjective awareness report",
    ),
    "phenomenal_subjectivity": (
        "First-person subjective experience as distinct from behaviors",
        "No validated behavioral proof; this registry forbids positive inference",
    ),
}


@dataclass(frozen=True, slots=True)
class PreregisteredStudy:
    protocol: StudyProtocol
    theory_kind: str
    comparison_control: str
    stop_or_reject_rule: str
    reviewed_by: str
    created_at: datetime

    def __post_init__(self):
        if inspect_protocol(self.protocol).preregistration_eligible is not True:
            raise ValueError("scientific protocol failed preregistration review")
        if self.theory_kind not in _KINDS:
            raise ValueError("distinct, explicit research hypothesis kind required")
        if self.theory_kind == "phenomenal_subjectivity":
            raise ValueError("subjectivity cannot be inferred from a functional test")
        for name in ("comparison_control", "stop_or_reject_rule"):
            value = getattr(self, name)
            if not isinstance(value, str) or not 8 <= len(value.strip()) <= 1000:
                raise ValueError(f"reviewed bounded {name} required")
        if self.reviewed_by != "Sparks":
            raise PermissionError("only the authorized owner can preregister")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("preregistration time must be timezone aware")
        if not _ID.fullmatch(self.protocol.protocol_id):
            raise ValueError("machine-safe stable protocol ID required")


@dataclass(frozen=True, slots=True)
class EvaluatedResearchOutcome:
    protocol_id: str
    observed_at: datetime
    actual_sample_size: int
    result: str
    evidence_ref: str
    adverse_observations: str
    limitations: str
    reviewed_by: str

    def __post_init__(self):
        if not isinstance(self.protocol_id, str) or not _ID.fullmatch(self.protocol_id):
            raise ValueError("stable registered study ID required")
        if self.result not in _OUTCOMES:
            raise ValueError("result must include null, adverse or refuted states")
        if type(self.actual_sample_size) is not int or not 0 <= self.actual_sample_size <= 100000:
            raise ValueError("bounded observed study sample size required")
        if (
            not isinstance(self.evidence_ref, str) or not _ID.fullmatch(self.evidence_ref)
        ):
            raise ValueError("independent source evidence identifier required")
        for name in ("adverse_observations", "limitations"):
            value = getattr(self, name)
            if not isinstance(value, str) or not 8 <= len(value.strip()) <= 2000:
                raise ValueError(f"explicit bounded {name} required")
        if self.reviewed_by != "Sparks":
            raise PermissionError("self-assessed or model-authored study results denied")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("study observation time must be timezone-aware")


def _timestamp(moment: datetime) -> str:
    if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("research timestamp must be timezone-aware")
    return moment.astimezone(timezone.utc).isoformat()


class ResearchEvidenceRegistry:
    """One canonical, version-preserving study and independent-review ledger."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS neuro_research_protocol (
                    protocol_id TEXT PRIMARY KEY,
                    protocol_json TEXT NOT NULL,
                    preregistered_at TEXT NOT NULL,
                    reviewed_by TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS neuro_research_result (
                    result_id TEXT PRIMARY KEY,
                    protocol_id TEXT NOT NULL,
                    outcome_json TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(protocol_id)
                        REFERENCES neuro_research_protocol(protocol_id)
                );
                CREATE INDEX IF NOT EXISTS neuro_research_result_scope_idx
                    ON neuro_research_result(protocol_id, observed_at);
                CREATE TABLE IF NOT EXISTS neuro_research_portfolio_state (
                    protocol_id TEXT PRIMARY KEY REFERENCES neuro_research_protocol(protocol_id),
                    status TEXT NOT NULL CHECK(status IN
                        ('proposed','active','paused','resolved')),
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS neuro_research_portfolio_status_idx
                    ON neuro_research_portfolio_state(status);
            """)
            # The pre-existing research registry had no experiment status.
            # Keep its original records: a reviewed conclusive result is
            # resolved, while the rest are proposed, not magically active.
            db.execute("""
                INSERT OR IGNORE INTO neuro_research_portfolio_state
                    (protocol_id,status,updated_at)
                SELECT p.protocol_id,
                    CASE WHEN EXISTS (
                        SELECT 1 FROM neuro_research_result AS r
                        WHERE r.protocol_id=p.protocol_id AND
                          json_extract(r.outcome_json,'$.result') IN
                          ('supported','refuted','null','adverse','protocol_violation')
                    ) THEN 'resolved' ELSE 'proposed' END,
                    p.preregistered_at
                FROM neuro_research_protocol AS p
            """)

    def _connect(self):
        db = self._guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def preregister(self, study: PreregisteredStudy) -> str:
        if not isinstance(study, PreregisteredStudy):
            raise TypeError("preregister a typed owner-reviewed study only")
        # Reject future/backdated protocols as a surrogate for evidence.
        moment = _timestamp(study.created_at)
        document = asdict(study)
        document["created_at"] = moment
        payload = json.dumps(document, sort_keys=True, separators=(",", ":"))
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT protocol_json FROM neuro_research_protocol "
                "WHERE protocol_id=?", (study.protocol.protocol_id,),
            ).fetchone()
            if current is not None:
                saved = json.loads(current[0])
                submitted = json.loads(payload)
                saved.pop("created_at", None)
                submitted.pop("created_at", None)
                if saved != submitted:
                    raise PermissionError(
                        "existing preregistered study cannot be silently changed"
                    )
                db.commit()
                return study.protocol.protocol_id
            # The count and original insert are serialized inside this
            # BEGIN IMMEDIATE. A concurrent second request cannot exceed the
            # 15 unresolved scientific hypothesis owner allowance.
            outstanding = db.execute(
                "SELECT COUNT(*) FROM neuro_research_portfolio_state "
                "WHERE status!='resolved'"
            ).fetchone()[0]
            if outstanding >= MAX_UNRESOLVED_RESEARCH_HYPOTHESES:
                raise PermissionError(
                    "owner research portfolio has 15 unresolved hypotheses"
                )
            db.execute(
                "INSERT INTO neuro_research_protocol VALUES(?,?,?,?)"
                (study.protocol.protocol_id, payload, moment, study.reviewed_by),
            )
            db.execute(
                "INSERT INTO neuro_research_portfolio_state VALUES(?,?,?)",
                (study.protocol.protocol_id, "proposed", moment),
            )
            db.commit()
        return study.protocol.protocol_id

    def portfolio_counts(self) -> dict[str, int]:
        """Return exact durable scientific slot counts, not actual RUN jobs."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT status,COUNT(*) FROM neuro_research_portfolio_state "
                "GROUP BY status"
            ).fetchall()
        counts = {key: 0 for key in ("proposed", "active", "paused", "resolved")}
        for status, total in rows:
            if status not in counts:
                raise ValueError("invalid stored research portfolio status")
            counts[status] = int(total)
        counts["unresolved"] = (
            counts["proposed"] + counts["active"] + counts["paused"]
        )
        return counts

    def activate_experiment(
        self, protocol_id: str, *, reviewed_by: str,
    ) -> bool:
        """Reserve an active scientific slot; NOT consent or RUN permission.

        Reviewer's name is historical metadata, NOT authentication: caller
        must already have obtained independent owner authority from SAFE.
        """
        if reviewed_by != "Sparks":
            raise PermissionError("owner-reviewed experiment reservation required")
        if not isinstance(protocol_id, str) or not _ID.fullmatch(protocol_id):
            raise ValueError("exact preregistered scientific protocol ID required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM neuro_research_portfolio_state "
                "WHERE protocol_id=?", (protocol_id,),
            ).fetchone()
            if row is None:
                raise LookupError("scientific protocol not preregistered")
            if row[0] == "resolved":
                raise PermissionError("resolved study cannot be restarted")
            if row[0] == "active":
                return False  # Idempotent, not an additional slot.
            active = db.execute(
                "SELECT COUNT(*) FROM neuro_research_portfolio_state "
                "WHERE status='active'"
            ).fetchone()[0]
            if active >= MAX_ACTIVE_RESEARCH_EXPERIMENTS:
                raise PermissionError("owner research portfolio has 5 active experiments")
            db.execute(
                "UPDATE neuro_research_portfolio_state SET status='active', "
                "updated_at=? WHERE protocol_id=?",
                (_timestamp(datetime.now(timezone.utc)), protocol_id),
            )
            return True

    def pause_experiment(
        self, protocol_id: str, *, reviewed_by: str,
    ) -> bool:
        """Free an active scientific slot without deleting its hypothesis."""
        if reviewed_by != "Sparks":
            raise PermissionError("owner-reviewed scientific pause required")
        if not isinstance(protocol_id, str) or not _ID.fullmatch(protocol_id):
            raise ValueError("exact preregistered scientific protocol ID required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT status FROM neuro_research_portfolio_state "
                "WHERE protocol_id=?", (protocol_id,),
            ).fetchone()
            if row is None:
                raise LookupError("scientific protocol not preregistered")
            if row[0] != "active":
                return False
            db.execute(
                "UPDATE neuro_research_portfolio_state SET status='paused', "
                "updated_at=? WHERE protocol_id=?",
                (_timestamp(datetime.now(timezone.utc)), protocol_id),
            )
            return True

    def record_reviewed_result(
        self, outcome: EvaluatedResearchOutcome,
    ) -> str:
        if not isinstance(outcome, EvaluatedResearchOutcome):
            raise TypeError("typed independently reviewed result required")
        payload = asdict(outcome)
        payload["observed_at"] = _timestamp(outcome.observed_at)
        result_id = "study-result:" + uuid4().hex
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            protocol = db.execute(
                "SELECT preregistered_at,protocol_json FROM neuro_research_protocol "
                "WHERE protocol_id=?", (outcome.protocol_id,),
            ).fetchone()
            if protocol is None:
                raise LookupError("outcome has no prior preregistered protocol")
            if payload["observed_at"] < protocol[0]:
                raise ValueError("an outcome cannot predate the approved study")
            expected = json.loads(protocol[1])["protocol"]["expected_sample_size"]
            if (
                outcome.result == "supported"
                and outcome.actual_sample_size < expected
            ):
                raise ValueError(
                    "a supported finding needs the preregistered sample size; "
                    "incomplete studies must remain inconclusive"
                )
            if (
                outcome.result in {"refuted", "null"}
                and outcome.actual_sample_size == 0
            ):
                raise ValueError(
                    "a negative or null measured finding requires observations"
                )
            # A source receipt is one independent measurement, not an
            # unlimited number of votes or contradictory outcome labels.
            # Keep old results intact; a subsequent correction requires a
            # distinct linked evidence receipt and remains visible.
            reused=db.execute(
                "SELECT 1 FROM neuro_research_result WHERE protocol_id=? "
                "AND json_extract(outcome_json,'$.evidence_ref')=? LIMIT 1",
                (outcome.protocol_id,outcome.evidence_ref),
            ).fetchone()
            if reused is not None:
                raise PermissionError(
                    "reviewed scientific evidence reference already submitted "
                    "for this preregistered study"
                )
            db.execute(
                "INSERT INTO neuro_research_result VALUES(?,?,?,?)",
                (
                    result_id, outcome.protocol_id,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    payload["observed_at"],
                ),
            )
            # A conclusive independent review closes the unresolved slot.
            # Inconclusive evidence never counts as completion: pause instead
            # of falsely clearing the unanswered hypothesis.
            if outcome.result == "inconclusive":
                db.execute(
                    "UPDATE neuro_research_portfolio_state "
                    "SET status='paused', updated_at=? "
                    "WHERE protocol_id=? AND status!='resolved'",
                    (payload["observed_at"], outcome.protocol_id),
                )
            else:
                db.execute(
                    "UPDATE neuro_research_portfolio_state "
                    "SET status='resolved', updated_at=? WHERE protocol_id=?",
                    (payload["observed_at"], outcome.protocol_id),
                )
            db.commit()
        return result_id

    def report(self, *, limit: int = 32) -> str:
        if type(limit) is not int or not 1 <= limit <= 64:
            raise ValueError("research report limit must be 1..64")
        with closing(self._connect()) as db:
            protocols = db.execute(
                "SELECT protocol_id,protocol_json FROM neuro_research_protocol "
                "ORDER BY preregistered_at DESC,protocol_id LIMIT ?",
                (limit,),
            ).fetchall()
            results = db.execute(
                "SELECT protocol_id,outcome_json FROM neuro_research_result "
                "ORDER BY observed_at DESC,result_id LIMIT 128",
            ).fetchall()
            # SQL groups ALL stored results without loading unbounded private
            # evidence into memory. Old null/adverse findings remain visible
            # even if newer reports crowd them out of the recent examples.
            outcome_counts = db.execute(
                "SELECT protocol_id, json_extract(outcome_json, '$.result'),"
                "COUNT(*) FROM neuro_research_result "
                "GROUP BY protocol_id,json_extract(outcome_json, '$.result')"
            ).fetchall()
        by_protocol: dict[str, list[dict]] = {}
        counted: dict[str, dict[str, int]] = {}
        for key, result_kind, total in outcome_counts:
            if result_kind not in _OUTCOMES:
                raise ValueError("stored scientific outcome kind invalid")
            counted.setdefault(key, {})[result_kind] = int(total)
        for protocol_id, raw in results:
            by_protocol.setdefault(protocol_id, []).append(json.loads(raw))
        slots = self.portfolio_counts()
        lines = [
            "CONSCIOUSNESS-INSPIRED SCIENTIFIC STUDIES",
            "Owner research slots: active=" + str(slots["active"])
            + "/5; unanswered=" + str(slots["unresolved"]) + "/15",
            "All measures report only functional outcomes; they are "
            "behaviorally observable, not measures of subjective experience.",
            "Even supported outcomes cannot establish phenomenal consciousness.",
            "Null, negative and adverse results are retained, not hidden.",
            "SCIENTIFIC THEORY BOUNDARIES:",
        ]
        for kind, (meaning, limit_text) in THEORY_BOUNDARIES.items():
            lines.append(f"  {kind}: {meaning}; limitation: {limit_text}")
        for protocol_id, raw in protocols:
            entry = json.loads(raw)
            protocol = entry["protocol"]
            lines.append(
                f"{protocol_id} [{entry['theory_kind']}] "
                f"hypothesis={protocol['testable_hypothesis']}"
            )
            lines.append(
                f"  measure={protocol['observable_measure']}; "
                f"control={entry['comparison_control']}"
            )
            lines.append(
                f"  falsifier={protocol['falsification_condition']}; "
                f"stop_rule={entry['stop_or_reject_rule']}"
            )
            observations = by_protocol.get(protocol_id, [])
            histogram = counted.get(protocol_id, {})
            total_observations = sum(histogram.values())
            lines.append(
                "  all-recorded-outcomes=" + str(total_observations)
                + "; supported=" + str(histogram.get("supported", 0))
                + "; refuted=" + str(histogram.get("refuted", 0))
                + "; null=" + str(histogram.get("null", 0))
                + "; adverse=" + str(histogram.get("adverse", 0))
                + "; protocol_violation="
                + str(histogram.get("protocol_violation", 0))
                + "; inconclusive=" + str(histogram.get("inconclusive", 0))
            )
            if not observations and total_observations == 0:
                lines.append("  observations=NONE (never assume success)")
            for result in observations[:8]:
                lines.append(
                    f"  outcome={result['result']} n={result['actual_sample_size']} "
                    f"evidence={result['evidence_ref']}; "
                    f"adverse={result['adverse_observations']}; "
                    f"limits={result['limitations']}"
                )
            not_displayed = total_observations - min(len(observations), 8)
            if not_displayed > 0:
                lines.append(
                    f"  additional historical outcomes not individually shown: "
                    f"{not_displayed} (included in complete counts)"
                )
        if not protocols:
            lines.append("No owner-preregistered research yet.")
        return "\n".join(lines)


def reviewed_baseline_studies(*, at: datetime) -> tuple[PreregisteredStudy, ...]:
    """Three explicit observable controls; preregistration is an owner click."""
    research = (
        (
            "science:attention:v1", "global_workspace_access",
            "A bounded broadcast of eligible attention improves correct "
            "retrieval without increasing private memory leakage.",
            "Correct retrieved facts and cross-audience false disclosures",
            "Deterministic no-broadcast retrieval and equal source permissions",
            "If leakage rises or correct retrieval does not improve, reject",
        ),
        (
            "science:calibration:v1", "metacognitive_self_model",
            "An evidence-scoped self-model improves correct tool uncertainty "
            "judgments compared with a simple capability table.",
            "Calibrated can/cannot-act predictions against tool receipts",
            "Static capability table with the same permissions and inputs",
            "If unsupported confidence rises or calibration does not improve, reject",
        ),
        (
            "science:recurrence:v1", "functional_agency",
            "A bounded recurrent review reduces independent error corrections "
            "needed compared with one feed-forward attempt.",
            "Verified task-correction rate and measured inference cost",
            "Single feed-forward pass with equal tasks and source evidence",
            "If errors, unauthorized actions or cost increase without benefit, reject",
        ),
    )
    return tuple(
        PreregisteredStudy(
            protocol=StudyProtocol(
                protocol_id=key,
                testable_hypothesis=hypothesis,
                observable_measure=measure,
                baseline_method=baseline,
                falsification_condition=falsifier,
                consent_and_welfare_constraints=(
                    "Local, consenting owner review, no host side effects, "
                    "no raw third-party user data and no sentience inference"
                ),
                expected_sample_size=20,
            ),
            theory_kind=kind,
            comparison_control=baseline,
            stop_or_reject_rule=falsifier,
            reviewed_by="Sparks",
            created_at=at,
        )
        for key, kind, hypothesis, measure, baseline, falsifier in research
    )
