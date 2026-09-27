"""Shared semantic interaction projection for text and future avatar rendering.

A RepresentedInteraction is the canonical reviewed event. Text and avatar
surfaces consume projections of that same event so they cannot silently drift.
AvatarIntent is deliberately not an animation receipt: until a renderer exists
and confirms completion, animation remains unverified.

Private/adult semantics are ordinary interaction semantics with stronger
audience requirements, not a global mode and never a consent grant.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import re

from sofia.interaction.registry import (
    CATALOG_VERSION,
    PRIVATE_SEMANTICS,
    InteractionCatalog,
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


class InteractionProjectionDenied(PermissionError):
    """Raised when an interaction cannot be exposed to the requested audience."""


class InteractionStage(str, Enum):
    PROPOSED = "proposed"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REPRESENTED = "represented"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class InteractionVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("interaction timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class PrivateInteractionGrant:
    """Trusted facts required to expose a private/adult represented interaction."""

    adult_verified: bool
    owner_verified: bool
    private_session: bool
    explicit_current_opt_in: bool
    external_stop_active: bool = False

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in (
            self.adult_verified,
            self.owner_verified,
            self.private_session,
            self.explicit_current_opt_in,
            self.external_stop_active,
        )):
            raise TypeError("private interaction grant facts must be booleans")

    def require(self) -> None:
        if (
            not self.adult_verified
            or not self.owner_verified
            or not self.private_session
            or not self.explicit_current_opt_in
            or self.external_stop_active
        ):
            raise InteractionProjectionDenied(
                "private represented interaction is not authorized"
            )


@dataclass(frozen=True, slots=True)
class RepresentedInteraction:
    """One reviewed, channel-neutral interaction event.

    REPRESENTED means the fictional/avatar-world action is part of the shared
    interaction state. It does not mean a renderer animated it or that physical
    real-world contact occurred.
    """

    interaction_id: str
    category: str
    semantic_id: str
    actor_id: str
    target_id: str
    stage: InteractionStage
    visibility: InteractionVisibility
    occurred_at: datetime
    evidence_refs: tuple[str, ...]
    region_id: str | None = None
    registry_version: str = CATALOG_VERSION

    def __post_init__(self) -> None:
        _identifier(self.interaction_id, "interaction_id")
        _identifier(self.semantic_id, "semantic_id")
        _identifier(self.actor_id, "actor_id")
        _identifier(self.target_id, "target_id")
        if self.actor_id == self.target_id:
            raise ValueError("interaction actor and target must be distinct")
        if self.category not in ("gesture", "action", "expression"):
            raise ValueError("interaction category is not supported")
        if not isinstance(self.stage, InteractionStage):
            raise TypeError("stage must be an InteractionStage")
        if not isinstance(self.visibility, InteractionVisibility):
            raise TypeError("visibility must be an InteractionVisibility")
        _utc(self.occurred_at)
        if self.region_id is not None:
            _identifier(self.region_id, "region_id")
        if (
            not isinstance(self.evidence_refs, tuple)
            or not self.evidence_refs
            or len(self.evidence_refs) > 16
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
        ):
            raise ValueError(
                "one to sixteen distinct evidence references are required"
            )
        for ref in self.evidence_refs:
            _identifier(ref, "evidence_ref")


@dataclass(frozen=True, slots=True)
class TextInteractionProjection:
    interaction_id: str
    provider_context: str
    visibility: InteractionVisibility


@dataclass(frozen=True, slots=True)
class AvatarInteractionIntent:
    """Future-renderer input generated from the exact same canonical event."""

    interaction_id: str
    animation_key: str
    actor_id: str
    target_id: str
    region_id: str | None
    stage: InteractionStage
    visibility: InteractionVisibility
    render_status: str = "unrendered"
    renderer_receipt_id: str | None = None

    @property
    def animation_confirmed(self) -> bool:
        return (
            self.render_status == "rendered"
            and isinstance(self.renderer_receipt_id, str)
            and bool(self.renderer_receipt_id)
        )


@dataclass(frozen=True, slots=True)
class InteractionProjectionBundle:
    interaction: RepresentedInteraction
    text: TextInteractionProjection
    avatar: AvatarInteractionIntent


def reviewed_interaction(
    *,
    catalog: InteractionCatalog,
    interaction_id: str,
    category: str,
    semantic_id: str,
    actor_id: str,
    target_id: str,
    stage: InteractionStage,
    occurred_at: datetime,
    evidence_refs: tuple[str, ...],
    region_id: str | None = None,
    visibility: InteractionVisibility | None = None,
) -> RepresentedInteraction:
    """Create a canonical interaction only from reviewed catalog vocabulary."""

    if not isinstance(catalog, InteractionCatalog):
        raise TypeError("reviewed InteractionCatalog is required")
    resolution = catalog.resolve_semantic(category, semantic_id)
    if resolution.status != "resolved" or resolution.canonical_id != semantic_id:
        raise ValueError("semantic interaction is not in the reviewed catalog")
    if region_id is not None and region_id not in catalog.region_ids:
        raise ValueError("interaction region is not in the canonical region catalog")

    requires_private = (category, semantic_id) in PRIVATE_SEMANTICS
    chosen_visibility = visibility or (
        InteractionVisibility.PRIVATE
        if requires_private
        else InteractionVisibility.PUBLIC
    )
    if requires_private and chosen_visibility is not InteractionVisibility.PRIVATE:
        raise ValueError("private/adult interaction cannot be projected publicly")

    return RepresentedInteraction(
        interaction_id=interaction_id,
        category=category,
        semantic_id=semantic_id,
        actor_id=actor_id,
        target_id=target_id,
        stage=stage,
        visibility=chosen_visibility,
        occurred_at=_utc(occurred_at),
        evidence_refs=evidence_refs,
        region_id=region_id,
    )


def _require_visibility(
    interaction: RepresentedInteraction,
    grant: PrivateInteractionGrant | None,
) -> None:
    if interaction.visibility is InteractionVisibility.PUBLIC:
        return
    if not isinstance(grant, PrivateInteractionGrant):
        raise InteractionProjectionDenied(
            "private interaction projection requires a current grant"
        )
    grant.require()


def project_interaction(
    interaction: RepresentedInteraction,
    *,
    grant: PrivateInteractionGrant | None = None,
) -> InteractionProjectionBundle:
    """Project one canonical event to text plus a future-renderer intent.

    Both projections carry the same interaction_id. The avatar projection stays
    explicitly unrendered until a separate renderer later supplies a receipt.
    """

    if not isinstance(interaction, RepresentedInteraction):
        raise TypeError("RepresentedInteraction is required")
    _require_visibility(interaction, grant)

    payload = {
        "interaction_id": interaction.interaction_id,
        "registry_version": interaction.registry_version,
        "category": interaction.category,
        "semantic_id": interaction.semantic_id,
        "actor_id": interaction.actor_id,
        "target_id": interaction.target_id,
        "region_id": interaction.region_id,
        "stage": interaction.stage.value,
        "visibility": interaction.visibility.value,
        "represented_action": interaction.stage is InteractionStage.REPRESENTED,
        "avatar_animation_confirmed": False,
        "physical_contact_confirmed": False,
        "evidence_refs": interaction.evidence_refs,
    }
    text = TextInteractionProjection(
        interaction_id=interaction.interaction_id,
        visibility=interaction.visibility,
        provider_context=(
            "TRUSTED SHARED REPRESENTED INTERACTION\n"
            "Text and avatar surfaces refer to this exact same reviewed semantic "
            "event. Respond naturally from it. Do not claim avatar animation "
            "completed unless a renderer receipt is separately present, and never "
            "reinterpret represented avatar-world contact as real-world physical "
            "contact. PRIVATE events must stay within the authorized private "
            "audience.\n"
            + json.dumps(payload, ensure_ascii=False)
        ),
    )
    avatar = AvatarInteractionIntent(
        interaction_id=interaction.interaction_id,
        animation_key=f"{interaction.category}:{interaction.semantic_id}",
        actor_id=interaction.actor_id,
        target_id=interaction.target_id,
        region_id=interaction.region_id,
        stage=interaction.stage,
        visibility=interaction.visibility,
    )
    return InteractionProjectionBundle(
        interaction=interaction,
        text=text,
        avatar=avatar,
    )
