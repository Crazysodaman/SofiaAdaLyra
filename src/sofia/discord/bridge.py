"""Offline bridge from durable Discord inbox rows to Sofía conversation output.

The bridge stages a response in the durable outbox. It never contacts Discord.
A supervised channel/session binding must be active before generation, and the
same binding generation must still be active when outbound authority is attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import uuid4

from sofia.discord.binding import BindingState, DiscordBindingStore
from sofia.discord.store import (
    DiscordInboxStore,
    DiscordOutboxRecord,
    InboxClaimResult,
)


class ConversationResponder(Protocol):
    @property
    def session_id(self) -> str | None: ...

    def respond(self, content: str): ...


class BridgeDisposition(str, Enum):
    PREPARED = "prepared"
    ALREADY_PREPARED = "already_prepared"
    IN_PROGRESS = "in_progress"
    OUTCOME_UNKNOWN = "outcome_unknown"
    NOT_FOUND = "not_found"
    NOT_READY = "not_ready"
    UNBOUND = "unbound"
    PAUSED = "paused"
    REVOKED = "revoked"
    SESSION_MISMATCH = "session_mismatch"
    WRONG_OWNER = "wrong_owner"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class BridgeResult:
    disposition: BridgeDisposition
    outbox: DiscordOutboxRecord | None = None


class DiscordBridgeError(RuntimeError):
    """A conversation result cannot be safely classified for automatic retry."""


class DiscordConversationBridge:
    """Create at most one staged logical response per durable inbox identity."""

    def __init__(
        self,
        *,
        store: DiscordInboxStore,
        bindings: DiscordBindingStore,
        conversation: ConversationResponder,
    ) -> None:
        if not isinstance(store, DiscordInboxStore):
            raise TypeError("store must be DiscordInboxStore")
        if not isinstance(bindings, DiscordBindingStore):
            raise TypeError("bindings must be DiscordBindingStore")
        if not hasattr(conversation, "respond") or not hasattr(conversation, "session_id"):
            raise TypeError("conversation must expose session_id and respond(content)")
        self._store = store
        self._bindings = bindings
        self._conversation = conversation

    def process(
        self,
        *,
        bot_user_id: int,
        channel_id: int,
        message_id: int,
    ) -> BridgeResult:
        existing = self._store.get_outbox_for_inbox(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            message_id=message_id,
        )
        if existing is not None:
            if self._bindings.outbox_binding(existing.response_id) is None:
                return BridgeResult(BridgeDisposition.BLOCKED, existing)
            return BridgeResult(
                BridgeDisposition.ALREADY_PREPARED,
                existing,
            )

        session_id = self._conversation.session_id
        if not isinstance(session_id, str) or not session_id.strip():
            raise RuntimeError(
                "Discord conversation bridge requires an active conversation session"
            )

        binding = self._bindings.get(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
        )
        if binding is None:
            return BridgeResult(BridgeDisposition.UNBOUND)
        if binding.state is BindingState.PAUSED:
            return BridgeResult(BridgeDisposition.PAUSED)
        if binding.state is BindingState.REVOKED:
            return BridgeResult(BridgeDisposition.REVOKED)
        if binding.session_id != session_id:
            return BridgeResult(BridgeDisposition.SESSION_MISMATCH)

        inbound = self._store.get(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            message_id=message_id,
        )
        if inbound is None:
            return BridgeResult(BridgeDisposition.NOT_FOUND)
        if inbound.author_user_id != binding.owner_user_id:
            return BridgeResult(BridgeDisposition.WRONG_OWNER)

        processing_token = str(uuid4())
        claim = self._store.claim_for_processing(
            bot_user_id=bot_user_id,
            channel_id=channel_id,
            message_id=message_id,
            processing_token=processing_token,
        )
        if claim is not InboxClaimResult.CLAIMED:
            disposition = {
                InboxClaimResult.NOT_FOUND: BridgeDisposition.NOT_FOUND,
                InboxClaimResult.IN_PROGRESS: BridgeDisposition.IN_PROGRESS,
                InboxClaimResult.RESPONSE_PREPARED: BridgeDisposition.ALREADY_PREPARED,
                InboxClaimResult.OUTCOME_UNKNOWN: BridgeDisposition.OUTCOME_UNKNOWN,
                InboxClaimResult.NOT_READY: BridgeDisposition.NOT_READY,
            }[claim]
            return BridgeResult(disposition)

        try:
            response = self._conversation.respond(inbound.content)
            content = getattr(response, "content", None)
            if not isinstance(content, str) or not content.strip():
                raise ValueError("conversation response content is empty")

            outbox = self._store.prepare_outbox(
                bot_user_id=bot_user_id,
                channel_id=channel_id,
                message_id=message_id,
                processing_token=processing_token,
                session_id=session_id,
                content=content,
            )
        except Exception as exc:
            try:
                self._store.mark_outcome_unknown(
                    bot_user_id=bot_user_id,
                    channel_id=channel_id,
                    message_id=message_id,
                    processing_token=processing_token,
                    error_kind=type(exc).__name__,
                )
            except Exception:
                pass
            raise DiscordBridgeError(
                "Discord conversation response outcome is unknown; automatic retry is blocked"
            ) from exc

        if not self._bindings.attach_outbox(
            outbox,
            expected_generation=binding.generation,
        ):
            return BridgeResult(BridgeDisposition.BLOCKED, outbox)

        return BridgeResult(BridgeDisposition.PREPARED, outbox)
