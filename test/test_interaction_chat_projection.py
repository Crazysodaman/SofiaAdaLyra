"""Headless chat integration tests; never call the model or the real desktop."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.conversation.model import ConversationRole
from sofia.embodiment.store import AvatarStore
from sofia.interaction.chat import (
    InteractiveConversationService,
    representational_experience_followup_prompt,
)

AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"


def _service(
    monkeypatch,
    content,
    *,
    personality=True,
    avatar=True,
    route_hint=None,
):
    original_user = CognitiveMessage(role=CognitiveRole.USER, content=content)
    original = CognitiveRequest(
        messages=(original_user,),
        route_hint=route_hint,
    )
    monkeypatch.setattr(EmotionalConversationService, "_build_request", lambda self: original)
    user = SimpleNamespace(id="message-1", session_id="session-1",
                           role=ConversationRole.USER, content=content,
                           created_at=datetime.now(timezone.utc))
    monkeypatch.setattr(InteractiveConversationService, "messages", lambda self: (user,))
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(
        personality=object() if personality else None,
        embodiment=AvatarStore(AVATAR).load() if avatar else None,
    )
    return service, original


def test_text_ear_interaction_projects_same_shared_policy_without_renderer(monkeypatch):
    service, original = _service(monkeypatch, "*taps your left ear*")
    result = service._build_request()
    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert '"region_id": "left-ear"' in result.messages[0].content
    assert '"gesture": "tap"' in result.messages[0].content
    assert '"policy_status": "accepted"' in result.messages[0].content
    assert '"interaction_preference_evidence": "unspecified"' in result.messages[0].content
    assert '"willingness_state": "undetermined"' in result.messages[0].content
    assert "*one ear flicks*" in result.messages[0].content
    assert "NOT sensed" in result.messages[0].content
    assert result.messages[-1] is original.messages[-1]
    assert original.messages[0].content == "*taps your left ear*"


def test_sensitive_region_is_recognized_without_mandatory_favorable_reaction(monkeypatch):
    service, _ = _service(monkeypatch, "*touches your groin*")
    result = service._build_request()
    prompt = result.messages[0].content
    assert '"policy_status": "accepted"' in prompt
    assert '"region_id": "groin"' in prompt
    assert '"gesture": "touch"' in prompt
    assert "does NOT mean" in prompt
    assert "negatively" in prompt
    assert '"optional_representational_text_cues": []' in prompt
    assert '"possible_modeled_emotions_not_actual_feelings": [' in prompt
    assert '"fondness"' in prompt and '"caution"' in prompt and '"frustration"' in prompt


@pytest.mark.parametrize("content", ["Tell me about your tail", "How do I pat your head?", "```pats your head```"])
def test_discussion_and_code_do_not_generate_an_interaction_projection(monkeypatch, content):
    service, original = _service(monkeypatch, content)
    assert service._build_request() is original


@pytest.mark.parametrize("personality,avatar", [(False, True), (True, False)])
def test_missing_personality_or_canonical_embodiment_does_not_invent_one(monkeypatch, personality, avatar):
    service, original = _service(monkeypatch, "*pats your head*",
                                 personality=personality, avatar=avatar)
    assert service._build_request() is original



def test_empty_tool_surface_does_not_skip_interaction_projection(monkeypatch):
    service, original = _service(monkeypatch, "*taps your left ear*")
    assert original.allow_tools is True
    assert original.tools == ()

    result = service._build_request()

    assert result.messages[0].role is CognitiveRole.SYSTEM
    assert "TRUSTED INTERACTION INTERPRETATION" in result.messages[0].content


def test_real_exposed_tool_surface_is_preserved(monkeypatch):
    from sofia.cognition.model import CognitiveToolDefinition

    tool = CognitiveToolDefinition(
        name="hardware.inspect",
        description="Inspect actual hardware capability.",
        parameters={"type": "object"},
    )
    original_user = CognitiveMessage(
        role=CognitiveRole.USER,
        content="Can you inspect the actual sensor hardware?",
    )
    original = CognitiveRequest(
        messages=(original_user,),
        tools=(tool,),
        allow_tools=True,
    )
    monkeypatch.setattr(
        EmotionalConversationService,
        "_build_request",
        lambda self: original,
    )
    user = SimpleNamespace(
        id="message-tool-1",
        session_id="session-1",
        role=ConversationRole.USER,
        content=original_user.content,
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(
        InteractiveConversationService,
        "messages",
        lambda self: (user,),
    )
    service = object.__new__(InteractiveConversationService)
    service._runtime = SimpleNamespace(
        personality=object(),
        embodiment=AvatarStore(AVATAR).load(),
    )

    result = service._build_request()

    assert result is original
    assert result.tools == (tool,)


def test_interaction_prompt_rejects_ungrounded_relationship_and_sensation_language(
    monkeypatch,
):
    service, _ = _service(monkeypatch, "*pats your head*")

    result = service._build_request()

    prompt = result.messages[0].content
    assert "Do not say the gesture 'feels good'" in prompt
    assert "Do not invent relationship titles" in prompt
    assert "Do not pivot a simple gesture into a diagnostic/work menu" in prompt
    assert "prefer a short natural response" in prompt


def _interaction_request_for_test(content="*pats your head*"):
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="TRUSTED INTERACTION INTERPRETATION\n{}",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=content,
            ),
        ),
        tools=(),
        allow_tools=False,
    )


def test_invalid_physical_sensation_is_retried_before_persistence():
    class Runtime:
        def __init__(self):
            self.calls = []

        def respond(
            self,
            request,
            *,
            filesystem_results=(),
            principal=None,
            context_plan=None,
        ):
            self.calls.append(request)
            return CognitiveResponse(
                content="*My ears flick.* Thanks, Sparks."
            )

    service = object.__new__(InteractiveConversationService)
    service._runtime = Runtime()
    request = _interaction_request_for_test()

    result = service._finalize_response(
        request,
        CognitiveResponse(
            content=(
                "Feeling the weight of that pat settle is nice. "
                "The tactile feedback keeps me grounded."
            )
        ),
        principal=None,
    )

    assert result.content == "*My ears flick.* Thanks, Sparks."
    assert len(service._runtime.calls) == 1
    correction = service._runtime.calls[0].messages[0]
    assert correction.role is CognitiveRole.SYSTEM
    assert "GROUNDING CORRECTION" in correction.content


@pytest.mark.parametrize(
    "draft",
    (
        "I felt a subtle grounding warmth spread across my hips.",
        "The fabric slid softly against my skin and I felt it.",
        "*Eyes flick to the side, then back—",
        "You are my creator and companion.",
    ),
)
def test_repeated_invalid_interaction_reply_uses_grounded_fallback(draft):
    class Runtime:
        def respond(
            self,
            request,
            *,
            filesystem_results=(),
            principal=None,
            context_plan=None,
        ):
            return CognitiveResponse(content=draft)

    service = object.__new__(InteractiveConversationService)
    service._runtime = Runtime()

    result = service._finalize_response(
        _interaction_request_for_test(),
        CognitiveResponse(content=draft),
        principal=None,
    )

    assert "literally felt physical contact" in result.content
    assert result.content != draft


def test_clothing_presentation_request_gets_grounded_interaction_context(
    monkeypatch,
):
    service, _ = _service(monkeypatch, "show me ur panties")

    result = service._build_request()

    prompt = result.messages[0].content
    assert "TRUSTED REPRESENTATIONAL PRESENTATION REQUEST" in prompt
    assert "must not invent current clothing" in prompt
    assert "must not claim tactile fabric-on-skin sensation" in prompt


def test_how_did_u_feel_followup_is_grounded_from_prior_presentation():
    messages = (
        SimpleNamespace(
            role=ConversationRole.USER,
            content="show me ur panties",
        ),
        SimpleNamespace(
            role=ConversationRole.ASSISTANT,
            content="generated prior reply",
        ),
        SimpleNamespace(
            role=ConversationRole.USER,
            content="how did u feel doing it",
        ),
    )

    prompt = representational_experience_followup_prompt(
        content="how did u feel doing it",
        messages=messages,
    )

    assert prompt is not None
    assert "TRUSTED REPRESENTATIONAL EXPERIENCE FOLLOW-UP" in prompt
    assert "Prior assistant-generated wording is not authoritative" in prompt
    assert "must not be reused as proof" in prompt


def test_interaction_projection_preserves_matrix_route_hint(monkeypatch):
    service, _ = _service(
        monkeypatch,
        "*pats your head*",
        route_hint="standard",
    )

    result = service._build_request()

    assert result.route_hint == "standard"
