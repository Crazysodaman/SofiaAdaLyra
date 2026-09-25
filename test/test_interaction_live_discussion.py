"""Real-CLI hypothetical regression: explanation is not executed contact."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.body_discussion import body_discussion_prompt
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.grammar import NaturalInteractionEngine

AVATAR = Path(__file__).resolve().parents[1] / 'src' / 'sofia' / 'data' / 'avatar.json'
NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


def test_actual_hypothetical_chat_is_read_only_and_all_regions_contextual(monkeypatch, tmp_path):
    content = 'Rubs your head, what happens if I pat your tail or rub your chest?'
    original = CognitiveRequest(messages=(CognitiveMessage(role=CognitiveRole.USER, content=content),))
    monkeypatch.setattr(EmotionalConversationService, '_build_request', lambda self: original)
    user = SimpleNamespace(id='saved-1', session_id='session-1', content=content,
                           role=ConversationRole.USER, created_at=NOW)
    monkeypatch.setattr(InteractiveConversationService, 'messages', lambda self: (user,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(personality=object(), embodiment=AvatarStore(AVATAR).load(),
                                       configuration=SimpleNamespace(state_path=tmp_path / 'sofia.db'))
    result = service._build_request()
    assert result.messages[-1] is original.messages[-1]
    prompt = result.messages[0].content
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert 'actions_executed": false' in prompt
    assert '"region_id": "head"' in prompt
    assert '"region_id": "tail"' in prompt
    assert '"region_id": "chest"' in prompt
    assert prompt.count('"policy": "contextual_requires_new_explicit_single_action"') == 3
    assert 'canonical represented body' in prompt
    assert 'classification is not consent' in prompt
    assert not (tmp_path / 'sofia.db').exists()
    assert not (tmp_path / 'sofia-lab.db').exists()


def test_ordinary_anatomy_question_and_how_to_remain_regular_chat():
    engine = NaturalInteractionEngine(AvatarStore(AVATAR).load())
    assert body_discussion_prompt(content='Tell me about your tail', engine=engine) is None
    assert body_discussion_prompt(content='How do I pat your head?', engine=engine) is None
    assert body_discussion_prompt(content='*pats your head*', engine=engine) is None
    prompt = body_discussion_prompt(content='If I touch your chest?', engine=engine)
    assert prompt is not None
    assert '"region_id": "chest"' in prompt
    assert '"policy": "contextual_requires_new_explicit_single_action"' in prompt
