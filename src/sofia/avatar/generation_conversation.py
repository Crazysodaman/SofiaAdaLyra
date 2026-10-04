"""Conversation boundary for direct generated-garment requests."""
from __future__ import annotations

from collections.abc import Callable
import re

from sofia.cognition.matrix.multi_question import split_multi_question
from sofia.social.model import PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID

from .generated_proposal import GarmentGenerationBrief
from .wardrobe import WardrobeError
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
        *,
        resolve_pending: Callable[
            [str],
            tuple[GarmentBlueprint, GarmentAcceptanceResult] | None,
        ] | None = None,
    ) -> None:
        if not callable(generate):
            raise TypeError("generate must be callable")
        if resolve_pending is not None and not callable(resolve_pending):
            raise TypeError("resolve_pending must be callable or None")
        self._generate = generate
        self._resolve_pending = resolve_pending

    @staticmethod
    def _render_result(
        blueprint: GarmentBlueprint,
        result: GarmentAcceptanceResult,
    ) -> str:
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

    @staticmethod
    def _is_pending_followup(
        content: str,
        *,
        previous_assistant_content: str | None,
        principal: PrincipalContext | None,
    ) -> bool:
        if principal is None or principal.principal_id != SPARKS_PRINCIPAL_ID:
            return False
        if (
            previous_assistant_content is None
            or "genuinely unsure whether I want to keep it"
            not in previous_assistant_content
            or "asking you before anything is added"
            not in previous_assistant_content
        ):
            return False
        return bool(content.strip()) and len(content.strip()) <= 1200

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

    def handle(
        self,
        *,
        content: str,
        previous_assistant_content: str | None = None,
        principal: PrincipalContext | None = None,
    ) -> str | None:
        if not isinstance(content, str):
            raise TypeError("content must be str")
        if previous_assistant_content is not None and not isinstance(
            previous_assistant_content,
            str,
        ):
            raise TypeError(
                "previous_assistant_content must be str or None"
            )
        if principal is not None and not isinstance(
            principal,
            PrincipalContext,
        ):
            raise TypeError("principal must be PrincipalContext or None")

        if (
            self._resolve_pending is not None
            and self._is_pending_followup(
                content,
                previous_assistant_content=previous_assistant_content,
                principal=principal,
            )
        ):
            try:
                resolved = self._resolve_pending(content.strip())
            except WardrobeError:
                return (
                    "I couldn't safely resolve that pending garment choice, "
                    "so I left it pending instead of changing my wardrobe."
                )
            if resolved is not None:
                return self._render_result(*resolved)

        brief = self.brief_for(content)
        if brief is None:
            return None
        if (
            principal is None
            or principal.principal_id != SPARKS_PRINCIPAL_ID
        ):
            return (
                "I only accept durable generated-wardrobe requests from "
                "authenticated Sparks context."
            )
        try:
            blueprint, result = self._generate(brief)
        except WardrobeError:
            return (
                "I couldn't turn that into a valid new garment after validation, "
                "so I didn't add anything to my wardrobe."
            )
        return self._render_result(blueprint, result)
