from pathlib import Path

import pytest

import sofia.application.bootstrap as bootstrap
from sofia.application import SofiaApplication, SofiaApplicationError
from sofia.application.act_service import SofiaActService
from sofia.interaction.opt_in_service import OptInInteractionConversationService
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.config.user_settings import RuntimeUserSettings
from sofia.runtime.model import RuntimeState
from sofia.social.principals import (
    discord_sparks_principal,
    local_sparks_principal,
)
from sofia.social.store import SocialSessionStore


PROJECT_ROOT = Path(__file__).parent.parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)


@pytest.fixture
def personality_path(tmp_path: Path) -> Path:
    path = tmp_path / "personality.json"

    path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "curious",
        "direct"
    ],
    "communication_style": "Clear, direct, and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return path


def create_configuration(
    personality_path: Path,
    state_path: Path,
) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        avatar_path=str(AVATAR_PATH),
        state_path=str(state_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def test_new_application_is_not_started(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    assert application.runtime.state is RuntimeState.CREATED




def test_production_application_composes_live_interact_memory_act_environment_and_avatar(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    assert isinstance(
        application.conversation,
        OptInInteractionConversationService,
    )
    assert application.runtime.memory_system.uses_reviewed_memory is True
    assert isinstance(application.act, SofiaActService)
    assert application.runtime.environment_service is not None
    assert application.wardrobe_studio is None

    application.start()
    try:
        assert application.wardrobe_studio is not None
        assert application.runtime.avatar_presentation is not None
        assert hasattr(application.conversation, "current_emotional_state")
    finally:
        application.shutdown()

def test_start_starts_runtime(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()

    assert application.runtime.state is RuntimeState.READY


def test_shutdown_stops_runtime(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()
    application.shutdown()

    assert application.runtime.state is RuntimeState.STOPPED


def test_start_twice_is_rejected(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.state is RuntimeState.READY


def test_shutdown_before_start_is_rejected(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    with pytest.raises(SofiaApplicationError):
        application.shutdown()

    assert application.runtime.state is RuntimeState.CREATED


def test_start_failure_is_exposed_as_application_error(
    tmp_path: Path,
):
    configuration = SofiaConfiguration(
        constitution_path=str(tmp_path / "missing.md"),
        constitution_hash_path=str(tmp_path / "missing.sha256"),
        identity_path=str(tmp_path / "missing.json"),
        personality_path=str(tmp_path / "missing-personality.json"),
        avatar_path=str(tmp_path / "missing-avatar.json"),
        state_path=str(tmp_path / "sofia.db"),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=tmp_path,
    )

    application = SofiaApplication(configuration)

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.state is RuntimeState.FAILED

def test_start_refreshes_environment_before_live_context(
    personality_path: Path,
    tmp_path: Path,
    monkeypatch,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )
    service = application.runtime.environment_service
    original_snapshot = service.snapshot
    refresh_flags: list[bool] = []

    def recording_snapshot(*, now=None, refresh_providers=True):
        refresh_flags.append(refresh_providers)
        return original_snapshot(
            now=now,
            refresh_providers=refresh_providers,
        )

    monkeypatch.setattr(
        service,
        "snapshot",
        recording_snapshot,
    )

    application.start()

    assert refresh_flags[:2] == [True, True]

    application.shutdown()


def test_channel_conversations_share_runtime_but_keep_audience_sessions_isolated(
    personality_path: Path,
    tmp_path: Path,
):
    configuration = create_configuration(
        personality_path,
        tmp_path / "sofia.db",
    )
    application = SofiaApplication(configuration)
    application.start()

    desktop_session = application.conversation.session_id
    assert desktop_session is not None

    discord_conversation = application.open_channel_conversation()
    discord_session = discord_conversation.session_id
    assert discord_session is not None
    assert discord_session != desktop_session

    application.conversation.respond(
        "Hello from the desktop.",
        principal=local_sparks_principal(),
    )
    discord_conversation.respond(
        "Hello from Discord.",
        principal=discord_sparks_principal(
            223456789012345678
        ),
    )

    bindings = SocialSessionStore(configuration.state_path)
    desktop_principal = bindings.get(desktop_session)
    discord_principal = bindings.get(discord_session)

    assert desktop_principal is not None
    assert discord_principal is not None
    assert desktop_principal.principal_id == discord_principal.principal_id
    assert desktop_principal.audience_id == "local:text"
    assert discord_principal.audience_id == (
        "discord:dm:223456789012345678"
    )

    application.shutdown()



def test_failed_application_start_rolls_back_runtime_and_can_retry(
    personality_path: Path,
    tmp_path: Path,
    monkeypatch,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )
    original = bootstrap.load_or_bootstrap_presentation

    def fail_after_runtime_start(*args, **kwargs):
        raise OSError("synthetic presentation startup failure")

    monkeypatch.setattr(
        bootstrap,
        "load_or_bootstrap_presentation",
        fail_after_runtime_start,
    )

    with pytest.raises(
        SofiaApplicationError,
        match="failed to start",
    ):
        application.start()

    assert application.runtime.state is RuntimeState.STOPPED
    assert application.conversation.session is None

    monkeypatch.setattr(
        bootstrap,
        "load_or_bootstrap_presentation",
        original,
    )

    application.start()
    try:
        assert application.runtime.state is RuntimeState.READY
        assert application.conversation.session is not None
    finally:
        application.shutdown()



def test_disabled_act_does_not_register_background_delivery_work(
    personality_path: Path,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.delenv("SOFIA_ACT_DELIVERY_ENABLED", raising=False)
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()
    try:
        coordinator = application.background_coordinator
        assert coordinator is not None
        assert coordinator._act_delivery is None
        assert "reflection_outreach" not in coordinator._tasks
    finally:
        application.shutdown()



def test_channel_open_requires_full_application_start(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )
    application.runtime.start()
    try:
        with pytest.raises(
            SofiaApplicationError,
            match="fully started",
        ):
            application.open_channel_conversation()
    finally:
        application.shutdown()



def test_disabled_idle_reflection_does_not_expose_worker(
    personality_path: Path,
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.delenv("SOFIA_IDLE_REFLECTIONS", raising=False)
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()
    try:
        assert application.background_coordinator is not None
        assert application.idle_reflection_worker is None
    finally:
        application.shutdown()



def test_interrupted_start_rolls_back_before_propagating_keyboard_interrupt(
    personality_path: Path,
    tmp_path: Path,
    monkeypatch,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    def interrupt_after_runtime_start(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        bootstrap,
        "load_or_bootstrap_presentation",
        interrupt_after_runtime_start,
    )

    with pytest.raises(KeyboardInterrupt):
        application.start()

    assert application.runtime.state is RuntimeState.STOPPED
    assert application.conversation.session is None



def test_environment_hot_reload_reapplies_reviewed_configuration(
    personality_path: Path,
    tmp_path: Path,
    monkeypatch,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )
    changed_settings = RuntimeUserSettings(refresh_seconds=301)
    monkeypatch.setattr(
        application._environment_settings_store,
        "load",
        lambda: changed_settings,
    )

    base_configuration = object()
    reviewed_configuration = object()
    environment_service = object()
    calls = []

    def create_configuration_spy(*, state_path):
        calls.append(("base", Path(state_path)))
        return base_configuration

    def apply_reviewed_spy(configuration, state_plane):
        calls.append(("reviewed", configuration, state_plane))
        return reviewed_configuration

    def create_environment_spy(configuration):
        calls.append(("environment", configuration))
        return environment_service

    def replace_environment_spy(service):
        calls.append(("replace", service))

    monkeypatch.setattr(
        bootstrap,
        "create_production_configuration",
        create_configuration_spy,
    )
    monkeypatch.setattr(
        bootstrap,
        "apply_reviewed_configuration",
        apply_reviewed_spy,
    )
    monkeypatch.setattr(
        bootstrap,
        "create_environment_service",
        create_environment_spy,
    )
    monkeypatch.setattr(
        application.runtime,
        "replace_environment_service",
        replace_environment_spy,
    )

    assert application._reload_environment_if_settings_changed() is True
    assert calls == [
        ("base", Path(application.runtime.configuration.state_path)),
        (
            "reviewed",
            base_configuration,
            application.runtime.state_plane,
        ),
        ("environment", reviewed_configuration),
        ("replace", environment_service),
    ]



def test_all_channel_conversations_share_foreground_activity_state(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )
    application.start()
    try:
        channel = application.open_channel_conversation()
        main = application.conversation

        assert channel._activity_state is main._activity_state

        channel._activity_state.begin()
        try:
            assert main.ready_for_idle_reflection(
                idle_seconds=0,
            ) is False
        finally:
            channel._activity_state.finish()

        assert main.ready_for_idle_reflection(
            idle_seconds=0,
        ) is True
    finally:
        application.shutdown()
