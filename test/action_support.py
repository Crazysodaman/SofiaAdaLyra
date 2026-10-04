"""Deterministic action executor fixture; production always composes a real boundary."""
from sofia.action.executor import ActionExecutor, ActionExecutorError
from sofia.action.model import ActionExecutionResult, ActionProposal, ActionStatus


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
