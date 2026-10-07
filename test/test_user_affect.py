"""User-affect adaptation remains tentative, bounded, and session-local."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from sofia.application.emotional_conversation import EmotionalConversationService
from sofia.application.conversation_service import ConversationService
from sofia.cognition.matrix import (
    ResponseValidation,
    ResponseValidationDisposition,
)
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.conversation.model import ConversationRole
from sofia.social.affect import (
    USER_AFFECTS,
    UserAffectAppraiser,
    UserAffectAssessment,
    UserAffectObservation,
    UserAffectTracker,
)
from sofia.social.principals import SPARKS_PRINCIPAL_ID


NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _envelope(*, affects, source="inferred", confidence=0.8):
    import json

    return (
        "A visible, affect-aware response.\n"
        "<sofia-user-affect>"
        + json.dumps({
            "record": True,
            "affects": affects,
            "source": source,
            "valence": -0.5,
            "activation": 0.7,
            "intensity": 0.75,
            "confidence": confidence,
            "basis": "The wording directly supports this tentative reading.",
            "clarify": False,
        })
        + "</sofia-user-affect>"
    )


@pytest.mark.parametrize("affect", sorted(USER_AFFECTS))
def test_every_canonical_nonsensitive_affect_can_be_validated(affect):
    if affect in {"aroused", "attracted", "desiring"}:
        pytest.skip("sensitive labels require explicit evidence")
    visible, assessment = UserAffectAppraiser.extract_response(
        _envelope(affects=[affect]),
        user_content="This has been a difficult and emotional day.",
    )
    assert visible == "A visible, affect-aware response."
    assert assessment is not None
    assert assessment.affects == (affect,)


def test_sensitive_affect_requires_explicit_first_person_report():
    with pytest.raises(ValueError, match="cannot be inferred"):
        UserAffectAppraiser.extract_response(
            _envelope(affects=["aroused"], source="inferred"),
            user_content="Say something sexy.",
        )

    visible, assessment = UserAffectAppraiser.extract_response(
        _envelope(affects=["aroused", "desiring"], source="self_reported"),
        user_content="I'm aroused and I desire you.",
    )
    assert visible == "A visible, affect-aware response."
    assert assessment is not None
    assert assessment.affects == ("aroused", "desiring")


def test_negated_sensitive_affect_is_not_recorded_as_positive_evidence():
    with pytest.raises(ValueError, match="explicit first-person evidence"):
        UserAffectAppraiser.extract_response(
            _envelope(affects=["aroused"], source="corrected"),
            user_content="I'm not aroused; I am only being playful.",
        )


def test_malformed_or_attributed_affect_envelope_never_reaches_user():
    content = (
        "Visible response.\n"
        '<sofia-user-affect source="model">untrusted payload'
    )
    assert (
        UserAffectAppraiser.strip_untrusted_envelope(content)
        == "Visible response."
    )
    assert UserAffectAppraiser.strip_untrusted_envelope(
        "Visible response.\n<SOFIA-USER-AFFECT>payload"
    ) == "Visible response."


def test_tracker_expires_and_has_no_durable_backing():
    assessment = UserAffectAssessment(
        affects=("frustrated",), source="inferred", valence=-0.6,
        activation=0.7, intensity=0.8, confidence=0.75,
        basis="Repeated failure language supports frustration.", clarify=False,
    )
    observation = UserAffectObservation(
        subject=SPARKS_PRINCIPAL_ID,
        evidence_ref="message-1",
        observed_at=NOW,
        assessment=assessment,
    )
    tracker = UserAffectTracker()
    tracker.record(observation)
    assert tracker.current(SPARKS_PRINCIPAL_ID, now=NOW) is observation
    assert tracker.current(
        SPARKS_PRINCIPAL_ID, now=NOW + timedelta(minutes=31)
    ) is None
    assert UserAffectTracker().current(SPARKS_PRINCIPAL_ID, now=NOW) is None


def test_combined_user_and_sofia_envelopes_are_hidden_and_retained_separately():
    user = SimpleNamespace(
        id="user-1", role=ConversationRole.USER,
        content="I'm frustrated by this failure.", created_at=NOW,
    )
    assistant = SimpleNamespace(
        id="assistant-1", role=ConversationRole.ASSISTANT,
        content="That failure is obnoxious. Let's isolate it.", created_at=NOW,
    )
    service = object.__new__(EmotionalConversationService)
    service._runtime = SimpleNamespace(
        personality=object(),
        core_state=SimpleNamespace(
            relationships=(SimpleNamespace(subject="Sparks"),),
        ),
    )
    service._session = None
    service._social_store = None
    service._user_affect_tracker = UserAffectTracker()
    service.messages = lambda: (user,)
    response = CognitiveResponse(content=(
        _envelope(affects=["frustrated"])
        + "\n<sofia-emotion-appraisal>"
        '{"record":true,"emotions":["concern","determination"],'
        '"reason":"The response settles on helping with the failure.",'
        '"confidence":0.8}'
        "</sofia-emotion-appraisal>"
    ))

    finalized = service._finalize_response(
        CognitiveRequest(messages=()), response, principal=None,
    )
    assert finalized.content == "A visible, affect-aware response."
    assert service._pending_emotion_appraisal.emotions == (
        "concern", "determination",
    )
    assert service._pending_user_affect.affects == ("frustrated",)

    service.messages = lambda: (user, assistant)
    service._persist_pending_user_affect()
    current = service.current_user_affect(now=NOW)
    assert current is not None
    assert current.evidence_ref == "user-1"
    assert current.assessment.affects == ("frustrated",)


def test_instruction_requires_adaptation_uncertainty_and_non_manipulation():
    prompt = UserAffectAppraiser.response_instruction().lower()
    assert "adapt the visible reply" in prompt
    assert "ask one natural clarifying question" in prompt
    assert "never state an inferred emotion as fact" in prompt
    assert "infer consent" in prompt
    assert "manipulate" in prompt
    assert "only when the user explicitly self-reports" in prompt


def test_malformed_sofia_envelope_cannot_leak_valid_user_affect_markup():
    user = SimpleNamespace(
        id="user-malformed", role=ConversationRole.USER,
        content="I'm frustrated.", created_at=NOW,
    )
    service = object.__new__(EmotionalConversationService)
    service._session = None
    service.messages = lambda: (user,)
    service._last_emotion_appraisal_error = None
    response = CognitiveResponse(content=(
        _envelope(affects=["frustrated"])
        + "\n<sofia-emotion-appraisal>{bad json}"
        "</sofia-emotion-appraisal>"
    ))

    finalized = service._finalize_response(
        CognitiveRequest(messages=()), response, principal=None,
    )

    assert finalized.content == "A visible, affect-aware response."
    assert "<sofia-" not in finalized.content
    assert service._pending_user_affect.affects == ("frustrated",)
    assert service.last_emotion_appraisal_error == "ValueError"


def test_matrix_fallback_discards_appraisals_from_rejected_draft(monkeypatch):
    fallback = CognitiveResponse(content="A safe evidence-bounded fallback.")

    def reject(self, request, response, *, principal):
        self._current_response_validation = ResponseValidation(
            ResponseValidationDisposition.FALLBACK,
            ("unsupported_claim",),
        )
        return fallback

    monkeypatch.setattr(ConversationService, "_matrix_finalize_response", reject)
    service = object.__new__(EmotionalConversationService)
    service._pending_emotion_appraisal = object()
    service._pending_user_affect = object()

    settled = service._matrix_finalize_response(
        CognitiveRequest(messages=()),
        CognitiveResponse(content="Rejected draft."),
        principal=None,
    )

    assert settled is fallback
    assert service._pending_emotion_appraisal is None
    assert service._pending_user_affect is None
