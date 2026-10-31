from test.owner_auth_fixture import (grant_with_signed_owner, revoke_with_signed_owner, private_with_signed_owner, record_verified_owner_approval)
from datetime import datetime, timedelta, timezone
import pytest
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
import json
import sqlite3

from sofia.platform.capability import Capability, CapabilitySystem
from sofia.platform.capability.model import CapabilityResult, CapabilityResultKind
from sofia.platform.capability.gateway import CapabilityGateway
from sofia.core.goals import (
    CompletionKind, GoalCompletionCondition, GoalEvidenceIndex,
    GoalEvidenceLedger, GoalService, GoalStatus, GoalStore,
)
from sofia.core.goals.coordinator import (
    GoalProductionCoordinator, goal_reconciliation_approval_parameters,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.core.generalization.advanced import AdvancedGeneralizationStore, EpisodePhase
from sofia.core.generalization.contracts import ExplorationAdmission
from sofia.core.learning.contracts import DataUseGrant
from sofia.core.learning.service import LearningService
from sofia.core.goals.model import GoalRunState
from sofia.modules.neuro import HomeostaticState, NeuralActivation, NeuroStateSnapshot
from sofia.core.social.principals import local_sparks_principal
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.goals.service import audience_scope
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.model import StateClass, StateKey, StateRecord


NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _isolated_goal_canonical_home(tmp_path):
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")



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


def coordinator(
    path, *, neural, notify=None, executions=None, mutations=None,
    reconciliation_authorizer=None, independent_outcome_verifier=None,
    reconciliation_approval_verifier=None,
):
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
        Capability("portainer.summary", "Read container state."),
        lambda _request: (executions.append("portainer") if executions is not None else None)
        or {"containers": []},
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
        reconciliation_authorizer=reconciliation_authorizer,
        independent_outcome_verifier=independent_outcome_verifier,
        reconciliation_approval_verifier=reconciliation_approval_verifier,
    )
    return goals, result


class _GeneralizationLearningGrant:
    def active_grant(self, *, principal_id, audience_id, purpose, required, at):
        return DataUseGrant(
            "grant:goal-generalization", principal_id, audience_id, purpose,
            frozenset(required), NOW - timedelta(hours=1), NOW + timedelta(days=30),
            "owner-ui:goal-generalization",
        )


def test_scoped_failed_experience_changes_diagnostic_choice_and_records_ablation(tmp_path):
    path = tmp_path / "sofia.db"
    SQLiteStatePlane(path)
    executions = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=executions,
    )
    advanced = AdvancedGeneralizationStore(
        path, goals=goals, admission=lambda: ExplorationAdmission(),
        learning=_GeneralizationLearningGrant(),
    )
    production.generalization = advanced
    principal = local_sparks_principal()
    ledger = GoalEvidenceLedger(path)
    refs = []
    for index, kind in enumerate((
        "reviewed_evidence", "external_observation", "reviewed_evidence",
        "operation_receipt", "operation_receipt",
    )):
        ref = f"planning-experience:{index}"
        ledger.record(
            evidence_ref=ref, kind=kind, observed_at=NOW,
            source="ops:planning-experience",
            assertion="portainer.summary" if index == 3 else None,
            successful=False if index == 4 else None,
            principal_id=principal.principal_id, audience=principal.audience_id,
        )
        refs.append(ref)
    advanced.record_episode(
        principal=principal, subject_id="service:docker",
        context_tags=("docker", "container"),
        phases=tuple(
            EpisodePhase(kind, f"Prior {kind}", (refs[index],))
            for index, kind in enumerate(
                ("intent", "observation", "hypothesis", "action", "outcome")
            )
        ),
        occurred_at=NOW, retention_until=NOW + timedelta(days=10), now=NOW,
    )
    goal = create_user_goal(
        goals, ledger, principal=principal, ref="message:docker-experience",
        title="Investigate Docker failures",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner confirms diagnosis.",
        ),
    )
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 1
    assert executions == []
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT capability FROM goal_action_attempt WHERE goal_id=?", (goal.id,),
        ).fetchone() == ("system.inspect",)
        assert db.execute(
            "SELECT ablation FROM ga_planning_influence WHERE goal_id=? "
            "ORDER BY ablation", (goal.id,),
        ).fetchall() == [("with_experience",), ("without_experience",)]


