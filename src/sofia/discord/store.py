"""Durable SQLite state for accepted Discord text events and staged replies.

The store is transport-agnostic. It records accepted owner DMs, survives process
restarts, prevents duplicate logical responses, and stages outbound text without
performing any Discord network operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.discord.inbound import InboundScreen


class InboxAcceptResult(str, Enum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


class InboxClaimResult(str, Enum):
    CLAIMED = "claimed"
    NOT_FOUND = "not_found"
    IN_PROGRESS = "in_progress"
    RESPONSE_PREPARED = "response_prepared"
    OUTCOME_UNKNOWN = "outcome_unknown"
    NOT_READY = "not_ready"


@dataclass(frozen=True, slots=True)
class DiscordInboxRecord:
    bot_user_id: int
    channel_id: int
    message_id: int
    author_user_id: int
    content: str
    payload_digest: str
    received_at: datetime
    state: str


@dataclass(frozen=True, slots=True)
class DiscordOutboxRecord:
    response_id: str
    bot_user_id: int
    channel_id: int
    trigger_message_id: int
    session_id: str
    content: str
    created_at: datetime
    state: str
    platform_message_id: int | None


class DiscordInboxStore:
    """Crash-safe channel state backed by the configured Sofía SQLite file.

    Discord snowflakes are unsigned 64-bit identifiers. SQLite INTEGER is
    signed 64-bit, so snowflakes are persisted as canonical decimal TEXT.
    """

    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self._database_path),
            timeout=5.0,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS discord_inbox (
                    bot_user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    author_user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    processing_token TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    PRIMARY KEY (bot_user_id, channel_id, message_id)
                )
                """
            )
            existing = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(discord_inbox)"
                ).fetchall()
            }
            additions = {
                "processing_token": "TEXT",
                "attempt_count": "INTEGER NOT NULL DEFAULT 0",
                "last_error": "TEXT",
            }
            for column, definition in additions.items():
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE discord_inbox "
                        f"ADD COLUMN {column} {definition}"
                    )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS discord_outbox (
                    response_id TEXT PRIMARY KEY,
                    bot_user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    trigger_message_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    platform_message_id TEXT,
                    last_error TEXT,
                    UNIQUE (
                        bot_user_id,
                        channel_id,
                        trigger_message_id
                    )
                )
                """
            )

    @staticmethod
    def _digest(screened: InboundScreen) -> str:
        event = screened.event
        if event is None:
            raise ValueError("accepted inbound screen is required")
        author = event.facts.author_user_id
        recipient = event.facts.recipient_user_id
        if type(author) is not int or type(recipient) is not int:
            raise ValueError("accepted event is missing canonical Discord IDs")
        payload = (
            f"{recipient}\n{event.channel_id}\n{event.message_id}\n{author}\n"
            f"{event.attachment_count}\n"
        ).encode("utf-8") + event.content.encode("utf-8")
        return sha256(payload).hexdigest()

    @staticmethod
    def _key(
        bot_user_id: int,
        channel_id: int,
        message_id: int,
    ) -> tuple[str, str, str]:
        values = (bot_user_id, channel_id, message_id)
        if any(type(value) is not int or not 0 < value < (1 << 64) for value in values):
            raise ValueError("Discord IDs must be positive unsigned 64-bit integers")
        return tuple(str(value) for value in values)

    def accept(self, screened: InboundScreen) -> InboxAcceptResult:
        if not isinstance(screened, InboundScreen) or not screened.accepted:
            raise ValueError("an accepted inbound screen is required")

        event = screened.event
        assert event is not None
        bot_user_id = event.facts.recipient_user_id
        author_user_id = event.facts.author_user_id
        if type(bot_user_id) is not int or type(author_user_id) is not int:
            raise ValueError("accepted event is missing canonical Discord IDs")

        digest = self._digest(screened)
        received_at = datetime.now(timezone.utc).isoformat()
        key = self._key(bot_user_id, event.channel_id, event.message_id)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT payload_digest
                FROM discord_inbox
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                """,
                key,
            ).fetchone()

            if row is not None:
                connection.rollback()
                return (
                    InboxAcceptResult.DUPLICATE
                    if row["payload_digest"] == digest
                    else InboxAcceptResult.CONFLICT
                )

            connection.execute(
                """
                INSERT INTO discord_inbox (
                    bot_user_id,
                    channel_id,
                    message_id,
                    author_user_id,
                    content,
                    payload_digest,
                    received_at,
                    state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    *key,
                    str(author_user_id),
                    event.content,
                    digest,
                    received_at,
                    "received",
                ),
            )
            connection.commit()
            return InboxAcceptResult.INSERTED
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        message_id: int,
    ) -> DiscordInboxRecord | None:
        key = self._key(bot_user_id, channel_id, message_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    bot_user_id,
                    channel_id,
                    message_id,
                    author_user_id,
                    content,
                    payload_digest,
                    received_at,
                    state
                FROM discord_inbox
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                """,
                key,
            ).fetchone()

        if row is None:
            return None

        return DiscordInboxRecord(
            bot_user_id=int(row["bot_user_id"]),
            channel_id=int(row["channel_id"]),
            message_id=int(row["message_id"]),
            author_user_id=int(row["author_user_id"]),
            content=row["content"],
            payload_digest=row["payload_digest"],
            received_at=datetime.fromisoformat(row["received_at"]),
            state=row["state"],
        )

    def claim_for_processing(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        message_id: int,
        processing_token: str,
    ) -> InboxClaimResult:
        if not isinstance(processing_token, str) or not processing_token.strip():
            raise ValueError("processing_token must be a non-empty string")
        token = processing_token.strip()
        key = self._key(bot_user_id, channel_id, message_id)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT state, processing_token
                FROM discord_inbox
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                """,
                key,
            ).fetchone()

            if row is None:
                connection.rollback()
                return InboxClaimResult.NOT_FOUND

            state = row["state"]
            old_token = row["processing_token"]
            if state == "received":
                connection.execute(
                    """
                    UPDATE discord_inbox
                    SET
                        state = 'processing',
                        processing_token = ?,
                        attempt_count = attempt_count + 1,
                        last_error = NULL
                    WHERE bot_user_id = ?
                      AND channel_id = ?
                      AND message_id = ?
                    """,
                    (token, *key),
                )
                connection.commit()
                return InboxClaimResult.CLAIMED

            connection.rollback()
            if state == "processing":
                return (
                    InboxClaimResult.CLAIMED
                    if old_token == token
                    else InboxClaimResult.IN_PROGRESS
                )
            if state == "response_prepared":
                return InboxClaimResult.RESPONSE_PREPARED
            if state == "outcome_unknown":
                return InboxClaimResult.OUTCOME_UNKNOWN
            return InboxClaimResult.NOT_READY
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def prepare_outbox(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        message_id: int,
        processing_token: str,
        session_id: str,
        content: str,
    ) -> DiscordOutboxRecord:
        if not isinstance(processing_token, str) or not processing_token.strip():
            raise ValueError("processing_token must be a non-empty string")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("outbox content must be a non-empty string")

        token = processing_token.strip()
        clean_session_id = session_id.strip()
        clean_content = content.strip()
        key = self._key(bot_user_id, channel_id, message_id)
        created_at = datetime.now(timezone.utc)
        response_id = str(uuid4())

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT state, processing_token
                FROM discord_inbox
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                """,
                key,
            ).fetchone()
            if row is None:
                raise KeyError("Discord inbox message does not exist")
            if row["state"] != "processing" or row["processing_token"] != token:
                raise RuntimeError("Discord inbox message is not owned by this processor")

            connection.execute(
                """
                INSERT INTO discord_outbox (
                    response_id,
                    bot_user_id,
                    channel_id,
                    trigger_message_id,
                    session_id,
                    content,
                    created_at,
                    state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'prepared')
                """,
                (
                    response_id,
                    key[0],
                    key[1],
                    key[2],
                    clean_session_id,
                    clean_content,
                    created_at.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE discord_inbox
                SET
                    state = 'response_prepared',
                    processing_token = NULL,
                    last_error = NULL
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                """,
                key,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return DiscordOutboxRecord(
            response_id=response_id,
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            trigger_message_id=message_id,
            session_id=clean_session_id,
            content=clean_content,
            created_at=created_at,
            state="prepared",
            platform_message_id=None,
        )

    def mark_outcome_unknown(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        message_id: int,
        processing_token: str,
        error_kind: str,
    ) -> bool:
        if not isinstance(processing_token, str) or not processing_token.strip():
            raise ValueError("processing_token must be a non-empty string")
        if not isinstance(error_kind, str) or not error_kind.strip():
            raise ValueError("error_kind must be a non-empty string")
        key = self._key(bot_user_id, channel_id, message_id)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE discord_inbox
                SET
                    state = 'outcome_unknown',
                    processing_token = NULL,
                    last_error = ?
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND message_id = ?
                  AND state = 'processing'
                  AND processing_token = ?
                """,
                (
                    error_kind.strip()[:128],
                    *key,
                    processing_token.strip(),
                ),
            )
            connection.commit()
            return cursor.rowcount == 1
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_outbox_for_inbox(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        message_id: int,
    ) -> DiscordOutboxRecord | None:
        key = self._key(bot_user_id, channel_id, message_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    response_id,
                    bot_user_id,
                    channel_id,
                    trigger_message_id,
                    session_id,
                    content,
                    created_at,
                    state,
                    platform_message_id
                FROM discord_outbox
                WHERE bot_user_id = ?
                  AND channel_id = ?
                  AND trigger_message_id = ?
                """,
                key,
            ).fetchone()

        if row is None:
            return None

        platform_message_id = row["platform_message_id"]
        return DiscordOutboxRecord(
            response_id=row["response_id"],
            bot_user_id=int(row["bot_user_id"]),
            channel_id=int(row["channel_id"]),
            trigger_message_id=int(row["trigger_message_id"]),
            session_id=row["session_id"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            state=row["state"],
            platform_message_id=(
                int(platform_message_id)
                if platform_message_id is not None
                else None
            ),
        )

    def recover_interrupted_processing(self) -> int:
        """Quarantine generation claims left behind by a terminated process.

        A hard stop can occur after conversation state changed but before the
        bridge staged an outbox row. Retrying automatically could create a
        second logical response, so restart recovery is deliberately
        conservative.
        """
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE discord_inbox
                SET state = 'outcome_unknown',
                    processing_token = NULL,
                    last_error = 'ProcessRestartDuringGeneration'
                WHERE state = 'processing'
                """
            )
            connection.commit()
            return int(cursor.rowcount)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_outbox(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        states: tuple[str, ...] = ("prepared",),
    ) -> tuple[DiscordOutboxRecord, ...]:
        """List durable responses for one exact Discord DM destination."""
        if type(bot_user_id) is not int or not 0 < bot_user_id < (1 << 64):
            raise ValueError("bot_user_id must be a Discord snowflake")
        if type(channel_id) is not int or not 0 < channel_id < (1 << 64):
            raise ValueError("channel_id must be a Discord snowflake")
        allowed = {"prepared", "sent"}
        if (
            not isinstance(states, tuple)
            or not states
            or any(state not in allowed for state in states)
        ):
            raise ValueError("states must be a non-empty tuple of known outbox states")

        placeholders = ", ".join("?" for _ in states)
        query = f"""
            SELECT
                response_id,
                bot_user_id,
                channel_id,
                trigger_message_id,
                session_id,
                content,
                created_at,
                state,
                platform_message_id
            FROM discord_outbox
            WHERE bot_user_id = ?
              AND channel_id = ?
              AND state IN ({placeholders})
            ORDER BY created_at, response_id
        """
        params = (str(bot_user_id), str(channel_id), *states)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return tuple(
            DiscordOutboxRecord(
                response_id=row["response_id"],
                bot_user_id=int(row["bot_user_id"]),
                channel_id=int(row["channel_id"]),
                trigger_message_id=int(row["trigger_message_id"]),
                session_id=row["session_id"],
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
                state=row["state"],
                platform_message_id=(
                    int(row["platform_message_id"])
                    if row["platform_message_id"] is not None
                    else None
                ),
            )
            for row in rows
        )

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM discord_inbox"
            ).fetchone()
        assert row is not None
        return int(row["count"])
