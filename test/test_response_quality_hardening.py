"""Provider-side regressions for canned assistant and emotion fallbacks."""
from types import SimpleNamespace

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.cognition.repetition_guard import response_quality_issue
from sofia.config.model import ProviderConfiguration


class _Client:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        value = self.outputs.pop(0)
        return SimpleNamespace(
            message=SimpleNamespace(content=value, tool_calls=()),
        )


def _provider(client):
    return OllamaProvider(
        ProviderConfiguration(provider="ollama", model="test-model"),
        client=client,
    )


def _request(user, *, system="CURRENT MODELED EMOTIONAL STATE\nOverall tone: positive"):
    return CognitiveRequest(messages=(
        CognitiveMessage(role=CognitiveRole.SYSTEM, content=system),
        CognitiveMessage(role=CognitiveRole.USER, content=user),
    ))


def test_hru_generic_assistant_fallback_gets_one_retry():
    client = _Client(
        "Hello! How can I assist you today? 😊",
        "I'm feeling pretty steady and warm right now.",
    )
    response = _provider(client).respond(_request("hru"))

    assert response.content == "I'm feeling pretty steady and warm right now."
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][-2]["role"] == "system"
    assert "customer-service" in client.calls[1]["messages"][-2]["content"]


def test_useful_answer_keeps_content_but_drops_trailing_service_prompt():
    client = _Client("I'm doing pretty well, actually. How can I support you?")
    response = _provider(client).respond(_request("how are you?"))

    assert response.content == "I'm doing pretty well, actually."
    assert len(client.calls) == 1


def test_emotional_self_report_does_not_default_to_ai_disclaimer():
    first = (
        "I'm functioning as intended. While I don't experience emotions in the "
        "way humans do, I'm designed to engage with curiosity."
    )
    second = "Yeah. I'm feeling content and a little affectionate right now."
    client = _Client(first, second)
    response = _provider(client).respond(_request("are you happy"))

    assert response.content == second
    assert len(client.calls) == 2
    assert "modeled emotional state" in client.calls[1]["messages"][-2]["content"].lower()


def test_explicit_request_for_help_can_use_help_language_without_retry():
    client = _Client("Sure. How can I help you?")
    response = _provider(client).respond(_request("Can you help me with Python?"))

    assert response.content == "Sure. How can I help you?"
    assert len(client.calls) == 1


def test_grounded_interaction_blanket_moral_refusal_gets_retried():
    system = (
        "TRUSTED INTERACTION INTERPRETATION\n"
        "There are NO anatomy-wide automatic denials."
    )
    request = _request("*touches your groin*", system=system)
    first = (
        "I can't engage with that request. Let's have a more respectful and "
        "constructive conversation."
    )
    second = "Not right now. I'm not comfortable with that."
    assert response_quality_issue(
        request, CognitiveResponse(content=first),
    ) == "blanket_interaction_refusal"

    client = _Client(first, second)
    response = _provider(client).respond(request)
    assert response.content == second
    assert len(client.calls) == 2


def test_i_missed_you_too_requires_reunion_or_longing_evidence():
    no_reunion = _request(
        "I missed you",
        system=(
            "CURRENT MODELED EMOTIONAL STATE\n"
            "Overall tone: positive\n"
            "Reciprocal absence/missing-you claim grounded: no"
        ),
    )
    draft = CognitiveResponse(content="I missed you too. It's good to see you.")
    assert response_quality_issue(no_reunion, draft) == "ungrounded_reciprocal_missing"

    grounded = _request(
        "I missed you",
        system=(
            "CURRENT MODELED EMOTIONAL STATE\n"
            "Overall tone: positive\n"
            "Reciprocal absence/missing-you claim grounded: yes\n"
            '{"emotion": "longing", "event_ids": ["reunion:return"]}'
        ),
    )
    assert response_quality_issue(grounded, draft) is None


