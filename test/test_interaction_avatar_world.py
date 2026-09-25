"""Avatar-world interpretation tests; no live model or production state access."""
from dataclasses import replace
from pathlib import Path
import json

import pytest

from sofia.application.bootstrap import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.defaults import create_default_configuration
from sofia.embodiment.store import AvatarStore
from sofia.interaction.avatar_world import avatar_world_guidance, gesture_provider_view
from sofia.interaction.chat import interaction_prompt
from sofia.interaction.expanded_service import _without_prescribed_gesture_reactions
from sofia.interaction.grammar import NaturalInteractionEngine
from sofia.personality.expression import personality_expression_guidance

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'sofia'


def _left_ear_decision():
    from datetime import datetime, timezone

    engine = NaturalInteractionEngine(AvatarStore(ROOT / 'data' / 'avatar.json').load())
    decision = engine.from_text(
        content='*pats your left ear*', message_id='isolated-ear',
        session_id='isolated-session', occurred_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
    )
    assert decision is not None and decision.status == 'accepted'
    return decision


def test_avatar_world_distinguishes_representation_offer_emotion_and_actual_capability():
    guidance = avatar_world_guidance()
    assert 'canonical representational body is her avatar' in guidance
    assert 'whether or not a renderer is currently visible' in guidance
    assert 'real-world touch' in guidance
    assert 'actual capabilities' in guidance
    assert 'proposal' in guidance
    assert 'not proof of subjective feelings' in guidance
    assert 'No emotion forces a particular gesture' in guidance
    assert 'without the corresponding verified result' in guidance
    assert guidance in personality_expression_guidance()


def test_provider_view_retains_policy_without_prescribing_exact_cue_or_emotion():
    original = interaction_prompt(_left_ear_decision())
    assert '*one ear flicks*' in original
    viewed = gesture_provider_view(original)
    assert viewed is not None
    assert '*one ear flicks*' not in viewed
    assert 'optional_representational_text_cues' not in viewed
    assert 'possible_modeled_emotions_not_actual_feelings' not in viewed
    original_decision = json.loads(original.rsplit('\n', 1)[-1])
    projected = json.loads(viewed.rsplit('\n', 1)[-1])
    assert projected == {key: original_decision[key] for key in (
        'registry_version', 'region_id', 'gesture', 'phase', 'policy_status',
        'policy_reason',
    )}
    assert original_decision['region_id'] == 'left-ear'
    assert original_decision['gesture'] == 'pat'
    assert original_decision['policy_status'] == 'accepted'
    assert 'NOT Sofía\'s consent' in viewed
    assert 'No emotional response or gesture is prescribed' in viewed
    assert '*one ear flicks*' in original  # The canonical decision is unchanged.


def test_provider_view_passes_unrelated_prompts_and_rejects_bad_trusted_data():
    assert gesture_provider_view('ordinary system context') is None
    from sofia.interaction.avatar_world import _GESTURE_MARKER
    with pytest.raises(ValueError, match='Invalid reviewed gesture decision'):
        gesture_provider_view(_GESTURE_MARKER + '\nnot JSON')
    with pytest.raises(ValueError, match='missing policy data'):
        gesture_provider_view(_GESTURE_MARKER + '\n{}')


def test_provider_view_does_not_change_unrelated_request():
    from sofia.cognition.model import CognitiveMessage, CognitiveRequest
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content='Can you physically sense my hand?'),))
    assert _without_prescribed_gesture_reactions(request) is request


@pytest.mark.parametrize('text,kind', (
    ('*pats your left ear*', 'gesture'),
    ('I ask to hug you', 'offer'),
    ('Can you physically sense my hand through an actual sensor?', 'real-world'),
))
def test_real_application_delivers_avatar_distinction_without_live_ollama(
    monkeypatch, tmp_path, text, kind,
):
    monkeypatch.setenv('SOFIA_IDLE_REFLECTIONS', '0')
    captured = []

    def fake_ollama_once(self, request):
        captured.append(request)
        return CognitiveResponse(content='Isolated response.')

    monkeypatch.setattr(OllamaProvider, '_respond_once', fake_ollama_once)
    configuration = replace(
        create_default_configuration(),
        state_path=tmp_path / 'isolated-avatar-world.db',
        filesystem_root=tmp_path,
    )
    application = SofiaApplication(configuration)
    try:
        application.start()
        captured.clear()
        assert application.conversation.respond(text).content == 'Isolated response.'
        assert len(captured) == 1
        request = captured[0]
        # Current main exposes the authorized cognitive tool surface to Ollama.
        # Presence of tools does not mean any tool was called or action executed.
        assert request.tools
        tool_names = {tool.name for tool in request.tools}
        assert 'tool_catalog' in tool_names
        assert len(tool_names) == len(request.tools)
        assert request.messages[-1].role is CognitiveRole.USER
        assert request.messages[-1].content == text
        system = '\n'.join(message.content for message in request.messages
                           if message.role is CognitiveRole.SYSTEM)
        assert 'AVATAR-WORLD CONVERSATIONAL INTERPRETATION' in system
        assert 'CURRENT AVATAR PRESENTATION' in system
        assert '"outfit_id": "engineer.signature"' in system
        assert 'actual capabilities' in system
        assert 'No emotion forces a particular gesture' in system
        if kind == 'gesture':
            assert 'TRUSTED INTERACTION INTERPRETATION' in system
            assert '"region_id": "left-ear"' in system
            assert '"policy_status": "accepted"' in system
            assert '*one ear flicks*' not in system
            assert 'optional_representational_text_cues' not in system
        elif kind == 'offer':
            assert 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION' in system
            assert '"action_id": "hug"' in system
            assert '"modality": "offered"' in system
            assert '"actions_executed": false' in system
            assert 'neither an offer nor an acceptance means' in system
        else:
            assert 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION' not in system
            assert 'TRUSTED INTERACTION INTERPRETATION' not in system
    finally:
        application.shutdown()
    assert not (tmp_path / 'sofia.db').exists()
