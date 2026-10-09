"""Durable subject-scoped evidence ledger and truth maintenance."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from sofia.capability.model import CapabilityResult, CapabilityResultKind

from .contracts import AcquisitionState, EpistemicState, EvidenceAtom, EvidenceNeed


@dataclass(frozen=True, slots=True)
class EvidenceResolution:
    need: EvidenceNeed
    acquisition_state: AcquisitionState
    atoms: tuple[EvidenceAtom, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.need, EvidenceNeed):
            raise TypeError("need must be EvidenceNeed")
        if not isinstance(self.acquisition_state, AcquisitionState):
            raise TypeError("acquisition_state must be AcquisitionState")
        if not isinstance(self.atoms, tuple) or any(
            not isinstance(atom, EvidenceAtom) for atom in self.atoms
        ):
            raise TypeError("atoms must contain EvidenceAtom values")
        if any(
            atom.subject_id != self.need.subject_id
            or atom.predicate != self.need.predicate
            or atom.scope_id != self.need.scope_id
            for atom in self.atoms
        ):
            raise ValueError("resolved atoms must exactly match need subject/predicate/scope")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


@dataclass(frozen=True, slots=True)
class CapabilityEvidencePayload:
    """Host-normalized capability output; never model-created evidence."""

    evidence_id: str
    subject_id: str
    predicate: str
    value: object
    source_id: str
    observed_at: datetime
    expires_at: datetime | None
    scope_id: str
    trust: float

    def atom(self) -> EvidenceAtom:
        return EvidenceAtom(
            evidence_id=self.evidence_id,
            subject_id=self.subject_id,
            predicate=self.predicate,
            value_json=json.dumps(
                self.value,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            source_id=self.source_id,
            observed_at=self.observed_at,
            expires_at=self.expires_at,
            scope_id=self.scope_id,
            trust=self.trust,
            epistemic_state=EpistemicState.OBSERVED,
            acquisition_state=AcquisitionState.CURRENT,
        )


class EvidenceConflict(RuntimeError):
    pass


class CognitiveEvidenceLedger:
    """Append-only evidence and status events in canonical `sofia.db`."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cognition_v2_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    expires_at TEXT,
                    scope_id TEXT NOT NULL,
                    trust REAL NOT NULL,
                    epistemic_state TEXT NOT NULL,
                    acquisition_state TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cognition_v2_evidence_lookup
                ON cognition_v2_evidence (
                    scope_id, subject_id, predicate, observed_at
                );
                CREATE TABLE IF NOT EXISTS cognition_v2_evidence_dependencies (
                    evidence_id TEXT NOT NULL,
                    dependency_id TEXT NOT NULL,
                    PRIMARY KEY (evidence_id, dependency_id),
                    FOREIGN KEY (evidence_id)
                        REFERENCES cognition_v2_evidence(evidence_id),
                    FOREIGN KEY (dependency_id)
                        REFERENCES cognition_v2_evidence(evidence_id)
                );
                CREATE TABLE IF NOT EXISTS cognition_v2_evidence_status (
                    serial INTEGER PRIMARY KEY AUTOINCREMENT,
                    evidence_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY (evidence_id)
                        REFERENCES cognition_v2_evidence(evidence_id)
                );
                CREATE INDEX IF NOT EXISTS idx_cognition_v2_evidence_status
                ON cognition_v2_evidence_status (evidence_id, serial);
                CREATE TABLE IF NOT EXISTS cognition_v2_corrections (
                    correction_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    target_ids_json TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    corrected_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _row_to_atom(row, *, state: AcquisitionState | None = None):
        return EvidenceAtom(
            evidence_id=row["evidence_id"],
            subject_id=row["subject_id"],
            predicate=row["predicate"],
            value_json=row["value_json"],
            source_id=row["source_id"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            expires_at=(
                None
                if row["expires_at"] is None
                else datetime.fromisoformat(row["expires_at"])
            ),
            scope_id=row["scope_id"],
            trust=float(row["trust"]),
            epistemic_state=EpistemicState(row["epistemic_state"]),
            acquisition_state=(
                AcquisitionState(row["acquisition_state"])
                if state is None else state
            ),
        )

    def append(
        self,
        atom: EvidenceAtom,
        *,
        depends_on: tuple[str, ...] = (),
    ) -> EvidenceAtom:
        return self._append(atom, depends_on=depends_on, execution_result=None)

    def append_execution(
        self,
        atom: EvidenceAtom,
        *,
        result: CapabilityResult,
        depends_on: tuple[str, ...] = (),
    ) -> EvidenceAtom:
        """Append an execution fact bound to its successful host result."""
        if not isinstance(result, CapabilityResult):
            raise TypeError("result must be CapabilityResult")
        return self._append(
            atom,
            depends_on=depends_on,
            execution_result=result,
        )

    def _append(
        self,
        atom: EvidenceAtom,
        *,
        depends_on: tuple[str, ...],
        execution_result: CapabilityResult | None,
    ) -> EvidenceAtom:
        if not isinstance(atom, EvidenceAtom):
            raise TypeError("atom must be EvidenceAtom")
        if not isinstance(depends_on, tuple):
            raise TypeError("depends_on must be tuple")
        if atom.evidence_id in depends_on or len(set(depends_on)) != len(depends_on):
            raise ValueError("dependencies must be unique and cannot self-reference")
        if atom.epistemic_state in {
            EpistemicState.INFERRED,
            EpistemicState.HYPOTHESIS,
        } and not depends_on:
            raise ValueError("inferred/hypothesis evidence requires dependencies")
        if atom.epistemic_state in {
            EpistemicState.OBSERVED,
            EpistemicState.KNOWN,
        } and not atom.source_id.startswith((
            "capability:",
            "environment:",
            "execution-receipt:",
            "memory-reviewed:",
            "runtime:",
            "sensor:",
            "state:",
        )):
            raise ValueError("observed/known evidence requires a reviewed host source")
        if (
            atom.epistemic_state is EpistemicState.USER_REPORTED
            and not atom.source_id.startswith("user-report:")
        ):
            raise ValueError("user-reported evidence requires a user-report source")
        if atom.predicate.startswith("execution."):
            if (
                execution_result is None
                or execution_result.kind is not CapabilityResultKind.SUCCESS
                or atom.source_id
                != f"execution-receipt:{execution_result.capability}"
            ):
                raise ValueError(
                    "execution claims require a matching successful result receipt"
                )
        elif execution_result is not None:
            raise ValueError("execution result can bind only an execution predicate")
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT * FROM cognition_v2_evidence WHERE evidence_id = ?",
                (atom.evidence_id,),
            ).fetchone()
            if existing is not None:
                existing_dependencies = tuple(
                    row["dependency_id"]
                    for row in db.execute(
                        """
                        SELECT dependency_id
                        FROM cognition_v2_evidence_dependencies
                        WHERE evidence_id = ? ORDER BY dependency_id
                        """,
                        (atom.evidence_id,),
                    ).fetchall()
                )
                if (
                    self._row_to_atom(existing) == atom
                    and existing_dependencies == tuple(sorted(depends_on))
                ):
                    return atom
                raise EvidenceConflict("evidence_id already identifies different evidence")
            dependencies = []
            for dependency_id in depends_on:
                row = db.execute(
                    "SELECT * FROM cognition_v2_evidence WHERE evidence_id = ?",
                    (dependency_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("evidence dependency does not exist")
                dependency = self._row_to_atom(row)
                if dependency.scope_id != atom.scope_id:
                    raise ValueError("evidence dependencies cannot cross scopes")
                dependencies.append(dependency)
            db.execute(
                """
                INSERT INTO cognition_v2_evidence (
                    evidence_id, subject_id, predicate, value_json, source_id,
                    observed_at, expires_at, scope_id, trust,
                    epistemic_state, acquisition_state, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    atom.evidence_id,
                    atom.subject_id,
                    atom.predicate,
                    atom.value_json,
                    atom.source_id,
                    atom.observed_at.isoformat(),
                    None if atom.expires_at is None else atom.expires_at.isoformat(),
                    atom.scope_id,
                    atom.trust,
                    atom.epistemic_state.value,
                    atom.acquisition_state.value,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            db.executemany(
                """
                INSERT INTO cognition_v2_evidence_dependencies (
                    evidence_id, dependency_id
                ) VALUES (?, ?)
                """,
                ((atom.evidence_id, item.evidence_id) for item in dependencies),
            )
        return atom

    def get(self, evidence_id: str) -> EvidenceAtom | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM cognition_v2_evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
            if row is None:
                return None
            state = self._latest_state(db, evidence_id)
        return self._row_to_atom(row, state=state)

    @staticmethod
    def _latest_state(db, evidence_id: str) -> AcquisitionState | None:
        row = db.execute(
            """
            SELECT state FROM cognition_v2_evidence_status
            WHERE evidence_id = ? ORDER BY serial DESC LIMIT 1
            """,
            (evidence_id,),
        ).fetchone()
        return None if row is None else AcquisitionState(row["state"])

    def matching(self, need: EvidenceNeed) -> tuple[EvidenceAtom, ...]:
        if not isinstance(need, EvidenceNeed):
            raise TypeError("need must be EvidenceNeed")
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT * FROM cognition_v2_evidence
                WHERE subject_id = ? AND predicate = ? AND scope_id = ?
                ORDER BY observed_at DESC, evidence_id ASC
                """,
                (need.subject_id, need.predicate, need.scope_id),
            ).fetchall()
            return tuple(
                self._row_to_atom(
                    row,
                    state=self._latest_state(db, row["evidence_id"]),
                )
                for row in rows
            )

    def dependencies(self, evidence_id: str) -> tuple[str, ...]:
        with closing(self._connect()) as db:
            return tuple(
                row["dependency_id"]
                for row in db.execute(
                    """
                    SELECT dependency_id
                    FROM cognition_v2_evidence_dependencies
                    WHERE evidence_id = ? ORDER BY dependency_id
                    """,
                    (evidence_id,),
                ).fetchall()
            )

    def dependents(self, evidence_id: str) -> tuple[str, ...]:
        with closing(self._connect()) as db:
            return tuple(
                row["evidence_id"]
                for row in db.execute(
                    """
                    SELECT evidence_id
                    FROM cognition_v2_evidence_dependencies
                    WHERE dependency_id = ? ORDER BY evidence_id
                    """,
                    (evidence_id,),
                ).fetchall()
            )

    def record_status(
        self,
        evidence_id: str,
        state: AcquisitionState,
        *,
        reason: str,
        source_ref: str,
        changed_at: datetime,
    ) -> None:
        if state not in {AcquisitionState.CONTRADICTED, AcquisitionState.REVOKED}:
            raise ValueError("only contradiction/revocation status is durable")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be nonempty")
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_ref must be nonempty")
        if changed_at.tzinfo is None or changed_at.utcoffset() is None:
            raise ValueError("changed_at must be timezone-aware")
        with closing(self._connect()) as db, db:
            if db.execute(
                "SELECT 1 FROM cognition_v2_evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone() is None:
                raise ValueError("cannot change unknown evidence")
            db.execute(
                """
                INSERT INTO cognition_v2_evidence_status (
                    evidence_id, state, reason, source_ref, changed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (evidence_id, state.value, reason, source_ref, changed_at.isoformat()),
            )

    def apply_correction(
        self,
        *,
        correction_id: str,
        need: EvidenceNeed,
        target_ids: tuple[str, ...],
        source_ref: str,
        reason: str,
        corrected_at: datetime,
    ) -> tuple[str, ...]:
        """Atomically contradict targets and revoke every dependent conclusion."""
        if not isinstance(need, EvidenceNeed):
            raise TypeError("need must be EvidenceNeed")
        if not target_ids or len(set(target_ids)) != len(target_ids):
            raise ValueError("correction targets must be nonempty and unique")
        if not isinstance(correction_id, str) or not correction_id.strip():
            raise ValueError("correction_id must be nonempty")
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_ref must be nonempty")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be nonempty")
        if corrected_at.tzinfo is None or corrected_at.utcoffset() is None:
            raise ValueError("corrected_at must be timezone-aware")
        with closing(self._connect()) as db, db:
            for evidence_id in target_ids:
                row = db.execute(
                    "SELECT * FROM cognition_v2_evidence WHERE evidence_id = ?",
                    (evidence_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("correction target does not exist")
                atom = self._row_to_atom(row)
                if (
                    atom.subject_id != need.subject_id
                    or atom.predicate != need.predicate
                    or atom.scope_id != need.scope_id
                ):
                    raise ValueError("correction target does not match exact claim key")
            try:
                db.execute(
                    """
                    INSERT INTO cognition_v2_corrections (
                        correction_id, subject_id, predicate, scope_id,
                        target_ids_json, source_ref, reason, corrected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        correction_id, need.subject_id, need.predicate,
                        need.scope_id, json.dumps(target_ids), source_ref,
                        reason, corrected_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise EvidenceConflict("correction_id already exists") from exc
            invalidated = []
            queue = [
                (evidence_id, AcquisitionState.CONTRADICTED)
                for evidence_id in target_ids
            ]
            seen = set()
            while queue:
                evidence_id, state = queue.pop(0)
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                db.execute(
                    """
                    INSERT INTO cognition_v2_evidence_status (
                        evidence_id, state, reason, source_ref, changed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id, state.value, reason, source_ref,
                        corrected_at.isoformat(),
                    ),
                )
                invalidated.append(evidence_id)
                queue.extend(
                    (row["evidence_id"], AcquisitionState.REVOKED)
                    for row in db.execute(
                        """
                        SELECT evidence_id
                        FROM cognition_v2_evidence_dependencies
                        WHERE dependency_id = ? ORDER BY evidence_id
                        """,
                        (evidence_id,),
                    ).fetchall()
                )
        return tuple(invalidated)


class EvidenceGraph:
    """Exact-key graph projection with freshness/trust truth maintenance."""

    def __init__(self, ledger: CognitiveEvidenceLedger) -> None:
        if not isinstance(ledger, CognitiveEvidenceLedger):
            raise TypeError("ledger must be CognitiveEvidenceLedger")
        self.ledger = ledger

    def resolve(self, need: EvidenceNeed, *, now: datetime) -> EvidenceResolution:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        matching = self.ledger.matching(need)
        if not matching:
            return EvidenceResolution(
                need, AcquisitionState.NOT_SAMPLED, reason="no exact scoped evidence"
            )
        states = {atom.acquisition_state for atom in matching}
        current = tuple(
            atom for atom in matching
            if atom.acquisition_state is AcquisitionState.CURRENT
            and atom.observed_at <= now
            and atom.epistemic_state not in {
                EpistemicState.HYPOTHESIS,
                EpistemicState.UNKNOWN,
            }
            and (atom.expires_at is None or atom.expires_at > now)
            and (
                need.max_age_seconds is None
                or (now - atom.observed_at).total_seconds() <= need.max_age_seconds
            )
            and atom.trust >= need.minimum_trust
        )
        if current:
            return EvidenceResolution(
                need, AcquisitionState.CURRENT, current, "exact current evidence"
            )
        if AcquisitionState.CONTRADICTED in states:
            state = AcquisitionState.CONTRADICTED
        elif AcquisitionState.REVOKED in states:
            state = AcquisitionState.REVOKED
        elif any(
            atom.expires_at is not None and atom.expires_at <= now
            or (
                need.max_age_seconds is not None
                and (now - atom.observed_at).total_seconds() > need.max_age_seconds
            )
            for atom in matching
        ):
            state = AcquisitionState.STALE
        elif AcquisitionState.FAILED in states:
            state = AcquisitionState.FAILED
        elif AcquisitionState.UNAVAILABLE in states:
            state = AcquisitionState.UNAVAILABLE
        else:
            state = AcquisitionState.NOT_SAMPLED
        return EvidenceResolution(need, state, reason="no eligible current evidence")

    def correct(
        self,
        *,
        correction_id: str,
        need: EvidenceNeed,
        target_ids: tuple[str, ...],
        source_ref: str,
        reason: str,
        corrected_at: datetime,
    ) -> tuple[str, ...]:
        if not target_ids:
            raise ValueError("correction requires target evidence")
        if (
            not isinstance(source_ref, str)
            or not source_ref.startswith("user-report:")
        ):
            raise ValueError("user correction requires an authenticated user-report source")
        return self.ledger.apply_correction(
            correction_id=correction_id,
            need=need,
            target_ids=target_ids,
            source_ref=source_ref,
            reason=reason,
            corrected_at=corrected_at,
        )


class EvidenceAcquisitionCoordinator:
    """Validate already-authorized capability output before ledger ingestion."""

    def __init__(self, ledger: CognitiveEvidenceLedger) -> None:
        self.ledger = ledger

    def record(
        self,
        need: EvidenceNeed,
        result: CapabilityResult,
        payload: CapabilityEvidencePayload,
    ) -> EvidenceAtom:
        if not isinstance(result, CapabilityResult):
            raise TypeError("result must be CapabilityResult")
        atom = payload.atom()
        if (
            atom.subject_id != need.subject_id
            or atom.predicate != need.predicate
            or atom.scope_id != need.scope_id
        ):
            raise ValueError("capability evidence does not match requested key")
        expected_source = f"capability:{result.capability}"
        if atom.source_id != expected_source:
            raise ValueError("capability evidence source does not match result")
        if result.kind in {
            CapabilityResultKind.DENIED,
            CapabilityResultKind.UNAUTHORIZED,
        }:
            raise ValueError("authority denial is not factual acquisition evidence")
        if result.kind is CapabilityResultKind.FAILED:
            atom = replace(
                atom,
                value_json="null",
                trust=0.0,
                epistemic_state=EpistemicState.UNKNOWN,
                acquisition_state=AcquisitionState.FAILED,
            )
        elif result.kind is CapabilityResultKind.UNAVAILABLE:
            atom = replace(
                atom,
                value_json="null",
                trust=0.0,
                epistemic_state=EpistemicState.UNKNOWN,
                acquisition_state=AcquisitionState.UNAVAILABLE,
            )
        return self.ledger.append(atom)

    def record_execution(
        self,
        need: EvidenceNeed,
        result: CapabilityResult,
        payload: CapabilityEvidencePayload,
    ) -> EvidenceAtom:
        """Record execution only when a matching successful result exists."""
        if not isinstance(result, CapabilityResult):
            raise TypeError("result must be CapabilityResult")
        if result.kind is not CapabilityResultKind.SUCCESS:
            raise ValueError("execution receipt requires a successful result")
        atom = payload.atom()
        if not need.predicate.startswith("execution."):
            raise ValueError("execution evidence requires an execution predicate")
        if (
            atom.subject_id != need.subject_id
            or atom.predicate != need.predicate
            or atom.scope_id != need.scope_id
        ):
            raise ValueError("execution evidence does not match requested key")
        if atom.source_id != f"execution-receipt:{result.capability}":
            raise ValueError("execution receipt does not match capability result")
        return self.ledger.append_execution(atom, result=result)
