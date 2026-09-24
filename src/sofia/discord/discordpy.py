"""Thin discord.py 2.7.1 adapter behind Sofía's transport-neutral gates.

Importing this module does not connect to Discord and does not read a token.
The third-party dependency is loaded only when a live client is explicitly
created.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType

from sofia.discord.access import DiscordInboundFacts, SingleUserDiscordConfig
from sofia.discord.bridge import (
    BridgeDisposition,
    DiscordConversationBridge,
)
from sofia.discord.delivery import DiscordSafeSender
from sofia.discord.inbound import DiscordTextEvent
from sofia.discord.ingress import DiscordIngress, IngressDisposition

DISCORDPY_VERSION = "2.7.1"


def load_discordpy() -> ModuleType:
    try:
        module = import_module("discord")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "discord.py is not installed; install project dependencies before "
            "creating the live Discord client"
        ) from exc
    version = getattr(module, "__version__", None)
    if version != DISCORDPY_VERSION:
        raise RuntimeError(
            f"discord.py {DISCORDPY_VERSION} is required; found {version!r}"
        )
    return module


def build_dm_intents(discord_module: ModuleType):
    """Request only direct-message Gateway events."""
    intents = discord_module.Intents.none()
    intents.dm_messages = True
    return intents


class DiscordPyMessageAdapter:
    """Convert authenticated discord.py callback objects into trusted facts."""

    def __init__(self, discord_module: ModuleType) -> None:
        self._discord = discord_module

    def to_event(
        self,
        message,
        *,
        bot_user_id: int,
    ) -> DiscordTextEvent:
        channel = message.channel
        guild = getattr(message, "guild", None)
        if isinstance(channel, self._discord.DMChannel):
            channel_kind = "dm"
        elif isinstance(channel, self._discord.GroupChannel):
            channel_kind = "group"
        elif guild is not None:
            channel_kind = "guild"
        else:
            channel_kind = "unknown"

        guild_id = getattr(guild, "id", None) if guild is not None else None
        author = getattr(message, "author", None)
        attachments = getattr(message, "attachments", ())
        return DiscordTextEvent(
            message_id=getattr(message, "id", None),
            channel_id=getattr(channel, "id", None),
            content=getattr(message, "content", None),
            attachment_count=len(attachments),
            facts=DiscordInboundFacts(
                author_user_id=getattr(author, "id", None),
                recipient_user_id=bot_user_id,
                channel_kind=channel_kind,
                guild_id=guild_id,
                author_is_bot=getattr(author, "bot", None),
                webhook_id=getattr(message, "webhook_id", None),
                authenticated_source=True,
            ),
        )


@dataclass(frozen=True, slots=True)
class DiscordLiveRuntime:
    config: SingleUserDiscordConfig
    ingress: DiscordIngress
    bridge: DiscordConversationBridge
    sender: DiscordSafeSender


def create_discordpy_client(
    runtime: DiscordLiveRuntime,
    *,
    discord_module: ModuleType | None = None,
):
    """Create, but do not start, the live DM client."""
    if not isinstance(runtime, DiscordLiveRuntime):
        raise TypeError("runtime must be DiscordLiveRuntime")
    discord = discord_module or load_discordpy()
    adapter = DiscordPyMessageAdapter(discord)
    intents = build_dm_intents(discord)

    class SofiaDiscordClient(discord.Client):
        def __init__(self) -> None:
            super().__init__(
                intents=intents,
                max_messages=None,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        async def on_ready(self) -> None:
            user = self.user
            if user is None or getattr(user, "id", None) != runtime.config.bot_user_id:
                await self.close()
                raise RuntimeError(
                    "connected Discord bot identity does not match configured bot_user_id"
                )

        async def on_message(self, message) -> None:
            user = self.user
            if user is None or getattr(user, "id", None) != runtime.config.bot_user_id:
                return

            event = adapter.to_event(message, bot_user_id=user.id)
            outcome = runtime.ingress.receive(event)
            if outcome.disposition not in (
                IngressDisposition.ACCEPTED,
                IngressDisposition.DUPLICATE,
            ):
                return

            result = await asyncio.to_thread(
                runtime.bridge.process,
                bot_user_id=user.id,
                channel_id=event.channel_id,
                message_id=event.message_id,
            )
            if result.outbox is None or result.disposition not in (
                BridgeDisposition.PREPARED,
                BridgeDisposition.ALREADY_PREPARED,
            ):
                return

            channel = message.channel

            async def send_chunk(content: str) -> int:
                sent = await channel.send(
                    content,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return sent.id

            await runtime.sender.send(
                result.outbox,
                send_chunk=send_chunk,
            )

    return SofiaDiscordClient()


def run_discordpy_client(
    token: str,
    runtime: DiscordLiveRuntime,
) -> None:
    """Explicit blocking entry point. Nothing calls this automatically."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Discord bot token must be supplied explicitly")
    client = create_discordpy_client(runtime)
    client.run(token.strip())
