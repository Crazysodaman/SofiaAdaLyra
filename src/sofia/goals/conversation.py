"""Authenticated deterministic conversation boundary for canonical goals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import re

from sofia.cognition.matrix import MatrixIntent, TurnMatrix
from sofia.conversation.model import ConversationMessage
from sofia.social.model import AudienceKind, PrincipalContext

from .model import (
    CompletionKind, Goal, GoalCompletionCondition, GoalOrigin, GoalRunState, GoalStatus,
    TERMINAL_GOAL_STATUSES,
)
from .evidence import GoalEvidenceLedger
from .policy import normalized_goal_title
from .service import GoalService


_CREATE = (
    re.compile(r"^\s*make\s+(.+?)\s+(?:a|my)\s+goal\s*[.!?]*$", re.I),
    re.compile(r"^\s*add\s+(?:a\s+)?goal\s+to\s+(.+?)\s*[.!?]*$", re.I),
    re.compile(r"^\s*your\s+goal\s+is\s+to\s+(.+?)\s*[.!?]*$", re.I),
    re.compile(r"^\s*i\s+want\s+you\s+to\s+(keep\s+an\s+eye\s+on\s+.+?)\s*[.!?]*$", re.I),
)
_LIST = re.compile(r"^\s*(?:list|show)\s+(?:me\s+)?(?:my|your|the)?\s*goals\s*[.!?]*$|^\s*what\s+are\s+(?:my|your|the)\s+current\s+goals\s*[.!?]*$", re.I)
_LIFECYCLE = re.compile(r"^\s*(pause|resume|cancel|approve|reject)\s+goal\s+(.+?)\s*[.!?]*$", re.I)
_BLOCKING = re.compile(r"^\s*what\s+is\s+blocking\s+goal\s+(.+?)\s*[.!?]*$", re.I)
_WHY = re.compile(r"^\s*why\s+is\s+goal\s+(.+?)\s+important\s*[.!?]*$", re.I)


@dataclass(frozen=True, slots=True)
class GoalConversationResult:
    content: str
    goal_id: str | None = None


class GoalConversationResolver:
    def __init__(self, goals: GoalService) -> None:
        if not isinstance(goals, GoalService):
            raise TypeError("goals must be GoalService")
        self.goals = goals
        evidence_path = getattr(goals.evidence_verifier, "path", None)
        self._evidence_ledger = (
            None if evidence_path is None else GoalEvidenceLedger(evidence_path)
        )

    @staticmethod
    def _authenticated_private(principal: PrincipalContext | None) -> PrincipalContext:
        if principal is None or principal.audience_kind is not AudienceKind.PRIVATE:
            raise PermissionError("goal management requires an authenticated private audience")
        return principal

    @staticmethod
    def _target(goals: tuple[Goal, ...], value: str) -> Goal:
        key = normalized_goal_title(value)
        matches = tuple(
            goal for goal in goals
            if goal.status not in TERMINAL_GOAL_STATUSES
            and (goal.id == value.strip() or normalized_goal_title(goal.title) == key)
        )
        if len(matches) != 1:
            raise ValueError("goal target is missing or ambiguous; use its exact title or id")
        return matches[0]

    def resolve(
        self,
        *,
        message: ConversationMessage,
        principal: PrincipalContext | None,
        turn: TurnMatrix | None,
    ) -> GoalConversationResult | None:
        if turn is None or turn.intent is not MatrixIntent.GOAL_MANAGEMENT:
            return None
        owner = self._authenticated_private(principal)
        text = message.content.strip()
        visible = self.goals.list_visible(owner)
        if _LIST.fullmatch(text):
            mine = "my" in text.casefold()
            rows = tuple(
                goal for goal in visible
                if goal.status not in TERMINAL_GOAL_STATUSES
                and (not mine or (
                    goal.origin is GoalOrigin.USER
                    and goal.owner_principal_id == owner.principal_id
                ))
            )
            if not rows:
                return GoalConversationResult("There are no matching current goals.")
            return GoalConversationResult("Current goals:\n" + "\n".join(
                f"- {goal.title} [{goal.status.value}; {goal.run_state.value}] ({goal.id})"
                for goal in rows
            ))
        for pattern in _CREATE:
            match = pattern.fullmatch(text)
            if match is None:
                continue
            title = " ".join(match.group(1).split()).strip(" .!?")
            if not title or len(title) > 180:
                raise ValueError("goal title must contain 1..180 characters")
            if self._evidence_ledger is None:
                raise RuntimeError("authenticated message evidence ledger is unavailable")
            self._evidence_ledger.record(
                evidence_ref=message.id,
                kind="authenticated_user_message",
                observed_at=message.created_at,
                source="conversation-host",
                principal_id=owner.principal_id,
                audience=f"{owner.audience_kind.value}:{owner.audience_id}",
            )
            duplicate = next((
                goal for goal in visible
                if goal.status not in TERMINAL_GOAL_STATUSES
                and normalized_goal_title(goal.title) == normalized_goal_title(title)
            ), None)
            if duplicate is not None:
                return GoalConversationResult(
                    f"That is already a current goal: {duplicate.title} [{duplicate.status.value}].",
                    duplicate.id,
                )
            goal = self.goals.create_user_goal(
                principal=owner,
                title=title,
                reason="Authenticated user explicitly requested this persistent goal.",
                base_priority=0.72,
                confidence=1.0,
                completion=GoalCompletionCondition(
                    CompletionKind.USER_DEFINED,
                    f"Authenticated owner confirms completion of: {title}",
                ),
                evidence_refs=(message.id,),
                now=message.created_at,
                expires_at=message.created_at + timedelta(days=90),
            )
            return GoalConversationResult(
                f"Added and activated goal: {goal.title} ({goal.id}).", goal.id,
            )
        lifecycle = _LIFECYCLE.fullmatch(text)
        if lifecycle is not None:
            operation, target = lifecycle.groups()
            goal = self._target(visible, target)
            if self._evidence_ledger is None:
                raise RuntimeError("authenticated message evidence ledger is unavailable")
            self._evidence_ledger.record(
                evidence_ref=message.id,
                kind="authenticated_user_message",
                observed_at=message.created_at,
                source="conversation-host",
                principal_id=owner.principal_id,
                audience=f"{owner.audience_kind.value}:{owner.audience_id}",
            )
            if operation.casefold() in {"approve", "reject"}:
                changed = self.goals.review_self_candidate(
                    goal=goal,
                    approve=operation.casefold() == "approve",
                    principal=owner,
                    evidence_refs=(message.id,),
                    now=message.created_at,
                )
                return GoalConversationResult(
                    f"Goal {changed.title} is now {changed.status.value}.", changed.id,
                )
            if goal.origin is not GoalOrigin.USER or goal.owner_principal_id != owner.principal_id:
                raise PermissionError("only your USER goals can be changed from conversation")
            transitions = {
                "pause": (GoalStatus.ACTIVE, GoalStatus.PAUSED),
                "resume": (GoalStatus.PAUSED, GoalStatus.ACTIVE),
                "cancel": (goal.status, GoalStatus.CANCELLED),
            }
            expected, next_status = transitions[operation.casefold()]
            if goal.status is not expected:
                raise ValueError(f"goal is {goal.status.value}, so it cannot be {operation}d")
            changed = self.goals.transition(
                goal_id=goal.id,
                principal_id=goal.scope_principal_id,
                audience=goal.scope_audience,
                expected_status=expected,
                next_status=next_status,
                actor_principal_id=owner.principal_id,
                authenticated_principal=owner,
                now=message.created_at,
                evidence_refs=(message.id,),
                note=f"authenticated owner requested {operation.casefold()}",
            )
            if operation.casefold() == "resume":
                changed = self.goals.set_run_state(
                    goal=changed,
                    run_state=GoalRunState.PENDING_INSPECTION,
                    actor_principal_id=owner.principal_id,
                    now=message.created_at,
                )
            return GoalConversationResult(
                f"Goal {changed.title} is now {changed.status.value}.", changed.id,
            )
        blocking = _BLOCKING.fullmatch(text)
        if blocking is not None:
            goal = self._target(visible, blocking.group(1))
            detail = goal.blocked_reason or (
                f"waiting state: {goal.run_state.value}"
                if goal.run_state.value != "none" else "no blocker is recorded"
            )
            return GoalConversationResult(f"{goal.title}: {detail}.", goal.id)
        why = _WHY.fullmatch(text)
        if why is not None:
            goal = self._target(visible, why.group(1))
            return GoalConversationResult(
                f"{goal.title} is important because {goal.reason}", goal.id,
            )
        raise ValueError("goal request was recognized but its exact lifecycle command was unclear")
