from abc import ABC, abstractmethod

from sofia.action.model import (
    ActionExecutionResult,
    ActionProposal,
    ActionStatus,
)


class ActionExecutorError(Exception):
    """
    Raised when an action executor cannot execute an action.
    """


class ActionExecutor(ABC):
    """
    Boundary through which approved actions are executed.

    Cognitive engines never receive an ActionExecutor.
    """

    @abstractmethod
    def execute(
        self,
        proposal: ActionProposal,
    ) -> ActionExecutionResult:
        raise NotImplementedError


class FailClosedActionExecutor(ActionExecutor):
    """
    Production-safe action boundary used until a concrete executor is wired.

    Approval is necessary but never sufficient to prove that a side effect
    occurred. This executor therefore refuses every approved action and emits
    a truthful FAILED result instead of manufacturing an EXECUTED receipt.
    """

    def __init__(
        self,
        reason: str = "No production action executor is configured.",
    ) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "FailClosedActionExecutor reason must be non-empty."
            )
        self._reason = reason.strip()

    @property
    def reason(self) -> str:
        return self._reason

    def execute(
        self,
        proposal: ActionProposal,
    ) -> ActionExecutionResult:
        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "FailClosedActionExecutor proposal must be an "
                "ActionProposal."
            )

        if proposal.status is not ActionStatus.APPROVED:
            raise ActionExecutorError(
                "Only approved action proposals may reach the "
                "production execution boundary."
            )

        return ActionExecutionResult(
            proposal_id=proposal.id,
            status=ActionStatus.FAILED,
            output=self._reason,
        )

class TestActionExecutor(ActionExecutor):
    """
    Deterministic executor used by tests.

    It records approved executions but performs no external side effects.
    """

    def __init__(self) -> None:
        self.executed: list[ActionProposal] = []

    def execute(
        self,
        proposal: ActionProposal,
    ) -> ActionExecutionResult:
        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "TestActionExecutor proposal must be an ActionProposal."
            )

        if proposal.status is not ActionStatus.APPROVED:
            raise ActionExecutorError(
                "Only approved action proposals may be executed."
            )

        self.executed.append(proposal)

        return ActionExecutionResult(
            proposal_id=proposal.id,
            status=ActionStatus.EXECUTED,
            output=f"Executed action: {proposal.action.name}",
        )