"""Final offline authorization gate for a future Discord send adapter.

A prepared outbox row is not permission to send. The gate rechecks current
configuration, exact recipient/channel/session binding, pause/revoke state, and
binding generation immediately before transport would be allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.discord.access import SingleUserDiscordConfig
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.store import DiscordOutboxRecord


class OutboundDenial(str, Enum):
    DISABLED = "disabled"
    CHANNEL_NOT_PINNED = "channel_not_pinned"
    NOT_PREPARED = "not_prepared"
    WRONG_BOT = "wrong_bot"
    WRONG_CHANNEL = "wrong_channel"
    MISSING_AUTHORITY = "missing_authority"
    WRONG_RECIPIENT = "wrong_recipient"
    UNBOUND = "unbound"
    PAUSED = "paused"
    REVOKED = "revoked"
    SESSION_MISMATCH = "session_mismatch"
    STALE_BINDING = "stale_binding"


@dataclass(frozen=True, slots=True)
class OutboundDecision:
    allowed: bool
    reason: OutboundDenial | None


class DiscordOutboundGate:
    """Recheck durable authority immediately before any future network send."""

    def __init__(
        self,
        *,
        config: SingleUserDiscordConfig,
        bindings: DiscordBindingStore,
    ) -> None:
        if not isinstance(config, SingleUserDiscordConfig):
            raise TypeError("config must be SingleUserDiscordConfig")
        if not isinstance(bindings, DiscordBindingStore):
            raise TypeError("bindings must be DiscordBindingStore")
        self._config = config
        self._bindings = bindings

    def authorize(self, outbox: DiscordOutboxRecord) -> OutboundDecision:
        if not isinstance(outbox, DiscordOutboxRecord):
            raise TypeError("outbox must be DiscordOutboxRecord")
        if not self._config.enabled:
            return OutboundDecision(False, OutboundDenial.DISABLED)
        if self._config.dm_channel_id is None:
            return OutboundDecision(False, OutboundDenial.CHANNEL_NOT_PINNED)
        if outbox.state != "prepared":
            return OutboundDecision(False, OutboundDenial.NOT_PREPARED)
        if outbox.bot_user_id != self._config.bot_user_id:
            return OutboundDecision(False, OutboundDenial.WRONG_BOT)
        if outbox.channel_id != self._config.dm_channel_id:
            return OutboundDecision(False, OutboundDenial.WRONG_CHANNEL)

        authority = self._bindings.outbox_binding(outbox.response_id)
        if authority is None:
            return OutboundDecision(False, OutboundDenial.MISSING_AUTHORITY)
        if authority.owner_user_id != self._config.owner_user_id:
            return OutboundDecision(False, OutboundDenial.WRONG_RECIPIENT)
        if (
            authority.bot_user_id != outbox.bot_user_id
            or authority.channel_id != outbox.channel_id
        ):
            return OutboundDecision(False, OutboundDenial.MISSING_AUTHORITY)
        if authority.session_id != outbox.session_id:
            return OutboundDecision(False, OutboundDenial.SESSION_MISMATCH)

        current = self._bindings.get(
            bot_user_id=outbox.bot_user_id,
            channel_id=outbox.channel_id,
        )
        if current is None:
            return OutboundDecision(False, OutboundDenial.UNBOUND)
        if current.state is BindingState.PAUSED:
            return OutboundDecision(False, OutboundDenial.PAUSED)
        if current.state is BindingState.REVOKED:
            return OutboundDecision(False, OutboundDenial.REVOKED)
        if current.owner_user_id != self._config.owner_user_id:
            return OutboundDecision(False, OutboundDenial.WRONG_RECIPIENT)
        if current.session_id != outbox.session_id:
            return OutboundDecision(False, OutboundDenial.SESSION_MISMATCH)
        if current.generation != authority.binding_generation:
            return OutboundDecision(False, OutboundDenial.STALE_BINDING)

        return OutboundDecision(True, None)