def test_g7a_verified_learning_changes_actual_goals_decision_vs_ablation(tmp_path):
    """The counterfactual must run GOALS, not merely label an audit trace."""
    learned_path = tmp_path / "learned.db"
    bootstrap_canonical_sqlite(learned_path)
    learned_goals, learned_production = coordinator(
        learned_path, neural=[snapshot("ops")],
    )
    advanced = AdvancedGeneralizationStore(
        learned_path, goals=learned_goals,
        admission=lambda: ExplorationAdmission(),
        learning=_GeneralizationLearningGrant(),
    )
    learned_production.generalization = advanced
    principal = local_sparks_principal()
    learned_ledger = GoalEvidenceLedger(learned_path)
    refs = []
    for index, kind in enumerate((
        "reviewed_evidence", "external_observation", "reviewed_evidence",
        "operation_receipt", "operation_receipt",
    )):
        ref = f"g7a-ablation-evidence:{index}"
        learned_ledger.record(
            evidence_ref=ref, kind=kind, observed_at=NOW,
            source="ops:g7a-ablation",
            assertion="portainer.summary" if index == 3 else None,
            successful=False if index == 4 else None,
            principal_id=principal.principal_id,
            audience=principal.audience_id,
        )
        refs.append(ref)
    advanced.record_episode(
        principal=principal,
        subject_id="service:docker",
        context_tags=("docker", "container"),
        phases=tuple(
            EpisodePhase(kind, f"Verified {kind}", (refs[index],))
            for index, kind in enumerate((
                "intent", "observation", "hypothesis", "action", "outcome",
            ))
        ),
        occurred_at=NOW, retention_until=NOW + timedelta(days=10), now=NOW,
    )
    condition = GoalCompletionCondition(
        CompletionKind.USER_DEFINED, "Owner confirms diagnosis.",
    )
    learned_goal = create_user_goal(
        learned_goals, learned_ledger, principal=principal,
        ref="message:g7a-learned", title="Investigate Docker failures",
        completion=condition,
    )
    assert learned_production.run_due(now=NOW + timedelta(seconds=1)) == 1
    with sqlite3.connect(learned_path) as db:
        learned_choice = db.execute(
            "SELECT capability FROM goal_action_attempt WHERE goal_id=?",
            (learned_goal.id,),
        ).fetchone()[0]
        traces = db.execute(
            "SELECT ablation FROM ga_planning_influence WHERE goal_id=? "
            "ORDER BY ablation",
            (learned_goal.id,),
        ).fetchall()
    assert learned_choice == "system.inspect"
    assert traces == [("with_experience",), ("without_experience",)]

    # No-learning control gets the SAME authenticated goal, clock, scope and
    # capability set but no learned failure. Its real selected action differs.
    baseline_path = tmp_path / "without-learning.db"
    bootstrap_canonical_sqlite(baseline_path)
    baseline_goals, baseline_production = coordinator(
        baseline_path, neural=[snapshot("ops")],
    )
    baseline_ledger = GoalEvidenceLedger(baseline_path)
    baseline_goal = create_user_goal(
        baseline_goals, baseline_ledger, principal=principal,
        ref="message:g7a-baseline", title="Investigate Docker failures",
        completion=condition,
    )
    assert baseline_production.run_due(now=NOW + timedelta(seconds=1)) == 1
    with sqlite3.connect(baseline_path) as db:
        baseline_choice = db.execute(
            "SELECT capability FROM goal_action_attempt WHERE goal_id=?",
            (baseline_goal.id,),
        ).fetchone()[0]
    assert baseline_choice == "portainer.summary"
    assert learned_choice != baseline_choice


