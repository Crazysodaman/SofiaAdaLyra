"""Owner-observed Run 3 exchanges replayed through the production service."""
from sofia.core.cognition.model import CognitiveResponse, CognitiveRole

from test.test_conversation_service import create_application


def test_natural_outfit_paraphrase_uses_same_canonical_presentation(tmp_path):
    application = create_application(tmp_path)
    application.start()
    try:
        natural = application.conversation.respond("So what do you have on rn")
        explicit = application.conversation.respond("what are you wearing")

        for answer in (natural, explicit):
            assert "day engineer outfit" in answer.content
            assert "Fitted technical long-sleeve top" in answer.content
            assert "Low-profile utility belt" in answer.content
        assert any(ref.startswith("evidence:") for ref in natural.evidence_refs)
        assert any(ref.startswith("evidence:") for ref in explicit.evidence_refs)
    finally:
        application.shutdown()


def test_weather_why_positional_recall_uses_current_session(tmp_path):
    application = create_application(tmp_path)
    application.start()
    service = application.conversation
    try:
        service.respond("check weather?")
        service.respond("why")
        answer = service.respond("what was I asking before the why?")

        assert answer.content == (
            'Before the “why,” you asked: “check weather?”'
        )
        assert len(answer.evidence_refs) == 1
        assert answer.evidence_refs[0].startswith("conversation-retrieval:")
        assert "offline" not in answer.content.casefold()
    finally:
        application.shutdown()


def test_disagreement_followups_keep_the_specific_exchange(
    tmp_path, monkeypatch,
):
    application = create_application(tmp_path)
    application.start()
    captured = []

    def respond(request, **_kwargs):
        captured.append(request)
        return CognitiveResponse(content="I will follow the evidence.")

    monkeypatch.setattr(application.runtime, "respond", respond)
    try:
        application.conversation.respond("so your saying Im wrong")
        application.conversation.respond("why are you backing down so fast?")

        assert len(captured) == 2
        for request in captured:
            assert any(
                message.role is CognitiveRole.SYSTEM
                and "TRUSTED DISAGREEMENT CONTINUITY" in message.content
                for message in request.messages
            )
        assert any(
            message.role is CognitiveRole.USER
            and message.content == "so your saying Im wrong"
            for message in captured[1].messages
        )
        assert any(
            message.role is CognitiveRole.ASSISTANT
            and message.content == "I will follow the evidence."
            for message in captured[1].messages
        )
    finally:
        application.shutdown()
