"""Canonical State Plane persistence for goals and embedded lifecycle history."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane, StatePlaneConflictError

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
GOAL_SCOPE_NAMESPACE = "goals-v1-scope-index"


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


class GoalStore:
    """CAS-backed durable goal repository; records are never physically deleted."""

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must implement StatePlane")
        self.state_plane = state_plane
        self._quarantine_legacy_unscoped_self()

    def _quarantine_legacy_unscoped_self(self) -> None:
        """Make pre-scope SELF records terminal without projecting their content."""
        for record in self.state_plane.list_namespace(GOAL_NAMESPACE):
            value = json.loads(record.value.decode("utf-8"))
            if (
                value.get("origin") != GoalOrigin.SELF.value
                or value.get("scope_principal_id") is not None
                or value.get("scope_audience") is not None
                or value.get("status") in {
                    item.value for item in (
                        GoalStatus.COMPLETED, GoalStatus.REJECTED,
                        GoalStatus.CANCELLED, GoalStatus.EXPIRED,
                        GoalStatus.SUPERSEDED,
                    )
                }
            ):
                continue
            now = datetime.now(timezone.utc)
            previous = value["status"]
            value["status"] = GoalStatus.CANCELLED.value
            value["updated_at"] = now.isoformat()
            value["run_state"] = GoalRunState.NONE.value
            value["blocked_reason"] = None
            value["revision"] = record.revision + 1
            history = value.setdefault("history", [])
            if not history:
                history.append({
                    "event_id": f"goal-event:{uuid4()}",
                    "from_status": None,
                    "to_status": previous,
                    "actor_principal_id": "sofia:self",
                    "occurred_at": value["created_at"],
                    "evidence_refs": [],
                    "note": "legacy lifecycle origin reconstructed during scope migration",
                })
            history.append({
                "event_id": f"goal-event:{uuid4()}",
                "from_status": previous,
                "to_status": GoalStatus.CANCELLED.value,
                "actor_principal_id": "sofia:self",
                "occurred_at": now.isoformat(),
                "evidence_refs": [],
                "note": "legacy unscoped SELF goal quarantined during scope migration",
            })
            updated = StateRecord(
                key=record.key,
                state_class=record.state_class,
                revision=record.revision + 1,
                value=json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                ).encode("utf-8"),
                updated_at=now,
                source=record.source,
            )
            try:
                self.state_plane.write(updated, expected_revision=record.revision)
            except StatePlaneConflictError:
                current = self.state_plane.read(record.key)
                if current is None or current.revision <= record.revision:
                    raise

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
        self._register_scope(goal.scope_principal_id, goal.scope_audience, goal.updated_at)
        record = StateRecord(
            key=self._key(goal.id, goal.scope_principal_id, goal.scope_audience),
            state_class=StateClass.SHARED_AUTHORITATIVE,
            revision=1,
            value=self._payload(goal),
            updated_at=goal.updated_at,
            source=f"goal:{goal.origin.value}",
        )
        return self._goal(self.state_plane.write(record, expected_revision=None))

    def _register_scope(
        self,
        principal_id: str | None,
        audience: str | None,
        now: datetime,
    ) -> None:
        payload = json.dumps({
            "principal_id": principal_id,
            "audience": audience,
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        key = StateKey(
            namespace=GOAL_SCOPE_NAMESPACE,
            key="scope:" + sha256(payload).hexdigest()[:32],
        )
        if self.state_plane.read(key) is not None:
            return
        try:
            self.state_plane.write(StateRecord(
                key=key,
                state_class=StateClass.SHARED_AUTHORITATIVE,
                revision=1,
                value=payload,
                updated_at=now,
                source="goals:scope-index",
            ), expected_revision=None)
        except StatePlaneConflictError:
            if self.state_plane.read(key) is None:
                raise

    def scopes(self) -> tuple[tuple[str | None, str | None], ...]:
        """Return content-free internal partitions for maintenance/recovery."""
        scopes = []
        for record in self.state_plane.list_namespace(GOAL_SCOPE_NAMESPACE):
            value = json.loads(record.value.decode("utf-8"))
            item = (value.get("principal_id"), value.get("audience"))
            if (item[0] is None) != (item[1] is None):
                raise ValueError("goal scope index contains a partial scope")
            scopes.append(item)
        try:
            scopes.extend(self.state_plane.list_scopes(GOAL_NAMESPACE))
        except NotImplementedError:
            # New writes always maintain the portable scope index. Backends
            # without administrative enumeration cannot migrate older scopes.
            pass
        if (None, None) not in scopes:
            scopes.append((None, None))
        return tuple(sorted(set(scopes), key=lambda item: (item[0] or "", item[1] or "")))

    def list_all_internal(self) -> tuple[Goal, ...]:
        """Privileged host-only enumeration; callers must not project content."""
        return tuple(
            goal
            for principal_id, audience in self.scopes()
            for goal in self.list_scope(principal_id=principal_id, audience=audience)
        )

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