def test_g7a_successful_prior_episode_does_not_forge_planning_influence(tmp_path):
    """Relevant experience alone is not proof that the planner changed."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    goals, production = coordinator(path, neural=[snapshot("ops")])
    advanced = AdvancedGeneralizationStore(
        path, goals=goals,
        admission=lambda: ExplorationAdmission(),
        learning=_GeneralizationLearningGrant(),
    )
    production.generalization = advanced
    principal = local_sparks_principal()
    ledger = GoalEvidenceLedger(path)
    refs = []
    kinds = (
        "reviewed_evidence", "external_observation", "reviewed_evidence",
        "operation_receipt", "operation_receipt",
    )
    for index, kind in enumerate(kinds):
        ref = f"g7a-no-change:{index}"
        ledger.record(
            evidence_ref=ref, kind=kind, observed_at=NOW,
            source="ops:g7a-no-change",
            assertion="portainer.summary" if index == 3 else None,
            successful=True if index == 4 else None,
            principal_id=principal.principal_id, audience=principal.audience_id,
        )
        refs.append(ref)
    advanced.record_episode(
        principal=principal, subject_id="service:docker",
        context_tags=("docker", "container"),
        phases=tuple(
            EpisodePhase(kind, f"Verified {kind}", (refs[index],))
            for index, kind in enumerate((
                "intent", "observation", "hypothesis", "action", "outcome",
            ))
        ),
        occurred_at=NOW, retention_until=NOW + timedelta(days=10), now=NOW,
    )
    goal = create_user_goal(
        goals, ledger, principal=principal,
        ref="message:g7a-no-change", title="Investigate Docker containers",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner verifies inspection.",
        ),
    )
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 1
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT capability FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == ("portainer.summary",)
        assert db.execute(
            "SELECT COUNT(*) FROM ga_planning_influence WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)


def test_g7a_revoked_learning_restores_baseline_planner_after_restart(tmp_path):
    """A revoked outcome cannot keep steering GOALS after a Core restart."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    principal = local_sparks_principal()
    goals, production = coordinator(path, neural=[snapshot("ops")])
    advanced = AdvancedGeneralizationStore(
        path, goals=goals, admission=lambda: ExplorationAdmission(),
        learning=_GeneralizationLearningGrant(),
    )
    production.generalization = advanced
    ledger = GoalEvidenceLedger(path)
    refs = []
    phase_kinds = ("intent", "observation", "hypothesis", "action", "outcome")
    evidence_kinds = (
        "reviewed_evidence", "external_observation", "reviewed_evidence",
        "operation_receipt", "operation_receipt",
    )
    for index, kind in enumerate(evidence_kinds):
        ref = f"g7a-revocation:{index}"
        ledger.record(
            evidence_ref=ref, kind=kind, observed_at=NOW,
            source="ops:g7a-reviewed-experience",
            assertion="portainer.summary" if index == 3 else None,
            successful=False if index == 4 else None,
            principal_id=principal.principal_id, audience=principal.audience_id,
        )
        refs.append(ref)
    advanced.record_episode(
        principal=principal, subject_id="service:docker",
        context_tags=("docker", "container"),
        phases=tuple(
            EpisodePhase(kind, f"Verified {kind}", (refs[index],))
            for index, kind in enumerate(phase_kinds)
        ),
        occurred_at=NOW, retention_until=NOW + timedelta(days=10), now=NOW,
    )
    condition = GoalCompletionCondition(
        CompletionKind.USER_DEFINED, "Owner verifies diagnosis.",
    )
    first = create_user_goal(
        goals, ledger, principal=principal, ref="message:g7a-before-revocation",
        title="Investigate Docker failures", completion=condition,
    )
    assert production.run_due(now=NOW + timedelta(seconds=1)) >= 1
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT capability FROM goal_action_attempt WHERE goal_id=?",
            (first.id,),
        ).fetchone() == ("system.inspect",)

    # Reproduce a previously authorized data-source revocation in the
    # persisted learning schema. No test code issues an actual owner grant.
    LearningService(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO ml_source_revocation(source_ref,revoked_at,approval_ref) "
            "VALUES(?,?,?)",
            (refs[4], (NOW + timedelta(minutes=1)).isoformat(),
             "safe:verified-revocation-fixture"),
        )

    # A new Core composition sees the revocation BEFORE the background
    # propagation pass. Retrieval must never allow stale learning influence.
    restarted_goals, restarted_production = coordinator(
        path, neural=[snapshot("ops")],
    )
    restarted_advanced = AdvancedGeneralizationStore(
        path, goals=restarted_goals,
        admission=lambda: ExplorationAdmission(),
        learning=_GeneralizationLearningGrant(),
    )
    restarted_production.generalization = restarted_advanced
    assert restarted_advanced.retrieve_experiences(
        principal=principal, tags=("docker",), now=NOW + timedelta(minutes=2),
    ) == ()
    second = create_user_goal(
        restarted_goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-after-revocation",
        # Distinct real follow-up goal: duplicate live goals remain forbidden.
        title="Investigate Docker service diagnostics after revocation",
        completion=condition,
    )
    # Verify the exact GOALS planner decision after restart without
    # executing unrelated persisted diagnostic children. Multi-goal RUN
    # reconciliation has its own revision/lease gate.
    advice = restarted_advanced.planning_advice(
        principal=principal, goal_id=second.id, context_tags=("docker",),
        now=NOW + timedelta(minutes=2),
    )
    assert advice["episode_ids"] == ()
    assert advice["avoid_capabilities"] == ()
    chosen = restarted_production.planner.plan(
        second, diagnostic_done=False,
        avoid_capabilities=tuple(advice["avoid_capabilities"]),
    )
    assert chosen is not None
    assert chosen[0].name == "portainer.summary"
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM ga_planning_influence WHERE goal_id=?",
            (second.id,),
        ).fetchone() == (0,)


