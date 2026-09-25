"""Environment-only Discord provisioning tests."""

import pytest

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
