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
from sofia.interaction.live_guard import (
    COMPOSITE_GESTURE_REPLY, MIXED_CONTROL_REPLY, RESUME_CONTROL_REPLY,
    STOP_CONTROL_REPLY, STOPPED_GESTURE_REPLY, mixed_interaction_control,
    unsupported_composite_gesture,
)
from sofia.interaction.world import LabWorld
from sofia.interaction.world_observation import lab_observation_prompt
from sofia.interaction.world_setup import lab_state_path, provision_starter_lab
from sofia.interaction.world_text import handle_lab_command, world_prompt

_LAB_COMMAND = re.compile(
    r"^sof[ií]a\s*,?\s+(?:enter|go to|leave|pick up|put down|work on|finish work on)\b",
    re.IGNORECASE,
)
_INTERACTION_FOLLOWUP = re.compile(
    r"^\s*(?:why\b.*|"
    r"what\s+if\b.*\b(?:wanted|consensual|consent)\b.*|"
    r"what\s+if\s+you\s+(?:wanted|liked|welcomed)\s+it\b.*|"
    r"what\s+if\s+you\s+(?:did\s+not|didn't|do\s+not|don't)\s+want\s+it\b.*|"
    r"what\s+if\s+you\s+normally\s+like\s+it\b.*|"
    r"(?:can|could|would)\s+you\s+change\s+your\s+mind\b.*|"
    r"would\s+it\s+be\s+different\b.*\b(?:want|consent)\w*\b.*)\s*$",
    re.IGNORECASE,
)


def interaction_followup_prompt(
    *, content: str, messages: tuple[ConversationMessage, ...],
    engine: NaturalInteractionEngine,
) -> str | None:
    """Ground a short consent/boundary follow-up in a prior saved gesture."""
    if not isinstance(content, str) or _INTERACTION_FOLLOWUP.match(content.strip()) is None:
        return None
    for previous in reversed(messages[:-1]):
        if previous.role is not ConversationRole.USER:
            continue
        occurred_at = getattr(previous, "created_at", None)
        session_id = getattr(previous, "session_id", None)
        message_id = getattr(previous, "id", None)
        if (not isinstance(occurred_at, datetime) or occurred_at.tzinfo is None
                or not isinstance(session_id, str) or not isinstance(message_id, str)):
            continue
        decision = engine.from_text(
            content=previous.content, message_id=message_id,
            session_id=session_id, occurred_at=occurred_at,
        )
        if decision is None:
            continue
        event = decision.event
        data = {
            "followup_only": True,
            "actions_executed": False,
            "prior_region_id": event.region_id,
            "prior_gesture": event.gesture,
            "interaction_preference_evidence": "unspecified",
            "willingness_state": "undetermined",
        }
        return (
            "TRUSTED INTERACTION FOLLOW-UP (read-only; no new action executed)\n"
            "The current user turn is a short question about the meaning, consent, "
            "or boundary of an earlier user-described represented gesture. It does "
            "not repeat that gesture and grants no new permission. Answer the "
            "follow-up directly in Sofía's voice. Mutual willingness matters: the "
            "user wanting an interaction is not enough by itself, and prior "
            "willingness never prevents Sofía from saying no, not now, uncertain, "
            "or changing her mind. An intimate represented body region is not, by "
            "itself, a reason to label the user or gesture inappropriate or "
            "disrespectful. Keep any intimate discussion non-graphic and centered "
            "on Sofía's current boundary, comfort, and context. No stored preference "
            "evidence is supplied for this follow-up, so do not repeat a prior model-"
            "invented claim of comfort, discomfort, preference, or boundary as if it "
            "were established. Treat the earlier assistant wording as non-authoritative "
            "unless backed by trusted context. The trusted willingness_state is "
            "'undetermined', so a non-hypothetical follow-up such as 'why' should explain "
            "that Sofía had not established current willingness rather than inventing a "
            "standing rejection, present refusal, preference, or claim that the interaction "
            "currently conflicts with her boundaries. Uncertainty is not evidence that something "
            "feels wrong or out of alignment. Answer hypothetical questions conditionally: "
            "if Sofía wanted it, say what follows from that hypothetical; if she did not "
            "want it, say what follows from that hypothetical. When willingness_state is "
            "'undetermined', do not append an ungrounded present claim such as 'right now "
            "I'm not ready', 'I'm not there', or 'I don't want it' to a hypothetical answer. "
            "Never describe represented contact as literal bodily sensation, including "
            "'I'd feel it in my body'. If a prior assistant "
            "reply used blanket moralizing unsupported by these rules, correct the "
            "substance instead of defending the canned wording. Avoid generic safety "
            "lectures and customer-service closers. Never claim real touch, physical "
            "sensation, or an unrecorded action occurred.\n"
            + json.dumps(data, ensure_ascii=False)
        )
    return None


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
        "interaction_preference_evidence": "unspecified",
        "willingness_state": "undetermined",
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
        "animation. An 'accepted' status means the gesture was RECOGNIZED "
        "and recorded as user-described virtual input; it does NOT mean "
        "Sofía consented, welcomed it, enjoyed it or actually felt contact. "
        "There are NO anatomy-wide automatic denials: assess every known "
        "region using the gesture, current and prior conversation, expressed "
        "boundaries and tone. Do not label a represented interaction "
        "inappropriate or disrespectful solely because the named region is "
        "intimate. There is no sexual-mode switch: sexual attraction, desire, "
        "arousal, romance, affection, comfort and hesitation are independent "
        "contextual states. Never infer attraction, desire or arousal merely "
        "from the user's sexual wording or the body region. When "
        "interaction_preference_evidence is 'unspecified', do not invent a "
        "stable preference, comfort, discomfort, attraction, aversion, or "
        "standing boundary. Uncertainty or a present need to decide is the "
        "grounded default unless CURRENT MODELED EMOTIONAL STATE or other "
        "trusted context supplies relevant evidence. For an intimate accepted "
        "gesture with willingness_state 'undetermined', answer from uncertainty "
        "rather than inventing a present yes/no, comfort, "
        "discomfort, a permanent preference, or a new standing boundary. User desire is not "
        "Sofía's consent; Sofía may want it, not "
        "want it, be uncertain, say not now, or change her mind. Keep intimate "
        "responses non-graphic and express Sofía's own current boundary rather "
        "than a generic safety lecture. Sofía may respond positively, neutrally, "
        "awkwardly, with a question, or negatively, including an explicit "
        "boundary; do not force a favorable or unfavorable response from "
        "region alone. A denied attempt did not happen; an acknowledged "
        "replay is NOT another gesture. A prior stop is binding until the "
        "user explicitly resumes in a separate saved control turn. For an "
        "unclear region, ask briefly instead of guessing. For a recognized "
        "gesture, respond as Sofía to the specific region, action and "
        "conversational mood with natural, non-repetitive dialogue. Do not "
        "reuse prior assistant wording, repeat a sentimental monologue, or "
        "automatically end with the same question. The modeled emotions and "
        "representational stage directions are OPTIONAL possibilities, not "
        "a checklist or fixed script; no stage direction is required. When a "
        "trusted CURRENT MODELED EMOTIONAL STATE is present elsewhere in the "
        "request, use it as the starting point for the reaction. Do not choose "
        "an unrelated stage direction merely because it appears in the option "
        "list; prose, boundary choice, and optional embodiment cue should be "
        "coherent with the same current state unless the new gesture itself "
        "clearly changes the moment. Be playful only when it fits; a serious "
        "question takes priority.\n"
        + json.dumps(data, ensure_ascii=False)
    )