def test_g7a_run_due_skips_stale_goal_snapshot_before_tool_dispatch(
    tmp_path, monkeypatch
):
    """A sibling/owner update after enumeration cannot authorize an old plan."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    dispatched = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=dispatched,
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-cas-snapshot", title="Diagnose Docker containers",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner reviews diagnosis.",
        ),
    )
    enumerate_live = goals.store.list_all_internal

    def competing_evidence_update():
        candidates = enumerate_live()
        current = next(item for item in candidates if item.id == goal.id)
        goals.set_run_state(
            goal=current, run_state=GoalRunState.PENDING_INSPECTION,
            actor_principal_id="sofia:self", now=NOW,
        )
        return candidates  # the original snapshot is now stale

    monkeypatch.setattr(goals.store, "list_all_internal", competing_evidence_update)
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 0
    assert dispatched == []
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)

    monkeypatch.setattr(goals.store, "list_all_internal", enumerate_live)
    assert production.run_due(now=NOW + timedelta(seconds=2)) == 1
    assert dispatched == ["portainer"]
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT capability FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == ("portainer.summary",)


def test_g7a_owner_cancelled_goal_cannot_execute_from_stale_snapshot(
    tmp_path, monkeypatch
):
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    dispatched = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=dispatched,
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-cancelled-snapshot", title="Diagnose Docker containers",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner reviews diagnosis.",
        ),
    )
    cancel_ref = "message:g7a-owner-cancel-before-dispatch"
    GoalEvidenceLedger(path).record(
        evidence_ref=cancel_ref, kind="authenticated_user_message",
        observed_at=NOW, source="test-owner-cancellation",
        principal_id=principal.principal_id,
        audience=f"private:{principal.audience_id}",
    )
    enumerate_live = goals.store.list_all_internal

    def owner_cancels_after_enumeration():
        candidates = enumerate_live()
        goals.transition(
            goal_id=goal.id,
            principal_id=goal.scope_principal_id,
            audience=goal.scope_audience,
            expected_status=GoalStatus.ACTIVE,
            next_status=GoalStatus.CANCELLED,
            actor_principal_id=principal.principal_id,
            authenticated_principal=principal,
            evidence_refs=(cancel_ref,),
            now=NOW,
            note="Owner cancelled before tool dispatch",
        )
        return candidates

    monkeypatch.setattr(
        goals.store, "list_all_internal", owner_cancels_after_enumeration,
    )
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 0
    assert dispatched == []
    assert goals.store.get(
        goal.id, principal_id=goal.scope_principal_id,
        audience=goal.scope_audience,
    ).status is GoalStatus.CANCELLED
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)


def test_g7a_atomic_reservation_rejects_revision_changed_after_final_check(
    tmp_path, monkeypatch
):
    """Changing goal revision between final read and reserve cannot race RUN."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    calls = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=calls,
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-atomic-revision", title="Diagnose Docker container health",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner verifies diagnosis.",
        ),
    )
    original_reserve = production._reserve_dispatch
    crossed_boundary = []

    def revise_before_reservation(**kwargs):
        original_goal = kwargs["goal"]
        goals.set_run_state(
            goal=original_goal, run_state=GoalRunState.WAITING_EVIDENCE,
            actor_principal_id="sofia:self", now=NOW,
        )
        crossed_boundary.append(original_goal.revision)
        return original_reserve(**kwargs)

    monkeypatch.setattr(production, "_reserve_dispatch", revise_before_reservation)
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 0
    assert crossed_boundary
    assert calls == []
    assert production.unresolved_dispatches(goal.id) == ()
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_dispatch WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)


def test_g7a_atomic_reservation_rejects_owner_cancellation_after_final_check(
    tmp_path, monkeypatch
):
    """Owner cancel and action reservation serialize on canonical writer."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    calls = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=calls,
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-atomic-cancel", title="Diagnose Docker container health",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner verifies diagnosis.",
        ),
    )
    cancel_ref = "message:g7a-cancel-during-reserve"
    GoalEvidenceLedger(path).record(
        evidence_ref=cancel_ref, kind="authenticated_user_message",
        observed_at=NOW, source="test-owner-cancellation",
        principal_id=principal.principal_id,
        audience=audience_scope(principal),
    )
    original_reserve = production._reserve_dispatch

    def cancel_before_reservation(**kwargs):
        goals.transition(
            goal_id=goal.id, principal_id=goal.scope_principal_id,
            audience=goal.scope_audience,
            expected_status=GoalStatus.ACTIVE, next_status=GoalStatus.CANCELLED,
            actor_principal_id=principal.principal_id,
            authenticated_principal=principal, evidence_refs=(cancel_ref,),
            now=NOW, note="Owner cancelled before atomic reservation",
        )
        return original_reserve(**kwargs)

    monkeypatch.setattr(production, "_reserve_dispatch", cancel_before_reservation)
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 0
    assert calls == []
    assert production.unresolved_dispatches(goal.id) == ()
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_dispatch WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)
    assert goals.store.get(
        goal.id, principal_id=goal.scope_principal_id,
        audience=goal.scope_audience,
    ).status is GoalStatus.CANCELLED


def test_g7a_goal_revocation_after_planning_blocks_tool_dispatch(
    tmp_path, monkeypatch
):
    """Even a previously proposed read-only action loses authority on cancel."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    dispatched = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=dispatched,
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-revoked-after-plan", title="Diagnose Docker containers",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner reviews diagnosis.",
        ),
    )
    cancel_ref = "message:g7a-owner-cancel-after-plan"
    GoalEvidenceLedger(path).record(
        evidence_ref=cancel_ref, kind="authenticated_user_message",
        observed_at=NOW, source="test-owner-cancellation",
        principal_id=principal.principal_id,
        audience=f"private:{principal.audience_id}",
    )
    propose = goals.propose_action

    def cancel_after_proposal(**kwargs):
        approved_proposal = propose(**kwargs)
        goals.transition(
            goal_id=goal.id,
            principal_id=goal.scope_principal_id,
            audience=goal.scope_audience,
            expected_status=GoalStatus.ACTIVE,
            next_status=GoalStatus.CANCELLED,
            actor_principal_id=principal.principal_id,
            authenticated_principal=principal,
            evidence_refs=(cancel_ref,),
            now=NOW,
            note="Owner cancellation while GOALS planned",
        )
        return approved_proposal

    monkeypatch.setattr(goals, "propose_action", cancel_after_proposal)
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 0
    assert dispatched == []
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)
    assert goals.store.get(
        goal.id, principal_id=goal.scope_principal_id,
        audience=goal.scope_audience,
    ).status is GoalStatus.CANCELLED


