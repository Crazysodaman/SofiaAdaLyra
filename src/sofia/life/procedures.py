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

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.creative import (
    ArtifactRevision, CreativeExplorer, CreativeStore, NativeCreativeAdapter,
)
from sofia.goals.evidence import GoalEvidenceIndex
from sofia.platform.run.work import DurableWorkStore, WorkStatus
from sofia.core.social.principals import local_sparks_principal

from .model import LifeProject, ProjectScope, ProjectStatus, TechnicalOutcome
from .store import LifeStore
from .validation import inspect_objective_artifact


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
                CREATE TABLE IF NOT EXISTS life_procedure_replacement (
                    successor_id TEXT PRIMARY KEY,
                    quarantined_predecessor_id TEXT NOT NULL UNIQUE,
                    disposition TEXT NOT NULL CHECK(
                        disposition='auto_nonexecutable_creative_knowledge'
                    ),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(successor_id)
                        REFERENCES life_procedure_catalog(procedure_id),
                    FOREIGN KEY(quarantined_predecessor_id)
                        REFERENCES life_procedure_catalog(procedure_id)
                );
                CREATE TABLE IF NOT EXISTS life_procedure_scan_cursor (
                    owner_principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    last_project_id TEXT NOT NULL,
                    PRIMARY KEY(owner_principal_id,audience_id)
                );
                CREATE TABLE IF NOT EXISTS life_procedure_source_audit_cursor (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    last_procedure_id TEXT NOT NULL
                );
            """)

    @staticmethod
    def native_source_toolchain_current(
        artifact: ArtifactRevision, *, original_result: dict[str, object],
    ) -> bool:
        """Exact current local native adapter, never a remote-host assumption.

        This is a *read-only* suitability predicate over the original
        immutable creative revision and original RUN operation receipt.
        The source artifact's OS/Python catalog key is checked separately.
        External/DEV/Fleet tools require independently authenticated host
        and version evidence before any future procedure eligibility.
        """
        if not isinstance(artifact, ArtifactRevision) or not isinstance(
            original_result, dict,
        ):
            return False
        probe = NativeCreativeAdapter().probe()
        return bool(
            probe.available
            and artifact.kind in probe.supported_kinds
            and artifact.tool_id == probe.adapter_id
            and artifact.tool_version == probe.version
            and original_result.get("tool_id") == artifact.tool_id
            and original_result.get("tool_version") == artifact.tool_version
        )

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
    def _definition(
        project: LifeProject, *, version: int = 1,
    ) -> tuple[str, str]:
        if (
            not isinstance(project, LifeProject)
            or project.scope is not ProjectScope.PERSONAL_PRIVATE
            or project.goal_id is None
        ):
            raise ValueError("only an actual scoped personal LIFE goal can describe a procedure")
        if type(version) is not int or not 1 <= version <= 32:
            raise ValueError("procedure revision must be a bounded positive integer")
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
            "version": version,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        procedure_id = "life-procedure:" + sha256(
            canonical.encode("utf-8")
        ).hexdigest()[:32]
        return procedure_id, environment

    @staticmethod
    def _auto_recovery_eligible(project: LifeProject) -> bool:
        """Only passive local creative reference knowledge can auto-activate.

        Never interpret a learned workflow as permission to invoke its tools:
        this catalog has no executor. Remote calls, device control, DEV,
        installed code, expanded capabilities and cross-audience use have
        no eligible automatic recovery path.
        """
        if not isinstance(project, LifeProject):
            return False
        tools = project.brief.required_tools
        return bool(
            project.scope is ProjectScope.PERSONAL_PRIVATE
            and project.audience_id == "local:text"
            and len(tools) == 2
            and tools[0] == NativeCreativeAdapter().probe().adapter_id
            and tools[1] in {"artifact-kind:text", "artifact-kind:story"}
            and project.brief.permission_requirements
            == ("creative.artifact.create",)
        )

    @classmethod
    def _current_definition_under_lock(
        cls, db: sqlite3.Connection, project: LifeProject,
    ) -> tuple[str, str, int, sqlite3.Row | None]:
        """Resolve current generation while preserving quarantined ancestors.

        The original key remains permanently quarantined. On a next real
        creative proof, only a *new* version may become a candidate; that
        version must earn two distinct fresh verified source projects.
        """
        for version in range(1, 33):
            key, environment = cls._definition(project, version=version)
            existing = db.execute(
                "SELECT procedure_id,version,status,updated_at FROM "
                "life_procedure_catalog WHERE procedure_id=?", (key,),
            ).fetchone()
            if existing is None:
                if version == 1:
                    return key, environment, version, None
                parent_key, _ = cls._definition(project, version=version - 1)
                previous = db.execute(
                    "SELECT procedure_id,version,status,updated_at FROM "
                    "life_procedure_catalog WHERE procedure_id=?", (parent_key,),
                ).fetchone()
                if previous is None or previous["status"] != "quarantined":
                    raise ValueError("missing immutable quarantined predecessor")
                return key, environment, version, previous
            if int(existing["version"]) != version:
                raise ValueError("procedure version does not match immutable key")
            if existing["status"] != "quarantined":
                return key, environment, version, None
        raise ValueError("procedure revision bound exhausted; owner review required")

    def procedure_version(self, procedure_id: str) -> int | None:
        """Return recorded original version for source-provenance comparison."""
        if not isinstance(procedure_id, str) or not procedure_id.startswith(
            "life-procedure:"
        ):
            raise ValueError("bounded original procedure ID required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT version FROM life_procedure_catalog WHERE procedure_id=?",
                (procedure_id,),
            ).fetchone()
        return None if row is None else int(row["version"])

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

    @staticmethod
    def _original_proof_current_under_lock(
        db: sqlite3.Connection, *, project: LifeProject,
        job_id: str, evidence_ref: str, original_result: dict[str, object],
        now: datetime,
    ) -> bool:
        """Recheck original SQLite RUN/LIFE/evidence identity at promotion.

        The expensive creative-byte inspection occurs before this lock.
        This final canonical-source CAS does not equate a historical RUN
        success with current authorization to execute another operation.
        """
        row = db.execute(
            "SELECT owner_principal_id,audience_id,goal_id,status,revision "
            "FROM life_project WHERE project_id=?", (project.project_id,),
        ).fetchone()
        if (
            row is None or row["owner_principal_id"] != project.owner_principal_id
            or row["audience_id"] != project.audience_id
            or row["goal_id"] != project.goal_id
            or row["status"] != ProjectStatus.COMPLETED.value
            or int(row["revision"]) != project.revision
        ):
            return False
        linked = db.execute(
            "SELECT 1 FROM life_project_job WHERE project_id=? AND job_id=?",
            (project.project_id, job_id),
        ).fetchone()
        work = db.execute(
            "SELECT kind,status,payload_json,result_json "
            "FROM autonomous_work_job WHERE job_id=?", (job_id,),
        ).fetchone()
        if linked is None or work is None or work["kind"] != "life-create-artifact" or work["status"] != WorkStatus.COMPLETED.value:
            return False
        try:
            payload = json.loads(work["payload_json"])
            result = json.loads(work["result_json"])
        except (ValueError, TypeError):
            return False
        parameters = payload.get("parameters") if isinstance(payload, dict) else None
        if (
            not isinstance(parameters, dict)
            or payload.get("project_id") != project.project_id
            or payload.get("goal_id") != project.goal_id
            or parameters.get("project_id") != project.project_id
            or parameters.get("audience_id") != project.audience_id
            or parameters.get("artifact_id") != original_result.get("artifact_id")
            or result != original_result
            or result.get("evidence_ref") != evidence_ref
        ):
            return False
        receipt = db.execute(
            "SELECT kind,source,successful,goal_id,action_id,"
            "principal_id,audience,observed_at "
            "FROM goal_evidence_record WHERE evidence_ref=?",
            (evidence_ref,),
        ).fetchone()
        if receipt is None:
            return False
        try:
            observed_at = datetime.fromisoformat(receipt["observed_at"])
        except (ValueError, TypeError, OverflowError):
            return False
        if (
            receipt["kind"] != "operation_receipt"
            or receipt["source"] != "life:creative-capability"
            or receipt["successful"] != 1
            or receipt["goal_id"] != project.goal_id
            or receipt["action_id"] != job_id
            or receipt["principal_id"] != local_sparks_principal().principal_id
            or receipt["audience"] != project.audience_id
            or observed_at.tzinfo is None or observed_at.utcoffset() is None
            or observed_at > now
        ):
            return False
        if db.execute(
            "SELECT 1 FROM life_project_artifact "
            "WHERE project_id=? AND artifact_id=? AND artifact_revision=?",
            (project.project_id, result.get("artifact_id"), result.get("revision")),
        ).fetchone() is None:
            return False
        reviews = db.execute(
            "SELECT technical_outcome,evidence_refs_json,objective_results_json "
            "FROM life_artifact_evaluation "
            "WHERE project_id=? AND artifact_id=? AND artifact_revision=?",
            (project.project_id, result.get("artifact_id"), result.get("revision")),
        ).fetchall()
        for review in reviews:
            try:
                refs = json.loads(review["evidence_refs_json"])
                checks = json.loads(review["objective_results_json"])
            except (ValueError, TypeError):
                continue
            if (
                review["technical_outcome"] == TechnicalOutcome.VALID.value
                and isinstance(refs, list) and evidence_ref in refs
                and isinstance(checks, dict)
                and set(checks) == set(project.brief.objectives)
                and all(value is True for value in checks.values())
            ):
                return True
        return False

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
        # Independently inspect current original bytes *here*, not only
        # in the coordinating caller. A compromised or stale future caller
        # cannot turn old evaluation labels into new verified skill status.
        creative = CreativeStore(self.path)
        artifact = creative.latest(
            output["artifact_id"], "sofia", project.audience_id,
        )
        if (
            artifact is None or artifact.project_id != project.project_id
            or artifact.revision != output["revision"]
        ):
            raise ValueError("current original creative revision not available")
        if not self.native_source_toolchain_current(
            artifact, original_result=output,
        ):
            raise ValueError(
                "original creative tool ID/version does not match "
                "the current verified local native adapter"
            )
        try:
            path, _media = CreativeExplorer(creative).verified_preview(
                output["artifact_id"],
                owner_principal_id="sofia",
                audience_id=project.audience_id,
            )
        except (LookupError, OSError, RuntimeError) as exc:
            raise ValueError("current original creative bytes have no valid digest") from exc
        report = inspect_objective_artifact(
            revision=artifact, path=path,
            objectives=project.brief.objectives,
        )
        if (
            report.revision != output["revision"]
            or not report.eligible_for_independent_completion
        ):
            raise ValueError("current typed objective validation no longer passes")
        now_iso = now.astimezone(timezone.utc).isoformat()
        project_brief = project.brief
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not self._original_proof_current_under_lock(
                db, project=project, job_id=job_id,
                evidence_ref=original_run_evidence_ref,
                original_result=output, now=now,
            ):
                raise ValueError(
                    "original LIFE/RUN/evaluation proof changed before skill promotion"
                )
            key, environment, version, _predecessor = (
                self._current_definition_under_lock(db, project)
            )
            previous_id = None
            if version > 1:
                previous_id, _ = self._definition(project, version=version - 1)
                previous = db.execute(
                    "SELECT status,updated_at FROM life_procedure_catalog "
                    "WHERE procedure_id=?", (previous_id,),
                ).fetchone()
                if (
                    not self._auto_recovery_eligible(project)
                    or previous is None
                    or previous["status"] != "quarantined"
                ):
                    raise PermissionError(
                        "skill successor requires owner approval outside "
                        "non-executable local creative knowledge"
                    )
                # A second look at an old successful RUN cannot rebuild the
                # quarantined skill under a shiny new revision number. Two
                # wholly new completed projects must independently prove it.
                try:
                    quarantined_at = datetime.fromisoformat(
                        previous["updated_at"]
                    )
                except (ValueError, TypeError, OverflowError) as exc:
                    raise ValueError(
                        "corrupt original quarantine timestamp"
                    ) from exc
                if (
                    quarantined_at.tzinfo is None
                    or quarantined_at.utcoffset() is None
                    or project.created_at <= quarantined_at
                    or db.execute(
                        "SELECT 1 FROM life_procedure_proof "
                        "WHERE project_id=? AND procedure_id<>? LIMIT 1",
                        (project.project_id, key),
                    ).fetchone() is not None
                ):
                    raise ValueError(
                        "recovery needs new independent post-quarantine source work"
                    )
            existing = db.execute(
                "SELECT * FROM life_procedure_catalog WHERE procedure_id=?",
                (key,),
            ).fetchone()
            if existing is None:
                db.execute(
                    """INSERT INTO life_procedure_catalog
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        key, version, project.owner_principal_id,
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
                if previous_id is not None:
                    db.execute(
                        "INSERT INTO life_procedure_replacement "
                        "(successor_id,quarantined_predecessor_id,"
                        "disposition,created_at) VALUES(?,?,?,?)",
                        (
                            key, previous_id,
                            "auto_nonexecutable_creative_knowledge", now_iso,
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

    def next_completed_source_page(
        self, *, owner_principal_id: str, audience_id: str, limit: int = 64,
    ) -> tuple[str, ...]:
        """Durably rotate through bounded original LIFE completions.

        A static first-N slice starves later completed projects forever when
        earlier candidates are invalid or already indexed. The scan cursor is
        canonical SQLite metadata, not a new scheduler or execution queue.
        Reserve a page before checking external artifacts; a crash may delay
        work until the next wrap but cannot mint a false verified procedure.
        """
        if (
            not isinstance(owner_principal_id, str) or not owner_principal_id.strip()
            or not isinstance(audience_id, str) or not audience_id.strip()
            or type(limit) is not int or not 1 <= limit <= 128
        ):
            raise ValueError("scoped bounded procedure reconciliation required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT last_project_id FROM life_procedure_scan_cursor "
                "WHERE owner_principal_id=? AND audience_id=?",
                (owner_principal_id, audience_id),
            ).fetchone()
            last_project_id = current[0] if current else ""
            parameters = (
                owner_principal_id, audience_id,
                ProjectStatus.COMPLETED.value, ProjectScope.PERSONAL_PRIVATE.value,
            )
            query = (
                "SELECT project_id FROM life_project "
                "WHERE owner_principal_id=? AND audience_id=? "
                "AND status=? AND scope=?"
            )
            rows = db.execute(
                query + " AND project_id>? ORDER BY project_id LIMIT ?",
                parameters + (last_project_id, limit),
            ).fetchall()
            if not rows and last_project_id:
                rows = db.execute(
                    query + " ORDER BY project_id LIMIT ?",
                    parameters + (limit,),
                ).fetchall()
            if not rows:
                return ()
            db.execute(
                "INSERT INTO life_procedure_scan_cursor "
                "(owner_principal_id,audience_id,last_project_id) "
                "VALUES(?,?,?) ON CONFLICT(owner_principal_id,audience_id) "
                "DO UPDATE SET last_project_id=excluded.last_project_id",
                (owner_principal_id, audience_id, rows[-1][0]),
            )
            return tuple(row[0] for row in rows)

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
        with closing(self._connect()) as db:
            key, environment, _version, _parent = (
                self._current_definition_under_lock(db, project)
            )
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

    def proof_receipts_for_procedure(
        self, procedure_id: str, *, limit: int = 64,
    ) -> tuple[tuple[str, str, str], ...]:
        """Read exact immutable-source references for independent rechecking.

        This reads only the current catalog's named proof group. There is no
        model-supplied source selection, implicit grant or work execution.
        Oversized/corrupt proof sets fail closed instead of partial grading.
        """
        if (
            not isinstance(procedure_id, str)
            or not procedure_id.startswith("life-procedure:")
            or type(limit) is not int or not 2 <= limit <= 128
        ):
            raise ValueError("bounded exact procedure proof required")
        with closing(self._connect()) as db:
            valid = db.execute(
                "SELECT 1 FROM life_procedure_catalog "
                "WHERE procedure_id=? AND status='verified'",
                (procedure_id,),
            ).fetchone()
            if valid is None:
                return ()
            rows = db.execute(
                "SELECT project_id,job_id,evidence_ref "
                "FROM life_procedure_proof WHERE procedure_id=? "
                "ORDER BY project_id,job_id LIMIT ?",
                (procedure_id, limit + 1),
            ).fetchall()
        if len(rows) > limit:
            return ()
        return tuple((row[0], row[1], row[2]) for row in rows)

    def source_projects_for_compatible_precedent(
        self, *, procedure: ProcedureRecord, project: LifeProject,
        limit: int = 64,
    ) -> tuple[str, ...]:
        """Exact compatible proof sources, never a global newest-N gate."""
        if type(limit) is not int or not 2 <= limit <= 128:
            raise ValueError("bounded original procedure source lookup required")
        if not isinstance(procedure, ProcedureRecord):
            return ()
        with closing(self._connect()) as db:
            key, environment, version, _parent = (
                self._current_definition_under_lock(db, project)
            )
        if (
            procedure.procedure_id != key
            or procedure.version != version or procedure.status != "verified"
            or procedure.owner_principal_id != project.owner_principal_id
            or procedure.audience_id != project.audience_id
            or procedure.environment != environment
        ):
            return ()
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT status FROM life_procedure_catalog "
                "WHERE procedure_id=? AND owner_principal_id=? "
                "AND audience_id=? AND environment=?",
                (key, project.owner_principal_id, project.audience_id, environment),
            ).fetchone()
            if row is None or row[0] != "verified":
                return ()
            originals = db.execute(
                "SELECT DISTINCT project_id FROM life_procedure_proof "
                "WHERE procedure_id=? ORDER BY project_id LIMIT ?",
                (key, limit + 1),
            ).fetchall()
        if len(originals) > limit:
            return ()
        return tuple(item[0] for item in originals)

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

    def next_verified_proof_audit_page(
        self, *, limit: int = 16,
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Durably and fairly inspect bounded verified-source project IDs.

        Retrieval for model drafting remains an independent read-only,
        most-recent source view. Only the recurring proof-integrity audit
        rotates; otherwise the same newest N procedures are checked forever.
        A restart resumes the canonical page cursor. Each catalog row remains
        non-executable and all original proof checks occur in the coordinator.
        """
        if type(limit) is not int or not 1 <= limit <= 64:
            raise ValueError("bounded verified procedure audit page required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                "SELECT last_procedure_id FROM life_procedure_source_audit_cursor "
                "WHERE singleton=1",
            ).fetchone()
            last = cursor[0] if cursor else ""
            rows = db.execute(
                "SELECT procedure_id FROM life_procedure_catalog "
                "WHERE status='verified' AND procedure_id>? "
                "ORDER BY procedure_id LIMIT ?",
                (last, limit),
            ).fetchall()
            if not rows and last:
                rows = db.execute(
                    "SELECT procedure_id FROM life_procedure_catalog "
                    "WHERE status='verified' ORDER BY procedure_id LIMIT ?",
                    (limit,),
                ).fetchall()
            if not rows:
                return ()
            db.execute(
                "INSERT INTO life_procedure_source_audit_cursor "
                "(singleton,last_procedure_id) VALUES(1,?) "
                "ON CONFLICT(singleton) DO UPDATE "
                "SET last_procedure_id=excluded.last_procedure_id",
                (rows[-1][0],),
            )
            result = []
            for row in rows:
                origins = db.execute(
                    "SELECT DISTINCT project_id FROM life_procedure_proof "
                    "WHERE procedure_id=? ORDER BY project_id",
                    (row[0],),
                ).fetchall()
                result.append((row[0], tuple(source[0] for source in origins)))
            return tuple(result)

    def quarantine(
        self, procedure_id: str, *, reason: str, now: datetime,
    ) -> bool:
        """CAS-downgrade verified knowledge, preserving first quarantine.

        Multiple coordinators can inspect the same verified source while
        proof becomes unavailable. Only the first verified->quarantined
        transition writes its original reason/time; repeated calls cannot
        erase the first audit decision or count a second invalidation.
        No reinstatement or new permission is implied.
        """
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
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                """UPDATE life_procedure_catalog SET status='quarantined',
                quarantine_reason=?, updated_at=?
                WHERE procedure_id=? AND status='verified'""",
                (
                    reason, now.astimezone(timezone.utc).isoformat(),
                    procedure_id,
                ),
            )
            if changed.rowcount == 1:
                return True
            original = db.execute(
                "SELECT status FROM life_procedure_catalog WHERE procedure_id=?",
                (procedure_id,),
            ).fetchone()
            if original is None:
                raise LookupError("original procedure does not exist")
            if original["status"] == "quarantined":
                return False
            raise ValueError("only verified procedures may be quarantined")
