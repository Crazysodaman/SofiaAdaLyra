"""Conversation projection of shared body interactions and actual virtual lab state.

Original user messages remain untouched. Only saved USER-role conversation turns
can request virtual gestures, explicit stop/resume or lab operations. This CLI
layer does not independently authenticate a human or an avatar controller.
No renderer or LLM can independently assert a completed action.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from time import monotonic
from uuid import uuid4

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.interaction.body_discussion import body_discussion_prompt
from sofia.interaction.core import InteractionDecision, _DISCUSSION
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger, control_command
from sofia.interaction.live_guard import MIXED_CONTROL_REPLY, mixed_interaction_control
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
        "Sofía has a CANONICAL REPRESENTATIONAL fox-eared, fox-tailed body. "
        "That body exists as her defined virtual embodiment even when no avatar "
        "is drawn. Do not erase or deny that embodiment with generic claims "
        "such as 'I have no form/head/ears/tail'; distinguish a virtual or "
        "text-described action from real-world touch only when relevant. "
        "Do not repeatedly lecture about being an AI or lacking physical "
        "sensation. This is a user-described VIRTUAL gesture, NOT sensed "
        "touch or an animation. The policy result is enforced outside the "
        "model; never change it or assert physical feelings or a played "
        "animation. A denied attempt did not happen; an acknowledged replay "
        "is NOT another gesture. For an unclear region, ask briefly instead "
        "of guessing. For an accepted gesture, respond as Sofía to the "
        "specific region, action and conversational mood with natural, "
        "non-repetitive dialogue. The modeled emotions and representational "
        "stage directions are OPTIONAL possibilities, not a checklist or "
        "fixed script; no stage direction is required. Be playful only when "
        "it fits; a serious question takes priority.\n"
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
        "A replay is not a new state change. Report the current stored state; "
        "do not claim unrelated actions in past user text were executed.\n"
        + json.dumps({"status": status, "reason": reason, "stopped": stopped})
    )


class InteractiveConversationService(EmotionalConversationService):
    """One conversation/emotion system with durable, virtual interaction rules."""

    def respond(self, content: str) -> CognitiveResponse:
        """Persist an honest deterministic reply to an unsupported mixed control.

        This branch must run before inference, tool orchestration or the
        single-gesture parser. It saves both original messages via the same
        conversation store; it neither performs a stop/resume nor logs touch.
        All other turns use the existing locked application response path.
        """
        if not mixed_interaction_control(content):
            return super().respond(content)
        if self._session is None:
            raise RuntimeError('ConversationService must be started before responding.')
        clean = content.strip()
        if not clean:
            raise ValueError('ConversationService content must not be empty.')
        self._active_user_requests += 1
        try:
            with self._model_lock:
                session_id = self._session.id
                self._conversation_store.save(ConversationMessage(
                    id=str(uuid4()), session_id=session_id, role=ConversationRole.USER,
                    content=clean, created_at=datetime.now(timezone.utc),
                ))
                response = CognitiveResponse(content=MIXED_CONTROL_REPLY)
                self._conversation_store.save(ConversationMessage(
                    id=str(uuid4()), session_id=session_id, role=ConversationRole.ASSISTANT,
                    content=response.content, created_at=datetime.now(timezone.utc),
                ))
                session = self._conversation_store.get_session(session_id)
                if session is None:
                    raise RuntimeError('ConversationService lost its active session.')
                self._session = session
                return response
        finally:
            self._last_user_activity = monotonic()
            self._active_user_requests -= 1

    def _should_record_legacy_affection(self, user) -> bool:
        # Existing emotional cues run in super()._build_request(). They must
        # not turn a hypothetical, quote, code or stopped pat into an event.
        text = user.content
        clean = text.strip()
        if ('\n' in text or '`' in text or '"' in text or '?' in text
                or (clean.startswith("'") and clean.endswith("'"))
                or _DISCUSSION.search(text)):
            return False
        if 'pat' not in text.casefold():
            return True  # Verbal praise is not a body interaction.
        config = getattr(self._runtime, 'configuration', None)
        if config is None:
            return True  # Existing object-only test doubles have no state.
        return not InteractionLedger(config.state_path).stopped(user.session_id)

    def _build_request(self) -> CognitiveRequest:
        request = super()._build_request()
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
        embodiment = self._runtime.embodiment
        if self._runtime.personality is None or embodiment is None:
            return request
        engine = NaturalInteractionEngine(embodiment)
        # Parse before touching the database. Unrelated conversation never
        # creates a lab or interaction record.
        candidate = engine.from_text(content=user.content, message_id=user.id,
                                     session_id=user.session_id, occurred_at=user.created_at)
        if candidate is not None:
            if state_path is None:
                # Compatibility with object-only projection tests; a normally
                # opened application always has persistent configuration.
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
        # A hypothetical, multi-action question gets READ-ONLY canonical
        # context, never a gesture decision or a newly provisioned lab.
        discussion = body_discussion_prompt(content=user.content, engine=engine)
        if discussion is not None:
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=discussion),
                          *request.messages), tools=request.tools,
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