def test_g7a_multiple_docker_goals_recover_without_stale_child_writes(tmp_path):
    """Restarted child plans cannot use snapshots revised by sibling merges."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    principal = local_sparks_principal()
    dispatched = []
    goals, first_runner = coordinator(
        path, neural=[snapshot("ops")], executions=dispatched,
    )
    ledger = GoalEvidenceLedger(path)
    first = create_user_goal(
        goals, ledger, principal=principal,
        ref="message:g7a-first-docker", title="Investigate Docker failures",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner confirms the diagnosis.",
        ),
    )
    assert first_runner.run_due(now=NOW + timedelta(seconds=1)) == 1
    assert dispatched == ["portainer"]
    assert goals.store.get(
        first.id, principal_id=first.scope_principal_id,
        audience=first.scope_audience,
    ).status is GoalStatus.ACTIVE

    # Existing diagnostic children persist across restart, while a second
    # distinct user request can decompose into overlapping child titles.
    reopened, second_runner = coordinator(
        path, neural=[snapshot("ops")], executions=dispatched,
    )
    followup = create_user_goal(
        reopened, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-docker-followup",
        title="Investigate Docker container connectivity after reboot",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner verifies the follow-up.",
        ),
    )
    assert second_runner.run_due(now=NOW + timedelta(minutes=2)) >= 1
    with sqlite3.connect(path) as db:
        first_count = db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (first.id,),
        ).fetchone()[0]
        second_count = db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (followup.id,),
        ).fetchone()[0]
        repeated = db.execute(
            "SELECT COUNT(*) FROM (SELECT attempt_id FROM goal_action_attempt "
            "GROUP BY attempt_id HAVING COUNT(*)>1)"
        ).fetchone()[0]
    assert first_count == 1
    assert second_count <= 1
    assert repeated == 0


def test_g7a_dispatch_receipt_is_atomically_linked_to_reserved_intent(tmp_path):
    """Only a recorded outcome may release the unresolved dispatch fence."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    goals, production = coordinator(path, neural=[snapshot("ops")])
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-journal-success",
        title="Investigate Docker diagnostics",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner reviews result.",
        ),
    )
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 1
    assert production.unresolved_dispatches(goal.id) == ()
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT d.status,d.evidence_ref,a.evidence_ref "
            "FROM goal_action_dispatch d JOIN goal_action_attempt a "
            "ON a.attempt_id=d.dispatch_id WHERE d.goal_id=?",
            (goal.id,),
        ).fetchone() == db.execute(
            "SELECT 'recorded',evidence_ref,evidence_ref "
            "FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone()
    # Recreating GOALS must preserve the journal; an acknowledged outcome
    # is never mistaken for an interrupted, unacknowledged dispatch.
    _, restarted = coordinator(path, neural=[snapshot("ops")])
    assert restarted.unresolved_dispatches(goal.id) == ()


def test_g7a_crash_before_receipt_leaves_no_false_success_or_replay(
    tmp_path, monkeypatch
):
    """A crash between capability dispatch and receipt makes the effect UNKNOWN."""
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    calls = []
    goals, production = coordinator(
        path, neural=[snapshot("ops")], executions=calls,
    )
    production.planner.gateway.capability_system.register(
        Capability("service.inspect", "Read local service evidence."),
        lambda _request: calls.append("service") or {"status": "running"},
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-unknown-service-effect",
        title="Inspect local service status",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner reviews service status.",
        ),
    )
    def crash_after_dispatch(proposal):
        calls.append("started")
        raise SystemExit("simulated Core crash after intent reservation")

    monkeypatch.setattr(production.planner.gateway, "execute", crash_after_dispatch)
    with pytest.raises(SystemExit, match="Core crash"):
        production.run_due(now=NOW + timedelta(seconds=1))
    unresolved = production.unresolved_dispatches(goal.id)
    assert len(unresolved) == 1
    assert unresolved[0][1] == "service.inspect"
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)
        assert db.execute(
            "SELECT status FROM goal_action_dispatch WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == ("unresolved",)

    # An independent Core process using the same canonical DB must not
    # replay the operation, even when the ordinary retry window has elapsed.
    _, restarted = coordinator(
        path, neural=[snapshot("ops")], executions=calls,
    )
    restarted.planner.gateway.capability_system.register(
        Capability("service.inspect", "Read local service evidence."),
        lambda _request: calls.append("replayed") or {"status": "running"},
    )
    assert restarted.run_due(now=NOW + timedelta(hours=2)) == 0
    assert "replayed" not in calls
    assert restarted.unresolved_dispatches(goal.id) == unresolved
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    "failure_kind",
    [CapabilityResultKind.FAILED, CapabilityResultKind.UNAVAILABLE],
)
def test_g7a_uncertain_gateway_result_never_auto_replays(
    tmp_path, monkeypatch, failure_kind
):
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    dispatches = []
    goals, production = coordinator(path, neural=[snapshot("ops")])
    production.planner.gateway.capability_system.register(
        Capability("service.inspect", "Read exact service status."),
        lambda _request: {"status": "running"},
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref=f"message:g7a-uncertain-{failure_kind.value}",
        title="Inspect local service status",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner verifies service state.",
        ),
    )

    def uncertain(proposal):
        dispatches.append(proposal.capability_name)
        return CapabilityResult(
            capability=proposal.capability_name, kind=failure_kind,
            error="upstream response cannot prove any external effect",
        )

    monkeypatch.setattr(production.planner.gateway, "execute", uncertain)
    assert production.run_due(now=NOW + timedelta(seconds=1)) == 1
    assert dispatches == ["service.inspect"]
    pending = production.unresolved_dispatches(goal.id)
    assert len(pending) == 1
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT result_kind FROM goal_action_attempt WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == (failure_kind.value,)
        assert db.execute(
            "SELECT status FROM goal_action_dispatch WHERE goal_id=?",
            (goal.id,),
        ).fetchone() == ("unresolved",)

    # A failed or unavailable gateway result is not independent evidence
    # of no effect, so even a due schedule cannot issue a second attempt.
    _, restarted = coordinator(path, neural=[snapshot("ops")])
    restarted.planner.gateway.capability_system.register(
        Capability("service.inspect", "Read exact service status."),
        lambda _request: {"status": "running"},
    )
    monkeypatch.setattr(restarted.planner.gateway, "execute", uncertain)
    # Past the six-hour scheduled retry, not just before it is eligible.
    assert restarted.run_due(now=NOW + timedelta(hours=7)) == 0
    assert dispatches == ["service.inspect"]
    assert restarted.unresolved_dispatches(goal.id) == pending



