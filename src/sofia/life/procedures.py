"""Canonical, non-executable catalog of evidence-verified creative procedures.

A procedure is *knowledge about* a previously authorized LIFE/RUN workflow,
not code, a capability grant or a workflow scheduler. This single-writer
SQLite projection never executes, schedules, grants or changes any device.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import platform
from pathlib import Path
import sqlite3

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.goals.evidence import GoalEvidenceIndex
from sofia.run.work import DurableWorkStore, WorkStatus
from sofia.social.principals import local_sparks_principal

from .model import LifeProject, ProjectScope, ProjectStatus, TechnicalOutcome
from .store import LifeStore


@dataclass(frozen=True, slots=True)
class ProcedureRecord:
    procedure_id: str
    version: int
    status: str
    owner_principal_id: str
    audience_id: str
    purpose: str
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    preconditions: tuple[str, ...]
    required_tools: tuple[str, ...]
    exact_capabilities: tuple[str, ...]
    source_objectives: tuple[str, ...]
    environment: str
    verification_rule: str
    verified_projects: int
    provenance_refs: tuple[str, ...]
    updated_at: datetime


class LifeProcedureCatalog:
    """Verified repeatability only, still subordinate to SAFE/GOALS/RUN."""

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS life_procedure_catalog (
                    procedure_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    owner_principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    input_types_json TEXT NOT NULL,
                    output_types_json TEXT NOT NULL,
                    preconditions_json TEXT NOT NULL,
                    required_tools_json TEXT NOT NULL,
                    exact_capabilities_json TEXT NOT NULL,
                    source_objectives_json TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    verification_rule TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(
                        status IN ('candidate','verified','quarantined')
                    ),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    provenance_refs_json TEXT NOT NULL,
                    quarantine_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS life_procedure_compatibility
                ON life_procedure_catalog(
                    owner_principal_id,audience_id,status,environment
                );
                CREATE TABLE IF NOT EXISTS life_procedure_proof (
                    procedure_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    PRIMARY KEY(procedure_id,project_id,job_id),
                    FOREIGN KEY(procedure_id)
                        REFERENCES life_procedure_catalog(procedure_id)
                );
                CREATE INDEX IF NOT EXISTS life_procedure_unique_projects
                ON life_procedure_proof(procedure_id,project_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def local_environment() -> str:
        """Local runtime compatibility, never assumed remote Fleet identity."""
        return ":".join((
            platform.system().casefold(),
            platform.machine().casefold(),
            str(platform.python_version_tuple()[0]),
            str(platform.python_version_tuple()[1]),
        ))

    @staticmethod
    def _definition(project: LifeProject) -> tuple[str, str]:
        if (
            not isinstance(project, LifeProject)
            or project.scope is not ProjectScope.PERSONAL_PRIVATE
            or project.goal_id is None
        ):
            raise ValueError("only an actual scoped personal LIFE goal can describe a procedure")
        brief = project.brief
        if (
            not brief.required_tools or not brief.permission_requirements
            or not brief.objectives
            or len(set(brief.objectives)) != len(brief.objectives)
        ):
            raise ValueError("a procedure needs exact original typed capabilities and goals")
        environment = LifeProcedureCatalog.local_environment()
        canonical = json.dumps({
            "owner": project.owner_principal_id,
            "audience": project.audience_id,
            "objectives": brief.objectives,
            "required_tools": brief.required_tools,
            "exact_capabilities": brief.permission_requirements,
            "environment": environment,
            "version": 1,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        procedure_id = "life-procedure:" + sha256(
            canonical.encode("utf-8")
        ).hexdigest()[:32]
        return procedure_id, environment

    @staticmethod
    def _decode(row: sqlite3.Row, project_count: int) -> ProcedureRecord:
        return ProcedureRecord(
            procedure_id=row["procedure_id"], version=int(row["version"]),
            status=row["status"],
            owner_principal_id=row["owner_principal_id"],
            audience_id=row["audience_id"], purpose=row["purpose"],
            input_types=tuple(json.loads(row["input_types_json"])),
            output_types=tuple(json.loads(row["output_types_json"])),
            preconditions=tuple(json.loads(row["preconditions_json"])),
            required_tools=tuple(json.loads(row["required_tools_json"])),
            exact_capabilities=tuple(json.loads(row["exact_capabilities_json"])),
            source_objectives=tuple(json.loads(row["source_objectives_json"])),
            environment=row["environment"],
            verification_rule=row["verification_rule"],
            verified_projects=project_count,
            provenance_refs=tuple(json.loads(row["provenance_refs_json"])),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def record_verified_attempt(
        self, *, project: LifeProject, job_id: str,
        original_run_evidence_ref: str, now: datetime,
    ) -> ProcedureRecord:
        """Record a proof already independently validated by the LIFE owner.

        Callers must check real RUN job, exact linked artifact revision,
        original operation receipt, closed objectives and current bytes.
        A single success is a candidate; two different source projects
        promote only descriptive knowledge, never executable authority.
        """
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None or now.utcoffset() is None
            or not isinstance(job_id, str) or not job_id.strip()
            or not isinstance(original_run_evidence_ref, str)
            or not original_run_evidence_ref.strip()
        ):
            raise ValueError("original source job, receipt and aware time required")
        key, environment = self._definition(project)
        # Do not let an arbitrary caller promote a made-up model lesson.
        # Recheck the original canonical LIFE row, linked RUN receipt and
        # independent evaluation before recording a single success.
        canonical = LifeStore(self.path).get(
            project.project_id,
            owner_principal_id=project.owner_principal_id,
            audience_id=project.audience_id,
        )
        if (
            canonical != project
            or canonical.status is not ProjectStatus.COMPLETED
        ):
            raise ValueError("procedure source is not the current completed LIFE project")
        original = GoalEvidenceIndex(self.path).lookup(original_run_evidence_ref)
        if (
            original is None or original.kind != "operation_receipt"
            or original.source != "life:creative-capability"
            or original.successful is not True
            or original.goal_id != project.goal_id
            or original.action_id != job_id
            or original.principal_id != local_sparks_principal().principal_id
            or original.audience != project.audience_id
            or original.observed_at > now
        ):
            raise ValueError("procedure requires the real original scoped RUN receipt")
        work = DurableWorkStore(self.path).get(job_id)
        output = work.result if isinstance(work.result, dict) else {}
        if (
            work.status is not WorkStatus.COMPLETED
            or output.get("evidence_ref") != original_run_evidence_ref
            or not isinstance(output.get("artifact_id"), str)
            or type(output.get("revision")) is not int
        ):
            raise ValueError("original RUN effect has no matching completed artifact")
        source = LifeStore(self.path)
        if (
            job_id not in source.jobs(project.project_id)
            or (output["artifact_id"], output["revision"])
            not in source.artifacts(project.project_id)
            or not any(
                evaluation.artifact_id == output["artifact_id"]
                and evaluation.artifact_revision == output["revision"]
                and evaluation.technical_outcome is TechnicalOutcome.VALID
                and original_run_evidence_ref in evaluation.evidence_refs
                and set(evaluation.objective_results) ==
                set(project.brief.objectives)
                and all(
                    value is True
                    for value in evaluation.objective_results.values()
                )
                for evaluation in source.evaluations(project.project_id)
            )
        ):
            raise ValueError("independent original LIFE objective proof missing")
        now_iso = now.astimezone(timezone.utc).isoformat()
        project_brief = project.brief
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT * FROM life_procedure_catalog WHERE procedure_id=?",
                (key,),
            ).fetchone()
            if existing is None:
                db.execute(
                    """INSERT INTO life_procedure_catalog
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        key, 1, project.owner_principal_id,
                        project.audience_id,
                        "Reproduce independently verified, original LIFE creative objectives",
                        json.dumps(("LifeProject", "CreativeArtifactCapability")),
                        json.dumps(("CreativeArtifactRevision", "RUN operation_receipt")),
                        json.dumps((
                            "canonical_goal_active_at_execution",
                            "exact_current_SAFE_grant_required",
                            "original_creative_adapter_available",
                            "current_artifact_objectives_independently_verified",
                            "no_remote_replay_authorized",
                        )),
                        json.dumps(project_brief.required_tools),
                        json.dumps(project_brief.permission_requirements),
                        json.dumps(project_brief.objectives),
                        environment,
                        "Two distinct source projects with confirmed completed RUN and original-byte validator PASS",
                        "candidate", now_iso, now_iso,
                        json.dumps((original_run_evidence_ref,)), None,
                    ),
                )
            elif existing["status"] == "quarantined":
                # Historical bad procedures cannot self-promote just by
                # recording new results. Independent reviewed reinstatement
                # is a separate authorized operator workflow.
                count = db.execute(
                    "SELECT COUNT(DISTINCT project_id) FROM life_procedure_proof "
                    "WHERE procedure_id=?", (key,),
                ).fetchone()[0]
                return self._decode(existing, int(count))
            db.execute(
                "INSERT OR IGNORE INTO life_procedure_proof VALUES(?,?,?,?,?)",
                (
                    key, project.project_id, job_id,
                    original_run_evidence_ref, now_iso,
                ),
            )
            proofs = db.execute(
                "SELECT evidence_ref FROM life_procedure_proof "
                "WHERE procedure_id=? ORDER BY verified_at,project_id LIMIT 32",
                (key,),
            ).fetchall()
            count = db.execute(
                "SELECT COUNT(DISTINCT project_id) "
                "FROM life_procedure_proof WHERE procedure_id=?",
                (key,),
            ).fetchone()[0]
            db.execute(
                """UPDATE life_procedure_catalog
                SET status=?,updated_at=?,provenance_refs_json=?
                WHERE procedure_id=? AND status!='quarantined'""",
                (
                    "verified" if int(count) >= 2 else "candidate",
                    now_iso,
                    json.dumps(tuple(row[0] for row in proofs)),
                    key,
                ),
            )
            row = db.execute(
                "SELECT * FROM life_procedure_catalog WHERE procedure_id=?",
                (key,),
            ).fetchone()
            return self._decode(row, int(count))

    def has_source_project(self, project_id: str) -> bool:
        """Fast idempotency check before replaying expensive source validation."""
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("original project ID required")
        with closing(self._connect()) as db:
            return db.execute(
                "SELECT 1 FROM life_procedure_proof "
                "WHERE project_id=? LIMIT 1", (project_id,),
            ).fetchone() is not None

    def available_for_project(
        self, project: LifeProject, *, limit: int = 8,
    ) -> tuple[ProcedureRecord, ...]:
        """Exact, local-only compatibility view, never skill execution."""
        if type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded procedure lookup required")
        key, environment = self._definition(project)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM life_procedure_catalog
                WHERE procedure_id=? AND owner_principal_id=?
                  AND audience_id=? AND environment=? AND status='verified'
                LIMIT ?""",
                (
                    key, project.owner_principal_id, project.audience_id,
                    environment, limit,
                ),
            ).fetchall()
            return tuple(self._decode(
                row, int(db.execute(
                    "SELECT COUNT(DISTINCT project_id) "
                    "FROM life_procedure_proof WHERE procedure_id=?",
                    (row["procedure_id"],),
                ).fetchone()[0]),
            ) for row in rows)

    def verified_proof_projects(
        self, *, limit: int = 16,
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Read original source project IDs for independently verified entries.

        No model-proposed or unverified attempt becomes proof. The result is
        bounded by catalog entries, never a whole-workspace transcript scan.
        """
        if type(limit) is not int or not 1 <= limit <= 64:
            raise ValueError("bounded procedure source audit required")
        with closing(self._connect()) as db:
            entries = db.execute(
                "SELECT procedure_id FROM life_procedure_catalog "
                "WHERE status='verified' ORDER BY updated_at DESC,procedure_id "
                "LIMIT ?", (limit,),
            ).fetchall()
            output = []
            for entry in entries:
                project_ids = db.execute(
                    "SELECT DISTINCT project_id FROM life_procedure_proof "
                    "WHERE procedure_id=? ORDER BY project_id",
                    (entry["procedure_id"],),
                ).fetchall()
                output.append((
                    entry["procedure_id"],
                    tuple(item[0] for item in project_ids),
                ))
            return tuple(output)

    def quarantine(
        self, procedure_id: str, *, reason: str, now: datetime,
    ) -> None:
        """Safe quarantine only; cannot promote or execute a procedure."""
        if (
            not isinstance(procedure_id, str)
            or not procedure_id.startswith("life-procedure:")
            or not isinstance(reason, str) or not reason.strip()
            or len(reason) > 500
            or not isinstance(now, datetime)
            or now.tzinfo is None or now.utcoffset() is None
        ):
            raise ValueError("source procedure ID, bounded reason and time required")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE life_procedure_catalog SET status='quarantined',
                quarantine_reason=?, updated_at=? WHERE procedure_id=?""",
                (reason, now.astimezone(timezone.utc).isoformat(), procedure_id),
            )
            if changed.rowcount != 1:
                raise LookupError("original procedure does not exist")
