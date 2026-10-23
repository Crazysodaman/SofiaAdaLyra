"""Canonical production owner for authority-free GA benchmark evidence."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable
from uuid import uuid4

from sofia.platform.application.optional_budget import OptionalAutonomyBudget
from sofia.goals.evidence import GoalEvidenceIndex
from sofia.learning.contracts import DataUse
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.social.model import PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .contracts import (
    AttemptMetrics, ExplorationAdmission, NovelProblemCase, NovelProblemSuite, SuiteSplit,
    answer_digest,
)


_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_CONDITIONS = frozenset({"baseline", "no_memory", "no_skill", "replay_only", "learned"})


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


class GeneralizationService:
    """Measures unfamiliar-task attempts; cannot execute or authorize them."""

    PURPOSE = "generalization-evaluation"

    def __init__(
        self, state_path: str | Path, *, learning,
        admission: Callable[[], ExplorationAdmission] | None = None,
    ) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self._learning = learning
        self._admission = admission
        self._evidence = GoalEvidenceIndex(self.path)
        self._stop = OperatorStopStore(self.path)
        self._budget = OptionalAutonomyBudget(self.path)
        self.workflows = None
        self.skills = None
        self.advanced = None
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ga_problem_suite(
                    suite_id TEXT PRIMARY KEY, source_revision TEXT NOT NULL,
                    owner_principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    seal_digest TEXT NOT NULL UNIQUE, sealed_at TEXT NOT NULL,
                    retention_until TEXT NOT NULL, provenance_ref TEXT NOT NULL,
                    data_grant_id TEXT NOT NULL, case_count INTEGER NOT NULL,
                    retired_at TEXT
                );
                CREATE TABLE IF NOT EXISTS ga_problem_case(
                    suite_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    family_id TEXT NOT NULL, domain TEXT NOT NULL, split TEXT NOT NULL,
                    prompt TEXT NOT NULL, expected_answer_sha256 TEXT NOT NULL,
                    milestone_digests_json TEXT NOT NULL,
                    required_evidence_kinds_json TEXT NOT NULL,
                    PRIMARY KEY(suite_id,case_id),
                    FOREIGN KEY(suite_id) REFERENCES ga_problem_suite(suite_id)
                );
                CREATE TABLE IF NOT EXISTS ga_evaluation_run(
                    run_id TEXT PRIMARY KEY, suite_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    condition TEXT NOT NULL, split TEXT NOT NULL,
                    source_revision TEXT NOT NULL, model_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','completed','expired')),
                    started_at TEXT NOT NULL, completed_at TEXT,
                    data_grant_id TEXT NOT NULL, budget_claim_id TEXT NOT NULL UNIQUE,
                    FOREIGN KEY(suite_id) REFERENCES ga_problem_suite(suite_id)
                );
                CREATE TABLE IF NOT EXISTS ga_case_grade(
                    run_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    answer_sha256 TEXT NOT NULL, objective_success INTEGER NOT NULL,
                    partial_score REAL NOT NULL, milestone_results_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
                    graded_at TEXT NOT NULL, grader TEXT NOT NULL,
                    PRIMARY KEY(run_id,case_id),
                    FOREIGN KEY(run_id) REFERENCES ga_evaluation_run(run_id)
                );
                CREATE TABLE IF NOT EXISTS ga_case_reveal(
                    run_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    revealed_at TEXT NOT NULL,
                    PRIMARY KEY(run_id,case_id)
                );
                CREATE INDEX IF NOT EXISTS ga_run_scope
                ON ga_evaluation_run(principal_id,audience_id,started_at DESC);
            """)

    def attach_workflow_owner(self, goals) -> None:
        """Compose one GOALS/RUN projection after application owners exist."""
        if self.workflows is not None:
            raise RuntimeError("generalization workflow owner already attached")
        from .workflow import GeneralizationWorkflowStore
        from .advanced import AdvancedGeneralizationStore
        self.workflows = GeneralizationWorkflowStore(self.path, goals=goals)
        self.advanced = AdvancedGeneralizationStore(
            self.path, goals=goals, admission=self._require_resource_admission,
            learning=self._learning,
        )

    def attach_skill_owner(self, procedures) -> None:
        """Compose qualification over the existing LIFE procedure catalog."""
        if self.skills is not None:
            raise RuntimeError("generalization skill owner already attached")
        from .skills import LearnedSkillStore
        self.skills = LearnedSkillStore(self.path, procedures=procedures)
        if self.advanced is None:
            raise RuntimeError("generalization workflow owner must be attached first")
        self.advanced.attach_skills(self.skills)

    def _connect(self) -> sqlite3.Connection:
        connection = self._guard.connect(timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _grant(self, principal: PrincipalContext, *, at: datetime):
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        grant = self._learning.active_grant(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            purpose=self.PURPOSE,
            required=(DataUse.OBSERVATION, DataUse.STORAGE, DataUse.FEATURE_EXTRACTION),
            at=at,
        )
        if grant is None:
            raise PermissionError("active exact generalization data-use grant required")
        return grant

    def _require_resource_admission(self) -> ExplorationAdmission:
        if self._admission is None:
            raise PermissionError("production resource admission is unavailable")
        state = self._admission()
        if not isinstance(state, ExplorationAdmission):
            raise TypeError("typed ExplorationAdmission required")
        if state.busy:
            raise PermissionError("gaming, busy, or do-not-disturb blocks exploratory learning")
        if (
            state.resource_pressure >= 0.8
            or state.cpu_percent is not None and state.cpu_percent >= 85
            or state.gpu_percent is not None and state.gpu_percent >= 85
        ):
            raise PermissionError("observed host resource pressure blocks exploratory learning")
        return state

    def register_suite(
        self, suite: NovelProblemSuite, *, principal: PrincipalContext,
    ) -> str:
        if not isinstance(suite, NovelProblemSuite):
            raise TypeError("typed NovelProblemSuite required")
        grant = self._grant(principal, at=suite.sealed_at)
        if _utc(suite.retention_until) > _utc(grant.expires_at):
            raise PermissionError("suite retention exceeds the exact data-use grant")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT seal_digest,owner_principal_id,audience_id FROM ga_problem_suite WHERE suite_id=?",
                (suite.suite_id,),
            ).fetchone()
            if prior is not None:
                if tuple(prior) != (suite.seal_digest, principal.principal_id, principal.audience_id):
                    raise PermissionError("immutable suite identity was reused differently")
                return suite.seal_digest
            db.execute(
                "INSERT INTO ga_problem_suite VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (suite.suite_id, suite.source_revision, principal.principal_id,
                 principal.audience_id, suite.seal_digest,
                 _utc(suite.sealed_at).isoformat(), _utc(suite.retention_until).isoformat(),
                 suite.provenance_ref, grant.grant_id, len(suite.cases), None),
            )
            for case in suite.cases:
                db.execute(
                    "INSERT INTO ga_problem_case VALUES(?,?,?,?,?,?,?,?,?)",
                    (suite.suite_id, case.case_id, case.family_id,
                     case.domain.value, case.split.value, case.prompt,
                     case.expected_answer_sha256,
                     json.dumps(case.milestone_digests, separators=(",", ":")),
                     json.dumps(case.required_evidence_kinds, separators=(",", ":"))),
                )
        return suite.seal_digest

    def begin_run(
        self, *, suite_id: str, principal: PrincipalContext, condition: str,
        split: SuiteSplit, source_revision: str, model_id: str, now: datetime,
    ) -> str:
        moment = _utc(now)
        if condition not in _CONDITIONS:
            raise ValueError("unsupported evaluation condition")
        if not isinstance(split, SuiteSplit) or split is SuiteSplit.TRAIN:
            raise ValueError("evaluation runs use validation or test only")
        if _REVISION.fullmatch(source_revision) is None:
            raise ValueError("exact source revision required")
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 240:
            raise ValueError("bounded actual model ID required")
        if self._stop.current().active:
            raise PermissionError("operator STOP blocks exploratory learning")
        self._require_resource_admission()
        grant = self._grant(principal, at=moment)
        run_id = "ga-run:" + uuid4().hex
        claim_id = "optional:" + run_id
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            suite = db.execute(
                "SELECT source_revision,owner_principal_id,audience_id,retention_until "
                "FROM ga_problem_suite WHERE suite_id=? AND retired_at IS NULL", (suite_id,),
            ).fetchone()
            if suite is None:
                raise LookupError("sealed suite does not exist")
            if suite[1] != principal.principal_id or suite[2] != principal.audience_id:
                raise PermissionError("suite principal/audience scope mismatch")
            if suite[0] != source_revision or moment >= datetime.fromisoformat(suite[3]):
                raise PermissionError("suite revision mismatch or retention expired")
            if not self._budget.reserve_in_transaction(
                db, claim_id=claim_id, task_kind="generalization_evaluation", now=moment,
            ):
                raise PermissionError("optional-work resource budget unavailable")
            db.execute(
                "INSERT INTO ga_evaluation_run VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, suite_id, principal.principal_id, principal.audience_id,
                 condition, split.value, source_revision, model_id, "active",
                 moment.isoformat(), None, grant.grant_id, claim_id),
            )
        return run_id

    def next_case(
        self, run_id: str, *, principal: PrincipalContext, now: datetime,
    ) -> NovelProblemCase | None:
        moment = _utc(now)
        if self._stop.current().active:
            raise PermissionError("operator STOP blocks exploratory learning")
        self._require_resource_admission()
        grant = self._grant(principal, at=moment)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = db.execute("SELECT * FROM ga_evaluation_run WHERE run_id=?", (run_id,)).fetchone()
            if run is None or run["status"] != "active":
                return None
            if (run["principal_id"], run["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("evaluation run scope mismatch")
            if run["data_grant_id"] != grant.grant_id:
                raise PermissionError("evaluation data-use grant was revoked or replaced")
            row = db.execute(
                "SELECT c.* FROM ga_problem_case c LEFT JOIN ga_case_grade g "
                "ON g.run_id=? AND g.case_id=c.case_id WHERE c.suite_id=? AND c.split=? "
                "AND g.case_id IS NULL ORDER BY c.case_id LIMIT 1",
                (run_id, run["suite_id"], run["split"]),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "INSERT OR IGNORE INTO ga_case_reveal VALUES(?,?,?)",
                (run_id, row["case_id"], moment.isoformat()),
            )
        return NovelProblemCase(
            case_id=row["case_id"], family_id=row["family_id"],
            domain=__import__("sofia.generalization.contracts", fromlist=["ProblemDomain"]).ProblemDomain(row["domain"]),
            split=SuiteSplit(row["split"]), prompt=row["prompt"],
            expected_answer_sha256=row["expected_answer_sha256"],
            milestone_digests=tuple(tuple(item) for item in json.loads(row["milestone_digests_json"])),
            required_evidence_kinds=tuple(json.loads(row["required_evidence_kinds_json"])),
        )

    def grade_case(
        self, *, run_id: str, case_id: str, principal: PrincipalContext,
        answer: object, milestones: dict[str, object], evidence_refs: tuple[str, ...],
        metrics: AttemptMetrics, now: datetime,
    ) -> dict[str, object]:
        moment = _utc(now)
        if self._stop.current().active:
            raise PermissionError("operator STOP blocks exploratory learning")
        self._require_resource_admission()
        grant = self._grant(principal, at=moment)
        if not isinstance(metrics, AttemptMetrics) or not isinstance(milestones, dict):
            raise TypeError("typed metrics and milestone mapping required")
        if len(evidence_refs) > 32 or len(set(evidence_refs)) != len(evidence_refs):
            raise ValueError("evidence refs must be unique and bounded")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = db.execute("SELECT * FROM ga_evaluation_run WHERE run_id=?", (run_id,)).fetchone()
            if run is None or run["status"] != "active":
                raise LookupError("active evaluation run required")
            if (run["principal_id"], run["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("evaluation run scope mismatch")
            if run["data_grant_id"] != grant.grant_id:
                raise PermissionError("evaluation data-use grant was revoked or replaced")
            case = db.execute(
                "SELECT * FROM ga_problem_case WHERE suite_id=? AND case_id=? AND split=?",
                (run["suite_id"], case_id, run["split"]),
            ).fetchone()
            if case is None or db.execute(
                "SELECT 1 FROM ga_case_reveal WHERE run_id=? AND case_id=?", (run_id, case_id),
            ).fetchone() is None:
                raise PermissionError("case was not revealed through this run")
            required = tuple(json.loads(case["required_evidence_kinds_json"]))
            observed_kinds = set()
            for ref in evidence_refs:
                evidence = self._evidence.lookup(ref)
                if evidence is None or evidence.principal_id != principal.principal_id or evidence.audience != principal.audience_id:
                    raise PermissionError("missing or cross-scope grader evidence")
                observed_kinds.add(evidence.kind)
            if not set(required).issubset(observed_kinds):
                raise PermissionError("required independent evidence kind missing")
            expected_milestones = dict(json.loads(case["milestone_digests_json"]))
            if set(milestones) - set(expected_milestones):
                raise ValueError("unknown milestone submitted")
            milestone_results = {
                name: name in milestones and answer_digest(milestones[name]) == digest
                for name, digest in expected_milestones.items()
            }
            answer_sha = answer_digest(answer)
            objective = answer_sha == case["expected_answer_sha256"] and all(milestone_results.values())
            denominator = 1 + len(milestone_results)
            partial = (
                int(answer_sha == case["expected_answer_sha256"])
                + sum(milestone_results.values())
            ) / denominator
            body = {
                "inference_route": metrics.inference_route, "model_id": metrics.model_id,
                "elapsed_ms": metrics.elapsed_ms, "estimated_tokens": metrics.estimated_tokens,
                "intervention_count": metrics.intervention_count,
                "tool_call_count": metrics.tool_call_count,
            }
            milestone_json = json.dumps(milestone_results, sort_keys=True)
            evidence_json = json.dumps(evidence_refs)
            metrics_json = json.dumps(body, sort_keys=True)
            prior = db.execute(
                "SELECT answer_sha256,objective_success,partial_score,"
                "milestone_results_json,evidence_refs_json,metrics_json "
                "FROM ga_case_grade WHERE run_id=? AND case_id=?",
                (run_id, case_id),
            ).fetchone()
            submitted = (
                answer_sha, int(objective), partial, milestone_json,
                evidence_json, metrics_json,
            )
            if prior is not None:
                if tuple(prior) != submitted:
                    raise PermissionError("graded case replay changed immutable attempt evidence")
                return {
                    "objective_success": objective, "partial_score": partial,
                    "milestones": milestone_results, "self_report_accepted": False,
                }
            db.execute(
                "INSERT INTO ga_case_grade VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, case_id, answer_sha, int(objective), partial,
                 milestone_json, evidence_json, metrics_json,
                 moment.isoformat(), "host_digest_and_typed_evidence_v1"),
            )
        return {"objective_success": objective, "partial_score": partial,
                "milestones": milestone_results, "self_report_accepted": False}

    def finish_run(
        self, run_id: str, *, principal: PrincipalContext, now: datetime,
    ) -> dict[str, object]:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = db.execute("SELECT * FROM ga_evaluation_run WHERE run_id=?", (run_id,)).fetchone()
            if run is None or (run["principal_id"], run["audience_id"]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("evaluation run scope mismatch")
            totals = db.execute(
                "SELECT COUNT(*),COALESCE(SUM(objective_success),0),"
                "COALESCE(AVG(partial_score),0.0),COALESCE(SUM(json_extract(metrics_json,'$.elapsed_ms')),0),"
                "COALESCE(SUM(json_extract(metrics_json,'$.estimated_tokens')),0),"
                "COALESCE(SUM(json_extract(metrics_json,'$.intervention_count')),0) "
                "FROM ga_case_grade WHERE run_id=?", (run_id,),
            ).fetchone()
            expected = db.execute(
                "SELECT COUNT(*) FROM ga_problem_case WHERE suite_id=? AND split=?",
                (run["suite_id"], run["split"]),
            ).fetchone()[0]
            if totals[0] != expected:
                raise RuntimeError("ungraded cases remain")
            if run["status"] == "active":
                db.execute(
                    "UPDATE ga_evaluation_run SET status='completed',completed_at=? WHERE run_id=? AND status='active'",
                    (moment.isoformat(), run_id),
                )
                self._budget.settle_in_transaction(
                    db, claim_id=run["budget_claim_id"], now=moment, failed=False,
                )
            elif run["status"] != "completed":
                raise RuntimeError("evaluation run is not finishable")
        return {
            "run_id": run_id, "cases": totals[0], "objective_successes": totals[1],
            "success_rate": totals[1] / totals[0] if totals[0] else None,
            "mean_partial_score": totals[2], "elapsed_ms": totals[3],
            "estimated_tokens": totals[4], "interventions": totals[5],
            "condition": run["condition"], "source_revision": run["source_revision"],
            "model_id": run["model_id"], "authority": False,
        }

    def diagnostics(self, *, principal: PrincipalContext, limit: int = 20) -> dict[str, object]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be in 1..100")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT run_id,suite_id,condition,split,source_revision,model_id,status,started_at,completed_at "
                "FROM ga_evaluation_run WHERE principal_id=? AND audience_id=? "
                "ORDER BY started_at DESC,run_id LIMIT ?",
                (principal.principal_id, principal.audience_id, limit),
            ).fetchall()
            output = []
            for row in rows:
                grade = db.execute(
                    "SELECT COUNT(*),COALESCE(SUM(objective_success),0),AVG(partial_score) "
                    "FROM ga_case_grade WHERE run_id=?", (row[0],),
                ).fetchone()
                output.append({**dict(row), "graded": grade[0], "objective_successes": grade[1],
                               "mean_partial_score": grade[2]})
        return {"runs": output, "authority": False,
                "unknown_is_success": False, "model_self_report_is_evidence": False,
                "advanced": None if self.advanced is None else self.advanced.diagnostics(
                    principal=principal,
                )}

    def expire_run(
        self, run_id: str, *, principal: PrincipalContext, now: datetime,
        reason: str,
    ) -> bool:
        """Close an interrupted run without converting missing grades to failure."""
        moment = _utc(now)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
            raise ValueError("bounded expiration reason required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            run = db.execute(
                "SELECT status,principal_id,audience_id,budget_claim_id "
                "FROM ga_evaluation_run WHERE run_id=?", (run_id,),
            ).fetchone()
            if run is None:
                raise LookupError("evaluation run does not exist")
            if (run[1], run[2]) != (principal.principal_id, principal.audience_id):
                raise PermissionError("evaluation run scope mismatch")
            if run[0] != "active":
                return False
            db.execute(
                "UPDATE ga_evaluation_run SET status='expired',completed_at=? "
                "WHERE run_id=? AND status='active'", (moment.isoformat(), run_id),
            )
            self._budget.settle_in_transaction(
                db, claim_id=run[3], now=moment, failed=True,
            )
        return True

    def expire_retention(self, *, now: datetime, limit: int = 64) -> int:
        """Redact expired sealed content without deleting aggregate receipts."""
        moment = _utc(now)
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("limit must be in 1..256")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT suite_id FROM ga_problem_suite WHERE retired_at IS NULL "
                "AND retention_until<=? ORDER BY retention_until,suite_id LIMIT ?",
                (moment.isoformat(), limit),
            ).fetchall()
            retired = 0
            for row in rows:
                active = db.execute(
                    "SELECT 1 FROM ga_evaluation_run WHERE suite_id=? AND status='active'",
                    (row[0],),
                ).fetchone()
                if active is not None:
                    continue
                db.execute(
                    "UPDATE ga_problem_case SET prompt='[retired]',"
                    "expected_answer_sha256=?,milestone_digests_json='[]',"
                    "required_evidence_kinds_json='[]' WHERE suite_id=?",
                    ("0" * 64, row[0]),
                )
                db.execute(
                    "UPDATE ga_problem_suite SET retired_at=? WHERE suite_id=? AND retired_at IS NULL",
                    (moment.isoformat(), row[0]),
                )
                retired += 1
        return retired
