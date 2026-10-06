"""Deterministic goal admission and bounded priority policy."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from .model import (
    Goal,
    GoalCandidate,
    GoalCost,
    GoalOrigin,
    GoalPolicyDecision,
    GoalPolicyResult,
    GoalPriority,
    GoalRisk,
    GoalStatus,
)


def normalized_goal_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


class GoalPolicy:
    MAX_ACTIVE = 32
    MAX_CANDIDATE = 64
    MAX_DEPTH = 4
    MAX_CHILDREN = 16

    def evaluate(
        self,
        candidate: GoalCandidate,
        *,
        existing: tuple[Goal, ...],
        resource_pressure: float = 0.0,
    ) -> GoalPolicyResult:
        if not isinstance(candidate, GoalCandidate):
            raise TypeError("candidate must be GoalCandidate")
        if (
            isinstance(resource_pressure, bool)
            or not isinstance(resource_pressure, (int, float))
            or not 0.0 <= float(resource_pressure) <= 1.0
        ):
            raise ValueError("resource pressure must be in 0..1")
        comparable = normalized_goal_title(candidate.title)
        duplicate = next((
            goal for goal in existing
            if goal.status in {
                GoalStatus.CANDIDATE, GoalStatus.ACTIVE,
                GoalStatus.PAUSED, GoalStatus.BLOCKED,
            }
            and normalized_goal_title(goal.title) == comparable
        ), None)
        if duplicate is not None:
            return GoalPolicyResult(
                GoalPolicyDecision.MERGE,
                "an equivalent live goal already exists",
                duplicate_goal_id=duplicate.id,
            )
        active_count = sum(goal.status is GoalStatus.ACTIVE for goal in existing)
        candidate_count = sum(
            goal.status is GoalStatus.CANDIDATE for goal in existing
        )
        if active_count >= self.MAX_ACTIVE or candidate_count >= self.MAX_CANDIDATE:
            return GoalPolicyResult(
                GoalPolicyDecision.DEFER,
                "bounded live-goal capacity has been reached",
            )
        if candidate.confidence < 0.55 or candidate.proposed_priority < 0.55:
            return GoalPolicyResult(
                GoalPolicyDecision.REJECT,
                "candidate is below grounded confidence or priority threshold",
            )
        if candidate.risk is GoalRisk.HIGH:
            return GoalPolicyResult(
                GoalPolicyDecision.ASK_USER,
                "high-risk direction requires user review before activation",
            )
        if resource_pressure >= 0.85 and candidate.cost is not GoalCost.LOW:
            return GoalPolicyResult(
                GoalPolicyDecision.DEFER,
                "current resource pressure is too high for this candidate",
            )
        return GoalPolicyResult(
            GoalPolicyDecision.ACCEPT,
            "grounded bounded candidate passed deterministic policy",
        )


def effective_priority(
    goal: Goal,
    *,
    now: datetime,
    urgency: float = 0.0,
    new_evidence: bool = False,
    resource_pressure: float = 0.0,
    conversational_relevance: float = 0.0,
    neuro_relevance: float = 0.0,
) -> GoalPriority:
    if not isinstance(goal, Goal):
        raise TypeError("goal must be Goal")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    values = {
        "urgency": urgency,
        "resource_pressure": resource_pressure,
        "conversational_relevance": conversational_relevance,
        "neuro_relevance": neuro_relevance,
    }
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise ValueError(f"{name} must be in 0..1")
    score = float(goal.base_priority)
    reasons = [f"base={score:.3f}"]
    if goal.origin is GoalOrigin.USER:
        score += 0.08
        reasons.append("authenticated-user=+0.080")
    urgency_bonus = min(0.15, float(urgency) * 0.15)
    score += urgency_bonus
    reasons.append(f"urgency=+{urgency_bonus:.3f}")
    age_days = max(0.0, (now - goal.created_at).total_seconds()) / 86400.0
    age_bonus = min(0.08, age_days * 0.008)
    score += age_bonus
    reasons.append(f"age=+{age_bonus:.3f}")
    if goal.expires_at is not None:
        remaining = (goal.expires_at - now).total_seconds()
        if remaining <= 0:
            deadline_bonus = 0.15
        else:
            deadline_bonus = 0.15 * max(0.0, 1.0 - remaining / 604800.0)
        score += deadline_bonus
        reasons.append(f"deadline=+{deadline_bonus:.3f}")
    if new_evidence:
        score += 0.05
        reasons.append("new-evidence=+0.050")
    conversation_bonus = min(0.10, float(conversational_relevance) * 0.10)
    score += conversation_bonus
    reasons.append(f"conversation=+{conversation_bonus:.3f}")
    # Deliberately small and caller-supplied. Goal→NEURO projection always calls
    # with zero, preventing a recursive attention/priority amplification loop.
    neuro_bonus = min(0.05, float(neuro_relevance) * 0.05)
    score += neuro_bonus
    reasons.append(f"neuro=+{neuro_bonus:.3f}")
    pressure_penalty = min(0.12, float(resource_pressure) * 0.12)
    score -= pressure_penalty
    reasons.append(f"resource=-{pressure_penalty:.3f}")
    if goal.status is GoalStatus.BLOCKED:
        score -= 0.25
        reasons.append("blocked=-0.250")
    elif goal.status is GoalStatus.PAUSED:
        score -= 0.35
        reasons.append("paused=-0.350")
    elif goal.status is GoalStatus.CANDIDATE:
        score -= 0.20
        reasons.append("candidate=-0.200")
    if goal.status in {
        GoalStatus.COMPLETED, GoalStatus.REJECTED, GoalStatus.CANCELLED,
        GoalStatus.EXPIRED, GoalStatus.SUPERSEDED,
    }:
        score = 0.0
        reasons.append("terminal=0.000")
    return GoalPriority(max(0.0, min(1.0, score)), tuple(reasons))
