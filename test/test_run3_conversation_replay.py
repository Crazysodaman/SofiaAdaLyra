"""Owner-observed Run 3 exchanges replayed through the production service."""
from pathlib import Path

from sofia.core.cognition.model import CognitiveResponse, CognitiveRole
from sofia.platform.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

from test.test_conversation_service import create_application


def stable_avatar_presentation(tmp_path: Path) -> None:
    """Seed supported production settings for a deterministic presentation.

    Live daypart routines choose the current outfit from the trusted local
    hour (presentation_routine.py switches to the late-lounge preset at or
    after 21:00), so a full-suite run crossing that hour honestly answers
    with the lounge outfit. These owner replays assert the canonical default
    presentation, so the supported user configuration with routines off (and
    the foundation-default day outfit) must be in place before boot.
    """
    state_path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(state_path)
    RuntimeUserSettingsStore(state_path).save(
        RuntimeUserSettings(avatar_routines_enabled=False),
    )


def test_natural_outfit_paraphrase_uses_same_canonical_presentation(tmp_path):
    stable_avatar_presentation(tmp_path)
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
    stable_avatar_presentation(tmp_path)
    application = create_application(tmp_path)
    application.start()
    service = application.conversation
    try:
        service.respond("what are you wearing")
        fit = service.respond("does it fit the weather? explain?")
        assert "day engineer outfit" in fit.content
        assert "cannot determine whether it fits" in fit.content
        assert "explicit weather refresh" in fit.content
        assert len(fit.evidence_refs) == 2

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
