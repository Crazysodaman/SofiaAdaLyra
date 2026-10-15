"""Commitment records projected from the canonical GOALS owner (V18 CA-3705).

The original requirement asks to *define a commitment record using existing
GOALS/ACT owners*: who asked, what exactly was promised, the due date,
preconditions, uncertainty, cancellation, and when it is appropriate to
proactively follow up.

This module introduces no new canonical writer and no new table. A commitment is
a read-only projection of an existing :class:`sofia.goals.model.Goal`; the GOALS
state plane remains the sole owner of the durable record. The projection also
exposes a deterministic follow-up predicate so ACT/LIFE can decide whether a
proactive reminder is appropriate without inventing authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sofia.goals.model import Goal, GoalOrigin, GoalRunState, GoalStatus

_TERMINAL = frozenset({
    GoalStatus.COMPLETED, GoalStatus.REJECTED, GoalStatus.CANCELLED,
    GoalStatus.EXPIRED, GoalStatus.SUPERSEDED,
})


class CommitmentError(ValueError):
    """Raised when a goal cannot be projected into a commitment record."""


@dataclass(frozen=True, slots=True)
class CommitmentRecord:
    """A non-authoritative projection of a promise held in the GOALS owner."""

    commitment_id: str
    requested_by_principal_id: str
    promised: str
    due_at: datetime | None
    preconditions: tuple[str, ...]
    uncertainty: float
    cancellable: bool
    active: bool
    follow_up_after: datetime | None

    def __post_init__(self) -> None:
        if not isinstance(self.commitment_id, str) or not self.commitment_id.strip():
            raise CommitmentError("commitment_id is required")
        if (
            not isinstance(self.requested_by_principal_id, str)
            or not self.requested_by_principal_id.strip()
        ):
            raise CommitmentError("requested_by_principal_id is required")
        if not isinstance(self.promised, str) or not self.promised.strip():
            raise CommitmentError("promised text is required")
        if self.due_at is not None and (
            self.due_at.tzinfo is None or self.due_at.utcoffset() is None
        ):
            raise CommitmentError("due_at must be timezone-aware")
        if (
            isinstance(self.uncertainty, bool)
            or not isinstance(self.uncertainty, (int, float))
            or not 0.0 <= float(self.uncertainty) <= 1.0
        ):
            raise CommitmentError("uncertainty must be in 0..1")
        if type(self.cancellable) is not bool or type(self.active) is not bool:
            raise CommitmentError("cancellable and active must be bool")
        if self.follow_up_after is not None and (
            self.follow_up_after.tzinfo is None
            or self.follow_up_after.utcoffset() is None
        ):
            raise CommitmentError("follow_up_after must be timezone-aware")

    def is_overdue(self, *, now: datetime) -> bool:
        if now.tzinfo is None or now.utcoffset() is None:
            raise CommitmentError("now must be timezone-aware")
        if self.due_at is None:
            return False
        return now > self.due_at and self.active

    def should_follow_up(self, *, now: datetime) -> bool:
        """Proactive follow-up is appropriate only for an active, due promise.

        A blocked promise is never chased (the preconditions are unsatisfied),
        and a cancelled or terminal promise is never chased.
        """
        if now.tzinfo is None or now.utcoffset() is None:
            raise CommitmentError("now must be timezone-aware")
        if not self.active or self.preconditions:
            return False
        if self.follow_up_after is None:
            return False
        return now >= self.follow_up_after


def commitment_from_goal(goal: Goal) -> CommitmentRecord | None:
    """Project a :class:`Goal` into a commitment, or ``None`` if it is not one.

    A commitment is a promise *to a principal*: it must be an active/blocked
    goal with a named owner principal and a bounded completion description. A
    purely terminal goal is a historical record, not an open promise.
    """
    if not isinstance(goal, Goal):
        raise TypeError("goal must be a Goal")
    if goal.origin not in (GoalOrigin.USER, GoalOrigin.SELF):
        return None
    active = goal.status in (GoalStatus.ACTIVE, GoalStatus.BLOCKED,
                             GoalStatus.PAUSED)
    preconditions: tuple[str, ...] = ()
    if goal.status is GoalStatus.BLOCKED and goal.blocked_reason:
        preconditions = (goal.blocked_reason,)
    if goal.run_state is GoalRunState.BLOCKED_APPROVAL:
        preconditions = preconditions + ("awaiting operator approval",)
    # Follow-up becomes appropriate at the completion deadline; a promise with
    # no deadline is never proactively chased unless it is overdue-blocked.
    return CommitmentRecord(
        commitment_id=goal.id,
        requested_by_principal_id=goal.owner_principal_id,
        promised=f"{goal.title}: {goal.completion.description}",
        due_at=goal.expires_at,
        preconditions=preconditions,
        uncertainty=round(1.0 - float(goal.confidence), 6),
        cancellable=goal.status not in _TERMINAL,
        active=active,
        follow_up_after=goal.expires_at if active else None,
    )
