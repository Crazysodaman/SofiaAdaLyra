"""The live adapter must not manufacture an executed social action."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.conversation.model import ConversationRole
from sofia.interaction.chat import InteractiveConversationService
from sofia.interaction.expanded_service import ExpandedConversationService
from sofia.interaction.ledger import InteractionLedger

NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


def test_saved_action_projects_source_linked_nonexecution(monkeypatch, tmp_path):
    original = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='I ask to hug you'),))
    monkeypatch.setattr(InteractiveConversationService, '_build_request',
                        lambda self: original)
    user = SimpleNamespace(id='saved-1', session_id='session-1',
                           content='I ask to hug you',
                           role=ConversationRole.USER, created_at=NOW)
    monkeypatch.setattr(ExpandedConversationService, 'messages',
                        lambda self: (user,))
    service = object.__new__(ExpandedConversationService)
    service._runtime = SimpleNamespace(configuration=SimpleNamespace(
        state_path=tmp_path / 'isolated.db'))
    request = service._build_request()
    assert request.messages[-1] is original.messages[-1]
    instruction = request.messages[0].content
    assert '"actor": "user"' in instruction
    assert '"target": "sofia"' in instruction
    assert '"action_id": "hug"' in instruction
    assert '"modality": "offered"' in instruction
    assert '"actions_executed": false' in instruction
    assert InteractionLedger(tmp_path / 'isolated.db').accepted('saved-1') is None


def test_stopped_social_action_is_handled_before_model(monkeypatch, tmp_path):
    db = tmp_path / 'isolated.db'
    ledger = InteractionLedger(db)
    ledger.control(session_id='session-1', message_id='stop-1',
                   content='Sofía, stop interactions', occurred_at=NOW)
    service = object.__new__(ExpandedConversationService)
    service._session = SimpleNamespace(id='session-1')
    service._runtime = SimpleNamespace(configuration=SimpleNamespace(state_path=db))
    monkeypatch.setattr(ExpandedConversationService, '_guarded_reply',
                        lambda self, content, reply: reply)
    monkeypatch.setattr(InteractiveConversationService, 'respond',
                        lambda self, content: pytest.fail('Blocked action reached model.'))
    reply = service.respond('I hug you')
    assert 'paused' in reply
    assert ledger.accepted('stop-1') is None


def test_compound_social_actions_not_projected_as_completed(monkeypatch):
    service = object.__new__(ExpandedConversationService)
    monkeypatch.setattr(ExpandedConversationService, '_guarded_reply',
                        lambda self, content, reply: reply)
    reply = service.respond('I hug you and kiss your cheek')
    assert 'not treated any as completed' in reply
