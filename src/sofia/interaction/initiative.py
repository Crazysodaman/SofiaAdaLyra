"""Pure gate for Sofía-proposed fictional interactions; no autonomous worker.

An offer, permission, text description, avatar execution and delivered message
are different events. This module never performs or claims the latter two.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.representation import (
    InteractionPhase,
    InteractionStage,
    InteractionVisibility,
    RepresentedInteraction,
    reviewed_interaction,
)
from sofia.interaction.target_body import RepresentedTargetBody


@dataclass(frozen=True)
class InitiativeProposal:
    id: str
    source_id: str
    actor: Literal['sofia']
    target: Literal['user']
    kind: Literal['offer', 'gesture', 'question', 'lab_suggestion']
    semantic_id: str | None
    region_id: str | None
    created_at: datetime
    expires_at: datetime | None
    state: Literal['proposed', 'permitted', 'described', 'declined', 'cancelled', 'expired']
    permission_source_id: str | None = None


class InitiativeGate:
    """Transition guard; caller must query authoritative stop/boundary state."""

    def __init__(self, catalog: InteractionCatalog) -> None:
        if not isinstance(catalog, InteractionCatalog):
            raise TypeError('Validated canonical catalog required.')
        self.catalog = catalog

    @staticmethod
    def _time(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timezone-aware time required.')
        return value.astimezone(timezone.utc)

    @staticmethod
    def _id(value: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError('Nonempty source/proposal ID required.')
        return value

    def propose(self, *, proposal_id: str, source_id: str,
                kind: str, semantic_id: str | None = None,
                region_id: str | None = None, at: datetime,
                expires_at: datetime | None = None) -> InitiativeProposal:
        if kind not in ('offer', 'gesture', 'question', 'lab_suggestion'):
            raise ValueError('Unknown initiative kind.')
        if kind in ('offer', 'gesture'):
            if semantic_id not in self.catalog.semantic_aliases['gesture'].values():
                raise ValueError('Only reviewed gesture IDs can propose body contact.')
            # Region is a represented scene label, NOT verification of the
            # user's actual body or an authenticated avatar hitbox.
            if region_id is not None and region_id not in self.catalog.region_ids:
                raise ValueError('Unknown represented region.')
        elif semantic_id is not None or region_id is not None:
            raise ValueError('A question/lab suggestion is not an executed body gesture.')
        created = self._time(at)
        expires = self._time(expires_at) if expires_at is not None else None
        if expires is not None and expires <= created:
            raise ValueError('Expiration must be after proposal creation.')
        return InitiativeProposal(self._id(proposal_id), self._id(source_id),
                                  'sofia', 'user', kind, semantic_id, region_id,
                                  created, expires, 'proposed')

    def transition(self, proposal: InitiativeProposal, *, action: str,
                   at: datetime, stopped: bool, user_boundary_active: bool,
                   permission_source_id: str | None = None) -> InitiativeProposal:
        """Requires fresh guard inputs. No generated text or side effects."""
        if not isinstance(proposal, InitiativeProposal):
            raise TypeError('Proposal required.')
        if not isinstance(stopped, bool) or not isinstance(user_boundary_active, bool):
            raise TypeError('Stop and boundary readings must be explicit booleans.')
        now = self._time(at)
        if now < proposal.created_at:
            raise ValueError('Cannot transition before proposal creation.')
        if proposal.state in ('described', 'declined', 'cancelled', 'expired'):
            return proposal  # Terminal state: no replay or resurrection.
        if action == 'cancel':
            return replace(proposal, state='cancelled')
        if action == 'decline':
            return replace(proposal, state='declined')
        if proposal.expires_at is not None and now >= proposal.expires_at:
            return replace(proposal, state='expired')
        if action not in ('permit', 'describe'):
            raise ValueError('Unknown transition.')
        contact = proposal.kind in ('offer', 'gesture')
        if contact and (stopped or user_boundary_active):
            return replace(proposal, state='cancelled')
        if action == 'permit':
            if proposal.kind != 'gesture' or proposal.state != 'proposed':
                raise ValueError('Only proposed contact gestures need a per-event permission.')
            return replace(proposal, state='permitted',
                           permission_source_id=self._id(permission_source_id))
        if proposal.kind == 'gesture' and (proposal.state != 'permitted' or
                                            not proposal.permission_source_id):
            raise ValueError('Do not describe a new contact as completed without permission.')
        if proposal.kind != 'gesture' and proposal.state != 'proposed':
            raise ValueError('Invalid transition for non-contact initiative.')
        return replace(proposal, state='described')


class InitiativeSource(str, Enum):
    CONVERSATION = "conversation"
    EMOTION = "emotion"
    REFLECTION = "reflection"
    RELATIONSHIP = "relationship"
    HABIT = "habit"
    USER_REQUEST = "user_request"


@dataclass(frozen=True, slots=True)
class CanonicalInteractionProposal:
    proposal_id: str
    interaction: RepresentedInteraction
    source: InitiativeSource
    rationale_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise ValueError("proposal_id must be nonempty")
        if not isinstance(self.interaction, RepresentedInteraction):
            raise TypeError("interaction must be RepresentedInteraction")
        if self.interaction.stage is not InteractionStage.PROPOSED:
            raise ValueError("canonical proposal must remain PROPOSED")
        if not isinstance(self.source, InitiativeSource):
            raise TypeError("source must be InitiativeSource")
        if not isinstance(self.rationale_ref, str) or not self.rationale_ref.strip():
            raise ValueError("rationale_ref must be nonempty")


@dataclass(frozen=True, slots=True)
class InteractionReactionLink:
    parent_interaction_id: str
    reaction_interaction_id: str
    evidence_ref: str

    def __post_init__(self) -> None:
        for name in (
            "parent_interaction_id",
            "reaction_interaction_id",
            "evidence_ref",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if self.parent_interaction_id == self.reaction_interaction_id:
            raise ValueError("reaction cannot be its own parent")


class CanonicalInitiativePlanner:
    """Build reviewed Sofía proposals without claiming representation or render."""

    def __init__(
        self,
        *,
        catalog: InteractionCatalog,
        sofia_id: str = "sofia",
    ) -> None:
        if not isinstance(catalog, InteractionCatalog):
            raise TypeError("catalog must be InteractionCatalog")
        if not isinstance(sofia_id, str) or not sofia_id.strip():
            raise ValueError("sofia_id must be nonempty")
        self._catalog = catalog
        self._sofia_id = sofia_id.strip()

    def propose(
        self,
        *,
        target_id: str,
        category: str,
        semantic_id: str,
        occurred_at: datetime,
        evidence_refs: tuple[str, ...],
        source: InitiativeSource,
        rationale_ref: str,
        region_id: str | None = None,
        target_region_id: str | None = None,
        target_body: RepresentedTargetBody | None = None,
        phase: InteractionPhase = InteractionPhase.INSTANT,
        modifiers: tuple[str, ...] = (),
        visibility: InteractionVisibility | None = None,
        self_directed: bool = False,
    ) -> CanonicalInteractionProposal:
        if not isinstance(source, InitiativeSource):
            raise TypeError("source must be InitiativeSource")
        if not isinstance(rationale_ref, str) or not rationale_ref.strip():
            raise ValueError("rationale_ref must be nonempty")
        actor_id = self._sofia_id
        resolved_target = actor_id if self_directed else target_id
        seed = "|".join((
            actor_id,
            resolved_target,
            category,
            semantic_id,
            occurred_at.isoformat(),
            rationale_ref,
            ",".join(evidence_refs),
        ))
        interaction = reviewed_interaction(
            catalog=self._catalog,
            interaction_id=f"interaction:{uuid5(NAMESPACE_URL, seed)}",
            category=category,
            semantic_id=semantic_id,
            actor_id=actor_id,
            target_id=resolved_target,
            stage=InteractionStage.PROPOSED,
            occurred_at=occurred_at,
            evidence_refs=evidence_refs,
            region_id=region_id,
            target_region_id=target_region_id,
            target_body=target_body,
            phase=phase,
            modifiers=modifiers,
            visibility=visibility,
        )
        return CanonicalInteractionProposal(
            proposal_id=f"proposal:{interaction.interaction_id}",
            interaction=interaction,
            source=source,
            rationale_ref=rationale_ref,
        )

    @staticmethod
    def link_reaction(
        *,
        parent: RepresentedInteraction,
        reaction: RepresentedInteraction,
        evidence_ref: str,
    ) -> InteractionReactionLink:
        if not isinstance(parent, RepresentedInteraction):
            raise TypeError("parent must be RepresentedInteraction")
        if not isinstance(reaction, RepresentedInteraction):
            raise TypeError("reaction must be RepresentedInteraction")
        return InteractionReactionLink(
            parent_interaction_id=parent.interaction_id,
            reaction_interaction_id=reaction.interaction_id,
            evidence_ref=evidence_ref,
        )
