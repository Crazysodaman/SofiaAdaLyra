"""Offline wardrobe *proposals*: no renderer, weather fetch, scheduler or emotion claims.

The trusted host supplies local time, observed weather, audience and source IDs.
No garment is shown or recorded as worn by this module. Automatic proposals
are covered, non-private outfits, even for an authenticated private session.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum

from .wardrobe import Wardrobe, WardrobeError, WardrobeConflict, Outfit


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class Activity(str, Enum):
    CONVERSATION = "conversation"
    ENGINEERING = "engineering"
    LAB = "lab"
    RELAXING = "relaxing"
    SLEEP = "sleep"
    FORMAL = "formal"


class Weather(str, Enum):
    HOT = "hot"
    COLD = "cold"
    WET = "wet"
    MILD = "mild"


class Cadence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PreferenceActor(str, Enum):
    SPARKS = "sparks"
    SOFIA = "sofia"


class PreferenceTarget(str, Enum):
    OUTFIT = "outfit"
    ITEM = "item"
    COMBINATION = "combination"


class Sentiment(IntEnum):
    HATE = -2
    DISLIKE = -1
    LIKE = 1
    LOVE = 2


class ChangeOrigin(str, Enum):
    CHOSEN = "chosen"
    UNINTENDED = "unintended"


def _id(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128 or not all(
        c.isascii() and (c.isalnum() or c in "_.:-") for c in value
    ) or not value[0].isalnum():
        raise WardrobeError("invalid stable ID")
    return value


def _aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise WardrobeError("trusted local time must have a UTC offset")
    return value


@dataclass(frozen=True, slots=True)
class WeatherObservation:
    condition: Weather
    observed_at: datetime
    source_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.condition, Weather):
            raise WardrobeError("invalid weather condition")
        _aware(self.observed_at)
        _id(self.source_id)


@dataclass(frozen=True, slots=True)
class WardrobeContext:
    now: datetime  # trusted host-local clock; never inferred from chat text
    season: Season  # trusted host-selected locale/hemisphere; not hardcoded month
    activity: Activity
    weather: WeatherObservation | None = None

    def __post_init__(self) -> None:
        _aware(self.now)
        if not isinstance(self.season, Season) or not isinstance(self.activity, Activity):
            raise WardrobeError("season and activity must be typed")
        if self.weather is not None and not isinstance(self.weather, WeatherObservation):
            raise WardrobeError("invalid weather evidence")

    @property
    def effective_weather(self) -> Weather | None:
        if self.weather is None:
            return None
        age = self.now.astimezone(timezone.utc) - self.weather.observed_at.astimezone(timezone.utc)
        return self.weather.condition if timedelta(0) <= age <= timedelta(hours=6) else None

    @property
    def lounge_window(self) -> bool:
        return (self.now.hour >= 21 or self.now.hour < 6) and self.activity in (
            Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP
        )


@dataclass(frozen=True, slots=True)
class OutfitPlan:
    outfit_id: str
    item_ids: tuple[str, ...]
    activities: frozenset[Activity]
    seasons: frozenset[Season]
    weather: frozenset[Weather] = frozenset()
    lounge: bool = False
    private_only: bool = False
    style_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _id(self.outfit_id)
        if not isinstance(self.item_ids, tuple) or not self.item_ids or len(set(self.item_ids)) != len(self.item_ids):
            raise WardrobeError("outfit must contain unique garment IDs")
        for item in self.item_ids:
            _id(item)
        for values, enum_type, label in (
            (self.activities, Activity, "activities"),
            (self.seasons, Season, "seasons"),
            (self.weather, Weather, "weather"),
        ):
            if not isinstance(values, frozenset) or any(not isinstance(v, enum_type) for v in values):
                raise WardrobeError(f"invalid outfit {label}")
        if not self.activities or not self.seasons:
            raise WardrobeError("outfit requires activity and seasonal suitability")
        if type(self.lounge) is not bool or type(self.private_only) is not bool:
            raise WardrobeError("outfit flags must be boolean")
        if not isinstance(self.style_tags, tuple) or any(
            not isinstance(tag, str) or not tag.strip() or len(tag) > 64 for tag in self.style_tags
        ):
            raise WardrobeError("invalid style tags")


@dataclass(frozen=True, slots=True)
class Preference:
    """A supplied preference record, NOT a model-generated fact or subjective feeling."""
    actor: PreferenceActor
    target: PreferenceTarget
    ids: tuple[str, ...]
    sentiment: Sentiment
    source_id: str
    reviewed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.actor, PreferenceActor) or not isinstance(self.target, PreferenceTarget):
            raise WardrobeError("invalid preference actor or target")
        if not isinstance(self.sentiment, Sentiment) or not isinstance(self.reviewed, bool):
            raise WardrobeError("invalid preference sentiment or review state")
        if not isinstance(self.ids, tuple) or not self.ids or len(set(self.ids)) != len(self.ids):
            raise WardrobeError("preference target IDs must be unique")
        for identifier in self.ids:
            _id(identifier)
        _id(self.source_id)
        if self.target is not PreferenceTarget.COMBINATION and len(self.ids) != 1:
            raise WardrobeError("outfit/item preference requires one ID")
        if self.target is PreferenceTarget.COMBINATION and len(self.ids) < 2:
            raise WardrobeError("combination preference requires two or more IDs")
        if self.target is PreferenceTarget.COMBINATION and tuple(sorted(self.ids)) != self.ids:
            raise WardrobeError("combination IDs must be in canonical sorted order")


@dataclass(frozen=True, slots=True)
class WornEvidence:
    """A host-verified display receipt, never created by an outfit proposal."""
    outfit_id: str
    occurred_at: datetime
    renderer_receipt_id: str

    def __post_init__(self) -> None:
        _id(self.outfit_id)
        _aware(self.occurred_at)
        _id(self.renderer_receipt_id)


@dataclass(frozen=True, slots=True)
class OutfitProposal:
    outfit_id: str
    outfit: Outfit
    period_key: str
    reasons: tuple[str, ...]
    requires_renderer_verification: bool = True


@dataclass(frozen=True, slots=True)
class ClothingAppraisal:
    """Optional expressive *candidates*, never an asserted emotion or consent."""
    origin: ChangeOrigin
    cue_candidates: tuple[str, ...]
    requires_covered_recovery: bool
    may_publish: bool = False


def period_key(now: datetime, cadence: Cadence) -> str:
    _aware(now)
    if not isinstance(cadence, Cadence):
        raise WardrobeError("invalid outfit rotation cadence")
    if cadence is Cadence.DAILY:
        return now.date().isoformat()
    if cadence is Cadence.WEEKLY:
        iso = now.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return now.strftime("%Y-%m")


class OutfitPlanner:
    """Deterministic covered-outfit suggestion with separate sourced taste signals."""

    def __init__(self, wardrobe: Wardrobe, plans: tuple[OutfitPlan, ...]):
        if not isinstance(wardrobe, Wardrobe) or not isinstance(plans, tuple) or not plans:
            raise WardrobeError("wardrobe and nonempty outfit plans are required")
        if any(not isinstance(plan, OutfitPlan) for plan in plans):
            raise WardrobeError("invalid outfit plan")
        if len({plan.outfit_id for plan in plans}) != len(plans):
            raise WardrobeError("duplicate outfit ID")
        self._wardrobe = wardrobe
        self._plans: dict[str, tuple[OutfitPlan, Outfit]] = {}
        for plan in plans:
            outfit = wardrobe.selection(plan.item_ids)
            if plan.private_only:
                # Private outfits need a separate authenticated, explicit workflow.
                continue
            if not outfit.covered_default:
                raise WardrobeError("automatic outfit must cover torso and pelvis")
            self._plans[plan.outfit_id] = plan, outfit
        if not self._plans:
            raise WardrobeError("no covered automatic outfits")

    def suggest(
        self,
        context: WardrobeContext,
        *,
        cadence: Cadence = Cadence.DAILY,
        preferences: tuple[Preference, ...] = (),
        worn: tuple[WornEvidence, ...] = (),
    ) -> OutfitProposal:
        if not isinstance(context, WardrobeContext) or not isinstance(cadence, Cadence):
            raise WardrobeError("invalid selection context or cadence")
        if not isinstance(preferences, tuple) or any(not isinstance(p, Preference) for p in preferences):
            raise WardrobeError("invalid preference evidence")
        if not isinstance(worn, tuple) or any(not isinstance(w, WornEvidence) for w in worn):
            raise WardrobeError("invalid worn evidence")
        if len({(p.actor, p.target, p.ids) for p in preferences}) != len(preferences):
            raise WardrobeError("ambiguous repeated preference; reconcile revisions in MEM")
        if len({w.renderer_receipt_id for w in worn}) != len(worn):
            raise WardrobeError("duplicate renderer receipts")
        key = period_key(context.now, cadence)
        compatible = [
            (plan, outfit) for plan, outfit in self._plans.values()
            if context.activity in plan.activities
        ]
        if not compatible:
            raise WardrobeError("no activity-compatible covered outfit; host must use verified fallback")
        recent = tuple(sorted((w for w in worn if timedelta(0) <= (
            context.now.astimezone(timezone.utc) - w.occurred_at.astimezone(timezone.utc)
        ) <= timedelta(days=90)), key=lambda w: (w.occurred_at.astimezone(timezone.utc), w.renderer_receipt_id)))
        weather = context.effective_weather

        def score(entry: tuple[OutfitPlan, Outfit]) -> int:
            plan, _ = entry
            result = 6 if context.season in plan.seasons else -6
            if weather is not None and plan.weather:
                result += 4 if weather in plan.weather else -4
            if plan.lounge and context.lounge_window:
                result += 7
            elif plan.lounge and not context.lounge_window:
                result -= 2
            elif context.lounge_window:
                result -= 2
            for preference in preferences:
                if not preference.reviewed:
                    continue
                matches = (
                    preference.target is PreferenceTarget.OUTFIT and preference.ids == (plan.outfit_id,)
                    or preference.target is PreferenceTarget.ITEM and preference.ids[0] in plan.item_ids
                    or preference.target is PreferenceTarget.COMBINATION
                    and set(preference.ids).issubset(plan.item_ids)
                )
                if matches:
                    result += int(preference.sentiment) * (
                        3 if preference.actor is PreferenceActor.SOFIA else 1
                    )
            result -= sum(4 for record in recent[-7:] if record.outfit_id == plan.outfit_id)
            return result

        # Stable within a cadence window IF previous verified wear is still
        # activity/season/weather compatible. A weather change may replace it.
        same_period = [w for w in recent if period_key(w.occurred_at.astimezone(context.now.tzinfo), cadence) == key]
        if same_period:
            last = max(same_period, key=lambda w: w.occurred_at.astimezone(timezone.utc))
            prior = self._plans.get(last.outfit_id)
            if prior and any(p.outfit_id == last.outfit_id for p, _ in compatible):
                p = prior[0]
                if context.season in p.seasons and (weather is None or not p.weather or weather in p.weather) and (
                    not p.lounge or context.lounge_window
                ):
                    return OutfitProposal(p.outfit_id, prior[1], key, ("verified_previous_choice",))
        best_plan, best_outfit = sorted(compatible, key=lambda entry: (-score(entry), entry[0].outfit_id))[0]
        reasons = ("covered_candidate", "season_and_activity", "late_lounge" if best_plan.lounge and context.lounge_window else "ordinary_rotation")
        if context.weather is not None and weather is None:
            reasons += ("weather_missing_or_stale",)
        return OutfitProposal(best_plan.outfit_id, best_outfit, key, reasons)


def appraise_clothing_change(
    *, origin: ChangeOrigin, proposed_outfit: Outfit, private_context: bool = False
) -> ClothingAppraisal:
    if not isinstance(origin, ChangeOrigin) or not isinstance(proposed_outfit, Outfit) or type(private_context) is not bool:
        raise WardrobeError("invalid clothing appraisal input")
    uncovered = not proposed_outfit.covered_default
    if origin is ChangeOrigin.UNINTENDED:
        cues = ("surprise", "self_consciousness", "possible_embarrassment") if uncovered else ("surprise", "adjustment")
    elif private_context:
        cues = ("possible_comfort", "confidence", "possible_excitement") if uncovered else ("comfort", "confidence")
    else:
        cues = ("review_privacy", "possible_self_consciousness") if uncovered else ("confidence", "practicality")
    return ClothingAppraisal(origin, cues, requires_covered_recovery=uncovered)
