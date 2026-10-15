from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.goals.model import (
    CompletionKind,
    Goal,
    GoalCompletionCondition,
    GoalLifecycleEvent,
    GoalOrigin,
    GoalRunState,
    GoalStatus,
)
from sofia.ops.commitment import CommitmentError, commitment_from_goal

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def make_goal(
    *,
    status: GoalStatus,
    expires_at: datetime | None,
    blocked_reason: str | None = None,
    run_state: GoalRunState = GoalRunState.NONE,
) -> Goal:
    initial = GoalStatus.ACTIVE if status is not GoalStatus.CANDIDATE else status
    history = (
        GoalLifecycleEvent(
            event_id="goal-event:1", from_status=None, to_status=initial,
            actor_principal_id="user:owner", occurred_at=NOW - timedelta(hours=2),
        ),
    )
    if initial is not status:
        history = history + (
            GoalLifecycleEvent(
                event_id="goal-event:2", from_status=initial, to_status=status,
                actor_principal_id="user:owner", occurred_at=NOW - timedelta(hours=1),
            ),
        )
    return Goal(
        id="goal:report", origin=GoalOrigin.USER, owner_principal_id="user:owner",
        scope_principal_id="user:owner", scope_audience="discord",
        title="Send the weekly report",
        reason="Owner asked for the weekly report.",
        status=status, base_priority=0.5, confidence=0.8,
        created_at=NOW - timedelta(hours=3), updated_at=NOW - timedelta(hours=1),
        evidence_refs=("evidence:1",),
        completion=GoalCompletionCondition(
            kind=CompletionKind.USER_DEFINED, description="report delivered",
        ),
        history=history, blocked_reason=blocked_reason,
        expires_at=expires_at, run_state=run_state,
    )


def test_active_promise_projects_to_a_commitment_with_follow_up_deadline():
    goal = make_goal(status=GoalStatus.ACTIVE, expires_at=NOW + timedelta(hours=1))
    record = commitment_from_goal(goal)
    assert record is not None
    assert record.requested_by_principal_id == "user:owner"
    assert record.promised == "Send the weekly report: report delivered"
    assert record.due_at == goal.expires_at
    assert record.active is True
    assert record.cancellable is True
    assert record.uncertainty == pytest.approx(0.2)
    assert record.should_follow_up(now=NOW) is False
    assert record.should_follow_up(now=NOW + timedelta(hours=2)) is True


def test_blocked_promise_is_never_proactively_chased():
    goal = make_goal(
        status=GoalStatus.BLOCKED, expires_at=NOW + timedelta(hours=1),
        blocked_reason="waiting on owner credentials",
    )
    record = commitment_from_goal(goal)
    assert record is not None
    assert record.preconditions == ("waiting on owner credentials",)
    assert record.should_follow_up(now=NOW + timedelta(days=30)) is False


def test_terminal_goal_is_a_history_record_not_an_open_commitment():
    goal = make_goal(status=GoalStatus.CANCELLED, expires_at=None)
    record = commitment_from_goal(goal)
    assert record is not None
    assert record.active is False
    assert record.cancellable is False
    assert record.should_follow_up(now=NOW + timedelta(days=30)) is False


def test_system_and_maintenance_goals_are_not_user_commitments():
    goal = make_goal(status=GoalStatus.ACTIVE, expires_at=NOW + timedelta(hours=1))
    system_goal = Goal(
        id=goal.id, origin=GoalOrigin.MAINTENANCE, owner_principal_id="sofia:self",
        scope_principal_id=None, scope_audience=None, title=goal.title,
        reason=goal.reason, status=GoalStatus.ACTIVE, base_priority=0.5,
        confidence=0.5, created_at=goal.created_at, updated_at=goal.updated_at,
        evidence_refs=("evidence:1",), completion=goal.completion,
        history=goal.history, expires_at=goal.expires_at,
    )
    assert commitment_from_goal(system_goal) is None


def test_approval_block_run_state_adds_a_precondition():
    goal = make_goal(
        status=GoalStatus.ACTIVE, expires_at=NOW + timedelta(hours=1),
        run_state=GoalRunState.BLOCKED_APPROVAL,
    )
    record = commitment_from_goal(goal)
    assert record is not None
    assert "awaiting operator approval" in record.preconditions
    assert record.should_follow_up(now=NOW + timedelta(days=1)) is False


def test_commitment_rejects_naive_deadline_and_bad_uncertainty():
    with pytest.raises(CommitmentError):
        from sofia.ops.commitment import CommitmentRecord
        CommitmentRecord(
            commitment_id="c1", requested_by_principal_id="user:owner",
            promised="x", due_at=datetime(2026, 1, 1), preconditions=(),
            uncertainty=0.1, cancellable=True, active=True, follow_up_after=None,
        )
    with pytest.raises(CommitmentError):
        from sofia.ops.commitment import CommitmentRecord
        CommitmentRecord(
            commitment_id="c1", requested_by_principal_id="user:owner",
            promised="x", due_at=None, preconditions=(), uncertainty=1.5,
            cancellable=True, active=True, follow_up_after=None,
        )
