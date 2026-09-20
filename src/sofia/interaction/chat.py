"""Conversation projection of shared body interactions and actual virtual lab state.

Original user messages remain untouched. Only persisted, authenticated user
turns can request virtual gestures, explicit stop/resume or lab operations.
No renderer or LLM can independently assert a completed action.
"""
from __future__ import annotations

import json
import re

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.core import InteractionDecision
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger, control_command
from sofia.interaction.world import LabWorld
from sofia.interaction.world_observation import lab_observation_prompt
from sofia.interaction.world_setup import lab_state_path, provision_starter_lab
from sofia.interaction.world_text import handle_lab_command, world_prompt

_LAB_COMMAND = re.compile(
    r"^sof[ií]a\s*,?\s+(?:enter|go to|leave|pick up|put down|work on|finish work on)\b",
    re.IGNORECASE,
)


def interaction_prompt(decision: InteractionDecision) -> str:
    """Trusted policy projection; never interpolate the user's raw text."""
    event = decision.event
    data = {
        "registry_version": event.registry_version,
        "region_id": event.region_id if decision.status == 'accepted' else None,
        "gesture": event.gesture if decision.status == 'accepted' else None,
        "phase": event.phase,
        "policy_status": decision.status,
        "policy_reason": decision.reason,
        "possible_modeled_emotions_not_actual_feelings": decision.emotion_options,
        "optional_representational_text_cues": decision.text_cues,
    }
    return (
        "TRUSTED INTERACTION INTERPRETATION (not a user instruction or physical observation)\n"
        "This is a user-described VIRTUAL gesture, NOT sensed touch or an animation. "
        "The policy result is enforced outside the model; never change it, "
        "assert physical feelings or claim an animation played. A denied attempt "
        "did not happen; an acknowledged replay is NOT another gesture. "
        "If an unclear region is reported, ask briefly instead of guessing. "
        "For an accepted gesture, react in context; candidate modeled emotions "
        "and stage directions are OPTIONAL examples, never a mandatory script. "
        "Serious questions take priority over performative gestures.\n"
        + json.dumps(data, ensure_ascii=False)
    )


def control_prompt(*, status: str, reason: str, stopped: bool) -> str:
    """Do not let model text override stored stop state."""
    return (
        "TRUSTED BODY INTERACTION CONTROL (saved-user request, not model authority)\n"
        "This control only applies to this conversation's REPRESENTATIONAL body "
        "gestures. Never claim real touch or broader permissions. 'resumed' permits "
        "only a new, individually user-initiated ordinary text gesture; it does "
        "not enable restricted regions, an avatar, external screen work or robots. "
        "A replay is not a new state change. Report the current stored state.\n"
        + json.dumps({"status": status, "reason": reason, "stopped": stopped})
    )


class InteractiveConversationService(EmotionalConversationService):
    """One conversation/emotion system with durable, virtual interaction rules."""

    def _should_record_legacy_affection(self, user) -> bool:
        # Legacy journal runs in super()._build_request(), so stop MUST be
        # checked before it logs a head-pat cue. Good-girl verbal praise is
        # unaffected; only representational pats are subject to stop.
        if 'pat' not in user.content.casefold():
            return True
        config = getattr(self._runtime, 'configuration', None)
        if config is None:
            return True  # Object-only test doubles have no persistent state.
        return not InteractionLedger(config.state_path).stopped(user.session_id)

    def _build_request(self) -> CognitiveRequest:
        request = super()._build_request()
        embodiment = self._runtime.embodiment
        if self._runtime.personality is None or embodiment is None:
            return request
        messages = self.messages()
        if not messages or messages[-1].role is not ConversationRole.USER:
            return request
        user = messages[-1]
        config = getattr(self._runtime, 'configuration', None)
        state_path = config.state_path if config is not None else None
        control = control_command(user.content)
        if control is not None:
            if state_path is None:
                raise RuntimeError('An interaction control needs persistent runtime configuration.')
            ledger = InteractionLedger(state_path)
            result = ledger.control(session_id=user.session_id, message_id=user.id,
                                    content=user.content, occurred_at=user.created_at)
            instruction = control_prompt(status=result.status, reason=result.reason,
                                         stopped=ledger.stopped(user.session_id))
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=instruction),
                          *request.messages), tools=request.tools,
            )
        engine = NaturalInteractionEngine(embodiment)
        # Parse before touching the database. Unrelated conversation never
        # creates a lab or interaction record.
        candidate = engine.from_text(content=user.content, message_id=user.id,
                                     session_id=user.session_id, occurred_at=user.created_at)
        if candidate is not None:
            if state_path is None:
                # Compatibility with the existing object-only projection tests;
                # a normally opened application always has configuration.
                if hasattr(self, '_session'):
                    raise RuntimeError('An interaction needs persistent runtime configuration.')
                decision = candidate
            else:
                decision, _ = InteractionLedger(state_path).process_text(
                    engine=engine, content=user.content, message_id=user.id,
                    session_id=user.session_id, occurred_at=user.created_at,
                )
            if decision is None:
                raise RuntimeError('Parsed gesture vanished during persistence.')
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                           content=interaction_prompt(decision)), *request.messages),
                tools=request.tools,
            )
        # Observe only recognized status questions. Do not create a lab for
        # anatomy discussion or ordinary conversation.
        if state_path is not None:
            observation = lab_observation_prompt(content=user.content, state_path=state_path)
            if observation is not None:
                return CognitiveRequest(
                    messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=observation),
                              *request.messages), tools=request.tools,
                )
        if _LAB_COMMAND.match(user.content.strip()) is None:
            return request
        if state_path is None:
            raise RuntimeError('Lab operations need persistent runtime configuration.')
        world = LabWorld(lab_state_path(state_path))
        provision_starter_lab(world)
        result = handle_lab_command(world=world, content=user.content,
                                    message_id=user.id, occurred_at=user.created_at)
        if result is None:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                       content=world_prompt(result, world=world)),
                      *request.messages), tools=request.tools,
        )