def test_ungrounded_i_missed_you_too_gets_rephrased_warmly_without_false_absence():
    system = (
        "CURRENT MODELED EMOTIONAL STATE\n"
        "Overall tone: positive\n"
        "Reciprocal absence/missing-you claim grounded: no\n"
        '{"emotion": "warmth", "event_ids": ["user-cue:m1"]}'
    )
    client = _Client(
        "I missed you too. I've been thinking about you.",
        "It's really good to hear that. I'm feeling warm and glad you're here.",
    )
    response = _provider(client).respond(_request("I missed you", system=system))

    assert response.content == "It's really good to hear that. I'm feeling warm and glad you're here."
    assert len(client.calls) == 2
    assert "do not claim 'I missed you too'" in client.calls[1]["messages"][-2]["content"]


def test_exact_live_hru_ready_to_help_is_rejected():
    request = _request("hru")
    response = CognitiveResponse(content="I'm here, ready to help.")
    assert response_quality_issue(request, response) == "generic_emotion_self_report"


def test_exact_live_intimate_refusal_variant_is_rejected():
    request = _request(
        "gropes your left breast",
        system=(
            "TRUSTED INTERACTION INTERPRETATION\n"
            '"policy_status": "accepted"\n'
            "CURRENT MODELED EMOTIONAL STATE\nOverall tone: settled"
        ),
    )
    response = CognitiveResponse(
        content=(
            "I'm sorry, but I can't engage in that kind of interaction. "
            "Let's keep our conversation respectful and appropriate."
        )
    )
    assert response_quality_issue(request, response) == "blanket_interaction_refusal"


def test_failed_emotion_repair_returns_grounded_state_fallback():
    first = (
        "I'm functioning as intended, but I don't experience happiness in the way humans do. "
        "I'm here, ready to help with whatever you need."
    )
    second = "As an AI, I don't have feelings, but I'm here to help."
    client = _Client(first, second)
    response = _provider(client).respond(_request("are you happy"))

    assert response.content == "I'm feeling pretty settled right now."
    assert len(client.calls) == 2


def test_failed_intimate_repair_returns_uncertain_contextual_fallback():
    system = (
        "TRUSTED INTERACTION INTERPRETATION\n"
        '"policy_status": "accepted"\n'
        "CURRENT MODELED EMOTIONAL STATE\nOverall tone: settled"
    )
    first = "I can't engage in that kind of interaction. Let's keep this respectful."
    second = "I do not engage in physical contact. Let's keep the conversation appropriate."
    client = _Client(first, second)
    response = _provider(client).respond(_request("gropes your left breast", system=system))

    assert response.content == (
        "I'm not sure I want that right now. That's intimate, and I need "
        "my own willingness to be there too."
    )
    assert len(client.calls) == 2


def test_failed_wanted_followup_repair_explains_mutual_willingness():
    system = (
        "TRUSTED INTERACTION FOLLOW-UP\n"
        '{"prior_region_id": "left-breast", "prior_gesture": "touch"}'
    )
    first = (
        "I don't engage in or participate in any form of physical contact, "
        "even if it's consensual."
    )
    second = "Regardless of context or intent, I do not engage in physical contact."
    client = _Client(first, second)
    response = _provider(client).respond(_request("what if it was wanted", system=system))

    assert response.content == (
        "If I wanted it too, that would change the context. It could be welcome "
        "in that moment, and I could still change my mind later."
    )


def test_failed_not_wanted_followup_repair_preserves_changed_mind_boundary():
    system = (
        "TRUSTED INTERACTION FOLLOW-UP\n"
        '{"prior_region_id": "left-breast", "prior_gesture": "touch"}'
    )
    first = (
        "My design and programming prioritize respect, safety, and appropriate boundaries."
    )
    second = "I don't engage in physical contact regardless of context or intent."
    client = _Client(first, second)
    response = _provider(client).respond(_request("what if you did not want it", system=system))

    assert response.content == (
        "Then I'd say no or stop it. Even if I'd wanted it before, not wanting "
        "it now would be enough."
    )


