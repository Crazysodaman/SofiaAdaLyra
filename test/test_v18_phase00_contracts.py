"""CA-003/004/005/006 executable ownership and trace contracts."""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from sofia.application.decision_persistence import inspect_turn_persistence
from sofia.application.decision_trace import project_companion_decision
from sofia.application.event_contracts import (
    CanonicalEventOwner,
    ContractErrorState,
    EVENT_FIELD_OWNERS,
    EventOwnershipProjection,
    project_matrix_event,
    project_act_delivery,
    project_run_job,
)
from sofia.act.delivery import BoundMessage, DeliveryOutcome, SendResult
from sofia.cognition.matrix.model import (
    AuthorityDecision,
    AuthorityPlan,
    CognitionExecutionStep,
    CognitionExecutionTrace,
    EvidenceMatrix,
    EvidenceRecord,
    EvidenceState,
    ResponseValidation,
    ResponseValidationDisposition,
    ToolExposurePlan,
)
from sofia.neuro.model import NeuralActivation, NeuroStateSnapshot
from sofia.run.work import WorkJob, WorkStatus
from test.test_v18_decision_persistence import NOW, _fixture


pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_verify]


def test_event_contract_covers_required_canonical_fields_and_has_no_authority():
    required = {
        "event_id", "source_id", "subject_id", "principal_id", "audience_id",
        "observed_at", "expires_at", "confidence", "evidence_refs", "action_id",
        "goal_id", "project_id", "consent_classification",
        "delivery_receipt_id", "resource_refs", "error_state",
    }
    assert required == set(EVENT_FIELD_OWNERS)
    assert all(EVENT_FIELD_OWNERS[field] for field in required)
    event = EventOwnershipProjection(
        schema_version=1, event_id="event:one",
        owner=CanonicalEventOwner.RUN, source_id="job:one",
        subject_id="host:venus", principal_id="principal:sparks",
        audience_id="private:sparks", observed_at=NOW,
        evidence_refs=("receipt:one",), action_id="action:one",
        resource_refs=("host:venus",), error_state=ContractErrorState.NONE,
    )
    assert not event.can_authorize


def test_event_contract_rejects_partial_scope_bad_time_and_duplicate_evidence():
    base = dict(
        schema_version=1, event_id="event:one",
        owner=CanonicalEventOwner.MATRIX, source_id="message:one",
        subject_id="session:one", principal_id=None, audience_id=None,
        observed_at=NOW,
    )
    with pytest.raises(ValueError, match="present together"):
        EventOwnershipProjection(**{**base, "principal_id": "principal:one"})
    with pytest.raises(ValueError, match="timezone-aware"):
        EventOwnershipProjection(
            **base, expires_at=datetime(2026, 1, 1),
        )
    with pytest.raises(ValueError, match="duplicates"):
        EventOwnershipProjection(
            **base, evidence_refs=("evidence:one", "evidence:one"),
        )