def _g7a_unresolved_reconciliation_fixture(
    path, *, reconciliation_authorizer=None, independent_outcome_verifier=None,
    reconciliation_approval_verifier=None,
):
    bootstrap_canonical_sqlite(path)
    goals, production = coordinator(
        path, neural=[snapshot("ops")],
        reconciliation_authorizer=reconciliation_authorizer,
        independent_outcome_verifier=independent_outcome_verifier,
        reconciliation_approval_verifier=reconciliation_approval_verifier,
    )
    principal = local_sparks_principal()
    goal = create_user_goal(
        goals, GoalEvidenceLedger(path), principal=principal,
        ref="message:g7a-reconcile-goal", title="Inspect Docker health",
        completion=GoalCompletionCondition(
            CompletionKind.USER_DEFINED, "Owner reviews inspection.",
        ),
    )
    dispatch_id = "goal-action:g7a-review-case"
    assert production._reserve_dispatch(
        dispatch_id=dispatch_id, goal=goal,
        capability="portainer.summary", now=NOW,
    )
    return goal, production, principal, dispatch_id


def _g7a_independent_outcome(path, goal, principal, dispatch_id, *,
                            source="ops-maintenance", action_id=None,
                            audience=None, successful=True):
    return GoalEvidenceLedger(path).record(
        evidence_ref="goal-evidence:external-verification-" + source,
        kind="operation_receipt", observed_at=NOW + timedelta(minutes=1),
        source=source, successful=successful,
        goal_id=goal.id,
        action_id=dispatch_id if action_id is None else action_id,
        assertion="portainer.summary", principal_id=principal.principal_id,
        audience=audience_scope(principal) if audience is None else audience,
    )


def test_g7a_reconciliation_requires_trusted_authority_and_effect_verifier(tmp_path):
    path = tmp_path / "sofia.db"
    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(path)
    evidence = _g7a_independent_outcome(path, goal, principal, dispatch_id)
    with pytest.raises(PermissionError, match="trusted reconciliation"):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id,
            principal=principal, evidence_ref=evidence.evidence_ref,
            now=NOW + timedelta(minutes=2),
        )
    assert production.unresolved_dispatches(goal.id) == (
        (dispatch_id, "portainer.summary"),
    )

    _, denied = coordinator(
        path, neural=[snapshot("ops")],
        reconciliation_authorizer=lambda *_: False,
        independent_outcome_verifier=lambda *_: True,
    )
    with pytest.raises(PermissionError, match="not independently authorized"):
        denied.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=evidence.evidence_ref, now=NOW + timedelta(minutes=2),
        )
    _, unverified = coordinator(
        path, neural=[snapshot("ops")],
        reconciliation_authorizer=lambda *_: True,
        independent_outcome_verifier=lambda *_: False,
    )
    with pytest.raises(ValueError, match="effect verification rejected"):
        unverified.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=evidence.evidence_ref, now=NOW + timedelta(minutes=2),
        )
    assert unverified.reconciliations(goal.id) == ()
    assert unverified.unresolved_dispatches(goal.id) == (
        (dispatch_id, "portainer.summary"),
    )


