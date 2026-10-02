from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)


PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "data" / "avatar.json"
)


@pytest.fixture
def configuration(tmp_path: Path) -> SofiaConfiguration:
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(
        (
            '{"name": "Sofía", '
            '"traits": ["rigorous", "curious", "direct"], '
            '"communication_style": "Clear and direct."}'
        ),
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="ui-test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def test_application_text_ui_uses_canonical_conversation(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(configuration)
    application.start()

    application.text_ui.save_draft("Hello from UI")
    response = application.text_ui.send()

    assert response.content == "Test cognitive response."
    assert application.text_ui.draft() is None

    history = application.text_ui.history()
    assert [message.actor for message in history] == [
        "user",
        "sofia",
    ]
    assert history[0].content == "Hello from UI"
    assert (
        history[0].session_id
        == application.conversation.session_id
    )
    trace = application.conversation.latest_matrix_trace()
    assert trace is not None
    assert trace.envelope.channel == "desktop"

    application.shutdown()


def test_application_text_ui_draft_survives_restart(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(configuration)
    application.start()
    session_id = application.conversation.session_id
    assert session_id is not None

    application.text_ui.save_draft(
        "unfinished after restart"
    )
    application.shutdown()

    resumed = SofiaApplication(configuration)
    resumed.start(session_id=session_id)

    draft = resumed.text_ui.draft()
    assert draft is not None
    assert draft.content == "unfinished after restart"

    resumed.shutdown()


def test_same_application_can_reopen_text_ui_after_shutdown(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(configuration)
    application.start()
    session_id = application.conversation.session_id
    assert session_id is not None

    application.text_ui.save_draft("restart same object")
    application.shutdown()

    application.start(session_id=session_id)

    assert application.text_ui.draft() is not None
    assert (
        application.text_ui.draft().content
        == "restart same object"
    )

    application.shutdown()


def test_text_ui_clothing_action_commits_canonical_avatar_state(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(configuration)
    application.start()

    application.text_ui.save_draft("change into bikini 4")
    response = application.text_ui.send()

    assert "Midnight Asymmetric Bikini" in response.content
    current = application.runtime.avatar_presentation.current
    assert current.outfit_id == "swim.bikini.04"
    assert application._presentation_bundle is not None
    matrix = application._presentation_bundle.current_matrix()
    assert (
        matrix.as_dict()["torso"]["base"]["garment_id"]
        == "closet.swim.bikini.04.top"
    )

    session_id = application.conversation.session_id
    application.shutdown()

    resumed = SofiaApplication(configuration)
    resumed.start(session_id=session_id)
    assert resumed.runtime.avatar_presentation.current.outfit_id == "swim.bikini.04"
    resumed.shutdown()


def test_text_ui_clothing_hypothetical_then_do_it_uses_prior_user_request(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(configuration)
    application.start()
    original = application.runtime.avatar_presentation.current

    application.text_ui.save_draft(
        "if i asked you to change into bikini 2 will you"
    )
    hypothetical = application.text_ui.send()

    assert "request itself" in hypothetical.content
    assert application.runtime.avatar_presentation.current == original

    application.text_ui.save_draft("do it")
    followup = application.text_ui.send()

    assert "Violet Halter Bikini" in followup.content
    assert application.runtime.avatar_presentation.current.outfit_id == (
        "swim.bikini.02"
    )
    application.shutdown()


def test_text_ui_undress_followup_never_claims_uncommitted_private_change(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(configuration)
    application.start()
    original = application.runtime.avatar_presentation.current

    application.text_ui.save_draft(
        "if i asked you to undress will you"
    )
    hypothetical = application.text_ui.send()
    assert "private presentation" in hypothetical.content
    assert application.runtime.avatar_presentation.current == original

    application.text_ui.save_draft("do it")
    followup = application.text_ui.send()

    assert "keeping my current outfit" in followup.content
    assert application.runtime.avatar_presentation.current == original
    application.shutdown()
