"""Thin live adapter for reviewed social actions and scoped preference context.

Text is not physical contact or rendered motion. Preflight blocks known stored
boundaries before the model; a second pre-model check fails closed if the
boundary changes. Cross-process atomic enforcement still belongs in the ledger.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.context_hygiene import without_legacy_auto_affection
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.preference_context import read_interaction_context

_ACTION_COMPOUND = re.compile(
    r"^\s*(?:sof[ií]a,\s*)?i\s+(?:hug|embrace|cuddle|snuggle)\b.*"
    r"\b(?:and|then|while|before|after|plus)\b|"
    r"^\s*(?:sof[ií]a,\s*)?i\s+(?:hug|embrace|cuddle|snuggle)\b.*[;&]",
    re.I,
)
_STOPPED_ACTION = (
    'Represented body interactions are paused, so I have not treated that '
    'action as completed. We can continue talking without body contact.'
)
_COMPOSITE_ACTION = (
    'That describes multiple actions. I have not treated any as completed. '
    'Please send separate actions if you want to explore them one at a time.'
)
_BOUNDARY_ACTION = (
    'That represented action conflicts with a recorded interaction boundary, '
    'so I have not accepted or narrated it as completed. We can keep talking.'
)


def action_prompt(intent) -> str:
    """Only reviewed canonical semantics enter this system instruction."""
    return (
        'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION\n'
        'The saved USER turn describes or offers a represented social action; '
        'it is NOT a physical observation, rendered avatar movement, performed '
        'tool operation, permission or proof of character enjoyment. '
        'A described action is the user’s fictional description, not proof '
        'Sofía agreed to it. An offered action remains an offer, not contact. '
        'Speak TO the user as Sofía, rather than analyzing the gesture or asking '
        'the user to explain an ordinary greeting. Treat an offer as an offer: '
        'respond to the request without implying contact occurred or defaulting '
        'to a physical-body disclaimer. For a description, respond to the '
        'specific moment without declaring that Sofía welcomed or felt it. '
        'Use a short, distinctive conversational response when the turn is '
        'simple; do not force a question, lecture, or stage direction. '
        'Acceptance, uncertainty, discomfort or refusal must follow actual '
        'context and boundaries, not a preset friendly or defensive script. '
        'Do not fabricate earlier contact, physical sensing, voice playback '
        'or animation; do not convert a proposal into execution.\n'
        + json.dumps({
            'source': 'saved_user_text', 'actor': intent.actor,
            'target': intent.target, 'action_id': intent.action_id,
            'modality': intent.modality, 'registry_version': intent.registry_version,
            'actions_executed': False,
        }, ensure_ascii=False)
    )


def preference_prompt(context) -> str:
    """Only the scoped, independently source-checked revision enters context."""
    return (
        'TRUSTED SCOPED MODELED PREFERENCE (not consent or tool authority)\n'
        'This is an explicitly reviewed modeled character preference, not a '
        'claim of subjective sensation or ongoing permission. It may change '
        'with later evidence; it does not override the current conversation, '
        'stop, or a direct refusal. Do not quote private journal entries or '
        'inject this into unrelated conversations.\n'
        + json.dumps({
            'subject': context.subject, 'semantic_id': context.semantic_id,
            'region_id': context.region_id, 'preference': context.preference,
            'source_id': context.source_id,
        }, ensure_ascii=False)
    )


class ExpandedConversationService(InteractiveConversationService):
    """Live action classification and read-only provenance-aware preferences."""

    def _should_record_legacy_affection(self, user) -> bool:
        """Never convert USER praise/pats into Sofía's emotional appraisal.

        The legacy journal auto-assigned affection, appreciation and
        playfulness to Sofía from user syntax alone. Saved cues remain intact,
        but future emotional revisions require reviewed evidence, not a word
        match. The conversation text is still available to the model.
        """
        return False

    def _context_for(self, content: str, *, message_id: str,
                     session_id: str, occurred_at: datetime):
        config = getattr(self._runtime, 'configuration', None)
        embodiment = getattr(self._runtime, 'embodiment', None)
        action = parse_user_action(content, message_id=message_id)
        if action is not None:
            return (action, read_interaction_context(
                config.state_path, subject='sofia', semantic_id=action.action_id,
                region_id='*')) if config is not None else (action, None)
        if config is None or embodiment is None:
            return None, None
        gesture = NaturalInteractionEngine(embodiment).from_text(
            content=content, message_id=message_id,
            session_id=session_id, occurred_at=occurred_at)
        if gesture is None or gesture.status != 'accepted':
            return None, None
        return None, read_interaction_context(
            config.state_path, subject='sofia',
            semantic_id=gesture.event.gesture, region_id=gesture.event.region_id)

    def respond(self, content: str):
        if isinstance(content, str):
            text = content.strip()
            if ('?' not in text and '"' not in text and '`' not in text and
                    not re.search(r"\b(?:not|never|don't|if|would|could|should)\b", text, re.I)
                    and _ACTION_COMPOUND.search(text)):
                return self._guarded_reply(content, _COMPOSITE_ACTION)
            if self._session is not None:
                config = getattr(self._runtime, 'configuration', None)
                if config is not None:
                    action, context = self._context_for(
                        content, message_id='preflight', session_id=self._session.id,
                        occurred_at=datetime.now(timezone.utc))
                    if action is not None and InteractionLedger(config.state_path).stopped(self._session.id):
                        return self._guarded_reply(content, _STOPPED_ACTION)
                    if context is not None and context.blocked:
                        return self._guarded_reply(content, _BOUNDARY_ACTION)
        return super().respond(content)

    def _build_request(self) -> CognitiveRequest:
        # Check source-backed boundaries BEFORE the parent writes an accepted
        # gesture to its ledger; a concurrent change fails closed here.
        messages = self.messages()
        action, context = None, None
        if messages and messages[-1].role is ConversationRole.USER:
            user = messages[-1]
            action, context = self._context_for(
                user.content, message_id=user.id, session_id=user.session_id,
                occurred_at=user.created_at)
            if context is not None and context.blocked:
                raise RuntimeError('A recorded interaction boundary blocks this action.')
        request = without_legacy_auto_affection(super()._build_request())
        if not messages or messages[-1].role is not ConversationRole.USER:
            return request
        instructions = []
        if action is not None:
            config = getattr(self._runtime, 'configuration', None)
            if config is None or InteractionLedger(config.state_path).stopped(user.session_id):
                raise RuntimeError('Interaction stop changed before action projection.')
            instructions.append(action_prompt(action))
        if context is not None and context.preference is not None:
            instructions.append(preference_prompt(context))
        if not instructions:
            return request
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                       content='\n\n'.join(instructions)),
                      *request.messages), tools=request.tools,
        )
