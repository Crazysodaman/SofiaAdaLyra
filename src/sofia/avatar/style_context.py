"""A source-aware clothing taste projection for future INTERACT integration.

Only explicit, externally reviewed likes/dislikes become taste claims. A garment
request is not a positive preference. Sofía's proposed taste is not Sparks' taste.
This module does not authenticate a chat source or inject model context itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from .wardrobe import WardrobeError
from .wardrobe_catalog import RequestStatus, StyleInput, WardrobePrebuild


@dataclass(frozen=True, slots=True)
class StyleContext:
    requested_by_sparks: tuple[StyleInput, ...]
    liked_by_sparks: tuple[StyleInput, ...]
    disliked_by_sparks: tuple[StyleInput, ...]
    awaiting_source_review: tuple[StyleInput, ...]

    def for_chat(self) -> dict[str, object]:
        """JSON-ready evidence, not a finished cognitive-context adapter."""
        def rows(values: tuple[StyleInput, ...]) -> list[dict[str, str]]:
            return [
                {"subject_id": item.subject_id, "source_id": item.source_id,
                 "detail": item.detail} for item in values
            ]
        return {
            "schema": "sofia.avatar.style-context.v1",
            "requested_by_sparks": rows(self.requested_by_sparks),
            "liked_by_sparks": rows(self.liked_by_sparks),
            "disliked_by_sparks": rows(self.disliked_by_sparks),
            "sofia_preference_claims": [],
        }


def project_style_context(
    catalog: WardrobePrebuild, *, reviewed_source_ids: frozenset[str] = frozenset(),
) -> StyleContext:
    """Trusted host must verify source ownership/content before marking reviewed."""
    if not isinstance(catalog, WardrobePrebuild) or not isinstance(reviewed_source_ids, frozenset):
        raise WardrobeError("invalid style context inputs")
    source_ids = {entry.source_id for entry in catalog.inputs}
    if any(not isinstance(x, str) or x not in source_ids for x in reviewed_source_ids):
        raise WardrobeError("reviewed source is unknown to wardrobe catalog")
    requests: list[StyleInput] = []
    likes: list[StyleInput] = []
    dislikes: list[StyleInput] = []
    awaiting: list[StyleInput] = []
    for record in catalog.inputs:
        if record.status is RequestStatus.USER_REQUESTED:
            requests.append(record)
        elif record.source_id not in reviewed_source_ids:
            awaiting.append(record)
        elif record.status is RequestStatus.USER_LIKED:
            likes.append(record)
        elif record.status is RequestStatus.USER_DISLIKED:
            dislikes.append(record)
        else:
            raise WardrobeError("unrecognized preference status")
    return StyleContext(tuple(requests), tuple(likes), tuple(dislikes), tuple(awaiting))