@pytest.mark.parametrize("bad_field", ["self_receipt", "wrong_action", "wrong_audience", "future"])
def test_g7a_reconciliation_rejects_self_attested_or_wrong_scoped_evidence(
    tmp_path, bad_field
):
    path = tmp_path / "sofia.db"
    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path, reconciliation_authorizer=lambda *_: True,
        independent_outcome_verifier=lambda *_: True,
    )
    data = dict(
        kind="operation_receipt", observed_at=NOW + timedelta(minutes=1),
        source="ops-maintenance", successful=True, goal_id=goal.id,
        action_id=dispatch_id, assertion="portainer.summary",
        principal_id=principal.principal_id, audience=audience_scope(principal),
    )
    if bad_field == "self_receipt":
        data["source"] = "goal-action"
    if bad_field == "wrong_action":
        data["action_id"] = "goal-action:another-dispatch"
    if bad_field == "wrong_audience":
        data["audience"] = "private:other-owner"
    if bad_field == "future":
        data["observed_at"] = NOW + timedelta(days=2)
    receipt = GoalEvidenceLedger(path).record(**data)
    with pytest.raises(ValueError, match="independent outcome must match"):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=receipt.evidence_ref,
            now=NOW + timedelta(minutes=2),
        )
    assert production.reconciliations(goal.id) == ()
    assert len(production.unresolved_dispatches(goal.id)) == 1


@pytest.mark.parametrize("successful,expected", [
    (True, "effect_verified"), (False, "no_effect_verified"),
])
def test_g7a_independent_reconciliation_is_durable_and_never_auto_replays(
    tmp_path, successful, expected
):
    path = tmp_path / "sofia.db"
    checks = []
    def authorize(principal, goal, dispatch, evidence):
        checks.append(("authorization", dispatch, evidence.evidence_ref))
        return principal.principal_id == goal.owner_principal_id
    def verify(dispatch, evidence):
        checks.append(("effect", dispatch, evidence.evidence_ref))
        return evidence.source == "ops-maintenance"

    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path, reconciliation_authorizer=authorize,
        independent_outcome_verifier=verify,
    )
    evidence = _g7a_independent_outcome(
        path, goal, principal, dispatch_id, successful=successful,
    )
    assert production.reconcile_dispatch(
        goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
        evidence_ref=evidence.evidence_ref, now=NOW + timedelta(minutes=2),
    ) == expected
    assert [item[0] for item in checks] == ["authorization", "effect"]
    assert production.unresolved_dispatches(goal.id) == ()
    assert production.reconciliations(goal.id) == (
        (dispatch_id, expected, evidence.evidence_ref),
    )
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT status,evidence_ref FROM goal_action_dispatch WHERE dispatch_id=?",
            (dispatch_id,),
        ).fetchone() == ("recorded", evidence.evidence_ref)

    # Reconciliation is an immutable audit, not permission to replay the goal.
    _, restarted = coordinator(path, neural=[snapshot("ops")])
    assert restarted.run_due(now=NOW + timedelta(hours=8)) == 0
    assert restarted.reconciliations(goal.id) == (
        (dispatch_id, expected, evidence.evidence_ref),
    )
    with pytest.raises(ValueError, match="unresolved exact"):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=evidence.evidence_ref, now=NOW + timedelta(hours=9),
        )



def _g7a_owner_signed_reconciliation_approval(
    path, goal, dispatch_id, evidence, *, capability="portainer.summary",
    now=NOW,
):
    verifier = ExecutionApprovalVerifier(path)
    params = goal_reconciliation_approval_parameters(
        goal=goal, dispatch_id=dispatch_id,
        capability=capability, evidence=evidence,
    )
    approval = ExecutionApproval(
        approval_id="g7a-reconciliation-approval",
        capability="goals.dispatch.reconcile",
        request_fingerprint=execution_fingerprint(
            "goals.dispatch.reconcile", params,
        ),
        approved_by="Sparks",
        approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(verifier, approval)
    return verifier, approval.approval_id


def test_g7a_real_safe_webauthn_approval_consumed_atomically_on_reconciliation(tmp_path):
    path = tmp_path / "sofia.db"
    verifier = ExecutionApprovalVerifier(bootstrap_canonical_sqlite(path))
    goal, _, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path, reconciliation_approval_verifier=verifier,
        independent_outcome_verifier=lambda _, evidence: (
            evidence.source == "ops-maintenance"
        ),
    )
    evidence = _g7a_independent_outcome(path, goal, principal, dispatch_id)
    verifier, approval_id = _g7a_owner_signed_reconciliation_approval(
        path, goal, dispatch_id, evidence,
    )
    _, production = coordinator(
        path, neural=[snapshot("ops")],
        reconciliation_approval_verifier=verifier,
        independent_outcome_verifier=lambda _, evidence: (
            evidence.source == "ops-maintenance"
        ),
    )
    # Cryptographic SAFE verification, owner proof, request fingerprint,
    # one-use approval consumption and journal reconciliation share a writer
    # transaction. No bypass via submitted owner labels.
    assert production.reconcile_dispatch(
        goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
        evidence_ref=evidence.evidence_ref,
        now=NOW + timedelta(minutes=2), approval_id=approval_id,
    ) == "effect_verified"
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?",
            (approval_id,),
        ).fetchone()[0] is not None
        assert db.execute(
            "SELECT status,evidence_ref FROM goal_action_dispatch "
            "WHERE dispatch_id=?",
            (dispatch_id,),
        ).fetchone() == ("recorded", evidence.evidence_ref)
    assert production.reconciliations(goal.id) == (
        (dispatch_id, "effect_verified", evidence.evidence_ref),
    )


