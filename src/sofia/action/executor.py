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
    Production-safe executor used until a concrete side-effect adapter is
    explicitly composed.

    This boundary never reports EXECUTED. Even an approved proposal with
    execution authority is denied unless a real production executor replaces
    this object through an intentional composition change.
    """

    def execute(
        self,
        proposal: ActionProposal,
    ) -> ActionExecutionResult:
        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "FailClosedActionExecutor proposal must be an ActionProposal."
            )

        if proposal.status is not ActionStatus.APPROVED:
            raise ActionExecutorError(
                "Only approved action proposals may reach the production "
                "execution boundary."
            )

        raise ActionExecutorError(
            "Production action execution is not configured; execution denied."
        )
