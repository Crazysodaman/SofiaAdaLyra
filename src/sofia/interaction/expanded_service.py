"""Thin live adapter for reviewed social actions, preserving the v1 ledger.

A user's description of an action is not an avatar command, consent, or actual
physical act. Contact offers remain offers. No new DB tables, idle workers,
notifications or permission are installed by this adapter.
"""
from __future__ import annotations

import json
import re

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.ledger import InteractionLedger

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


def action_prompt(intent) -> str:
    """Only reviewed canonical semantics enter this system instruction."""
    return (
        'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION\n'
        'The saved USER turn describes or offers a represented social action; '
        'it is NOT a physical observation, rendered avatar movement, performed '
        'tool operation, permission or proof of character enjoyment. '
        'A described action is the user’s fictional description, not proof '
        'Sofía agreed to it. An offered action remains an offer, not contact. '
        'Respond contextually, including acceptance, clarification, discomfort '
        'or refusal as appropriate to conversational evidence and boundaries. '
        'Do not fabricate physical sensing, voice playback or animation; '
        'do not convert a proposal into execution. Avoid repetitive stage '
        'directions and permit a quiet/no-expression response.\n'
        + json.dumps({
            'source': 'saved_user_text', 'actor': intent.actor,
            'target': intent.target, 'action_id': intent.action_id,
            'modality': intent.modality, 'registry_version': intent.registry_version,
            'actions_executed': False,
        }, ensure_ascii=False)
    )


class ExpandedConversationService(InteractiveConversationService):
    """Live social-action interpretation; existing stop and memory remain primary."""

    def respond(self, content: str):
        if isinstance(content, str):
            text = content.strip()
            if ('?' not in text and '"' not in text and '`' not in text and
                    not re.search(r"\b(?:not|never|don't|if|would|could|should)\b", text, re.I)
                    and _ACTION_COMPOUND.search(text)):
                return self._guarded_reply(content, _COMPOSITE_ACTION)
            if self._session is not None:
                action = parse_user_action(content, message_id='preflight')
                if action is not None:
                    config = getattr(self._runtime, 'configuration', None)
                    if config is None:
                        raise RuntimeError('Represented actions require persistent configuration.')
                    if InteractionLedger(config.state_path).stopped(self._session.id):
                        return self._guarded_reply(content, _STOPPED_ACTION)
        return super().respond(content)

    def _build_request(self) -> CognitiveRequest:
        request = super()._build_request()
        messages = self.messages()
        if not messages or messages[-1].role is not ConversationRole.USER:
            return request
        user = messages[-1]
        intent = parse_user_action(user.content, message_id=user.id)
        if intent is None:
            return request
        config = getattr(self._runtime, 'configuration', None)
        if config is None or InteractionLedger(config.state_path).stopped(user.session_id):
            raise RuntimeError('Interaction stop changed before action projection.')
        return CognitiveRequest(
            messages=(CognitiveMessage(role=CognitiveRole.SYSTEM,
                                       content=action_prompt(intent)), *request.messages),
            tools=request.tools,
        )