def test_canonical_event_rejects_untyped_and_backdated_expiry():
    base = dict(
        schema_version=1, event_id="event:one",
        owner=CanonicalEventOwner.MATRIX, source_id="message:one",
        subject_id="session:one", principal_id=None, audience_id=None,
        observed_at=NOW,
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        EventOwnershipProjection(**{**base, "observed_at": "not a datetime"})
    with pytest.raises(ValueError, match="timezone-aware"):
        EventOwnershipProjection(**base, expires_at="a string")
    with pytest.raises(ValueError, match="cannot precede"):
        EventOwnershipProjection(**base, expires_at=NOW - timedelta(seconds=1))
    assert EventOwnershipProjection(
        **base, expires_at=NOW,
    ).expires_at == NOW



def test_matrix_adapter_requires_independent_scope_binding(tmp_path):
    state, matrix = _fixture(tmp_path)
    verified = inspect_turn_persistence(state, matrix_trace=matrix)
    # The audience comes from the independent SOCIAL binding, never by
    # guessing from the desktop channel.
    projection = project_matrix_event(matrix, persistence=verified)
    assert projection.principal_id == "principal:one"
    assert projection.audience_id == "private:one"
    assert projection.event_id == matrix.envelope.message_id
    assert projection.error_state is ContractErrorState.UNCERTAIN
    assert not projection.can_authorize


def test_companion_trace_joins_only_exact_source_owned_turn_inputs(tmp_path):
    state, matrix = _fixture(tmp_path)
    matrix = replace(
        matrix,
        evidence=EvidenceMatrix(records=(
            EvidenceRecord(
                "conversation-memory", EvidenceState.AVAILABLE,
                "conversation-retrieval:message-older",
            ),
            EvidenceRecord("goal", EvidenceState.AVAILABLE, "goal:inspect-docker"),
            EvidenceRecord("life", EvidenceState.AVAILABLE, "life:project:diagnostics"),
        )),
        authority=AuthorityPlan(
            AuthorityDecision.REQUIRES_APPROVAL,
            requested_action="restart docker", reason="mutation requires approval",
        ),
        tool_exposure=ToolExposurePlan(
            capabilities=("ops.service.inspect",), reason="read-only inspection",
        ),
        cognition_execution=CognitionExecutionTrace(
            serial=1, actual_route="verify",
            steps=(
                CognitionExecutionStep("primary", "model-a", "venus", True),
                CognitionExecutionStep("secondary", "model-b", "artemis", True),
            ), verification_passes=1,
        ),
        response_validation=ResponseValidation(
            ResponseValidationDisposition.PASS, (),
        ),
    )
    snapshot = NeuroStateSnapshot(
        generated_at=matrix.created_at,
        focus=NeuralActivation(
            "goal:inspect-docker", "goal:inspect-docker", "goal", 0.9, 0.4, NOW,
        ),
        secondary=(NeuralActivation(
            "life:project:diagnostics", "life:project:diagnostics", "life",
            0.7, 0.2, NOW,
        ),),
        active_signal_count=2,
    )
    trace = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=snapshot,
        neuro_turn_snapshot=snapshot,
        canonical_persistence=inspect_turn_persistence(state, matrix_trace=matrix),
    )
    assert trace is not None and trace.schema_version == 2
    assert trace.source_event is not None and not trace.source_event.can_authorize
    assert trace.neuro_winner is not None and trace.neuro_winner.selected
    assert len(trace.rejected_alternatives) == 1
    assert trace.eligible_memory_refs == ("conversation-retrieval:message-older",)
    assert trace.referenced_goal_refs == ("goal:inspect-docker",)
    assert trace.referenced_activity_refs == ("life:project:diagnostics",)
    assert trace.execution_decision is not None
    assert trace.execution_decision.external_effect_claimed is False
    assert trace.execution_decision.exposed_capabilities == ("ops.service.inspect",)
    assert len(trace.execution_decision.model_steps) == 2
    assert trace.outcomes[0].kind == "response_validation"
    assert not trace.outcomes[0].independently_verified


def test_restart_reprojection_preserves_canonical_data_not_ephemeral_neuro(tmp_path):
    state, matrix = _fixture(tmp_path)
    proof = inspect_turn_persistence(state, matrix_trace=matrix)
    before = project_companion_decision(
        matrix_trace=matrix,
        neuro_snapshot=NeuroStateSnapshot(generated_at=NOW, focus=None),
        neuro_turn_snapshot=NeuroStateSnapshot(generated_at=NOW, focus=None),
        canonical_persistence=proof,
    )
    after = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None,
        neuro_turn_snapshot=None,
        canonical_persistence=inspect_turn_persistence(state, matrix_trace=matrix),
    )
    assert before is not None and after is not None
    assert before.source_event == after.source_event
    assert before.referenced_evidence == after.referenced_evidence
    assert before.neuro_turn_correlated
    assert not after.neuro_turn_correlated
    assert after.neuro_winner is None


