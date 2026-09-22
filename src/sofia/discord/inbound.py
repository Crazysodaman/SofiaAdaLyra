"""Offline Discord DM ingress screening and *process-local* replay preflight.

No Discord transport, origin authentication, durable inbox, conversation dispatch,
message delivery, token handling, or production database access exists here.
Never use this in-memory ledger as a crash-safe inbox or a security boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import blake2b
from secrets import token_bytes
from threading import Lock

from sofia.discord.access import (
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    _snowflake,
    authorize_private_dm,
)


class InboundDenial(str, Enum):
    MALFORMED_EVENT = "malformed_event"
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
    """Screen only. No queueing, execution, message persistence, or replies."""
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


class ReplayResult(str, Enum):
    CLAIMED = "claimed"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    FULL = "full"


class InMemoryReplayLedger:
    """Bounded, atomic duplicate check for offline tests within ONE process.

    A CLAIMED value is NOT a durable enqueue, processing result, or send receipt.
    Restart clears this ledger; use a transactional durable inbox before live D1.
    """

    def __init__(self, *, capacity: int = 1024) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._key = token_bytes(32)
        self._seen: dict[tuple[int, int, int], bytes] = {}
        self._lock = Lock()

    def claim(self, screened: InboundScreen) -> ReplayResult:
        if not isinstance(screened, InboundScreen) or not screened.accepted:
            raise ValueError("an accepted inbound screen is required")
        event = screened.event
        assert event is not None
        # Keep message text out of the ledger; this digest is local and secret-keyed.
        digest = blake2b(
            event.facts.author_user_id.to_bytes(8, "big")
            + len(event.content.encode("utf-8")).to_bytes(8, "big")
            + event.content.encode("utf-8"),
            key=self._key,
            digest_size=32,
        ).digest()
        identity = (event.facts.recipient_user_id, event.channel_id, event.message_id)
        with self._lock:
            old = self._seen.get(identity)
            if old is not None:
                return ReplayResult.DUPLICATE if old == digest else ReplayResult.CONFLICT
            if len(self._seen) >= self._capacity:
                return ReplayResult.FULL
            self._seen[identity] = digest
            return ReplayResult.CLAIMED
