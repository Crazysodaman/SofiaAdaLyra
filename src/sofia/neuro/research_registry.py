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
            db.execute(
                "INSERT INTO neuro_research_protocol VALUES(?,?,?,?)",
                (study.protocol.protocol_id, payload, moment, study.reviewed_by),
            )
            db.commit()
        return study.protocol.protocol_id

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
                "SELECT preregistered_at FROM neuro_research_protocol "
                "WHERE protocol_id=?", (outcome.protocol_id,),
            ).fetchone()
            if protocol is None:
                raise LookupError("outcome has no prior preregistered protocol")
            if payload["observed_at"] < protocol[0]:
                raise ValueError("an outcome cannot predate the approved study")
            db.execute(
                "INSERT INTO neuro_research_result VALUES(?,?,?,?)",
                (
                    result_id, outcome.protocol_id,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    payload["observed_at"],
                ),
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
        by_protocol: dict[str, list[dict]] = {}
        for protocol_id, raw in results:
            by_protocol.setdefault(protocol_id, []).append(json.loads(raw))
        lines = [
            "CONSCIOUSNESS-INSPIRED SCIENTIFIC STUDIES",
            "All measures are behavioral/functionally observable only.",
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
            if not observations:
                lines.append("  observations=NONE (never assume success)")
            for result in observations[:8]:
                lines.append(
                    f"  outcome={result['result']} n={result['actual_sample_size']} "
                    f"evidence={result['evidence_ref']}; "
                    f"adverse={result['adverse_observations']}; "
                    f"limits={result['limitations']}"
                )
            if len(observations) > 8:
                lines.append(f"  additional outcomes: {len(observations)-8}")
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
