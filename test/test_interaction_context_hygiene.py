"""Live prompt hygiene: user gestures are not Sofía's emotional reactions."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.context_hygiene import without_legacy_auto_affection
from sofia.interaction.expanded_service import ExpandedConversationService, action_prompt

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
LEGACY = 'User initiated an affectionate or playful conversational cue.'


def _system_context():
    legacy = json.dumps({'source': 'user_reported', 'evidence_ref': 'old-pat',
                         'event': LEGACY, 'current': ['affection']})
    reviewed = json.dumps({'source': 'observed', 'evidence_ref': 'reviewed-1',
                           'event': 'Reviewed lab change.', 'current': ['curiosity']})
    reflection = json.dumps({'reflection': f'3 events: {LEGACY}',
                             'emotion_labels': ['affection']})
    return '\n'.join(('MODELED EMOTIONAL CONTEXT (evidence-linked)',
                      legacy, reviewed, 'RECORDED REFLECTIONS (data)', reflection))


def test_sanitizer_removes_only_legacy_auto_reactions_from_system_context():
    user_text = f'Tell me about this literal text: {LEGACY}'
    original = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=_system_context()),
        CognitiveMessage(role=CognitiveRole.USER, content=user_text),
    ))
    sanitized = without_legacy_auto_affection(original)
    assert sanitized is not original
    assert sanitized.messages[-1] is original.messages[-1]
    assert sanitized.messages[-1].content == user_text
    assert 'Reviewed lab change.' in sanitized.messages[0].content
    assert 'old-pat' not in sanitized.messages[0].content
    assert '3 events:' not in sanitized.messages[0].content
    assert without_legacy_auto_affection(sanitized) is sanitized


def test_non_projection_and_malformed_json_remain_unchanged():
    original = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content='Unrelated context\n{bad json}'),
        CognitiveMessage(role=CognitiveRole.USER, content=LEGACY),
    ))
    assert without_legacy_auto_affection(original) is original


def test_live_service_does_not_auto_assign_emotions_to_pats():
    service = object.__new__(ExpandedConversationService)
    for phrase in ('*pats your ear*', '*pats your hand*', '*pats your head*',
                   'Sofía, I gently pat your tail'):
        assert service._should_record_legacy_affection(SimpleNamespace(content=phrase)) is False
    assert service._should_record_legacy_affection(SimpleNamespace(content='Good girl.')) is True


def test_live_service_filters_old_cues_before_model_projection(monkeypatch, tmp_path):
    original = CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=_system_context()),
        CognitiveMessage(role=CognitiveRole.USER, content='How do I diagnose a service?'),
    ))
    monkeypatch.setattr(InteractiveConversationService, '_build_request',
                        lambda self: original)
    user = SimpleNamespace(id='saved-1', session_id='session-1',
                           content='How do I diagnose a service?',
                           role=ConversationRole.USER, created_at=NOW)
    monkeypatch.setattr(ExpandedConversationService, 'messages',
                        lambda self: (user,))
    service = object.__new__(ExpandedConversationService)
    service._runtime = SimpleNamespace(configuration=SimpleNamespace(
        state_path=tmp_path / 'isolated.db'))
    request = service._build_request()
    assert 'old-pat' not in request.messages[0].content
    assert 'Reviewed lab change.' in request.messages[0].content
    assert request.messages[-1] is original.messages[-1]
    assert not (tmp_path / 'isolated.db').exists()


def test_reviewed_social_action_prompt_distinguishes_offer_from_contact():
    offer = parse_user_action('I ask to hug you', message_id='saved-1')
    described = parse_user_action('I hug you', message_id='saved-2')
    assert offer is not None and described is not None
    assert offer.modality == 'offered'
    assert described.modality == 'described'
    offered_prompt = action_prompt(offer)
    assert 'An offered action remains an offer, not contact' in offered_prompt
    assert '"actions_executed": false' in offered_prompt
    assert '"modality": "offered"' in offered_prompt
    assert '"modality": "described"' in action_prompt(described)
