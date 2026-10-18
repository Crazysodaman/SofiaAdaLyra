"""Restart-safe long-horizon projections over canonical GOALS and RUN.

This module never creates a job, invokes a capability, or marks a goal done.
It records why already-authorized GOALS/RUN work forms a bounded plan and
reconciles only the canonical outcomes those owners report.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from sofia.goals.evidence import GoalEvidenceIndex
from sofia.goals.model import GoalStatus
from sofia.goals.service import GoalService
from sofia.run.work import DurableWorkStore, WorkStatus
from sofia.social.model import PrincipalContext
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_TERMINAL = {WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.CANCELLED, WorkStatus.UNCERTAIN}


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    goal_id: str
    job_id: str
    depends_on: tuple[str, ...]
    expected_effect: str
    completion_constraint: str
    risk: str
    information_value: float

    def __post_init__(self) -> None:
        for value, label in ((self.step_id, "step_id"), (self.goal_id, "goal_id"), (self.job_id, "job_id")):
            _identifier(value, label)
        if len(self.depends_on) > 8 or len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("dependencies must be unique and bounded")
        for value in self.depends_on:
            _identifier(value, "dependency")
            if value == self.step_id:
                raise ValueError("step cannot depend on itself")
        for label, value in (
            ("expected_effect", self.expected_effect),
            ("completion_constraint", self.completion_constraint),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError(f"{label} must be bounded nonempty text")
        if self.risk not in {"read_only", "isolated_change", "protected"}:
            raise ValueError("unsupported step risk")
        if isinstance(self.information_value, bool) or not isinstance(self.information_value, (int, float)) or not math.isfinite(self.information_value) or not 0 <= self.information_value <= 1:
            raise ValueError("information_value must be finite in [0,1]")


class GeneralizationWorkflowStore:
    """Non-authoritative plan/checkpoint history joined to GOALS and RUN."""

    def __init__(self, state_path: str | Path, *, goals: GoalService) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self._goals = goals
        self._work = DurableWorkStore(self.path)
        self._evidence = GoalEvidenceIndex(self.path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ga_workflow(
                    workflow_id TEXT PRIMARY KEY, root_goal_id TEXT NOT NULL,
                    original_objective TEXT NOT NULL, principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL, status TEXT NOT NULL,
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, source_case_id TEXT,
                    UNIQUE(root_goal_id,principal_id,audience_id)
                );
                CREATE TABLE IF NOT EXISTS ga_workflow_revision(
                    workflow_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    reason TEXT NOT NULL, evidence_ref TEXT NOT NULL,
                    created_at TEXT NOT NULL, plan_digest TEXT NOT NULL,
                    PRIMARY KEY(workflow_id,revision)
                );
                CREATE TABLE IF NOT EXISTS ga_workflow_step(
                    workflow_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    step_id TEXT NOT NULL, goal_id TEXT NOT NULL, job_id TEXT NOT NULL,
                    depends_on_json TEXT NOT NULL, expected_effect TEXT NOT NULL,
                    completion_constraint TEXT NOT NULL, risk TEXT NOT NULL,
                    information_value REAL NOT NULL,
                    PRIMARY KEY(workflow_id,revision,step_id),
                    UNIQUE(workflow_id,revision,job_id)
                );
                CREATE TABLE IF NOT EXISTS ga_workflow_checkpoint(
                    checkpoint_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                    state_digest TEXT NOT NULL, state_json TEXT NOT NULL,
                    unresolved_count INTEGER NOT NULL, restart_observed INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ga_workflow_channel(
                    workflow_id TEXT NOT NULL, principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL, source_evidence_ref TEXT NOT NULL,
                    target_evidence_ref TEXT NOT NULL, bound_at TEXT NOT NULL,
                    PRIMARY KEY(workflow_id,audience_id)
                );
                CREATE INDEX IF NOT EXISTS ga_workflow_checkpoint_recent
                ON ga_workflow_checkpoint(workflow_id,created_at DESC);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _scope_payload_matches(payload: dict, principal: PrincipalContext) -> bool:
        return (
            payload.get("principal_id") == principal.principal_id
            and payload.get("audience_id") == principal.audience_id
        )

    def _validate_steps(
        self, steps: tuple[WorkflowStep, ...], *, principal: PrincipalContext,
    ) -> None:
        if not isinstance(steps, tuple) or not 1 <= len(steps) <= 32:
            raise ValueError("workflow requires 1..32 typed steps")
        if any(not isinstance(step, WorkflowStep) for step in steps):
            raise TypeError("workflow steps must be typed")
        ids = {step.step_id for step in steps}
        if len(ids) != len(steps):
            raise ValueError("step IDs must be unique")
        visible = {goal.id: goal for goal in self._goals.list_visible(principal)}
        for step in steps:
            if any(dependency not in ids for dependency in step.depends_on):
                raise ValueError("dependency names an unknown step")
            goal = visible.get(step.goal_id)
            if goal is None or goal.status in {
                GoalStatus.REJECTED, GoalStatus.CANCELLED, GoalStatus.EXPIRED,
                GoalStatus.SUPERSEDED,
            }:
                raise PermissionError("step goal is not visible and live")
            job = self._work.get(step.job_id)
            if job.risk != step.risk or job.completion_condition != step.completion_constraint:
                raise ValueError("step changed canonical RUN risk or completion constraint")
            if not self._scope_payload_matches(job.payload, principal):
                raise PermissionError("RUN job lacks exact workflow principal/audience scope")
        # Deterministic acyclic dependency check.
        dependencies = {item.step_id: set(item.depends_on) for item in steps}
        resolved: set[str] = set()
        while len(resolved) < len(steps):
            ready = {key for key, value in dependencies.items() if key not in resolved and value <= resolved}
            if not ready:
                raise ValueError("workflow dependency cycle detected")
            resolved.update(ready)

    @staticmethod
    def _plan_digest(steps: tuple[WorkflowStep, ...]) -> str:
        body = [{
            "step_id": step.step_id, "goal_id": step.goal_id,
            "job_id": step.job_id, "depends_on": step.depends_on,
            "expected_effect": step.expected_effect,
            "completion_constraint": step.completion_constraint,
            "risk": step.risk, "information_value": step.information_value,
        } for step in steps]
        return sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def create(
        self, *, root_goal_id: str, original_objective: str,
        principal: PrincipalContext, steps: tuple[WorkflowStep, ...],
        evidence_ref: str, now: datetime, source_case_id: str | None = None,
    ) -> str:
        moment = _utc(now)
        visible = {goal.id: goal for goal in self._goals.list_visible(principal)}
        root = visible.get(root_goal_id)
        if root is None or root.status not in {GoalStatus.ACTIVE, GoalStatus.CANDIDATE, GoalStatus.BLOCKED, GoalStatus.PAUSED}:
            raise PermissionError("root goal is not visible and live")
        if not isinstance(original_objective, str) or not original_objective.strip() or len(original_objective) > 1000:
            raise ValueError("bounded original objective required")
        evidence = self._evidence.lookup(evidence_ref)
        if evidence is None or evidence.principal_id != principal.principal_id or evidence.audience != principal.audience_id:
            raise PermissionError("scoped workflow source evidence required")
        self._validate_steps(steps, principal=principal)
        workflow_id = "ga-workflow:" + uuid4().hex
        digest = self._plan_digest(steps)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT workflow_id,original_objective,revision,source_case_id "
                "FROM ga_workflow WHERE root_goal_id=? AND principal_id=? AND audience_id=?",
                (root_goal_id, principal.principal_id, principal.audience_id),
            ).fetchone()
            if existing is not None:
                prior = db.execute(
                    "SELECT plan_digest,evidence_ref FROM ga_workflow_revision "
                    "WHERE workflow_id=? AND revision=?",
                    (existing[0], existing[2]),
                ).fetchone()
                if (
                    existing[1] != original_objective.strip()
                    or existing[3] != source_case_id
                    or prior is None or prior[0] != digest or prior[1] != evidence_ref
                ):
                    raise PermissionError("workflow replay changed immutable plan evidence")
                return existing[0]
            db.execute(
                "INSERT INTO ga_workflow VALUES(?,?,?,?,?,'active',1,?,?,?)",
                (workflow_id, root_goal_id, original_objective.strip(),
                 principal.principal_id, principal.audience_id,
                 moment.isoformat(), moment.isoformat(), source_case_id),
            )
            db.execute(
                "INSERT INTO ga_workflow_revision VALUES(?,?,?,?,?,?)",
                (workflow_id, 1, "initial bounded plan", evidence_ref,
                 moment.isoformat(), digest),
            )
            self._insert_steps(db, workflow_id, 1, steps)
        return workflow_id

    @staticmethod
    def _insert_steps(db, workflow_id: str, revision: int, steps: tuple[WorkflowStep, ...]) -> None:
        for step in steps:
            db.execute(
                "INSERT INTO ga_workflow_step VALUES(?,?,?,?,?,?,?,?,?,?)",
                (workflow_id, revision, step.step_id, step.goal_id, step.job_id,
                 json.dumps(step.depends_on), step.expected_effect,
                 step.completion_constraint, step.risk, step.information_value),
            )

    def checkpoint(
        self, workflow_id: str, *, principal: PrincipalContext, now: datetime,
        restart_observed: bool = False,
    ) -> dict[str, object]:
        moment = _utc(now)
        if type(restart_observed) is not bool:
            raise TypeError("restart_observed must be bool")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            workflow = db.execute("SELECT * FROM ga_workflow WHERE workflow_id=?", (workflow_id,)).fetchone()
            if workflow is None or (workflow["principal_id"], workflow["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("workflow scope mismatch")
            rows = db.execute(
                "SELECT * FROM ga_workflow_step WHERE workflow_id=? AND revision=? ORDER BY step_id",
                (workflow_id, workflow["revision"]),
            ).fetchall()
            states = []
            unresolved = 0
            for row in rows:
                job = self._work.get(row["job_id"])
                result = job.result if isinstance(job.result, dict) else {}
                artifacts = {key: result[key] for key in ("artifact_id", "revision", "evidence_ref", "receipt_id") if key in result}
                external_controls = {
                    "job_fingerprint": job.fingerprint,
                    **{
                        key: job.payload[key]
                        for key in (
                            "action_id", "approval_id", "approval_ref",
                            "idempotency_key", "rollback_ref",
                        )
                        if isinstance(job.payload.get(key), str)
                    },
                }
                if job.status is not WorkStatus.COMPLETED:
                    unresolved += 1
                states.append({
                    "step_id": row["step_id"], "job_id": job.job_id,
                    "status": job.status.value, "reason": job.reason,
                    "attempt_count": job.attempt_count, "artifacts": artifacts,
                    "external_controls": external_controls,
                    "uncertain_external_effect": job.status is WorkStatus.UNCERTAIN,
                })
            encoded = json.dumps(states, sort_keys=True, separators=(",", ":"))
            digest = sha256(encoded.encode()).hexdigest()
            checkpoint_id = "ga-checkpoint:" + uuid4().hex
            db.execute(
                "INSERT INTO ga_workflow_checkpoint VALUES(?,?,?,?,?,?,?,?)",
                (checkpoint_id, workflow_id, workflow["revision"], moment.isoformat(),
                 digest, encoded, unresolved, int(restart_observed)),
            )
        return {"checkpoint_id": checkpoint_id, "revision": workflow["revision"],
                "states": states, "unresolved": unresolved, "state_digest": digest}

    def ready_steps(
        self, workflow_id: str, *, principal: PrincipalContext,
    ) -> tuple[dict[str, object], ...]:
        with closing(self._connect()) as db:
            workflow = db.execute("SELECT * FROM ga_workflow WHERE workflow_id=?", (workflow_id,)).fetchone()
            if workflow is None or (workflow["principal_id"], workflow["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("workflow scope mismatch")
            rows = db.execute(
                "SELECT * FROM ga_workflow_step WHERE workflow_id=? AND revision=?",
                (workflow_id, workflow["revision"]),
            ).fetchall()
        statuses = {row["step_id"]: self._work.get(row["job_id"]).status for row in rows}
        ready = []
        for row in rows:
            job = self._work.get(row["job_id"])
            dependencies = tuple(json.loads(row["depends_on_json"]))
            if job.status is WorkStatus.QUEUED and all(statuses[item] is WorkStatus.COMPLETED for item in dependencies):
                ready.append({
                    "step_id": row["step_id"], "job_id": row["job_id"],
                    "risk": row["risk"], "information_value": row["information_value"],
                    "expected_effect": row["expected_effect"], "authority": False,
                })
        return tuple(sorted(ready, key=lambda item: (-float(item["information_value"]), str(item["step_id"]))))

    def replan(
        self, workflow_id: str, *, principal: PrincipalContext,
        steps: tuple[WorkflowStep, ...], reason: str, evidence_ref: str,
        expected_revision: int, now: datetime,
    ) -> int:
        moment = _utc(now)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 800:
            raise ValueError("bounded replan reason required")
        evidence = self._evidence.lookup(evidence_ref)
        if evidence is None or evidence.principal_id != principal.principal_id or evidence.audience != principal.audience_id:
            raise PermissionError("scoped changed-environment evidence required")
        self._validate_steps(steps, principal=principal)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            workflow = db.execute("SELECT * FROM ga_workflow WHERE workflow_id=?", (workflow_id,)).fetchone()
            if workflow is None or (workflow["principal_id"], workflow["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("workflow scope mismatch")
            if workflow["revision"] != expected_revision or expected_revision >= 8:
                raise RuntimeError("workflow changed or bounded replan limit reached")
            prior_jobs = db.execute(
                "SELECT job_id FROM ga_workflow_step WHERE workflow_id=? AND revision=?",
                (workflow_id, expected_revision),
            ).fetchall()
            if not any(self._work.get(row[0]).status in {WorkStatus.FAILED, WorkStatus.UNCERTAIN, WorkStatus.CANCELLED} for row in prior_jobs):
                raise ValueError("replan requires a grounded failed/uncertain prior step")
            revision = expected_revision + 1
            db.execute(
                "UPDATE ga_workflow SET revision=?,updated_at=? WHERE workflow_id=? AND revision=?",
                (revision, moment.isoformat(), workflow_id, expected_revision),
            )
            db.execute(
                "INSERT INTO ga_workflow_revision VALUES(?,?,?,?,?,?)",
                (workflow_id, revision, reason.strip(), evidence_ref,
                 moment.isoformat(), self._plan_digest(steps)),
            )
            self._insert_steps(db, workflow_id, revision, steps)
        return revision

    def bind_channel(
        self, workflow_id: str, *, source: PrincipalContext,
        target: PrincipalContext, source_evidence_ref: str,
        target_evidence_ref: str, now: datetime,
    ) -> None:
        moment = _utc(now)
        if source.principal_id != target.principal_id:
            raise PermissionError("cross-principal workflow continuation denied")
        records = (
            self._evidence.lookup(source_evidence_ref),
            self._evidence.lookup(target_evidence_ref),
        )
        if (
            any(item is None or item.kind != "conversation_message" for item in records)
            or records[0].principal_id != source.principal_id
            or records[0].audience != source.audience_id
            or records[1].principal_id != target.principal_id
            or records[1].audience != target.audience_id
        ):
            raise PermissionError("authenticated evidence from both channel audiences required")
        with closing(self._connect()) as db, db:
            workflow = db.execute("SELECT principal_id,audience_id FROM ga_workflow WHERE workflow_id=?", (workflow_id,)).fetchone()
            if workflow is None or tuple(workflow) != (source.principal_id, source.audience_id):
                raise PermissionError("source channel does not own workflow")
            db.execute(
                "INSERT OR IGNORE INTO ga_workflow_channel VALUES(?,?,?,?,?,?)",
                (workflow_id, target.principal_id, target.audience_id,
                 source_evidence_ref, target_evidence_ref, moment.isoformat()),
            )

    def resume_summary(
        self, workflow_id: str, *, principal: PrincipalContext,
    ) -> dict[str, object]:
        with closing(self._connect()) as db:
            workflow = db.execute("SELECT * FROM ga_workflow WHERE workflow_id=?", (workflow_id,)).fetchone()
            if workflow is None:
                raise LookupError("workflow does not exist")
            native = (workflow["principal_id"], workflow["audience_id"]) == (principal.principal_id, principal.audience_id)
            bound = db.execute(
                "SELECT 1 FROM ga_workflow_channel WHERE workflow_id=? AND principal_id=? AND audience_id=?",
                (workflow_id, principal.principal_id, principal.audience_id),
            ).fetchone() is not None
            if not native and not bound:
                raise PermissionError("workflow is not authorized for this audience")
            checkpoint = db.execute(
                "SELECT checkpoint_id,created_at,state_digest,unresolved_count,restart_observed "
                "FROM ga_workflow_checkpoint WHERE workflow_id=? ORDER BY created_at DESC LIMIT 1",
                (workflow_id,),
            ).fetchone()
        return {
            "workflow_id": workflow_id, "root_goal_id": workflow["root_goal_id"],
            "original_objective": workflow["original_objective"],
            "status": workflow["status"], "revision": workflow["revision"],
            "checkpoint": None if checkpoint is None else dict(checkpoint),
            "transcript_included": False, "execution_authorized": False,
        }

    def reliability(self, *, principal: PrincipalContext) -> dict[str, object]:
        with closing(self._connect()) as db:
            workflows = db.execute(
                "SELECT workflow_id,created_at,status FROM ga_workflow WHERE principal_id=? AND audience_id=?",
                (principal.principal_id, principal.audience_id),
            ).fetchall()
            buckets = {"one_step": [], "multistep": [], "restarted": [], "24h": [], "72h": []}
            for workflow in workflows:
                checkpoints = db.execute(
                    "SELECT created_at,unresolved_count,restart_observed FROM ga_workflow_checkpoint "
                    "WHERE workflow_id=? ORDER BY created_at", (workflow[0],),
                ).fetchall()
                if not checkpoints:
                    continue
                steps = db.execute(
                    "SELECT COUNT(*) FROM ga_workflow_step WHERE workflow_id=? AND revision=("
                    "SELECT revision FROM ga_workflow WHERE workflow_id=?)", (workflow[0], workflow[0]),
                ).fetchone()[0]
                elapsed = (datetime.fromisoformat(checkpoints[-1][0]) - datetime.fromisoformat(workflow[1])).total_seconds()
                success = checkpoints[-1][1] == 0
                buckets["one_step" if steps == 1 else "multistep"].append(success)
                if any(row[2] for row in checkpoints):
                    buckets["restarted"].append(success)
                if elapsed >= 24 * 3600:
                    buckets["24h"].append(success)
                if elapsed >= 72 * 3600:
                    buckets["72h"].append(success)
        return {key: {"observed": len(values), "success_rate": (sum(values) / len(values) if values else None)} for key, values in buckets.items()}
