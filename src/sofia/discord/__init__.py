"""Discord channel boundaries. Importing this package starts no live client."""

from sofia.discord.act_sender import (
    DiscordActAttempt,
    DiscordActChunk,
    DiscordActChunkState,
    DiscordActDeliveryStore,
    DiscordActSafeSender,
)
from sofia.discord.access import (
    AccessDecision,
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    authorize_private_dm,
)
from sofia.discord.binding import (
    BindingState,
    DiscordBindingStore,
    DiscordChannelBinding,
    DiscordOutboundBinding,
)
from sofia.discord.bridge import (
    BridgeDisposition,
    BridgeResult,
    DiscordBridgeError,
    DiscordConversationBridge,
)
from sofia.discord.delivery import (
    DISCORD_MESSAGE_LIMIT,
    DeliveryDisposition,
    DeliveryResult,
    DeliveryState,
    DiscordDeliveryChunk,
    DiscordDeliveryStore,
    DiscordSafeSender,
    chunk_discord_text,
)
from sofia.discord.discordpy import (
    DISCORDPY_VERSION,
    DiscordLiveRuntime,
    DiscordPyMessageAdapter,
    build_dm_intents,
    create_discordpy_client,
    load_discordpy,
    run_discordpy_client,
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
from sofia.discord.outbound import (
    DiscordOutboundGate,
    OutboundDecision,
    OutboundDenial,
)
from sofia.discord.store import (
    DiscordInboxRecord,
    DiscordInboxStore,
    DiscordOutboxRecord,
    InboxAcceptResult,
    InboxClaimResult,
)

__all__ = (
    "DiscordActAttempt",
    "DiscordActChunk",
    "DiscordActChunkState",
    "DiscordActDeliveryStore",
    "DiscordActSafeSender",
    "AccessDecision",
    "Denial",
    "DiscordInboundFacts",
    "SingleUserDiscordConfig",
    "authorize_private_dm",
    "BindingState",
    "DiscordBindingStore",
    "DiscordChannelBinding",
    "DiscordOutboundBinding",
    "BridgeDisposition",
    "BridgeResult",
    "DiscordBridgeError",
    "DiscordConversationBridge",
    "DISCORD_MESSAGE_LIMIT",
    "DeliveryDisposition",
    "DeliveryResult",
    "DeliveryState",
    "DiscordDeliveryChunk",
    "DiscordDeliveryStore",
    "DiscordSafeSender",
    "chunk_discord_text",
    "DISCORDPY_VERSION",
    "DiscordLiveRuntime",
    "DiscordPyMessageAdapter",
    "build_dm_intents",
    "create_discordpy_client",
    "load_discordpy",
    "run_discordpy_client",
    "DiscordTextEvent",
    "InboundDenial",
    "InboundScreen",
    "screen_text_dm",
    "DiscordIngress",
    "IngressDisposition",
    "IngressOutcome",
    "DiscordOutboundGate",
    "OutboundDecision",
    "OutboundDenial",
    "DiscordInboxRecord",
    "DiscordInboxStore",
    "DiscordOutboxRecord",
    "InboxAcceptResult",
    "InboxClaimResult",
)
