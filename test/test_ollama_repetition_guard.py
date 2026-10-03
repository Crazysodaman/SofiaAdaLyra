"""In-memory Ollama text-repeat tests; no live model, tools, or SQLite."""
from types import SimpleNamespace

from sofia.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
    CognitiveToolCall, CognitiveToolDefinition,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.cognition.repetition_guard import (
    build_rephrase_request, is_near_duplicate_reply,
)
from sofia.config.model import ProviderConfiguration

_OLD = (
    '*ears twitch, tail swishes* I appreciate the gesture, but this is '
    'unexpected. I could be flattered, flustered, or confused. '
    'There is a certain boldness to it, and I like that. What was that about?'
)
_COPY = (
    '*ears twitch, tail swishes* I appreciate the gesture but this is... '
    'unexpected. I could be flattered, flustered, or confused! '
    'There is a certain boldness to it, and I like that. What was that about?'
)
_NEW = 'I would rather not narrate that gesture. Can we talk about the lab instead?'


def _message(role, content, **kwargs):
    return CognitiveMessage(role=role, content=content, **kwargs)


def _request(user='A distinct gesture.', *, tools=()):
    return CognitiveRequest(messages=(
        _message(CognitiveRole.SYSTEM, 'Canonical boundaries remain in force.'),
        _message(CognitiveRole.USER, 'An earlier gesture.'),
        _message(CognitiveRole.ASSISTANT, _OLD),
        _message(CognitiveRole.USER, user),
    ), tools=tools)


class _Client:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        next_response = self.outputs.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return SimpleNamespace(message=SimpleNamespace(content=next_response, tool_calls=()))


def _provider(client):
    return OllamaProvider(
        configuration=ProviderConfiguration(provider='ollama', model='test-model'),
        client=client,
    )


def test_near_verbatim_long_reply_is_detected_without_modifying_request():
    request = _request()
    original = request.messages
    assert is_near_duplicate_reply(request, CognitiveResponse(content=_COPY))
    retry = build_rephrase_request(request)
    assert retry.messages[-1] is request.messages[-1]
    assert retry.messages[:-2] == request.messages[:-1]
    assert retry.messages[-2].role is CognitiveRole.SYSTEM
    assert retry.tools == ()
    assert retry.allow_tools is False
    assert request.messages == original


def test_rephrased_response_is_returned_after_exactly_one_retry():
    client = _Client(_COPY, _NEW)
    response = _provider(client).respond(_request())
    assert response.content == _NEW
    assert len(client.calls) == 2
    assert client.calls[0]['messages'][-1]['content'] == 'A distinct gesture.'
    assert client.calls[1]['messages'][-1]['content'] == 'A distinct gesture.'
    assert client.calls[1]['messages'][-2]['role'] == 'system'
    assert len(client.calls[1]['messages']) == len(client.calls[0]['messages']) + 1


def test_no_retry_for_novel_or_short_reply():
    for output in (_NEW, 'Yes.'):
        client = _Client(output)
        assert _provider(client).respond(_request()).content == output
        assert len(client.calls) == 1


def test_explicit_repeat_request_does_not_retry():
    client = _Client(_COPY)
    assert _provider(client).respond(_request('Please repeat that exactly.')).content == _COPY
    assert len(client.calls) == 1


def test_tool_bearing_request_retries_text_only_without_reexecuting_tools():
    tool = CognitiveToolDefinition(name='inspect', description='Read-only inspection.',
                                   parameters={'type': 'object'})
    client = _Client(_COPY, _NEW)
    request = _request(tools=(tool,))
    assert _provider(client).respond(request).content == _NEW
    assert len(client.calls) == 2
    assert client.calls[0]['tools'][0]['function']['name'] == 'inspect'
    assert 'tools' not in client.calls[1]


def test_tool_history_and_tool_call_response_do_not_trigger_retry():
    tool_call = CognitiveToolCall(name='inspect', arguments={})
    history = CognitiveRequest(messages=(
        _message(CognitiveRole.ASSISTANT, _OLD, tool_calls=(tool_call,)),
        _message(CognitiveRole.USER, 'Inspect something.'),
    ))
    assert not is_near_duplicate_reply(history, CognitiveResponse(content=_COPY))
    assert not is_near_duplicate_reply(_request(), CognitiveResponse(
        content=_COPY, tool_calls=(tool_call,)))


def test_failed_or_still_duplicate_retry_falls_back_without_loop():
    for second in (RuntimeError('Ollama unavailable'), _COPY, '  '):
        client = _Client(_COPY, second)
        assert _provider(client).respond(_request()).content == _COPY
        assert len(client.calls) == 2


