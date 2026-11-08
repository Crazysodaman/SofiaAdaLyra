"""Read-only, owner-approved planning for optional-module consolidation.

This registry records six owner-selected rationalizations, not package aliases
or authorization. It cannot install, unregister, delete, migrate state,
approve effects, or claim a module is signed/deployed. The current signed
package identities and all 47 optional catalog IDs remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ConsolidationPlan:
    source_id: str
    destination_ids: tuple[str, ...]
    strategy: str
    conditions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "destination_ids": list(self.destination_ids),
            "strategy": self.strategy,
            "conditions": list(self.conditions),
            "authority_effect": "none",
            "source_retired": False,
            "package_identity_changed": False,
            "runtime_capabilities_changed": False,
            "migration_verified": False,
        }


# An explicit source -> destination graph. None of these are active aliases.
# Splitting a proposed workflow among two destinations is not a two-way grant.
_PLANS: tuple[ConsolidationPlan, ...] = (
    ConsolidationPlan(
        "MOD-GENERALIZATION", ("MOD-ML",), "transfer_evaluation_profile",
        (
            "preserve existing generalization capability registration and saved state",
            "retain Core ownership of autobiographical skill learning",
            "prove parity of signed package, reviewer and source evidence before retirement",
        ),
    ),
    ConsolidationPlan(
        "MOD-CALENDAR", ("MOD-PRODUCTIVITY",), "calendar_provider_profile",
        (
            "keep calendar credentials and attendee privacy independently scoped",
            "do not inherit scheduling or invitation-write grants from task review",
            "migrate only after endpoint, provenance and owner permission tests",
        ),
    ),
    ConsolidationPlan(
        "MOD-PROJECT-FORGE", ("MOD-PRODUCTIVITY", "MOD-CREATIVE"),
        "workflow_and_artifact_split",
        (
            "preserve project IDs and durable operation receipts",
            "keep personal Core goals and preferences in Core",
            "do not infer completed artifacts from proposed jobs",
        ),
    ),
    ConsolidationPlan(
        "MOD-FILE-WATCH", ("MOD-IT-OBSERVABILITY",),
        "scoped_event_source_adapter",
        (
            "preserve approved filesystem root and privacy scope",
            "no file content access or workflow execution from event observation",
            "route dispatch only through independently governed Platform jobs",
        ),
    ),
    ConsolidationPlan(
        "MOD-DIGITAL-TWIN", ("MOD-HOMELAB", "MOD-WORKSHOP"),
        "isolated_simulation_profile",
        (
            "preserve simulation-only evidence without real-world effects",
            "separate sandbox identity, resource budgets and replay",
            "retain standalone process if isolation is independently required",
        ),
    ),
    ConsolidationPlan(
        "MOD-AVATAR-STUDIO", ("MOD-CREATIVE", "RM-AVATAR2D"),
        "shared_art_and_rig_authoring",
        (
            "preserve avatar rig, wardrobe and private/public asset boundaries",
            "Core alone chooses identity and voluntary expression",
            "keep optional separate authoring UI if resources require isolation",
        ),
    ),
)

# These are conditional ideas, not added to the approved optional catalog.
_CONDITIONAL_CANDIDATES: tuple[tuple[str, str, str], ...] = (
    ("MOD-IT-GAME-SERVERS", "MOD-GAMES",
     "split only if real server administration needs distinct provider grants "
     "and independent lifecycle beyond gameplay assistance"),
    ("MOD-IT-IDENTITY-DIRECTORY", "MOD-IT-SYSTEMS",
     "split only for a reviewed external AD/LDAP use case, never for Aegis SAFE"),
)


def consolidation_plans() -> tuple[ConsolidationPlan, ...]:
    """Proposed package changes only; all existing IDs remain active."""
    return _PLANS


def candidate_modules() -> tuple[dict[str, str], ...]:
    """Conditional *ideas* which are not source-registered or installable."""
    return tuple(
        {"candidate_id": candidate_id, "initial_owner": initial_owner,
         "split_condition": reason, "approved_catalog_entry": False,
         "installable": False}
        for candidate_id, initial_owner, reason in _CONDITIONAL_CANDIDATES
    )


def catalog_consolidation_review(module_ids: Iterable[str]) -> dict[str, object]:
    """Pure metadata report for a caller's catalog inventory.

    No input may grant authority or mark a module merged: wrong/missing IDs
    are surfaced as unverified rather than implicitly creating packages.
    """
    ids = tuple(module_ids)
    if any(type(item) is not str or not item for item in ids):
        raise ValueError("nonempty catalog IDs are required")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate catalog identity")
    present = set(ids)
    planned = {plan.source_id for plan in _PLANS}
    if len(planned) != len(_PLANS):
        raise AssertionError("duplicate consolidation source")
    if any(plan.source_id in plan.destination_ids
           or len(plan.destination_ids) != len(set(plan.destination_ids))
           or not plan.destination_ids for plan in _PLANS):
        raise AssertionError("invalid consolidation graph")
    return {
        "schema": "sofia.optional.consolidation_review.v1",
        "effect": "none",
        "approval_for_execution": False,
        "migration_verified": False,
        "current_catalog_count": len(present),
        "planned_consolidation_count": len(_PLANS),
        "unobserved_source_ids": sorted(planned - present),
        "unobserved_destination_ids": sorted(
            {parent for plan in _PLANS for parent in plan.destination_ids}
            - present - {"RM-AVATAR2D"}
        ),
        "plans": [plan.as_dict() for plan in _PLANS],
        "conditional_new_modules": list(candidate_modules()),
    }
