"""Opt-in ambiguity clarification for narrowly reviewed hug questions.

Question wording cannot establish whether the user meant avatar fiction or
real contact. No model inference, action, consent, preference, sensor reading,
or animation is justified by a question. The owning host persists both turns
and atomically rechecks independently source-attested stop/boundary records.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sofia.cognition.model import CognitiveResponse
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply
from sofia.interaction.decision_expression import CandidateChoice
from sofia.interaction.reviewed_hug_question import (
    CLARIFICATION, is_reviewed_hug_question,
)
from sofia.interaction.trusted_offer_gate import GuardedOfferResult, _policy_gate


def respond_reviewed_hug_question(service, content: str) -> CognitiveResponse:
    """Save exact reviewed question; never infer or issue a permission grant."""
    if not is_reviewed_hug_question(content):
        raise ValueError('Only a complete reviewed ambiguous hug question is supported.')
    if service._session is None:
        raise RuntimeError('A started conversation session is required.')
    service._active_user_requests += 1
    try:
        with service._model_lock:
            session_id = service._session.id
            path = Path(service._runtime.configuration.state_path)
            user = ConversationMessage(
                id=str(uuid4()), session_id=session_id, role=ConversationRole.USER,
                content=content, created_at=datetime.now(timezone.utc),
            )
            service._conversation_store.save(user)
            blocked = _policy_gate(state_path=path, session_id=session_id)
            result = (GuardedOfferResult(status=blocked) if blocked is not None else
                      GuardedOfferResult(
                          status='responded',
                          choice=CandidateChoice('clarify', 'Ambiguous question; no consent inferred.'),
                          response=CLARIFICATION,
                      ))
            reply = commit_guarded_offer_reply(
                state_path=path, session_id=session_id,
                user_message_id=user.id, user_content=user.content, result=result,
            )
            updated = service._conversation_store.get_session(session_id)
            if updated is None:
                raise RuntimeError('Conversation session vanished after reply persistence.')
            service._session = updated
            return CognitiveResponse(content=reply)
    finally:
        service._last_user_activity = monotonic()
        service._active_user_requests -= 1
