"""Explicit Sparks outfit-level likes supplied during AVATAR design review.

These records are for the wardrobe catalog, not claims of Sofía's own tastes.
Source IDs identify conversation evidence but are not authentication tokens.
A trusted host must verify the source before showing a positive preference in
INTERACT via project_style_context(reviewed_source_ids=...).
"""
from __future__ import annotations

from dataclasses import replace

from .wardrobe import WardrobeError
from .wardrobe_catalog import RequestStatus, StyleInput, WardrobePrebuild, build_starter_wardrobe

SPARKS_LIKED_OUTFIT_SOURCE_IDS = frozenset({
    "chat.2026-09-22.like.both.engineer",
    "chat.2026-09-22.like.both.lounge",
})


def confirmed_sparks_outfit_likes() -> tuple[StyleInput, ...]:
    """Outfit likes only; do not infer individual garment or color preferences."""
    return (
        StyleInput(
            "engineer.signature", RequestStatus.USER_LIKED,
            "chat.2026-09-22.like.both.engineer",
            "Sparks answered 'Both' when asked whether he likes the engineer outfit, lounge outfit, both or neither.",
        ),
        StyleInput(
            "lounge.relaxed", RequestStatus.USER_LIKED,
            "chat.2026-09-22.like.both.lounge",
            "Sparks answered 'Both' when asked whether he likes the engineer outfit, lounge outfit, both or neither.",
        ),
    )


def with_sparks_outfit_likes(catalog: WardrobePrebuild) -> WardrobePrebuild:
    """Enrich an existing wardrobe once without overwriting later user input."""
    if not isinstance(catalog, WardrobePrebuild):
        raise WardrobeError("a valid wardrobe prebuild is required")
    existing = {(entry.subject_id, entry.source_id) for entry in catalog.inputs}
    additions = tuple(
        record for record in confirmed_sparks_outfit_likes()
        if (record.subject_id, record.source_id) not in existing
    )
    return replace(catalog, inputs=catalog.inputs + additions)


def build_sparks_starter_wardrobe() -> WardrobePrebuild:
    """Build the starter wardrobe with the confirmed Sparks likes already present."""
    return with_sparks_outfit_likes(build_starter_wardrobe())
