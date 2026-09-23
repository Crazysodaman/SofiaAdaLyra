"""Discord channel boundaries. No live client is started by importing this package."""

from sofia.discord.access import (
    AccessDecision,
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    authorize_private_dm,
)
from sofia.discord.inbound import (
    DiscordTextEvent,
    InboundDenial,
    InboundScreen,
    screen_text_dm,
)
from sofia.discord.ingress import (
    DiscordIngress,
    IngressDisposition,
    IngressOutcome,
)
from sofia.discord.store import (
    DiscordInboxRecord,
    DiscordInboxStore,
    InboxAcceptResult,
)

__all__ = (
    "AccessDecision",
    "Denial",
    "DiscordInboundFacts",
    "SingleUserDiscordConfig",
    "authorize_private_dm",
    "DiscordTextEvent",
    "InboundDenial",
    "InboundScreen",
    "screen_text_dm",
    "DiscordIngress",
    "IngressDisposition",
    "IngressOutcome",
    "DiscordInboxRecord",
    "DiscordInboxStore",
    "InboxAcceptResult",
)
