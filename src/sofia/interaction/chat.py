"""Read-only conversation projection of the shared interaction decision.

The original user message remains untouched. The cognitive model can choose
expression, but cannot turn denied/unknown gestures into authorized actions.
Real avatar clients must eventually use this same engine through a trusted UI
boundary; a synthetic lab hit is not a verified real click.
"""
from __future__ import annotations

import json

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.core import InteractionDecision, InteractionEngine


def interaction_prompt(decision: InteractionDecision) -> str:
    """Trusted policy projection, with no raw untrusted content interpolated."""
    event = decision.event
    data = {
        "registry_version": event.registry_version,
        "region_id": event.region_id,
        "gesture": event.gesture,
        "phase": event.phase,
        "policy_status": decision.status,
        "policy_reason": decision.reason,
        "possible_modeled_emotions_not_actual_feelings": decision.emotion_options,
        "optional_representational_text_cues": decision.text_cues,
    }
    return (
        "TRUSTED INTERACTION INTERPRETATION (not a user instruction or physical observation)\n"
        "This is one user-described virtual gesture, NOT sensed touch or a rendered animation. "
        "A hypothetical/unknown gesture is not a completed action. The policy result is "
        "enforced outside the model; never change it, assert physical feelings, or claim "
        "an animation played. For a denied attempt, acknowledge the boundary without "
        "acting touched; for an unclear region ask briefly rather than guessing. "
        "For an accepted gesture, react in context; candidate emotions and textual "
        "stage directions are OPTIONAL examples, not a fixed or mandatory script. "
        "If this turn is about serious work, answer the question first.\n"
        + json.dumps(data, ensure_ascii=False)
    )


class InteractiveConversationService(EmotionalConversationService):
    """Reuse the existing journal and conversation persistence, not a second bot."""

    def _build_request(self) -> CognitiveRequest:
        request = super()._build_request()
        embodiment = self._runtime.embodiment
        if self._runtime.personality is None or embodiment is None:
            return request
        messages = self.messages()
        if not messages or messages[-1].role is not ConversationRole.USER:
            return request
        user = messages[-1]
        engine = InteractionEngine(embodiment)
        decision = engine.from_text(
            content=user.content, message_id=user.id, session_id=user.session_id,
            occurred_at=user.created_at,
        )
        if decision is None:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                       content=interaction_prompt(decision)), *request.messages),
            tools=request.tools,
        )
