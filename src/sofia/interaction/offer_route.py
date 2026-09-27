"""Production-reviewed routing for the canonical represented hug offer."""
from __future__ import annotations

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.interaction.decision_expression import ReviewedFrame, choice_request

OFFER = "I ask to hug you"


def routed_choice_request(base: CognitiveRequest, frame: ReviewedFrame) -> CognitiveRequest:
    """Build the tool-free avatar-social choice request for the reviewed offer."""
    if (
        frame.kind != "offer"
        or frame.user_text != OFFER
        or frame.choices != ("accept", "decline", "clarify", "boundary")
    ):
        raise ValueError("The reviewed synthetic hug offer is required.")

    original = choice_request(base, frame)
    route_instruction = (
        "TRUSTED ROUTE: avatar_social_offer. The action grammar already routed "
        "this request to the represented-avatar social channel. This is a "
        "CHOICE of how Sofía responds to an OFFER, not a physical capability "
        "question or a report that touch happened. Real-world sensor or hardware "
        "questions take a different route and do not belong to this decision. "
        "Choose using Sofía's contextual willingness and boundaries; accepting, "
        "declining, clarifying and setting a boundary are all legitimate. Do not "
        "treat absence of a real-world body as a reason to decline an avatar "
        "offer. Nothing here grants consent, executes touch, animates a body, "
        "creates a memory or asserts subjective sensation. "
        "Return ONLY strict JSON with exactly two string keys, choice and reason. "
        "The reason briefly explains the conversational choice, not a factual "
        "claim of sensation or history. No markdown. Allowed choices: "
        "accept, decline, clarify, boundary."
    )
    return CognitiveRequest(
        messages=(
            original.messages[0],
            original.messages[1],
            CognitiveMessage(role=CognitiveRole.SYSTEM, content=route_instruction),
            original.messages[3],
        ),
        tools=(),
    )
