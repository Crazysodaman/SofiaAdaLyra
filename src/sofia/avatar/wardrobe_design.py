"""Structured garment design vocabulary for Sofía's wardrobe creator.

This module describes what a garment is. It does not claim that an asset exists,
that a garment is currently worn, or that a renderer has displayed it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

from .wardrobe import WardrobeError
from .wardrobe_types import GarmentTypeDefinition, garment_type

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_STYLE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z", re.ASCII)
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\Z")

PALETTE: dict[str, str] = {
    "black": "#0B0D12",
    "charcoal": "#171A21",
    "crimson": "#8B1E3F",
    "dark_violet": "#3A245C",
    "cyan": "#19D3C5",
    "soft_violet": "#6A4C93",
    "silver": "#AAB2BD",
}


def resolve_color(value: str) -> str:
    """Resolve a named palette color or accept an explicit RGB hex."""
    if not isinstance(value, str) or not value.strip():
        raise WardrobeError("color must be nonempty")
    key = value.strip()
    if _HEX.fullmatch(key):
        return key.upper()
    try:
        return PALETTE[key.casefold()]
    except KeyError as exc:
        raise WardrobeError(f"unknown wardrobe color: {value}") from exc


@dataclass(frozen=True, slots=True)
class GraphicDesign:
    enabled: bool = False
    placement: str | None = None
    design: str | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise WardrobeError("graphic enabled flag must be boolean")
        if self.enabled:
            if (
                not isinstance(self.placement, str)
                or not self.placement.strip()
                or not isinstance(self.design, str)
                or not self.design.strip()
            ):
                raise WardrobeError(
                    "enabled graphic requires placement and design"
                )
        elif self.placement is not None or self.design is not None:
            raise WardrobeError(
                "disabled graphic cannot define placement or design"
            )


class Suitability(str, Enum):
    UNSPECIFIED = "unspecified"
    UNSUITABLE = "unsuitable"
    POOR = "poor"
    ACCEPTABLE = "acceptable"
    GOOD = "good"
    EXCELLENT = "excellent"

    @property
    def score(self) -> int:
        return {
            Suitability.UNSPECIFIED: 0,
            Suitability.UNSUITABLE: -8,
            Suitability.POOR: -4,
            Suitability.ACCEPTABLE: 0,
            Suitability.GOOD: 2,
            Suitability.EXCELLENT: 4,
        }[self]


class TraitLevel(str, Enum):
    UNSPECIFIED = "unspecified"
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class FabricWeight(str, Enum):
    UNSPECIFIED = "unspecified"
    ULTRALIGHT = "ultralight"
    LIGHT = "light"
    MIDWEIGHT = "midweight"
    HEAVY = "heavy"


@dataclass(frozen=True, slots=True)
class MaterialProperties:
    stretch: TraitLevel = TraitLevel.UNSPECIFIED
    fabric_weight: FabricWeight = FabricWeight.UNSPECIFIED
    texture: str | None = None
    breathability: TraitLevel = TraitLevel.UNSPECIFIED
    insulation: TraitLevel = TraitLevel.UNSPECIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.stretch, TraitLevel):
            raise WardrobeError("invalid material stretch")
        if not isinstance(self.fabric_weight, FabricWeight):
            raise WardrobeError("invalid fabric weight")
        if self.texture is not None and (
            not isinstance(self.texture, str)
            or not self.texture.strip()
            or len(self.texture) > 120
        ):
            raise WardrobeError("invalid material texture")
        if not isinstance(self.breathability, TraitLevel):
            raise WardrobeError("invalid material breathability")
        if not isinstance(self.insulation, TraitLevel):
            raise WardrobeError("invalid material insulation")

    def as_dict(self) -> dict[str, object]:
        return {
            "stretch": self.stretch.value,
            "fabric_weight": self.fabric_weight.value,
            "texture": self.texture,
            "breathability": self.breathability.value,
            "insulation": self.insulation.value,
        }


@dataclass(frozen=True, slots=True)
class TemperatureProfile:
    minimum_c: float | None = None
    preferred_minimum_c: float | None = None
    preferred_maximum_c: float | None = None
    maximum_c: float | None = None
    thermal_weight: FabricWeight = FabricWeight.UNSPECIFIED

    def __post_init__(self) -> None:
        values = (
            self.minimum_c,
            self.preferred_minimum_c,
            self.preferred_maximum_c,
            self.maximum_c,
        )
        if any(
            value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not -120.0 <= float(value) <= 80.0
            )
            for value in values
        ):
            raise WardrobeError("invalid garment temperature profile")
        specified = tuple(value is not None for value in values)
        if any(specified) and not all(specified):
            raise WardrobeError(
                "temperature profile must define all range values or none"
            )
        if all(specified):
            numeric = tuple(float(value) for value in values)
            if not (
                numeric[0] <= numeric[1]
                <= numeric[2] <= numeric[3]
            ):
                raise WardrobeError("invalid garment temperature range")
        if not isinstance(self.thermal_weight, FabricWeight):
            raise WardrobeError("invalid thermal weight")

    def suitability_for(self, temperature_c: float | None) -> Suitability:
        if temperature_c is None or self.minimum_c is None:
            return Suitability.UNSPECIFIED
        value = float(temperature_c)
        if value < float(self.minimum_c) or value > float(self.maximum_c):
            return Suitability.UNSUITABLE
        if (
            float(self.preferred_minimum_c)
            <= value <= float(self.preferred_maximum_c)
        ):
            return Suitability.EXCELLENT
        return Suitability.ACCEPTABLE

    def as_dict(self) -> dict[str, object]:
        def fahrenheit(value):
            return None if value is None else round(float(value) * 9 / 5 + 32, 1)
        return {
            "minimum_c": self.minimum_c,
            "minimum_f": fahrenheit(self.minimum_c),
            "preferred_minimum_c": self.preferred_minimum_c,
            "preferred_minimum_f": fahrenheit(self.preferred_minimum_c),
            "preferred_maximum_c": self.preferred_maximum_c,
            "preferred_maximum_f": fahrenheit(self.preferred_maximum_c),
            "maximum_c": self.maximum_c,
            "maximum_f": fahrenheit(self.maximum_c),
            "thermal_weight": self.thermal_weight.value,
        }


@dataclass(frozen=True, slots=True)
class PrecipitationProfile:
    dry: Suitability = Suitability.UNSPECIFIED
    mist: Suitability = Suitability.UNSPECIFIED
    drizzle: Suitability = Suitability.UNSPECIFIED
    rain: Suitability = Suitability.UNSPECIFIED
    heavy_rain: Suitability = Suitability.UNSPECIFIED
    snow: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, Suitability)
            for value in (
                self.dry, self.mist, self.drizzle, self.rain,
                self.heavy_rain, self.snow,
            )
        ):
            raise WardrobeError("invalid precipitation suitability")

    def rating(self, condition: str) -> Suitability:
        if condition not in {
            "dry", "mist", "drizzle", "rain", "heavy_rain", "snow"
        }:
            return Suitability.UNSPECIFIED
        return getattr(self, condition)

    def as_dict(self) -> dict[str, str]:
        return {
            name: getattr(self, name).value
            for name in (
                "dry", "mist", "drizzle", "rain", "heavy_rain", "snow"
            )
        }


@dataclass(frozen=True, slots=True)
class MoistureProfile:
    quick_dry: bool | None = None
    water_resistance: TraitLevel = TraitLevel.UNSPECIFIED
    absorbency: TraitLevel = TraitLevel.UNSPECIFIED
    wet_comfort: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if self.quick_dry is not None and type(self.quick_dry) is not bool:
            raise WardrobeError("quick_dry must be boolean or None")
        if not isinstance(self.water_resistance, TraitLevel):
            raise WardrobeError("invalid water resistance")
        if not isinstance(self.absorbency, TraitLevel):
            raise WardrobeError("invalid absorbency")
        if not isinstance(self.wet_comfort, Suitability):
            raise WardrobeError("invalid wet comfort")

    def as_dict(self) -> dict[str, object]:
        return {
            "quick_dry": self.quick_dry,
            "water_resistance": self.water_resistance.value,
            "absorbency": self.absorbency.value,
            "wet_comfort": self.wet_comfort.value,
        }


@dataclass(frozen=True, slots=True)
class HumidityProfile:
    low: Suitability = Suitability.UNSPECIFIED
    moderate: Suitability = Suitability.UNSPECIFIED
    high: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, Suitability)
            for value in (self.low, self.moderate, self.high)
        ):
            raise WardrobeError("invalid humidity suitability")

    def rating(self, humidity_percent: float | None) -> Suitability:
        if humidity_percent is None:
            return Suitability.UNSPECIFIED
        value = float(humidity_percent)
        if value < 35.0:
            return self.low
        if value <= 70.0:
            return self.moderate
        return self.high

    def as_dict(self) -> dict[str, str]:
        return {
            "low": self.low.value,
            "moderate": self.moderate.value,
            "high": self.high.value,
        }


@dataclass(frozen=True, slots=True)
class WindProfile:
    resistance: TraitLevel = TraitLevel.UNSPECIFIED
    strong_wind: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.resistance, TraitLevel):
            raise WardrobeError("invalid wind resistance")
        if not isinstance(self.strong_wind, Suitability):
            raise WardrobeError("invalid strong-wind suitability")

    def as_dict(self) -> dict[str, str]:
        return {
            "resistance": self.resistance.value,
            "strong_wind": self.strong_wind.value,
        }


@dataclass(frozen=True, slots=True)
class SunlightProfile:
    direct_sun: Suitability = Suitability.UNSPECIFIED
    uv_protection: TraitLevel = TraitLevel.UNSPECIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.direct_sun, Suitability):
            raise WardrobeError("invalid direct-sun suitability")
        if not isinstance(self.uv_protection, TraitLevel):
            raise WardrobeError("invalid UV protection")

    def as_dict(self) -> dict[str, str]:
        return {
            "direct_sun": self.direct_sun.value,
            "uv_protection": self.uv_protection.value,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentProfile:
    temperature: TemperatureProfile = field(default_factory=TemperatureProfile)
    precipitation: PrecipitationProfile = field(default_factory=PrecipitationProfile)
    moisture: MoistureProfile = field(default_factory=MoistureProfile)
    humidity: HumidityProfile = field(default_factory=HumidityProfile)
    wind: WindProfile = field(default_factory=WindProfile)
    sunlight: SunlightProfile = field(default_factory=SunlightProfile)
    indoor: Suitability = Suitability.UNSPECIFIED
    outdoor: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.temperature, TemperatureProfile):
            raise WardrobeError("invalid temperature profile")
        if not isinstance(self.precipitation, PrecipitationProfile):
            raise WardrobeError("invalid precipitation profile")
        if not isinstance(self.moisture, MoistureProfile):
            raise WardrobeError("invalid moisture profile")
        if not isinstance(self.humidity, HumidityProfile):
            raise WardrobeError("invalid humidity profile")
        if not isinstance(self.wind, WindProfile):
            raise WardrobeError("invalid wind profile")
        if not isinstance(self.sunlight, SunlightProfile):
            raise WardrobeError("invalid sunlight profile")
        if not isinstance(self.indoor, Suitability) or not isinstance(self.outdoor, Suitability):
            raise WardrobeError("invalid indoor/outdoor suitability")

    def as_dict(self) -> dict[str, object]:
        return {
            "temperature": self.temperature.as_dict(),
            "precipitation": self.precipitation.as_dict(),
            "moisture": self.moisture.as_dict(),
            "humidity": self.humidity.as_dict(),
            "wind": self.wind.as_dict(),
            "sunlight": self.sunlight.as_dict(),
            "indoor": self.indoor.value,
            "outdoor": self.outdoor.value,
        }


@dataclass(frozen=True, slots=True)
class RatedContext:
    excellent: tuple[str, ...] = ()
    good: tuple[str, ...] = ()
    acceptable: tuple[str, ...] = ()
    poor: tuple[str, ...] = ()
    unsuitable: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        groups = (
            self.excellent,
            self.good,
            self.acceptable,
            self.poor,
            self.unsuitable,
        )
        flattened = []
        for group in groups:
            if not isinstance(group, tuple):
                raise WardrobeError("context ratings must use tuples")
            for value in group:
                if not isinstance(value, str) or _STYLE.fullmatch(value) is None:
                    raise WardrobeError("invalid context rating value")
                flattened.append(value)
        if len(flattened) != len(set(flattened)):
            raise WardrobeError("context rating values cannot overlap")

    def rating(self, value: str | None) -> Suitability:
        if value is None:
            return Suitability.UNSPECIFIED
        for level, values in (
            (Suitability.EXCELLENT, self.excellent),
            (Suitability.GOOD, self.good),
            (Suitability.ACCEPTABLE, self.acceptable),
            (Suitability.POOR, self.poor),
            (Suitability.UNSUITABLE, self.unsuitable),
        ):
            if value in values:
                return level
        return Suitability.UNSPECIFIED

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "excellent": list(self.excellent),
            "good": list(self.good),
            "acceptable": list(self.acceptable),
            "poor": list(self.poor),
            "unsuitable": list(self.unsuitable),
        }


@dataclass(frozen=True, slots=True)
class MovementProfile:
    mobility: Suitability = Suitability.UNSPECIFIED
    seated_comfort: Suitability = Suitability.UNSPECIFIED
    active_comfort: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, Suitability)
            for value in (
                self.mobility,
                self.seated_comfort,
                self.active_comfort,
            )
        ):
            raise WardrobeError("invalid movement suitability")

    def as_dict(self) -> dict[str, str]:
        return {
            "mobility": self.mobility.value,
            "seated_comfort": self.seated_comfort.value,
            "active_comfort": self.active_comfort.value,
        }


@dataclass(frozen=True, slots=True)
class ContextProfile:
    dayparts: RatedContext = field(default_factory=RatedContext)
    seasons: RatedContext = field(default_factory=RatedContext)
    activities: RatedContext = field(default_factory=RatedContext)
    settings: RatedContext = field(default_factory=RatedContext)
    formality: RatedContext = field(default_factory=RatedContext)
    emotion_styles: RatedContext = field(default_factory=RatedContext)
    movement: MovementProfile = field(default_factory=MovementProfile)

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, RatedContext)
            for value in (
                self.dayparts,
                self.seasons,
                self.activities,
                self.settings,
                self.formality,
                self.emotion_styles,
            )
        ):
            raise WardrobeError("invalid rated garment context")
        if not isinstance(self.movement, MovementProfile):
            raise WardrobeError("invalid movement profile")

    def as_dict(self) -> dict[str, object]:
        return {
            "dayparts": self.dayparts.as_dict(),
            "seasons": self.seasons.as_dict(),
            "activities": self.activities.as_dict(),
            "settings": self.settings.as_dict(),
            "formality": self.formality.as_dict(),
            "emotion_styles": self.emotion_styles.as_dict(),
            "movement": self.movement.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class ComfortProfile:
    softness: TraitLevel = TraitLevel.UNSPECIFIED
    flexibility: TraitLevel = TraitLevel.UNSPECIFIED
    compression: TraitLevel = TraitLevel.UNSPECIFIED
    heat_retention: TraitLevel = TraitLevel.UNSPECIFIED
    ventilation: TraitLevel = TraitLevel.UNSPECIFIED
    skin_contact: Suitability = Suitability.UNSPECIFIED

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, TraitLevel)
            for value in (
                self.softness,
                self.flexibility,
                self.compression,
                self.heat_retention,
                self.ventilation,
            )
        ):
            raise WardrobeError("invalid comfort trait level")
        if not isinstance(self.skin_contact, Suitability):
            raise WardrobeError("invalid skin-contact suitability")

    def as_dict(self) -> dict[str, str]:
        return {
            "softness": self.softness.value,
            "flexibility": self.flexibility.value,
            "compression": self.compression.value,
            "heat_retention": self.heat_retention.value,
            "ventilation": self.ventilation.value,
            "skin_contact": self.skin_contact.value,
        }


@dataclass(frozen=True, slots=True)
class GarmentDesign:
    """Creator-facing structured design for one actual wardrobe piece."""

    item_id: str
    name: str
    garment_type: str
    fit: str
    rise: str | None
    length: str
    sleeve_length: str | None
    material: str
    primary: str
    accent: str | None
    pattern: str
    graphic: GraphicDesign
    features: tuple[str, ...]
    style_tags: tuple[str, ...] = ()
    private_only: bool = False
    description: str = ""
    material_properties: MaterialProperties = field(
        default_factory=MaterialProperties
    )
    environment: EnvironmentProfile = field(
        default_factory=EnvironmentProfile
    )
    context: ContextProfile = field(default_factory=ContextProfile)
    comfort: ComfortProfile = field(default_factory=ComfortProfile)

    def __post_init__(self) -> None:
        for value, label in (
            (self.item_id, "item ID"),
            (self.garment_type, "garment type"),
            (self.fit, "fit"),
            (self.length, "length"),
        ):
            if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
                raise WardrobeError(f"invalid {label}")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 160:
            raise WardrobeError("invalid garment name")
        if self.rise is not None and (
            not isinstance(self.rise, str) or _STYLE.fullmatch(self.rise) is None
        ):
            raise WardrobeError("invalid garment rise")
        if self.sleeve_length is not None and (
            not isinstance(self.sleeve_length, str)
            or _STYLE.fullmatch(self.sleeve_length) is None
        ):
            raise WardrobeError("invalid sleeve length")
        if not isinstance(self.material, str) or not self.material.strip():
            raise WardrobeError("material is required")
        resolve_color(self.primary)
        if self.accent is not None:
            resolve_color(self.accent)
        if not isinstance(self.pattern, str) or not self.pattern.strip():
            raise WardrobeError("pattern is required")
        if not isinstance(self.graphic, GraphicDesign):
            raise WardrobeError("graphic must be GraphicDesign")
        for values, label in (
            (self.features, "features"),
            (self.style_tags, "style tags"),
        ):
            if (
                not isinstance(values, tuple)
                or len(set(values)) != len(values)
                or any(
                    not isinstance(value, str)
                    or _STYLE.fullmatch(value) is None
                    for value in values
                )
            ):
                raise WardrobeError(f"invalid {label}")
        if type(self.private_only) is not bool:
            raise WardrobeError("private_only must be boolean")
        if not isinstance(self.material_properties, MaterialProperties):
            raise WardrobeError("invalid material properties")
        if not isinstance(self.environment, EnvironmentProfile):
            raise WardrobeError("invalid garment environment profile")
        if not isinstance(self.context, ContextProfile):
            raise WardrobeError("invalid garment context profile")
        if not isinstance(self.comfort, ComfortProfile):
            raise WardrobeError("invalid garment comfort profile")
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
            or len(self.description) > 1600
        ):
            raise WardrobeError("description must be bounded nonempty text")


def validate_design(design: GarmentDesign) -> GarmentTypeDefinition:
    """Validate type-specific fields and return the resolved type definition."""
    if not isinstance(design, GarmentDesign):
        raise TypeError("design must be GarmentDesign")
    definition = garment_type(design.garment_type)
    if definition.supports_rise:
        if design.rise is None:
            raise WardrobeError(
                f"{design.garment_type} requires rise"
            )
    elif design.rise is not None:
        raise WardrobeError(
            f"{design.garment_type} does not support rise"
        )
    if definition.supports_sleeve_length:
        if design.sleeve_length is None:
            raise WardrobeError(
                f"{design.garment_type} requires sleeve_length"
            )
    elif design.sleeve_length is not None:
        raise WardrobeError(
            f"{design.garment_type} does not support sleeve_length"
        )
    if design.graphic.enabled and not definition.supports_graphic:
        raise WardrobeError(
            f"{design.garment_type} does not support graphics"
        )
    return definition
