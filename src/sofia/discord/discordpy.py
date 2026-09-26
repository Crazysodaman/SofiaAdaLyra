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
from sofia.discord.act_live import DiscordActTransportBridge
from sofia.discord.act_sender import DiscordActSafeSender
from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.bridge import (
    BridgeDisposition,
    DiscordConversationBridge,
)
from sofia.discord.delivery import DiscordSafeSender
from sofia.discord.inbound import DiscordTextEvent, screen_text_dm
from sofia.discord.ingress import DiscordIngress, IngressDisposition
from sofia.discord.store import DiscordInboxStore, DiscordOutboxRecord

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
    store: DiscordInboxStore
    bindings: DiscordBindingStore
    session_id: str
    act_transport: DiscordActTransportBridge | None = None
    act_sender: DiscordActSafeSender | None = None


def ensure_verified_binding(runtime: DiscordLiveRuntime):
    """Create the first durable binding only after Discord identity verification."""
    binding = runtime.bindings.get(
        bot_user_id=runtime.config.bot_user_id,
        channel_id=runtime.config.dm_channel_id,
    )
    if binding is None:
        return runtime.bindings.bind(
            bot_user_id=runtime.config.bot_user_id,
            owner_user_id=runtime.config.owner_user_id,
            channel_id=runtime.config.dm_channel_id,
            session_id=runtime.session_id,
        )
    if binding.owner_user_id != runtime.config.owner_user_id:
        raise RuntimeError(
            "configured Discord owner does not match durable channel binding"
        )
    if binding.state is BindingState.REVOKED:
        raise RuntimeError(
            "Discord channel binding is revoked; supervised re-enrollment is required"
        )
    if binding.session_id != runtime.session_id:
        raise RuntimeError(
            "Discord channel binding does not match the active Sofía conversation"
        )
    return binding


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
            self._message_lock = asyncio.Lock()
            self._sofia_startup_error: Exception | None = None
            self._sofia_ready = False

        async def _send_outbox(self, channel, outbox: DiscordOutboxRecord) -> None:
            async def send_chunk(content: str) -> int:
                sent = await channel.send(
                    content,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return sent.id

            await runtime.sender.send(
                outbox,
                send_chunk=send_chunk,
            )

        async def _bound_dm_channel(self):
            channel_id = runtime.config.dm_channel_id
            if channel_id is None:
                raise RuntimeError("live Discord requires a pinned DM channel")
            owner = await self.fetch_user(runtime.config.owner_user_id)
            channel = await owner.create_dm()
            if getattr(channel, "id", None) != channel_id:
                raise RuntimeError(
                    "resolved Discord DM channel does not match configured dm_channel_id"
                )
            return channel

        def _bind_act_transport(self, channel) -> None:
            if runtime.act_transport is None:
                return

            async def send_chunk(content: str) -> int:
                sent = await channel.send(
                    content,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return sent.id

            runtime.act_transport.bind(
                loop=asyncio.get_running_loop(),
                channel_id=channel.id,
                send_chunk_async=send_chunk,
            )

        async def _recover_prepared_outbox(self, channel) -> None:
            pending = runtime.store.list_outbox(
                bot_user_id=runtime.config.bot_user_id,
                channel_id=runtime.config.dm_channel_id,
                states=("prepared",),
            )
            for outbox in pending:
                await self._send_outbox(channel, outbox)

        async def on_ready(self) -> None:
            user = self.user
            if user is None or getattr(user, "id", None) != runtime.config.bot_user_id:
                self._sofia_startup_error = RuntimeError(
                    "connected Discord bot identity does not match configured bot_user_id"
                )
                await self.close()
                return
            try:
                channel = await self._bound_dm_channel()
                async with self._message_lock:
                    ensure_verified_binding(runtime)
                    await self._recover_prepared_outbox(channel)
                    self._bind_act_transport(channel)
                self._sofia_ready = True
                print(
                    "Sofía Discord ready: authenticated bot identity and "
                    "private DM channel verified."
                )
            except Exception as exc:
                self._sofia_startup_error = exc
                await self.close()
                return

        async def on_disconnect(self) -> None:
            if runtime.act_transport is not None:
                runtime.act_transport.unbind()

        async def on_message(self, message) -> None:
            user = self.user
            if user is None or getattr(user, "id", None) != runtime.config.bot_user_id:
                return

            event = adapter.to_event(message, bot_user_id=user.id)
            if not screen_text_dm(runtime.config, event).accepted:
                return

            async with self._message_lock:
                binding = runtime.bindings.get(
                    bot_user_id=user.id,
                    channel_id=event.channel_id,
                )
                if binding is None or binding.state is not BindingState.ACTIVE:
                    return

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

                await self._send_outbox(message.channel, result.outbox)

    return SofiaDiscordClient()


def run_discordpy_client(
    token: str,
    runtime: DiscordLiveRuntime,
) -> None:
    """Explicit blocking entry point. Nothing calls this automatically."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Discord bot token must be supplied explicitly")
    client = create_discordpy_client(runtime)
    try:
        client.run(token.strip())
    finally:
        act_transport = getattr(runtime, "act_transport", None)
        if act_transport is not None:
            act_transport.unbind()
    startup_error = getattr(client, "_sofia_startup_error", None)
    if startup_error is not None:
        raise RuntimeError(f"Discord startup failed: {startup_error}") from startup_error
    if not getattr(client, "_sofia_ready", False):
        raise RuntimeError("Discord client exited before authenticated readiness")
