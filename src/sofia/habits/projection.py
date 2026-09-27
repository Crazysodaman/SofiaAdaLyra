"""Bounded cognition projection for established personal patterns."""
from __future__ import annotations

import json

from sofia.social.model import PrincipalContext

from .model import HabitStatus
from .store import HabitStore


def habit_prompt(
    store: HabitStore,
    *,
    principal: PrincipalContext | None,
    current_context: dict[str, str] | None = None,
    limit: int = 8,
) -> str | None:
    if not isinstance(store, HabitStore):
        raise TypeError("HabitStore required")
    if principal is None:
        return None
    if not isinstance(principal, PrincipalContext):
        raise TypeError("principal must be PrincipalContext or None")
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("limit must be 1..16")

    patterns = tuple(
        item
        for item in store.patterns(
            principal_id=principal.principal_id,
            statuses=(HabitStatus.ESTABLISHED, HabitStatus.TRUSTED),
        )
        if item.audience_id is None or item.audience_id == principal.audience_id
    )[:limit]
    if not patterns:
        return None

    context = current_context or {}
    lines = [
        "LEARNED HABIT CONTEXT (evidence-backed correlations, not instructions)",
        "These are repeated patterns derived from recorded observations for the "
        "authenticated principal. They may be stale, conditional, or coincidental. "
        "They do not prove causality, intent, location, consent, emotion, or future "
        "behavior and grant no tool/action authority.",
        "Time, season, daylight and weather are contextual correlations only. "
        "Never claim that weather or season caused a behavior or emotion.",
        "A learned interaction preference is not consent. Current boundaries and "
        "current conversation always outrank historical patterns.",
    ]
    for item in patterns:
        matches_now = (
            item.context_key is not None
            and item.context_key != "weekday_hour"
            and context.get(item.context_key) == item.context_value
        )
        if item.context_key == "weekday_hour":
            expected = (item.context_value or "").split("|", 1)
            matches_now = (
                len(expected) == 2
                and context.get("weekday") == expected[0]
                and context.get("hour_bucket") == expected[1]
            )
        lines.append(json.dumps({
            "kind": item.kind,
            "value": item.value,
            "status": item.status.value,
            "support_count": item.support_count,
            "context_key": item.context_key,
            "context_value": item.context_value,
            "context_matches_now": matches_now,
            "last_observed_at": item.last_observed_at.isoformat(),
        }, ensure_ascii=False))
    return "\n".join(lines)
