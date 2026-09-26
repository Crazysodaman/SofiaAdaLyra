"""Deterministic answers for direct authoritative AVATAR self-fact queries.

The LLM may discuss style and presentation conversationally, but it does not
get authority to contradict typed current presentation state. Recognition is
deliberately conservative and limited to direct self-fact questions.
"""
from __future__ import annotations

from dataclasses import dataclass
from sofia.embodiment.model import Embodiment

from .presentation import PresentationProjection


@dataclass(frozen=True, slots=True)
class AvatarSelfFactAnswer:
    recognized: bool
    content: str = ""

    def __post_init__(self) -> None:
        if type(self.recognized) is not bool:
            raise TypeError("recognized must be a bool")
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if not self.recognized and self.content:
            raise ValueError("unrecognized answer cannot contain content")


def _normalize(query: str) -> str:
    value = " ".join(query.strip().casefold().split())
    return value.rstrip(" ?!.")


def _friendly_outfit(outfit_id: str | None) -> str:
    names = {
        "engineer.signature": "signature engineer outfit",
        "lounge.relaxed": "relaxed lounge outfit",
        "fallback.covered": "covered fallback outfit",
    }
    if outfit_id is None:
        return "current outfit"
    return names.get(outfit_id, outfit_id.replace(".", " ").replace("_", " "))


class AvatarSelfFactResolver:
    """Resolve a small set of direct current-presentation questions."""

    _CURRENT_OUTFIT_FORMS = frozenset({
        "what outfit are you wearing right now",
        "what outfit are you wearing",
        "what outfit do you have on",
        "what are you wearing right now",
        "what are you wearing",
        "what are you wearing rn",
        "what are you currently wearing",
        "tell me your current public-safe outfit and appearance presentation state, including the outfit identifier if available",
        "tell me your current public safe outfit and appearance presentation state, including the outfit identifier if available",
        "what is your current public-safe outfit",
        "what is your current public safe outfit",
        "what is your current outfit identifier",
    })
    _HAIR_COLOR_FORMS = frozenset({
        "what color is your hair",
        "what is your hair color",
        "what's your hair color",
    })
    _TAIL_COLOR_FORMS = frozenset({
        "what color is your tail",
        "what is your tail color",
        "what's your tail color",
    })
    _CURRENT_LOOK_FORMS = frozenset({
        "describe how you currently look",
        "describe how you look",
        "describe your current appearance",
        "what do you look like",
    })
    _FORM_OR_AVATAR_FORMS = frozenset({
        "do you have a physical form or avatar",
        "do you have a physical form or an avatar",
        "do you have a physical form",
        "do you have an avatar",
        "what is your physical form",
        "what's your physical form",
    })
    _TONIGHT_OUTFIT_FORMS = frozenset({
        "what outfit would you want to change into tonight",
        "what outfit would you like to change into tonight",
        "what would you want to wear tonight",
        "what would you like to wear tonight",
    })

    def resolve(
        self,
        query: str,
        *,
        embodiment: Embodiment,
        presentation: PresentationProjection,
        available_outfit_ids: tuple[str, ...] = (),
    ) -> AvatarSelfFactAnswer:
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        if not isinstance(embodiment, Embodiment):
            raise TypeError("embodiment must be Embodiment")
        if not isinstance(presentation, PresentationProjection):
            raise TypeError("presentation must be PresentationProjection")
        if not isinstance(available_outfit_ids, tuple) or any(
            not isinstance(item, str) for item in available_outfit_ids
        ):
            raise TypeError("available_outfit_ids must be a tuple of strings")

        normalized = _normalize(query)
        appearance = dict(embodiment.physical_self.appearance)
        outfit = _friendly_outfit(presentation.outfit_id)

        if normalized in self._CURRENT_OUTFIT_FORMS:
            identifier = (
                f" (outfit ID: {presentation.outfit_id})"
                if presentation.outfit_id is not None
                else ""
            )
            return AvatarSelfFactAnswer(
                True,
                (
                    f"I'm in my {outfit} right now{identifier}."
                ),
            )

        if normalized in self._HAIR_COLOR_FORMS:
            color = presentation.appearance.hair_color
            style = presentation.appearance.hairstyle
            return AvatarSelfFactAnswer(
                True,
                f"My hair is {color}, worn {style}.",
            )

        if normalized in self._TAIL_COLOR_FORMS:
            return AvatarSelfFactAnswer(
                True,
                f"My tail is {presentation.appearance.tail_color}.",
            )

        if normalized in self._CURRENT_LOOK_FORMS:
            features = ", ".join(embodiment.physical_self.additional_features)
            skin = appearance.get("skin_color")
            parts = [
                f"a {embodiment.physical_self.form}-form representational avatar",
            ]
            if features:
                parts.append(f"with {features}")
            parts.append(
                f"{presentation.appearance.hairstyle} "
                f"{presentation.appearance.hair_color} hair"
            )
            if skin:
                parts.append(f"{skin} skin")
            parts.append(f"a {presentation.appearance.tail_color} tail")
            parts.append(f"my {outfit}")
            return AvatarSelfFactAnswer(
                True,
                "Right now, my representational look is " + ", ".join(parts) + ".",
            )

        if normalized in self._FORM_OR_AVATAR_FORMS:
            features = ", ".join(embodiment.physical_self.additional_features)
            feature_text = f" with {features}" if features else ""
            return AvatarSelfFactAnswer(
                True,
                (
                    f"Yes. I have a canonical representational "
                    f"{embodiment.physical_self.form}-form avatar/body{feature_text}. "
                    "It is not a biological physical body, and its authoritative "
                    "state does not imply that a renderer is currently displaying it."
                ),
            )

        if normalized in self._TONIGHT_OUTFIT_FORMS:
            if "lounge.relaxed" in available_outfit_ids:
                candidate = _friendly_outfit("lounge.relaxed")
                return AvatarSelfFactAnswer(
                    True,
                    (
                        f"Tonight I'd lean toward my {candidate}. That's a choice "
                        "I'm considering, not something I've already changed into."
                    ),
                )
            return AvatarSelfFactAnswer(
                True,
                (
                    "I don't have a reviewed alternate outfit available for tonight "
                    "in the current AVATAR catalog, so I wouldn't invent one."
                ),
            )

        return AvatarSelfFactAnswer(False)
