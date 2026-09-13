from sofia.action.executor import (
    ActionExecutor,
    ActionExecutorError,
)
from sofia.action.model import (
    ActionExecutionResult,
    ActionProposal,
    ActionRisk,
    ActionStatus,
)
from sofia.authority.model import Authority
from sofia.cognition.operation import CognitiveOperation


class ActionSystemError(Exception):
    """
    Raised when Sofía's action system cannot complete an operation.
    """


class ActionSystem:
    """
    Coordinates action proposal, approval, and execution.

    The action system is deliberately separate from the cognitive engine.
    """

    def __init__(
        self,
        executor: ActionExecutor,
    ) -> None:
        if not isinstance(executor, ActionExecutor):
            raise TypeError(
                "ActionSystem requires an ActionExecutor."
            )

        self._executor = executor

    @property
    def executor(self) -> ActionExecutor:
        return self._executor

    def propose(
        self,
        operation: CognitiveOperation,
        proposal: ActionProposal,
    ) -> ActionProposal:
        self._validate_operation(operation)

        if not operation.authority.can_propose_actions:
            raise ActionSystemError(
                "Cognitive operation is not authorized "
                "to propose actions."
            )

        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "ActionSystem proposal must be an ActionProposal."
            )

        return proposal

    def approve(
        self,
        operation: CognitiveOperation,
        proposal: ActionProposal,
    ) -> ActionProposal:
        self._validate_operation(operation)

        if not operation.authority.can_execute_actions:
            raise ActionSystemError(
                "Cognitive operation is not authorized "
                "to approve actions for execution."
            )

        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "ActionSystem proposal must be an ActionProposal."
            )

        if proposal.status is not ActionStatus.PROPOSED:
            raise ActionSystemError(
                "Only proposed actions may be approved."
            )

        return ActionProposal(
            action=proposal.action,
            rationale=proposal.rationale,
            expected_outcome=proposal.expected_outcome,
            risk_explanation=proposal.risk_explanation,
            id=proposal.id,
            status=ActionStatus.APPROVED,
        )

    def execute(
        self,
        operation: CognitiveOperation,
        proposal: ActionProposal,
    ) -> ActionExecutionResult:
        self._validate_operation(operation)

        if not operation.authority.can_execute_actions:
            raise ActionSystemError(
                "Cognitive operation is not authorized "
                "to execute actions."
            )

        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "ActionSystem proposal must be an ActionProposal."
            )

        if proposal.status is not ActionStatus.APPROVED:
            raise ActionSystemError(
                "Only approved actions may be executed."
            )

        if (
            proposal.action.requires_approval
            and proposal.status is not ActionStatus.APPROVED
        ):
            raise ActionSystemError(
                "This action requires approval before execution."
            )

        try:
            return self._executor.execute(proposal)

        except ActionExecutorError:
            raise

        except Exception as exc:
            raise ActionSystemError(
                "Action execution failed."
            ) from exc

    @staticmethod
    def _validate_operation(
        operation: CognitiveOperation,
    ) -> None:
        if not isinstance(operation, CognitiveOperation):
            raise TypeError(
                "ActionSystem operation must be a CognitiveOperation."
            )

    @staticmethod
    def validate_self_improvement_proposal(
        proposal: ActionProposal,
    ) -> None:
        if not isinstance(proposal, ActionProposal):
            raise TypeError(
                "Self-improvement proposal must be an ActionProposal."
            )

        if proposal.action.risk is ActionRisk.LOW:
            raise ActionSystemError(
                "Self-improvement actions cannot be classified as LOW risk."
            )

        if not proposal.action.requires_approval:
            raise ActionSystemError(
                "Self-improvement actions must require approval."
            )