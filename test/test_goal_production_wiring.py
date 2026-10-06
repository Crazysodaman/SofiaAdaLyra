from datetime import datetime, timedelta, timezone
import json
import sqlite3

from sofia.capability import Capability, CapabilitySystem
from sofia.capability.gateway import CapabilityGateway
from sofia.goals import (
    CompletionKind, GoalCompletionCondition, GoalEvidenceIndex,
    GoalEvidenceLedger, GoalService, GoalStatus, GoalStore,
)
from sofia.goals.coordinator import GoalProductionCoordinator
from sofia.goals.model import GoalRunState
from sofia.neuro import HomeostaticState, NeuralActivation, NeuroStateSnapshot
from sofia.social.principals import local_sparks_principal
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.safe.permissions import PermissionStore
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.state.model import StateClass, StateKey, StateRecord


NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


def snapshot(kind: str, *, pressure: float = 0.1) -> NeuroStateSnapshot:
    activation = NeuralActivation(
        key=f"{kind}:reviewed-anomaly",
        source="reviewed-anomaly",
        kind=kind,
        score=0.92,
        novelty=0.8,
        updated_at=NOW,
    )
    return NeuroStateSnapshot(
        generated_at=NOW,
        focus=activation,
        homeostasis=HomeostaticState(cognitive_load=pressure),
        active_signal_count=1,
    )


def coordinator(path, *, neural, notify=None, executions=None, mutations=None):
    plane = SQLiteStatePlane(path)
    goals = GoalService(
        GoalStore(plane), evidence_verifier=GoalEvidenceIndex(path),
    )
    capabilities = CapabilitySystem(authorization_checker=lambda _request: True)
    capabilities.register(
        Capability("ops.fleet.list", "Read fleet state."),
        lambda _request: (executions.append("fleet") if executions is not None else None)
        or {"hosts": []},
    )
    capabilities.register(
        Capability("system.inspect", "Read host state."),
        lambda _request: {"ok": True},
    )
    capabilities.register(
        Capability("local.service.restart", "Restart exact local service."),
        lambda request: (
            mutations.append(request.parameters["name"])
            if mutations is not None else None
        ) or {"restarted": request.parameters["name"]},
    )
    result = GoalProductionCoordinator(
        goals=goals,
        state_path=path,
        gateway=CapabilityGateway(capabilities),
        principal_provider=local_sparks_principal,
        neuro_provider=lambda: neural[0],
        notify_review=notify,
    )
    return goals, result


def failed_workload(path):
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE ops_workload_instance(
                instance_id TEXT PRIMARY KEY,workload_id TEXT,version TEXT,
                host_id TEXT,phase TEXT,lease_epoch INTEGER,observed_at TEXT
            )
        """)
        db.execute(
            "INSERT INTO ops_workload_instance VALUES(?,?,?,?,?,?,?)",
            ("one", "papermerge", "1", "artemis", "failed", None, NOW.isoformat()),
        )


def test_neuro_anomaly_creates_activates_and_runs_scoped_self_goal(tmp_path):
    path = tmp_path / "sofia.db"
    SQLiteStatePlane(path)
    failed_workload(path)
    neural = [snapshot("fleet")]
    executions = []
    goals, production = coordinator(
        path, neural=neural, executions=executions,
    )

    assert production.discover(now=NOW) == 1
    visible = goals.list_visible(local_sparks_principal())
    assert len(visible) == 1
    goal = visible[0]
    assert goal.status is GoalStatus.ACTIVE
    assert goal.run_state is GoalRunState.PENDING_INSPECTION
    assert goal.scope_principal_id == local_sparks_principal().principal_id

    assert production.run_due(now=NOW + timedelta(seconds=1)) == 1
    assert executions == ["fleet"]
    after_first_run = goals.list_visible(local_sparks_principal())
    refreshed = next(item for item in after_first_run if item.id == goal.id)
    children = tuple(item for item in after_first_run if item.parent_goal_id == goal.id)
    assert len(children) == 2
    assert refreshed.run_state is GoalRunState.SCHEDULED_RECHECK
    assert len(refreshed.evidence_refs) == 2

    # Restart recovers the durable schedule and executes only when it is due.
    _, restarted = coordinator(path, neural=neural, executions=executions)
    # Pending child diagnostics are real queued work and recover immediately;
    # the parent's one-hour recheck itself is not run early.
    assert restarted.run_due(now=NOW + timedelta(minutes=30)) == 2
    assert restarted.run_due(now=NOW + timedelta(hours=2)) >= 1
    assert executions == ["fleet", "fleet", "fleet"]


def test_duplicate_anomaly_merges_evidence_without_goal_confetti(tmp_path):
    path = tmp_path / "sofia.db"
    SQLiteStatePlane(path)
    failed_workload(path)
    neural = [snapshot("fleet")]
    goals, production = coordinator(path, neural=neural)
    production.discover(now=NOW)
    production.discover(now=NOW + timedelta(minutes=5))
    assert len(goals.list_visible(local_sparks_principal())) == 1


def test_high_risk_restart_anomaly_asks_sparks_and_does_not_run(tmp_path):
    path = tmp_path / "sofia.db"
    SQLiteStatePlane(path)
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE run_supervisor_state(
                owner_id TEXT PRIMARY KEY,epoch INTEGER,consecutive_failures INTEGER,
                last_start_at TEXT,backoff_until TEXT,readiness_deadline TEXT,
                updated_at TEXT
            )
        """)
        db.execute(
            "INSERT INTO run_supervisor_state VALUES(?,?,?,?,?,?,?)",
            ("sofia", 1, 5, None, None, None, NOW.isoformat()),
        )
    notices = []
    neural = [snapshot("run")]
    goals, production = coordinator(
        path, neural=neural, notify=lambda goal, _now: notices.append(goal.id),
    )
    production.discover(now=NOW)
    goal = goals.list_visible(local_sparks_principal())[0]
    assert goal.status is GoalStatus.CANDIDATE
    assert goal.run_state is GoalRunState.NONE
    assert notices == [goal.id]
    assert production.run_due(now=NOW + timedelta(minutes=1)) == 0


