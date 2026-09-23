"""Durable SQLite inbox for accepted Discord text events.

The store is intentionally transport-agnostic. It records accepted owner DMs,
survives process restarts, and provides deterministic duplicate/conflict
handling before any conversation response is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
import sqlite3

from sofia.discord.inbound import InboundScreen


class InboxAcceptResult(str, Enum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


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


class DiscordInboxStore:
    """Crash-safe inbox backed by the configured Sofía SQLite state file."""

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
                    bot_user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    author_user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    PRIMARY KEY (bot_user_id, channel_id, message_id)
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
                (bot_user_id, event.channel_id, event.message_id),
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
                    bot_user_id,
                    event.channel_id,
                    event.message_id,
                    author_user_id,
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
                (bot_user_id, channel_id, message_id),
            ).fetchone()

        if row is None:
            return None

        return DiscordInboxRecord(
            bot_user_id=row["bot_user_id"],
            channel_id=row["channel_id"],
            message_id=row["message_id"],
            author_user_id=row["author_user_id"],
            content=row["content"],
            payload_digest=row["payload_digest"],
            received_at=datetime.fromisoformat(row["received_at"]),
            state=row["state"],
        )

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM discord_inbox"
            ).fetchone()
        assert row is not None
        return int(row["count"])
