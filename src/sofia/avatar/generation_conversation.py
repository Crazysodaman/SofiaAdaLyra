"""Conversation boundary for direct generated-garment requests."""
from __future__ import annotations

from collections.abc import Callable
import re

from sofia.cognition.matrix.multi_question import split_multi_question

from .generated_proposal import GarmentGenerationBrief
from .wardrobe_design import ContentRating
from .wardrobe_generated_store import (
    GarmentAcceptanceResult,
    SofiaGarmentDecision,
)
from .wardrobe_prebuild import GarmentBlueprint


_GENERATE = re.compile(
    r"^\s*(?:please\s+)?(?:design|generate|create|make)\s+"
    r"(?:(?:yourself|for\s+yourself)\s+)?"
    r"(?:(?:a|an)\s+)?(?:new\s+)?",
    re.IGNORECASE,
)
_GARMENT = re.compile(
    r"\b(?:garment|clothing|shirt|tee|top|tank|hoodie|sweater|"
    r"pants|trousers|jeans|shorts|skirt|dress|jumpsuit|romper|"
    r"bodysuit|bra|bralette|briefs|panties|underwear|socks|"
    r"stockings|thigh[- ]highs|legwear|shoes|boots|sandals|"
    r"slippers|jacket|coat|vest|belt|gloves|bracelet|necklace|"
    r"choker|collar|ear\s+accessory|tail\s+accessory|accessory)\b",
    re.IGNORECASE,
)
_EXPLICIT = re.compile(
    r"\b(?:explicit|sexual|nudish|nude-style)\b",
    re.IGNORECASE,
)
_LEWD = re.compile(r"\blewd\b", re.IGNORECASE)
_PRIVATE = re.compile(r"\bprivate\b", re.IGNORECASE)


class WardrobeGenerationConversationService:
    """Recognize one direct garment-generation request and report ownership."""

    def __init__(
        self,
        generate: Callable[
            [GarmentGenerationBrief],
            tuple[GarmentBlueprint, GarmentAcceptanceResult],
        ],
    ) -> None:
        if not callable(generate):
            raise TypeError("generate must be callable")
        self._generate = generate

    @staticmethod
    def brief_for(content: str) -> GarmentGenerationBrief | None:
        if not isinstance(content, str):
            raise TypeError("content must be str")
        if len(split_multi_question(content)) != 1:
            return None
        if _GENERATE.search(content) is None or _GARMENT.search(content) is None:
            return None
        rating = (
            ContentRating.EXPLICIT
            if _EXPLICIT.search(content)
            else (
                ContentRating.LEWD
                if _LEWD.search(content)
                else ContentRating.STANDARD
            )
        )
        private_only = bool(
            rating is not ContentRating.STANDARD
            or _PRIVATE.search(content)
        )
        return GarmentGenerationBrief(
            content.strip(),
            content_rating=rating,
            private_only=private_only,
        )

    def handle(self, *, content: str) -> str | None:
        brief = self.brief_for(content)
        if brief is None:
            return None
        blueprint, result = self._generate(brief)
        name = blueprint.garment.name

        if result.decision is SofiaGarmentDecision.ACCEPT:
            if not result.persisted:
                raise RuntimeError(
                    "accepted generated garment was not persisted"
                )
            return (
                f"I designed {name} and decided I want to keep it. "
                "It's now part of my wardrobe. "
                f"My reason: {result.reason}"
            )
        if result.decision is SofiaGarmentDecision.ASK_SPARKS:
            return (
                f"I designed {name}, but I'm genuinely unsure whether I want "
                "to keep it, so I'm asking you before anything is added. "
                f"My reason: {result.reason}"
            )
        return (
            f"I designed {name}, but I decided not to add it to my wardrobe. "
            f"My reason: {result.reason}"
        )