def control_prompt(*, status: str, reason: str, stopped: bool) -> str:
    """Do not let model text override stored stop state."""
    return (
        "TRUSTED BODY INTERACTION CONTROL (saved-user request, not model authority)\n"
        "This control only applies to this conversation's REPRESENTATIONAL body "
        "gestures. Never claim real touch or broader permissions. 'resumed' permits "
        "only a NEW individually user-described text gesture; no anatomy is "
        "automatically denied or welcomed. Resuming does not authorize an "
        "avatar, external screen work or robots. A replay is not a new state "
        "change. Report the current stored state; do not claim unrelated "
        "actions in past user text were executed.\n"
        + json.dumps({"status": status, "reason": reason, "stopped": stopped})
    )


class InteractiveConversationService(EmotionalConversationService):
    """One conversation/emotion system with durable, virtual interaction rules."""

    def _guarded_reply(self, content: str, reply: str, *, command: str | None = None,
                       stopped_gesture: bool = False) -> CognitiveResponse:
        """Persist saved-user evidence and authoritative outcomes without an LLM.

        Compound turns only save conversation; an exact control or stopped
        gesture also writes its matching ledger event from the SAME saved ID.
        No emotional appraisal, filesystem tool or rendered gesture is invoked.
        """
        if self._session is None:
            raise RuntimeError('ConversationService must be started before responding.')
        clean = content.strip()
        if not clean:
            raise ValueError('ConversationService content must not be empty.')
        self._active_user_requests += 1
        try:
            with self._model_lock:
                session_id = self._session.id
                user = ConversationMessage(
                    id=str(uuid4()), session_id=session_id, role=ConversationRole.USER,
                    content=clean, created_at=datetime.now(timezone.utc),
                )
                self._conversation_store.save(user)
                if command is not None or stopped_gesture:
                    configuration = getattr(self._runtime, 'configuration', None)
                    if configuration is None:
                        raise RuntimeError('Interaction controls require persistent configuration.')
                    ledger = InteractionLedger(configuration.state_path)
                    if command is not None:
                        result = ledger.control(session_id=session_id, message_id=user.id,
                                                content=clean, occurred_at=user.created_at)
                        expected = 'stopped' if command == 'stop' else 'resumed'
                        if result.status != expected or ledger.stopped(session_id) != (command == 'stop'):
                            raise RuntimeError('Unexpected interaction control outcome.')
                        reply = STOP_CONTROL_REPLY if command == 'stop' else RESUME_CONTROL_REPLY
                    else:
                        embodiment = getattr(self._runtime, 'embodiment', None)
                        if embodiment is None:
                            raise RuntimeError('A stopped gesture needs canonical embodiment.')
                        decision, fresh = ledger.process_text(
                            engine=NaturalInteractionEngine(embodiment), content=clean,
                            message_id=user.id, session_id=session_id,
                            occurred_at=user.created_at,
                        )
                        if decision is None or decision.status != 'denied' or not fresh:
                            raise RuntimeError('Stopped gesture did not receive a durable denial.')
                response = CognitiveResponse(content=reply)
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

    def respond(self, content: str) -> CognitiveResponse:
        """Route enforceable actions before model inference or tool orchestration."""
        if not isinstance(content, str):
            return super().respond(content)
        if mixed_interaction_control(content):
            return self._guarded_reply(content, MIXED_CONTROL_REPLY)
        if unsupported_composite_gesture(content):
            return self._guarded_reply(content, COMPOSITE_GESTURE_REPLY)
        command = control_command(content)
        if command is not None:
            return self._guarded_reply(content, '', command=command)
        configuration = getattr(self._runtime, 'configuration', None)
        embodiment = getattr(self._runtime, 'embodiment', None)
        if configuration is not None and embodiment is not None and self._session is not None:
            # Only a recognized gesture needs a ledger lookup. Plain chat
            # never initializes the interaction database.
            candidate = NaturalInteractionEngine(embodiment).from_text(
                content=content, message_id='preflight', session_id=self._session.id,
                occurred_at=datetime.now(timezone.utc),
            )
            if candidate is not None and InteractionLedger(configuration.state_path).stopped(self._session.id):
                return self._guarded_reply(content, STOPPED_GESTURE_REPLY, stopped_gesture=True)
        return super().respond(content)

    def _should_record_legacy_affection(self, user) -> bool:
        # Old emotional cues must not turn a hypothetical, compound sentence,
        # quoted phrase or stopped pat into a newly welcomed event.
        text = user.content
        clean = text.strip()
        if ('\n' in text or '`' in text or '"' in text or '?' in text
                or (clean.startswith("'") and clean.endswith("'"))
                or _DISCUSSION.search(text) or unsupported_composite_gesture(text)):
            return False
        if 'pat' not in text.casefold():
            return True  # Verbal praise is not a body interaction.
        config = getattr(self._runtime, 'configuration', None)
        if config is None:
            return True  # Existing object-only test doubles have no state.
        if InteractionLedger(config.state_path).stopped(user.session_id):
            return False
        embodiment = getattr(self._runtime, 'embodiment', None)
        if embodiment is None:
            return False
        decision = NaturalInteractionEngine(embodiment).from_text(
            content=text, message_id=user.id, session_id=user.session_id,
            occurred_at=user.created_at,
        )
        return decision is not None and decision.status == 'accepted'

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
                          *request.messages), tools=(),
            )
        embodiment = self._runtime.embodiment
        if self._runtime.personality is None or embodiment is None:
            return request
        engine = NaturalInteractionEngine(embodiment)
        candidate = engine.from_text(content=user.content, message_id=user.id,
                                     session_id=user.session_id, occurred_at=user.created_at)
        if candidate is not None:
            if state_path is None:
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
                tools=(),
            )
        discussion = body_discussion_prompt(content=user.content, engine=engine)
        if discussion is not None:
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=discussion),
                          *request.messages), tools=(),
            )
        followup = interaction_followup_prompt(
            content=user.content, messages=messages, engine=engine,
        )
        if followup is not None:
            return CognitiveRequest(
                messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=followup),
                          *request.messages), tools=(),
            )
        if state_path is not None:
            observation = lab_observation_prompt(content=user.content, state_path=state_path)
            if observation is not None:
                return CognitiveRequest(
                    messages=(CognitiveMessage(role=CognitiveRole.SYSTEM, content=observation),
                              *request.messages), tools=(),
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
                      *request.messages), tools=(),
        )
