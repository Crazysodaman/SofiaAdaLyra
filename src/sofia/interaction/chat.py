"""Conversation projection of shared body interactions and actual virtual lab state.

Original user messages remain untouched. Virtual location actions are only
issued for narrow, explicitly addressed commands from persisted user turns.
A renderer and an LLM cannot independently declare an action completed.
"""
from __future__ import annotations

import json
import re

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.core import InteractionDecision, InteractionEngine
from sofia.interaction.world import LabWorld
from sofia.interaction.world_observation import lab_observation_prompt
from sofia.interaction.world_setup import lab_state_path, provision_starter_lab
from sofia.interaction.world_text import handle_lab_command, world_prompt

_LAB_COMMAND = re.compile(
    r"^sof[ií]a\s*,?\s+(?:enter|go to|leave|pick up|put down|work on|finish work on)\b",
    re.IGNORECASE,
)


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
    """One existing conversation and emotion system, plus virtual world state."""

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
        if decision is not None:
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                           content=interaction_prompt(decision)), *request.messages),
                tools=request.tools,
            )
        # A lab-status question is observation only. It must not create a
        # database, provision objects, or submit an action to LabWorld.perform.
        observation = lab_observation_prompt(
            content=user.content, state_path=self._runtime.configuration.state_path,
        )
        if observation is not None:
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                           content=observation), *request.messages),
                tools=request.tools,
            )
        # Do not instantiate or provision the world for ordinary conversation,
        # narration, anatomy discussion or unaddressed text.
        if _LAB_COMMAND.match(user.content.strip()) is None:
            return request
        world = LabWorld(lab_state_path(self._runtime.configuration.state_path))
        provision_starter_lab(world)
        result = handle_lab_command(world=world, content=user.content,
                                    message_id=user.id, occurred_at=user.created_at)
        if result is None:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                       content=world_prompt(result, world=world)),
                      *request.messages),
            tools=request.tools,
        )
