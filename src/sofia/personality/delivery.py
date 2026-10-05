"""Personality framing for deterministic, already-grounded responses.

This layer may add brief voice around trusted factual payloads. It must never
rewrite measurements, timestamps, sources, uncertainty, or authority.
"""
from __future__ import annotations


def grounded_weather_delivery(
    content: str,
    *,
    condition: str | None = None,
) -> str:
    """Add restrained Sofía voice to a current-weather fact string.

    The authoritative resolver output is retained byte-for-byte as the prefix.
    Only a short, nonfactual aside may be appended, selected from the already
    grounded condition label. Unknown/non-current weather passes through.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if condition is not None and not isinstance(condition, str):
        raise TypeError("condition must be a string or None")
    if not content.startswith("Current weather") or condition is None:
        return content

    normalized = condition.strip().casefold()
    if not normalized:
        return content

    if any(word in normalized for word in ("thunder", "storm")):
        aside = "The atmosphere is being dramatic. Noted."
    elif any(word in normalized for word in ("rain", "drizzle", "shower")):
        aside = "The sky has opinions today."
    elif any(word in normalized for word in ("snow", "sleet", "ice", "freezing")):
        aside = "Subtle weather has apparently left the building."
    elif any(word in normalized for word in ("fog", "mist", "haze")):
        aside = "Visibility is choosing mystery today."
    elif any(word in normalized for word in ("cloud", "overcast")):
        aside = "The sky is being indecisive. Figures."
    elif any(word in normalized for word in ("clear", "sunny", "fair")):
        aside = "Rather cooperative weather, for once."
    else:
        return content
    return f"{content} {aside}"