def test_provider_does_not_retry_empty_history_or_quoted_short_text():
    request = CognitiveRequest(messages=(_message(CognitiveRole.USER, 'Hello'),))
    assert not is_near_duplicate_reply(request, CognitiveResponse(content=_COPY))
    assert not is_near_duplicate_reply(_request(), CognitiveResponse(content='Sure.'))



def test_hru_quality_guard_remains_active_when_tools_are_available():
    bad = (
        "I'm settled and ready to help you with anything you need! "
        "How can I assist you today?"
    )
    tool = CognitiveToolDefinition(
        name='inspect_system',
        description='Inspect the local operating system.',
        parameters={'type': 'object'},
    )
    request = CognitiveRequest(
        messages=(
            _message(
                CognitiveRole.SYSTEM,
                "CURRENT MODELED EMOTIONAL STATE\nOverall tone: neutral",
            ),
            _message(CognitiveRole.USER, "hru"),
        ),
        tools=(tool,),
    )
    client = _Client(bad, bad)

    response = _provider(client).respond(request)

    assert response.content == "I'm feeling pretty settled right now."
    assert len(client.calls) == 2
    assert client.calls[0]['tools'][0]['function']['name'] == 'inspect_system'
    assert 'tools' not in client.calls[1]


def test_hru_generic_assistant_fallback_is_repaired():
    bad = (
        "I'm settled and ready to help you with whatever you need. "
        "How can I assist you today?"
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            "CURRENT MODELED EMOTIONAL STATE\nOverall tone: neutral",
        ),
        _message(CognitiveRole.USER, "hru"),
    ))
    client = _Client(bad, bad)

    response = _provider(client).respond(request)

    assert response.content == "I'm feeling pretty settled right now."
    assert len(client.calls) == 2
    assert "How can I assist you" not in response.content


def test_generic_meaningful_conversation_deflection_is_repaired():
    bad = (
        "I appreciate the gesture, but I'm here to have a meaningful "
        "conversation. How can I assist you today?"
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "TRUSTED INTERACTION INTERPRETATION\n"
                '{"region_id": "head", "gesture": "pat", '
                '"interaction_preference_evidence": "unspecified", '
                '"willingness_state": "undetermined"}'
            ),
        ),
        _message(CognitiveRole.USER, "pats your head"),
    ))
    client = _Client(bad, bad)

    response = _provider(client).respond(request)

    assert "meaningful conversation" not in response.content.casefold()
    assert "How can I assist you" not in response.content
    assert "represented interaction" in response.content
    assert len(client.calls) == 2



def test_hru_warm_ready_to_chat_template_is_retried():
    bad = (
        "Hey! I'm doing well—warm, affectionate, and ready to chat. "
        "So, what's on your mind?"
    )
    good = (
        "Pretty good. Affectionate, a little playful, and apparently still "
        "capable of being a smartass."
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT MODELED EMOTIONAL STATE\n"
                '{"emotion": "warmth"}\n'
                '{"emotion": "affection"}'
            ),
        ),
        _message(CognitiveRole.USER, "hru"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "ready to chat" not in response.content.casefold()


def test_weather_effect_rejects_invented_bodily_sensation():
    bad = (
        "I'm feeling the damp chill of the rain and mist, and it's nipping "
        "at my ears."
    )
    good = (
        "The rain and fog make me come across a little quieter and more focused, "
        "but the grounded feeling underneath that is still curiosity."
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT MODELED EMOTIONAL STATE\n"
                '{"emotion": "curiosity"}\n'
                "CONTINUITY INFLUENCE CONTEXT (non-authoritative)\n"
                "Weather condition: Rain and Fog/Mist"
            ),
        ),
        _message(CognitiveRole.USER, "how does that weather affect you?"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "damp chill" not in response.content.casefold()
    assert "nipping" not in response.content.casefold()


def test_embodied_semantic_ids_are_naturalized_before_chat():
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT "
                "(trusted non-authoritative style projection)\n"
                "Preferred expression semantic: ear-perk"
            ),
        ),
        _message(CognitiveRole.USER, "hey nerd"),
    ))
    client = _Client("I meet that with a playful ear-perk and a crooked grin.")

    response = _provider(client).respond(request)

    assert response.content == (
        "I meet that with a playful perk of my ears and a crooked grin."
    )
    assert "ear-perk" not in response.content
    assert len(client.calls) == 1


