"""Durable evidence, proposal lifecycle, and outcome records for EVOLVE.

The mutation executors intentionally remain small and storage-neutral.  This
module owns the higher-level record of what was proposed, which evidence was
reviewed, what success means, and whether an applied change helped.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .amendment import AmendmentProposal, ProtectedTarget
from .code import CodeEvolutionProposal
from .revision import RevisionProposal, RevisionScope


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_OPEN_STATUSES = (
    "proposed",
    "under_review",
    "approved",
    "candidate_built",
    "verified",
    "applied_pending_activation",
    "committed_pending_release",
    "rollback_required",
    "evaluating",
)


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


class EvolutionProposalKind(str, Enum):
    REVISION = "revision"
    AMENDMENT = "amendment"
    CODE = "code"


class EvolutionProposalStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    CANDIDATE_BUILT = "candidate_built"
    VERIFIED = "verified"
    REJECTED = "rejected"
    APPLIED_PENDING_ACTIVATION = "applied_pending_activation"
    COMMITTED_PENDING_RELEASE = "committed_pending_release"
    ROLLBACK_REQUIRED = "rollback_required"
    EVALUATING = "evaluating"
    ACCEPTED = "accepted"
    ROLLED_BACK = "rolled_back"


class EvolutionOutcome(str, Enum):
    IMPROVED = "improved"
    NO_CHANGE = "no_change"
    REGRESSED = "regressed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class EvolutionEvidence:
    evidence_id: str
    kind: str
    source_ref: str
    summary: str
    payload: dict[str, object]
    observed_at: datetime
    recorded_at: datetime

    def __post_init__(self) -> None:
        _identifier(self.evidence_id, "evidence_id")
        _identifier(self.kind, "evidence kind")
        if not isinstance(self.source_ref, str) or not self.source_ref.strip():
            raise ValueError("evidence source_ref must be nonempty")
        if not isinstance(self.summary, str) or not self.summary.strip() or len(self.summary) > 2000:
            raise ValueError("evidence summary must be bounded nonempty text")
        if not isinstance(self.payload, dict):
            raise TypeError("evidence payload must be a dictionary")
        _utc(self.observed_at)
        _utc(self.recorded_at)

    @property
    def payload_sha256(self) -> str:
        return sha256(
            json.dumps(
                self.payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class EvolutionProposalRecord:
    proposal_id: str
    kind: EvolutionProposalKind
    target: str
    fingerprint: str
    proposed_content: str
    success_metric: str
    status: EvolutionProposalStatus
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EvolutionOutcomeRecord:
    proposal_id: str
    outcome: EvolutionOutcome
    evidence_id: str
    notes: str
    measured_at: datetime


class EvolutionLifecycleStore:
    """Canonical SQLite proposal/evidence/outcome store."""

    def __init__(self, state_path: Path | str, *, daily_proposal_limit: int = 10) -> None:
        self.path = Path(state_path)
        if type(daily_proposal_limit) is not int or daily_proposal_limit < 1:
            raise ValueError("daily_proposal_limit must be a positive integer")
        self.daily_proposal_limit = daily_proposal_limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            self._migrate_code_proposal_kind(db)
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS evolve_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evolve_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('revision','amendment','code')),
                    target TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    proposed_content TEXT NOT NULL,
                    success_metric TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    activated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS evolve_proposals_target_status
                    ON evolve_proposals(target, status);
                CREATE TABLE IF NOT EXISTS evolve_proposal_evidence (
                    proposal_id TEXT NOT NULL REFERENCES evolve_proposals(proposal_id),
                    evidence_id TEXT NOT NULL REFERENCES evolve_evidence(evidence_id),
                    PRIMARY KEY (proposal_id, evidence_id)
                );
                CREATE TABLE IF NOT EXISTS evolve_outcomes (
                    proposal_id TEXT PRIMARY KEY REFERENCES evolve_proposals(proposal_id),
                    outcome TEXT NOT NULL,
                    evidence_id TEXT NOT NULL REFERENCES evolve_evidence(evidence_id),
                    notes TEXT NOT NULL,
                    measured_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _migrate_code_proposal_kind(db: sqlite3.Connection) -> None:
        """Expand the original two-kind CHECK without losing proposal history."""

        row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='evolve_proposals'"
        ).fetchone()
        if row is None or "'code'" in (row[0] or ""):
            return
        db.execute("PRAGMA foreign_keys=OFF")
        db.executescript(
            """
            CREATE TABLE evolve_proposals_new (
                proposal_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK(kind IN ('revision','amendment','code')),
                target TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                proposed_content TEXT NOT NULL,
                success_metric TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                activated_at TEXT
            );
            INSERT INTO evolve_proposals_new
            SELECT proposal_id,kind,target,fingerprint,proposal_json,
                   proposed_content,success_metric,status,created_at,updated_at,
                   activated_at
            FROM evolve_proposals;
            DROP TABLE evolve_proposals;
            ALTER TABLE evolve_proposals_new RENAME TO evolve_proposals;
            """
        )
        db.execute("PRAGMA foreign_keys=ON")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def record_evidence(self, evidence: EvolutionEvidence) -> EvolutionEvidence:
        if not isinstance(evidence, EvolutionEvidence):
            raise TypeError("evidence must be EvolutionEvidence")
        payload_json = json.dumps(
            evidence.payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT kind,source_ref,summary,payload_sha256,observed_at,recorded_at "
                "FROM evolve_evidence WHERE evidence_id=?",
                (evidence.evidence_id,),
            ).fetchone()
            if existing is not None:
                expected = (
                    evidence.kind,
                    evidence.source_ref,
                    evidence.summary.strip(),
                    evidence.payload_sha256,
                    _utc(evidence.observed_at).isoformat(),
                    _utc(evidence.recorded_at).isoformat(),
                )
                if tuple(existing) != expected:
                    raise ValueError("evidence_id already records different evidence")
                return self.get_evidence(evidence.evidence_id)
            db.execute(
                """
                INSERT INTO evolve_evidence
                (evidence_id,kind,source_ref,summary,payload_json,payload_sha256,
                 observed_at,recorded_at) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    evidence.evidence_id,
                    evidence.kind,
                    evidence.source_ref,
                    evidence.summary.strip(),
                    payload_json,
                    evidence.payload_sha256,
                    _utc(evidence.observed_at).isoformat(),
                    _utc(evidence.recorded_at).isoformat(),
                ),
            )
        return evidence

    def get_evidence(self, evidence_id: str) -> EvolutionEvidence:
        _identifier(evidence_id, "evidence_id")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT evidence_id,kind,source_ref,summary,payload_json,payload_sha256,"
                "observed_at,recorded_at "
                "FROM evolve_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
        if row is None:
            raise LookupError("EVOLVE evidence does not exist")
        evidence = EvolutionEvidence(
            evidence_id=row[0],
            kind=row[1],
            source_ref=row[2],
            summary=row[3],
            payload=json.loads(row[4]),
            observed_at=datetime.fromisoformat(row[6]),
            recorded_at=datetime.fromisoformat(row[7]),
        )
        if evidence.payload_sha256 != row[5]:
            raise RuntimeError("EVOLVE evidence payload digest mismatch")
        return evidence

    def list_evidence(self, *, limit: int = 50) -> tuple[EvolutionEvidence, ...]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be in 1..200")
        with closing(self._connect()) as db:
            ids = tuple(
                row[0]
                for row in db.execute(
                    "SELECT evidence_id FROM evolve_evidence "
                    "ORDER BY observed_at DESC, evidence_id LIMIT ?",
                    (limit,),
                )
            )
        return tuple(self.get_evidence(item) for item in ids)

    @staticmethod
    def _proposal_document(
        proposal: RevisionProposal | AmendmentProposal | CodeEvolutionProposal,
    ) -> dict[str, object]:
        document = asdict(proposal)
        if isinstance(proposal, RevisionProposal):
            document["scope"] = proposal.scope.value
        elif isinstance(proposal, AmendmentProposal):
            document["target"] = proposal.target.value
        document["created_at"] = _utc(proposal.created_at).isoformat()
        document["expires_at"] = _utc(proposal.expires_at).isoformat()
        document["evidence_ids"] = list(proposal.evidence_ids)
        return document

    @staticmethod
    def _target(
        proposal: RevisionProposal | AmendmentProposal | CodeEvolutionProposal,
    ) -> str:
        if isinstance(proposal, RevisionProposal):
            return f"{proposal.scope.value}:{proposal.key}"
        if isinstance(proposal, AmendmentProposal):
            return f"protected:{proposal.target.value}"
        return proposal.target

    @staticmethod
    def _paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        return any(
            a == b or a.startswith(b + "/") or b.startswith(a + "/")
            for a in left
            for b in right
        )

    def add_proposal(
        self,
        proposal: RevisionProposal | AmendmentProposal | CodeEvolutionProposal,
        *,
        proposed_content: str,
        success_metric: str,
        now: datetime,
    ) -> EvolutionProposalRecord:
        if not isinstance(
            proposal,
            (RevisionProposal, AmendmentProposal, CodeEvolutionProposal),
        ):
            raise TypeError("proposal must be a revision, amendment, or code proposal")
        if not isinstance(proposed_content, str):
            raise TypeError("proposed_content must be text")
        if not isinstance(success_metric, str) or not success_metric.strip() or len(success_metric) > 1000:
            raise ValueError("bounded success_metric required")
        moment = _utc(now)
        if isinstance(proposal, RevisionProposal):
            kind = EvolutionProposalKind.REVISION
        elif isinstance(proposal, AmendmentProposal):
            kind = EvolutionProposalKind.AMENDMENT
        else:
            kind = EvolutionProposalKind.CODE
        target = self._target(proposal)
        document_json = json.dumps(
            self._proposal_document(proposal),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT fingerprint FROM evolve_proposals WHERE proposal_id=?",
                (proposal.proposal_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] != proposal.fingerprint:
                    raise ValueError("proposal_id already records a different proposal")
                return self.get_proposal(proposal.proposal_id)
            for evidence_id in proposal.evidence_ids:
                if db.execute(
                    "SELECT 1 FROM evolve_evidence WHERE evidence_id=?",
                    (evidence_id,),
                ).fetchone() is None:
                    raise ValueError(f"proposal evidence does not exist: {evidence_id}")
            start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
            count = db.execute(
                "SELECT COUNT(*) FROM evolve_proposals WHERE created_at>=?",
                (start.isoformat(),),
            ).fetchone()[0]
            if count >= self.daily_proposal_limit:
                raise RuntimeError("daily EVOLVE proposal budget exhausted")
            duplicate = db.execute(
                "SELECT proposal_id FROM evolve_proposals WHERE target=? AND status IN "
                f"({','.join('?' for _ in _OPEN_STATUSES)})",
                (target, *_OPEN_STATUSES),
            ).fetchone()
            if duplicate is not None:
                raise RuntimeError(
                    f"an open EVOLVE proposal already owns this target: {duplicate[0]}"
                )
            if isinstance(proposal, CodeEvolutionProposal):
                open_code = db.execute(
                    "SELECT proposal_id,proposal_json FROM evolve_proposals "
                    "WHERE kind='code' AND status IN "
                    f"({','.join('?' for _ in _OPEN_STATUSES)})",
                    _OPEN_STATUSES,
                ).fetchall()
                for open_id, raw in open_code:
                    document = json.loads(raw)
                    if self._paths_overlap(
                        proposal.allowed_paths,
                        tuple(document["allowed_paths"]),
                    ):
                        raise RuntimeError(
                            "an open EVOLVE code proposal overlaps approved scope: "
                            f"{open_id}"
                        )
            db.execute(
                """
                INSERT INTO evolve_proposals
                (proposal_id,kind,target,fingerprint,proposal_json,proposed_content,
                 success_metric,status,created_at,updated_at,activated_at)
                VALUES (?,?,?,?,?,?,?,'proposed',?,?,NULL)
                """,
                (
                    proposal.proposal_id,
                    kind.value,
                    target,
                    proposal.fingerprint,
                    document_json,
                    proposed_content,
                    success_metric.strip(),
                    _utc(proposal.created_at).isoformat(),
                    moment.isoformat(),
                ),
            )
            db.executemany(
                "INSERT INTO evolve_proposal_evidence(proposal_id,evidence_id) VALUES (?,?)",
                ((proposal.proposal_id, item) for item in proposal.evidence_ids),
            )
        return self.get_proposal(proposal.proposal_id)

    @staticmethod
    def _record(row: tuple) -> EvolutionProposalRecord:
        return EvolutionProposalRecord(
            proposal_id=row[0],
            kind=EvolutionProposalKind(row[1]),
            target=row[2],
            fingerprint=row[3],
            proposed_content=row[4],
            success_metric=row[5],
            status=EvolutionProposalStatus(row[6]),
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
            activated_at=(datetime.fromisoformat(row[9]) if row[9] else None),
        )

    def get_proposal(self, proposal_id: str) -> EvolutionProposalRecord:
        _identifier(proposal_id, "proposal_id")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT proposal_id,kind,target,fingerprint,proposed_content,success_metric,"
                "status,created_at,updated_at,activated_at FROM evolve_proposals "
                "WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise LookupError("EVOLVE proposal does not exist")
        return self._record(row)

    def proposal_object(
        self,
        proposal_id: str,
    ) -> RevisionProposal | AmendmentProposal | CodeEvolutionProposal:
        _identifier(proposal_id, "proposal_id")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT kind,proposal_json FROM evolve_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            raise LookupError("EVOLVE proposal does not exist")
        data = json.loads(row[1])
        data["evidence_ids"] = tuple(data["evidence_ids"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        if EvolutionProposalKind(row[0]) is EvolutionProposalKind.REVISION:
            data["scope"] = RevisionScope(data["scope"])
            return RevisionProposal(**data)
        if EvolutionProposalKind(row[0]) is EvolutionProposalKind.AMENDMENT:
            data["target"] = ProtectedTarget(data["target"])
            return AmendmentProposal(**data)
        data["allowed_paths"] = tuple(data["allowed_paths"])
        data["tests"] = tuple(data["tests"])
        return CodeEvolutionProposal(**data)

    def attach_evidence(self, proposal_id: str, evidence_id: str) -> None:
        """Attach newly produced evidence without rewriting the reviewed proposal."""

        _identifier(proposal_id, "proposal_id")
        self.get_evidence(evidence_id)
        with closing(self._connect()) as db, db:
            if db.execute(
                "SELECT 1 FROM evolve_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone() is None:
                raise LookupError("EVOLVE proposal does not exist")
            db.execute(
                "INSERT OR IGNORE INTO evolve_proposal_evidence(proposal_id,evidence_id) "
                "VALUES (?,?)",
                (proposal_id, evidence_id),
            )

    def proposal_evidence(self, proposal_id: str) -> tuple[EvolutionEvidence, ...]:
        _identifier(proposal_id, "proposal_id")
        with closing(self._connect()) as db:
            ids = tuple(
                row[0]
                for row in db.execute(
                    "SELECT evidence_id FROM evolve_proposal_evidence "
                    "WHERE proposal_id=? ORDER BY evidence_id",
                    (proposal_id,),
                )
            )
        if not ids and not self._proposal_exists(proposal_id):
            raise LookupError("EVOLVE proposal does not exist")
        return tuple(self.get_evidence(item) for item in ids)

    def _proposal_exists(self, proposal_id: str) -> bool:
        with closing(self._connect()) as db:
            return db.execute(
                "SELECT 1 FROM evolve_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone() is not None

    def list_proposals(self, *, limit: int = 50) -> tuple[EvolutionProposalRecord, ...]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be in 1..200")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT proposal_id,kind,target,fingerprint,proposed_content,success_metric,"
                "status,created_at,updated_at,activated_at FROM evolve_proposals "
                "ORDER BY created_at DESC, proposal_id LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def transition(
        self,
        proposal_id: str,
        *,
        expected: tuple[EvolutionProposalStatus, ...],
        status: EvolutionProposalStatus,
        now: datetime,
    ) -> EvolutionProposalRecord:
        if not isinstance(status, EvolutionProposalStatus):
            raise TypeError("status must be EvolutionProposalStatus")
        if not expected or not all(isinstance(item, EvolutionProposalStatus) for item in expected):
            raise TypeError("expected must contain proposal statuses")
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "UPDATE evolve_proposals SET status=?,updated_at=?,activated_at="
                "CASE WHEN ?='evaluating' THEN ? ELSE activated_at END "
                f"WHERE proposal_id=? AND status IN ({','.join('?' for _ in expected)})",
                (
                    status.value,
                    moment.isoformat(),
                    status.value,
                    moment.isoformat(),
                    proposal_id,
                    *(item.value for item in expected),
                ),
            )
            if changed.rowcount != 1:
                raise RuntimeError("EVOLVE proposal lifecycle transition refused")
        return self.get_proposal(proposal_id)

    def record_outcome(
        self,
        proposal_id: str,
        *,
        outcome: EvolutionOutcome,
        evidence_id: str,
        notes: str,
        measured_at: datetime,
    ) -> EvolutionOutcomeRecord:
        if not isinstance(outcome, EvolutionOutcome):
            raise TypeError("outcome must be EvolutionOutcome")
        self.get_evidence(evidence_id)
        if not isinstance(notes, str) or not notes.strip() or len(notes) > 2000:
            raise ValueError("bounded outcome notes required")
        moment = _utc(measured_at)
        terminal = (
            EvolutionProposalStatus.ACCEPTED
            if outcome is EvolutionOutcome.IMPROVED
            else EvolutionProposalStatus.UNDER_REVIEW
        )
        with closing(self._connect()) as db, db:
            current = db.execute(
                "SELECT status FROM evolve_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if current is None:
                raise LookupError("EVOLVE proposal does not exist")
            if current[0] != EvolutionProposalStatus.EVALUATING.value:
                raise RuntimeError("only an effective evaluating proposal can record outcome")
            db.execute(
                "INSERT INTO evolve_outcomes(proposal_id,outcome,evidence_id,notes,measured_at) "
                "VALUES (?,?,?,?,?)",
                (proposal_id, outcome.value, evidence_id, notes.strip(), moment.isoformat()),
            )
            db.execute(
                "UPDATE evolve_proposals SET status=?,updated_at=? WHERE proposal_id=?",
                (terminal.value, moment.isoformat(), proposal_id),
            )
        return EvolutionOutcomeRecord(
            proposal_id=proposal_id,
            outcome=outcome,
            evidence_id=evidence_id,
            notes=notes.strip(),
            measured_at=moment,
        )
