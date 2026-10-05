"""Bounded post-conversation self-appraisal contracts."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.conversation.model import ConversationRole
from sofia.emotion.appraisal import ConversationEmotionAppraiser
from sofia.emotion.catalog import EMOTIONS
from sofia.emotion.journal import EmotionalJournal
from sofia.emotion.model import CurrentEmotionalState
from sofia.social.principals import SPARKS_PRINCIPAL_ID


NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
EMPTY_STATE = CurrentEmotionalState(
    as_of=NOW,
    subject=SPARKS_PRINCIPAL_ID,
    tone="settled",
    active=(),
)


def _appraiser(payload, requests=None):
    def generate(request):
        if requests is not None:
            requests.append(request)
        return CognitiveResponse(content=json.dumps(payload))

    return ConversationEmotionAppraiser(generate)


@pytest.mark.parametrize("emotion", sorted(EMOTIONS))
def test_every_canonical_emotion_can_be_appraised(emotion):
    appraisal = _appraiser({
        "record": True,
        "emotions": [emotion],
        "reason": "The saved exchange supports this settled appraisal.",
        "confidence": 0.8,
    }).appraise(
        user_content="A meaningful exchange.",
        assistant_content="A settled response.",
        current_state=EMPTY_STATE,
    )

    assert appraisal is not None
    assert appraisal.emotions == (emotion,)


def test_independent_emotions_can_form_one_bounded_mixture():
    emotions = [
        "sexual-attraction",
        "sexual-desire",
        "sexual-arousal",
        "affection",
        "bashfulness",
        "uncertainty",
    ]
    appraisal = _appraiser({
        "record": True,
        "emotions": emotions,
        "reason": "Several compatible and conflicting appraisals coexist.",
        "confidence": 0.76,
    }).appraise(
        user_content="A relationship conversation.",
        assistant_content="A nuanced and bounded response.",
        current_state=EMPTY_STATE,
    )

    assert appraisal is not None
    assert appraisal.emotions == tuple(emotions)


def test_appraiser_can_abstain_and_has_no_tools_or_action_authority():
    requests = []
    assert _appraiser({
        "record": False,
        "emotions": [],
        "reason": "Routine exchange.",
        "confidence": 0.9,
    }, requests).appraise(
        user_content="What time is it?",
        assistant_content="It is noon.",
        current_state=EMPTY_STATE,
    ) is None

    request = requests[0]
    assert request.allow_tools is False
    assert request.tools == ()
    assert request.capability_allowlist == ()
    prompt = request.messages[0].content.lower()
    assert "no one implies another" in prompt
    assert "never proof of physical sensation" in prompt
    assert "contradictory emotions may coexist" in prompt


def test_one_call_response_envelope_is_stripped_and_validated():
    visible, appraisal = ConversationEmotionAppraiser.extract_response(
        "A natural visible reply.\n"
        "<sofia-emotion-appraisal>"
        '{"record":true,"emotions":["sexual-desire","tenderness"],'
        '"reason":"The reply supports a mixed appraisal.","confidence":0.8}'
        "</sofia-emotion-appraisal>"
    )

    assert visible == "A natural visible reply."
    assert appraisal is not None
    assert appraisal.emotions == ("sexual-desire", "tenderness")


def test_malformed_appraisal_markup_can_be_removed_before_display():
    content = (
        "Visible reply.\n<sofia-emotion-appraisal>{bad json}"
        "</sofia-emotion-appraisal>"
    )
    with pytest.raises(ValueError):
        ConversationEmotionAppraiser.extract_response(content)
    assert (
        ConversationEmotionAppraiser.strip_untrusted_envelope(content)
        == "Visible reply."
    )


@pytest.mark.parametrize(
    "payload",
    (
        {
            "record": True,
            "emotions": ["not-an-emotion"],
            "reason": "Invalid label.",
            "confidence": 0.9,
        },
        {
            "record": True,
            "emotions": ["joy", "joy"],
            "reason": "Duplicate label.",
            "confidence": 0.9,
        },
        {
            "record": True,
            "emotions": ["joy"],
            "reason": "Confidence is too low.",
            "confidence": 0.2,
        },
        {
            "record": False,
            "emotions": ["joy"],
            "reason": "An abstention cannot smuggle an emotion.",
            "confidence": 0.9,
        },
    ),
)
def test_invalid_or_ungrounded_appraisal_is_rejected(payload):
    with pytest.raises(ValueError):
        _appraiser(payload).appraise(
            user_content="Saved user turn.",
            assistant_content="Saved assistant turn.",
            current_state=EMPTY_STATE,
        )


def test_saved_exchange_appraisal_is_persisted_in_relationship_scope(tmp_path):
    user = SimpleNamespace(
        id="user-1",
        role=ConversationRole.USER,
        content="A meaningful relationship exchange.",
        created_at=NOW,
    )
    assistant = SimpleNamespace(
        id="assistant-1",
        role=ConversationRole.ASSISTANT,
        content="I feel both drawn in and a little uncertain.",
        created_at=NOW,
    )

    class Runtime:
        personality = object()
        core_state = SimpleNamespace(
            relationships=(SimpleNamespace(subject="Sparks"),),
        )

    service = object.__new__(EmotionalConversationService)
    service._runtime = Runtime()
    service._session = None
    service._social_store = None
    service._emotional_journal = EmotionalJournal(tmp_path / "state.db")
    service._last_emotion_appraisal_error = None
    finalized = service._finalize_response(
        CognitiveRequest(messages=()),
        CognitiveResponse(content=(
            "Visible.\n<sofia-emotion-appraisal>"
            '{"record":true,"emotions":["sexual-attraction",'
            '"affectionate-uncertainty"],"reason":"The settled response '
            'supports a mixed appraisal.","confidence":0.8}'
            "</sofia-emotion-appraisal>"
        )),
        principal=None,
    )
    assert finalized.content == "Visible."
    service.messages = lambda: (user, assistant)

    service._persist_pending_emotion_appraisal()

    events = service.emotional_journal.recent(
        now=NOW,
        subject=SPARKS_PRINCIPAL_ID,
        scope=service.relationship_scope,
    )
    assert len(events) == 1
    assert events[0].event_id == "conversation-appraisal:assistant-1"
    assert events[0].current_emotions == (
        "sexual-attraction",
        "affectionate-uncertainty",
    )
    assert service.last_emotion_appraisal_error is None
