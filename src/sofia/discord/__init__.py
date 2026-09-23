"""Discord channel boundaries. Importing this package starts no live client."""

from sofia.discord.access import (
    AccessDecision,
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    authorize_private_dm,
)
from sofia.discord.bridge import (
    BridgeDisposition,
    BridgeResult,
    DiscordBridgeError,
    DiscordConversationBridge,
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
    DiscordOutboxRecord,
    InboxAcceptResult,
    InboxClaimResult,
)

__all__ = (
    "AccessDecision",
    "Denial",
    "DiscordInboundFacts",
    "SingleUserDiscordConfig",
    "authorize_private_dm",
    "BridgeDisposition",
    "BridgeResult",
    "DiscordBridgeError",
    "DiscordConversationBridge",
    "DiscordTextEvent",
    "InboundDenial",
    "InboundScreen",
    "screen_text_dm",
    "DiscordIngress",
    "IngressDisposition",
    "IngressOutcome",
    "DiscordInboxRecord",
    "DiscordInboxStore",
    "DiscordOutboxRecord",
    "InboxAcceptResult",
    "InboxClaimResult",
)
