"""Crash-aware Discord sender adapter for PKG-ACT proactive delivery.

ACT owns eligibility, recipient/channel binding, retry policy, and its durable
attempt ledger. This adapter adds Discord-specific authority checks and
chunk-level transport evidence without pretending proactive messages are
replies to fabricated inbound Discord message IDs.

Importing or constructing these classes performs no network I/O.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
import sqlite3
from typing import Callable
from uuid import uuid4

from sofia.act.delivery import (
    DeliveryOutcome,
    DeliveryPayload,
    SendResult,
)
from sofia.discord.access import SingleUserDiscordConfig, _snowflake
from sofia.discord.binding import (
    BindingState,
    DiscordBindingStore,
    DiscordChannelBinding,
)
from sofia.discord.delivery import chunk_discord_text


class DiscordActChunkState(str, Enum):
    PREPARED = "prepared"
    SENT = "sent"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True, slots=True)
class DiscordActChunk:
    attempt_id: str
    chunk_index: int
    content: str
    state: DiscordActChunkState
    platform_message_id: int | None
    send_in_progress: bool
    last_error: str | None


@dataclass(frozen=True, slots=True)
class DiscordActAttempt:
    attempt_id: str
    message_id: str
    recipient_id: str
    bot_user_id: int
    owner_user_id: int
    channel_id: int
    session_id: str
    binding_generation: int
    content_digest: str
    state: str
    receipt_id: str | None
    last_error: str | None


class DiscordActDeliveryStore:
    """Durable proactive Discord transport evidence keyed by ACT attempt ID."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path), timeout=5.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS discord_act_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    recipient_id TEXT NOT NULL,
                    bot_user_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    binding_generation INTEGER NOT NULL CHECK(binding_generation > 0),
                    content_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                        ('prepared','delivered','outcome_unknown')),
                    receipt_id TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL DEFAULT
                        (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );

                CREATE TABLE IF NOT EXISTS discord_act_chunks (
                    attempt_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
                    content TEXT NOT NULL,
                    content_digest TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                        ('prepared','sent','outcome_unknown')),
                    platform_message_id TEXT,
                    send_token TEXT,
                    last_error TEXT,
                    PRIMARY KEY (attempt_id, chunk_index),
                    FOREIGN KEY (attempt_id)
                        REFERENCES discord_act_attempts(attempt_id)
                );
                """
            )

    @staticmethod
    def _attempt_from_row(row: sqlite3.Row) -> DiscordActAttempt:
        return DiscordActAttempt(
            attempt_id=row["attempt_id"],
            message_id=row["message_id"],
            recipient_id=row["recipient_id"],
            bot_user_id=int(row["bot_user_id"]),
            owner_user_id=int(row["owner_user_id"]),
            channel_id=int(row["channel_id"]),
            session_id=row["session_id"],
            binding_generation=int(row["binding_generation"]),
            content_digest=row["content_digest"],
            state=row["state"],
            receipt_id=row["receipt_id"],
            last_error=row["last_error"],
        )

    def attempt(self, attempt_id: str) -> DiscordActAttempt | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT attempt_id, message_id, recipient_id, bot_user_id,
                       owner_user_id, channel_id, session_id,
                       binding_generation, content_digest, state,
                       receipt_id, last_error
                FROM discord_act_attempts
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()
        return None if row is None else self._attempt_from_row(row)

    def prepare(
        self,
        payload: DeliveryPayload,
        *,
        binding: DiscordChannelBinding,
    ) -> DiscordActAttempt:
        if not isinstance(payload, DeliveryPayload):
            raise TypeError("DeliveryPayload required")
        if not isinstance(binding, DiscordChannelBinding):
            raise TypeError("DiscordChannelBinding required")

        chunks = chunk_discord_text(payload.content)
        content_digest = sha256(payload.content.encode("utf-8")).hexdigest()
        chunk_digests = tuple(
            sha256(chunk.encode("utf-8")).hexdigest() for chunk in chunks
        )

        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                """
                SELECT attempt_id, message_id, recipient_id, bot_user_id,
                       owner_user_id, channel_id, session_id,
                       binding_generation, content_digest, state,
                       receipt_id, last_error
                FROM discord_act_attempts
                WHERE attempt_id = ?
                """,
                (payload.attempt_id,),
            ).fetchone()
            if existing is not None:
                expected = (
                    payload.message_id,
                    payload.recipient_id,
                    str(binding.bot_user_id),
                    str(binding.owner_user_id),
                    str(binding.channel_id),
                    binding.session_id,
                    binding.generation,
                    content_digest,
                )
                actual = (
                    existing["message_id"],
                    existing["recipient_id"],
                    existing["bot_user_id"],
                    existing["owner_user_id"],
                    existing["channel_id"],
                    existing["session_id"],
                    int(existing["binding_generation"]),
                    existing["content_digest"],
                )
                if actual != expected:
                    raise ValueError(
                        "ACT attempt ID already belongs to different Discord content or authority"
                    )

                rows = db.execute(
                    """
                    SELECT chunk_index, content, content_digest
                    FROM discord_act_chunks
                    WHERE attempt_id=?
                    ORDER BY chunk_index
                    """,
                    (payload.attempt_id,),
                ).fetchall()
                if len(rows) != len(chunks) or any(
                    int(row["chunk_index"]) != index
                    or row["content"] != chunks[index]
                    or row["content_digest"] != chunk_digests[index]
                    for index, row in enumerate(rows)
                ):
                    raise ValueError("ACT attempt already has a different Discord chunk plan")
                db.rollback()
                return self.attempt(payload.attempt_id)

            db.execute(
                """
                INSERT INTO discord_act_attempts (
                    attempt_id, message_id, recipient_id, bot_user_id,
                    owner_user_id, channel_id, session_id,
                    binding_generation, content_digest, state,
                    receipt_id, last_error
                )
                VALUES (?,?,?,?,?,?,?,?,?,'prepared',NULL,NULL)
                """,
                (
                    payload.attempt_id,
                    payload.message_id,
                    payload.recipient_id,
                    str(binding.bot_user_id),
                    str(binding.owner_user_id),
                    str(binding.channel_id),
                    binding.session_id,
                    binding.generation,
                    content_digest,
                ),
            )
            db.executemany(
                """
                INSERT INTO discord_act_chunks (
                    attempt_id, chunk_index, content, content_digest,
                    state, platform_message_id, send_token, last_error
                )
                VALUES (?,?,?,?,'prepared',NULL,NULL,NULL)
                """,
                [
                    (
                        payload.attempt_id,
                        index,
                        chunk,
                        chunk_digests[index],
                    )
                    for index, chunk in enumerate(chunks)
                ],
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        attempt = self.attempt(payload.attempt_id)
        assert attempt is not None
        return attempt

    def chunks(self, attempt_id: str) -> tuple[DiscordActChunk, ...]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT attempt_id, chunk_index, content, state,
                       platform_message_id, send_token, last_error
                FROM discord_act_chunks
                WHERE attempt_id=?
                ORDER BY chunk_index
                """,
                (attempt_id,),
            ).fetchall()
        return tuple(
            DiscordActChunk(
                attempt_id=row["attempt_id"],
                chunk_index=int(row["chunk_index"]),
                content=row["content"],
                state=DiscordActChunkState(row["state"]),
                platform_message_id=(
                    int(row["platform_message_id"])
                    if row["platform_message_id"] is not None
                    else None
                ),
                send_in_progress=row["send_token"] is not None,
                last_error=row["last_error"],
            )
            for row in rows
        )

    def claim_chunk(
        self,
        *,
        attempt_id: str,
        chunk_index: int,
        send_token: str,
    ) -> bool:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT state, send_token
                FROM discord_act_chunks
                WHERE attempt_id=? AND chunk_index=?
                """,
                (attempt_id, chunk_index),
            ).fetchone()
            if row is None:
                raise KeyError("Discord ACT chunk does not exist")
            if row["state"] != DiscordActChunkState.PREPARED.value:
                db.rollback()
                return False
            if row["send_token"] is not None:
                db.rollback()
                return row["send_token"] == send_token
            db.execute(
                """
                UPDATE discord_act_chunks
                SET send_token=?, last_error=NULL
                WHERE attempt_id=? AND chunk_index=?
                  AND state='prepared' AND send_token IS NULL
                """,
                (send_token, attempt_id, chunk_index),
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def mark_sent(
        self,
        *,
        attempt_id: str,
        chunk_index: int,
        platform_message_id: int,
        send_token: str,
    ) -> None:
        if not _snowflake(platform_message_id):
            raise ValueError("platform_message_id must be a Discord snowflake")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT state, platform_message_id, send_token
                FROM discord_act_chunks
                WHERE attempt_id=? AND chunk_index=?
                """,
                (attempt_id, chunk_index),
            ).fetchone()
            if row is None:
                raise KeyError("Discord ACT chunk does not exist")
            if row["state"] == DiscordActChunkState.SENT.value:
                if row["platform_message_id"] != str(platform_message_id):
                    raise ValueError("Discord ACT chunk already has a different receipt")
                return
            if (
                row["state"] != DiscordActChunkState.PREPARED.value
                or row["send_token"] != send_token
            ):
                raise RuntimeError("Discord ACT chunk is not owned by this sender")
            db.execute(
                """
                UPDATE discord_act_chunks
                SET state='sent', platform_message_id=?,
                    send_token=NULL, last_error=NULL
                WHERE attempt_id=? AND chunk_index=? AND send_token=?
                """,
                (
                    str(platform_message_id),
                    attempt_id,
                    chunk_index,
                    send_token,
                ),
            )

    def mark_unknown(
        self,
        *,
        attempt_id: str,
        error_type: str,
        chunk_index: int | None = None,
        send_token: str | None = None,
    ) -> None:
        clean_error = error_type.strip()[:120]
        if not clean_error:
            raise ValueError("error_type required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if chunk_index is not None:
                if send_token is None:
                    raise ValueError("send_token required for a claimed chunk")
                db.execute(
                    """
                    UPDATE discord_act_chunks
                    SET state='outcome_unknown', send_token=NULL, last_error=?
                    WHERE attempt_id=? AND chunk_index=?
                      AND state='prepared' AND send_token=?
                    """,
                    (
                        clean_error,
                        attempt_id,
                        chunk_index,
                        send_token,
                    ),
                )
            db.execute(
                """
                UPDATE discord_act_attempts
                SET state='outcome_unknown', last_error=?
                WHERE attempt_id=? AND state='prepared'
                """,
                (clean_error, attempt_id),
            )

    def sent_count(self, attempt_id: str) -> int:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT COUNT(*) AS count
                FROM discord_act_chunks
                WHERE attempt_id=? AND state='sent'
                """,
                (attempt_id,),
            ).fetchone()
        assert row is not None
        return int(row["count"])

    def complete(self, attempt_id: str) -> str:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            attempt = db.execute(
                """
                SELECT state, receipt_id
                FROM discord_act_attempts
                WHERE attempt_id=?
                """,
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                raise KeyError("Discord ACT attempt does not exist")
            if attempt["state"] == "outcome_unknown":
                raise RuntimeError("Discord ACT attempt outcome is unknown")
            if attempt["state"] == "delivered":
                db.rollback()
                assert attempt["receipt_id"] is not None
                return attempt["receipt_id"]

            rows = db.execute(
                """
                SELECT state, platform_message_id
                FROM discord_act_chunks
                WHERE attempt_id=?
                ORDER BY chunk_index
                """,
                (attempt_id,),
            ).fetchall()
            if not rows or any(row["state"] != "sent" for row in rows):
                raise RuntimeError("Discord ACT attempt is not fully acknowledged")
            provider_ids = tuple(row["platform_message_id"] for row in rows)
            if any(value is None for value in provider_ids):
                raise RuntimeError("Discord ACT receipt evidence is incomplete")

            digest = sha256("|".join(provider_ids).encode("utf-8")).hexdigest()[:40]
            receipt_id = f"discord:{digest}"
            db.execute(
                """
                UPDATE discord_act_attempts
                SET state='delivered', receipt_id=?, last_error=NULL
                WHERE attempt_id=? AND state='prepared'
                """,
                (receipt_id, attempt_id),
            )
            db.commit()
            return receipt_id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def recover_interrupted(self) -> int:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            attempts = [
                row["attempt_id"]
                for row in db.execute(
                    """
                    SELECT DISTINCT c.attempt_id
                    FROM discord_act_chunks AS c
                    JOIN discord_act_attempts AS a
                      ON a.attempt_id=c.attempt_id
                    WHERE a.state='prepared'
                      AND (
                          (c.state='prepared' AND c.send_token IS NOT NULL)
                          OR c.state='sent'
                      )
                    """
                ).fetchall()
            ]
            if not attempts:
                db.rollback()
                return 0

            placeholders = ",".join("?" for _ in attempts)
            db.execute(
                f"""
                UPDATE discord_act_chunks
                SET state='outcome_unknown',
                    send_token=NULL,
                    last_error='ProcessRestartDuringSend'
                WHERE attempt_id IN ({placeholders})
                  AND state='prepared'
                  AND send_token IS NOT NULL
                """,
                attempts,
            )
            db.execute(
                f"""
                UPDATE discord_act_attempts
                SET state='outcome_unknown',
                    last_error='ProcessRestartDuringSend'
                WHERE attempt_id IN ({placeholders})
                  AND state='prepared'
                """,
                attempts,
            )
            db.commit()
            return len(attempts)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class DiscordActSafeSender:
    """Synchronous ACT sender over an explicitly supplied Discord transport."""

    CHANNEL = "discord_dm"

    def __init__(
        self,
        *,
        config: SingleUserDiscordConfig,
        bindings: DiscordBindingStore,
        deliveries: DiscordActDeliveryStore,
        session_id: str,
        recipient_id: str,
        send_chunk: Callable[[str], int],
    ) -> None:
        if not isinstance(config, SingleUserDiscordConfig):
            raise TypeError("SingleUserDiscordConfig required")
        if not isinstance(bindings, DiscordBindingStore):
            raise TypeError("DiscordBindingStore required")
        if not isinstance(deliveries, DiscordActDeliveryStore):
            raise TypeError("DiscordActDeliveryStore required")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id required")
        if not isinstance(recipient_id, str) or not recipient_id.strip():
            raise ValueError("recipient_id required")
        if not callable(send_chunk):
            raise TypeError("send_chunk must be callable")

        self.config = config
        self.bindings = bindings
        self.deliveries = deliveries
        self.session_id = session_id.strip()
        self.recipient_id = recipient_id.strip()
        self.send_chunk = send_chunk

    @staticmethod
    def _failed(error_type: str) -> SendResult:
        return SendResult(DeliveryOutcome.FAILED, error_type=error_type)

    @staticmethod
    def _unknown(error_type: str) -> SendResult:
        return SendResult(DeliveryOutcome.OUTCOME_UNKNOWN, error_type=error_type)

    def _current_binding(
        self,
        payload: DeliveryPayload,
    ) -> tuple[DiscordChannelBinding | None, str | None]:
        if not self.config.enabled:
            return None, "discord_disabled"
        if self.config.dm_channel_id is None:
            return None, "discord_channel_unpinned"
        if payload.recipient_id != self.recipient_id:
            return None, "discord_wrong_recipient"
        if payload.channel != self.CHANNEL:
            return None, "discord_wrong_channel"
        if payload.destination != str(self.config.dm_channel_id):
            return None, "discord_wrong_destination"

        binding = self.bindings.get(
            bot_user_id=self.config.bot_user_id,
            channel_id=self.config.dm_channel_id,
        )
        if binding is None:
            return None, "discord_unbound"
        if binding.state is BindingState.PAUSED:
            return None, "discord_paused"
        if binding.state is BindingState.REVOKED:
            return None, "discord_revoked"
        if binding.owner_user_id != self.config.owner_user_id:
            return None, "discord_wrong_owner"
        if binding.session_id != self.session_id:
            return None, "discord_session_mismatch"
        return binding, None

    def __call__(self, payload: DeliveryPayload) -> SendResult:
        if not isinstance(payload, DeliveryPayload):
            raise TypeError("DeliveryPayload required")

        existing = self.deliveries.attempt(payload.attempt_id)
        if existing is not None:
            expected_digest = sha256(payload.content.encode("utf-8")).hexdigest()
            if (
                existing.message_id != payload.message_id
                or existing.recipient_id != payload.recipient_id
                or existing.content_digest != expected_digest
                or existing.bot_user_id != self.config.bot_user_id
                or existing.owner_user_id != self.config.owner_user_id
                or existing.channel_id != self.config.dm_channel_id
                or existing.session_id != self.session_id
            ):
                raise ValueError(
                    "ACT attempt ID already belongs to different Discord content or authority"
                )
            if existing.state == "delivered":
                assert existing.receipt_id is not None
                return SendResult(
                    DeliveryOutcome.DELIVERED,
                    receipt_id=existing.receipt_id,
                )
            if existing.state == "outcome_unknown":
                return self._unknown(
                    existing.last_error or "discord_outcome_unknown"
                )

        binding, denial = self._current_binding(payload)
        if binding is None:
            return self._failed(denial or "discord_denied")

        attempt = (
            existing
            if existing is not None
            else self.deliveries.prepare(payload, binding=binding)
        )
        if attempt.state == "delivered":
            assert attempt.receipt_id is not None
            return SendResult(
                DeliveryOutcome.DELIVERED,
                receipt_id=attempt.receipt_id,
            )
        if attempt.state == "outcome_unknown":
            return self._unknown(
                attempt.last_error or "discord_outcome_unknown"
            )

        for chunk in self.deliveries.chunks(payload.attempt_id):
            if chunk.state is DiscordActChunkState.SENT:
                continue
            if chunk.state is DiscordActChunkState.OUTCOME_UNKNOWN:
                self.deliveries.mark_unknown(
                    attempt_id=payload.attempt_id,
                    error_type="discord_chunk_outcome_unknown",
                )
                return self._unknown("discord_chunk_outcome_unknown")

            current, denial = self._current_binding(payload)
            if (
                current is None
                or current.generation != attempt.binding_generation
            ):
                error = denial or "discord_stale_binding"
                if self.deliveries.sent_count(payload.attempt_id):
                    self.deliveries.mark_unknown(
                        attempt_id=payload.attempt_id,
                        error_type=error,
                    )
                    return self._unknown(error)
                return self._failed(error)

            send_token = str(uuid4())
            if not self.deliveries.claim_chunk(
                attempt_id=payload.attempt_id,
                chunk_index=chunk.chunk_index,
                send_token=send_token,
            ):
                refreshed = self.deliveries.chunks(payload.attempt_id)
                state = refreshed[chunk.chunk_index].state
                if state is DiscordActChunkState.SENT:
                    continue
                return self._unknown("discord_chunk_claim_conflict")

            try:
                platform_message_id = self.send_chunk(chunk.content)
                if not _snowflake(platform_message_id):
                    raise ValueError("Discord transport returned invalid message ID")
                self.deliveries.mark_sent(
                    attempt_id=payload.attempt_id,
                    chunk_index=chunk.chunk_index,
                    platform_message_id=platform_message_id,
                    send_token=send_token,
                )
            except Exception as exc:
                error = type(exc).__name__
                self.deliveries.mark_unknown(
                    attempt_id=payload.attempt_id,
                    chunk_index=chunk.chunk_index,
                    send_token=send_token,
                    error_type=error,
                )
                return self._unknown(error)

        receipt_id = self.deliveries.complete(payload.attempt_id)
        return SendResult(
            DeliveryOutcome.DELIVERED,
            receipt_id=receipt_id,
        )
