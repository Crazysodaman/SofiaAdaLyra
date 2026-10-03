from uuid import UUID

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
        # Status values are not authority proofs. Keep process-local issuance
        # registries so callers cannot manufacture PROPOSED/APPROVED lifecycle
        # state merely by constructing an ActionProposal with that enum value.
        # Production therefore fails closed across restarts.
        self._proposed: dict[UUID, ActionProposal] = {}
        self._approved: dict[UUID, ActionProposal] = {}

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

        if proposal.status is not ActionStatus.PROPOSED:
            raise ActionSystemError(
                "Only newly proposed actions may enter the proposal boundary."
            )

        if proposal.id in self._approved:
            raise ActionSystemError(
                "An already approved action cannot be proposed again."
            )
        existing = self._proposed.get(proposal.id)
        if existing is not None and existing != proposal:
            raise ActionSystemError(
                "Action proposal ID was reused for different content."
            )
        self._proposed[proposal.id] = proposal
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

        issued = self._proposed.get(proposal.id)
        if issued != proposal:
            raise ActionSystemError(
                "Proposal was not issued by this ActionSystem."
            )

        approved = ActionProposal(
            action=proposal.action,
            rationale=proposal.rationale,
            expected_outcome=proposal.expected_outcome,
            risk_explanation=proposal.risk_explanation,
            id=proposal.id,
            status=ActionStatus.APPROVED,
        )
        self._proposed.pop(proposal.id, None)
        self._approved[approved.id] = approved
        return approved

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

        issued = self._approved.get(proposal.id)
        if issued != proposal:
            raise ActionSystemError(
                "Approved proposal was not issued by this ActionSystem."
            )

        # Approval is single-use. Consume it before crossing the executor
        # boundary so an exception or ambiguous side effect cannot be replayed
        # under the same approval.
        self._approved.pop(proposal.id, None)

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