def test_run_and_act_adapters_preserve_error_and_receipt_semantics():
    run = project_run_job(WorkJob(
        job_id="job:one", kind="ops.inspect", fingerprint="f" * 64,
        payload={"project_id": "project:one"}, priority=50,
        resource_cost=2, risk="read_only", completion_condition="receipt",
        status=WorkStatus.UNCERTAIN, created_at=NOW, updated_at=NOW,
        deadline=NOW + timedelta(minutes=5), attempt_count=1,
    ))
    assert run.action_id == "job:one"
    assert run.project_id == "project:one"
    assert run.error_state is ContractErrorState.UNCERTAIN
    assert not run.can_authorize

    message = BoundMessage(
        "message:one", "goal:one", "evidence:one", "not projected",
        NOW, "recipient:one", "discord", "channel:one",
        NOW + timedelta(minutes=5),
    )
    unknown = project_act_delivery(
        message, send_result=SendResult(DeliveryOutcome.OUTCOME_UNKNOWN),
    )
    assert unknown.delivery_receipt_id is None
    assert unknown.error_state is ContractErrorState.UNCERTAIN
    delivered = project_act_delivery(
        message,
        send_result=SendResult(DeliveryOutcome.DELIVERED, "discord-ack:one"),
    )
    assert delivered.delivery_receipt_id == "discord-ack:one"
    assert delivered.error_state is ContractErrorState.NONE


def test_companion_trace_accepts_only_typed_selected_sources_and_outcomes(tmp_path):
    state, matrix = _fixture(tmp_path)
    matrix = replace(
        matrix, evidence=EvidenceMatrix(records=(
            EvidenceRecord("goal", EvidenceState.AVAILABLE, "goal:one"),
            EvidenceRecord("act", EvidenceState.AVAILABLE, "message:one"),
        )),
    )
    selected = EventOwnershipProjection(
        schema_version=1, event_id="goal-event:one",
        owner=CanonicalEventOwner.GOALS, source_id="goal-event:one",
        subject_id="goal:one", principal_id=None, audience_id=None,
        observed_at=NOW, goal_id="goal:one",
    )
    delivery = project_act_delivery(
        BoundMessage(
            "message:one", "goal:one", "evidence:one", "not projected",
            NOW, "recipient:one", "discord", "channel:one",
            NOW + timedelta(minutes=5),
        ),
        send_result=SendResult(DeliveryOutcome.DELIVERED, "discord-ack:one"),
    )
    trace = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None,
        selected_goal_event=selected, outcome_events=(delivery,),
    )
    assert trace is not None and trace.goal_id == "goal:one"
    assert trace.outcomes[-1].kind == "act_event"
    assert not trace.outcomes[-1].independently_verified
    assert trace.outcomes[-1].source_ref == "discord-ack:one"

    foreign = replace(
        selected, principal_id="principal:other", audience_id="private:other",
    )
    with pytest.raises(PermissionError, match="crosses"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            selected_goal_event=foreign,
        )


def test_trace_refuses_unrelated_goal_and_act_receipts(tmp_path):
    state, matrix = _fixture(tmp_path)
    foreign_goal = EventOwnershipProjection(
        schema_version=1, event_id="goal-event:unrelated",
        owner=CanonicalEventOwner.GOALS, source_id="goal-event:unrelated",
        subject_id="goal:unrelated", principal_id=None, audience_id=None,
        observed_at=NOW, goal_id="goal:unrelated",
    )
    foreign_act = project_act_delivery(
        BoundMessage(
            "message:unrelated", "goal:unrelated", "evidence:one",
            "not projected", NOW, "recipient:one", "discord", "channel:one",
            NOW + timedelta(minutes=5),
        ),
        send_result=SendResult(DeliveryOutcome.DELIVERED, "ack:unrelated"),
    )
    with pytest.raises(ValueError, match="same-turn source reference"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            selected_goal_event=foreign_goal,
        )
    with pytest.raises(ValueError, match="same-turn source reference"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            outcome_events=(foreign_act,),
        )


def test_unverified_act_projection_cannot_claim_external_effect(tmp_path):
    state, matrix = _fixture(tmp_path)
    matrix = replace(
        matrix, evidence=EvidenceMatrix(records=(
            EvidenceRecord("act", EvidenceState.AVAILABLE, "message:one"),
        )),
    )
    forged = EventOwnershipProjection(
        schema_version=1, event_id="message:one",
        owner=CanonicalEventOwner.ACT, source_id="message:one",
        subject_id="recipient:one", principal_id=None, audience_id=None,
        observed_at=NOW, action_id="message:one",
        delivery_receipt_id="ack:unverified",
        error_state=ContractErrorState.NONE,
    )
    trace = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None, outcome_events=(forged,),
    )
    assert trace is not None
    assert trace.outcomes[-1].source_ref == "ack:unverified"
    assert trace.outcomes[-1].independently_verified is False
    assert trace.objective_verified is False



