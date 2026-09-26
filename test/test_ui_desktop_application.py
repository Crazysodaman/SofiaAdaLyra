from pathlib import Path

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.ui.desktop_controller import DesktopWorkbenchController


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


def _configuration(tmp_path: Path) -> SofiaConfiguration:
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
            model="desktop-test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def test_desktop_controller_uses_real_application_text_ui(
    tmp_path: Path,
):
    application = SofiaApplication(
        _configuration(tmp_path)
    )
    controller = DesktopWorkbenchController(
        application
    )

    controller.start()
    response = controller.send(
        "Hello from the Windows workbench."
    )

    assert response.content == "Test cognitive response."
    history = controller.history()
    assert history[-2].actor == "user"
    assert (
        history[-2].content
        == "Hello from the Windows workbench."
    )
    assert history[-1].actor == "sofia"

    controller.shutdown()


def test_desktop_controller_recovers_draft_after_application_restart(
    tmp_path: Path,
):
    configuration = _configuration(tmp_path)

    first = DesktopWorkbenchController(
        SofiaApplication(configuration)
    )
    first.start()
    session_id = first.session_id
    first.save_draft("recover after restart")
    first.shutdown(
        current_draft="recover after restart"
    )

    second = DesktopWorkbenchController(
        SofiaApplication(configuration)
    )
    second.start(session_id=session_id)

    assert second.draft_text() == "recover after restart"

    second.shutdown()
