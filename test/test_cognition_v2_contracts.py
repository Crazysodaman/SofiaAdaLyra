"""Batch 1 regression tests for Cognition v2 ownership contracts."""
from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from sofia.cognition.v2 import (
    AcquisitionState,
    AnswerPlan,
    ClaimPlan,
    CognitiveSchedule,
    CognitiveTask,
    CognitiveTaskKind,
    ConversationFocus,
    EpistemicState,
    EvidenceAtom,
    EvidenceNeed,
    FocusReference,
    ModelWorkerRole,
    TurnKernelInput,
    TurnPlan,
)


NOW = datetime(2026, 10, 8, 18, 0, tzinfo=timezone.utc)


def _turn() -> TurnKernelInput:
    return TurnKernelInput(
        turn_id="turn:1",
        session_id="session:1",
        content="What's Artemis's CPU?",
        created_at=NOW,
        channel="discord",
        principal_id="sparks",
        audience_id="private:sparks",
    )


def _schedule() -> CognitiveSchedule:
    return CognitiveSchedule(
        schedule_id="schedule:1",
        tasks=(
            CognitiveTask(
                task_id="resolve:artemis",
                kind=CognitiveTaskKind.DETERMINISTIC,
            ),
            CognitiveTask(
                task_id="inspect:artemis",
                kind=CognitiveTaskKind.EVIDENCE_ACQUISITION,
                depends_on=("resolve:artemis",),
            ),
            CognitiveTask(
                task_id="reason:artemis",
                kind=CognitiveTaskKind.REASONING,
                depends_on=("inspect:artemis",),
                preferred_roles=(ModelWorkerRole.PRIMARY,),
            ),
        ),
    )


def test_turn_input_requires_principal_and_audience_together():
    assert _turn().audience_id == "private:sparks"
    with pytest.raises(ValueError, match="both be present or absent"):
        TurnKernelInput(
            turn_id="turn:2",
            session_id="session:1",
            content="Hello",
            created_at=NOW,
            channel="desktop",
            principal_id="sparks",
            audience_id=None,
        )


def test_conversation_focus_is_session_and_audience_scoped():
    reference = FocusReference(
        reference_id="reference:artemis",
        subject_id="fleet-node:artemis",
        kind="fleet-node",
        source_turn_id="turn:1",
        confidence=1.0,
        evidence_refs=("fleet-inventory:revision-4",),
    )
    focus = ConversationFocus(
        session_id="session:1",
        audience_id="private:sparks",
        revision=4,
        primary_reference=reference,
        active_topic_ids=("topic:artemis",),
        unresolved_request_ids=("request:cpu",),
    )

    assert focus.primary_reference.subject_id == "fleet-node:artemis"
    assert focus.audience_id == "private:sparks"


def test_evidence_contract_keeps_subject_and_acquisition_separate():
    atom = EvidenceAtom(
        evidence_id="remote-hardware:receipt-1",
        subject_id="fleet-node:artemis",
        predicate="hardware.cpu.model",
        value_json='"Ryzen"',
        source_id="capability:remote.hardware.inspect",
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        scope_id="private:sparks",
        trust=0.95,
        epistemic_state=EpistemicState.OBSERVED,
        acquisition_state=AcquisitionState.CURRENT,
    )

    assert atom.subject_id == "fleet-node:artemis"
    assert atom.epistemic_state is EpistemicState.OBSERVED
    assert atom.acquisition_state is AcquisitionState.CURRENT


def test_turn_plan_requires_subject_scoped_evidence_needs():
    need = EvidenceNeed(
        need_id="need:artemis-cpu",
        subject_id="fleet-node:artemis",
        predicate="hardware.cpu.model",
        scope_id="private:sparks",
        max_age_seconds=60,
        minimum_trust=0.8,
    )
    plan = TurnPlan(
        turn_id=_turn().turn_id,
        focus_revision=4,
        domains=("fleet", "machine"),
        evidence_needs=(need,),
        schedule=_schedule(),
        response_strategy="tool-assisted",
        action_requires_authority=False,
    )

    assert plan.evidence_needs[0].subject_id == "fleet-node:artemis"


def test_schedule_rejects_unknown_dependencies_and_invalid_parallel_groups():
    with pytest.raises(ValueError, match="unknown task"):
        CognitiveSchedule(
            schedule_id="schedule:bad",
            tasks=(CognitiveTask(
                task_id="reason:1",
                kind=CognitiveTaskKind.REASONING,
                depends_on=("missing:task",),
            ),),
        )
    with pytest.raises(ValueError, match="at least two"):
        CognitiveSchedule(
            schedule_id="schedule:bad-parallel",
            tasks=(CognitiveTask(
                task_id="reason:1",
                kind=CognitiveTaskKind.REASONING,
            ),),
            parallel_groups=(("reason:1",),),
        )
    with pytest.raises(ValueError, match="contains a cycle"):
        CognitiveSchedule(
            schedule_id="schedule:cycle",
            tasks=(
                CognitiveTask(
                    task_id="reason:1",
                    kind=CognitiveTaskKind.REASONING,
                    depends_on=("critique:1",),
                ),
                CognitiveTask(
                    task_id="critique:1",
                    kind=CognitiveTaskKind.CRITIQUE,
                    depends_on=("reason:1",),
                ),
            ),
        )


def test_observed_claim_requires_evidence_and_unknown_does_not_fake_it():
    with pytest.raises(ValueError, match="require evidence"):
        ClaimPlan(
            claim_id="claim:cpu",
            subject_id="fleet-node:artemis",
            predicate="hardware.cpu.model",
            rendered_value="Ryzen",
            epistemic_state=EpistemicState.OBSERVED,
            evidence_refs=(),
        )
    unknown = ClaimPlan(
        claim_id="claim:cpu-unknown",
        subject_id="fleet-node:artemis",
        predicate="hardware.cpu.model",
        rendered_value="currently unknown",
        epistemic_state=EpistemicState.UNKNOWN,
        evidence_refs=(),
    )
    answer = AnswerPlan(
        turn_id="turn:1",
        claims=(unknown,),
        unknown_need_ids=("need:artemis-cpu",),
    )
    assert answer.execution_receipt_refs == ()


def test_v2_contracts_cannot_carry_permission_consent_or_execution_authority():
    prohibited = {
        "permission",
        "authority",
        "consent",
        "execute",
        "execution_result",
        "receipt",
        "tool_result",
    }
    contract_types = (
        TurnKernelInput,
        ConversationFocus,
        EvidenceNeed,
        EvidenceAtom,
        CognitiveTask,
        CognitiveSchedule,
        TurnPlan,
    )
    field_names = {
        item.name
        for contract in contract_types
        for item in fields(contract)
    }
    assert field_names.isdisjoint(prohibited)