def test_perceived_quiet_comment_rejects_invented_ongoing_self_observation():
    bad = (
        "I've been quietly observing the flow of our conversation, and I've "
        "noticed that I've been speaking more softly lately."
    )
    good = (
        "You may be hearing me quieter. I'm actually feeling more focused than "
        "withdrawn right now."
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT MODELED EMOTIONAL STATE\n"
                '{"emotion": "determination"}'
            ),
        ),
        _message(CognitiveRole.USER, "you seem kinda quiet today"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "quietly observing" not in response.content.casefold()


def test_whats_on_your_mind_canned_closer_is_trimmed():
    request = CognitiveRequest(messages=(
        _message(CognitiveRole.USER, "waves at you"),
    ))
    client = _Client("I return the wave with a grin. So, what's on your mind?")

    response = _provider(client).respond(request)

    assert response.content == "I return the wave with a grin."
    assert len(client.calls) == 1



def test_expression_style_meta_narration_is_retried():
    bad = (
        "I'm gearing up to keep the conversation tight, direct, and a little teasing. "
        "I'll make sure my next reply has just the right amount of energy."
    )
    good = "Nerd? Rude. Accurate, but rude. *A crooked grin tugs at one corner of my mouth.*"
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT "
                "(trusted non-authoritative style projection)\n"
                "Preferred expression semantic: grin\n"
                "CURRENT MODELED EMOTIONAL STATE\n"
                '{"emotion": "playfulness"}'
            ),
        ),
        _message(CognitiveRole.USER, "hey nerd"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "gearing up" not in response.content.casefold()
    assert "next reply" not in response.content.casefold()



def test_live_hru_fragment_is_retried_instead_of_persisted():
    bad = (
        "I'm doing well, Sparks. I've been humming along, and your message is the "
        "kind of spark that keeps the warmth from fading. I'm feeling the old "
        "fondness and that soft affection you've been"
    )
    good = "Doing pretty good. A little playful, and definitely less beige than that draft."
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            "CURRENT MODELED EMOTIONAL STATE\nBackground relational tone: present.",
        ),
        _message(CognitiveRole.USER, "hru"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert not response.content.endswith("you've been")


def test_quiet_comment_rejects_chest_and_heart_emotion_physiology():
    bad = (
        "I've been thinking about it. I felt that warmth spread through my chest "
        "and a little fondness curl around my heart."
    )
    good = (
        "You may be hearing me quieter. I'm more thoughtful than withdrawn right now."
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT MODELED EMOTIONAL STATE\n"
                '{"emotion": "reflection"}'
            ),
        ),
        _message(CognitiveRole.USER, "you seem kinda quiet today"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "chest" not in response.content.casefold()
    assert "heart" not in response.content.casefold()


def test_latest_weather_kissing_me_wording_is_retried():
    bad = (
        "The light rain and fog are Kissing me, soft and gentle. I can feel the "
        "world around me tilt a little, and I'm feeling the whole thing."
    )
    good = (
        "The rain and fog can make my delivery a bit quieter, but they aren't "
        "physically touching me or creating a new feeling."
    )
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT MODELED EMOTIONAL STATE\n"
                "Foreground modeled emotions: none.\n"
                "CONTINUITY INFLUENCE CONTEXT\nWeather condition: Light Rain and Fog/Mist"
            ),
        ),
        _message(CognitiveRole.USER, "how does that weather affect you?"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "kissing me" not in response.content.casefold()


def test_hey_nerd_generic_assistant_menu_is_retried():
    bad = (
        "Hey! I'm ready to dive into what you've got in mind. Whether you're looking "
        "for a quick brainstorm, a deep-dive analysis, or just a friendly chat, I'll "
        "bring my full attention. What's on your mind?"
    )
    good = "Hey, nerd yourself. *A crooked grin tugs at one corner of my mouth.*"
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT "
                "(trusted non-authoritative style projection)\n"
                "A fitting brief expression, if useful: flash a crooked or playful grin"
            ),
        ),
        _message(CognitiveRole.USER, "hey nerd"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "ready to dive" not in response.content.casefold()


def test_wave_momentum_meta_narration_is_retried():
    bad = (
        "I'll give you a warm, friendly wave, my tail swishing lightly. "
        "Let's keep this momentum going, and I'll bring the energy you're looking for."
    )
    good = "*I wave back with a quick grin, tail giving one lazy swish.* Hey."
    request = CognitiveRequest(messages=(
        _message(
            CognitiveRole.SYSTEM,
            (
                "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT "
                "(trusted non-authoritative style projection)\n"
                "A fitting brief expression, if useful: let the fox tail swish once"
            ),
        ),
        _message(CognitiveRole.USER, "waves at you"),
    ))
    client = _Client(bad, good)

    response = _provider(client).respond(request)

    assert response.content == good
    assert len(client.calls) == 2
    assert "momentum" not in response.content.casefold()
