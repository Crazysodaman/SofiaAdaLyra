"""Bounded adaptive desktop theming from trusted Sofía state.

Themes are presentation only. They do not change identity, personality,
authority, memories, emotional state, outfit selection, or environment facts.
No model output may directly set arbitrary colors through this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from sofia.avatar.presentation import PresentationProjection
from sofia.environment.model import (
    DaylightState,
    EnvironmentFreshness,
    EnvironmentSnapshot,
)
from sofia.personality.emotion import CurrentEmotionalState


_HEX = re.compile(r"#[0-9A-Fa-f]{6}\Z")

_CANONICAL = {
    "background": "#000000",
    "panel": "#0B0D12",
    "primary": "#9400D3",
    "secondary": "#00C2FF",
    "tertiary": "#39FF14",
    "text": "#E8E8EE",
    "muted": "#9A9AAA",
}

_NAMED_APPEARANCE_COLORS = {
    "deep crimson": "#8B1E3F",
    "dark violet": "#9400D3",
    "electric cyan": "#00C2FF",
}


@dataclass(frozen=True, slots=True)
class ThemeSignals:
    local_time: datetime
    daylight: DaylightState | None = None
    weather_condition: str | None = None
    outfit_id: str | None = None
    appearance_tags: tuple[str, ...] = ()
    hair_color: str | None = None
    tail_color: str | None = None
    emotional_tone: str | None = None
    primary_emotion: str | None = None
    primary_emotion_intensity: float = 0.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.local_time, datetime)
            or self.local_time.tzinfo is None
            or self.local_time.utcoffset() is None
        ):
            raise ValueError("local_time must be timezone-aware")
        if self.daylight is not None and not isinstance(
            self.daylight, DaylightState
        ):
            raise TypeError("daylight must be DaylightState or None")
        if self.weather_condition is not None and not isinstance(
            self.weather_condition, str
        ):
            raise TypeError("weather_condition must be a string or None")
        if self.outfit_id is not None and not isinstance(
            self.outfit_id, str
        ):
            raise TypeError("outfit_id must be a string or None")
        if not isinstance(self.appearance_tags, tuple) or any(
            not isinstance(tag, str) for tag in self.appearance_tags
        ):
            raise TypeError("appearance_tags must be a tuple of strings")
        if self.emotional_tone is not None and not isinstance(
            self.emotional_tone, str
        ):
            raise TypeError("emotional_tone must be a string or None")
        if self.primary_emotion is not None and not isinstance(
            self.primary_emotion, str
        ):
            raise TypeError("primary_emotion must be a string or None")
        if (
            isinstance(self.primary_emotion_intensity, bool)
            or not isinstance(
                self.primary_emotion_intensity,
                (int, float),
            )
            or not 0.0 <= float(
                self.primary_emotion_intensity
            ) <= 1.0
        ):
            raise ValueError(
                "primary_emotion_intensity must be between 0 and 1"
            )


@dataclass(frozen=True, slots=True)
class ThemePalette:
    name: str
    background: str
    panel: str
    primary: str
    secondary: str
    tertiary: str
    text: str
    muted: str
    drivers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("theme name must be nonempty")
        for field_name in (
            "background",
            "panel",
            "primary",
            "secondary",
            "tertiary",
            "text",
            "muted",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or _HEX.fullmatch(value) is None:
                raise ValueError(
                    f"{field_name} must be a six-digit hex color"
                )
        if not isinstance(self.drivers, tuple) or any(
            not isinstance(driver, str) or not driver
            for driver in self.drivers
        ):
            raise ValueError("drivers must be nonempty strings")


def _appearance_hex(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if _HEX.fullmatch(value):
        return value.upper()
    return _NAMED_APPEARANCE_COLORS.get(normalized)


def theme_signals_from_sources(
    *,
    environment: EnvironmentSnapshot,
    presentation: PresentationProjection | None,
    emotion: CurrentEmotionalState | None,
) -> ThemeSignals:
    """Convert authoritative source objects into bounded presentation signals."""
    if not isinstance(environment, EnvironmentSnapshot):
        raise TypeError("environment must be EnvironmentSnapshot")
    if presentation is not None and not isinstance(
        presentation, PresentationProjection
    ):
        raise TypeError(
            "presentation must be PresentationProjection or None"
        )
    if emotion is not None and not isinstance(
        emotion, CurrentEmotionalState
    ):
        raise TypeError(
            "emotion must be CurrentEmotionalState or None"
        )

    local_time = (
        environment.user_local_time
        or environment.host_local_time
    )
    daylight = (
        environment.daylight.state
        if environment.daylight is not None
        else None
    )
    weather_condition = None
    if (
        environment.weather is not None
        and environment.weather_freshness
        is EnvironmentFreshness.CURRENT
    ):
        weather_condition = environment.weather.condition

    primary = emotion.active[0] if emotion and emotion.active else None
    appearance = presentation.appearance if presentation else None

    return ThemeSignals(
        local_time=local_time,
        daylight=daylight,
        weather_condition=weather_condition,
        outfit_id=(
            presentation.outfit_id
            if presentation is not None
            else None
        ),
        appearance_tags=(
            appearance.style_tags
            if appearance is not None
            else ()
        ),
        hair_color=(
            appearance.hair_color
            if appearance is not None
            else None
        ),
        tail_color=(
            appearance.tail_color
            if appearance is not None
            else None
        ),
        emotional_tone=(
            emotion.tone
            if emotion is not None
            else None
        ),
        primary_emotion=(
            primary.name
            if primary is not None
            else None
        ),
        primary_emotion_intensity=(
            primary.intensity
            if primary is not None
            else 0.0
        ),
    )


class AdaptiveThemePolicy:
    """Choose a restrained accessible palette from trusted presentation signals."""

    _WARM = frozenset({
        "affection",
        "appreciation",
        "fondness",
        "gratitude",
        "romance",
        "warmth",
    })
    _BRIGHT = frozenset({
        "amusement",
        "excitement",
        "joy",
        "playfulness",
    })
    _FOCUSED = frozenset({
        "anticipation",
        "curiosity",
        "determination",
        "hope",
        "reflection",
    })
    _LOW = frozenset({
        "concern",
        "disappointment",
        "longing",
        "sadness",
        "uncertainty",
    })
    _HOT = frozenset({
        "anger",
        "frustration",
    })

    def select(
        self,
        signals: ThemeSignals,
    ) -> ThemePalette:
        if not isinstance(signals, ThemeSignals):
            raise TypeError("signals must be ThemeSignals")

        background = _CANONICAL["background"]
        panel = _CANONICAL["panel"]
        primary = _CANONICAL["primary"]
        secondary = _CANONICAL["secondary"]
        tertiary = _CANONICAL["tertiary"]
        drivers: list[str] = []

        hour = signals.local_time.hour
        night = (
            signals.daylight
            in {DaylightState.NIGHT, DaylightState.POLAR_NIGHT}
            or (
                signals.daylight is None
                and (hour < 6 or hour >= 20)
            )
        )
        if night:
            panel = "#070A10"
            drivers.append("night")
        else:
            panel = "#101018"
            drivers.append("day")

        outfit = (signals.outfit_id or "").lower()
        if "lounge" in outfit:
            primary = "#8B1E3F"
            panel = "#100A11" if night else "#171018"
            drivers.append("lounge")
        elif "engineer" in outfit:
            primary = "#9400D3"
            secondary = "#00C2FF"
            drivers.append("engineer")
        elif "fallback" in outfit:
            primary = "#665A7A"
            secondary = "#7DA8B8"
            drivers.append("fallback")

        weather = (signals.weather_condition or "").casefold()
        if any(word in weather for word in ("thunder", "storm")):
            secondary = "#72A7FF"
            tertiary = "#A47CFF"
            drivers.append("storm")
        elif any(word in weather for word in ("rain", "drizzle", "shower")):
            secondary = "#5AC8E8"
            tertiary = "#6AAE9B"
            drivers.append("rain")
        elif any(word in weather for word in ("snow", "sleet", "ice")):
            secondary = "#B9E8FF"
            tertiary = "#A8D8E8"
            drivers.append("snow")
        elif any(word in weather for word in ("cloud", "overcast", "fog")):
            secondary = "#86A8B7"
            drivers.append("cloud")
        elif any(word in weather for word in ("clear", "sunny", "fair")):
            secondary = "#00C2FF"
            tertiary = "#39FF14"
            drivers.append("clear")

        emotion = signals.primary_emotion
        intensity = float(
            signals.primary_emotion_intensity
        )
        if emotion is not None and intensity >= 0.20:
            if emotion in self._WARM:
                primary = "#8B1E3F"
                drivers.append(f"emotion:{emotion}")
            elif emotion in self._BRIGHT:
                primary = "#9400D3"
                tertiary = "#39FF14"
                drivers.append(f"emotion:{emotion}")
            elif emotion in self._FOCUSED:
                secondary = "#00C2FF"
                tertiary = "#39FF14"
                drivers.append(f"emotion:{emotion}")
            elif emotion in self._LOW:
                primary = "#67558D"
                secondary = "#6FAFC8"
                drivers.append(f"emotion:{emotion}")
            elif emotion in self._HOT:
                primary = "#9F2020"
                secondary = "#D58B3A"
                drivers.append(f"emotion:{emotion}")

        # Canonical appearance can tint the primary accent only when a typed
        # outfit/emotion rule has not already selected a stronger semantic cue.
        if not any(
            driver.startswith("emotion:")
            for driver in drivers
        ) and "lounge" not in outfit:
            tail = _appearance_hex(signals.tail_color)
            hair = _appearance_hex(signals.hair_color)
            if tail is not None:
                primary = tail
                drivers.append("tail-color")
            elif hair is not None:
                primary = hair
                drivers.append("hair-color")

        name = "+".join(drivers) if drivers else "canonical"
        return ThemePalette(
            name=name,
            background=background,
            panel=panel,
            primary=primary,
            secondary=secondary,
            tertiary=tertiary,
            text=_CANONICAL["text"],
            muted=_CANONICAL["muted"],
            drivers=tuple(drivers),
        )


def canonical_theme() -> ThemePalette:
    return ThemePalette(
        name="canonical",
        background=_CANONICAL["background"],
        panel=_CANONICAL["panel"],
        primary=_CANONICAL["primary"],
        secondary=_CANONICAL["secondary"],
        tertiary=_CANONICAL["tertiary"],
        text=_CANONICAL["text"],
        muted=_CANONICAL["muted"],
        drivers=("manual",),
    )