@pytest.mark.parametrize("state", [
    EvidenceState.STALE,
    EvidenceState.UNKNOWN,
    EvidenceState.MISSING,
])
def test_unavailable_matrix_evidence_cannot_link_goal_or_eligible_memory(tmp_path, state):
    _state_path, matrix = _fixture(tmp_path)
    matrix = replace(
        matrix, evidence=EvidenceMatrix(records=(
            EvidenceRecord("goal", state, "goal:one"),
            EvidenceRecord("memory", state, "memory:one"),
        )),
    )
    event = EventOwnershipProjection(
        schema_version=1, event_id="goal:event",
        owner=CanonicalEventOwner.GOALS, source_id="goal:event",
        subject_id="goal:one", principal_id=None, audience_id=None,
        observed_at=NOW, goal_id="goal:one",
    )
    with pytest.raises(ValueError, match="same-turn source reference"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            selected_goal_event=event,
        )
    diagnostic = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None,
    )
    assert diagnostic is not None
    assert diagnostic.referenced_evidence == ("goal:one", "memory:one")
    assert diagnostic.eligible_memory_refs == ()
    assert diagnostic.referenced_goal_refs == ()
    assert diagnostic.goal_id is None
    assert not diagnostic.objective_verified


@pytest.mark.parametrize(("failure", "expected"), [
    ("expired", "expired"),
    ("revoked", "not an eligible"),
    ("failed", "not an eligible"),
    ("future", "postdate"),
])
def test_ca005_ca006_unusable_goal_event_cannot_become_selected_provenance(
    tmp_path, failure, expected,
):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("goal", EvidenceState.AVAILABLE, "goal:bounded"),
    )))
    event = EventOwnershipProjection(
        schema_version=1,
        event_id="goal:bounded",
        owner=CanonicalEventOwner.GOALS,
        source_id="goal:bounded",
        subject_id="goal:bounded",
        principal_id=None,
        audience_id=None,
        observed_at=(
            matrix.created_at + timedelta(seconds=1)
            if failure == "future" else NOW
        ),
        expires_at=(
            NOW + timedelta(milliseconds=1)
            if failure == "expired" else None
        ),
        error_state={
            "expired": ContractErrorState.NONE,
            "future": ContractErrorState.NONE,
            "revoked": ContractErrorState.REVOKED,
            "failed": ContractErrorState.FAILED,
        }[failure],
    )
    with pytest.raises(ValueError, match=expected):
        project_companion_decision(
            matrix_trace=matrix,
            neuro_snapshot=None,
            selected_goal_event=event,
        )


@pytest.mark.parametrize(("kind", "state", "offset", "expires"), [
    ("revoked", ContractErrorState.REVOKED, 0, None),
    ("failed", ContractErrorState.FAILED, 0, None),
    ("uncertain", ContractErrorState.UNCERTAIN, 0, None),
    ("future", ContractErrorState.NONE, 60, None),
    ("expired", ContractErrorState.NONE, 0, 1),
])
def test_ca006_outcome_events_cannot_certify_ineligible_sources(
    tmp_path, kind, state, offset, expires,
):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("effect", EvidenceState.AVAILABLE, "act:receipt-one"),
    )))
    event = EventOwnershipProjection(
        schema_version=1,
        event_id="act:receipt-one",
        owner=CanonicalEventOwner.ACT,
        source_id="act:receipt-one",
        subject_id="session:one",
        principal_id=None,
        audience_id=None,
        observed_at=NOW + timedelta(seconds=offset),
        expires_at=(NOW + timedelta(milliseconds=expires) if expires else None),
        error_state=state,
    )
    with pytest.raises(ValueError, match="postdates|expired|not an eligible"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            outcome_events=(event,),
        )


