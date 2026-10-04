"""Contextual autonomy policy for requested AVATAR wardrobe changes."""
from __future__ import annotations

from dataclasses import dataclass

from sofia.cognition.matrix import (
    ContextualInfluencePlan,
    InfluenceMode,
    InfluenceSignal,
    InfluenceSurface,
)
from sofia.personality.influence import ContinuityInfluence

from .clothing_intent import ClothingActionIntent
from .wardrobe_planner import OutfitPlan, WardrobeContext


@dataclass(frozen=True, slots=True)
class WardrobeAutonomyDecision:
    accepted: bool
    reason: str
    alternative_outfit_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be bool")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("autonomy reason must be nonempty")
        if self.alternative_outfit_id is not None and (
            not isinstance(self.alternative_outfit_id, str)
            or not self.alternative_outfit_id.strip()
        ):
            raise ValueError(
                "alternative_outfit_id must be None or nonempty"
            )
        if self.accepted and self.alternative_outfit_id is not None:
            raise ValueError(
                "accepted wardrobe decisions cannot counter-propose"
            )


@dataclass(frozen=True, slots=True)
class WardrobeAutonomyContext:
    """Trusted non-authoritative context for one clothing request."""

    continuity: ContinuityInfluence
    influence_plan: ContextualInfluencePlan
    wardrobe_context: WardrobeContext | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.continuity, ContinuityInfluence):
            raise TypeError("continuity must be ContinuityInfluence")
        if not isinstance(self.influence_plan, ContextualInfluencePlan):
            raise TypeError("influence_plan must be ContextualInfluencePlan")
        if (
            self.influence_plan.surface
            is not InfluenceSurface.WARDROBE_REQUEST_AUTONOMY
        ):
            raise ValueError(
                "wardrobe autonomy context requires wardrobe request surface"
            )
        if self.wardrobe_context is not None and not isinstance(
            self.wardrobe_context,
            WardrobeContext,
        ):
            raise TypeError(
                "wardrobe_context must be WardrobeContext or None"
            )


class WardrobeAutonomyPolicy:
    """Replaceable host policy for one requested wardrobe state transition.

    The default policy accepts valid public clothing changes and refuses
    restricted/private transitions. A richer policy can later incorporate
    trusted preference/emotion/activity evidence without giving user prose or
    an LLM direct state authority.
    """

    def decide(
        self,
        *,
        intent: ClothingActionIntent,
        candidate_item_ids: tuple[str, ...],
        private_only: bool,
    ) -> WardrobeAutonomyDecision:
        if not isinstance(intent, ClothingActionIntent):
            raise TypeError("intent must be ClothingActionIntent")
        if not isinstance(candidate_item_ids, tuple):
            raise TypeError("candidate_item_ids must be a tuple")
        if type(private_only) is not bool:
            raise TypeError("private_only must be bool")
        return WardrobeAutonomyDecision(
            True,
            "valid wardrobe change accepted by host autonomy policy",
        )

    def decide_contextual(
        self,
        *,
        intent: ClothingActionIntent,
        candidate_item_ids: tuple[str, ...],
        private_only: bool,
        candidate_plan: OutfitPlan | None,
        alternative_plan: OutfitPlan | None,
        context: WardrobeAutonomyContext | None,
    ) -> WardrobeAutonomyDecision:
        """Apply bounded context while preserving legacy policy overrides."""
        if type(self).decide is not WardrobeAutonomyPolicy.decide:
            return self.decide(
                intent=intent,
                candidate_item_ids=candidate_item_ids,
                private_only=private_only,
            )

        baseline = self.decide(
            intent=intent,
            candidate_item_ids=candidate_item_ids,
            private_only=private_only,
        )
        if (
            not baseline.accepted
            or context is None
            or candidate_plan is None
        ):
            return baseline

        wardrobe = context.wardrobe_context
        plan = context.influence_plan

        if (
            wardrobe is not None
            and plan.mode_for(InfluenceSignal.SEASON)
            is InfluenceMode.HARD_COMPATIBILITY
            and wardrobe.season not in candidate_plan.seasons
        ):
            return self._counter(
                "that outfit is not compatible with the grounded current season",
                alternative_plan,
            )

        if (
            wardrobe is not None
            and plan.mode_for(InfluenceSignal.WEATHER)
            is InfluenceMode.STRONG_PREFERENCE
            and candidate_plan.weather
            and wardrobe.effective_weather is not None
            and wardrobe.effective_weather not in candidate_plan.weather
        ):
            return self._counter(
                "the fresh weather evidence makes that outfit a poor fit right now",
                alternative_plan,
            )

        if (
            wardrobe is not None
            and plan.mode_for(InfluenceSignal.DAYPART)
            is InfluenceMode.BOUNDED_BIAS
            and wardrobe.lounge_window
            and not candidate_plan.lounge
            and alternative_plan is not None
            and alternative_plan.lounge
        ):
            return self._counter(
                "the current late-day lounge window makes a lounge outfit feel more appropriate",
                alternative_plan,
            )

        if (
            wardrobe is not None
            and plan.mode_for(InfluenceSignal.EMOTION)
            is InfluenceMode.BOUNDED_BIAS
            and alternative_plan is not None
            and alternative_plan.outfit_id != candidate_plan.outfit_id
        ):
            strong_tags = {
                tag
                for influence in wardrobe.emotion_influences
                if influence.intensity >= 0.75
                for tag in influence.style_tags
            }
            if (
                strong_tags
                and not (strong_tags & set(candidate_plan.style_tags))
                and (strong_tags & set(alternative_plan.style_tags))
            ):
                return self._counter(
                    "my current modeled emotional style preference leans toward another valid outfit",
                    alternative_plan,
                )

        return baseline

    @staticmethod
    def _counter(
        reason: str,
        alternative_plan: OutfitPlan | None,
    ) -> WardrobeAutonomyDecision:
        return WardrobeAutonomyDecision(
            False,
            reason,
            None if alternative_plan is None else alternative_plan.outfit_id,
        )


