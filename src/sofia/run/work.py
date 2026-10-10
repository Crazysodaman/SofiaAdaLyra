"""Durable, bounded execution for non-authoritative background work."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import re
import sqlite3
from threading import Event, Lock
from typing import Callable
from uuid import uuid4


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class WorkStatus(str, Enum):
    QUEUED = "queued"
    BLOCKED = "blocked"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN = "uncertain"


TERMINAL_WORK_STATUSES = frozenset({
    WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.CANCELLED,
    WorkStatus.UNCERTAIN,
})


@dataclass(frozen=True, slots=True)
class WorkJob:
    job_id: str
    kind: str
    fingerprint: str
    payload: dict[str, object]
    priority: int
    resource_cost: int
    risk: str
    completion_condition: str
    status: WorkStatus
    created_at: datetime
    updated_at: datetime
    deadline: datetime
    attempt_count: int
    result: dict[str, object] | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class WorkResult:
    status: WorkStatus
    result: dict[str, object]
    reason: str

    def __post_init__(self) -> None:
        if self.status not in {
            WorkStatus.COMPLETED, WorkStatus.WAITING_APPROVAL,
            WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.UNCERTAIN,
        }:
            raise ValueError("handler returned an invalid work status")


class WorkOverloadError(RuntimeError):
    pass


class DurableWorkStore:
    """Canonical job lifecycle. Workers may report outcomes, not mutate owners."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("existing application state database required")
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS autonomous_work_job (
                    job_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    priority INTEGER NOT NULL CHECK(priority BETWEEN 0 AND 100),
                    resource_cost INTEGER NOT NULL CHECK(resource_cost BETWEEN 1 AND 100),
                    risk TEXT NOT NULL CHECK(risk IN ('read_only','isolated_change','protected')),
                    completion_condition TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    reason TEXT
                );
                CREATE INDEX IF NOT EXISTS autonomous_work_ready
                    ON autonomous_work_job(status,priority DESC,created_at);
                CREATE TABLE IF NOT EXISTS autonomous_work_event (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS autonomous_work_event_recent
                    ON autonomous_work_event(occurred_at DESC,event_id DESC);
                CREATE TABLE IF NOT EXISTS autonomous_work_plan (
                    plan_id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS autonomous_work_plan_step (
                    plan_id TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE,
                    step_order INTEGER NOT NULL CHECK(step_order >= 0),
                    depends_on_job_id TEXT,
                    PRIMARY KEY(plan_id,step_order)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _validate_id(value: str, label: str) -> str:
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            raise ValueError(f"{label} must be a bounded identifier")
        return value

    @staticmethod
    def _job(row: sqlite3.Row) -> WorkJob:
        return WorkJob(
            job_id=row["job_id"], kind=row["kind"], fingerprint=row["fingerprint"],
            payload=json.loads(row["payload_json"]), priority=int(row["priority"]),
            resource_cost=int(row["resource_cost"]), risk=row["risk"],
            completion_condition=row["completion_condition"], status=WorkStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            deadline=datetime.fromisoformat(row["deadline"]),
            attempt_count=int(row["attempt_count"]),
            result=None if row["result_json"] is None else json.loads(row["result_json"]),
            reason=row["reason"],
        )

    @staticmethod
    def _event(db, job_id, old, new, reason, now) -> None:
        db.execute(
            "INSERT INTO autonomous_work_event(job_id,from_status,to_status,reason,occurred_at) VALUES(?,?,?,?,?)",
            (job_id, None if old is None else old.value, new.value, reason, _utc(now).isoformat()),
        )

    def enqueue(
        self, *, kind: str, fingerprint: str, payload: dict[str, object],
        priority: int, resource_cost: int, risk: str,
        completion_condition: str, now: datetime, deadline: datetime,
    ) -> WorkJob:
        self._validate_id(kind, "kind")
        self._validate_id(fingerprint, "fingerprint")
        if type(priority) is not int or not 0 <= priority <= 100:
            raise ValueError("priority must be in 0..100")
        if type(resource_cost) is not int or not 1 <= resource_cost <= 100:
            raise ValueError("resource_cost must be in 1..100")
        if risk not in {"read_only", "isolated_change", "protected"}:
            raise ValueError("unsupported work risk")
        if not isinstance(completion_condition, str) or not completion_condition.strip():
            raise ValueError("meaningful completion_condition required")
        moment, due = _utc(now), _utc(deadline)
        if due <= moment:
            raise ValueError("deadline must be in the future")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 64_000:
            raise ValueError("work payload is too large")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM autonomous_work_job WHERE fingerprint=?", (fingerprint,)).fetchone()
            if old is not None:
                return self._job(old)
            job_id = f"work:{uuid4()}"
            db.execute(
                """INSERT INTO autonomous_work_job
                (job_id,kind,fingerprint,payload_json,priority,resource_cost,risk,
                 completion_condition,status,created_at,updated_at,deadline,
                 attempt_count,result_json,reason)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, kind, fingerprint, encoded, priority, resource_cost, risk,
                 completion_condition.strip(), WorkStatus.QUEUED.value, moment.isoformat(),
                 moment.isoformat(), due.isoformat(), 0, None, "accepted"),
            )
            self._event(db, job_id, None, WorkStatus.QUEUED, "accepted", moment)
            row = db.execute("SELECT * FROM autonomous_work_job WHERE job_id=?", (job_id,)).fetchone()
        return self._job(row)

    def get(self, job_id: str) -> WorkJob:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM autonomous_work_job WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise LookupError("work job does not exist")
        return self._job(row)

    def list(self, *, limit: int = 100) -> tuple[WorkJob, ...]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be in 1..500")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM autonomous_work_job ORDER BY created_at DESC,job_id LIMIT ?", (limit,)
            ).fetchall()
        return tuple(self._job(row) for row in rows)

    def open_count(self) -> int:
        with closing(self._connect()) as db:
            return int(db.execute(
                "SELECT COUNT(*) FROM autonomous_work_job WHERE status IN ('queued','running','blocked')"
            ).fetchone()[0])

    def create_plan(
        self, *, fingerprint: str, title: str, evidence_ref: str,
        now: datetime,
    ) -> str:
        self._validate_id(fingerprint, "plan fingerprint")
        if not title.strip() or not evidence_ref.strip():
            raise ValueError("plan title and evidence_ref required")
        moment = _utc(now).isoformat()
        plan_id = "plan:" + fingerprint
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO autonomous_work_plan VALUES(?,?,?,?,?,?,?)",
                (plan_id, fingerprint, title.strip(), evidence_ref.strip(),
                 WorkStatus.QUEUED.value, moment, moment),
            )
            row = db.execute(
                "SELECT plan_id,title,evidence_ref FROM autonomous_work_plan WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
            if row[1] != title.strip() or row[2] != evidence_ref.strip():
                raise ValueError("plan fingerprint reused for different work")
        return row[0]

    def attach_step(
        self, *, plan_id: str, job_id: str, step_order: int,
        depends_on_job_id: str | None = None,
    ) -> None:
        if type(step_order) is not int or step_order < 0:
            raise ValueError("step_order must be nonnegative")
        with closing(self._connect()) as db, db:
            if db.execute("SELECT 1 FROM autonomous_work_plan WHERE plan_id=?", (plan_id,)).fetchone() is None:
                raise LookupError("work plan does not exist")
            if db.execute("SELECT 1 FROM autonomous_work_job WHERE job_id=?", (job_id,)).fetchone() is None:
                raise LookupError("work job does not exist")
            if depends_on_job_id is not None and db.execute(
                "SELECT 1 FROM autonomous_work_job WHERE job_id=?", (depends_on_job_id,)
            ).fetchone() is None:
                raise LookupError("dependency job does not exist")
            db.execute(
                "INSERT OR IGNORE INTO autonomous_work_plan_step VALUES(?,?,?,?)",
                (plan_id, job_id, step_order, depends_on_job_id),
            )

    def ready(self, *, limit: int) -> tuple[WorkJob, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT job.* FROM autonomous_work_job AS job
                LEFT JOIN autonomous_work_plan_step AS step ON step.job_id=job.job_id
                LEFT JOIN autonomous_work_job AS dependency
                  ON dependency.job_id=step.depends_on_job_id
                WHERE job.status='queued'
                  AND (step.depends_on_job_id IS NULL OR dependency.status='completed')
                ORDER BY job.priority DESC,job.created_at,job.job_id LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._job(row) for row in rows)

    def transition(
        self, job_id: str, *, expected: tuple[WorkStatus, ...], status: WorkStatus,
        reason: str, now: datetime, result: dict[str, object] | None = None,
        increment_attempt: bool = False,
    ) -> WorkJob:
        if not expected:
            raise ValueError("expected statuses required")
        moment = _utc(now)
        result_json = None if result is None else json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM autonomous_work_job WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise LookupError("work job does not exist")
            old = WorkStatus(row["status"])
            if old not in expected:
                raise RuntimeError(f"work transition expected {[s.value for s in expected]}, found {old.value}")
            db.execute(
                "UPDATE autonomous_work_job SET status=?,updated_at=?,result_json=?,reason=?,attempt_count=attempt_count+? WHERE job_id=?",
                (status.value, moment.isoformat(), result_json, reason, int(increment_attempt), job_id),
            )
            self._event(db, job_id, old, status, reason, moment)
            plan = db.execute(
                "SELECT plan_id FROM autonomous_work_plan_step WHERE job_id=?", (job_id,)
            ).fetchone()
            if plan is not None:
                statuses = [item[0] for item in db.execute(
                    """SELECT job.status FROM autonomous_work_plan_step AS step
                    JOIN autonomous_work_job AS job ON job.job_id=step.job_id
                    WHERE step.plan_id=? ORDER BY step.step_order""", (plan[0],)
                ).fetchall()]
                if statuses and all(item == WorkStatus.COMPLETED.value for item in statuses):
                    plan_status = WorkStatus.COMPLETED.value
                elif any(item in {WorkStatus.FAILED.value, WorkStatus.UNCERTAIN.value} for item in statuses):
                    plan_status = WorkStatus.FAILED.value
                elif any(item == WorkStatus.WAITING_APPROVAL.value for item in statuses):
                    plan_status = WorkStatus.WAITING_APPROVAL.value
                elif any(item == WorkStatus.RUNNING.value for item in statuses):
                    plan_status = WorkStatus.RUNNING.value
                else:
                    plan_status = WorkStatus.QUEUED.value
                db.execute(
                    "UPDATE autonomous_work_plan SET status=?,updated_at=? WHERE plan_id=?",
                    (plan_status, moment.isoformat(), plan[0]),
                )
            updated = db.execute("SELECT * FROM autonomous_work_job WHERE job_id=?", (job_id,)).fetchone()
        return self._job(updated)

    def recover(self, *, now: datetime) -> int:
        moment = _utc(now)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT job_id FROM autonomous_work_job WHERE status='running'").fetchall()
            for row in rows:
                db.execute(
                    "UPDATE autonomous_work_job SET status='uncertain',updated_at=?,reason='process_restarted_during_execution' WHERE job_id=?",
                    (moment.isoformat(), row[0]),
                )
                self._event(db, row[0], WorkStatus.RUNNING, WorkStatus.UNCERTAIN,
                            "process_restarted_during_execution", moment)
            if rows:
                db.execute(
                    """UPDATE autonomous_work_plan
                    SET status='failed',updated_at=?
                    WHERE plan_id IN (
                        SELECT DISTINCT step.plan_id
                        FROM autonomous_work_plan_step AS step
                        JOIN autonomous_work_job AS job ON job.job_id=step.job_id
                        WHERE job.status='uncertain'
                    )""",
                    (moment.isoformat(),),
                )
        return len(rows)


WorkHandler = Callable[[WorkJob, Event], WorkResult]


class TaskExecutionManager:
    """Bounded concurrent executor; canonical state stays in owning services."""

    def __init__(
        self, store: DurableWorkStore, handlers: dict[str, WorkHandler], *,
        max_workers: int = 2, max_queued: int = 32,
    ) -> None:
        if type(max_workers) is not int or not 1 <= max_workers <= 8:
            raise ValueError("max_workers must be in 1..8")
        if type(max_queued) is not int or not max_workers <= max_queued <= 256:
            raise ValueError("max_queued must be bounded")
        self.store, self.handlers = store, dict(handlers)
        self.max_workers, self.max_queued = max_workers, max_queued
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sofia-work")
        self._active: dict[str, tuple[Future, Event]] = {}
        self._lock = Lock()

    def submit(self, **kwargs) -> WorkJob:
        open_count = self.store.open_count()
        if open_count >= self.max_queued:
            raise WorkOverloadError("autonomous work queue is full")
        if kwargs.get("kind") not in self.handlers:
            raise ValueError("no reviewed handler for work kind")
        return self.store.enqueue(**kwargs)

    def _run(self, job: WorkJob, cancel: Event) -> WorkResult:
        if cancel.is_set():
            return WorkResult(WorkStatus.FAILED, {}, "cancelled_before_start")
        return self.handlers[job.kind](job, cancel)

    def _finish(self, job_id: str, future: Future) -> None:
        finished_at = datetime.now(timezone.utc)
        try:
            result = future.result()
            if not isinstance(result, WorkResult):
                raise TypeError("work handler must return WorkResult")
        except Exception as exc:
            result = WorkResult(WorkStatus.FAILED, {"error_type": type(exc).__name__}, type(exc).__name__)
        try:
            job = self.store.get(job_id)
            measured = dict(result.result)
            measured["execution"] = {
                "duration_ms": max(
                    0, int((finished_at - job.updated_at).total_seconds() * 1000)
                ),
                "resource_cost_admission": job.resource_cost,
            }
            self.store.transition(
                job_id, expected=(WorkStatus.RUNNING,), status=result.status,
                reason=result.reason, result=measured, now=finished_at,
            )
        except RuntimeError:
            pass
        finally:
            with self._lock:
                self._active.pop(job_id, None)

    def tick(self, *, now: datetime, busy: bool = False, resource_pressure: float = 0.0) -> int:
        moment = _utc(now)
        if not 0.0 <= float(resource_pressure) <= 1.0:
            raise ValueError("resource_pressure must be in 0..1")
        self.poll(now=moment)
        if busy or resource_pressure >= 0.85:
            return 0
        with self._lock:
            capacity = self.max_workers - len(self._active)
            active_cost = sum(self.store.get(job_id).resource_cost for job_id in self._active)
        started = 0
        for job in self.store.ready(limit=max(0, capacity)):
            if active_cost + job.resource_cost > 100:
                continue
            if moment >= job.deadline:
                self.store.transition(
                    job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.FAILED,
                    reason="deadline_expired_before_start", now=moment,
                )
                continue
            running = self.store.transition(
                job.job_id, expected=(WorkStatus.QUEUED,), status=WorkStatus.RUNNING,
                reason="worker_claimed", now=moment, increment_attempt=True,
            )
            cancel = Event()
            future = self._pool.submit(self._run, running, cancel)
            with self._lock:
                self._active[job.job_id] = (future, cancel)
            future.add_done_callback(lambda f, key=job.job_id: self._finish(key, f))
            started += 1
            active_cost += job.resource_cost
        return started

    def poll(self, *, now: datetime) -> None:
        moment = _utc(now)
        with self._lock:
            active = tuple(self._active.items())
        for job_id, (future, cancel) in active:
            if future.done():
                continue
            job = self.store.get(job_id)
            if moment >= job.deadline:
                cancel.set()
                future.cancel()
                try:
                    self.store.transition(
                        job_id, expected=(WorkStatus.RUNNING,), status=WorkStatus.UNCERTAIN,
                        reason="deadline_exceeded_worker_cancellation_requested", now=moment,
                    )
                except RuntimeError:
                    pass

    def cancel(self, job_id: str, *, now: datetime) -> WorkJob:
        job = self.store.get(job_id)
        if job.status in TERMINAL_WORK_STATUSES or job.status is WorkStatus.WAITING_APPROVAL:
            return job
        with self._lock:
            active = self._active.get(job_id)
        if active is not None:
            active[1].set()
            active[0].cancel()
        return self.store.transition(
            job_id, expected=(job.status,), status=WorkStatus.CANCELLED,
            reason="operator_cancelled", now=now,
        )

    def close(self, *, wait: bool = False) -> None:
        with self._lock:
            active = tuple(self._active.values())
        for _, cancel in active:
            cancel.set()
        self._pool.shutdown(wait=wait, cancel_futures=True)
