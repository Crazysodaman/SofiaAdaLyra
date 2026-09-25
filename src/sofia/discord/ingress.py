"""Trusted-adapter ingress boundary for owner Discord DMs.

This service does not authenticate a socket or raw Discord payload itself.
A future gateway adapter must establish source authenticity before constructing
DiscordInboundFacts(authenticated_source=True).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.discord.access import SingleUserDiscordConfig
from sofia.discord.inbound import DiscordTextEvent, InboundScreen, screen_text_dm
from sofia.discord.store import DiscordInboxStore, InboxAcceptResult


class IngressDisposition(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    DENIED = "denied"


@dataclass(frozen=True, slots=True)
class IngressOutcome:
    disposition: IngressDisposition
    screen: InboundScreen


class DiscordIngress:
    """Screen and durably record one trusted-adapter Discord event."""

    def __init__(
        self,
        *,
        config: SingleUserDiscordConfig,
        inbox: DiscordInboxStore,
        max_chars: int = 4000,
    ) -> None:
        if not isinstance(config, SingleUserDiscordConfig):
            raise TypeError("config must be SingleUserDiscordConfig")
        if not isinstance(inbox, DiscordInboxStore):
            raise TypeError("inbox must be DiscordInboxStore")
        if type(max_chars) is not int or not 1 <= max_chars <= 4000:
            raise ValueError("max_chars must be an integer from 1 through 4000")
        self._config = config
        self._inbox = inbox
        self._max_chars = max_chars

    def receive(self, event: DiscordTextEvent) -> IngressOutcome:
        screen = screen_text_dm(
            self._config,
            event,
            max_chars=self._max_chars,
        )
        if not screen.accepted:
            return IngressOutcome(IngressDisposition.DENIED, screen)

        result = self._inbox.accept(screen)
        disposition = {
            InboxAcceptResult.INSERTED: IngressDisposition.ACCEPTED,
            InboxAcceptResult.DUPLICATE: IngressDisposition.DUPLICATE,
            InboxAcceptResult.CONFLICT: IngressDisposition.CONFLICT,
        }[result]
        return IngressOutcome(disposition, screen)
