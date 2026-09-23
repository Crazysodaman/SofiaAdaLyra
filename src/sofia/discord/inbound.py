"""Offline Discord DM ingress screening.

No Discord transport, token handling, conversation dispatch, or outbound send
exists here. A DiscordTextEvent is data produced by a future trusted adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.discord.access import (
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    _snowflake,
    authorize_private_dm,
)


class InboundDenial(str, Enum):
    MALFORMED_EVENT = "malformed_event"
    WRONG_CHANNEL = "wrong_channel"
    UNSUPPORTED_CONTENT = "unsupported_content"
    EMPTY_CONTENT = "empty_content"
    CONTENT_TOO_LONG = "content_too_long"


@dataclass(frozen=True, slots=True)
class DiscordTextEvent:
    """Data from a trusted adapter, NOT a raw or self-authenticating payload."""

    message_id: int
    channel_id: int
    content: str
    facts: DiscordInboundFacts
    attachment_count: int = 0


@dataclass(frozen=True, slots=True)
class InboundScreen:
    event: DiscordTextEvent | None
    denial: Denial | InboundDenial | None

    @property
    def accepted(self) -> bool:
        return self.event is not None and self.denial is None


def screen_text_dm(
    config: SingleUserDiscordConfig,
    event: DiscordTextEvent,
    *,
    max_chars: int = 4000,
) -> InboundScreen:
    """Screen one text DM without queueing, executing, or replying."""
    if not isinstance(config, SingleUserDiscordConfig):
        raise TypeError("config must be SingleUserDiscordConfig")
    if not isinstance(event, DiscordTextEvent):
        raise TypeError("event must be DiscordTextEvent")
    if type(max_chars) is not int or not 1 <= max_chars <= 4000:
        raise ValueError("max_chars must be an integer from 1 through 4000")
    access = authorize_private_dm(config, event.facts)
    if not access.allowed:
        return InboundScreen(None, access.reason)
    if (
        not _snowflake(event.message_id)
        or not _snowflake(event.channel_id)
        or type(event.attachment_count) is not int
        or event.attachment_count < 0
        or type(event.content) is not str
    ):
        return InboundScreen(None, InboundDenial.MALFORMED_EVENT)
    if (
        config.dm_channel_id is not None
        and event.channel_id != config.dm_channel_id
    ):
        return InboundScreen(None, InboundDenial.WRONG_CHANNEL)
    if event.attachment_count:
        return InboundScreen(None, InboundDenial.UNSUPPORTED_CONTENT)
    if not event.content.strip():
        return InboundScreen(None, InboundDenial.EMPTY_CONTENT)
    if "\x00" in event.content:
        return InboundScreen(None, InboundDenial.UNSUPPORTED_CONTENT)
    if len(event.content) > max_chars:
        return InboundScreen(None, InboundDenial.CONTENT_TOO_LONG)
    try:
        event.content.encode("utf-8")
    except UnicodeEncodeError:
        return InboundScreen(None, InboundDenial.MALFORMED_EVENT)
    return InboundScreen(event, None)
