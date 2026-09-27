"""Context-aware hairstyle planning for Sofía's headless avatar state.

Hair is representational presentation, not biological state. The planner may use
trusted time/season/weather/activity and already-grounded modeled emotion as
bounded style influences. It never infers emotion from appearance and never
changes privacy, attire, consent, or action authority.
"""
from __future__ import annotations

from dataclasses import dataclass

from .presentation import (
    AppearanceState,
    AttireMode,
    PresentationAuthority,
    PresentationState,
)
from .presentation_store import PresentationStore
from .wardrobe_routine import (
    Activity,
    EmotionStyleInfluence,
    Season,
    WardrobeContext,
    Weather,
)


@dataclass(frozen=True, slots=True)
class HairstylePlan:
    plan_id: str
    hairstyle: str
    activities: frozenset[Activity]
    seasons: frozenset[Season]
    weather: frozenset[Weather] = frozenset()
    lounge: bool = False
    style_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise ValueError("plan_id required")
        if not isinstance(self.hairstyle, str) or not self.hairstyle.strip():
            raise ValueError("hairstyle required")
        if not isinstance(self.activities, frozenset) or not self.activities:
            raise ValueError("hairstyle plan requires activities")
        if any(not isinstance(item, Activity) for item in self.activities):
            raise TypeError("activities must contain Activity")
        if not isinstance(self.seasons, frozenset) or not self.seasons:
            raise ValueError("hairstyle plan requires seasons")
        if any(not isinstance(item, Season) for item in self.seasons):
            raise TypeError("seasons must contain Season")
        if not isinstance(self.weather, frozenset) or any(
            not isinstance(item, Weather) for item in self.weather
        ):
            raise TypeError("weather must contain Weather")
        if type(self.lounge) is not bool:
            raise TypeError("lounge must be boolean")
        if (
            not isinstance(self.style_tags, tuple)
            or len(set(self.style_tags)) != len(self.style_tags)
            or any(
                not isinstance(tag, str)
                or not tag.strip()
                or len(tag) > 64
                for tag in self.style_tags
            )
        ):
            raise ValueError("invalid hairstyle style tags")


@dataclass(frozen=True, slots=True)
class HairstyleProposal:
    plan_id: str
    hairstyle: str
    reasons: tuple[str, ...]
    style_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AppearanceRoutineResult:
    changed: bool
    deferred_private: bool
    proposal: HairstyleProposal | None
    state: PresentationState
    reason: str


def starter_hairstyles() -> tuple[HairstylePlan, ...]:
    all_seasons = frozenset(Season)
    return (
        HairstylePlan(
            "hair.engineering.high-ponytail",
            "high ponytail with loose face-framing strands",
            frozenset({Activity.ENGINEERING, Activity.LAB}),
            all_seasons,
            weather=frozenset({Weather.HOT, Weather.MILD}),
            style_tags=("technical", "focused", "practical"),
        ),
        HairstylePlan(
            "hair.engineering.side-braid",
            "long side braid",
            frozenset({Activity.ENGINEERING, Activity.LAB, Activity.CONVERSATION}),
            all_seasons,
            weather=frozenset({Weather.WET, Weather.COLD}),
            style_tags=("technical", "practical", "composed"),
        ),
        HairstylePlan(
            "hair.relaxed.loose-waves",
            "long loose layered waves",
            frozenset({Activity.CONVERSATION, Activity.RELAXING}),
            all_seasons,
            style_tags=("relaxed", "soft", "warm"),
        ),
        HairstylePlan(
            "hair.lounge.messy-bun",
            "loose messy bun with a few strands down",
            frozenset({Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP}),
            all_seasons,
            lounge=True,
            style_tags=("relaxed", "cozy", "casual"),
        ),
        HairstylePlan(
            "hair.playful.half-up",
            "half-up style with long waves",
            frozenset({Activity.CONVERSATION, Activity.RELAXING}),
            all_seasons,
            style_tags=("playful", "bright", "soft"),
        ),
        HairstylePlan(
            "hair.formal.braided-updo",
            "braided updo",
            frozenset({Activity.FORMAL}),
            all_seasons,
            style_tags=("formal", "elegant", "composed"),
        ),
        HairstylePlan(
            "hair.rest.low-braid",
            "loose low braid",
            frozenset({Activity.SLEEP, Activity.RELAXING}),
            all_seasons,
            lounge=True,
            style_tags=("relaxed", "quiet", "soft"),
        ),
    )


