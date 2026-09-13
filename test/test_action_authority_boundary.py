import pytest

from sofia.action.executor import TestActionExecutor
from sofia.action.model import Action, ActionProposal, ActionRisk
from sofia.action.system import ActionSystem, ActionSystemError
from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveRequest
from sofia.cognition.operation import CognitiveOperation


def make_operation(authority: Authority) -> CognitiveOperation:
    return CognitiveOperation(
        context=CognitiveContext(
            request=CognitiveRequest(messages=()),
        ),
        authority=authority,
    )


def make_proposal() -> ActionProposal:
    return ActionProposal(
        action=Action(
            name="system.test",
            description="Test action.",
            risk=ActionRisk.LOW,
            requires_approval=True,
        ),
        rationale="Testing authority separation.",
        expected_outcome="Execution remains controlled.",
        risk_explanation="No external side effects.",
    )


def test_proposal_authority_does_not_grant_execution_authority():
    executor = TestActionExecutor()
    system = ActionSystem(executor)

    operation = make_operation(
        Authority(
            can_respond=True,
            can_propose_actions=True,
            can_execute_actions=False,
        )
    )

    proposal = system.propose(
        operation,
        make_proposal(),
    )

    assert proposal is not None

    with pytest.raises(ActionSystemError):
        system.approve(operation, proposal)

    with pytest.raises(ActionSystemError):
        system.execute(operation, proposal)

    assert executor.executed == []


def test_execution_authority_without_proposal_authority_cannot_propose():
    executor = TestActionExecutor()
    system = ActionSystem(executor)

    operation = make_operation(
        Authority(
            can_respond=True,
            can_propose_actions=False,
            can_execute_actions=True,
        )
    )

    with pytest.raises(ActionSystemError):
        system.propose(operation, make_proposal())


def test_authority_is_not_part_of_action_proposal():
    proposal = make_proposal()

    assert not hasattr(proposal, "authority")


def test_authority_is_not_part_of_action():
    action = Action(
        name="system.test",
        description="Test action.",
    )

    assert not hasattr(action, "authority")