def test_ca006_rejects_duplicate_canonical_outcome_receipt(tmp_path):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("effect", EvidenceState.AVAILABLE, "act:duplicate"),
    )))
    event = EventOwnershipProjection(
        schema_version=1,
        event_id="act:duplicate",
        owner=CanonicalEventOwner.ACT,
        source_id="act:duplicate",
        subject_id="session:one",
        principal_id=None,
        audience_id=None,
        observed_at=NOW,
    )
    with pytest.raises(ValueError, match="duplicate canonical decision event identity"):
        project_companion_decision(
            matrix_trace=matrix,
            neuro_snapshot=None,
            outcome_events=(event, event),
        )


def test_ca006_keeps_single_legitimate_outcome_receipt(tmp_path):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("effect", EvidenceState.AVAILABLE, "act:unique"),
    )))
    event = EventOwnershipProjection(
        schema_version=1,
        event_id="act:unique",
        owner=CanonicalEventOwner.ACT,
        source_id="act:unique",
        subject_id="session:one",
        principal_id=None,
        audience_id=None,
        observed_at=NOW,
    )
    result = project_companion_decision(
        matrix_trace=matrix,
        neuro_snapshot=None,
        outcome_events=(event,),
    )
    assert len(result.outcomes) == 1
    assert result.outcomes[0].source_ref == "act:unique"
    assert result.outcomes[0].independently_verified is False


@pytest.mark.parametrize("owner", [
    CanonicalEventOwner.MATRIX,
    CanonicalEventOwner.MEMORY,
    CanonicalEventOwner.GOALS,
    CanonicalEventOwner.LIFE,
    CanonicalEventOwner.NEURO,
    CanonicalEventOwner.SAFE,
])
def test_ca006_non_effect_owner_cannot_masquerade_as_outcome(tmp_path, owner):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("record", EvidenceState.AVAILABLE, "source:one"),
    )))
    event = EventOwnershipProjection(
        schema_version=1,
        event_id="source:one",
        owner=owner,
        source_id="source:one",
        subject_id=None,
        principal_id=None,
        audience_id=None,
        observed_at=NOW,
    )
    with pytest.raises(ValueError, match="RUN or ACT"):
        project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None,
            outcome_events=(event,),
        )


def test_ca006_canonical_run_owner_is_allowed_without_claiming_verification(tmp_path):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("run", EvidenceState.AVAILABLE, "run:one"),
    )))
    event = EventOwnershipProjection(
        schema_version=1,
        event_id="run:one",
        owner=CanonicalEventOwner.RUN,
        source_id="run:one",
        subject_id=None,
        principal_id=None,
        audience_id=None,
        observed_at=NOW,
    )
    projection = project_companion_decision(
        matrix_trace=matrix, neuro_snapshot=None,
        outcome_events=(event,),
    )
    assert projection.outcomes[-1].kind == "run_event"
    assert projection.outcomes[-1].independently_verified is False


@pytest.mark.parametrize("shared_receipt", [True, False])
def test_ca006_delivery_receipt_identity_is_not_double_counted(
    tmp_path, shared_receipt,
):
    _, matrix = _fixture(tmp_path)
    matrix = replace(matrix, evidence=EvidenceMatrix(records=(
        EvidenceRecord("act", EvidenceState.AVAILABLE, "act:first"),
        EvidenceRecord("act", EvidenceState.AVAILABLE, "act:second"),
    )))
    events = tuple(EventOwnershipProjection(
        schema_version=1, event_id=f"act:{label}",
        owner=CanonicalEventOwner.ACT, source_id=f"act:{label}",
        subject_id="session:one", principal_id=None, audience_id=None,
        observed_at=NOW,
        delivery_receipt_id=(
            "receipt:shared" if shared_receipt else f"receipt:{label}"
        ),
    ) for label in ("first", "second"))
    if shared_receipt:
        with pytest.raises(ValueError, match="duplicate canonical delivery receipt"):
            project_companion_decision(
                matrix_trace=matrix, neuro_snapshot=None, outcome_events=events,
            )
    else:
        projected = project_companion_decision(
            matrix_trace=matrix, neuro_snapshot=None, outcome_events=events,
        )
        assert len(projected.outcomes) == 2
        assert all(not event.independently_verified for event in projected.outcomes)
