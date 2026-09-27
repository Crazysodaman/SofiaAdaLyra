"""Source-backed interaction -> emotional appraisal bridge."""
from __future__ import annotations

from datetime import datetime

from sofia.personality.emotion import EmotionalJournal

from .preference_context import InteractionContext
from .semantic_context import InteractionClass, interaction_class


_CANONICAL_DIRECTIONS = frozenset({"enjoy", "dislike", "mixed", "neutral"})


def _labels(
    *,
    classification: InteractionClass,
    direction: str,
    offered: bool,
) -> tuple[str, ...]:
    if direction == "dislike":
        return ("aversion", "caution")
    if direction == "mixed":
        return ("affectionate-uncertainty", "uncertainty")
    if direction == "neutral":
        return ("curiosity",)

    if offered:
        if classification is InteractionClass.SEXUAL:
            return ("anticipation", "sensuality")
        if classification is InteractionClass.INTIMATE:
            return ("anticipation", "affectionate-uncertainty")
        if classification is InteractionClass.ROMANTIC:
            return ("anticipation", "romance")
        if classification is InteractionClass.AFFECTIONATE:
            return ("anticipation", "warmth")
        return ("anticipation",)

    if classification is InteractionClass.SEXUAL:
        # A reviewed preference can support attraction/sensuality, but not
        # current consent, arousal, desire, or a claim that contact occurred.
        return ("sexual-attraction", "sensuality")
    if classification is InteractionClass.INTIMATE:
        return ("sensuality", "affectionate-uncertainty")
    if classification is InteractionClass.ROMANTIC:
        return ("romance", "tenderness")
    if classification is InteractionClass.AFFECTIONATE:
        return ("warmth", "fondness")
    return ("contentment",)


def record_interaction_appraisal(
    *,
    semantic_id: str,
    region_id: str | None,
    context: InteractionContext | None,
    message_id: str,
    occurred_at: datetime,
    subject: str,
    journal: EmotionalJournal,
    offered: bool = False,
) -> str | None:
    """Record only appraisals grounded in a reviewed Sofía preference.

    Unknown preference intentionally means no durable emotional write. Current
    modeled emotion may still influence the immediate conversational response.
    """
    if context is None or context.blocked or context.status != "reviewed":
        return None
    preference = context.preference
    if preference not in _CANONICAL_DIRECTIONS:
        return None
    if not isinstance(journal, EmotionalJournal):
        raise TypeError("journal must be EmotionalJournal")
    if not isinstance(offered, bool):
        raise TypeError("offered must be boolean")

    classification = interaction_class(
        semantic_id,
        region_id=region_id,
    )
    labels = _labels(
        classification=classification,
        direction=preference,
        offered=offered,
    )
    event_id = f"interaction-affect:{message_id}:{semantic_id}"
    return journal.record(
        event_id=event_id,
        source="inferred",
        evidence_ref=context.source_id or message_id,
        description=(
            f"A saved user {'offer' if offered else 'interaction description'} "
            f"matched a reviewed Sofía preference for {semantic_id} "
            f"(class={classification.value}, preference={preference}). "
            "This appraisal does not establish contact, sensation, consent, "
            "arousal, desire, or future permission."
        )[:320],
        emotions=labels,
        occurred_at=occurred_at,
        subject=subject,
    )