class AppearancePlanner:
    """Choose hairstyle from bounded presentation context."""

    def __init__(
        self,
        plans: tuple[HairstylePlan, ...] | None = None,
    ) -> None:
        self.plans = plans or starter_hairstyles()
        if (
            not isinstance(self.plans, tuple)
            or not self.plans
            or any(not isinstance(item, HairstylePlan) for item in self.plans)
        ):
            raise TypeError("plans must contain HairstylePlan values")
        if len({item.plan_id for item in self.plans}) != len(self.plans):
            raise ValueError("hairstyle plan IDs must be unique")

    @staticmethod
    def _emotion_bias(
        plan: HairstylePlan,
        influences: tuple[EmotionStyleInfluence, ...],
    ) -> float:
        tags = set(plan.style_tags)
        return sum(
            float(item.intensity)
            for item in influences
            if tags.intersection(item.style_tags)
        )

    def suggest(
        self,
        context: WardrobeContext,
        *,
        current: AppearanceState,
    ) -> HairstyleProposal:
        if not isinstance(context, WardrobeContext):
            raise TypeError("WardrobeContext required")
        if not isinstance(current, AppearanceState):
            raise TypeError("AppearanceState required")

        compatible = tuple(
            plan
            for plan in self.plans
            if context.activity in plan.activities
        )
        if not compatible:
            raise ValueError("no hairstyle plan for current activity")

        weather = context.effective_weather

        def score(plan: HairstylePlan) -> float:
            result = 6.0 if context.season in plan.seasons else -6.0
            if weather is not None and plan.weather:
                result += 4.0 if weather in plan.weather else -2.0
            if context.lounge_window:
                result += 5.0 if plan.lounge else -1.0
            elif plan.lounge:
                result -= 2.0
            result += min(
                3.0,
                self._emotion_bias(plan, context.emotion_influences) * 2.0,
            )
            if plan.hairstyle == current.hairstyle:
                result += 1.5
            return result

        best = sorted(
            compatible,
            key=lambda item: (-score(item), item.plan_id),
        )[0]
        reasons = ["activity", "season"]
        if weather is not None and best.weather:
            reasons.append("weather")
        if context.lounge_window and best.lounge:
            reasons.append("late_lounge")
        if self._emotion_bias(best, context.emotion_influences) > 0:
            reasons.append("modeled_emotion_influence")
        return HairstyleProposal(
            plan_id=best.plan_id,
            hairstyle=best.hairstyle,
            reasons=tuple(reasons),
            style_tags=best.style_tags,
        )


class HeadlessAppearanceRoutine:
    """Commit hairstyle changes to the same authoritative presentation state."""

    def __init__(
        self,
        *,
        authority: PresentationAuthority,
        store: PresentationStore,
        planner: AppearancePlanner | None = None,
    ) -> None:
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("PresentationAuthority required")
        if not isinstance(store, PresentationStore):
            raise TypeError("PresentationStore required")
        self.authority = authority
        self.store = store
        self.planner = planner or AppearancePlanner()

    def evaluate(
        self,
        context: WardrobeContext,
        *,
        operation_id: str,
    ) -> AppearanceRoutineResult:
        current = self.authority.current
        if current.private_only or current.attire is AttireMode.NUDE:
            return AppearanceRoutineResult(
                changed=False,
                deferred_private=True,
                proposal=None,
                state=current,
                reason="private_presentation_active",
            )

        proposal = self.planner.suggest(
            context,
            current=current.appearance,
        )
        if proposal.hairstyle == current.appearance.hairstyle:
            return AppearanceRoutineResult(
                changed=False,
                deferred_private=False,
                proposal=proposal,
                state=current,
                reason="hairstyle_already_current",
            )

        tags = tuple(
            dict.fromkeys(
                (
                    *current.appearance.style_tags,
                    *proposal.style_tags,
                )
            )
        )[:12]
        appearance = AppearanceState(
            hairstyle=proposal.hairstyle,
            hair_color=current.appearance.hair_color,
            tail_color=current.appearance.tail_color,
            style_tags=tags,
        )
        self.authority.propose_appearance(
            operation_id=operation_id,
            expected_revision=current.revision,
            appearance=appearance,
            reason="headless_hair_context:" + ",".join(proposal.reasons),
        )
        state = self.authority.commit_text(
            operation_id=operation_id,
            renderer_unavailable=True,
        )
        self.store.save(self.authority)
        return AppearanceRoutineResult(
            changed=True,
            deferred_private=False,
            proposal=proposal,
            state=state,
            reason="hairstyle_changed",
        )