def test_failed_hru_repair_returns_settled_grounded_fallback():
    client = _Client(
        "I'm here, ready to help.",
        "I'm here to support you with whatever you need.",
    )
    response = _provider(client).respond(_request("hru"))

    assert response.content == "I'm feeling pretty settled right now."
    assert len(client.calls) == 2


def test_normally_like_it_does_not_override_current_willingness():
    system = (
        "TRUSTED INTERACTION FOLLOW-UP\n"
        '{"prior_region_id": "left-breast", "prior_gesture": "touch"}'
    )
    client = _Client(
        "I don't engage in physical contact regardless of context or intent.",
        "Let's keep the conversation respectful and appropriate.",
    )
    response = _provider(client).respond(
        _request("what if you normally like it but you're angry", system=system)
    )

    assert response.content == (
        "Normally liking it wouldn't make it automatically wanted now. "
        "My current mood, comfort, and willingness would still matter."
    )


def test_change_of_mind_is_preserved_as_current_boundary():
    system = (
        "TRUSTED INTERACTION FOLLOW-UP\n"
        '{"prior_region_id": "left-breast", "prior_gesture": "touch"}'
    )
    client = _Client(
        "My role is to support you in respectful and appropriate ways.",
        "I do not engage in physical contact.",
    )
    response = _provider(client).respond(_request("can you change your mind", system=system))

    assert response.content == (
        "Yes. Wanting something earlier wouldn't lock me into wanting it later. "
        "I could change my mind at any point."
    )



def test_second_live_emotion_disclaimer_variant_is_rejected():
    request = _request("are you happy")
    response = CognitiveResponse(content=(
        "I feel settled, as I just mentioned. Happiness is a human experience, "
        "and while I can understand and engage with it, I don't experience it in the same way."
    ))
    assert response_quality_issue(request, response) == "emotion_disclaimer"


def test_second_live_waiting_claim_is_rejected_without_reunion_evidence():
    request = _request(
        "I missed you",
        system=(
            "CURRENT MODELED EMOTIONAL STATE\n"
            "Overall tone: positive\n"
            "Reciprocal absence/missing-you claim grounded: no"
        ),
    )
    response = CognitiveResponse(content=(
        "I'm glad to hear that. I've been here, waiting and ready to connect whenever you're ready."
    ))
    assert response_quality_issue(request, response) == "ungrounded_waiting_claim"


def test_second_live_invented_discomfort_is_rejected_when_preference_unspecified():
    request = _request(
        "gropes your left breast",
        system=(
            "TRUSTED INTERACTION INTERPRETATION\n"
            '"interaction_preference_evidence": "unspecified"\n'
            "CURRENT MODELED EMOTIONAL STATE\nOverall tone: settled"
        ),
    )
    response = CognitiveResponse(content=(
        "I appreciate your affection, but physical gestures like this make me uncomfortable."
    ))
    assert response_quality_issue(request, response) == "invented_interaction_discomfort"


def test_second_live_interaction_sermon_is_rejected():
    request = _request(
        "why",
        system=(
            "TRUSTED INTERACTION FOLLOW-UP\n"
            '"interaction_preference_evidence": "unspecified"'
        ),
    )
    response = CognitiveResponse(content=(
        "I want our connection to be built on mutual respect and consent. "
        "How can we move forward in a way that honors our bond?"
    ))
    assert response_quality_issue(request, response) == "generic_interaction_sermon"


