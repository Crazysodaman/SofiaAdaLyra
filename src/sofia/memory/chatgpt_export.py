"""Parse a full ChatGPT data export as memory source evidence.

A full conversation export is not itself a durable-memory list. This module
extracts only user/assistant visible text from the active conversation branch,
honors ChatGPT's do-not-remember flag, and never promotes imported material.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from typing import Any
from zipfile import BadZipFile, ZipFile


_VISIBLE_CONTENT_TYPES = frozenset({"text", "multimodal_text"})
_VISIBLE_ROLES = frozenset({"user", "assistant"})


def _aware_utc(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _text_content(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if not isinstance(content, dict):
        return None
    if content.get("content_type") not in _VISIBLE_CONTENT_TYPES:
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    text_parts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            value = part.strip()
        elif isinstance(part, dict):
            raw = part.get("text")
            value = raw.strip() if isinstance(raw, str) else ""
        else:
            value = ""
        if value:
            text_parts.append(value)
    if not text_parts:
        return None
    return "\n".join(text_parts)


@dataclass(frozen=True, slots=True)
class ChatGPTExportMessage:
    source_id: str
    conversation_id: str
    message_id: str
    role: str
    content: str
    source_created_at: datetime | None
    position: int


@dataclass(frozen=True, slots=True)
class ChatGPTExportConversation:
    conversation_id: str
    title: str | None
    source_created_at: datetime | None
    source_updated_at: datetime | None
    memory_scope: str | None
    is_archived: bool
    messages: tuple[ChatGPTExportMessage, ...]


@dataclass(frozen=True, slots=True)
class ChatGPTExportBatch:
    source_digest: str
    observed_at: datetime
    conversations: tuple[ChatGPTExportConversation, ...]
    skipped_do_not_remember: int = 0

    @property
    def message_count(self) -> int:
        return sum(len(item.messages) for item in self.conversations)


def _active_node_ids(conversation: dict[str, Any]) -> tuple[str, ...]:
    mapping = conversation.get("mapping")
    current = conversation.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(current, str):
        return ()
    ordered: list[str] = []
    seen: set[str] = set()
    node_id: str | None = current
    while node_id is not None:
        if node_id in seen:
            raise ValueError("ChatGPT conversation mapping contains a cycle")
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break
        ordered.append(node_id)
        parent = node.get("parent")
        node_id = parent if isinstance(parent, str) and parent else None
    ordered.reverse()
    return tuple(ordered)


def _conversation(
    raw: Any,
    *,
    digest: str,
) -> ChatGPTExportConversation | None:
    if not isinstance(raw, dict):
        raise ValueError("ChatGPT export conversations must be objects")
    if raw.get("is_do_not_remember") is True:
        return None

    conversation_id = raw.get("conversation_id") or raw.get("id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValueError("ChatGPT export conversation is missing its ID")
    conversation_id = conversation_id.strip()

    mapping = raw.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("ChatGPT export conversation mapping is missing")

    messages: list[ChatGPTExportMessage] = []
    for position, node_id in enumerate(_active_node_ids(raw)):
        node = mapping.get(node_id)
        message = node.get("message") if isinstance(node, dict) else None
        if not isinstance(message, dict):
            continue
        author = message.get("author")
        role = author.get("role") if isinstance(author, dict) else None
        if role not in _VISIBLE_ROLES:
            continue
        content = _text_content(message)
        if content is None:
            continue
        message_id = message.get("id") or node_id
        if not isinstance(message_id, str) or not message_id.strip():
            continue
        message_id = message_id.strip()
        messages.append(
            ChatGPTExportMessage(
                source_id=(
                    f"chatgpt-export:{digest}:{conversation_id}:{message_id}"
                ),
                conversation_id=conversation_id,
                message_id=message_id,
                role=role,
                content=content,
                source_created_at=_aware_utc(message.get("create_time")),
                position=position,
            )
        )

    title = raw.get("title")
    return ChatGPTExportConversation(
        conversation_id=conversation_id,
        title=title.strip() if isinstance(title, str) and title.strip() else None,
        source_created_at=_aware_utc(raw.get("create_time")),
        source_updated_at=_aware_utc(raw.get("update_time")),
        memory_scope=(
            raw.get("memory_scope").strip()
            if isinstance(raw.get("memory_scope"), str)
            and raw.get("memory_scope").strip()
            else None
        ),
        is_archived=bool(raw.get("is_archived", False)),
        messages=tuple(messages),
    )


def parse_chatgpt_export_archive(
    payload: bytes,
    *,
    observed_at: datetime | None = None,
) -> ChatGPTExportBatch:
    """Parse OpenAI's full export ZIP without treating chat history as memory."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("payload must be nonempty bytes")
    when = observed_at or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    digest = hashlib.sha256(payload).hexdigest()
    try:
        archive = ZipFile(BytesIO(payload))
    except BadZipFile as exc:
        raise ValueError("input is not a valid ChatGPT export ZIP") from exc

    with archive:
        names = set(archive.namelist())
        if "export_manifest.json" not in names:
            raise ValueError("ChatGPT export manifest is missing")
        conversation_files = sorted(
            name for name in names
            if name.startswith("conversations-") and name.endswith(".json")
        )
        if not conversation_files:
            raise ValueError("ChatGPT export contains no conversation files")

        conversations: list[ChatGPTExportConversation] = []
        skipped = 0
        seen_ids: set[str] = set()
        for name in conversation_files:
            decoded = json.loads(archive.read(name).decode("utf-8-sig"))
            if not isinstance(decoded, list):
                raise ValueError(f"{name} must contain a JSON array")
            for raw in decoded:
                if isinstance(raw, dict) and raw.get("is_do_not_remember") is True:
                    skipped += 1
                    continue
                item = _conversation(raw, digest=digest)
                if item is None:
                    skipped += 1
                    continue
                if item.conversation_id in seen_ids:
                    raise ValueError("duplicate ChatGPT conversation ID")
                seen_ids.add(item.conversation_id)
                conversations.append(item)

    return ChatGPTExportBatch(
        source_digest=digest,
        observed_at=when.astimezone(timezone.utc),
        conversations=tuple(conversations),
        skipped_do_not_remember=skipped,
    )
