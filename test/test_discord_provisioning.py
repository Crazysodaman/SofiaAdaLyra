"""Environment-only Discord provisioning tests."""

from pathlib import Path

import pytest

from sofia.config import create_production_configuration
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore
from sofia.discord.provisioning import DiscordProvisioning

OWNER = "123456789012345678"
BOT = "987654321098765432"
CHANNEL = "223456789012345678"


def enabled_env():
    return {
        "SOFIA_DISCORD_ENABLED": "1",
        "SOFIA_DISCORD_OWNER_ID": OWNER,
        "SOFIA_DISCORD_BOT_ID": BOT,
        "SOFIA_DISCORD_DM_CHANNEL_ID": CHANNEL,
        "SOFIA_DISCORD_TOKEN": "local-secret-token",
    }


def test_discord_is_disabled_by_default() -> None:
    provisioning = DiscordProvisioning.from_environment({})
    assert provisioning.enabled is False
    assert provisioning.token is None


def test_enabled_provisioning_builds_exact_single_user_config() -> None:
    provisioning = DiscordProvisioning.from_environment(enabled_env())
    config = provisioning.require_config()
    assert config.enabled is True
    assert config.owner_user_id == int(OWNER)
    assert config.bot_user_id == int(BOT)
    assert config.dm_channel_id == int(CHANNEL)
    assert provisioning.require_token() == "local-secret-token"


def test_token_is_not_in_repr() -> None:
    provisioning = DiscordProvisioning.from_environment(enabled_env())
    assert "local-secret-token" not in repr(provisioning)


@pytest.mark.parametrize(
    "missing",
    [
        "SOFIA_DISCORD_OWNER_ID",
        "SOFIA_DISCORD_BOT_ID",
        "SOFIA_DISCORD_DM_CHANNEL_ID",
        "SOFIA_DISCORD_TOKEN",
    ],
)
def test_enabled_provisioning_requires_every_secret_or_identity_field(missing) -> None:
    environ = enabled_env()
    del environ[missing]
    with pytest.raises(ValueError):
        DiscordProvisioning.from_environment(environ)


def test_disabled_mode_does_not_require_or_validate_live_fields() -> None:
    provisioning = DiscordProvisioning.from_environment(
        {
            "SOFIA_DISCORD_ENABLED": "0",
            "SOFIA_DISCORD_OWNER_ID": "garbage",
            "SOFIA_DISCORD_TOKEN": "",
        }
    )
    assert provisioning.enabled is False



def _configuration(tmp_path: Path) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="test-model",
        ),
        filesystem_root=tmp_path,
    )


def test_runtime_provisioning_loads_saved_ids_and_protected_token(
    tmp_path,
    monkeypatch,
):
    configuration = _configuration(tmp_path)
    RuntimeUserSettingsStore(configuration.state_path).save(
        RuntimeUserSettings(
            discord_enabled=True,
            discord_owner_user_id=int(OWNER),
            discord_bot_user_id=int(BOT),
            discord_dm_channel_id=int(CHANNEL),
        )
    )

    class Secrets:
        def get(self, key):
            assert key == "discord-token"
            return "saved-secret-token"

    monkeypatch.setattr(
        "sofia.discord.provisioning.ProtectedSecretStore.for_state_path",
        staticmethod(lambda path: Secrets()),
    )

    provisioning = DiscordProvisioning.from_runtime(
        configuration,
        environ={},
    )

    assert provisioning.enabled is True
    assert provisioning.owner_user_id == int(OWNER)
    assert provisioning.bot_user_id == int(BOT)
    assert provisioning.dm_channel_id == int(CHANNEL)
    assert provisioning.require_token() == "saved-secret-token"


def test_runtime_provisioning_environment_override_wins(
    tmp_path,
    monkeypatch,
):
    configuration = _configuration(tmp_path)
    RuntimeUserSettingsStore(configuration.state_path).save(
        RuntimeUserSettings()
    )

    provisioning = DiscordProvisioning.from_runtime(
        configuration,
        environ=enabled_env(),
    )

    assert provisioning.require_token() == "local-secret-token"


def test_runtime_provisioning_saved_disabled_does_not_require_secret(
    tmp_path,
):
    configuration = _configuration(tmp_path)
    RuntimeUserSettingsStore(configuration.state_path).save(
        RuntimeUserSettings(discord_enabled=False)
    )

    provisioning = DiscordProvisioning.from_runtime(
        configuration,
        environ={},
    )

    assert provisioning.enabled is False



def test_production_discord_reads_saved_settings_from_live_state(
    tmp_path,
    monkeypatch,
):
    state_root = tmp_path / "ProgramData" / "SofiaAdaLyra"
    protected_root = state_root / "protected"
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("SOFIA_PROTECTED_ROOT", str(protected_root))
    monkeypatch.delenv("SOFIA_DISCORD_ENABLED", raising=False)

    RuntimeUserSettingsStore(state_root / "sofia.db").save(
        RuntimeUserSettings(
            discord_enabled=True,
            discord_owner_user_id=int(OWNER),
            discord_bot_user_id=int(BOT),
            discord_dm_channel_id=int(CHANNEL),
        )
    )

    class Secrets:
        def get(self, key):
            assert key == "discord-token"
            return "production-secret-token"

    monkeypatch.setattr(
        "sofia.discord.provisioning.ProtectedSecretStore.for_state_path",
        staticmethod(lambda path: Secrets()),
    )

    configuration = create_production_configuration()
    provisioning = DiscordProvisioning.from_runtime(
        configuration,
        environ={},
    )

    assert configuration.state_path == state_root / "sofia.db"
    assert provisioning.enabled is True
    assert provisioning.owner_user_id == int(OWNER)
    assert provisioning.bot_user_id == int(BOT)
    assert provisioning.dm_channel_id == int(CHANNEL)
    assert provisioning.require_token() == "production-secret-token"
