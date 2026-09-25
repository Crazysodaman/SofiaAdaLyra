"""Explicitly opt-in live conversation integration for ONE reviewed avatar offer.

Default conversation behavior is unchanged. This host path owns saved USER
provenance, constructs the canonical provider-bound context, runs a tool-free
choice/expression through the configured cognitive engine, and atomically
rechecks policy while saving the ASSISTANT reply. No preference, consent,
physical action, renderer event or tool authorization is written.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sofia.cognition.context import CognitiveContext
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import CognitiveResponse
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.architecture_compare import OFFER
from sofia.interaction.atomic_offer_release import commit_guarded_offer_reply
from sofia.interaction.decision_expression import from_reviewed_action
from sofia.interaction.trusted_offer_gate import (
    GuardedOfferResult, _policy_gate, run_guarded_offer,
)


_ENV = 'SOFIA_INTERACT_STAGED_OFFERS'


def staged_offers_enabled() -> bool:
    """Conservative opt-in; malformed configuration must not silently enable."""
    value = os.environ.get(_ENV, '').strip().lower()
    if value in ('', '0', 'false', 'off'):
        return False
    if value in ('1', 'true', 'on'):
        return True
    raise ValueError(_ENV + ' must be 1 or 0 (also accepts true/false).')


def _canonical_offer_request(runtime, conversation_request):
    """Use the existing runtime's verified state and configured assembler.

    Keep the model setting, canonical self-state, bounded memories, emotional
    projections and original transcript. Never reuse a synthetic test context.
    The dispatcher has no role: this interaction route has zero tools.
    """
    context = CognitiveContext(
        request=conversation_request,
        identity=runtime.identity,
        personality=runtime.personality,
        constitution=runtime.constitution,
        embodiment=runtime.embodiment,
        core_state=runtime.core_state,
        memories=runtime.memory_system.recall_relevant(OFFER),
        operational_state=runtime.operational_state,
        runtime_continuity=runtime.runtime_continuity,
        workspace_changes=runtime.workspace_changes,
        operational_self_model=runtime.operational_self_model,
    )
    assembled = runtime.cognitive_system.context_assembler.assemble(
        context, tools=(),
    )
    if assembled.tools:
        raise RuntimeError('Avatar offer assembly may not expose tools.')
    return assembled


def respond_staged_offer(service, content: str) -> CognitiveResponse:
    """Persist one exact USER offer, then only an atomically releasable reply.

    A blocked offer is checked BEFORE ordinary context assembly, which may
    itself reject known boundaries. The transactional release rechecks policy.
    Failure keeps the original saved USER turn, never retries unguarded.
    """
    if content != OFFER:
        raise ValueError('Only the exact grammar-reviewed hug offer is supported.')
    if service._session is None:
        raise RuntimeError('A started conversation session is required.')
    runtime = service._runtime
    config = runtime.configuration
    if (config.provider.provider != 'ollama'
            or config.provider.model != 'qwen3:14b'
            or not isinstance(runtime.cognitive_system.engine, LLMCognitiveEngine)):
        raise RuntimeError('Staged avatar offers require the configured qwen3:14b engine.')
    service._active_user_requests += 1
    try:
        with service._model_lock:
            session_id = service._session.id
            user = ConversationMessage(
                id=str(uuid4()), session_id=session_id, role=ConversationRole.USER,
                content=content, created_at=datetime.now(timezone.utc),
            )
            service._conversation_store.save(user)
            intent = parse_user_action(user.content, message_id=user.id)
            if (intent is None or intent.modality != 'offered'
                    or intent.action_id != 'hug'):
                raise RuntimeError('Saved user turn failed reviewed offer grammar.')
            frame = from_reviewed_action(user_text=user.content, intent=intent)
            # ExpandedConversationService._build_request intentionally raises
            # for an active boundary. Return a source-checked blocked result
            # instead of building any model request. Commit rechecks under lock.
            blocked = _policy_gate(state_path=Path(config.state_path), session_id=session_id)
            if blocked is not None:
                result = GuardedOfferResult(status=blocked)
            else:
                conversation_request = service._build_request()
                base = _canonical_offer_request(runtime, conversation_request)
                result = run_guarded_offer(
                    provider=runtime.cognitive_system.engine,
                    base=base, frame=frame, state_path=config.state_path,
                    session_id=session_id,
                )
            reply = commit_guarded_offer_reply(
                state_path=config.state_path, session_id=session_id,
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