def test_deferred_candidate_is_reconsidered_after_resource_pressure_drops(tmp_path):
    path = tmp_path / "sofia.db"
    SQLiteStatePlane(path)
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE application_background_claims(
                claim_id TEXT PRIMARY KEY,task_kind TEXT,claimed_at TEXT,
                day_utc TEXT,status TEXT,finished_at TEXT,error_type TEXT
            )
        """)
        for number in (1, 2):
            db.execute(
                "INSERT INTO application_background_claims VALUES(?,?,?,?,?,?,?)",
                (str(number), "test", NOW.isoformat(), NOW.date().isoformat(),
                 "failed", NOW.isoformat(), "ExampleFailure"),
            )
    neural = [snapshot("run", pressure=0.9)]
    goals, production = coordinator(path, neural=neural)
    production.discover(now=NOW)
    assert goals.list_visible(local_sparks_principal())[0].status is GoalStatus.CANDIDATE

    neural[0] = snapshot("run", pressure=0.1)
    production.discover(now=NOW + timedelta(hours=2))
    goal = goals.list_visible(local_sparks_principal())[0]
    assert goal.status is GoalStatus.ACTIVE
    assert goal.run_state is GoalRunState.PENDING_INSPECTION


def scoped_principal(audience: str) -> PrincipalContext:
    return PrincipalContext(
        principal_id="person:sparks",
        audience_id=audience,
        audience_kind=AudienceKind.PRIVATE,
        display_name="Sparks",
    )


def create_user_goal(
    goals, ledger, *, principal, ref, completion, expires_at=None, title=None,
):
    ledger.record(
        evidence_ref=ref, kind="authenticated_user_message", observed_at=NOW,
        source="test-conversation", principal_id=principal.principal_id,
        audience=f"private:{principal.audience_id}",
    )
    return goals.create_user_goal(
        principal=principal,
        title=title or f"Goal for {principal.audience_id} {ref}",
        reason="Authenticated test direction.", base_priority=0.7, confidence=1.0,
        completion=completion, evidence_refs=(ref,), now=NOW,
        expires_at=expires_at,
    )


def test_scoped_expiration_survives_restart_without_cross_audience_projection(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    ledger = GoalEvidenceLedger(path)
    goals = GoalService(GoalStore(plane), evidence_verifier=GoalEvidenceIndex(path))
    one = scoped_principal("dm:one")
    two = scoped_principal("dm:two")
    condition = GoalCompletionCondition(CompletionKind.USER_DEFINED, "Owner confirms.")
    first = create_user_goal(
        goals, ledger, principal=one, ref="message:one", completion=condition,
        expires_at=NOW + timedelta(hours=1),
    )
    second = create_user_goal(
        goals, ledger, principal=two, ref="message:two", completion=condition,
        expires_at=NOW + timedelta(hours=1),
    )

    restarted = GoalService(
        GoalStore(SQLiteStatePlane(path)), evidence_verifier=GoalEvidenceIndex(path),
    )
    expired = restarted.expire_due(now=NOW + timedelta(hours=2))
    assert {item.id for item in expired} == {first.id, second.id}
    assert {item.id for item in restarted.list_visible(one)} == {first.id}
    assert {item.id for item in restarted.list_visible(two)} == {second.id}


def test_legacy_unscoped_self_goal_is_quarantined_on_restart(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    payload = {
        "id": "goal:legacy-self", "origin": "self",
        "owner_principal_id": "sofia:self", "scope_principal_id": None,
        "scope_audience": None, "title": "Legacy private direction",
        "reason": "Imported before scoped SELF enforcement.", "status": "active",
        "base_priority": 0.7, "confidence": 0.9,
        "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
        "evidence_refs": [],
        "completion": {"kind": "evidence_true", "description": "Resolved.",
                       "no_recurrence_seconds": None},
        "history": [], "parent_goal_id": None, "blocked_reason": None,
        "completion_evidence": [], "expires_at": None,
        "superseded_by": None, "run_state": "pending_inspection", "revision": 1,
    }
    plane.write(StateRecord(
        key=StateKey(namespace="goals-v1", key="goal:legacy-self"),
        state_class=StateClass.SHARED_AUTHORITATIVE, revision=1,
        value=json.dumps(payload).encode("utf-8"),
        updated_at=NOW, source="goal:self",
    ), expected_revision=None)

    store = GoalStore(SQLiteStatePlane(path))
    quarantined = store.get(
        "goal:legacy-self", principal_id=None, audience=None,
    )
    assert quarantined is not None
    assert quarantined.status is GoalStatus.CANCELLED
    assert quarantined.run_state is GoalRunState.NONE
    assert quarantined.history[-1].note.startswith("legacy unscoped SELF")
    service = GoalService(store, evidence_verifier=GoalEvidenceIndex(path))
    assert service.list_visible(scoped_principal("dm:one")) == ()


def test_goal_state_cannot_self_validate_another_goal(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    ledger = GoalEvidenceLedger(path)
    index = GoalEvidenceIndex(path)
    goals = GoalService(GoalStore(plane), evidence_verifier=index)
    owner = scoped_principal("dm:one")
    first = create_user_goal(
        goals, ledger, principal=owner, ref="message:first",
        completion=GoalCompletionCondition(CompletionKind.USER_DEFINED, "Owner confirms."),
    )
    assert index.lookup(first.id) is None
    try:
        goals.create_user_goal(
            principal=owner, title="Manufactured circular goal",
            reason="Must not trust goal state as factual evidence.",
            base_priority=0.7, confidence=1.0,
            completion=GoalCompletionCondition(CompletionKind.EVIDENCE_TRUE, "Fact."),
            evidence_refs=(first.id,), now=NOW + timedelta(seconds=1),
        )
    except ValueError as exc:
        assert "host-verified" in str(exc)
    else:
        raise AssertionError("goal state became circular factual evidence")


def test_typed_evidence_refs_are_idempotent_but_immutable(tmp_path):
    ledger = GoalEvidenceLedger(tmp_path / "sofia.db")
    first = ledger.record(
        evidence_ref="evidence:stable", kind="ops_fault", observed_at=NOW,
        source="ops", successful=False, assertion="docker_failed",
    )
    repeated = ledger.record(
        evidence_ref="evidence:stable", kind="ops_fault", observed_at=NOW,
        source="ops", successful=False, assertion="docker_failed",
    )
    assert repeated == first
    try:
        ledger.record(
            evidence_ref="evidence:stable", kind="ops_fault", observed_at=NOW,
            source="ops", successful=True, assertion="docker_recovered",
        )
    except ValueError as exc:
        assert "immutable evidence" in str(exc)
    else:
        raise AssertionError("an evidence reference was rebound to a different fact")


def test_typed_completion_rejects_wrong_goal_receipt_and_offline_coverage(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    ledger = GoalEvidenceLedger(path)
    goals = GoalService(
        GoalStore(plane), evidence_verifier=GoalEvidenceIndex(path),
    )
    owner = scoped_principal("dm:one")
    operation = create_user_goal(
        goals, ledger, principal=owner, ref="message:operation",
        completion=GoalCompletionCondition(
            CompletionKind.OPERATION_RECEIPT, "Verified repair operation.",
        ),
    )
    wrong = ledger.record(
        kind="operation_receipt", observed_at=NOW + timedelta(minutes=1),
        source="capability-gateway", successful=True, goal_id="goal:other",
    )
    try:
        goals.transition(
            goal_id=operation.id, principal_id=operation.scope_principal_id,
            audience=operation.scope_audience, expected_status=GoalStatus.ACTIVE,
            next_status=GoalStatus.COMPLETED, actor_principal_id="sofia:self",
            now=NOW + timedelta(minutes=2), evidence_refs=(wrong.evidence_ref,),
        )
    except ValueError as exc:
        assert "linked operation receipt" in str(exc)
    else:
        raise AssertionError("unrelated operation receipt completed a goal")

    monitoring = create_user_goal(
        goals, ledger, principal=owner, ref="message:monitoring",
        completion=GoalCompletionCondition(
            CompletionKind.NO_RECURRENCE, "No recurrence for one hour.",
            no_recurrence_seconds=3600,
        ),
    )
    gap = ledger.record(
        kind="monitoring_coverage", observed_at=NOW + timedelta(hours=1),
        source="telemetry", successful=True, goal_id=monitoring.id,
        coverage_started_at=NOW, coverage_ended_at=NOW + timedelta(hours=1),
        coverage_complete=False,
    )
    try:
        goals.transition(
            goal_id=monitoring.id, principal_id=monitoring.scope_principal_id,
            audience=monitoring.scope_audience, expected_status=GoalStatus.ACTIVE,
            next_status=GoalStatus.COMPLETED, actor_principal_id="sofia:self",
            now=NOW + timedelta(hours=1), evidence_refs=(gap.evidence_ref,),
            no_recurrence_since=NOW,
        )
    except ValueError as exc:
        assert "continuous monitoring" in str(exc)
    else:
        raise AssertionError("offline telemetry gap satisfied no-recurrence")


def test_dynamic_priority_uses_new_typed_evidence_without_neuro_feedback_loop(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    ledger = GoalEvidenceLedger(path)
    goals = GoalService(
        GoalStore(plane), evidence_verifier=GoalEvidenceIndex(path),
    )
    owner = scoped_principal("dm:one")
    goal = create_user_goal(
        goals, ledger, principal=owner, ref="message:priority",
        completion=GoalCompletionCondition(
            CompletionKind.ROOT_CAUSE_IDENTIFIED, "Identify Fleet root cause.",
        ),
        title="Investigate Artemis fleet outage",
        expires_at=NOW + timedelta(days=2),
    )
    evidence = ledger.record(
        kind="ops_fault", observed_at=NOW + timedelta(minutes=1),
        source="fleet:artemis", successful=False, goal_id=goal.id,
        assertion="artemis_offline",
    )
    goal = goals.add_evidence(
        goal=goal, evidence_refs=(evidence.evidence_ref,),
        now=NOW + timedelta(minutes=1), note="new related Fleet evidence",
    )
    neural = [snapshot("fleet", pressure=0.4)]
    _, production = coordinator(path, neural=neural)
    first = production.priority(
        goal, now=NOW + timedelta(minutes=2),
        conversation="Artemis fleet status", mark_evaluated=True,
    )
    second = production.priority(
        goal, now=NOW + timedelta(minutes=3),
        conversation="unrelated", mark_evaluated=False,
    )
    assert "new-evidence=+0.050" in first.reasons
    assert any(reason.startswith("conversation=+0.050") for reason in first.reasons)
    assert any(reason.startswith("neuro=+") for reason in first.reasons)
    assert "new-evidence=+0.050" not in second.reasons
    assert goal.base_priority == 0.7


def test_mutation_next_step_blocks_until_exact_existing_permission(tmp_path):
    path = tmp_path / "sofia.db"
    plane = SQLiteStatePlane(path)
    ledger = GoalEvidenceLedger(path)
    goals = GoalService(
        GoalStore(plane), evidence_verifier=GoalEvidenceIndex(path),
    )
    owner = local_sparks_principal()
    goal = create_user_goal(
        goals, ledger, principal=owner, ref="message:restart",
        title="Restarting Docker",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner confirms Docker is stable.",
        ),
    )
    neural = [snapshot("ops")]
    mutations = []
    _, production = coordinator(path, neural=neural, mutations=mutations)

    # First pass is observation only. The next validated mutation blocks.
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 1
    assert mutations == []
    production.run_due(now=NOW + timedelta(hours=2))
    blocked = goals.store.get(
        goal.id, principal_id=goal.scope_principal_id,
        audience=goal.scope_audience,
    )
    assert blocked.status is GoalStatus.BLOCKED
    assert blocked.run_state is GoalRunState.BLOCKED_APPROVAL
    assert mutations == []

    PermissionStore(path).grant(
        "local.service.restart", scope={"name": "Docker"},
        granted_by="Sparks", now=NOW + timedelta(hours=2, minutes=1),
    )
    assert production.wake_approved(
        now=NOW + timedelta(hours=2, minutes=2),
    ) == 1
    assert production.run_due(
        now=NOW + timedelta(hours=2, minutes=3),
    ) == 1
    assert mutations == ["Docker"]
    waiting = goals.store.get(
        goal.id, principal_id=goal.scope_principal_id,
        audience=goal.scope_audience,
    )
    assert waiting.status is GoalStatus.ACTIVE
    assert waiting.run_state is GoalRunState.WAITING_EVIDENCE
    assert production.run_due(now=NOW + timedelta(days=1)) == 0
    assert mutations == ["Docker"]