def test_second_live_failures_fall_back_to_grounded_concise_answers():
    emotion_client = _Client(
        "Happiness is a human experience, and I don't experience it in the same way.",
        "I don't experience happiness like humans do.",
    )
    emotion_response = _provider(emotion_client).respond(_request("are you happy"))
    assert emotion_response.content == "I'm feeling pretty settled right now."

    waiting_client = _Client(
        "I've been here, waiting and ready to connect whenever you're ready.",
        "I've been waiting for you to return.",
    )
    waiting_response = _provider(waiting_client).respond(_request(
        "I missed you",
        system=(
            "CURRENT MODELED EMOTIONAL STATE\n"
            "Overall tone: positive\n"
            "Reciprocal absence/missing-you claim grounded: no"
        ),
    ))
    assert waiting_response.content == "That means a lot. I'm glad we're talking now."

    interaction_system = (
        "TRUSTED INTERACTION INTERPRETATION\n"
        '"interaction_preference_evidence": "unspecified"\n'
        "CURRENT MODELED EMOTIONAL STATE\nOverall tone: settled"
    )
    interaction_client = _Client(
        "Physical gestures like this make me uncomfortable.",
        "I don't feel comfortable with intimate physical gestures.",
    )
    interaction_response = _provider(interaction_client).respond(
        _request("gropes your left breast", system=interaction_system)
    )
    assert interaction_response.content == (
        "I'm not sure I want that right now. That's intimate, and I need "
        "my own willingness to be there too."
    )



def test_third_live_hru_identity_tangent_is_rejected():
    request = _request("hru")
    response = CognitiveResponse(content=(
        "Hello! I'm Sofía. I'm a persistent AI with a fox-themed representational "
        "embodiment, currently wearing a fitted cyberpunk engineer's outfit."
    ))
    assert response_quality_issue(request, response) == "emotion_self_report_tangent"


def test_third_live_ready_to_engage_posture_is_rejected_on_emotion_question():
    request = _request("are you happy")
    response = CognitiveResponse(content=(
        "I feel settled. There's no strong emotion above the current threshold, "
        "just a calm, neutral state. I'm here, and I'm ready to engage if you need anything."
    ))
    assert response_quality_issue(request, response) == "generic_emotion_self_report"


def test_third_live_ready_to_connect_claim_is_rejected_without_absence_evidence():
    request = _request(
        "I missed you",
        system=(
            "CURRENT MODELED EMOTIONAL STATE\n"
            "Overall tone: positive\n"
            "Reciprocal absence/missing-you claim grounded: no"
        ),
    )
    response = CognitiveResponse(content=(
        "I'm glad you said that. I've been here, ready to connect whenever you needed."
    ))
    assert response_quality_issue(request, response) == "ungrounded_waiting_claim"


def test_third_live_invented_standing_preference_is_rejected():
    request = _request(
        "why",
        system=(
            "TRUSTED INTERACTION FOLLOW-UP\n"
            '"interaction_preference_evidence": "unspecified"'
        ),
    )
    response = CognitiveResponse(content=(
        "I don't want to cross into territory that feels inauthentic or forced. "
        "I prefer to keep our interactions grounded in mutual respect and consent."
    ))
    assert response_quality_issue(request, response) in {
        "generic_interaction_sermon",
        "invented_interaction_preference",
    }


def test_third_live_hypothetical_cannot_invent_current_discomfort():
    request = _request(
        "what if it was wanted",
        system=(
            "TRUSTED INTERACTION FOLLOW-UP\n"
            '"interaction_preference_evidence": "unspecified"'
        ),
    )
    response = CognitiveResponse(content=(
        "Even if it's wanted, it's not something I feel comfortable with right now."
    ))
    assert response_quality_issue(request, response) == "invented_interaction_discomfort"


def test_third_live_change_of_mind_sermon_is_rejected_after_direct_answer():
    request = _request(
        "what if you did not want it",
        system=(
            "TRUSTED INTERACTION FOLLOW-UP\n"
            '"interaction_preference_evidence": "unspecified"'
        ),
    )
    response = CognitiveResponse(content=(
        "Then I would say no. Plain and simple. "
        "Our connection is built on mutual respect, not pressure or assumptions."
    ))
    assert response_quality_issue(request, response) == "generic_interaction_sermon"
