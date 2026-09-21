"""Discord adapter boundaries; this package does not start a Discord client."""

from sofia.discord.access import (
    AccessDecision,
    Denial,
    DiscordInboundFacts,
    SingleUserDiscordConfig,
    authorize_private_dm,
)

__all__ = (
    "AccessDecision",
    "Denial",
    "DiscordInboundFacts",
    "SingleUserDiscordConfig",
    "authorize_private_dm",
)
