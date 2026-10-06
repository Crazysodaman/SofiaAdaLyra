"""Canonical State Plane persistence for goals and embedded lifecycle history."""
from __future__ import annotations

from datetime import datetime
import json

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane

from .model import (
    CompletionKind,
    Goal,
    GoalCompletionCondition,
    GoalLifecycleEvent,
    GoalOrigin,
    GoalRunState,
    GoalStatus,
)


GOAL_NAMESPACE = "goals-v1"


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


class GoalStore:
    """CAS-backed durable goal repository; records are never physically deleted."""

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must implement StatePlane")
        self.state_plane = state_plane

    @staticmethod
    def _key(goal_id: str, principal_id: str | None, audience: str | None) -> StateKey:
        return StateKey(
            namespace=GOAL_NAMESPACE,
            key=goal_id,
            principal_id=principal_id,
            audience=audience,
        )

    @staticmethod
    def _payload(goal: Goal) -> bytes:
        value = {
            "id": goal.id,
            "origin": goal.origin.value,
            "owner_principal_id": goal.owner_principal_id,
            "scope_principal_id": goal.scope_principal_id,
            "scope_audience": goal.scope_audience,
            "title": goal.title,
            "reason": goal.reason,
            "status": goal.status.value,
            "base_priority": goal.base_priority,
            "confidence": goal.confidence,
            "created_at": goal.created_at.isoformat(),
            "updated_at": goal.updated_at.isoformat(),
            "evidence_refs": list(goal.evidence_refs),
            "completion": {
                "kind": goal.completion.kind.value,
                "description": goal.completion.description,
                "no_recurrence_seconds": goal.completion.no_recurrence_seconds,
            },
            "history": [{
                "event_id": item.event_id,
                "from_status": (
                    None if item.from_status is None else item.from_status.value
                ),
                "to_status": item.to_status.value,
                "actor_principal_id": item.actor_principal_id,
                "occurred_at": item.occurred_at.isoformat(),
                "evidence_refs": list(item.evidence_refs),
                "note": item.note,
            } for item in goal.history],
            "parent_goal_id": goal.parent_goal_id,
            "blocked_reason": goal.blocked_reason,
            "completion_evidence": list(goal.completion_evidence),
            "expires_at": _time(goal.expires_at),
            "superseded_by": goal.superseded_by,
            "run_state": goal.run_state.value,
            "revision": goal.revision,
        }
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")

    @staticmethod
    def _goal(record: StateRecord) -> Goal:
        value = json.loads(record.value.decode("utf-8"))
        completion = value["completion"]
        goal = Goal(
            id=value["id"],
            origin=GoalOrigin(value["origin"]),
            owner_principal_id=value["owner_principal_id"],
            scope_principal_id=value["scope_principal_id"],
            scope_audience=value["scope_audience"],
            title=value["title"],
            reason=value["reason"],
            status=GoalStatus(value["status"]),
            base_priority=float(value["base_priority"]),
            confidence=float(value["confidence"]),
            created_at=datetime.fromisoformat(value["created_at"]),
            updated_at=datetime.fromisoformat(value["updated_at"]),
            evidence_refs=tuple(value["evidence_refs"]),
            completion=GoalCompletionCondition(
                kind=CompletionKind(completion["kind"]),
                description=completion["description"],
                no_recurrence_seconds=completion["no_recurrence_seconds"],
            ),
            history=tuple(GoalLifecycleEvent(
                event_id=item["event_id"],
                from_status=(
                    None if item["from_status"] is None
                    else GoalStatus(item["from_status"])
                ),
                to_status=GoalStatus(item["to_status"]),
                actor_principal_id=item["actor_principal_id"],
                occurred_at=datetime.fromisoformat(item["occurred_at"]),
                evidence_refs=tuple(item["evidence_refs"]),
                note=item["note"],
            ) for item in value["history"]),
            parent_goal_id=value["parent_goal_id"],
            blocked_reason=value["blocked_reason"],
            completion_evidence=tuple(value["completion_evidence"]),
            expires_at=(
                None if value["expires_at"] is None
                else datetime.fromisoformat(value["expires_at"])
            ),
            superseded_by=value["superseded_by"],
            run_state=GoalRunState(value["run_state"]),
            revision=int(value["revision"]),
        )
        if goal.revision != record.revision:
            raise ValueError("goal payload revision disagrees with State Plane")
        return goal

    def create(self, goal: Goal) -> Goal:
        if not isinstance(goal, Goal) or goal.revision != 1:
            raise ValueError("new goal must be a revision-1 Goal")
        record = StateRecord(
            key=self._key(goal.id, goal.scope_principal_id, goal.scope_audience),
            state_class=StateClass.SHARED_AUTHORITATIVE,
            revision=1,
            value=self._payload(goal),
            updated_at=goal.updated_at,
            source=f"goal:{goal.origin.value}",
        )
        return self._goal(self.state_plane.write(record, expected_revision=None))

    def update(self, goal: Goal, *, expected_revision: int) -> Goal:
        if not isinstance(goal, Goal):
            raise TypeError("goal must be Goal")
        if goal.revision != expected_revision + 1:
            raise ValueError("goal revision must increment exactly once")
        record = StateRecord(
            key=self._key(goal.id, goal.scope_principal_id, goal.scope_audience),
            state_class=StateClass.SHARED_AUTHORITATIVE,
            revision=goal.revision,
            value=self._payload(goal),
            updated_at=goal.updated_at,
            source=f"goal:{goal.origin.value}",
        )
        return self._goal(self.state_plane.write(
            record, expected_revision=expected_revision,
        ))

    def get(
        self,
        goal_id: str,
        *,
        principal_id: str | None,
        audience: str | None,
    ) -> Goal | None:
        record = self.state_plane.read(self._key(goal_id, principal_id, audience))
        return None if record is None else self._goal(record)

    def list_scope(
        self,
        *,
        principal_id: str | None,
        audience: str | None,
    ) -> tuple[Goal, ...]:
        return tuple(
            self._goal(record)
            for record in self.state_plane.list_namespace(
                GOAL_NAMESPACE,
                principal_id=principal_id,
                audience=audience,
            )
        )
