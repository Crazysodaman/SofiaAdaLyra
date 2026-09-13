from uuid import UUID

import pytest

from sofia.action.executor import (
    ActionExecutorError,
    TestActionExecutor,
)
from sofia.action.model import (
    Action,
    ActionExecutionResult,
    ActionProposal,
    ActionRisk,
    ActionStatus,
)
from sofia.action.system import ActionSystem, ActionSystemError
from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveRequest
from sofia.cognition.operation import CognitiveOperation


def make_operation(
    *,
    can_propose_actions: bool = True,
    can_execute_actions: bool = False,
) -> CognitiveOperation:
    return CognitiveOperation(
        context=CognitiveContext(
            request=CognitiveRequest(messages=()),
        ),
        authority=Authority(
            can_respond=True,
            can_propose_actions=can_propose_actions,
            can_execute_actions=can_execute_actions,
        ),
    )


def make_proposal(
    *,
    risk: ActionRisk = ActionRisk.LOW,
    requires_approval: bool = True,
) -> ActionProposal:
    return ActionProposal(
        action=Action(
            name="test.action",
            description="Perform a deterministic test action.",
            parameters=(("value", "test"),),
            risk=risk,
            requires_approval=requires_approval,
        ),
        rationale="The action is useful for testing.",
        expected_outcome="The test executor records the action.",
        risk_explanation="The test executor performs no external side effects.",
    )


def test_action_is_immutable():
    action = Action(
        name="test.action",
        description="A test action.",
    )

    with pytest.raises(AttributeError):
        action.name = "changed"


def test_action_rejects_invalid_name():
    with pytest.raises(ValueError):
        Action(
            name="",
            description="A test action.",
        )


def test_action_rejects_invalid_risk():
    with pytest.raises(TypeError):
        Action(
            name="test.action",
            description="A test action.",
            risk="low",
        )


def test_action_proposal_generates_uuid():
    proposal = make_proposal()

    assert isinstance(proposal.id, UUID)
    assert proposal.status is ActionStatus.PROPOSED


def test_action_proposal_is_immutable():
    proposal = make_proposal()

    with pytest.raises(AttributeError):
        proposal.rationale = "changed"


def test_proposal_requires_all_explanations():
    with pytest.raises(ValueError):
        ActionProposal(
            action=Action(
                name="test.action",
                description="A test action.",
            ),
            rationale="",
            expected_outcome="Something happens.",
            risk_explanation="No meaningful risk.",
        )


def test_proposal_requires_action_authority():
    action_system = ActionSystem(TestActionExecutor())
    operation = make_operation(can_propose_actions=False)
    proposal = make_proposal()

    with pytest.raises(ActionSystemError):
        action_system.propose(operation, proposal)


def test_proposal_is_allowed_with_proposal_authority():
    action_system = ActionSystem(TestActionExecutor())
    operation = make_operation(can_propose_actions=True)
    proposal = make_proposal()

    result = action_system.propose(operation, proposal)

    assert result == proposal
    assert result.status is ActionStatus.PROPOSED


def test_execution_is_denied_without_execution_authority():
    action_system = ActionSystem(TestActionExecutor())
    operation = make_operation(can_execute_actions=False)
    proposal = make_proposal()

    with pytest.raises(ActionSystemError):
        action_system.execute(operation, proposal)


def test_only_approved_actions_can_execute():
    action_system = ActionSystem(TestActionExecutor())
    operation = make_operation(can_execute_actions=True)
    proposal = make_proposal()

    with pytest.raises(ActionSystemError):
        action_system.execute(operation, proposal)


def test_authorized_operation_can_approve_proposal():
    action_system = ActionSystem(TestActionExecutor())
    operation = make_operation(can_execute_actions=True)
    proposal = make_proposal()

    approved = action_system.approve(operation, proposal)

    assert approved.id == proposal.id
    assert approved.status is ActionStatus.APPROVED
    assert approved.action == proposal.action


def test_approved_action_can_execute():
    executor = TestActionExecutor()
    action_system = ActionSystem(executor)
    operation = make_operation(can_execute_actions=True)
    proposal = make_proposal()

    approved = action_system.approve(operation, proposal)
    result = action_system.execute(operation, approved)

    assert result.proposal_id == proposal.id
    assert result.status is ActionStatus.EXECUTED
    assert result.output == "Executed action: test.action"
    assert executor.executed == [approved]


def test_executor_never_receives_unapproved_action():
    executor = TestActionExecutor()
    proposal = make_proposal()

    with pytest.raises(ActionExecutorError):
        executor.execute(proposal)

    assert executor.executed == []


def test_execution_result_requires_execution_status():
    with pytest.raises(ValueError):
        ActionExecutionResult(
            proposal_id=UUID(int=0),
            status=ActionStatus.PROPOSED,
        )


def test_self_improvement_requires_more_than_low_risk():
    proposal = make_proposal(risk=ActionRisk.LOW)

    with pytest.raises(ActionSystemError):
        ActionSystem.validate_self_improvement_proposal(proposal)


def test_self_improvement_requires_approval():
    proposal = make_proposal(
        risk=ActionRisk.MODERATE,
        requires_approval=False,
    )

    with pytest.raises(ActionSystemError):
        ActionSystem.validate_self_improvement_proposal(proposal)


def test_self_improvement_proposal_passes_boundary():
    proposal = make_proposal(
        risk=ActionRisk.MODERATE,
        requires_approval=True,
    )

    ActionSystem.validate_self_improvement_proposal(proposal)


def test_action_system_requires_executor():
    with pytest.raises(TypeError):
        ActionSystem(executor=object())