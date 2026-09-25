"""Trace actual CLI application -> runtime -> Ollama request without live model or DB.

Use canonical source records with a temporary filesystem/state database. Capture
only in memory; never print or persist provider prompts or access state/sofia.db.
Classification is NOT consent, physical sensing, or action execution.
"""
from dataclasses import replace

import pytest

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration
from sofia.interaction.ledger import InteractionLedger


@pytest.mark.parametrize('text,region,gesture,kind', (
    ('Good girl, gently touches your butt', 'buttocks', 'touch', 'gesture'),
    ('*pats your left ear*', 'left-ear', 'pat', 'gesture'),
    ('gropes your butt', 'buttocks', 'intimate-touch', 'gesture'),
    ('I ask to hug you', None, None, 'offer'),
))
def test_real_application_projects_saved_user_action_to_ollama(
    monkeypatch, tmp_path, text, region, gesture, kind,
):
    monkeypatch.setenv('SOFIA_IDLE_REFLECTIONS', '0')
    captured = []

    def fake_ollama_once(self, request):
        captured.append(request)
        return CognitiveResponse(content='Isolated test response.')

    monkeypatch.setattr(OllamaProvider, '_respond_once', fake_ollama_once)
    configuration = replace(
        create_default_configuration(),
        state_path=tmp_path / 'isolated-sofia.db',
        filesystem_root=tmp_path,
    )
    application = SofiaApplication(configuration)
    try:
        application.start()
        captured.clear()  # Ignore any startup-awareness generation.
        response = application.conversation.respond(text)
        assert response.content == 'Isolated test response.'
        assert len(captured) == 1  # No model call, retry, or tools in this test.
        request = captured[0]
        assert request.tools == ()
        assert request.messages[-1].role is CognitiveRole.USER
        assert request.messages[-1].content == text
        assert 'CONSTITUTION (bounded conversational projection)' in request.messages[0].content
        system = '\n'.join(
            message.content for message in request.messages
            if message.role is CognitiveRole.SYSTEM
        )
        last_saved_user = next(
            message for message in reversed(application.conversation.messages())
            if message.role.value == 'user'
        )
        ledger = InteractionLedger(configuration.state_path)
        if kind == 'offer':
            assert 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION' in system
            assert '"action_id": "hug"' in system
            assert '"modality": "offered"' in system
            assert '"actions_executed": false' in system
            assert ledger.accepted(last_saved_user.id) is None
        else:
            assert 'TRUSTED INTERACTION INTERPRETATION' in system
            assert f'"region_id": "{region}"' in system
            assert f'"gesture": "{gesture}"' in system
            assert '"policy_status": "accepted"' in system
            assert ledger.accepted(last_saved_user.id) == (
                last_saved_user.session_id, region, gesture,
            )
    finally:
        application.shutdown()
    assert not (tmp_path / 'sofia.db').exists()
