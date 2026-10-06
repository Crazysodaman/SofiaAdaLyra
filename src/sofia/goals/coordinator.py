"""Application-owned closed-loop coordinator for evidence, goals, ACT, and RUN."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.capability.gateway import CapabilityGateway
from sofia.capability.model import CapabilityResultKind
from sofia.neuro.model import NeuralActivation, NeuroStateSnapshot, NeuroWakeMode
from sofia.safe.permissions import PermissionLevel, capability_permission_policy
from sofia.safe.permissions import PermissionStore
from sofia.social.model import PrincipalContext

from .evidence import GoalEvidenceLedger
from .model import (
    CompletionKind, Goal, GoalCompletionCondition, GoalCost, GoalPolicyDecision,
    GoalPriority, GoalRisk, GoalRunState, GoalStatus, SOFIA_GOAL_OWNER_ID,
    TERMINAL_GOAL_STATUSES,
)
from .policy import effective_priority
from .service import GoalService


@dataclass(frozen=True, slots=True)
class ReviewedAnomaly:
    key: str
    title: str
    reason: str
    evidence_ref: str
    activation_kind: str
    risk: GoalRisk = GoalRisk.LOW
    cost: GoalCost = GoalCost.LOW


class GoalRunSchedule:
    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS goal_run_schedule (
                    goal_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    wake_reason TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('scheduled','cancelled','claimed')),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(goal_id,principal_id,audience)
                )
            """)

    def schedule(self, goal: Goal, *, due_at: datetime, reason: str, now: datetime) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""
                INSERT INTO goal_run_schedule(
                    goal_id,principal_id,audience,due_at,wake_reason,status,updated_at
                ) VALUES(?,?,?,?,?,'scheduled',?)
                ON CONFLICT(goal_id,principal_id,audience) DO UPDATE SET
                    due_at=excluded.due_at,wake_reason=excluded.wake_reason,
                    status='scheduled',updated_at=excluded.updated_at
            """, (
                goal.id, goal.scope_principal_id or "", goal.scope_audience or "",
                due_at.isoformat(), reason[:160], now.isoformat(),
            ))

    def due(self, now: datetime, *, limit: int = 16) -> tuple[tuple[str,str|None,str|None], ...]:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            rows = db.execute("""
                SELECT goal_id,principal_id,audience FROM goal_run_schedule
                WHERE status='scheduled' AND due_at<=?
                ORDER BY due_at,goal_id LIMIT ?
            """, (now.isoformat(), limit)).fetchall()
        return tuple((row[0], row[1] or None, row[2] or None) for row in rows)

    def cancel(self, goal: Goal, *, now: datetime) -> None:
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("""
                UPDATE goal_run_schedule SET status='cancelled',updated_at=?
                WHERE goal_id=? AND principal_id=? AND audience=?
            """, (
                now.isoformat(), goal.id, goal.scope_principal_id or "",
                goal.scope_audience or "",
            ))


class GoalActionPlanner:
    """Deterministic initial diagnostics; it creates no permission or receipt."""
    def __init__(self, gateway: CapabilityGateway) -> None:
        self.gateway = gateway

    _SERVICE_RESTART = re.compile(
        r"^restart(?:ing)?\s+(?:the\s+)?([A-Za-z0-9_.-]{1,80})(?:\s+service)?$",
        re.IGNORECASE,
    )

    def plan(self, goal: Goal, *, diagnostic_done: bool = False):
        names = set(self.gateway.capability_system.capability_names())
        text = f"{goal.title} {goal.reason}".casefold()
        restart = self._SERVICE_RESTART.fullmatch(goal.title.strip())
        if restart is not None and diagnostic_done:
            capability_name = "local.service.restart"
            if capability_name not in names:
                return None
            capability = self.gateway.capability_system.resolve(capability_name)
            return capability, {"name": restart.group(1)}
        choices = []
        if any(word in text for word in ("docker", "container", "papermerge")):
            choices.extend(("portainer.summary", "system.inspect"))
        elif any(word in text for word in ("fleet", "artemis", "offline", "node")):
            choices.extend(("ops.fleet.list", "network.inspect"))
        elif any(word in text for word in ("network", "latency", "tunnel")):
            choices.extend(("network.inspect", "system.inspect"))
        elif any(word in text for word in ("service", "restart")):
            choices.extend(("service.inspect", "system.inspect"))
        capability = next((item for item in choices if item in names), None)
        if capability is None:
            return None
        policy = capability_permission_policy(capability)
        if policy.level is not PermissionLevel.OBSERVE_READ:
            raise PermissionError("initial automatic goal step must remain Level-1 read-only")
        return self.gateway.capability_system.resolve(capability), {}


class GoalProductionCoordinator:
    """Conservative production loop. Attention triggers; typed evidence grounds."""
    def __init__(
        self,
        *,
        goals: GoalService,
        state_path: str | Path,
        gateway: CapabilityGateway,
        principal_provider: Callable[[], PrincipalContext | None],
        neuro_provider: Callable[[], NeuroStateSnapshot | None],
        notify_review: Callable[[Goal, datetime], None] | None = None,
        wake_recorder: Callable[..., None] | None = None,
    ) -> None:
        self.goals = goals
        self.path = Path(state_path)
        self.ledger = GoalEvidenceLedger(self.path)
        self.schedule = GoalRunSchedule(self.path)
        self.planner = GoalActionPlanner(gateway)
        self.permissions = PermissionStore(self.path)
        self.principal_provider = principal_provider
        self.neuro_provider = neuro_provider
        self.notify_review = notify_review
        self.wake_recorder = wake_recorder
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS goal_candidate_decision (
                    candidate_key TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    goal_id TEXT,
                    decided_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS goal_action_attempt (
                    attempt_id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    result_kind TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    attempted_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS goal_priority_evaluation (
                    goal_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    evidence_at TEXT,
                    evaluated_at TEXT NOT NULL,
                    score REAL,
                    reasons_json TEXT,
                    PRIMARY KEY(goal_id,principal_id,audience)
                );
                CREATE TABLE IF NOT EXISTS goal_action_pending (
                    goal_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'blocked_approval','authorized','executed','cancelled'
                    )),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(goal_id,principal_id,audience)
                );
            """)
            columns = {
                row[1] for row in db.execute(
                    "PRAGMA table_info(goal_priority_evaluation)"
                )
            }
            if "score" not in columns:
                db.execute("ALTER TABLE goal_priority_evaluation ADD COLUMN score REAL")
            if "reasons_json" not in columns:
                db.execute(
                    "ALTER TABLE goal_priority_evaluation ADD COLUMN reasons_json TEXT"
                )

    @staticmethod
    def _tags(value: str) -> frozenset[str]:
        allowed = {
            "docker", "container", "papermerge", "fleet", "artemis",
            "network", "tunnel", "cloudflare", "service", "latency",
            "workload", "background", "run", "host", "node",
        }
        tokens = {
            token.strip(".,:;!?()[]{}'\"").casefold()
            for token in value.split()
        }
        return frozenset(tokens & allowed)

    def evidence_relevant(self, goal: Goal, evidence_ref: str) -> bool:
        """Conservative typed linkage; text similarity never establishes fact."""
        evidence = self.goals._evidence((evidence_ref,))
        if not evidence:
            return False
        item = evidence[0]
        if item.goal_id is not None:
            return item.goal_id == goal.id
        goal_tags = self._tags(f"{goal.title} {goal.reason}")
        evidence_tags = self._tags(
            f"{item.source or ''} {item.assertion or ''}"
        )
        return bool(goal_tags and goal_tags & evidence_tags)

    def priority(
        self,
        goal: Goal,
        *,
        now: datetime,
        conversation: str = "",
        mark_evaluated: bool = False,
    ) -> GoalPriority:
        snapshot = self.neuro_provider()
        pressure = 0.0 if snapshot is None else snapshot.homeostasis.cognitive_load
        urgency = 0.0
        if goal.expires_at is not None:
            seconds = (goal.expires_at - now).total_seconds()
            urgency = 1.0 if seconds <= 0 else max(0.0, 1.0 - seconds / 604800.0)
        latest = max(
            (
                item.observed_at
                for ref in goal.evidence_refs
                for item in self.goals._evidence((ref,))
                if self.evidence_relevant(goal, ref)
            ),
            default=None,
        )
        scope = (goal.scope_principal_id or "", goal.scope_audience or "")
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute(
                "SELECT evidence_at FROM goal_priority_evaluation "
                "WHERE goal_id=? AND principal_id=? AND audience=?",
                (goal.id, *scope),
            ).fetchone()
        previous = None if not row or row[0] is None else datetime.fromisoformat(row[0])
        new_evidence = latest is not None and (previous is None or latest > previous)
        goal_tags = self._tags(f"{goal.title} {goal.reason}")
        content_tags = self._tags(conversation)
        conversational = 1.0 if (
            goal.id in conversation
            or goal.title.casefold() in conversation.casefold()
        ) else (0.5 if goal_tags & content_tags else 0.0)
        neuro_relevance = 0.0
        if snapshot is not None:
            non_goal = tuple(
                item for item in (snapshot.focus, *snapshot.secondary)
                if item is not None and item.kind != "goal"
            )
            neuro_relevance = max(
                (
                    item.score
                    for item in non_goal
                    if item.kind in goal_tags or self._tags(item.source) & goal_tags
                ),
                default=0.0,
            )
        result = effective_priority(
            goal,
            now=now,
            urgency=urgency,
            new_evidence=new_evidence,
            resource_pressure=pressure,
            conversational_relevance=conversational,
            neuro_relevance=min(0.5, neuro_relevance),
        )
        if mark_evaluated:
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute("""
                    INSERT INTO goal_priority_evaluation(
                        goal_id,principal_id,audience,evidence_at,evaluated_at,
                        score,reasons_json
                    ) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(goal_id,principal_id,audience) DO UPDATE SET
                        evidence_at=excluded.evidence_at,
                        evaluated_at=excluded.evaluated_at,
                        score=excluded.score,
                        reasons_json=excluded.reasons_json
                """, (
                    goal.id, *scope,
                    None if latest is None else latest.isoformat(), now.isoformat(),
                    result.value, json.dumps(result.reasons),
                ))
        return result

    def _reviewed_anomalies(self, now: datetime) -> tuple[ReviewedAnomaly, ...]:
        anomalies: list[ReviewedAnomaly] = []
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if "net_cloudflare_tunnel_status" in tables:
                row = db.execute("""
                    SELECT state,restart_count,updated_at FROM net_cloudflare_tunnel_status
                    WHERE singleton=1 AND configured=1
                """).fetchone()
                if row is not None and row[0] in {"degraded", "failed"}:
                    observed = datetime.fromisoformat(row[2])
                    ref = "goal-evidence:tunnel:" + sha256(row[2].encode()).hexdigest()[:20]
                    self.ledger.record(
                        evidence_ref=ref, kind="network_fault", observed_at=observed,
                        source="cloudflare-status", successful=False,
                        assertion=f"cloudflare_tunnel_{row[0]}",
                        payload={"state": row[0], "restart_count": int(row[1])},
                    )
                    anomalies.append(ReviewedAnomaly(
                        "network:cloudflare", "Investigate degraded mobile tunnel",
                        "Cloudflare tunnel has durable degraded/failed status.", ref,
                        "network",
                    ))
            if "application_background_claims" in tables:
                cutoff = (now - timedelta(hours=24)).isoformat()
                row = db.execute("""
                    SELECT COUNT(*),MAX(finished_at) FROM application_background_claims
                    WHERE status='failed' AND finished_at>=?
                """, (cutoff,)).fetchone()
                if row is not None and int(row[0] or 0) >= 2 and row[1]:
                    ref = "goal-evidence:background:" + sha256(row[1].encode()).hexdigest()[:20]
                    self.ledger.record(
                        evidence_ref=ref, kind="run_fault",
                        observed_at=datetime.fromisoformat(row[1]), source="background-claims",
                        successful=False, assertion="repeated_background_failure",
                        payload={"failures_24h": int(row[0])},
                    )
                    anomalies.append(ReviewedAnomaly(
                        "run:background", "Investigate repeated background failures",
                        "Multiple durable RUN claims failed during the last 24 hours.",
                        ref, "run", cost=GoalCost.MEDIUM,
                    ))
            if "run_supervisor_state" in tables:
                row = db.execute("""
                    SELECT owner_id,consecutive_failures,updated_at
                    FROM run_supervisor_state
                    WHERE consecutive_failures>=5
                    ORDER BY consecutive_failures DESC,updated_at DESC LIMIT 1
                """).fetchone()
                if row is not None:
                    ref = "goal-evidence:restart:" + sha256(
                        f"{row[0]}:{row[2]}".encode()
                    ).hexdigest()[:20]
                    self.ledger.record(
                        evidence_ref=ref,
                        kind="service_restart_anomaly",
                        observed_at=datetime.fromisoformat(row[2]),
                        source="run-supervisor",
                        successful=False,
                        assertion="repeated_service_restart_failure",
                        payload={"failures": int(row[1])},
                    )
                    anomalies.append(ReviewedAnomaly(
                        f"run:restart:{row[0]}",
                        "Investigate repeated service restart failures",
                        "RUN supervisor reports five or more consecutive failures.",
                        ref,
                        "run",
                        risk=GoalRisk.HIGH,
                        cost=GoalCost.MEDIUM,
                    ))
            if "ops_workload_instance" in tables:
                row = db.execute(
                    "SELECT COUNT(*),MAX(observed_at) FROM ops_workload_instance WHERE phase='failed'"
                ).fetchone()
                if row is not None and int(row[0] or 0) and row[1]:
                    stamp = str(row[1])
                    ref = "goal-evidence:workload:" + sha256(stamp.encode()).hexdigest()[:20]
                    self.ledger.record(
                        evidence_ref=ref, kind="ops_fault",
                        observed_at=datetime.fromisoformat(stamp),
                        source="ops-workload", successful=False,
                        assertion="workload_failed", payload={"failed": int(row[0])},
                    )
                    anomalies.append(ReviewedAnomaly(
                        "fleet:workload", "Investigate failed Fleet workloads",
                        "OPS reports one or more workloads in failed phase.", ref, "fleet",
                    ))
        return tuple(anomalies[:8])

    @staticmethod
    def _activation(snapshot: NeuroStateSnapshot, kind: str, now: datetime) -> NeuralActivation | None:
        candidates = tuple(item for item in (snapshot.focus, *snapshot.secondary) if item)
        return next((item for item in candidates if item.kind == kind and item.score >= 0.72), None)

    def discover(self, *, now: datetime) -> int:
        principal = self.principal_provider()
        snapshot = self.neuro_provider()
        if principal is None or snapshot is None:
            return 0
        pressure = snapshot.homeostasis.cognitive_load
        changed = 0
        for anomaly in self._reviewed_anomalies(now):
            activation = self._activation(snapshot, anomaly.activation_kind, now)
            if activation is None:
                continue
            candidate = self.goals.candidate_from_activation(
                activation=activation, title=anomaly.title, reason=anomaly.reason,
                completion=GoalCompletionCondition(
                    CompletionKind.ROOT_CAUSE_IDENTIFIED,
                    f"Reviewed root cause identified for {anomaly.title}",
                ),
                evidence_refs=(anomaly.evidence_ref,), now=now,
                risk=anomaly.risk, cost=anomaly.cost, principal=principal,
                expires_at=now + timedelta(days=14),
            )
            if candidate is None:
                continue
            goal_id = candidate.candidate_id.replace("goal-candidate:", "goal:")
            existing_exact = self.goals.store.get(
                goal_id,
                principal_id=candidate.scope_principal_id,
                audience=candidate.scope_audience,
            )
            if existing_exact is not None and existing_exact.status is GoalStatus.REJECTED:
                continue
            prior_decision = None
            prior_at = None
            with closing(sqlite3.connect(self.path, timeout=10)) as db:
                prior = db.execute(
                    "SELECT decision,decided_at FROM goal_candidate_decision "
                    "WHERE candidate_key=?",
                    (candidate.candidate_id,),
                ).fetchone()
            if prior is not None:
                prior_decision, prior_at = prior[0], datetime.fromisoformat(prior[1])
            if (
                existing_exact is not None
                and existing_exact.status is GoalStatus.CANDIDATE
                and prior_decision == GoalPolicyDecision.ASK_USER.value
            ):
                continue
            if (
                existing_exact is not None
                and existing_exact.status is GoalStatus.CANDIDATE
                and prior_decision == GoalPolicyDecision.DEFER.value
            ):
                if prior_at is not None and now < prior_at + timedelta(hours=1):
                    continue
                decision = self.goals.policy.evaluate(
                    candidate,
                    existing=tuple(
                        item for item in self.goals.store.list_scope(
                            principal_id=candidate.scope_principal_id,
                            audience=candidate.scope_audience,
                        )
                        if item.id != existing_exact.id
                    ),
                    resource_pressure=pressure,
                )
                if decision.decision is GoalPolicyDecision.ACCEPT:
                    goal = self.goals.transition(
                        goal_id=existing_exact.id,
                        principal_id=existing_exact.scope_principal_id,
                        audience=existing_exact.scope_audience,
                        expected_status=GoalStatus.CANDIDATE,
                        next_status=GoalStatus.ACTIVE,
                        actor_principal_id=SOFIA_GOAL_OWNER_ID,
                        now=now,
                        evidence_refs=candidate.evidence_refs,
                        note="deferred candidate passed bounded reconsideration",
                    )
                    goal = self.goals.set_run_state(
                        goal=goal,
                        run_state=GoalRunState.PENDING_INSPECTION,
                        actor_principal_id=SOFIA_GOAL_OWNER_ID,
                        now=now,
                    )
                else:
                    goal = existing_exact
            else:
                decision = self.goals.evaluate_candidate(
                    candidate, resource_pressure=pressure,
                )
                goal = self.goals.admit_candidate(
                    candidate,
                    decision=decision,
                    now=now,
                    resource_pressure=pressure,
                )
            if (
                goal is not None
                and decision.decision is GoalPolicyDecision.MERGE
                and goal.status is GoalStatus.ACTIVE
                and goal.run_state is GoalRunState.WAITING_EVIDENCE
                and self.evidence_relevant(goal, anomaly.evidence_ref)
            ):
                goal = self.goals.set_run_state(
                    goal=goal,
                    run_state=GoalRunState.PENDING_INSPECTION,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID,
                    now=now,
                )
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute("""
                    INSERT OR REPLACE INTO goal_candidate_decision(
                        candidate_key,decision,reason,goal_id,decided_at
                    ) VALUES(?,?,?,?,?)
                """, (
                    candidate.candidate_id, decision.decision.value, decision.reason,
                    None if goal is None else goal.id, now.isoformat(),
                ))
            if goal is not None:
                changed += 1
                if decision.decision is GoalPolicyDecision.ASK_USER and self.notify_review:
                    try:
                        self.notify_review(goal, now)
                    except Exception:
                        # ACT delivery is best-effort and never controls the
                        # canonical candidate or its review requirement.
                        pass
        return changed

    def _recently_attempted(
        self, goal_id: str, capability: str, *, now: datetime,
    ) -> bool:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute(
                "SELECT MAX(attempted_at) FROM goal_action_attempt WHERE goal_id=? AND capability=?",
                (goal_id, capability),
            ).fetchone()
        return bool(
            row and row[0]
            and datetime.fromisoformat(row[0]) > now - timedelta(minutes=30)
        )

    def _diagnostic_done(self, goal_id: str) -> bool:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            row = db.execute("""
                SELECT 1 FROM goal_action_attempt
                WHERE goal_id=? AND result_kind='success'
                LIMIT 1
            """, (goal_id,)).fetchone()
        return row is not None

    def _successful_attempt(self, goal_id: str, capability: str) -> bool:
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            return db.execute("""
                SELECT 1 FROM goal_action_attempt
                WHERE goal_id=? AND capability=? AND result_kind='success'
                LIMIT 1
            """, (goal_id, capability)).fetchone() is not None

    def wake_approved(self, *, now: datetime) -> int:
        """Wake blocked Level-3 work only after the canonical grant changes."""
        awakened = 0
        with closing(sqlite3.connect(self.path, timeout=10)) as db:
            rows = db.execute("""
                SELECT goal_id,principal_id,audience,capability,parameters_json
                FROM goal_action_pending WHERE status='blocked_approval'
                ORDER BY updated_at LIMIT 16
            """).fetchall()
        for goal_id, principal_id, audience, capability, parameters_json in rows:
            parameters = json.loads(parameters_json)
            if not self.permissions.allows_standing(capability, parameters):
                continue
            goal = self.goals.store.get(
                goal_id, principal_id=principal_id or None,
                audience=audience or None,
            )
            if goal is None or goal.status is not GoalStatus.BLOCKED:
                continue
            active = self.goals.transition(
                goal_id=goal.id,
                principal_id=goal.scope_principal_id,
                audience=goal.scope_audience,
                expected_status=GoalStatus.BLOCKED,
                next_status=GoalStatus.ACTIVE,
                actor_principal_id=SOFIA_GOAL_OWNER_ID,
                now=now,
                note="canonical exact standing approval became available",
            )
            self.goals.set_run_state(
                goal=active, run_state=GoalRunState.PENDING_INSPECTION,
                actor_principal_id=SOFIA_GOAL_OWNER_ID, now=now,
            )
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute("""
                    UPDATE goal_action_pending SET status='authorized',updated_at=?
                    WHERE goal_id=? AND principal_id=? AND audience=?
                """, (now.isoformat(), goal_id, principal_id, audience))
            awakened += 1
        return awakened

    def run_due(self, *, now: datetime) -> int:
        attempted = 0
        due = set(self.schedule.due(now))
        for goal in self.goals.store.list_all_internal():
            if attempted >= 8:
                break
            key = (goal.id, goal.scope_principal_id, goal.scope_audience)
            if goal.status in TERMINAL_GOAL_STATUSES:
                self.schedule.cancel(goal, now=now)
                continue
            eligible = (
                goal.status is GoalStatus.ACTIVE
                and (
                    goal.run_state is GoalRunState.PENDING_INSPECTION
                    or key in due
                )
            )
            if not eligible:
                continue
            text = f"{goal.title} {goal.reason}".casefold()
            existing_children = tuple(
                item for item in self.goals.store.list_scope(
                    principal_id=goal.scope_principal_id,
                    audience=goal.scope_audience,
                )
                if item.parent_goal_id == goal.id
            )
            if not existing_children and goal.parent_goal_id is None:
                steps = (
                    (
                        "Inspect container summary",
                        "Inspect host resources",
                        "Inspect local service state",
                    )
                    if any(word in text for word in ("docker", "container", "papermerge"))
                    else (
                        "Inspect Fleet membership state",
                        "Inspect network state",
                    )
                    if any(word in text for word in ("fleet", "artemis", "offline", "node"))
                    else ()
                )
                if steps:
                    self.goals.decompose(
                        parent=goal, child_titles=steps, now=now,
                    )
            plan = self.planner.plan(
                goal, diagnostic_done=self._diagnostic_done(goal.id),
            )
            if plan is None:
                self.goals.set_run_state(
                    goal=goal, run_state=GoalRunState.WAITING_EVIDENCE,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID, now=now,
                )
                continue
            capability, parameters = plan
            permission = capability_permission_policy(capability.name)
            if permission.level not in {
                PermissionLevel.OBSERVE_READ,
                PermissionLevel.SAFE_AUTONOMOUS,
            } and not self.permissions.allows_standing(
                capability.name, parameters,
            ):
                with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                    db.execute("""
                        INSERT INTO goal_action_pending(
                            goal_id,principal_id,audience,capability,
                            parameters_json,status,updated_at
                        ) VALUES(?,?,?,?,?,'blocked_approval',?)
                        ON CONFLICT(goal_id,principal_id,audience) DO UPDATE SET
                            capability=excluded.capability,
                            parameters_json=excluded.parameters_json,
                            status='blocked_approval',updated_at=excluded.updated_at
                    """, (
                        goal.id, goal.scope_principal_id or "",
                        goal.scope_audience or "", capability.name,
                        json.dumps(parameters, sort_keys=True, separators=(",", ":")),
                        now.isoformat(),
                    ))
                self.goals.transition(
                    goal_id=goal.id,
                    principal_id=goal.scope_principal_id,
                    audience=goal.scope_audience,
                    expected_status=GoalStatus.ACTIVE,
                    next_status=GoalStatus.BLOCKED,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID,
                    now=now,
                    blocked_reason=(
                        f"Exact existing permission required for {capability.name}."
                    ),
                    note="next validated goal action is blocked on approval",
                )
                continue
            if (
                permission.level not in {
                    PermissionLevel.OBSERVE_READ,
                    PermissionLevel.SAFE_AUTONOMOUS,
                }
                and self._successful_attempt(goal.id, capability.name)
            ):
                self.goals.set_run_state(
                    goal=goal, run_state=GoalRunState.WAITING_EVIDENCE,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID, now=now,
                )
                continue
            if self._recently_attempted(goal.id, capability.name, now=now):
                self.goals.set_run_state(
                    goal=goal, run_state=GoalRunState.WAITING_EVIDENCE,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID, now=now,
                )
                continue
            proposal = self.goals.propose_action(
                goal=goal, capability_name=capability.name,
                parameters=parameters, requested_scope=None,
                rationale=f"Bounded Level-1 diagnostic for goal {goal.id}",
            )
            result = self.planner.gateway.execute(proposal.proposal)
            attempt_id = "goal-action:" + sha256(
                f"{goal.id}\0{capability.name}\0{now.isoformat()}".encode()
            ).hexdigest()[:24]
            evidence = self.ledger.record(
                kind="operation_receipt", observed_at=now,
                source="goal-action", successful=result.kind is CapabilityResultKind.SUCCESS,
                goal_id=goal.id, action_id=attempt_id,
                assertion=capability.name,
                payload={"result_kind": result.kind.value},
            )
            with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                db.execute("""
                    INSERT INTO goal_action_attempt(
                        attempt_id,goal_id,capability,result_kind,evidence_ref,attempted_at
                    ) VALUES(?,?,?,?,?,?)
                """, (
                    attempt_id, goal.id, capability.name, result.kind.value,
                    evidence.evidence_ref, now.isoformat(),
                ))
            refreshed = self.goals.add_evidence(
                goal=goal, evidence_refs=(evidence.evidence_ref,), now=now,
                note=f"RUN diagnostic {capability.name}: {result.kind.value}",
            )
            if (
                result.kind is CapabilityResultKind.SUCCESS
                and refreshed.parent_goal_id is not None
                and refreshed.completion.kind is CompletionKind.OPERATION_RECEIPT
            ):
                self.goals.transition(
                    goal_id=refreshed.id,
                    principal_id=refreshed.scope_principal_id,
                    audience=refreshed.scope_audience,
                    expected_status=GoalStatus.ACTIVE,
                    next_status=GoalStatus.COMPLETED,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID,
                    now=now,
                    evidence_refs=(evidence.evidence_ref,),
                    note="bounded diagnostic child completed with linked receipt",
                )
                self.schedule.cancel(refreshed, now=now)
                attempted += 1
                continue
            if permission.level not in {
                PermissionLevel.OBSERVE_READ,
                PermissionLevel.SAFE_AUTONOMOUS,
            }:
                with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                    db.execute("""
                        UPDATE goal_action_pending
                        SET status=?,updated_at=?
                        WHERE goal_id=? AND principal_id=? AND audience=?
                    """, (
                        "executed" if result.kind is CapabilityResultKind.SUCCESS
                        else "authorized",
                        now.isoformat(), goal.id, goal.scope_principal_id or "",
                        goal.scope_audience or "",
                    ))
                refreshed = self.goals.set_run_state(
                    goal=refreshed, run_state=GoalRunState.WAITING_EVIDENCE,
                    actor_principal_id=SOFIA_GOAL_OWNER_ID, now=now,
                )
                attempted += 1
                continue
            next_state = (
                GoalRunState.SCHEDULED_RECHECK
                if result.kind is CapabilityResultKind.SUCCESS
                else GoalRunState.WAITING_EVIDENCE
            )
            refreshed = self.goals.set_run_state(
                goal=refreshed, run_state=next_state,
                actor_principal_id=SOFIA_GOAL_OWNER_ID, now=now,
            )
            if next_state is GoalRunState.SCHEDULED_RECHECK:
                self.schedule.schedule(
                    refreshed, due_at=now + timedelta(hours=1),
                    reason="bounded diagnostic recheck", now=now,
                )
            else:
                self.schedule.schedule(
                    refreshed, due_at=now + timedelta(hours=6),
                    reason="bounded evidence/status poll", now=now,
                )
            attempted += 1
        return attempted

    def reconcile_startup(self, *, now: datetime) -> dict[str, int]:
        expired = len(self.goals.expire_due(now=now))
        cleaned = self.cleanup_terminal(now=now)
        return {"expired": expired, "terminal_schedules_cleaned": cleaned}

    def cleanup_terminal(self, *, now: datetime) -> int:
        cleaned = 0
        for goal in self.goals.store.list_all_internal():
            if goal.status in TERMINAL_GOAL_STATUSES:
                self.schedule.cancel(goal, now=now)
                with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
                    db.execute("""
                        UPDATE goal_action_pending SET status='cancelled',updated_at=?
                        WHERE goal_id=? AND principal_id=? AND audience=?
                          AND status='blocked_approval'
                    """, (
                        now.isoformat(), goal.id, goal.scope_principal_id or "",
                        goal.scope_audience or "",
                    ))
                cleaned += 1
        return cleaned

    def complete_ready_parents(self, *, now: datetime) -> int:
        completed = 0
        all_goals = self.goals.store.list_all_internal()
        for parent in all_goals:
            if (
                parent.status is not GoalStatus.ACTIVE
                or parent.completion.kind is not CompletionKind.ALL_CHILDREN
            ):
                continue
            children = tuple(
                child for child in all_goals
                if child.parent_goal_id == parent.id
                and child.scope_principal_id == parent.scope_principal_id
                and child.scope_audience == parent.scope_audience
            )
            if not children or any(
                child.status is not GoalStatus.COMPLETED for child in children
            ):
                continue
            refs = tuple(dict.fromkeys(
                ref for child in children for ref in child.completion_evidence
            ))[:32]
            if not refs:
                continue
            self.goals.transition(
                goal_id=parent.id,
                principal_id=parent.scope_principal_id,
                audience=parent.scope_audience,
                expected_status=GoalStatus.ACTIVE,
                next_status=GoalStatus.COMPLETED,
                actor_principal_id=SOFIA_GOAL_OWNER_ID,
                now=now,
                evidence_refs=refs,
                note="all bounded child goals completed with typed evidence",
            )
            completed += 1
        return completed

    def tick(self, *, now: datetime) -> dict[str, int]:
        expired = len(self.goals.expire_due(now=now))
        discovered = self.discover(now=now)
        approvals = self.wake_approved(now=now)
        actions = self.run_due(now=now)
        parents = self.complete_ready_parents(now=now)
        cleaned = self.cleanup_terminal(now=now)
        result = {
            "expired": expired,
            "discovered": discovered,
            "approvals_woken": approvals,
            "actions": actions,
            "parents_completed": parents,
            "terminal_cleaned": cleaned,
        }
        if self.wake_recorder is not None:
            active_work = discovered + actions + parents + expired
            self.wake_recorder(
                mode=(
                    NeuroWakeMode.DETERMINISTIC
                    if active_work else NeuroWakeMode.NONE
                ),
                reason=(
                    "host goal coordinator handled bounded work without a model"
                    if active_work
                    else "goal refresh found no actionable state"
                ),
                llm_called=False,
                now=now,
            )
        return result
