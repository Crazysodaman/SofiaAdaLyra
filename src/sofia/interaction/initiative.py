"""Pure gate for Sofía-proposed fictional interactions; no autonomous worker.

An offer, permission, text description, avatar execution and delivered message
are different events. This module never performs or claims the latter two.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal

from sofia.interaction.registry import InteractionCatalog


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
