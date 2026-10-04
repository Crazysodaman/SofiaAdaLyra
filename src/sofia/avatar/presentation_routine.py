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
from .wardrobe_prebuild import DAY_DEFAULT_OUTFIT_ID, NIGHT_LOUNGE_OUTFIT_ID
from .wardrobe_planner import (
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

    def evaluate_daypart_fallback(
        self,
        *,
        now,
        operation_id: str,
    ) -> PresentationRoutineResult:
        """Apply only all-season canonical daypart choices when season is unknown.

        Missing location/season evidence must not block a clock-grounded lounge
        transition. This fallback deliberately uses only the reviewed all-season
        canonical lounge/engineer presets and does not infer weather or season.
        """
        if (
            not hasattr(now, "tzinfo")
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise TypeError("now must be timezone-aware")
        current = self.authority.current
        if current.private_only or current.attire is AttireMode.NUDE:
            return PresentationRoutineResult(
                changed=False,
                deferred_private=True,
                proposal=None,
                state=current,
                reason="private_presentation_active",
            )

        late_lounge = now.hour >= 21 or now.hour < 6
        target = (
            NIGHT_LOUNGE_OUTFIT_ID
            if late_lounge
            else DAY_DEFAULT_OUTFIT_ID
        )
        if target not in self.authority.available_outfit_ids:
            return PresentationRoutineResult(
                changed=False,
                deferred_private=False,
                proposal=None,
                state=current,
                reason="daypart_fallback_outfit_unavailable",
            )
        if self.authority.last_daily.outfit_id == target:
            return PresentationRoutineResult(
                changed=False,
                deferred_private=False,
                proposal=None,
                state=current,
                reason="daypart_fallback_already_current",
            )

        reason = (
            "headless_daily_context:late_lounge,season_unknown"
            if late_lounge
            else "headless_daily_context:daytime_default,season_unknown"
        )
        def mutate() -> PresentationState:
            self.authority.propose_outfit(
                operation_id=operation_id,
                expected_revision=current.revision,
                outfit_id=target,
                reason=reason,
                daily=True,
            )
            return self.authority.commit_text(
                operation_id=operation_id,
                renderer_unavailable=True,
            )

        state = self.store.persist_mutation(
            self.authority,
            mutate,
        )
        if not isinstance(state, PresentationState):
            raise RuntimeError(
                "daypart presentation mutation returned invalid state"
            )
        return PresentationRoutineResult(
            changed=True,
            deferred_private=False,
            proposal=None,
            state=state,
            reason="daypart_fallback_changed",
        )

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

        def mutate() -> PresentationState:
            self.authority.propose_outfit(
                operation_id=operation_id,
                expected_revision=current.revision,
                outfit_id=proposal.outfit_id,
                reason="headless_daily_context:" + ",".join(proposal.reasons),
                daily=True,
            )
            return self.authority.commit_text(
                operation_id=operation_id,
                renderer_unavailable=True,
            )

        state = self.store.persist_mutation(
            self.authority,
            mutate,
        )
        if not isinstance(state, PresentationState):
            raise RuntimeError(
                "daily presentation mutation returned invalid state"
            )
        return PresentationRoutineResult(
            changed=True,
            deferred_private=False,
            proposal=proposal,
            state=state,
            reason="daily_outfit_changed",
        )
