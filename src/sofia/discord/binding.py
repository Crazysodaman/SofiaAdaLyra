"""Durable Discord DM-to-conversation binding and outbound snapshots.

Bindings are supervised host state, not inferred from message text, usernames,
LLM output, or Discord display names. Any pause, resume, revoke, or rebind
increments a generation so replies staged under older authority become stale.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import sqlite3

from sofia.discord.access import _snowflake
from sofia.discord.store import DiscordOutboxRecord


class BindingState(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class DiscordChannelBinding:
    bot_user_id: int
    owner_user_id: int
    channel_id: int
    session_id: str
    state: BindingState
    generation: int
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DiscordOutboundBinding:
    response_id: str
    bot_user_id: int
    owner_user_id: int
    channel_id: int
    session_id: str
    binding_generation: int
    created_at: datetime


def _session_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("session_id must be a string")
    clean = value.strip()
    if not clean or len(clean) > 200:
        raise ValueError("session_id must be 1 through 200 characters")
    return clean


class DiscordBindingStore:
    """Persist one supervised owner DM binding and immutable reply snapshots."""

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
                CREATE TABLE IF NOT EXISTS discord_channel_bindings (
                    bot_user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    state TEXT NOT NULL
                        CHECK (state IN ('active', 'paused', 'revoked')),
                    generation INTEGER NOT NULL CHECK (generation > 0),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bot_user_id, channel_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS discord_outbound_bindings (
                    response_id TEXT PRIMARY KEY,
                    bot_user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    owner_user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    binding_generation INTEGER NOT NULL
                        CHECK (binding_generation > 0),
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _ids(
        bot_user_id: int,
        owner_user_id: int,
        channel_id: int,
    ) -> tuple[str, str, str]:
        values = (bot_user_id, owner_user_id, channel_id)
        if any(not _snowflake(value) for value in values):
            raise ValueError("Discord IDs must be positive unsigned 64-bit integers")
        if bot_user_id == owner_user_id:
            raise ValueError("bot_user_id and owner_user_id must differ")
        return tuple(str(value) for value in values)

    def bind(
        self,
        *,
        bot_user_id: int,
        owner_user_id: int,
        channel_id: int,
        session_id: str,
    ) -> DiscordChannelBinding:
        bot, owner, channel = self._ids(
            bot_user_id, owner_user_id, channel_id
        )
        session = _session_id(session_id)
        now = datetime.now(timezone.utc)

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT owner_user_id, generation
                FROM discord_channel_bindings
                WHERE bot_user_id = ? AND channel_id = ?
                """,
                (bot, channel),
            ).fetchone()
            if row is not None and row["owner_user_id"] != owner:
                raise ValueError(
                    "existing Discord channel binding belongs to a different owner"
                )
            generation = int(row["generation"]) + 1 if row is not None else 1
            connection.execute(
                """
                INSERT INTO discord_channel_bindings (
                    bot_user_id,
                    channel_id,
                    owner_user_id,
                    session_id,
                    state,
                    generation,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                ON CONFLICT(bot_user_id, channel_id) DO UPDATE SET
                    owner_user_id = excluded.owner_user_id,
                    session_id = excluded.session_id,
                    state = 'active',
                    generation = excluded.generation,
                    updated_at = excluded.updated_at
                """,
                (
                    bot,
                    channel,
                    owner,
                    session,
                    generation,
                    now.isoformat(),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return DiscordChannelBinding(
            bot_user_id=bot_user_id,
            owner_user_id=owner_user_id,
            channel_id=channel_id,
            session_id=session,
            state=BindingState.ACTIVE,
            generation=generation,
            updated_at=now,
        )

    def get(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
    ) -> DiscordChannelBinding | None:
        if not _snowflake(bot_user_id) or not _snowflake(channel_id):
            raise ValueError("Discord IDs must be positive unsigned 64-bit integers")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    bot_user_id,
                    channel_id,
                    owner_user_id,
                    session_id,
                    state,
                    generation,
                    updated_at
                FROM discord_channel_bindings
                WHERE bot_user_id = ? AND channel_id = ?
                """,
                (str(bot_user_id), str(channel_id)),
            ).fetchone()
        if row is None:
            return None
        return DiscordChannelBinding(
            bot_user_id=int(row["bot_user_id"]),
            owner_user_id=int(row["owner_user_id"]),
            channel_id=int(row["channel_id"]),
            session_id=row["session_id"],
            state=BindingState(row["state"]),
            generation=int(row["generation"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def pause(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
    ) -> DiscordChannelBinding:
        return self._transition(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            target=BindingState.PAUSED,
        )

    def resume(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
    ) -> DiscordChannelBinding:
        return self._transition(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            target=BindingState.ACTIVE,
        )

    def revoke(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
    ) -> DiscordChannelBinding:
        return self._transition(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            target=BindingState.REVOKED,
        )

    def _transition(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        target: BindingState,
    ) -> DiscordChannelBinding:
        if not _snowflake(bot_user_id) or not _snowflake(channel_id):
            raise ValueError("Discord IDs must be positive unsigned 64-bit integers")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT owner_user_id, session_id, state, generation, updated_at
                FROM discord_channel_bindings
                WHERE bot_user_id = ? AND channel_id = ?
                """,
                (str(bot_user_id), str(channel_id)),
            ).fetchone()
            if row is None:
                raise KeyError("Discord channel binding does not exist")

            current = BindingState(row["state"])
            if current is BindingState.REVOKED and target is not BindingState.REVOKED:
                raise RuntimeError(
                    "revoked Discord binding requires supervised re-binding"
                )
            if target is BindingState.ACTIVE and current is not BindingState.PAUSED:
                if current is BindingState.ACTIVE:
                    connection.rollback()
                    return self.get(
                        bot_user_id=bot_user_id,
                        channel_id=channel_id,
                    )
                raise RuntimeError("Discord binding cannot be resumed from this state")
            if target is BindingState.PAUSED and current is not BindingState.ACTIVE:
                if current is BindingState.PAUSED:
                    connection.rollback()
                    return self.get(
                        bot_user_id=bot_user_id,
                        channel_id=channel_id,
                    )
                raise RuntimeError("Discord binding cannot be paused from this state")
            if target is BindingState.REVOKED and current is BindingState.REVOKED:
                connection.rollback()
                return self.get(
                    bot_user_id=bot_user_id,
                    channel_id=channel_id,
                )

            generation = int(row["generation"]) + 1
            now = datetime.now(timezone.utc)
            connection.execute(
                """
                UPDATE discord_channel_bindings
                SET state = ?, generation = ?, updated_at = ?
                WHERE bot_user_id = ? AND channel_id = ?
                """,
                (
                    target.value,
                    generation,
                    now.isoformat(),
                    str(bot_user_id),
                    str(channel_id),
                ),
            )
            connection.commit()
            owner_user_id = int(row["owner_user_id"])
            session_id = row["session_id"]
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return DiscordChannelBinding(
            bot_user_id=bot_user_id,
            owner_user_id=owner_user_id,
            channel_id=channel_id,
            session_id=session_id,
            state=target,
            generation=generation,
            updated_at=now,
        )

    def attach_outbox(
        self,
        outbox: DiscordOutboxRecord,
        *,
        expected_generation: int,
    ) -> bool:
        """Attach immutable authority only if the binding is still unchanged."""
        if not isinstance(outbox, DiscordOutboxRecord):
            raise TypeError("outbox must be DiscordOutboxRecord")
        if type(expected_generation) is not int or expected_generation < 1:
            raise ValueError("expected_generation must be a positive integer")

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            binding = connection.execute(
                """
                SELECT owner_user_id, session_id, state, generation
                FROM discord_channel_bindings
                WHERE bot_user_id = ? AND channel_id = ?
                """,
                (str(outbox.bot_user_id), str(outbox.channel_id)),
            ).fetchone()
            if (
                binding is None
                or binding["state"] != BindingState.ACTIVE.value
                or int(binding["generation"]) != expected_generation
                or binding["session_id"] != outbox.session_id
            ):
                connection.rollback()
                return False

            existing = connection.execute(
                """
                SELECT
                    bot_user_id,
                    channel_id,
                    owner_user_id,
                    session_id,
                    binding_generation
                FROM discord_outbound_bindings
                WHERE response_id = ?
                """,
                (outbox.response_id,),
            ).fetchone()
            expected = (
                str(outbox.bot_user_id),
                str(outbox.channel_id),
                binding["owner_user_id"],
                outbox.session_id,
                expected_generation,
            )
            if existing is not None:
                actual = (
                    existing["bot_user_id"],
                    existing["channel_id"],
                    existing["owner_user_id"],
                    existing["session_id"],
                    int(existing["binding_generation"]),
                )
                connection.rollback()
                if actual != expected:
                    raise ValueError(
                        "response_id already has different Discord authority"
                    )
                return True

            connection.execute(
                """
                INSERT INTO discord_outbound_bindings (
                    response_id,
                    bot_user_id,
                    channel_id,
                    owner_user_id,
                    session_id,
                    binding_generation,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outbox.response_id,
                    expected[0],
                    expected[1],
                    expected[2],
                    expected[3],
                    expected[4],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def outbox_binding(
        self,
        response_id: str,
    ) -> DiscordOutboundBinding | None:
        if not isinstance(response_id, str) or not response_id.strip():
            raise ValueError("response_id must be a non-empty string")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    response_id,
                    bot_user_id,
                    channel_id,
                    owner_user_id,
                    session_id,
                    binding_generation,
                    created_at
                FROM discord_outbound_bindings
                WHERE response_id = ?
                """,
                (response_id.strip(),),
            ).fetchone()
        if row is None:
            return None
        return DiscordOutboundBinding(
            response_id=row["response_id"],
            bot_user_id=int(row["bot_user_id"]),
            owner_user_id=int(row["owner_user_id"]),
            channel_id=int(row["channel_id"]),
            session_id=row["session_id"],
            binding_generation=int(row["binding_generation"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
