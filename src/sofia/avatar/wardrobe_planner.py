"""Offline wardrobe planning and *proposals*: no renderer, weather fetch, scheduler or emotion claims.

The trusted host supplies local time, observed weather, audience and source IDs.
No garment is shown or recorded as worn by the planner. Automatic proposals
are covered, non-private outfits, even for an authenticated private session.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum

from sofia.environment.model import (
    DaylightState,
    EnvironmentFreshness,
    EnvironmentSnapshot,
    Season,
)
from sofia.personality.influence import ContinuityInfluence

from .wardrobe import Wardrobe, WardrobeError, Outfit
from .wardrobe_design import GarmentDesign, Suitability


class Activity(str, Enum):
    CONVERSATION = "conversation"
    ENGINEERING = "engineering"
    LAB = "lab"
    RELAXING = "relaxing"
    SLEEP = "sleep"
    FORMAL = "formal"
    EXERCISE = "exercise"
    GAMING = "gaming"
    CASUAL = "casual"
    OUTDOOR = "outdoor"
    WORKSHOP = "workshop"
    TRAVEL = "travel"


class Weather(str, Enum):
    HOT = "hot"
    COLD = "cold"
    WET = "wet"
    MILD = "mild"


class EnvironmentMode(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class WearSetting(str, Enum):
    HOME = "home"
    PRIVATE = "private"
    CASUAL_PUBLIC = "casual_public"
    WORKSHOP = "workshop"
    LAB = "lab"
    OFFICE = "office"
    OUTDOOR = "outdoor"
    FORMAL_EVENT = "formal_event"


class Formality(str, Enum):
    LOUNGE = "lounge"
    CASUAL = "casual"
    WORK = "work"
    SMART_CASUAL = "smart_casual"
    FORMAL = "formal"


class MovementDemand(str, Enum):
    REST = "rest"
    SEATED = "seated"
    LIGHT = "light"
    ACTIVE = "active"
    HIGH_MOBILITY = "high_mobility"


class SunExposure(str, Enum):
    SHADE = "shade"
    INDIRECT = "indirect"
    DIRECT = "direct"


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
class EmotionStyleInfluence:
    """Trusted modeled-emotion evidence that may gently bias style selection.

    The host maps an already-grounded modeled emotion to presentation style
    tags. AVATAR does not infer emotion from user text. Influence is bounded
    so it cannot override privacy, coverage, activity compatibility or season.
    """

    emotion: str
    intensity: float
    style_tags: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.emotion, str) or not self.emotion.strip() or len(self.emotion) > 64:
            raise WardrobeError("invalid emotion influence name")
        if isinstance(self.intensity, bool) or not isinstance(self.intensity, (int, float)):
            raise WardrobeError("emotion influence intensity must be numeric")
        if not 0.0 <= float(self.intensity) <= 1.0:
            raise WardrobeError("emotion influence intensity must be between zero and one")
        if (
            not isinstance(self.style_tags, tuple)
            or not self.style_tags
            or len(set(self.style_tags)) != len(self.style_tags)
            or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 64 for tag in self.style_tags)
        ):
            raise WardrobeError("invalid emotion style tags")
        if (
            not isinstance(self.evidence_refs, tuple)
            or not self.evidence_refs
            or len(set(self.evidence_refs)) != len(self.evidence_refs)
            or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 160 for ref in self.evidence_refs)
        ):
            raise WardrobeError("emotion influence requires bounded evidence refs")


@dataclass(frozen=True, slots=True)
class WardrobeContext:
    now: datetime
    season: Season
    activity: Activity
    weather: WeatherObservation | None = None
    emotion_influences: tuple[EmotionStyleInfluence, ...] = ()
    outdoor_temperature_c: float | None = None
    feels_like_c: float | None = None
    outdoor_humidity_percent: float | None = None
    wind_kph: float | None = None
    precipitation_mm: float | None = None
    weather_condition: str | None = None
    daylight_state: DaylightState | None = None
    indoor_temperature_c: float | None = None
    indoor_humidity_percent: float | None = None
    environment_mode: EnvironmentMode | None = None
    setting: WearSetting | None = None
    formality: Formality | None = None
    movement: MovementDemand | None = None
    sun_exposure: SunExposure | None = None

    def __post_init__(self) -> None:
        _aware(self.now)
        if not isinstance(self.season, Season) or not isinstance(self.activity, Activity):
            raise WardrobeError("season and activity must be typed")
        if self.weather is not None and not isinstance(self.weather, WeatherObservation):
            raise WardrobeError("invalid weather evidence")
        if (
            not isinstance(self.emotion_influences, tuple)
            or any(not isinstance(item, EmotionStyleInfluence) for item in self.emotion_influences)
        ):
            raise WardrobeError("invalid emotion influences")
        numeric_bounds = {
            "outdoor_temperature_c": (-120.0, 80.0),
            "feels_like_c": (-120.0, 80.0),
            "outdoor_humidity_percent": (0.0, 100.0),
            "wind_kph": (0.0, 600.0),
            "precipitation_mm": (0.0, 5000.0),
            "indoor_temperature_c": (-80.0, 80.0),
            "indoor_humidity_percent": (0.0, 100.0),
        }
        for name, (minimum, maximum) in numeric_bounds.items():
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise WardrobeError(f"{name} must be numeric or None")
            if not minimum <= float(value) <= maximum:
                raise WardrobeError(f"{name} outside supported bounds")
        if self.weather_condition is not None and (
            not isinstance(self.weather_condition, str)
            or not self.weather_condition.strip()
            or len(self.weather_condition) > 80
        ):
            raise WardrobeError("invalid weather condition")
        for value, expected, label in (
            (self.daylight_state, DaylightState, "daylight state"),
            (self.environment_mode, EnvironmentMode, "environment mode"),
            (self.setting, WearSetting, "wear setting"),
            (self.formality, Formality, "formality"),
            (self.movement, MovementDemand, "movement demand"),
            (self.sun_exposure, SunExposure, "sun exposure"),
        ):
            if value is not None and not isinstance(value, expected):
                raise WardrobeError(f"invalid {label}")

    @classmethod
    def from_environment_snapshot(
        cls,
        snapshot: EnvironmentSnapshot,
        *,
        activity: Activity,
        emotion_influences: tuple[EmotionStyleInfluence, ...] = (),
        environment_mode: EnvironmentMode | None = None,
        setting: WearSetting | None = None,
        formality: Formality | None = None,
        movement: MovementDemand | None = None,
        sun_exposure: SunExposure | None = None,
    ) -> "WardrobeContext":
        """Adapt canonical ENVIRONMENT evidence for wardrobe planning."""
        if not isinstance(snapshot, EnvironmentSnapshot):
            raise WardrobeError("snapshot must be EnvironmentSnapshot")
        if not isinstance(activity, Activity):
            raise WardrobeError("activity must be Activity")
        if snapshot.season is None:
            raise WardrobeError(
                "environment snapshot has no grounded season"
            )

        weather = None
        source = snapshot.weather
        current_weather = (
            source
            if (
                source is not None
                and snapshot.weather_freshness is EnvironmentFreshness.CURRENT
            )
            else None
        )
        if current_weather is not None:
            condition = current_weather.condition.casefold()
            wet_tokens = (
                "rain", "shower", "drizzle", "thunder",
                "storm", "hail", "sleet", "pour",
            )
            cold_tokens = ("snow", "ice", "frost", "freez")
            temperature = (
                current_weather.feels_like_c
                if current_weather.feels_like_c is not None
                else current_weather.temperature_c
            )
            if any(token in condition for token in wet_tokens):
                wardrobe_weather = Weather.WET
            elif (
                any(token in condition for token in cold_tokens)
                or (temperature is not None and temperature <= 10.0)
            ):
                wardrobe_weather = Weather.COLD
            elif temperature is not None and temperature >= 27.0:
                wardrobe_weather = Weather.HOT
            else:
                wardrobe_weather = Weather.MILD
            weather = WeatherObservation(
                condition=wardrobe_weather,
                observed_at=current_weather.observed_at,
                source_id=current_weather.source_id,
            )

        indoor = (
            snapshot.indoor
            if (
                snapshot.indoor is not None
                and snapshot.indoor_freshness is EnvironmentFreshness.CURRENT
            )
            else None
        )
        return cls(
            now=snapshot.user_local_time or snapshot.host_local_time,
            season=snapshot.season,
            activity=activity,
            weather=weather,
            emotion_influences=emotion_influences,
            outdoor_temperature_c=(
                None if current_weather is None
                else current_weather.temperature_c
            ),
            feels_like_c=(
                None if current_weather is None
                else current_weather.feels_like_c
            ),
            outdoor_humidity_percent=(
                None if current_weather is None
                else current_weather.humidity_percent
            ),
            wind_kph=(
                None if current_weather is None
                else current_weather.wind_kph
            ),
            precipitation_mm=(
                None if current_weather is None
                else current_weather.precipitation_mm
            ),
            weather_condition=(
                None if current_weather is None
                else current_weather.condition
            ),
            daylight_state=(
                None if snapshot.daylight is None
                else snapshot.daylight.state
            ),
            indoor_temperature_c=(
                None if indoor is None else indoor.temperature_c
            ),
            indoor_humidity_percent=(
                None if indoor is None else indoor.humidity_percent
            ),
            environment_mode=environment_mode,
            setting=setting,
            formality=formality,
            movement=movement,
            sun_exposure=sun_exposure,
        )

    @property
    def effective_weather(self) -> Weather | None:
        if self.weather is not None:
            age = (
                self.now.astimezone(timezone.utc)
                - self.weather.observed_at.astimezone(timezone.utc)
            )
            if timedelta(0) <= age <= timedelta(hours=6):
                return self.weather.condition

        condition = (self.weather_condition or "").casefold()
        temperature = self.effective_temperature_c
        if any(
            token in condition
            for token in (
                "rain",
                "shower",
                "drizzle",
                "thunder",
                "storm",
                "hail",
                "sleet",
                "pour",
            )
        ):
            return Weather.WET
        if (
            any(
                token in condition
                for token in ("snow", "ice", "frost", "freez")
            )
            or (
                temperature is not None
                and temperature <= 10.0
            )
        ):
            return Weather.COLD
        if temperature is not None and temperature >= 27.0:
            return Weather.HOT
        if self.weather_condition is not None or temperature is not None:
            return Weather.MILD
        return None

    @property
    def effective_temperature_c(self) -> float | None:
        if (
            self.environment_mode is EnvironmentMode.INDOOR
            and self.indoor_temperature_c is not None
        ):
            return float(self.indoor_temperature_c)
        if self.feels_like_c is not None:
            return float(self.feels_like_c)
        if self.outdoor_temperature_c is not None:
            return float(self.outdoor_temperature_c)
        return None

    @property
    def effective_humidity_percent(self) -> float | None:
        if (
            self.environment_mode is EnvironmentMode.INDOOR
            and self.indoor_humidity_percent is not None
        ):
            return float(self.indoor_humidity_percent)
        if self.outdoor_humidity_percent is not None:
            return float(self.outdoor_humidity_percent)
        return None

    @property
    def precipitation_kind(self) -> str | None:
        condition = (self.weather_condition or "").casefold()
        amount = self.precipitation_mm
        if any(token in condition for token in ("snow", "sleet", "ice")):
            return "snow"
        if any(token in condition for token in ("downpour", "heavy rain", "pour", "storm", "thunder")):
            return "heavy_rain"
        if "drizzle" in condition:
            return "drizzle"
        if any(token in condition for token in ("mist", "fog")):
            return "mist"
        if any(token in condition for token in ("rain", "shower")):
            return "rain"
        if amount is not None:
            if amount >= 10.0:
                return "heavy_rain"
            if amount > 0.0:
                return "drizzle"
        if self.weather_condition is not None:
            return "dry"
        return None

    @property
    def daypart(self) -> str:
        hour = self.now.hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 21:
            return "evening"
        if 21 <= hour <= 23:
            return "night"
        return "late_night"

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
    display_name: str | None = None
    manual_only: bool = False

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
        if (
            type(self.lounge) is not bool
            or type(self.private_only) is not bool
            or type(self.manual_only) is not bool
        ):
            raise WardrobeError("outfit flags must be boolean")
        if not isinstance(self.style_tags, tuple) or any(
            not isinstance(tag, str) or not tag.strip() or len(tag) > 64 for tag in self.style_tags
        ):
            raise WardrobeError("invalid style tags")
        if self.display_name is not None and (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
            or len(self.display_name) > 160
        ):
            raise WardrobeError("invalid outfit display name")


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

    def __init__(
        self,
        wardrobe: Wardrobe,
        plans: tuple[OutfitPlan, ...],
        *,
        designs: dict[str, GarmentDesign] | None = None,
    ):
        if not isinstance(wardrobe, Wardrobe) or not isinstance(plans, tuple) or not plans:
            raise WardrobeError("wardrobe and nonempty outfit plans are required")
        if any(not isinstance(plan, OutfitPlan) for plan in plans):
            raise WardrobeError("invalid outfit plan")
        if len({plan.outfit_id for plan in plans}) != len(plans):
            raise WardrobeError("duplicate outfit ID")
        if designs is None:
            designs = {}
        if (
            not isinstance(designs, dict)
            or any(
                not isinstance(item_id, str)
                or not isinstance(design, GarmentDesign)
                or design.item_id != item_id
                for item_id, design in designs.items()
            )
        ):
            raise WardrobeError("invalid garment design map")
        self._wardrobe = wardrobe
        self._designs = dict(designs)
        self._plans: dict[str, tuple[OutfitPlan, Outfit]] = {}
        for plan in plans:
            outfit = wardrobe.selection(plan.item_ids)
            if plan.private_only or plan.manual_only:
                # Private/manual outfits require an explicit selection workflow.
                continue
            if outfit.private_only:
                raise WardrobeError(
                    "automatic outfit cannot contain private-only garments"
                )
            if not outfit.covered_default:
                raise WardrobeError("automatic outfit must cover torso and pelvis")
            self._plans[plan.outfit_id] = plan, outfit
        if not self._plans:
            raise WardrobeError("no covered automatic outfits")

    @staticmethod
    def _movement_rating(design: GarmentDesign, demand: MovementDemand | None) -> Suitability:
        if demand is None:
            return Suitability.UNSPECIFIED
        movement = design.context.movement
        if demand in (MovementDemand.REST, MovementDemand.SEATED):
            return movement.seated_comfort
        if demand is MovementDemand.HIGH_MOBILITY:
            return min(
                (movement.mobility, movement.active_comfort),
                key=lambda item: item.score,
            )
        return movement.active_comfort

    @staticmethod
    def _design_score(
        design: GarmentDesign,
        context: WardrobeContext,
    ) -> tuple[int, bool]:
        """Return bounded item score and whether physical evidence says unsuitable."""
        result = 0
        physically_unsuitable = False
        environment = design.environment
        preferences = design.context

        temperature = environment.temperature.suitability_for(
            context.effective_temperature_c
        )
        if temperature is Suitability.UNSUITABLE:
            physically_unsuitable = True
        result += temperature.score * 3

        precipitation = environment.precipitation.rating(
            context.precipitation_kind or ""
        )
        if precipitation is Suitability.UNSUITABLE:
            physically_unsuitable = True
        result += precipitation.score * 3

        humidity = environment.humidity.rating(
            context.effective_humidity_percent
        )
        result += humidity.score

        if context.wind_kph is not None and context.wind_kph >= 35.0:
            wind = environment.wind.strong_wind
            if wind is Suitability.UNSUITABLE:
                physically_unsuitable = True
            result += wind.score * 2

        if context.environment_mode is EnvironmentMode.INDOOR:
            result += environment.indoor.score * 2
        elif context.environment_mode is EnvironmentMode.OUTDOOR:
            result += environment.outdoor.score * 2

        if context.sun_exposure is SunExposure.DIRECT:
            result += environment.sunlight.direct_sun.score

        result += preferences.dayparts.rating(context.daypart).score
        result += preferences.seasons.rating(context.season.value).score
        result += preferences.activities.rating(context.activity.value).score * 2
        result += preferences.settings.rating(
            None if context.setting is None else context.setting.value
        ).score * 2
        result += preferences.formality.rating(
            None if context.formality is None else context.formality.value
        ).score * 2
        result += OutfitPlanner._movement_rating(
            design,
            context.movement,
        ).score * 2

        emotion_bias = 0.0
        for influence in context.emotion_influences:
            candidates = (influence.emotion,) + influence.style_tags
            best = max(
                (
                    preferences.emotion_styles.rating(value).score
                    for value in candidates
                ),
                default=0,
            )
            if best > 0:
                emotion_bias += best * float(influence.intensity)
        result += min(3, round(emotion_bias))
        return result, physically_unsuitable

    def _outfit_profile_score(
        self,
        plan: OutfitPlan,
        context: WardrobeContext,
    ) -> tuple[int, bool]:
        scored = [
            self._design_score(design, context)
            for item_id in plan.item_ids
            if (design := self._designs.get(item_id)) is not None
        ]
        if not scored:
            return 0, False
        average = round(sum(score for score, _ in scored) / len(scored))
        physically_unsuitable = any(flag for _, flag in scored)
        if physically_unsuitable:
            average -= 8
        return average, physically_unsuitable

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
            (plan, outfit)
            for plan, outfit in self._plans.values()
            if context.activity in plan.activities
            and not (
                plan.lounge
                and "night" in plan.style_tags
                and not context.lounge_window
            )
        ]
        if not compatible:
            raise WardrobeError(
                "no activity-compatible covered outfit; "
                "host must use verified fallback"
            )

        recent = tuple(sorted((w for w in worn if timedelta(0) <= (
            context.now.astimezone(timezone.utc) - w.occurred_at.astimezone(timezone.utc)
        ) <= timedelta(days=90)), key=lambda w: (w.occurred_at.astimezone(timezone.utc), w.renderer_receipt_id)))
        weather = context.effective_weather

        def score(entry: tuple[OutfitPlan, Outfit]) -> int:
            plan, _ = entry
            result = 6 if context.season in plan.seasons else -6
            profile_score, _ = self._outfit_profile_score(plan, context)
            result += profile_score
            # Profile and outfit-tag scoring share one grounded emotion budget.
            neutral_score, _ = self._outfit_profile_score(
                plan, replace(context, emotion_influences=())
            ) if context.emotion_influences else (profile_score, False)
            profile_emotion_bias = max(0, profile_score - neutral_score)
            if plan.weather:
                if weather is None:
                    # Do not choose a weather-specialized outfit from missing
                    # or stale weather evidence merely because IDs sort first.
                    result -= 1
                else:
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
            # Emotion is intentionally a small bounded influence, never a
            # deterministic outfit switch. Even many active emotions can add
            # at most three points, below activity/season and strong reviewed
            # Sofía preference signals.
            emotion_bias = 0.0
            plan_tags = set(plan.style_tags)
            for influence in context.emotion_influences:
                if plan_tags.intersection(influence.style_tags):
                    emotion_bias += float(influence.intensity)
            result += min(max(0, 3 - profile_emotion_bias), round(emotion_bias * 3))
            result -= sum(4 for record in recent[-7:] if record.outfit_id == plan.outfit_id)
            return result

        # Stable within a cadence window IF previous verified wear is still
        # activity/weather/physical-context compatible. Season is a preference,
        # not a veto; actual measured conditions may outweigh the calendar.
        same_period = [w for w in recent if period_key(w.occurred_at.astimezone(context.now.tzinfo), cadence) == key]
        if same_period:
            last = max(same_period, key=lambda w: w.occurred_at.astimezone(timezone.utc))
            prior = self._plans.get(last.outfit_id)
            if prior and any(p.outfit_id == last.outfit_id for p, _ in compatible):
                p = prior[0]
                _, physically_unsuitable = self._outfit_profile_score(
                    p,
                    context,
                )
                if (weather is None or not p.weather or weather in p.weather) and (
                    not p.lounge or context.lounge_window
                ) and not physically_unsuitable:
                    return OutfitProposal(p.outfit_id, prior[1], key, ("verified_previous_choice",))
        best_plan, best_outfit = sorted(compatible, key=lambda entry: (-score(entry), entry[0].outfit_id))[0]
        reasons = ("covered_candidate", "season_and_activity", "late_lounge" if best_plan.lounge and context.lounge_window else "ordinary_rotation")
        if self._designs:
            reasons += ("garment_environment_context",)
        if any(set(best_plan.style_tags).intersection(item.style_tags) for item in context.emotion_influences):
            reasons += ("modeled_emotion_influence",)
        if context.weather is not None and weather is None:
            reasons += ("weather_missing_or_stale",)
        return OutfitProposal(best_plan.outfit_id, best_outfit, key, reasons)


def wardrobe_emotion_influences(
    influence: ContinuityInfluence,
) -> tuple[EmotionStyleInfluence, ...]:
    """Translate grounded modeled emotion into bounded wardrobe style bias."""
    if not isinstance(influence, ContinuityInfluence):
        raise TypeError("influence must be ContinuityInfluence")
    if (
        influence.primary_emotion is None
        or influence.primary_intensity < 0.20
        or not influence.primary_emotion_evidence_refs
    ):
        return ()

    emotion = influence.primary_emotion
    if emotion in {"joy", "excitement", "playfulness", "amusement"}:
        tags = ("playful", "bright")
    elif emotion in {"fondness", "affection", "warmth", "tenderness"}:
        tags = ("soft", "cozy")
    elif emotion in {"determination", "frustration", "anger"}:
        tags = ("focused", "practical")
    elif emotion in {"bashfulness", "embarrassment", "nervousness"}:
        tags = ("soft", "reserved")
    else:
        tags = ("contextual",)

    return (
        EmotionStyleInfluence(
            emotion=emotion,
            intensity=influence.primary_intensity,
            style_tags=tags,
            evidence_refs=influence.primary_emotion_evidence_refs,
        ),
    )
