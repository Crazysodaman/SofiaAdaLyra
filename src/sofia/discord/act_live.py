"""Thread-safe bridge from synchronous ACT delivery to discord.py's event loop.

The live Discord client owns the async network transport. RUN/ACT callers remain
synchronous and may execute on worker/host threads. This bridge binds only after
the authenticated pinned DM channel is verified, uses
`asyncio.run_coroutine_threadsafe` for cross-thread handoff, and unbinds on
disconnect/shutdown.

Constructing or importing this module performs no network I/O.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import RLock

from sofia.discord.access import _snowflake
from sofia.discord.delivery import DISCORD_MESSAGE_LIMIT


class DiscordActTransportBridge:
    """Synchronous transport callable backed by a verified async Discord loop."""

    def __init__(
        self,
        *,
        expected_channel_id: int,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not _snowflake(expected_channel_id):
            raise ValueError("expected_channel_id must be a Discord snowflake")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not 1.0 <= float(timeout_seconds) <= 120.0
        ):
            raise ValueError("timeout_seconds must be in 1..120")

        self.expected_channel_id = expected_channel_id
        self.timeout_seconds = float(timeout_seconds)
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._send_chunk_async: Callable[[str], Awaitable[int]] | None = None

    @property
    def connected(self) -> bool:
        with self._lock:
            loop = self._loop
            sender = self._send_chunk_async
        return bool(
            loop is not None
            and sender is not None
            and loop.is_running()
            and not loop.is_closed()
        )

    def bind(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        channel_id: int,
        send_chunk_async: Callable[[str], Awaitable[int]],
    ) -> None:
        if not isinstance(loop, asyncio.AbstractEventLoop):
            raise TypeError("asyncio event loop required")
        if channel_id != self.expected_channel_id:
            raise RuntimeError("Discord ACT channel does not match pinned channel")
        if not callable(send_chunk_async):
            raise TypeError("send_chunk_async must be callable")
        if loop.is_closed() or not loop.is_running():
            raise RuntimeError("Discord event loop must be running before ACT bind")

        with self._lock:
            self._loop = loop
            self._send_chunk_async = send_chunk_async

    def unbind(self) -> None:
        with self._lock:
            self._loop = None
            self._send_chunk_async = None

    def send_chunk(self, content: str) -> int:
        if (
            not isinstance(content, str)
            or not content
            or len(content) > DISCORD_MESSAGE_LIMIT
        ):
            raise ValueError("Discord ACT chunk must be 1..2000 characters")

        with self._lock:
            loop = self._loop
            sender = self._send_chunk_async

        if (
            loop is None
            or sender is None
            or loop.is_closed()
            or not loop.is_running()
        ):
            raise RuntimeError("Discord ACT transport is not ready")

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            raise RuntimeError(
                "synchronous ACT send cannot run on the Discord event-loop thread"
            )

        future = asyncio.run_coroutine_threadsafe(sender(content), loop)
        try:
            message_id = future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            raise TimeoutError("Discord ACT transport timed out") from None

        if not _snowflake(message_id):
            raise ValueError("Discord transport returned invalid message ID")
        return message_id
