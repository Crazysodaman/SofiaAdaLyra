"""Qualification and lifecycle for verified LIFE procedures.

Skills remain descriptive until existing SAFE/RUN owners admit and execute an
exact job.  This module cannot create capabilities, grants, receipts or jobs.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import sqlite3

from sofia.goals.evidence import GoalEvidenceIndex
from sofia.life.procedures import LifeProcedureCatalog, ProcedureRecord
from sofia.platform.run.work import DurableWorkStore, WorkStatus
from sofia.core.social.model import PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_RISKS = ("read_only", "isolated_change", "protected")
_TRIALS = ("positive", "missing_dependency", "version_difference", "counterexample")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class LearnedSkill:
    skill_id: str
    procedure_id: str
    version: int
    status: str
    principal_id: str
    audience_id: str
    risk: str
    required_tools: tuple[str, ...]
    exact_capabilities: tuple[str, ...]
    prerequisites: tuple[str, ...]
    postconditions: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    superseded_by: str | None


class LearnedSkillStore:
    """Canonical qualification projection; no executor and no authority."""

    def __init__(
        self, state_path: str | Path, *, procedures: LifeProcedureCatalog,
    ) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self._procedures = procedures
        self._evidence = GoalEvidenceIndex(self.path)
        self._work = DurableWorkStore(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ga_learned_skill(
                    skill_id TEXT PRIMARY KEY, procedure_id TEXT NOT NULL,
                    procedure_version INTEGER NOT NULL,
                    principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    risk TEXT NOT NULL, required_tools_json TEXT NOT NULL,
                    exact_capabilities_json TEXT NOT NULL,
                    prerequisites_json TEXT NOT NULL,
                    postconditions_json TEXT NOT NULL,
                    provenance_refs_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN(
                        'candidate','verified','revoked','invalidated','deprecated','superseded'
                    )),
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    lifecycle_reason TEXT NOT NULL, superseded_by TEXT,
                    UNIQUE(procedure_id,procedure_version)
                );
                CREATE TABLE IF NOT EXISTS ga_skill_adapter(
                    skill_id TEXT NOT NULL, platform TEXT NOT NULL,
                    adapter_id TEXT NOT NULL, adapter_version TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, verified_at TEXT NOT NULL,
                    PRIMARY KEY(skill_id,platform)
                );
                CREATE TABLE IF NOT EXISTS ga_skill_trial(
                    skill_id TEXT NOT NULL, trial_kind TEXT NOT NULL,
                    run_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    family_id TEXT NOT NULL, passed INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY(skill_id,trial_kind,run_id,case_id)
                );
                CREATE TABLE IF NOT EXISTS ga_skill_rehearsal(
                    skill_id TEXT NOT NULL, job_id TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, rollback_ref TEXT,
                    observed_at TEXT NOT NULL,
                    PRIMARY KEY(skill_id,job_id)
                );
                CREATE TABLE IF NOT EXISTS ga_skill_lifecycle(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT NOT NULL, from_status TEXT,
                    to_status TEXT NOT NULL, reason TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _minimum_risk(capabilities: tuple[str, ...]) -> str:
        lowered = tuple(value.casefold() for value in capabilities)
        if any(any(token in value for token in ("manage", "delete", "install", "permission", "dev.")) for value in lowered):
            return "protected"
        if any(any(token in value for token in ("create", "write", "edit", "update", "restart")) for value in lowered):
            return "isolated_change"
        return "read_only"

    @staticmethod
    def _decode(row: sqlite3.Row) -> LearnedSkill:
        return LearnedSkill(
            skill_id=row["skill_id"], procedure_id=row["procedure_id"],
            version=int(row["procedure_version"]), status=row["status"],
            principal_id=row["principal_id"], audience_id=row["audience_id"],
            risk=row["risk"], required_tools=tuple(json.loads(row["required_tools_json"])),
            exact_capabilities=tuple(json.loads(row["exact_capabilities_json"])),
            prerequisites=tuple(json.loads(row["prerequisites_json"])),
            postconditions=tuple(json.loads(row["postconditions_json"])),
            provenance_refs=tuple(json.loads(row["provenance_refs_json"])),
            superseded_by=row["superseded_by"],
        )

    def register_candidate(
        self, procedure: ProcedureRecord, *, principal: PrincipalContext,
        risk: str, now: datetime,
    ) -> LearnedSkill:
        moment = _utc(now)
        if not isinstance(procedure, ProcedureRecord) or procedure.status != "verified":
            raise PermissionError("only an independently verified procedure may become a skill")
        if (procedure.owner_principal_id, procedure.audience_id) != (principal.principal_id, principal.audience_id):
            raise PermissionError("procedure principal/audience scope mismatch")
        proof = self._procedures.proof_receipts_for_procedure(procedure.procedure_id)
        if len({item[0] for item in proof}) < 2 or set(item[2] for item in proof) != set(procedure.provenance_refs):
            raise PermissionError("current independent procedure proofs are incomplete")
        minimum = self._minimum_risk(procedure.exact_capabilities)
        if risk not in _RISKS or _RISKS.index(risk) < _RISKS.index(minimum):
            raise PermissionError("skill risk cannot understate its exact capabilities")
        skill_id = f"ga-skill:{procedure.procedure_id.split(':')[-1]}:v{procedure.version}"
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO ga_learned_skill VALUES(?,?,?,?,?,?,?,?,?,?,?,"
                "'candidate',?,?,?,?)",
                (skill_id, procedure.procedure_id, procedure.version,
                 principal.principal_id, principal.audience_id, risk,
                 json.dumps(procedure.required_tools),
                 json.dumps(procedure.exact_capabilities),
                 json.dumps(procedure.preconditions),
                 json.dumps(procedure.output_types),
                 json.dumps(procedure.provenance_refs),
                 moment.isoformat(), moment.isoformat(),
                 "awaiting cross-platform and held-out qualification", None),
            )
            row = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if row is None or (
                row["procedure_id"] != procedure.procedure_id
                or int(row["procedure_version"]) != procedure.version
                or row["principal_id"] != principal.principal_id
                or row["audience_id"] != principal.audience_id
                or row["risk"] != risk
                or tuple(json.loads(row["required_tools_json"])) != procedure.required_tools
                or tuple(json.loads(row["exact_capabilities_json"])) != procedure.exact_capabilities
                or tuple(json.loads(row["prerequisites_json"])) != procedure.preconditions
                or tuple(json.loads(row["postconditions_json"])) != procedure.output_types
                or tuple(json.loads(row["provenance_refs_json"])) != procedure.provenance_refs
            ):
                raise PermissionError("immutable skill identity collision")
        return self._decode(row)

    def record_adapter(
        self, skill_id: str, *, principal: PrincipalContext, platform_name: str,
        adapter_id: str, adapter_version: str, evidence_ref: str, now: datetime,
    ) -> None:
        moment = _utc(now)
        platform_key = platform_name.casefold()
        if platform_key not in {"windows", "linux"}:
            raise ValueError("adapter platform must be Windows or Linux")
        if not all(isinstance(value, str) and value.strip() and len(value) <= 160 for value in (adapter_id, adapter_version)):
            raise ValueError("bounded adapter identity and version required")
        evidence = self._evidence.lookup(evidence_ref)
        if (
            evidence is None or evidence.kind not in {"operation_receipt", "reviewed_evidence"}
            or evidence.successful is not True
            or evidence.principal_id != principal.principal_id
            or evidence.audience != principal.audience_id
            or evidence.source != f"skill-adapter:{platform_key}"
        ):
            raise PermissionError("independent platform adapter evidence required")
        with closing(self._connect()) as db, db:
            skill = db.execute("SELECT principal_id,audience_id,status FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if skill is None or tuple(skill[:2]) != (principal.principal_id, principal.audience_id) or skill[2] != "candidate":
                raise PermissionError("scoped candidate skill required")
            db.execute(
                "INSERT INTO ga_skill_adapter VALUES(?,?,?,?,?,?) ON CONFLICT(skill_id,platform) "
                "DO UPDATE SET adapter_id=excluded.adapter_id,adapter_version=excluded.adapter_version,"
                "evidence_ref=excluded.evidence_ref,verified_at=excluded.verified_at",
                (skill_id, platform_key, adapter_id, adapter_version, evidence_ref, moment.isoformat()),
            )

    def record_trial(
        self, skill_id: str, *, principal: PrincipalContext, trial_kind: str,
        run_id: str, case_id: str, now: datetime,
    ) -> bool:
        moment = _utc(now)
        if trial_kind not in _TRIALS:
            raise ValueError("unsupported skill trial kind")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            skill = db.execute("SELECT principal_id,audience_id,status FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if skill is None or tuple(skill[:2]) != (principal.principal_id, principal.audience_id) or skill[2] != "candidate":
                raise PermissionError("scoped candidate skill required")
            grade = db.execute(
                "SELECT g.objective_success,c.family_id,r.status,r.principal_id,r.audience_id,"
                "r.condition,r.split "
                "FROM ga_case_grade g JOIN ga_evaluation_run r ON r.run_id=g.run_id "
                "JOIN ga_problem_case c ON c.suite_id=r.suite_id AND c.case_id=g.case_id "
                "WHERE g.run_id=? AND g.case_id=?", (run_id, case_id),
            ).fetchone()
            if (
                grade is None or grade[2] != "completed"
                or tuple(grade[3:5]) != (principal.principal_id, principal.audience_id)
                or grade[5] != "learned" or grade[6] != "test"
            ):
                raise PermissionError("completed scoped independent GA grade required")
            db.execute(
                "INSERT OR IGNORE INTO ga_skill_trial VALUES(?,?,?,?,?,?,?)",
                (skill_id, trial_kind, run_id, case_id, grade[1], int(bool(grade[0])), moment.isoformat()),
            )
        return bool(grade[0])

    def qualify(self, skill_id: str, *, principal: PrincipalContext, now: datetime) -> LearnedSkill:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            skill = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if skill is None or (skill["principal_id"], skill["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("skill scope mismatch")
            current = self._procedures.proof_receipts_for_procedure(skill["procedure_id"])
            if (
                set(item[2] for item in current) != set(json.loads(skill["provenance_refs_json"]))
                or len({item[0] for item in current}) < 2
            ):
                raise PermissionError("source procedure proof changed before qualification")
            adapters = {row[0] for row in db.execute(
                "SELECT platform FROM ga_skill_adapter WHERE skill_id=?", (skill_id,),
            ).fetchall()}
            trials = db.execute(
                "SELECT trial_kind,passed,family_id FROM ga_skill_trial WHERE skill_id=?",
                (skill_id,),
            ).fetchall()
            passed = {row[0] for row in trials if row[1]}
            families = {row[2] for row in trials if row[1]}
            if adapters != {"windows", "linux"} or passed != set(_TRIALS) or len(families) < 4:
                raise PermissionError("cross-platform and four distinct held-out qualifications required")
            if skill["status"] == "candidate":
                db.execute(
                    "UPDATE ga_learned_skill SET status='verified',updated_at=?,"
                    "lifecycle_reason='qualified by platform adapters and held-out trials' WHERE skill_id=?",
                    (moment.isoformat(), skill_id),
                )
                db.execute(
                    "INSERT INTO ga_skill_lifecycle(skill_id,from_status,to_status,reason,evidence_ref,occurred_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (skill_id, "candidate", "verified", "independent qualification complete",
                     "ga-qualification:" + skill_id, moment.isoformat()),
                )
            row = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
        return self._decode(row)

    def record_rehearsal(
        self, skill_id: str, *, principal: PrincipalContext, job_id: str,
        evidence_ref: str, rollback_ref: str | None, now: datetime,
    ) -> None:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            skill = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if skill is None or skill["status"] != "verified" or (skill["principal_id"], skill["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("verified scoped skill required")
            job = self._work.get(job_id)
            evidence = self._evidence.lookup(evidence_ref)
            if (
                job.status is not WorkStatus.COMPLETED
                or evidence is None or evidence.kind != "operation_receipt"
                or evidence.successful is not True or evidence.action_id != job_id
                or evidence.principal_id != principal.principal_id
                or evidence.audience != principal.audience_id
                or not isinstance(job.result, dict)
                or job.result.get("evidence_ref") != evidence_ref
                or job.payload.get("principal_id") != principal.principal_id
                or job.payload.get("audience_id") != principal.audience_id
            ):
                raise PermissionError("rehearsal requires matching completed RUN receipt")
            if skill["risk"] != "read_only" and not rollback_ref:
                raise PermissionError("non-read-only rehearsal requires rollback evidence")
            db.execute(
                "INSERT OR IGNORE INTO ga_skill_rehearsal VALUES(?,?,?,?,?)",
                (skill_id, job_id, evidence_ref, rollback_ref, moment.isoformat()),
            )

    def reconcile_source(self, skill_id: str, *, now: datetime) -> bool:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            skill = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if skill is None or skill["status"] in {"revoked", "invalidated", "deprecated", "superseded"}:
                return False
            current = self._procedures.proof_receipts_for_procedure(skill["procedure_id"])
            refs = {item[2] for item in current}
            expected = set(json.loads(skill["provenance_refs_json"]))
            if refs == expected and len({item[0] for item in current}) >= 2:
                return False
            db.execute(
                "UPDATE ga_learned_skill SET status='invalidated',updated_at=?,"
                "lifecycle_reason='source procedure proof changed or was revoked' WHERE skill_id=?",
                (moment.isoformat(), skill_id),
            )
            db.execute(
                "INSERT INTO ga_skill_lifecycle(skill_id,from_status,to_status,reason,evidence_ref,occurred_at) "
                "VALUES(?,?,?,?,?,?)",
                (skill_id, skill["status"], "invalidated",
                 "source procedure proof changed or was revoked", skill["procedure_id"], moment.isoformat()),
            )
        return True

    def reconcile_sources(self, *, now: datetime, limit: int = 64) -> int:
        """Boundedly invalidate skills whose canonical LIFE proof disappeared."""
        _utc(now)
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("limit must be in 1..256")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT skill_id FROM ga_learned_skill WHERE status IN ('candidate','verified') "
                "ORDER BY updated_at,skill_id LIMIT ?", (limit,),
            ).fetchall()
        return sum(self.reconcile_source(row[0], now=now) for row in rows)

    def invalidate_revoked_sources(
        self, evidence_refs: set[str], *, now: datetime, limit: int = 128,
    ) -> int:
        """Invalidate derived skills when an exact learning source is revoked."""
        moment = _utc(now)
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("limit must be in 1..256")
        if not evidence_refs:
            return 0
        changed = 0
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT skill_id,status,provenance_refs_json FROM ga_learned_skill "
                "WHERE status IN ('candidate','verified') ORDER BY updated_at LIMIT ?",
                (limit,),
            ).fetchall()
            for row in rows:
                if not (set(json.loads(row[2])) & evidence_refs):
                    continue
                db.execute(
                    "UPDATE ga_learned_skill SET status='invalidated',updated_at=?,"
                    "lifecycle_reason='learning source revoked' WHERE skill_id=?",
                    (moment.isoformat(), row[0]),
                )
                db.execute(
                    "INSERT INTO ga_skill_lifecycle(skill_id,from_status,to_status,reason,evidence_ref,occurred_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (row[0], row[1], "invalidated", "learning source revoked",
                     "revocation:source-lineage", moment.isoformat()),
                )
                changed += 1
        return changed

    def transition_lifecycle(
        self, skill_id: str, *, principal: PrincipalContext, to_status: str,
        reason: str, evidence_ref: str, now: datetime,
        superseded_by: str | None = None,
    ) -> LearnedSkill:
        moment = _utc(now)
        if to_status not in {"revoked", "deprecated", "superseded"}:
            raise ValueError("unsupported owner lifecycle transition")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValueError("bounded lifecycle reason required")
        evidence = self._evidence.lookup(evidence_ref)
        if (
            evidence is None or evidence.kind != "reviewed_evidence"
            or evidence.principal_id != principal.principal_id
            or evidence.audience != principal.audience_id
        ):
            raise PermissionError("scoped owner-reviewed lifecycle evidence required")
        if (to_status == "superseded") != bool(superseded_by):
            raise ValueError("superseded status requires exactly one successor")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
            if row is None or (row["principal_id"], row["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("skill scope mismatch")
            if row["status"] in {"revoked", "invalidated", "deprecated", "superseded"}:
                return self._decode(row)
            if superseded_by is not None:
                successor = db.execute(
                    "SELECT principal_id,audience_id,status FROM ga_learned_skill WHERE skill_id=?",
                    (superseded_by,),
                ).fetchone()
                if successor is None or tuple(successor[:2]) != (principal.principal_id, principal.audience_id) or successor[2] != "verified":
                    raise PermissionError("verified scoped successor required")
            db.execute(
                "UPDATE ga_learned_skill SET status=?,updated_at=?,lifecycle_reason=?,"
                "superseded_by=? WHERE skill_id=?",
                (to_status, moment.isoformat(), reason.strip(), superseded_by, skill_id),
            )
            db.execute(
                "INSERT INTO ga_skill_lifecycle(skill_id,from_status,to_status,reason,evidence_ref,occurred_at) "
                "VALUES(?,?,?,?,?,?)",
                (skill_id, row["status"], to_status, reason.strip(), evidence_ref, moment.isoformat()),
            )
            changed = db.execute("SELECT * FROM ga_learned_skill WHERE skill_id=?", (skill_id,)).fetchone()
        return self._decode(changed)

    def visible(self, *, principal: PrincipalContext) -> tuple[LearnedSkill, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM ga_learned_skill WHERE principal_id=? AND audience_id=? "
                "ORDER BY updated_at DESC,skill_id",
                (principal.principal_id, principal.audience_id),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)
