from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4


class ActionRisk(Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ActionStatus(Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class Action:
    name: str
    description: str
    parameters: tuple[tuple[str, str], ...] = ()
    risk: ActionRisk = ActionRisk.LOW
    requires_approval: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Action name must be a non-empty string.")

        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(
                "Action description must be a non-empty string."
            )

        if not isinstance(self.parameters, tuple):
            raise TypeError("Action parameters must be a tuple.")

        for parameter in self.parameters:
            if (
                not isinstance(parameter, tuple)
                or len(parameter) != 2
                or not isinstance(parameter[0], str)
                or not isinstance(parameter[1], str)
            ):
                raise TypeError(
                    "Each Action parameter must be a "
                    "(name, value) tuple of strings."
                )

        if not isinstance(self.risk, ActionRisk):
            raise TypeError("Action risk must be an ActionRisk.")

        if not isinstance(self.requires_approval, bool):
            raise TypeError(
                "Action requires_approval must be a bool."
            )


@dataclass(frozen=True)
class ActionProposal:
    action: Action
    rationale: str
    expected_outcome: str
    risk_explanation: str
    id: UUID = None
    status: ActionStatus = ActionStatus.PROPOSED

    def __post_init__(self) -> None:
        if not isinstance(self.action, Action):
            raise TypeError(
                "ActionProposal action must be an Action."
            )

        if (
            not isinstance(self.rationale, str)
            or not self.rationale.strip()
        ):
            raise ValueError(
                "ActionProposal rationale must be a non-empty string."
            )

        if (
            not isinstance(self.expected_outcome, str)
            or not self.expected_outcome.strip()
        ):
            raise ValueError(
                "ActionProposal expected_outcome must be a "
                "non-empty string."
            )

        if (
            not isinstance(self.risk_explanation, str)
            or not self.risk_explanation.strip()
        ):
            raise ValueError(
                "ActionProposal risk_explanation must be a "
                "non-empty string."
            )

        if self.id is None:
            object.__setattr__(self, "id", uuid4())
        elif not isinstance(self.id, UUID):
            raise TypeError("ActionProposal id must be a UUID.")

        if not isinstance(self.status, ActionStatus):
            raise TypeError(
                "ActionProposal status must be an ActionStatus."
            )


@dataclass(frozen=True)
class ActionExecutionResult:
    proposal_id: UUID
    status: ActionStatus
    output: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, UUID):
            raise TypeError(
                "ActionExecutionResult proposal_id must be a UUID."
            )

        if self.status not in (
            ActionStatus.EXECUTED,
            ActionStatus.FAILED,
        ):
            raise ValueError(
                "ActionExecutionResult status must be EXECUTED or FAILED."
            )

        if not isinstance(self.output, str):
            raise TypeError(
                "ActionExecutionResult output must be a string."
            )