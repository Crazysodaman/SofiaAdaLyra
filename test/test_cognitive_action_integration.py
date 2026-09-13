from uuid import UUID

import pytest

from sofia.action.executor import TestActionExecutor
from sofia.action.model import (
    Action,
    ActionProposal,
    ActionRisk,
    ActionStatus,
)
from sofia.action.system import ActionSystem
from sofia.authority.model import Authority
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import CognitiveRequest
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem


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


def make_proposal() -> ActionProposal:
    return ActionProposal(
        action=Action(
            name="test.action",
            description="A deterministic action.",
            risk=ActionRisk.LOW,
            requires_approval=True,
        ),
        rationale="Test the cognitive/action boundary.",
        expected_outcome="The action is executed only after approval.",
        risk_explanation="The test executor has no external side effects.",
    )


def make_system(executor: TestActionExecutor) -> CognitiveSystem:
    return CognitiveSystem(
        engine=RuleEngine(),
        context_assembler=CognitiveContextAssembler(),
        action_system=ActionSystem(executor),
    )


def test_cognitive_system_can_create_action_proposal():
    executor = TestActionExecutor()
    system = make_system(executor)
    operation = make_operation()
    proposal = make_proposal()

    result = system.propose_action(operation, proposal)

    assert result == proposal
    assert executor.executed == []


def test_cognitive_system_cannot_execute_from_proposal_authority():
    executor = TestActionExecutor()
    system = make_system(executor)
    operation = make_operation(can_execute_actions=False)
    proposal = make_proposal()

    with pytest.raises(Exception):
        system.execute_action(operation, proposal)

    assert executor.executed == []


def test_cognitive_system_requires_explicit_approval_before_execution():
    executor = TestActionExecutor()
    system = make_system(executor)
    operation = make_operation(can_execute_actions=True)
    proposal = make_proposal()

    with pytest.raises(Exception):
        system.execute_action(operation, proposal)

    assert executor.executed == []


def test_cognitive_system_can_approve_then_execute():
    executor = TestActionExecutor()
    system = make_system(executor)
    operation = make_operation(can_execute_actions=True)
    proposal = make_proposal()

    approved = system.approve_action(operation, proposal)
    result = system.execute_action(operation, approved)

    assert approved.id == proposal.id
    assert isinstance(approved.id, UUID)
    assert approved.status is ActionStatus.APPROVED
    assert result.proposal_id == proposal.id
    assert result.status is ActionStatus.EXECUTED
    assert executor.executed == [approved]


def test_action_system_is_outside_cognitive_engine():
    executor = TestActionExecutor()
    system = make_system(executor)

    assert system.action_system is not None
    assert system.action_system.executor is executor
    assert not hasattr(system.engine, "execute")