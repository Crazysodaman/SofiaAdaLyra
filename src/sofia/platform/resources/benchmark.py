"""Durable, idle-gated HNF benchmark scheduling on canonical RUN."""
from __future__ import annotations

from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import tempfile
from time import perf_counter
from typing import Callable

from sofia.platform.resources.inventory import HardwareInventoryStore, InventoryRecord
from sofia.platform.resources.inventory import HardwareTelemetryStore
from sofia.platform.run.work import (
    DurableWorkStore, TaskExecutionManager, WorkJob, WorkResult, WorkStatus,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


class BenchmarkKind(str, Enum):
    CPU_SINGLE = "cpu_single"
    CPU_MULTI = "cpu_multi"
    MEMORY = "memory"
    STORAGE = "storage"
    GPU = "gpu"
    NETWORK = "network"
    LLM = "llm"
    MODULE = "module"


@dataclass(frozen=True, slots=True)
class IdleAdmission:
    eligible: bool
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    observed_at: datetime

    def __post_init__(self) -> None:
        if type(self.eligible) is not bool:
            raise TypeError("eligible must be bool")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if type(self.reasons) is not tuple or type(self.evidence_refs) is not tuple:
            raise TypeError("reasons/evidence_refs must be tuples")
        if self.eligible and self.reasons:
            raise ValueError("eligible admission cannot have rejection reasons")


@dataclass(frozen=True, slots=True)
class BenchmarkMeasurement:
    name: str
    value: int | float
    unit: str
    sample_count: int = 1
    variance: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.unit.strip():
            raise ValueError("measurement name and unit required")
        if type(self.value) not in (int, float) or self.value < 0:
            raise ValueError("measurement value must be nonnegative")
        if type(self.sample_count) is not int or not 1 <= self.sample_count <= 10_000:
            raise ValueError("sample_count must be in 1..10000")
        if self.variance is not None and (
            type(self.variance) not in (int, float) or self.variance < 0
        ):
            raise ValueError("variance must be nonnegative or None")


@dataclass(frozen=True, slots=True)
class BenchmarkExecution:
    measurements: tuple[BenchmarkMeasurement, ...]
    configuration: dict[str, object]
    resource_usage: dict[str, object]
    evidence_refs: tuple[str, ...] = ()
    model_id: str | None = None
    model_digest: str | None = None
    environmental_conditions: dict[str, object] | None = None


BenchmarkRunner = Callable[[WorkJob, object], BenchmarkExecution]
IdleObserver = Callable[[str, str, BenchmarkKind, datetime], IdleAdmission]
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")


def resolve_source_revision(workspace: Path) -> str | None:
    """Resolve exact runtime source or refuse an unverifiable/dirty checkout."""
    configured = os.environ.get("SOFIA_SOURCE_REVISION", "").strip()
    if configured:
        return configured if _GIT_REVISION.fullmatch(configured) is not None else None
    try:
        status = subprocess.run(
            ("git", "status", "--porcelain", "--untracked-files=no"),
            cwd=workspace, text=True, capture_output=True, check=False, timeout=5,
        )
        revision = subprocess.run(
            ("git", "rev-parse", "HEAD"), cwd=workspace, text=True,
            capture_output=True, check=False, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = revision.stdout.strip()
    if status.returncode or status.stdout.strip() or revision.returncode:
        return None
    return value if _GIT_REVISION.fullmatch(value) is not None else None


class VerifiedIdleObserver:
    """Fail-closed admission from STOP, activity, telemetry, jobs and leases."""

    def __init__(
        self, *, state_path: Path, telemetry: HardwareTelemetryStore,
        maximum_age: timedelta = timedelta(minutes=2), policy_enabled: bool = True,
    ) -> None:
        if not isinstance(state_path, Path) or not isinstance(telemetry, HardwareTelemetryStore):
            raise TypeError("state_path and telemetry are required")
        if not isinstance(maximum_age, timedelta) or maximum_age <= timedelta(0):
            raise ValueError("maximum_age must be positive")
        if type(policy_enabled) is not bool:
            raise TypeError("policy_enabled must be bool")
        from sofia.platform.ops.activity import HostActivityStore
        from sofia.platform.safe.operator_stop import OperatorStopStore
        self._guard = CanonicalSQLiteGuard(state_path)
        self.activity = HostActivityStore(state_path)
        self.operator_stop = OperatorStopStore(state_path)
        self.telemetry = telemetry
        self.maximum_age = maximum_age
        self.policy_enabled = policy_enabled

    def _active_conflict(self, host_id: str, resource_id: str, now: datetime) -> bool:
        with closing(self._guard.connect(timeout=10)) as db:
            work = db.execute(
                "SELECT 1 FROM autonomous_work_job WHERE kind!='platform.benchmark' "
                "AND status IN ('queued','running','blocked') LIMIT 1"
            ).fetchone()
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='platform_resource_reservation'"
            ).fetchone()
            lease = None
            if table is not None:
                lease = db.execute(
                    "SELECT 1 FROM platform_resource_reservation "
                    "WHERE status='active' AND expires_at>? "
                    "AND (resource_id=? OR resource_id LIKE ?) LIMIT 1",
                    (now.isoformat(), resource_id, f"%{host_id}%"),
                ).fetchone()
        return work is not None or lease is not None

    def __call__(
        self, host_id: str, resource_id: str, kind: BenchmarkKind, now: datetime,
    ) -> IdleAdmission:
        moment = now.astimezone(timezone.utc)
        reasons: list[str] = []
        evidence: list[str] = []
        if not self.policy_enabled:
            reasons.append("local_policy_disabled")
        if self.operator_stop.current().active:
            reasons.append("operator_stop")
        state = self.activity.state(host_id)
        if (
            state.effective.value != "idle" or state.observed_at is None
            or moment - state.observed_at.astimezone(timezone.utc) > self.maximum_age
            or state.observed_at.astimezone(timezone.utc) > moment + timedelta(seconds=5)
        ):
            reasons.append("activity_not_verified_idle")
        else:
            evidence.append(f"activity:{host_id}:{state.observed_at.isoformat()}")
        facts = tuple(
            fact for fact in self.telemetry.latest(host_id)
            if fact.verified and fact.fresh(moment, self.maximum_age)
        )

        def values(key: str, *, exact_resource: bool = False):
            return tuple(
                fact for fact in facts if fact.key == key
                and (not exact_resource or fact.resource_id == resource_id)
            )

        cpu = values("cpu.utilization_percent")
        memory = values("memory.allocatable_bytes")
        temperature = values("health.temperature_c")
        throttled = values("health.throttled")
        power = values("health.power_limited")
        if not cpu or float(cpu[0].value) > 20.0:
            reasons.append("cpu_headroom_unverified")
        if not memory or int(memory[0].value) < 256 * 1024 * 1024:
            reasons.append("memory_headroom_unverified")
        if not temperature or float(temperature[0].value) > 85.0:
            reasons.append("thermal_headroom_unverified")
        if not throttled or throttled[0].value is not False:
            reasons.append("throttle_state_unverified")
        if not power or power[0].value is not False:
            reasons.append("power_headroom_unverified")
        if kind is BenchmarkKind.GPU:
            gpu = values("gpu.utilization_percent", exact_resource=True)
            vram = values("gpu.vram.allocatable_bytes", exact_resource=True)
            if not gpu or float(gpu[0].value) > 10.0:
                reasons.append("gpu_headroom_unverified")
            if not vram or int(vram[0].value) < 256 * 1024 * 1024:
                reasons.append("vram_headroom_unverified")
        if self._active_conflict(host_id, resource_id, moment):
            reasons.append("workload_or_lease_conflict")
        evidence.extend(fact.source_ref for fact in facts)
        return IdleAdmission(
            not reasons, tuple(dict.fromkeys(reasons)),
            tuple(dict.fromkeys(evidence)), moment,
        )


class BenchmarkCoordinator:
    """Queue resumable non-effectful benchmarks through the existing RUN owner."""

    WORK_KIND = "platform.benchmark"
    SUITE_VERSION = "hnf-benchmark-v1"

    def __init__(
        self, *, state_path: Path, inventory: HardwareInventoryStore,
        work_store: DurableWorkStore, manager: TaskExecutionManager,
        idle_observer: IdleObserver, source_revision: str,
        scratch_root: Path | None = None,
        result_freshness: timedelta = timedelta(days=30),
        max_attempts: int = 3,
    ) -> None:
        if not isinstance(state_path, Path) or not isinstance(inventory, HardwareInventoryStore):
            raise TypeError("state_path and inventory required")
        if not isinstance(work_store, DurableWorkStore) or not isinstance(manager, TaskExecutionManager):
            raise TypeError("canonical RUN store/manager required")
        if not callable(idle_observer):
            raise TypeError("idle_observer required")
        if not isinstance(source_revision, str) or _GIT_REVISION.fullmatch(source_revision) is None:
            raise ValueError("exact source revision required")
        if (
            not isinstance(result_freshness, timedelta)
            or not timedelta(minutes=1) <= result_freshness <= timedelta(days=365)
        ):
            raise ValueError("result_freshness must be in 1 minute..365 days")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be in 1..10")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.inventory, self.work_store, self.manager = inventory, work_store, manager
        self.idle_observer, self.source_revision = idle_observer, source_revision
        self.result_freshness = result_freshness
        self.max_attempts = max_attempts
        self.scratch_root = (scratch_root or state_path.parent / "benchmark-scratch").absolute()
        if self.scratch_root.is_symlink():
            raise RuntimeError("benchmark scratch root cannot be redirected")
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self._runners: dict[BenchmarkKind, BenchmarkRunner] = {
            BenchmarkKind.CPU_SINGLE: self._cpu_single,
            BenchmarkKind.CPU_MULTI: self._cpu_multi,
            BenchmarkKind.MEMORY: self._memory,
            BenchmarkKind.STORAGE: self._storage,
        }
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS platform_benchmark_plan(
                    benchmark_id TEXT PRIMARY KEY,host_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL,kind TEXT NOT NULL,
                    suite_version TEXT NOT NULL,source_revision TEXT NOT NULL,
                    inventory_revision INTEGER NOT NULL,status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,next_eligible_at TEXT NOT NULL,
                    job_id TEXT,last_reason TEXT NOT NULL,created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(host_id,resource_id,kind,suite_version,inventory_revision));
                CREATE TABLE IF NOT EXISTS platform_benchmark_result(
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benchmark_id TEXT NOT NULL,attempt INTEGER NOT NULL,
                    host_id TEXT NOT NULL,resource_id TEXT NOT NULL,kind TEXT NOT NULL,
                    suite_version TEXT NOT NULL,source_revision TEXT NOT NULL,
                    inventory_revision INTEGER NOT NULL,started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,duration_ms INTEGER NOT NULL,
                    status TEXT NOT NULL,measurements_json TEXT NOT NULL,
                    configuration_json TEXT NOT NULL,resource_usage_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,model_id TEXT,model_digest TEXT,
                    failure_reason TEXT,fresh_until TEXT NOT NULL,
                    UNIQUE(benchmark_id,attempt));
            """)
        manager.register_handler(self.WORK_KIND, self._execute)
        self.reconcile(now=datetime.now(timezone.utc))

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def register_runner(self, kind: BenchmarkKind, runner: BenchmarkRunner) -> None:
        if not isinstance(kind, BenchmarkKind) or not callable(runner):
            raise TypeError("reviewed benchmark kind and runner required")
        if kind in self._runners:
            raise ValueError("benchmark runner already registered")
        self._runners[kind] = runner

    @staticmethod
    def _supported(record: InventoryRecord) -> tuple[tuple[BenchmarkKind, str], ...]:
        keys = {fact.key for fact in record.facts}
        result = [(BenchmarkKind.CPU_SINGLE, f"host:{record.host_id}"),
                  (BenchmarkKind.CPU_MULTI, f"host:{record.host_id}")]
        if any(key.startswith("memory.") for key in keys):
            result.append((BenchmarkKind.MEMORY, f"host:{record.host_id}"))
        for fact in record.facts:
            if fact.key.startswith("gpu."):
                pair = (BenchmarkKind.GPU, fact.resource_id)
                if pair not in result:
                    result.append(pair)
        for fact in record.facts:
            if fact.key.startswith("storage."):
                pair = (BenchmarkKind.STORAGE, fact.resource_id)
                if pair not in result:
                    result.append(pair)
        return tuple(result)

    def queue_inventory(self, record: InventoryRecord, *, now: datetime) -> int:
        if not record.enrolled or not record.trusted:
            return 0
        moment = now.astimezone(timezone.utc)
        created = 0
        with closing(self._connect()) as db, db:
            for kind, resource_id in self._supported(record):
                if kind not in self._runners:
                    continue
                identity = json.dumps({
                    "host": record.host_id, "resource": resource_id,
                    "kind": kind.value, "suite": self.SUITE_VERSION,
                    "inventory_revision": record.revision,
                }, sort_keys=True, separators=(",", ":"))
                benchmark_id = "benchmark:" + sha256(identity.encode()).hexdigest()
                changed = db.execute("""INSERT OR IGNORE INTO platform_benchmark_plan
                    VALUES(?,?,?,?,?,?,?,'pending',0,?,NULL,'inventory_eligible',?,?)""", (
                    benchmark_id, record.host_id, resource_id, kind.value,
                    self.SUITE_VERSION, self.source_revision, record.revision,
                    moment.isoformat(), moment.isoformat(), moment.isoformat(),
                ))
                created += int(changed.rowcount == 1)
        return created

    def reconcile(self, *, now: datetime) -> int:
        """Repair plan projections from canonical RUN without replaying a job.

        Benchmarks are bounded, scratch-only observations, so a later *new*
        attempt may be admitted after an interrupted process.  The uncertain
        RUN receipt remains immutable and the old fingerprint is never reused.
        """
        moment = now.astimezone(timezone.utc)
        repaired = 0
        with closing(self._connect()) as db, db:
            rows = db.execute(
                "SELECT benchmark_id,attempt,job_id FROM platform_benchmark_plan "
                "WHERE status='queued' AND job_id IS NOT NULL"
            ).fetchall()
            for row in rows:
                try:
                    job = self.work_store.get(row["job_id"])
                except LookupError:
                    status, reason = "pending", "run_receipt_missing"
                else:
                    if job.status in {WorkStatus.QUEUED, WorkStatus.RUNNING}:
                        continue
                    if job.status is WorkStatus.COMPLETED:
                        result = db.execute(
                            "SELECT 1 FROM platform_benchmark_result "
                            "WHERE benchmark_id=? AND attempt=? AND status='completed'",
                            (row["benchmark_id"], row["attempt"]),
                        ).fetchone()
                        status = "completed" if result is not None else "failed"
                        reason = (
                            "reconciled_verified_result" if result is not None
                            else "run_completed_without_benchmark_evidence"
                        )
                    elif int(row["attempt"]) >= self.max_attempts:
                        status, reason = "failed", f"run_{job.status.value}:attempt_limit"
                    else:
                        status, reason = "pending", f"run_{job.status.value}:new_attempt_required"
                db.execute(
                    "UPDATE platform_benchmark_plan SET status=?,job_id=NULL," 
                    "next_eligible_at=?,last_reason=?,updated_at=? "
                    "WHERE benchmark_id=? AND status='queued' AND job_id=?",
                    (
                        status,
                        (moment + timedelta(minutes=5)).isoformat(),
                        reason,
                        moment.isoformat(),
                        row["benchmark_id"], row["job_id"],
                    ),
                )
                repaired += 1
        return repaired

    def expire_stale_results(self, *, now: datetime) -> int:
        """Make completed plans eligible for a bounded, distinct retest."""
        moment = now.astimezone(timezone.utc)
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE platform_benchmark_plan AS plan
                SET status='pending',next_eligible_at=?,last_reason='result_stale',updated_at=?
                WHERE status='completed' AND EXISTS(
                    SELECT 1 FROM platform_benchmark_result AS result
                    WHERE result.benchmark_id=plan.benchmark_id
                      AND result.attempt=plan.attempt
                      AND result.fresh_until<=?
                )""",
                (moment.isoformat(), moment.isoformat(), moment.isoformat()),
            )
        return int(changed.rowcount)

    def schedule(self, *, now: datetime, limit: int = 4) -> int:
        moment = now.astimezone(timezone.utc)
        self.reconcile(now=moment)
        self.expire_stale_results(now=moment)
        for record in self.inventory.current_records():
            self.queue_inventory(record, now=moment)
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT * FROM platform_benchmark_plan
                WHERE status='pending' AND next_eligible_at<=?
                ORDER BY created_at,benchmark_id LIMIT ?""", (moment.isoformat(), limit)).fetchall()
        scheduled = 0
        for row in rows:
            kind = BenchmarkKind(row["kind"])
            admission = self.idle_observer(
                row["host_id"], row["resource_id"], kind, moment,
            )
            if not isinstance(admission, IdleAdmission):
                raise TypeError("idle observer returned invalid admission")
            if not admission.eligible:
                with closing(self._connect()) as db, db:
                    db.execute("""UPDATE platform_benchmark_plan
                        SET next_eligible_at=?,last_reason=?,updated_at=?
                        WHERE benchmark_id=? AND status='pending'""", (
                        (moment + timedelta(minutes=5)).isoformat(),
                        ";".join(admission.reasons) or "idle_unverified",
                        moment.isoformat(), row["benchmark_id"],
                    ))
                continue
            attempt = int(row["attempt"]) + 1
            payload = {
                "benchmark_id": row["benchmark_id"], "attempt": attempt,
                "host_id": row["host_id"], "resource_id": row["resource_id"],
                "kind": kind.value, "inventory_revision": int(row["inventory_revision"]),
                "source_revision": row["source_revision"],
                "idle_evidence_refs": list(admission.evidence_refs),
            }
            def link_plan(db: sqlite3.Connection, job: WorkJob) -> None:
                changed = db.execute("""UPDATE platform_benchmark_plan
                    SET status='queued',attempt=?,job_id=?,last_reason='run_queued',updated_at=?
                    WHERE benchmark_id=? AND status='pending' AND attempt=?""", (
                    attempt, job.job_id, moment.isoformat(), row["benchmark_id"], attempt - 1,
                ))
                if changed.rowcount != 1:
                    raise RuntimeError("benchmark plan changed during RUN admission")

            job = self.manager.submit(
                kind=self.WORK_KIND,
                fingerprint=f"{row['benchmark_id']}:{attempt}", payload=payload,
                priority=10, resource_cost=20, risk="read_only",
                completion_condition="persist bounded measured benchmark result",
                now=moment, deadline=moment + timedelta(minutes=10),
                after_enqueue=link_plan,
            )
            scheduled += 1
        return scheduled

    def _execute(self, job: WorkJob, cancel) -> WorkResult:
        payload = job.payload
        kind = BenchmarkKind(str(payload["kind"]))
        now = datetime.now(timezone.utc)
        admission = self.idle_observer(
            str(payload["host_id"]), str(payload["resource_id"]), kind, now,
        )
        if not admission.eligible:
            self._record_failure(
                payload, kind=kind, started_at=now, now=now,
                exc=InterruptedError("preempted_before_start"), status="cancelled",
            )
            self._finish_plan(payload, status="pending", reason="preempted:" + ";".join(admission.reasons), now=now)
            return WorkResult(WorkStatus.FAILED, {"preempted": True}, "benchmark_preempted_before_start")
        if cancel.is_set():
            self._record_failure(
                payload, kind=kind, started_at=now, now=now,
                exc=InterruptedError("cancelled_before_start"), status="cancelled",
            )
            self._finish_plan(payload, status="pending", reason="cancelled_before_start", now=now)
            return WorkResult(WorkStatus.FAILED, {"cancelled": True}, "benchmark_cancelled")
        runner = self._runners.get(kind)
        if runner is None:
            self._record_failure(
                payload, kind=kind, started_at=now, now=now,
                exc=RuntimeError("runner_unavailable"), status="failed",
            )
            self._finish_plan(payload, status="pending", reason="runner_unavailable", now=now)
            return WorkResult(WorkStatus.FAILED, {}, "benchmark_runner_unavailable")
        started = perf_counter()
        started_at = now
        try:
            execution = runner(job, cancel)
            if not isinstance(execution, BenchmarkExecution):
                raise TypeError("benchmark runner returned invalid execution")
            if cancel.is_set():
                raise InterruptedError("benchmark cancelled")
            completed = datetime.now(timezone.utc)
            duration_ms = max(0, int((perf_counter() - started) * 1000))
            with closing(self._connect()) as db, db:
                db.execute("""INSERT INTO platform_benchmark_result VALUES(
                    NULL,?,?,?,?,?,?,?,?,?,?,?,'completed',?,?,?,?,?,?,NULL,?)""", (
                    payload["benchmark_id"], payload["attempt"], payload["host_id"],
                    payload["resource_id"], kind.value, self.SUITE_VERSION,
                    payload["source_revision"], payload["inventory_revision"],
                    started_at.isoformat(), completed.isoformat(), duration_ms,
                    json.dumps([{"name": item.name, "value": item.value, "unit": item.unit,
                                 "sample_count": item.sample_count, "variance": item.variance}
                                for item in execution.measurements], sort_keys=True),
                    json.dumps(execution.configuration, sort_keys=True),
                    json.dumps({
                        **execution.resource_usage,
                        "environmental_conditions": execution.environmental_conditions or {},
                    }, sort_keys=True),
                    json.dumps(tuple(payload.get("idle_evidence_refs", ())) + execution.evidence_refs),
                    execution.model_id, execution.model_digest,
                    (completed + self.result_freshness).isoformat(),
                ))
            self._finish_plan(payload, status="completed", reason="measured_result_persisted", now=completed)
            return WorkResult(WorkStatus.COMPLETED, {
                "benchmark_id": payload["benchmark_id"],
                "measurements": [item.name for item in execution.measurements],
                "duration_ms": duration_ms,
            }, "benchmark_measured_and_persisted")
        except InterruptedError:
            cancelled = datetime.now(timezone.utc)
            self._record_failure(
                payload, kind=kind, started_at=started_at, now=cancelled,
                exc=InterruptedError("cancelled_yielded"), status="cancelled",
            )
            self._finish_plan(payload, status="pending", reason="cancelled_yielded", now=cancelled)
            return WorkResult(WorkStatus.FAILED, {"cancelled": True}, "benchmark_cancelled_safely")
        except Exception as exc:
            failed = datetime.now(timezone.utc)
            terminal = int(payload["attempt"]) >= self.max_attempts
            self._record_failure(
                payload, kind=kind, started_at=started_at, now=failed,
                exc=exc, status="failed",
            )
            self._finish_plan(
                payload, status="failed" if terminal else "pending",
                reason=f"runner_failed:{type(exc).__name__}", now=failed,
            )
            return WorkResult(
                WorkStatus.FAILED, {"error_type": type(exc).__name__},
                "benchmark_runner_failed",
            )

    def _record_failure(
        self, payload: dict[str, object], *, kind: BenchmarkKind,
        started_at: datetime, now: datetime, exc: Exception, status: str,
    ) -> None:
        if status not in {"failed", "cancelled"}:
            raise ValueError("invalid benchmark failure status")
        with closing(self._connect()) as db, db:
            db.execute("""INSERT OR IGNORE INTO platform_benchmark_result VALUES(
                NULL,?,?,?,?,?,?,?,?,?,?,?,?, '[]','{}','{}',?,NULL,NULL,?,?)""", (
                payload["benchmark_id"], payload["attempt"], payload["host_id"],
                payload["resource_id"], kind.value, self.SUITE_VERSION,
                payload["source_revision"], payload["inventory_revision"],
                started_at.isoformat(), now.isoformat(),
                max(0, int((now - started_at).total_seconds() * 1000)),
                status,
                json.dumps(tuple(payload.get("idle_evidence_refs", ()))),
                type(exc).__name__, now.isoformat(),
            ))

    def _finish_plan(self, payload, *, status: str, reason: str, now: datetime) -> None:
        next_at = now if status == "completed" else now + timedelta(minutes=5)
        with closing(self._connect()) as db, db:
            db.execute("""UPDATE platform_benchmark_plan SET status=?,job_id=NULL,
                next_eligible_at=?,last_reason=?,updated_at=? WHERE benchmark_id=?""", (
                status, next_at.isoformat(), reason, now.isoformat(), payload["benchmark_id"],
            ))

    def plans(self) -> tuple[dict[str, object], ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM platform_benchmark_plan ORDER BY created_at,benchmark_id"
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def results(self, *, host_id: str | None = None) -> tuple[dict[str, object], ...]:
        query = "SELECT * FROM platform_benchmark_result"
        parameters: tuple[object, ...] = ()
        if host_id is not None:
            query += " WHERE host_id=?"
            parameters = (host_id,)
        query += " ORDER BY completed_at DESC,result_id DESC"
        with closing(self._connect()) as db:
            rows = db.execute(query, parameters).fetchall()
        return tuple(dict(row) for row in rows)

    @staticmethod
    def _cpu_single(job: WorkJob, cancel) -> BenchmarkExecution:
        started = perf_counter(); value = 0
        iterations = 200_000
        for index in range(iterations):
            if index % 20_000 == 0 and cancel.is_set():
                raise InterruptedError
            value = ((value * 33) ^ index) & 0xFFFFFFFF
        elapsed = max(perf_counter() - started, 1e-9)
        return BenchmarkExecution(
            (BenchmarkMeasurement("integer_iterations_per_second", iterations / elapsed, "iterations_per_second"),),
            {"iterations": iterations, "algorithm": "bounded-integer-v1"},
            {"checksum": value},
        )

    @staticmethod
    def _cpu_multi(job: WorkJob, cancel) -> BenchmarkExecution:
        workers = min(4, max(1, os.cpu_count() or 1))
        block = b"sofia-hnf-multicore-v1" * 32_768
        rounds = 24

        def hash_batch(_: int) -> bytes:
            digest = b""
            for _index in range(rounds):
                if cancel.is_set():
                    raise InterruptedError
                digest = sha256(block + digest).digest()
            return digest

        started = perf_counter()
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sofia-bench-cpu") as pool:
            digests = tuple(pool.map(hash_batch, range(workers)))
        elapsed = max(perf_counter() - started, 1e-9)
        processed = len(block) * rounds * workers
        return BenchmarkExecution(
            (
                BenchmarkMeasurement("multicore_hash_bytes_per_second", processed / elapsed, "bytes_per_second"),
                BenchmarkMeasurement("logical_cpu_count", os.cpu_count() or 1, "count"),
            ),
            {"algorithm": "sha256-threaded-v1", "workers": workers, "rounds": rounds,
             "bytes_per_round": len(block)},
            {"digest_prefixes": [item.hex()[:8] for item in digests]},
        )

    @staticmethod
    def _memory(job: WorkJob, cancel) -> BenchmarkExecution:
        size = 8 * 1024 * 1024; source = bytes((index % 251 for index in range(size)))
        started = perf_counter(); target = bytearray(size)
        for offset in range(0, size, 1024 * 1024):
            if cancel.is_set():
                raise InterruptedError
            target[offset:offset + 1024 * 1024] = source[offset:offset + 1024 * 1024]
        elapsed = max(perf_counter() - started, 1e-9)
        indices = tuple((index * 7919) % 65_521 for index in range(20_000))
        probe = list(range(65_521)); checksum = 0
        latency_started = perf_counter()
        for offset, index in enumerate(indices):
            if offset % 2_000 == 0 and cancel.is_set():
                raise InterruptedError
            checksum ^= probe[index]
        latency_ns = (perf_counter() - latency_started) * 1_000_000_000 / len(indices)
        return BenchmarkExecution(
            (
                BenchmarkMeasurement("memory_copy_bytes_per_second", size / elapsed, "bytes_per_second"),
                BenchmarkMeasurement("memory_index_access_latency_ns", latency_ns, "nanoseconds", len(indices)),
            ),
            {"bytes": size, "chunk_bytes": 1024 * 1024,
             "latency_samples": len(indices), "runtime": "python"},
            {"copy_checksum": target[-1], "latency_checksum": checksum},
        )

    def _storage(self, job: WorkJob, cancel) -> BenchmarkExecution:
        size = 4 * 1024 * 1024; payload = b"\xA5" * (1024 * 1024)
        started = perf_counter()
        with tempfile.TemporaryDirectory(prefix="sofia-benchmark-", dir=self.scratch_root) as folder:
            target = Path(folder) / "bounded.bin"
            with target.open("wb") as stream:
                for _ in range(4):
                    if cancel.is_set():
                        raise InterruptedError
                    stream.write(payload)
                stream.flush(); os.fsync(stream.fileno())
            write_elapsed = max(perf_counter() - started, 1e-9)
            if target.stat().st_size != size:
                raise RuntimeError("benchmark scratch verification failed")
            read_started = perf_counter()
            with target.open("rb") as stream:
                while stream.read(1024 * 1024):
                    if cancel.is_set():
                        raise InterruptedError
            read_elapsed = max(perf_counter() - read_started, 1e-9)
            random_started = perf_counter(); operations = 64
            with target.open("r+b", buffering=0) as stream:
                for index in range(operations):
                    if cancel.is_set():
                        raise InterruptedError
                    stream.seek((index * 65_537) % (size - 4096))
                    stream.write(payload[:4096])
                os.fsync(stream.fileno())
            random_elapsed = max(perf_counter() - random_started, 1e-9)
        return BenchmarkExecution(
            (
                BenchmarkMeasurement("sequential_write_bytes_per_second", size / write_elapsed, "bytes_per_second"),
                BenchmarkMeasurement("sequential_read_bytes_per_second", size / read_elapsed, "bytes_per_second"),
                BenchmarkMeasurement("random_write_operations_per_second", operations / random_elapsed, "operations_per_second", operations),
                BenchmarkMeasurement("random_write_latency_ms", random_elapsed * 1000 / operations, "milliseconds", operations),
            ),
            {"bytes": size, "scratch_only": True, "fsync": True,
             "random_block_bytes": 4096, "random_operations": operations},
            {"temporary_cleanup_verified": True, "python": platform.python_version()},
        )
