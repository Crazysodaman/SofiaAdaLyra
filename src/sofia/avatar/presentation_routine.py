"""Headless daily AVATAR presentation routine.

The routine turns trusted time/season/activity/weather/emotion context into a
public daily outfit transition. It never runs a renderer and never interrupts a
private-only presentation. Scheduling belongs to RUN; this module performs one
explicit evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .presentation import AttireMode, PresentationAuthority, PresentationState
from .presentation_store import PresentationStore
from .wardrobe_routine import (
    Cadence,
    OutfitPlanner,
    OutfitProposal,
    Preference,
    WardrobeContext,
    WornEvidence,
)


@dataclass(frozen=True, slots=True)
class PresentationRoutineResult:
    changed: bool
    deferred_private: bool
    proposal: OutfitProposal | None
    state: PresentationState
    reason: str


class HeadlessPresentationRoutine:
    def __init__(
        self,
        *,
        authority: PresentationAuthority,
        store: PresentationStore,
        planner: OutfitPlanner,
    ) -> None:
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("PresentationAuthority is required")
        if not isinstance(store, PresentationStore):
            raise TypeError("PresentationStore is required")
        if not isinstance(planner, OutfitPlanner):
            raise TypeError("OutfitPlanner is required")
        self.authority = authority
        self.store = store
        self.planner = planner

    def evaluate(
        self,
        context: WardrobeContext,
        *,
        operation_id: str,
        preferences: tuple[Preference, ...] = (),
        worn: tuple[WornEvidence, ...] = (),
        cadence: Cadence = Cadence.DAILY,
    ) -> PresentationRoutineResult:
        current = self.authority.current
        if current.private_only or current.attire is AttireMode.NUDE:
            return PresentationRoutineResult(
                changed=False,
                deferred_private=True,
                proposal=None,
                state=current,
                reason="private_presentation_active",
            )

        proposal = self.planner.suggest(
            context,
            cadence=cadence,
            preferences=preferences,
            worn=worn,
        )
        if self.authority.last_daily.outfit_id == proposal.outfit_id:
            return PresentationRoutineResult(
                changed=False,
                deferred_private=False,
                proposal=proposal,
                state=current,
                reason="daily_outfit_already_current",
            )

        self.authority.propose_outfit(
            operation_id=operation_id,
            expected_revision=current.revision,
            outfit_id=proposal.outfit_id,
            reason="headless_daily_context:" + ",".join(proposal.reasons),
            daily=True,
        )
        state = self.authority.commit_text(
            operation_id=operation_id,
            renderer_unavailable=True,
        )
        self.store.save(self.authority)
        return PresentationRoutineResult(
            changed=True,
            deferred_private=False,
            proposal=proposal,
            state=state,
            reason="daily_outfit_changed",
        )
