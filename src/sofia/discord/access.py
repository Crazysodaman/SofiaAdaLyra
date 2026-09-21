"""Fail-closed inbound Discord DM policy for the initial single-user rollout.

This module does not authenticate Discord events: callers must supply facts
from a trusted gateway/adapter, never from an LLM, username, or message body.
It has no network operations, bot token handling, outbox, or side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


def _snowflake(value: object) -> bool:
    """Discord snowflakes are positive integers; booleans are not IDs."""
    return type(value) is int and 0 < value < (1 << 64)


class Denial(str, Enum):
    DISABLED = "disabled"
    UNVERIFIED_SOURCE = "unverified_source"
    MALFORMED = "malformed"
    NOT_DIRECT_MESSAGE = "not_direct_message"
    WRONG_RECIPIENT = "wrong_recipient"
    NOT_OWNER = "not_owner"
    AUTOMATED_SENDER = "automated_sender"


@dataclass(frozen=True, slots=True)
class SingleUserDiscordConfig:
    """Exact Discord account IDs, configured outside message content."""

    owner_user_id: int
    bot_user_id: int
    enabled: bool = False

    def __post_init__(self) -> None:
        if not _snowflake(self.owner_user_id):
            raise ValueError("owner_user_id must be a positive Discord snowflake")
        if not _snowflake(self.bot_user_id):
            raise ValueError("bot_user_id must be a positive Discord snowflake")
        if self.owner_user_id == self.bot_user_id:
            raise ValueError("owner_user_id and bot_user_id must differ")
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be a boolean")


@dataclass(frozen=True, slots=True)
class DiscordInboundFacts:
    """Metadata derived by an authenticated adapter, not raw user claims.

    ``authenticated_source`` alone cannot verify a gateway message. The
    adapter must establish authenticated origin *before* constructing facts.
    ``recipient_user_id`` must refer to the bot receiving this DM, not a
    mention or a name supplied in message text.
    """

    author_user_id: int | None
    recipient_user_id: int | None
    channel_kind: str | None
    guild_id: int | None
    author_is_bot: bool | None
    webhook_id: int | None
    authenticated_source: bool


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reason: Denial | None


def authorize_private_dm(
    config: SingleUserDiscordConfig,
    facts: DiscordInboundFacts,
) -> AccessDecision:
    """Authorize only authenticated, human-authored owner-to-bot private DMs.

    No message content, display name, relationship state, guild role, or LLM
    instruction can override this check. An accepted inbound event grants
    *no* permission to send proactive messages, access files, or browse.
    """
    if not isinstance(config, SingleUserDiscordConfig):
        raise TypeError("config must be SingleUserDiscordConfig")
    if not isinstance(facts, DiscordInboundFacts):
        raise TypeError("facts must be DiscordInboundFacts")
    if not config.enabled:
        return AccessDecision(False, Denial.DISABLED)
    if facts.authenticated_source is not True:
        return AccessDecision(False, Denial.UNVERIFIED_SOURCE)
    if (
        not _snowflake(facts.author_user_id)
        or not _snowflake(facts.recipient_user_id)
        or type(facts.author_is_bot) is not bool
        or (facts.guild_id is not None and not _snowflake(facts.guild_id))
        or (facts.webhook_id is not None and not _snowflake(facts.webhook_id))
        or type(facts.channel_kind) is not str
    ):
        return AccessDecision(False, Denial.MALFORMED)
    if facts.channel_kind != "dm" or facts.guild_id is not None:
        return AccessDecision(False, Denial.NOT_DIRECT_MESSAGE)
    if facts.author_is_bot or facts.webhook_id is not None:
        return AccessDecision(False, Denial.AUTOMATED_SENDER)
    if facts.recipient_user_id != config.bot_user_id:
        return AccessDecision(False, Denial.WRONG_RECIPIENT)
    if facts.author_user_id != config.owner_user_id:
        return AccessDecision(False, Denial.NOT_OWNER)
    return AccessDecision(True, None)
