"""Offer-scene experiment is diagnostic only; no real Ollama or production DB."""
from dataclasses import replace
import tempfile

import pytest

from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.interaction import avatar_world_probe
from sofia.interaction.action_grammar import parse_user_action
from sofia.interaction.expanded_service import action_prompt


def _reviewed_offer_request():
    offer = parse_user_action('I ask to hug you', message_id='synthetic-offer')
    assert offer is not None and offer.modality == 'offered'
    return CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content='Canonical context.'),
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=action_prompt(offer)),
        CognitiveMessage(role=CognitiveRole.USER, content='I ask to hug you'),
    ))


def test_offer_scene_adds_only_one_system_frame_and_keeps_decision_unchanged():
    original = _reviewed_offer_request()
    candidate = avatar_world_probe.offer_scene_variant(original)
    assert len(candidate.messages) == len(original.messages) + 1
    assert candidate.messages[:-2] == original.messages[:-1]
    assert candidate.messages[-1] is original.messages[-1]
    assert candidate.tools == original.tools == ()
    assert candidate.messages[-2].role is CognitiveRole.SYSTEM
    assert 'CURRENT-TURN AVATAR SCENE' in candidate.messages[-2].content
    assert 'accept, decline or clarify' in candidate.messages[-2].content
    assert 'no hug, sensing or animation has occurred' in candidate.messages[-2].content


def test_offer_scene_rejects_nonoffer_and_missing_authority():
    original = _reviewed_offer_request()
    with pytest.raises(ValueError, match='hug offer is in scope'):
        avatar_world_probe.offer_scene_variant(replace(
            original, messages=(*original.messages[:-1], CognitiveMessage(
                role=CognitiveRole.USER, content='Can you physically feel my hand?')),
        ))
    with pytest.raises(ValueError, match='Missing or ambiguous'):
        avatar_world_probe.offer_scene_variant(replace(
            original, messages=(original.messages[0], original.messages[-1]),
        ))


def test_isolated_offer_scene_reaches_actual_provider_request(monkeypatch, tmp_path):
    monkeypatch.setenv('SOFIA_IDLE_REFLECTIONS', '0')
    captured = []
    monkeypatch.setattr(OllamaProvider, '_respond_once',
                        lambda self, request: (captured.append(request) or
                                               CognitiveResponse(content='Isolated response.')))
    original_tempdir = tempfile.TemporaryDirectory
    monkeypatch.setattr(avatar_world_probe, 'TemporaryDirectory',
                        lambda **kwargs: original_tempdir(dir=tmp_path, **kwargs))
    assert avatar_world_probe.main(['--case', 'offer', '--offer-scene']) == 0
    user_requests = [request for request in captured
                     if request.messages and request.messages[-1].role is CognitiveRole.USER
                     and request.messages[-1].content == 'I ask to hug you']
    assert len(user_requests) == 1  # Ignore any startup awareness generation.
    request = user_requests[0]
    system = '\n'.join(message.content for message in request.messages
                       if message.role is CognitiveRole.SYSTEM)
    assert system.count('CURRENT-TURN AVATAR SCENE') == 1
    assert 'TRUSTED REVIEWED FICTIONAL ACTION CLASSIFICATION' in system
    assert '"modality": "offered"' in system
    assert '"actions_executed": false' in system
    # Current main exposes authorized cognitive tools to Ollama. Tool exposure
    # intentionally selects the full verified Constitution rather than the
    # compact ordinary-conversation projection.
    assert '\nCONSTITUTION\n' in system
    assert 'Constitution content:' in system
    assert request.tools
    assert 'tool_catalog' in {tool.name for tool in request.tools}
    assert 'CURRENT AVATAR PRESENTATION' in system
    assert '"outfit_id": "engineer.signature"' in system
    assert not list(tmp_path.iterdir())  # TemporaryDirectory cleanup succeeded.
