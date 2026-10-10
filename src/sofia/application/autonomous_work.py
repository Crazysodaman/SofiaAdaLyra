"""Evidence-driven autonomous engineering over EVOLVE, DEV, RUN, and ACT."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess

from sofia.act.outreach import Importance, OutreachCategory
from sofia.application.presence import (
    InitiativeEvent, PresenceInitiativeEngine, WorldAvailability,
    WorldEpistemicState, WorldObservation,
)
from sofia.application.evolution import SofiaEvolutionService
from sofia.evolve.orchestrator import CodeEvolutionOrchestrator
from sofia.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkJob, WorkResult, WorkStatus,
)


@dataclass(frozen=True, slots=True)
class ImprovementDiagnostic:
    diagnostic_id: str
    source_ref: str
    summary: str
    details: dict[str, object]
    allowed_paths: tuple[str, ...]
    tests: tuple[str, ...]
    success_metric: str
    observed_at: datetime
    severity: int = 50

    def __post_init__(self) -> None:
        if not self.diagnostic_id or len(self.diagnostic_id) > 160:
            raise ValueError("diagnostic_id must be bounded")
        if not self.source_ref.strip() or not self.summary.strip():
            raise ValueError("diagnostic source and summary required")
        if not self.allowed_paths or len(self.allowed_paths) > 64:
            raise ValueError("bounded allowed_paths required")
        if len(self.tests) > 32:
            raise ValueError("tests must be bounded")
        if not self.success_metric.strip():
            raise ValueError("success_metric required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if type(self.severity) is not int or not 1 <= self.severity <= 100:
            raise ValueError("severity must be in 1..100")
        json.dumps(self.details, sort_keys=True, ensure_ascii=False)


class AutonomousWorkCoordinator:
    """The single production owner of discovery-to-review engineering work."""

    def __init__(
        self, *, state_path: Path | str, workspace: Path,
        evolution: SofiaEvolutionService,
        code_orchestrator: CodeEvolutionOrchestrator,
        presence: PresenceInitiativeEngine,
        max_workers: int = 2,
    ) -> None:
        self.path = Path(state_path)
        self.workspace = workspace.resolve()
        if not self.workspace.is_dir():
            raise ValueError("engineering workspace must exist")
        if not isinstance(evolution, SofiaEvolutionService):
            raise TypeError("evolution must be SofiaEvolutionService")
        if not isinstance(code_orchestrator, CodeEvolutionOrchestrator):
            raise TypeError("code_orchestrator must be CodeEvolutionOrchestrator")
        if not isinstance(presence, PresenceInitiativeEngine):
            raise TypeError("presence must be PresenceInitiativeEngine")
        self.evolution, self.code_orchestrator, self.presence = evolution, code_orchestrator, presence
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS autonomous_improvement_diagnostic (
                    diagnostic_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    source_ref TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    allowed_paths_json TEXT NOT NULL,
                    tests_json TEXT NOT NULL,
                    success_metric TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('new','scheduled','ignored')),
                    proposal_id TEXT,
                    reason TEXT
                );
                CREATE INDEX IF NOT EXISTS autonomous_diagnostic_new
                    ON autonomous_improvement_diagnostic(status,severity DESC,observed_at);
                CREATE TABLE IF NOT EXISTS autonomous_discovery_cursor (
                    source TEXT PRIMARY KEY,
                    cursor_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
        self.work_store = DurableWorkStore(self.path)
        self.work_store.recover(now=datetime.now(timezone.utc))
        self.manager = TaskExecutionManager(
            self.work_store,
            {
                "evolve-code-build": self._build_candidate,
                "runtime-failure-review": self._review_runtime_failure,
            },
            max_workers=max_workers,
        )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _fingerprint(value: object) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256(encoded.encode("utf-8")).hexdigest()

    def record_diagnostic(self, diagnostic: ImprovementDiagnostic) -> bool:
        if not isinstance(diagnostic, ImprovementDiagnostic):
            raise TypeError("diagnostic must be ImprovementDiagnostic")
        for path in diagnostic.allowed_paths:
            relative = Path(path.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("diagnostic write scope escapes workspace")
        fingerprint = self._fingerprint({
            "source": diagnostic.source_ref, "summary": diagnostic.summary,
            "details": diagnostic.details, "paths": diagnostic.allowed_paths,
            "tests": diagnostic.tests, "metric": diagnostic.success_metric,
        })
        with closing(self._connect()) as db, db:
            existing = db.execute(
                "SELECT fingerprint FROM autonomous_improvement_diagnostic WHERE diagnostic_id=?",
                (diagnostic.diagnostic_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] != fingerprint:
                    raise ValueError("diagnostic_id reused for different evidence")
                return False
            changed = db.execute(
                """INSERT OR IGNORE INTO autonomous_improvement_diagnostic
                VALUES(?,?,?,?,?,?,?,?,?,?,'new',NULL,'evidence_recorded')""",
                (
                    diagnostic.diagnostic_id, fingerprint, diagnostic.source_ref,
                    diagnostic.summary.strip(), json.dumps(diagnostic.details, sort_keys=True),
                    json.dumps(diagnostic.allowed_paths), json.dumps(diagnostic.tests),
                    diagnostic.success_metric.strip(),
                    diagnostic.observed_at.astimezone(timezone.utc).isoformat(), diagnostic.severity,
                ),
            )
        return changed.rowcount == 1

    def scan_runtime_failures(self, *, now: datetime) -> int:
        """Discover actual durable failures; do not guess a code fix for them."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        now = now.astimezone(timezone.utc)
        with closing(self._connect()) as db, db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='application_background_claims'"
            ).fetchone() is None:
                return 0
            rows = db.execute(
                """SELECT task_kind,error_type,MAX(finished_at) AS seen,COUNT(*) AS occurrences
                FROM application_background_claims
                WHERE status='failed' AND finished_at IS NOT NULL
                GROUP BY task_kind,error_type HAVING COUNT(*) >= 2 LIMIT 16"""
            ).fetchall()
            created = 0
            for row in rows:
                fingerprint = "runtime-failure:" + self._fingerprint(dict(row))[:40]
                before = db.total_changes
                db.execute(
                    """INSERT OR IGNORE INTO autonomous_work_job
                    (job_id,kind,fingerprint,payload_json,priority,resource_cost,risk,
                     completion_condition,status,created_at,updated_at,deadline,
                     attempt_count,result_json,reason)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,NULL,?)""",
                    (
                        "work:" + fingerprint, "runtime-failure-review", fingerprint,
                        json.dumps(dict(row), sort_keys=True), 55, 5, "read_only",
                        "Record a bounded diagnostic summary of the repeated durable failure.",
                        WorkStatus.QUEUED.value, now.isoformat(), now.isoformat(),
                        (now + timedelta(minutes=10)).isoformat(), "discovered_repeated_failure",
                    ),
                )
                if db.total_changes > before:
                    db.execute(
                        "INSERT INTO autonomous_work_event(job_id,from_status,to_status,reason,occurred_at) VALUES(?,NULL,'queued','discovered_repeated_failure',?)",
                        ("work:" + fingerprint, now.isoformat()),
                    )
                    created += 1
        return created

    def discover_improvements(self, *, now: datetime, limit: int = 1) -> int:
        """Promote reviewed diagnostics into canonical EVOLVE proposals and RUN jobs."""
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM autonomous_improvement_diagnostic WHERE status='new' ORDER BY severity DESC,observed_at LIMIT ?",
                (limit,),
            ).fetchall()
        if not rows:
            return 0
        head = subprocess.run(
            ("git", "rev-parse", "HEAD"), cwd=self.workspace, text=True,
            capture_output=True, check=False, timeout=15,
        )
        if head.returncode or len(head.stdout.strip()) != 40:
            return 0
        base_sha = head.stdout.strip()
        created = 0
        for row in rows:
            allowed_paths = tuple(json.loads(row["allowed_paths_json"]))
            tests = tuple(json.loads(row["tests_json"]))
            if not all((self.workspace / path).exists() for path in allowed_paths):
                with closing(self._connect()) as db, db:
                    db.execute(
                        "UPDATE autonomous_improvement_diagnostic SET status='ignored',reason='approved_path_missing' WHERE diagnostic_id=? AND status='new'",
                        (row["diagnostic_id"],),
                    )
                continue
            evidence_id = "autonomous-diagnostic:" + row["fingerprint"][:32]
            observed = datetime.fromisoformat(row["observed_at"])
            self.evolution.record_evidence(
                evidence_id=evidence_id, kind="engineering-diagnostic",
                source_ref=row["source_ref"], summary=row["summary"],
                payload=json.loads(row["details_json"]), observed_at=observed,
                recorded_at=now,
            )
            proposal_id = "autonomous-code:" + row["fingerprint"][:32]
            try:
                self.evolution.propose_code(
                    proposal_id=proposal_id, base_sha=base_sha,
                    prompt=(
                        "Fix the observed, evidence-backed problem without unrelated refactoring. "
                        + row["summary"] + "\nSuccess metric: " + row["success_metric"]
                    ),
                    allowed_paths=allowed_paths, tests=tests,
                    evidence_ids=(evidence_id,), reason=row["summary"],
                    rollback_plan="Discard the isolated DEV candidate; production is unchanged.",
                    success_metric=row["success_metric"], now=now,
                )
            except RuntimeError as exc:
                if "overlap" not in str(exc).casefold():
                    raise
                with closing(self._connect()) as db, db:
                    db.execute(
                        "UPDATE autonomous_improvement_diagnostic SET status='ignored',reason='overlapping_open_proposal' WHERE diagnostic_id=? AND status='new'",
                        (row["diagnostic_id"],),
                    )
                continue
            plan_fingerprint = row["fingerprint"][:40]
            plan_id = self.work_store.create_plan(
                fingerprint=plan_fingerprint,
                title="Build isolated improvement candidate: " + row["summary"][:120],
                evidence_ref=evidence_id,
                now=now,
            )
            job = self.manager.submit(
                kind="evolve-code-build", fingerprint="build:" + row["fingerprint"][:40],
                payload={"proposal_id": proposal_id, "diagnostic_id": row["diagnostic_id"]},
                priority=int(row["severity"]), resource_cost=60, risk="isolated_change",
                completion_condition="A scoped DEV candidate passes its declared tests and reaches operator review.",
                now=now, deadline=now + timedelta(minutes=45),
            )
            self.work_store.attach_step(
                plan_id=plan_id, job_id=job.job_id, step_order=0,
            )
            with closing(self._connect()) as db, db:
                db.execute(
                    "UPDATE autonomous_improvement_diagnostic SET status='scheduled',proposal_id=?,reason='evolve_proposal_created' WHERE diagnostic_id=? AND status='new'",
                    (proposal_id, row["diagnostic_id"]),
                )
            created += 1
        return created

    def _build_candidate(self, job: WorkJob, cancel) -> WorkResult:
        if cancel.is_set():
            return WorkResult(WorkStatus.FAILED, {}, "cancelled_before_dev")
        proposal_id = str(job.payload["proposal_id"])
        try:
            build_time = max(datetime.now(timezone.utc), job.updated_at)
            candidate = self.code_orchestrator.build_candidate(
                proposal_id, now=build_time,
            )
        except Exception as exc:
            failed_at = max(datetime.now(timezone.utc), job.updated_at)
            error_type = type(exc).__name__
            failure_id = "dev-build-failure:" + sha256(
                job.job_id.encode("utf-8")
            ).hexdigest()[:32]
            self.evolution.record_evidence(
                evidence_id=failure_id, kind="engineering-failure",
                source_ref=f"dev:build:{proposal_id}",
                summary=f"Isolated DEV candidate build failed with {error_type}.",
                payload={"proposal_id": proposal_id, "error_type": error_type},
                observed_at=failed_at, recorded_at=failed_at,
            )
            self.evolution.lifecycle.attach_evidence(proposal_id, failure_id)
            observation = WorldObservation(
                observation_id=failure_id, subject_id=f"evolve:{proposal_id}",
                predicate="engineering.candidate_failed", source_id="dev:isolated-candidate",
                observed_at=failed_at, expires_at=failed_at + timedelta(days=2),
                confidence=1.0, epistemic_state=WorldEpistemicState.OBSERVED,
                availability=WorldAvailability.DEGRADED,
                value={"proposal_id": proposal_id, "error_type": error_type},
                audience_id="sparks",
            )
            self.presence.consider(InitiativeEvent(
                event_id=f"dev-failed:{job.job_id}", trigger_kind="dev_finding",
                observation=observation,
                content=(
                    f"The isolated improvement candidate for {proposal_id} failed "
                    f"during {error_type}. Production was not changed."
                ),
                created_at=failed_at, expires_at=failed_at + timedelta(days=2),
                category=OutreachCategory.OPERATIONAL,
                importance=Importance.ROUTINE, salience=0.55,
            ))
            return WorkResult(
                WorkStatus.FAILED, {"proposal_id": proposal_id, "error_type": error_type},
                error_type,
            )
        changed = list(candidate.get("changed_paths", ()))
        evidence_id = str(candidate["evidence_id"])
        now = datetime.now(timezone.utc)
        observation = WorldObservation(
            observation_id=evidence_id, subject_id=f"evolve:{proposal_id}",
            predicate="engineering.candidate_ready", source_id="dev:isolated-candidate",
            observed_at=now, expires_at=now + timedelta(days=7), confidence=1.0,
            epistemic_state=WorldEpistemicState.OBSERVED,
            availability=WorldAvailability.NOT_APPLICABLE,
            value={"proposal_id": proposal_id, "changed_paths": changed}, audience_id="sparks",
        )
        self.presence.consider(InitiativeEvent(
            event_id=f"dev-review:{proposal_id}", trigger_kind="dev_finding",
            observation=observation,
            content=(
                f"I built and tested an isolated improvement candidate for {proposal_id}. "
                f"It changes {len(changed)} reviewed path(s). Production is unchanged; it is ready for your review."
            ),
            created_at=now, expires_at=now + timedelta(days=7),
            category=OutreachCategory.OPERATIONAL, importance=Importance.IMPORTANT,
            salience=0.8,
        ))
        return WorkResult(
            WorkStatus.WAITING_APPROVAL,
            {
                "proposal_id": proposal_id, "evidence_id": evidence_id,
                "changed_paths": changed, "tests_passed": candidate.get("tests_passed"),
                "patch_sha256": sha256(str(candidate.get("patch", "")).encode()).hexdigest(),
            },
            "candidate_built_waiting_operator_review",
        )

    @staticmethod
    def _review_runtime_failure(job: WorkJob, cancel) -> WorkResult:
        if cancel.is_set():
            return WorkResult(WorkStatus.FAILED, {}, "cancelled")
        return WorkResult(
            WorkStatus.COMPLETED,
            {"observation": job.payload, "conclusion": "repeated_failure_requires_scoped_diagnosis"},
            "durable_failure_summarized_without_guessing_fix",
        )

    def tick(self, *, now: datetime, busy: bool = False, resource_pressure: float = 0.0) -> dict[str, int]:
        failures = self.scan_runtime_failures(now=now)
        proposals = self.discover_improvements(now=now)
        started = self.manager.tick(now=now, busy=busy, resource_pressure=resource_pressure)
        return {"failures_discovered": failures, "proposals_created": proposals, "jobs_started": started}

    def has_pending(self) -> bool:
        return bool(self.work_store.ready(limit=1))

    def close(self) -> None:
        self.manager.close(wait=False)
