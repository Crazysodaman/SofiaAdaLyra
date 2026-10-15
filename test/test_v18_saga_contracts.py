from __future__ import annotations

import pytest

from sofia.ops.saga import (
    CompensationPlan,
    EffectClass,
    Escalation,
    OperationEffect,
    PartialOutcome,
    SagaError,
    classify_operation,
    plan_compensation,
)


def test_named_operations_are_classified_for_the_original_examples():
    assert classify_operation("discord.message.send").effect_class is (
        EffectClass.IRREVERSIBLE
    )
    assert classify_operation("git.commit.local").effect_class is EffectClass.REVERSIBLE
    assert classify_operation("git.push").effect_class is EffectClass.IRREVERSIBLE
    assert classify_operation(
        "home_assistant.service.call"
    ).effect_class is EffectClass.RETRYABLE_IDEMPOTENT
    assert classify_operation("jmri.turnout.set").effect_class is (
        EffectClass.RETRYABLE_IDEMPOTENT
    )
    assert classify_operation("hephaestus.package.stage").effect_class is (
        EffectClass.COMPENSABLE
    )


def test_unknown_operation_fails_closed_rather_than_assuming_reversible():
    effect = classify_operation("unregistered.custom.thing")
    assert effect.effect_class is EffectClass.UNKNOWN
    plan = plan_compensation(PartialOutcome(operation_id="unregistered.custom.thing"))
    assert plan.escalation is Escalation.OPERATOR_ACTION_REQUIRED
    assert plan.compensating_actions == ()
    assert plan.may_retry_automatically is False


def test_irreversible_operation_can_never_present_a_compensating_reversal():
    with pytest.raises(SagaError):
        OperationEffect(
            operation_id="git.push",
            effect_class=EffectClass.IRREVERSIBLE,
            compensation="git revert",
        )


def test_idempotent_effect_requires_a_stable_key_and_retries_automatically():
    with pytest.raises(SagaError):
        OperationEffect(
            operation_id="example.op",
            effect_class=EffectClass.RETRYABLE_IDEMPOTENT,
            requires_idempotency_key=False,
        )
    plan = plan_compensation(PartialOutcome(operation_id="home_assistant.state.set"))
    assert plan.may_retry_automatically is True
    assert plan.requires_idempotency_key is True
    assert plan.escalation is Escalation.NONE


def test_compensable_requires_a_declared_bounded_compensation():
    with pytest.raises(SagaError):
        OperationEffect(
            operation_id="example.op", effect_class=EffectClass.COMPENSABLE
        )
    plan = plan_compensation(PartialOutcome(operation_id="hephaestus.package.stage"))
    assert plan.effect_class is EffectClass.COMPENSABLE
    assert len(plan.compensating_actions) == 1
    assert plan.escalation is Escalation.OPERATOR_REVIEW


def test_partial_external_success_escalates_irreversible_effect_to_operator_action():
    outcome = PartialOutcome(
        operation_id="discord.message.send",
        committed_steps=("delivered",),
        uncommitted_steps=("acknowledged",),
        external_effect_observed=True,
    )
    plan = plan_compensation(outcome)
    assert plan.effect_class is EffectClass.IRREVERSIBLE
    assert plan.escalation is Escalation.OPERATOR_ACTION_REQUIRED
    assert plan.compensating_actions == ()
    assert "cannot be undone" in plan.reason


def test_reversible_operation_rolls_back_locally_without_operator():
    plan = plan_compensation(PartialOutcome(operation_id="git.commit.local"))
    assert plan.effect_class is EffectClass.REVERSIBLE
    assert plan.escalation is Escalation.NONE
    assert plan.compensating_actions == (
        "git reset --soft to the pre-operation revision",
    )
    assert isinstance(plan, CompensationPlan)


def test_partial_outcome_rejects_overlapping_or_malformed_steps():
    with pytest.raises(SagaError):
        PartialOutcome(
            operation_id="git.push",
            committed_steps=("a",),
            uncommitted_steps=("a",),
        )
    with pytest.raises(SagaError):
        PartialOutcome(operation_id="bad id with spaces")

    with pytest.raises(SagaError):
        classify_operation("also bad")
