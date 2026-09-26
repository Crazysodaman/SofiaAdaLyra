"""Deterministic answers for direct authoritative AVATAR self-fact queries.

The LLM may discuss style and presentation conversationally, but it does not
get authority to contradict typed current presentation state. Recognition is
deliberately conservative and limited to direct self-fact questions.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

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

    _CURRENT_OUTFIT = re.compile(
        r"^(?:what(?:'s| is)\s+)?(?:outfit\s+(?:are|do)\s+you\s+"
        r"(?:wear(?:ing)?|have\s+on)|what\s+are\s+you\s+wearing)"
        r"(?:\s+(?:right\s+now|rn|currently))?$"
    )
    _HAIR_COLOR = re.compile(
        r"^(?:what\s+color\s+is\s+your\s+hair|what(?:'s| is)\s+your\s+hair\s+color)$"
    )
    _TAIL_COLOR = re.compile(
        r"^(?:what\s+color\s+is\s+your\s+tail|what(?:'s| is)\s+your\s+tail\s+color)$"
    )
    _CURRENT_LOOK = re.compile(
        r"^(?:describe\s+(?:how\s+you\s+currently\s+look|your\s+current\s+"
        r"appearance|how\s+you\s+look)|what\s+do\s+you\s+look\s+like)$"
    )
    _FORM_OR_AVATAR = re.compile(
        r"^(?:do\s+you\s+have\s+(?:a\s+)?(?:physical\s+form(?:\s+or\s+"
        r"(?:an?\s+)?avatar)?|avatar)|what(?:'s| is)\s+your\s+physical\s+form)$"
    )
    _TONIGHT_OUTFIT = re.compile(
        r"^(?:what\s+outfit\s+would\s+you\s+(?:want|like)\s+to\s+change\s+"
        r"into\s+tonight|what\s+would\s+you\s+(?:want|like)\s+to\s+wear\s+tonight)$"
    )

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

        if self._CURRENT_OUTFIT.fullmatch(normalized):
            return AvatarSelfFactAnswer(
                True,
                (
                    f"I'm currently wearing my {outfit} in my representational "
                    "presentation. That's my authoritative current AVATAR state, "
                    "even if no visual renderer is active."
                ),
            )

        if self._HAIR_COLOR.fullmatch(normalized):
            color = presentation.appearance.hair_color
            style = presentation.appearance.hairstyle
            return AvatarSelfFactAnswer(
                True,
                f"My hair is {color}, currently styled {style}.",
            )

        if self._TAIL_COLOR.fullmatch(normalized):
            return AvatarSelfFactAnswer(
                True,
                f"My tail is {presentation.appearance.tail_color}.",
            )

        if self._CURRENT_LOOK.fullmatch(normalized):
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
                "My current look is " + ", ".join(parts) + ".",
            )

        if self._FORM_OR_AVATAR.fullmatch(normalized):
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

        if self._TONIGHT_OUTFIT.fullmatch(normalized):
            if "lounge.relaxed" in available_outfit_ids:
                candidate = _friendly_outfit("lounge.relaxed")
                return AvatarSelfFactAnswer(
                    True,
                    (
                        f"Tonight I'd lean toward my {candidate} as a presentation "
                        "candidate. That's a possible choice, not a claim that I've "
                        "already changed into it."
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
