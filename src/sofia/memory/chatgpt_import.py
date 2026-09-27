from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class ChatGPTMemoryImportItem:
    """One exact source item recovered from a ChatGPT memory dump."""

    source_id: str
    content: str
    source_created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id must be a nonempty string")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("content must be a nonempty string")
        if self.source_created_at is not None:
            if not isinstance(self.source_created_at, datetime):
                raise TypeError("source_created_at must be a datetime or None")
            if (
                self.source_created_at.tzinfo is None
                or self.source_created_at.utcoffset() is None
            ):
                raise ValueError("source_created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ChatGPTMemoryImportBatch:
    """
    Parsed, immutable ChatGPT memory evidence.

    source_digest identifies the exact imported payload. Parsing does not
    promote anything into cognition or trusted long-term memory.
    """

    source_digest: str
    observed_at: datetime
    items: tuple[ChatGPTMemoryImportItem, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_digest):
            raise ValueError("source_digest must be a lowercase SHA-256 digest")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at must be a datetime")
        if (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.items, tuple):
            raise TypeError("items must be a tuple")
        if any(not isinstance(item, ChatGPTMemoryImportItem) for item in self.items):
            raise TypeError("items must contain ChatGPTMemoryImportItem values")


def parse_chatgpt_memory_dump(
    payload: str,
    *,
    observed_at: datetime | None = None,
) -> ChatGPTMemoryImportBatch:
    """
    Parse common ChatGPT memory-dump shapes without assigning trust.

    Supported inputs are JSON arrays of strings or objects, JSON objects
    containing a memories or memory array, and plain-text bullet/line dumps.

    The exact original payload is identified by SHA-256 so repeated imports can
    be made idempotent by the persistence layer. Missing source timestamps stay
    unknown rather than being rewritten as the import time.
    """
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("payload must be a nonempty string")

    when = observed_at or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    raw_items = _decode_items(payload)
    items = tuple(
        _to_item(raw, index=index, digest=digest)
        for index, raw in enumerate(raw_items)
    )

    if not items:
        raise ValueError("memory dump did not contain any importable items")

    return ChatGPTMemoryImportBatch(
        source_digest=digest,
        observed_at=when.astimezone(timezone.utc),
        items=items,
    )


def _decode_items(payload: str) -> list[Any]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError:
        return _plain_text_items(payload)

    if isinstance(decoded, list):
        return decoded

    if isinstance(decoded, dict):
        for key in ("memories", "memory"):
            value = decoded.get(key)
            if isinstance(value, list):
                return value

        for key in ("content", "text", "summary"):
            value = decoded.get(key)
            if isinstance(value, str) and value.strip():
                return [decoded]

    raise ValueError("unsupported ChatGPT memory dump shape")


def _plain_text_items(payload: str) -> list[str]:
    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if not lines:
        return []

    bullet = re.compile(r"^(?:[-*•]+|\d+[.)])\s+")
    stripped = [bullet.sub("", line).strip() for line in lines]
    useful = [line for line in stripped if line]
    return useful if len(useful) > 1 else [payload.strip()]


def _to_item(raw: Any, *, index: int, digest: str) -> ChatGPTMemoryImportItem:
    source_id = f"chatgpt-memory:{digest}:{index}"

    if isinstance(raw, str):
        content = raw.strip()
        if not content:
            raise ValueError("memory dump contains an empty string item")
        return ChatGPTMemoryImportItem(source_id=source_id, content=content)

    if not isinstance(raw, dict):
        raise ValueError("memory dump items must be strings or objects")

    content = None
    for key in ("content", "text", "memory", "summary"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            content = value.strip()
            break
    if content is None:
        raise ValueError("memory dump object is missing textual content")

    for key in ("id", "memory_id", "source_id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            source_id = f"chatgpt-memory:{digest}:{value.strip()}"
            break

    created_at = _parse_timestamp(
        raw.get("created_at", raw.get("create_time"))
    )
    return ChatGPTMemoryImportItem(
        source_id=source_id,
        content=content,
        source_created_at=created_at,
    )


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None

    return parsed.astimezone(timezone.utc)
