"""Crash-aware Discord outbound chunk delivery.

A generated reply is not equivalent to a delivered Discord message. This
module persists each bounded chunk before transport, rechecks outbound
authorization before every send, records provider message IDs only after
acknowledged sends, and blocks automatic retries after ambiguous failures.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
import sqlite3

from sofia.discord.access import _snowflake
from sofia.discord.outbound import DiscordOutboundGate, OutboundDenial
from sofia.discord.store import DiscordOutboxRecord

DISCORD_MESSAGE_LIMIT = 2000


class DeliveryState(str, Enum):
    PREPARED = "prepared"
    SENT = "sent"
    OUTCOME_UNKNOWN = "outcome_unknown"


class DeliveryDisposition(str, Enum):
    SENT = "sent"
    ALREADY_SENT = "already_sent"
    BLOCKED = "blocked"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True, slots=True)
class DiscordDeliveryChunk:
    response_id: str
    chunk_index: int
    content: str
    content_digest: str
    state: DeliveryState
    platform_message_id: int | None
    last_error: str | None


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    disposition: DeliveryDisposition
    denial: OutboundDenial | None = None


def chunk_discord_text(
    content: str,
    *,
    max_chars: int = DISCORD_MESSAGE_LIMIT,
) -> tuple[str, ...]:
    """Split text without dropping or rewriting content."""
    if not isinstance(content, str) or not content:
        raise ValueError("Discord delivery content must be non-empty text")
    if type(max_chars) is not int or not 1 <= max_chars <= DISCORD_MESSAGE_LIMIT:
        raise ValueError("max_chars must be between 1 and Discord's message limit")

    chunks: list[str] = []
    start = 0
    while start < len(content):
        hard_end = min(start + max_chars, len(content))
        end = hard_end
        if hard_end < len(content):
            window = content[start:hard_end]
            newline = window.rfind("\n")
            space = window.rfind(" ")
            boundary = max(newline, space)
            if boundary >= max_chars // 2:
                end = start + boundary + 1
        chunk = content[start:end]
        if not chunk:
            end = hard_end
            chunk = content[start:end]
        chunks.append(chunk)
        start = end

    if "".join(chunks) != content:
        raise RuntimeError("Discord chunking changed message content")
    return tuple(chunks)


class DiscordDeliveryStore:
    """Durable per-chunk delivery evidence in Sofía's existing SQLite state."""

    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path), timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS discord_delivery_chunks (
                    response_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
                    content TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK (state IN ('prepared', 'sent', 'outcome_unknown')),
                    platform_message_id TEXT,
                    last_error TEXT,
                    PRIMARY KEY (response_id, chunk_index)
                )
                """
            )

    def prepare(
        self,
        outbox: DiscordOutboxRecord,
        chunks: tuple[str, ...],
    ) -> tuple[DiscordDeliveryChunk, ...]:
        if not isinstance(outbox, DiscordOutboxRecord):
            raise TypeError("outbox must be DiscordOutboxRecord")
        if not chunks or any(not isinstance(chunk, str) or not chunk for chunk in chunks):
            raise ValueError("at least one non-empty Discord chunk is required")
        if any(len(chunk) > DISCORD_MESSAGE_LIMIT for chunk in chunks):
            raise ValueError("Discord delivery chunk exceeds message limit")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT bot_user_id, channel_id, session_id, content, state
                FROM discord_outbox
                WHERE response_id = ?
                """,
                (outbox.response_id,),
            ).fetchone()
            expected = (
                str(outbox.bot_user_id),
                str(outbox.channel_id),
                outbox.session_id,
                outbox.content,
            )
            if row is None:
                raise KeyError("Discord outbox response does not exist")
            actual = (
                row["bot_user_id"],
                row["channel_id"],
                row["session_id"],
                row["content"],
            )
            if actual != expected:
                raise ValueError("Discord outbox record does not match durable state")
            if row["state"] not in ("prepared", "sent"):
                raise RuntimeError("Discord outbox is not eligible for delivery")

            existing = connection.execute(
                """
                SELECT chunk_index, content, content_digest, state,
                       platform_message_id, last_error
                FROM discord_delivery_chunks
                WHERE response_id = ?
                ORDER BY chunk_index
                """,
                (outbox.response_id,),
            ).fetchall()

            digests = tuple(sha256(chunk.encode("utf-8")).hexdigest() for chunk in chunks)
            if existing:
                if len(existing) != len(chunks):
                    raise ValueError("Discord response already has a different chunk plan")
                for index, row_existing in enumerate(existing):
                    if (
                        int(row_existing["chunk_index"]) != index
                        or row_existing["content"] != chunks[index]
                        or row_existing["content_digest"] != digests[index]
                    ):
                        raise ValueError(
                            "Discord response already has a different chunk plan"
                        )
                connection.rollback()
                return self.list(outbox.response_id)

            if row["state"] == "sent":
                raise RuntimeError("sent Discord outbox is missing delivery evidence")

            connection.executemany(
                """
                INSERT INTO discord_delivery_chunks (
                    response_id,
                    chunk_index,
                    content,
                    content_digest,
                    state
                )
                VALUES (?, ?, ?, ?, 'prepared')
                """,
                [
                    (outbox.response_id, index, chunk, digests[index])
                    for index, chunk in enumerate(chunks)
                ],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.list(outbox.response_id)

    def list(self, response_id: str) -> tuple[DiscordDeliveryChunk, ...]:
        if not isinstance(response_id, str) or not response_id.strip():
            raise ValueError("response_id must be non-empty text")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT response_id, chunk_index, content, content_digest, state,
                       platform_message_id, last_error
                FROM discord_delivery_chunks
                WHERE response_id = ?
                ORDER BY chunk_index
                """,
                (response_id.strip(),),
            ).fetchall()
        return tuple(
            DiscordDeliveryChunk(
                response_id=row["response_id"],
                chunk_index=int(row["chunk_index"]),
                content=row["content"],
                content_digest=row["content_digest"],
                state=DeliveryState(row["state"]),
                platform_message_id=(
                    int(row["platform_message_id"])
                    if row["platform_message_id"] is not None
                    else None
                ),
                last_error=row["last_error"],
            )
            for row in rows
        )

    def mark_sent(
        self,
        *,
        response_id: str,
        chunk_index: int,
        platform_message_id: int,
    ) -> None:
        if not _snowflake(platform_message_id):
            raise ValueError("platform_message_id must be a Discord snowflake")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT state, platform_message_id
                FROM discord_delivery_chunks
                WHERE response_id = ? AND chunk_index = ?
                """,
                (response_id, chunk_index),
            ).fetchone()
            if row is None:
                raise KeyError("Discord delivery chunk does not exist")
            if row["state"] == DeliveryState.SENT.value:
                if row["platform_message_id"] != str(platform_message_id):
                    raise ValueError("Discord chunk already has a different message ID")
                connection.rollback()
                return
            if row["state"] != DeliveryState.PREPARED.value:
                raise RuntimeError("ambiguous Discord delivery cannot be marked sent")
            connection.execute(
                """
                UPDATE discord_delivery_chunks
                SET state = 'sent', platform_message_id = ?, last_error = NULL
                WHERE response_id = ? AND chunk_index = ?
                """,
                (str(platform_message_id), response_id, chunk_index),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_unknown(
        self,
        *,
        response_id: str,
        chunk_index: int,
        error_kind: str,
    ) -> None:
        if not isinstance(error_kind, str) or not error_kind.strip():
            raise ValueError("error_kind must be non-empty text")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE discord_delivery_chunks
                SET state = 'outcome_unknown',
                    last_error = ?
                WHERE response_id = ? AND chunk_index = ?
                  AND state = 'prepared'
                """,
                (error_kind.strip()[:128], response_id, chunk_index),
            )

    def complete(self, response_id: str) -> bool:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT state
                FROM discord_delivery_chunks
                WHERE response_id = ?
                ORDER BY chunk_index
                """,
                (response_id,),
            ).fetchall()
            if not rows:
                raise RuntimeError("Discord response has no delivery chunks")
            if any(row["state"] != DeliveryState.SENT.value for row in rows):
                connection.rollback()
                return False
            cursor = connection.execute(
                """
                UPDATE discord_outbox
                SET state = 'sent', last_error = NULL
                WHERE response_id = ? AND state IN ('prepared', 'sent')
                """,
                (response_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Discord outbox cannot be completed")
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class DiscordSafeSender:
    """Authorize and record each Discord message chunk independently."""

    def __init__(
        self,
        *,
        gate: DiscordOutboundGate,
        deliveries: DiscordDeliveryStore,
    ) -> None:
        if not isinstance(gate, DiscordOutboundGate):
            raise TypeError("gate must be DiscordOutboundGate")
        if not isinstance(deliveries, DiscordDeliveryStore):
            raise TypeError("deliveries must be DiscordDeliveryStore")
        self._gate = gate
        self._deliveries = deliveries

    async def send(
        self,
        outbox: DiscordOutboxRecord,
        *,
        send_chunk: Callable[[str], Awaitable[int]],
    ) -> DeliveryResult:
        decision = self._gate.authorize(outbox)
        if not decision.allowed:
            return DeliveryResult(DeliveryDisposition.BLOCKED, decision.reason)

        chunks = chunk_discord_text(outbox.content)
        records = self._deliveries.prepare(outbox, chunks)
        if records and all(record.state is DeliveryState.SENT for record in records):
            self._deliveries.complete(outbox.response_id)
            return DeliveryResult(DeliveryDisposition.ALREADY_SENT)

        for record in records:
            if record.state is DeliveryState.SENT:
                continue
            if record.state is DeliveryState.OUTCOME_UNKNOWN:
                return DeliveryResult(DeliveryDisposition.OUTCOME_UNKNOWN)

            decision = self._gate.authorize(outbox)
            if not decision.allowed:
                return DeliveryResult(DeliveryDisposition.BLOCKED, decision.reason)

            try:
                platform_message_id = await send_chunk(record.content)
                if not _snowflake(platform_message_id):
                    raise ValueError("Discord send did not return a valid message ID")
                self._deliveries.mark_sent(
                    response_id=record.response_id,
                    chunk_index=record.chunk_index,
                    platform_message_id=platform_message_id,
                )
            except asyncio.CancelledError:
                self._deliveries.mark_unknown(
                    response_id=record.response_id,
                    chunk_index=record.chunk_index,
                    error_kind="CancelledError",
                )
                raise
            except Exception as exc:
                self._deliveries.mark_unknown(
                    response_id=record.response_id,
                    chunk_index=record.chunk_index,
                    error_kind=type(exc).__name__,
                )
                return DeliveryResult(DeliveryDisposition.OUTCOME_UNKNOWN)

        self._deliveries.complete(outbox.response_id)
        return DeliveryResult(DeliveryDisposition.SENT)
