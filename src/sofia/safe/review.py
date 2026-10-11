"""Read-only SAFE capability/grant review.

Pure reporting only. Unlisted capability names default to protected.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from sofia.safe.permissions import (
    PermissionLevel, PermissionStore,
    capability_permission_policy, explicitly_classified_capabilities,
)


@dataclass(frozen=True, slots=True)
class CapabilityReview:
    capability: str
    level: int
    explicitly_classified: bool
    standing_grant_allowed: bool
    active_grants: int
    concerns: tuple[str, ...]


def review_capabilities(
    registered: Iterable[str], *, permission_store: PermissionStore | None = None,
    now: datetime | None = None,
) -> tuple[CapabilityReview, ...]:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("time must be aware")
    values = tuple(registered)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError("registered capability names must be nonempty strings")
    duplicates = {name for name in values if values.count(name) > 1}
    classified = explicitly_classified_capabilities()
    grants = () if permission_store is None else permission_store.grants()
    entries = []
    for name in sorted(set(values)):
        policy = capability_permission_policy(name)
        active = tuple(g for g in grants if g.capability == name and g.is_active_at(moment))
        issues = []
        if name not in classified:
            issues.append("not_explicitly_classified_defaults_to_protected")
        if name in duplicates:
            issues.append("duplicate_capability_registration")
        if active and (
            policy.level != PermissionLevel.REVERSIBLE_SCOPED or
            not policy.standing_grant_allowed
        ):
            issues.append("standing_grant_for_non_grantable_capability")
        if any(not g.scope for g in active):
            issues.append("unbounded_standing_grant_scope_requires_review")
        if policy.level == PermissionLevel.NEVER_SELF_AUTHORIZED and active:
            issues.append("level_5_must_never_use_standing_authority")
        entries.append(CapabilityReview(
            name, int(policy.level), name in classified,
            policy.standing_grant_allowed, len(active), tuple(issues),
        ))
    return tuple(entries)


def compact_policy_review(registered: Iterable[str], store: PermissionStore) -> str:
    entries = review_capabilities(registered, permission_store=store)
    flagged = tuple(item for item in entries if item.concerns)
    if not flagged:
        return f"Reviewed {len(entries)} configured capabilities. No static warnings; runtime authorization is not verified."
    return "\n".join(
        f"{item.capability} [L{item.level}]: {', '.join(item.concerns)}"
        for item in flagged
    )
