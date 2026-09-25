"""Explicit environment provisioning for the single-owner Discord transport.

Secrets are read only by the live Discord entry point. Disabled configuration
requires no IDs or token, and token values are excluded from object repr.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import os

from sofia.discord.access import SingleUserDiscordConfig, _snowflake


def _enabled(value: str | None) -> bool:
    setting = (value or "").strip().lower()
    if setting in ("", "0", "false", "off", "no"):
        return False
    if setting in ("1", "true", "on", "yes"):
        return True
    raise ValueError(
        "SOFIA_DISCORD_ENABLED must be 1 or 0 "
        "(also accepts true/false, on/off, yes/no)"
    )


def _required_snowflake(environ: Mapping[str, str], name: str) -> int:
    raw = environ.get(name, "").strip()
    if not raw or not raw.isascii() or not raw.isdigit():
        raise ValueError(f"{name} must be a positive Discord snowflake")
    value = int(raw)
    if not _snowflake(value):
        raise ValueError(f"{name} must be a positive Discord snowflake")
    return value


@dataclass(frozen=True, slots=True)
class DiscordIdentity:
    owner_user_id: int
    bot_user_id: int
    dm_channel_id: int

    def __post_init__(self) -> None:
        if not _snowflake(self.owner_user_id):
            raise ValueError("owner_user_id must be a positive Discord snowflake")
        if not _snowflake(self.bot_user_id):
            raise ValueError("bot_user_id must be a positive Discord snowflake")
        if not _snowflake(self.dm_channel_id):
            raise ValueError("dm_channel_id must be a positive Discord snowflake")
        if self.owner_user_id == self.bot_user_id:
            raise ValueError("Discord owner and bot IDs must differ")

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "DiscordIdentity":
        source = os.environ if environ is None else environ
        owner = _required_snowflake(source, "SOFIA_DISCORD_OWNER_ID")
        bot = _required_snowflake(source, "SOFIA_DISCORD_BOT_ID")
        channel = _required_snowflake(source, "SOFIA_DISCORD_DM_CHANNEL_ID")
        if owner == bot:
            raise ValueError("Discord owner and bot IDs must differ")
        return cls(owner_user_id=owner, bot_user_id=bot, dm_channel_id=channel)


@dataclass(frozen=True, slots=True)
class DiscordProvisioning:
    enabled: bool
    owner_user_id: int | None = None
    bot_user_id: int | None = None
    dm_channel_id: int | None = None
    token: str | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "DiscordProvisioning":
        source = os.environ if environ is None else environ
        enabled = _enabled(source.get("SOFIA_DISCORD_ENABLED"))
        if not enabled:
            return cls(enabled=False)

        identity = DiscordIdentity.from_environment(source)
        token = source.get("SOFIA_DISCORD_TOKEN", "").strip()
        if not token:
            raise ValueError(
                "SOFIA_DISCORD_TOKEN must be supplied when Discord is enabled"
            )
        return cls(
            enabled=True,
            owner_user_id=identity.owner_user_id,
            bot_user_id=identity.bot_user_id,
            dm_channel_id=identity.dm_channel_id,
            token=token,
        )

    def require_config(self) -> SingleUserDiscordConfig:
        if not self.enabled:
            raise RuntimeError("Discord transport is disabled")
        assert self.owner_user_id is not None
        assert self.bot_user_id is not None
        assert self.dm_channel_id is not None
        return SingleUserDiscordConfig(
            owner_user_id=self.owner_user_id,
            bot_user_id=self.bot_user_id,
            enabled=True,
            dm_channel_id=self.dm_channel_id,
        )

    def require_token(self) -> str:
        if not self.enabled or not isinstance(self.token, str) or not self.token:
            raise RuntimeError("Discord transport token is unavailable")
        return self.token