def test_g7a_safe_approval_rejects_wrong_fingerprint_without_consumption(tmp_path):
    path = tmp_path / "sofia.db"
    verifier = ExecutionApprovalVerifier(bootstrap_canonical_sqlite(path))
    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path, reconciliation_approval_verifier=verifier,
        independent_outcome_verifier=lambda *_: True,
    )
    evidence = _g7a_independent_outcome(path, goal, principal, dispatch_id)
    verifier, approval_id = _g7a_owner_signed_reconciliation_approval(
        path, goal, dispatch_id, evidence, capability="system.inspect",
    )
    with pytest.raises(PermissionError, match="parameters do not match"):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=evidence.evidence_ref,
            now=NOW + timedelta(minutes=2), approval_id=approval_id,
        )
    assert production.unresolved_dispatches(goal.id) == (
        (dispatch_id, "portainer.summary"),
    )
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?",
            (approval_id,),
        ).fetchone() == (None,)


def test_g7a_safe_approval_and_reconciliation_rollback_together_on_conflict(tmp_path):
    path = tmp_path / "sofia.db"
    verifier = ExecutionApprovalVerifier(bootstrap_canonical_sqlite(path))
    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path, reconciliation_approval_verifier=verifier,
        independent_outcome_verifier=lambda *_: True,
    )
    evidence = _g7a_independent_outcome(path, goal, principal, dispatch_id)
    verifier, approval_id = _g7a_owner_signed_reconciliation_approval(
        path, goal, dispatch_id, evidence,
    )
    # A different existing audit entry already claims the evidence ref.
    # The uniqueness conflict must roll back owner SAFE consumption as well
    # as the attempted dispatch update, not half-commit the action.
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO goal_action_reconciliation("
            "dispatch_id,goal_id,capability,evidence_ref,outcome,"
            "reviewer_principal_id,reviewed_at) VALUES(?,?,?,?,?,?,?)",
            (
                "goal-action:conflicting-old-proof", goal.id,
                "portainer.summary", evidence.evidence_ref,
                "effect_verified", principal.principal_id,
                NOW.isoformat(),
            ),
        )
    with pytest.raises(sqlite3.IntegrityError):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=evidence.evidence_ref,
            now=NOW + timedelta(minutes=2), approval_id=approval_id,
        )
    assert production.unresolved_dispatches(goal.id) == (
        (dispatch_id, "portainer.summary"),
    )
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?",
            (approval_id,),
        ).fetchone() == (None,)
        db.execute(
            "DELETE FROM goal_action_reconciliation "
            "WHERE dispatch_id='goal-action:conflicting-old-proof'"
        )
    assert production.reconcile_dispatch(
        goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
        evidence_ref=evidence.evidence_ref,
        now=NOW + timedelta(minutes=2), approval_id=approval_id,
    ) == "effect_verified"


def test_g7a_production_safe_verifier_still_rejects_unverified_host_outcome(tmp_path):
    path = tmp_path / "sofia.db"
    verifier = ExecutionApprovalVerifier(bootstrap_canonical_sqlite(path))
    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path, reconciliation_approval_verifier=verifier,
        independent_outcome_verifier=lambda *_: False,
    )
    evidence = _g7a_independent_outcome(path, goal, principal, dispatch_id)
    verifier, approval_id = _g7a_owner_signed_reconciliation_approval(
        path, goal, dispatch_id, evidence,
    )
    with pytest.raises(ValueError, match="effect verification rejected"):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id, principal=principal,
            evidence_ref=evidence.evidence_ref,
            now=NOW + timedelta(minutes=2), approval_id=approval_id,
        )
    with sqlite3.connect(path) as db:
        assert db.execute(
            "SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?",
            (approval_id,),
        ).fetchone() == (None,)
    assert production.unresolved_dispatches(goal.id)


def test_g7a_external_verifier_exception_keeps_dispatch_unknown(tmp_path):
    """A disconnected witness cannot be treated as a successful review."""
    path = tmp_path / "sofia.db"

    def disconnected(_dispatch, _evidence):
        raise OSError("host observer is unreachable")

    goal, production, principal, dispatch_id = _g7a_unresolved_reconciliation_fixture(
        path,
        reconciliation_authorizer=lambda *_: True,
        independent_outcome_verifier=disconnected,
    )
    receipt = _g7a_independent_outcome(path, goal, principal, dispatch_id)
    with pytest.raises(OSError, match="unreachable"):
        production.reconcile_dispatch(
            goal_id=goal.id, dispatch_id=dispatch_id,
            principal=principal, evidence_ref=receipt.evidence_ref,
            now=NOW + timedelta(minutes=2),
        )
    assert production.unresolved_dispatches(goal.id) == (
        (dispatch_id, "portainer.summary"),
    )
    assert production.reconciliations(goal.id) == ()
    # Losing the verifier cannot authorize another attempt after restart.
    _, restarted = coordinator(path, neural=[snapshot("ops")])
    assert restarted.run_due(now=NOW + timedelta(hours=8)) == 0
    assert restarted.unresolved_dispatches(goal.id) == (
        (dispatch_id, "portainer.summary"),
    )


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

    grant_with_signed_owner(PermissionStore(path), 
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
