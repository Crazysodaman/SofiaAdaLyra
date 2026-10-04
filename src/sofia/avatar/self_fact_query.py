"""Deterministic answers for direct authoritative AVATAR self-fact queries.

The LLM may discuss style and presentation conversationally, but it does not
get authority to contradict typed current presentation state. Recognition is
deliberately conservative and limited to direct self-fact questions.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from sofia.embodiment.model import Embodiment

from .presentation import AttireMode, PresentationProjection
from .wardrobe_matrix import WardrobeSlotMatrix


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
    raw = " ".join(query.strip().casefold().split()).rstrip(" ?!.")
    raw = re.sub(
        r"\b(?:whatca|whatcha|watcha|whatchu)\b",
        "what are you",
        raw,
    )
    raw = re.sub(r"\bwearin\b", "wearing", raw)
    raw = re.sub(
        r"^(?:(?:okay|ok|well|so)\s+)+",
        "",
        raw,
    )
    raw = re.sub(
        r"^(?:hey\s+)?sof[ií]a\s*[,;:]?\s+",
        "",
        raw,
    )
    shorthand = {
        "u": "you",
        "r": "are",
        "ur": "your",
    }
    return " ".join(
        shorthand.get(token, token)
        for token in raw.split()
    )


def _friendly_outfit(outfit_id: str | None) -> str:
    names = {
        "day.default": "day engineer outfit",
        "night.lounge": "late-night lounge outfit",
        "fallback.covered": "covered fallback outfit",
    }
    if outfit_id is None:
        return "current outfit"
    if outfit_id.startswith("dynamic.chat."):
        return "custom outfit variation"
    return names.get(outfit_id, "custom outfit variation")


class AvatarSelfFactResolver:
    """Resolve grounded current-presentation questions without LLM invention."""

    _UNDERGARMENT_TERM_RE = re.compile(
        r"\b(?:panties|panty|underwear|undergarments?|bra|lingerie|"
        r"briefs|knickers)\b",
        re.IGNORECASE,
    )
    _UNDERGARMENT_FACT_CUE_RE = re.compile(
        r"\b(?:wearing|have\s+on|got\s+on|color|colour|describe|"
        r"look\s+like|which|what|show|see)\b",
        re.IGNORECASE,
    )
    _CURRENT_OUTFIT_STATE_FOLLOWUP_RE = re.compile(
        r"(?=.*\b(?:naked|nude|clothed|wearing|wear\s+anything|"
        r"not\s+wearing|weren't\s+wearing|were\s+not\s+wearing)\b)"
        r"(?=.*\b(?:thought|said|still|currently|right\s+now|"
        r"are\s+you|were\s+you|but)\b)",
        re.IGNORECASE,
    )

    def allows_private_projection(self, query: str) -> bool:
        """Return whether this exact self-fact request may use private state.

        Explicit public-safe/identifier questions intentionally stay on the
        public projection even inside an authenticated private session.
        """
        if not isinstance(query, str):
            raise TypeError("query must be a string")
        normalized = _normalize(query)
        return (
            self._is_current_outfit_query(normalized)
            or self._is_current_outfit_state_followup(normalized)
            or self._is_presentation_reason_query(normalized)
            or self._is_undergarment_query(normalized)
            or normalized in self._CURRENT_LOOK_FORMS
        )

    _DAYPART_OUTFIT_REASON = re.compile(
        r"^why\b.*\b(?:night\s*wear|nightwear|lounge\s*wear|loungewear|"
        r"lounge\s+outfit|wear)\b.*\b(?:night|late|am|pm|morning|evening)\b",
        re.IGNORECASE,
    )
    _PRESENTATION_REASON_RE = re.compile(
        r"^why\s+(?:(?:did\s+you\s+(?:pick|choose))|"
        r"(?:are\s+you\s+wearing))\s+(?:that|it)$"
        r"|^why\s+(?:that|this)\s+(?:one|outfit|choice)$"
        r"|^why\s+(?:the|your)\s+outfit$",
        re.IGNORECASE,
    )

    _UNDERGARMENT_PRESENTATION_FORMS = frozenset({
        "show me your panties",
        "let me see your panties",
        "show me your underwear",
        "let me see your underwear",
    })
    _CURRENT_OUTFIT_FORMS = frozenset({
        "what outfit are you wearing right now",
        "what outfit are you wearing",
        "what is your outfit",
        "what's your outfit",
        "whats your outfit",
        "which is your outfit",
        "what outfit do you have on",
        "what are you wearing right now",
        "what are you wearing",
        "what are you wearing rn",
        "what are you currently wearing",
        "what you wearing",
        "which outfit is this",
        "what outfit is this",
        "which outfit is that",
        "what outfit is that",
        "what is this outfit",
        "what is that outfit",
        "which outfit are you wearing",
        "what is this outfit called",
        "what is that outfit called",
    })
    _PUBLIC_PRESENTATION_FORMS = frozenset({
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
    _BODY_DESCRIPTION_FORMS = frozenset({
        "describe your body",
        "describe your body to me",
        "what does your body look like",
        "what's your body like",
        "what is your body like",
        "what kind of body do you have",
        "what is your build",
        "what's your build",
        "describe your build",
        "describe your figure",
        "what does your figure look like",
        "what is your body type",
        "what's your body type",
        "tell me about your body",
        "tell me what your body looks like",
        "how is your body built",
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
        "what would tonight's lounge outfit be",
        "what would tonights lounge outfit be",
        "what is tonight's lounge outfit",
        "what is tonights lounge outfit",
        "what would your lounge outfit be tonight",
        "what lounge outfit would you wear tonight",
    })

    @classmethod
    def _is_presentation_reason_query(cls, normalized: str) -> bool:
        return cls._PRESENTATION_REASON_RE.fullmatch(normalized) is not None

    @classmethod
    def _is_current_outfit_query(cls, normalized: str) -> bool:
        if normalized in cls._CURRENT_OUTFIT_FORMS:
            return True
        return (
            re.search(
                r"\b(?:what\s+are\s+you|what\s+are\s+u|what\s+r\s+u)"
                r"\s+wearing\b",
                normalized,
                re.IGNORECASE,
            )
            is not None
        )

    @classmethod
    def _is_current_outfit_state_followup(
        cls,
        normalized: str,
    ) -> bool:
        return (
            not cls._is_current_outfit_query(normalized)
            and cls._CURRENT_OUTFIT_STATE_FOLLOWUP_RE.search(normalized)
            is not None
        )

    @classmethod
    def _is_undergarment_query(cls, normalized: str) -> bool:
        return (
            normalized in cls._UNDERGARMENT_PRESENTATION_FORMS
            or (
                cls._UNDERGARMENT_TERM_RE.search(normalized) is not None
                and cls._UNDERGARMENT_FACT_CUE_RE.search(normalized) is not None
            )
        )

    @classmethod
    def _is_body_description_query(cls, normalized: str) -> bool:
        if normalized in cls._BODY_DESCRIPTION_FORMS:
            return True
        return (
            re.search(r"\b(?:body|build|figure|physique)\b", normalized)
            is not None
            and re.search(
                r"\b(?:describe|look\s+like|what|tell\s+me|built)\b",
                normalized,
            )
            is not None
        )

    @staticmethod
    def _measurement_text(embodiment: Embodiment, name: str) -> str:
        measurement = embodiment.get_measurement(name)
        value = measurement.value
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"{value} {measurement.unit}"

    @staticmethod
    def _requested_undergarment_categories(normalized: str) -> tuple[str, ...]:
        if re.search(r"\b(?:panties|panty|knickers)\b", normalized):
            return ("closet.panty",)
        if re.search(r"\bbra\b", normalized):
            return ("closet.bra",)
        return (
            "closet.panty",
            "closet.bra",
            "closet.underwear_top",
            "closet.underwear_bottom",
        )

    @staticmethod
    def _matrix_garments(
        matrix: WardrobeSlotMatrix | None,
        *,
        categories: tuple[str, ...],
    ):
        if matrix is None:
            return ()
        seen: set[str] = set()
        rows = []
        for cell in matrix.cells:
            if cell.garment_id in seen or cell.category not in categories:
                continue
            seen.add(cell.garment_id)
            rows.append(cell)
        return tuple(rows)

    def resolve(
        self,
        query: str,
        *,
        embodiment: Embodiment,
        presentation: PresentationProjection,
        available_outfit_ids: tuple[str, ...] = (),
        wardrobe_matrix: WardrobeSlotMatrix | None = None,
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
        if wardrobe_matrix is not None and not isinstance(
            wardrobe_matrix,
            WardrobeSlotMatrix,
        ):
            raise TypeError("wardrobe_matrix must be WardrobeSlotMatrix or None")

        normalized = _normalize(query)
        appearance = dict(embodiment.physical_self.appearance)
        outfit = _friendly_outfit(presentation.outfit_id)

        if self._is_presentation_reason_query(normalized):
            reason = presentation.reason.casefold()
            pieces = ", ".join(presentation.item_names)
            piece_text = (
                " Current pieces: " + pieces + "."
                if pieces
                else ""
            )
            if presentation.attire is AttireMode.NUDE:
                if reason.startswith("user_clothing_action:"):
                    return AvatarSelfFactAnswer(
                        True,
                        (
                            "I didn't independently pick an outfit there. My current "
                            "private AVATAR presentation has no clothing because an "
                            "explicit clothing action committed the undressed state."
                        ),
                    )
                return AvatarSelfFactAnswer(
                    True,
                    (
                        "My current private AVATAR presentation has no clothing, but "
                        "the stored presentation reason does not support a separate "
                        "preference explanation. I won't invent one."
                    ),
                )

            if reason.startswith("user_clothing_action:"):
                return AvatarSelfFactAnswer(
                    True,
                    (
                        f"I didn't independently select my {outfit} as an automatic "
                        "wardrobe choice. It was committed from an explicit clothing "
                        "action in the conversation."
                        + piece_text
                    ),
                )
            if reason.startswith("headless_daily_context:"):
                details = reason.split(":", 1)[1].split(",")
                why = []
                if "late_lounge" in details:
                    why.append("the trusted local clock is in the late-lounge window")
                if "season_and_activity" in details:
                    why.append("it matches the grounded season and current activity")
                if "modeled_emotion_influence" in details:
                    why.append("modeled emotion gave it a bounded style preference")
                if "ordinary_rotation" in details:
                    why.append("it was the reviewed daily rotation candidate")
                if "daytime_default" in details:
                    why.append("it is the reviewed daytime default")
                if why:
                    return AvatarSelfFactAnswer(
                        True,
                        f"I picked my {outfit} because "
                        + ", and ".join(why)
                        + "."
                        + piece_text,
                    )
                return AvatarSelfFactAnswer(
                    True,
                    (
                        f"My {outfit} came from the headless daily wardrobe planner's "
                        "trusted contextual selection. I don't have a more specific "
                        "grounded reason to add."
                        + piece_text
                    ),
                )
            if reason == "canonical_daily_bootstrap":
                return AvatarSelfFactAnswer(
                    True,
                    (
                        f"My {outfit} is the canonical daily default that bootstraps "
                        "the presentation state when no later grounded choice replaces it."
                        + piece_text
                    ),
                )
            return AvatarSelfFactAnswer(
                True,
                (
                    f"My current presentation is my {outfit}, but the persisted "
                    "presentation record does not support a more specific human-readable "
                    "reason. I won't make one up."
                    + piece_text
                ),
            )

        if self._is_current_outfit_state_followup(normalized):
            if presentation.attire is AttireMode.NUDE:
                return AvatarSelfFactAnswer(
                    True,
                    (
                        "My authoritative current private AVATAR presentation "
                        "is nude. I am not wearing clothing in that current "
                        "presentation."
                    ),
                )
            pieces = ", ".join(presentation.item_names)
            piece_text = (
                f" The pieces are: {pieces}."
                if pieces
                else ""
            )
            return AvatarSelfFactAnswer(
                True,
                (
                    f"My authoritative current AVATAR presentation is clothed "
                    f"in my {outfit}.{piece_text}"
                ),
            )

        if self._is_undergarment_query(normalized):
            if presentation.attire is AttireMode.NUDE:
                return AvatarSelfFactAnswer(
                    True,
                    "I'm not wearing any clothing in my current private AVATAR "
                    "presentation, so I'm not wearing panties or other "
                    "undergarments either.",
                )

            categories = self._requested_undergarment_categories(normalized)
            matrix_matches = self._matrix_garments(
                wardrobe_matrix,
                categories=categories,
            )
            if matrix_matches:
                details = []
                for garment in matrix_matches:
                    accent_text = (
                        " Accent colors: "
                        + ", ".join(garment.accent_hexes)
                        + "."
                        if garment.accent_hexes
                        else ""
                    )
                    details.append(
                        f"{garment.name}: {garment.description} "
                        f"Primary color: {garment.primary_hex}."
                        f"{accent_text}"
                    )
                return AvatarSelfFactAnswer(
                    True,
                    "My current AVATAR wardrobe matrix lists "
                    + " ".join(details),
                )

            # Backward-compatible fallback when a caller does not supply the
            # matrix. Exact projected names may establish a garment, but
            # generic undergarments are never relabeled as panties.
            name_matches = tuple(
                item for item in presentation.item_names
                if any(
                    name in item.casefold()
                    for name in ("panties", "underwear", "briefs", "knickers")
                )
            )
            if name_matches:
                return AvatarSelfFactAnswer(
                    True,
                    "My current avatar presentation lists: "
                    + ", ".join(name_matches)
                    + ". That's a text description, not evidence that an image "
                    "was rendered. The wardrobe matrix metadata was not supplied, "
                    "so I won't invent its color or construction details.",
                )
            panties_specific = re.search(
                r"\b(?:panties|panty|knickers)\b",
                normalized,
            ) is not None
            missing = (
                "doesn't identify a specific panties item or other matching "
                "undergarment"
                if panties_specific
                else "does not identify a specific matching undergarment"
            )
            return AvatarSelfFactAnswer(
                True,
                "My current avatar presentation's wardrobe matrix "
                + missing
                + " I can accurately describe. I won't substitute my trousers "
                "or another garment, and I won't invent one.",
            )

        if self._is_current_outfit_query(normalized):
            if presentation.attire is AttireMode.NUDE:
                return AvatarSelfFactAnswer(
                    True,
                    "I'm not wearing any clothing in my current private AVATAR "
                    "presentation.",
                )
            pieces = ", ".join(presentation.item_names)
            piece_text = f" The pieces are: {pieces}." if pieces else ""
            return AvatarSelfFactAnswer(
                True,
                f"I'm in my {outfit} right now.{piece_text}",
            )

        if self._DAYPART_OUTFIT_REASON.search(normalized):
            pieces = ", ".join(presentation.item_names)
            piece_text = f" The pieces are: {pieces}." if pieces else ""
            if "late_lounge" in presentation.reason:
                return AvatarSelfFactAnswer(
                    True,
                    (
                        f"You're right: my current contextual presentation is my "
                        f"{outfit} because the trusted local clock is in the "
                        f"late-lounge window.{piece_text}"
                    ),
                )
            return AvatarSelfFactAnswer(
                True,
                (
                    f"My authoritative current presentation is my {outfit}. "
                    "This presentation does not contain a grounded late-lounge "
                    "selection reason, so I won't invent a weather, temperature, "
                    "or emotion explanation for it."
                ),
            )

        if normalized in self._PUBLIC_PRESENTATION_FORMS:
            identifier = (
                presentation.outfit_id
                if presentation.outfit_id is not None
                else "unknown"
            )
            tags = ", ".join(
                presentation.appearance.style_tags
            ) or "none"
            return AvatarSelfFactAnswer(
                True,
                (
                    f"I'm in my {outfit} right now "
                    f"(outfit ID: {identifier}). "
                    f"My public-safe presentation has "
                    f"{presentation.appearance.hairstyle} "
                    f"{presentation.appearance.hair_color} hair, "
                    f"a {presentation.appearance.tail_color} tail, "
                    f"and style tags: {tags}."
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

        if self._is_body_description_query(normalized):
            features = ", ".join(embodiment.physical_self.additional_features)
            skin = appearance.get("skin_color", "unspecified")
            height = self._measurement_text(embodiment, "height")
            weight = self._measurement_text(embodiment, "weight")
            bust = self._measurement_text(embodiment, "bust")
            underbust = self._measurement_text(embodiment, "underbust")
            waist = self._measurement_text(embodiment, "waist")
            hips = self._measurement_text(embodiment, "hips")
            feature_text = f", with {features}" if features else ""
            return AvatarSelfFactAnswer(
                True,
                (
                    f"My canonical representational body is a "
                    f"{embodiment.physical_self.form}-form avatar{feature_text}. "
                    f"I'm {height} tall and {weight}. My stored body measurements "
                    f"are bust {bust}, underbust {underbust}, waist {waist}, and "
                    f"hips {hips}. My appearance record specifies {skin} skin, "
                    f"{presentation.appearance.hairstyle} "
                    f"{presentation.appearance.hair_color} hair, and a "
                    f"{presentation.appearance.tail_color} tail. Those are "
                    "authoritative AVATAR facts, not a biological-body claim."
                ),
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
            if "night.lounge" in available_outfit_ids:
                candidate = _friendly_outfit("night.lounge")
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
