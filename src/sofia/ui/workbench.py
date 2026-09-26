"""Current-main PKG-UI workbench objects for a private, text-first client.

This is a *headless domain component*, not an authentication boundary, memory
backend, rendered UI, or LLM thought stream. The host must authenticate the
actor before supplying an actor ID. Model output must never supply that ID.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Callable


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)


class WorkbenchError(ValueError):
    """Invalid workbench data or operation."""


class AccessDenied(PermissionError):
    """The verified caller is not the sole configured owner."""


class ConflictError(RuntimeError):
    """A stale revision or repeated operation would overwrite work."""


class ItemKind(str, Enum):
    PAGE = "page"
    STICKY_NOTE = "sticky_note"
    NOTEBOOK = "notebook"
    BINDER = "binder"
    BOOK = "book"


class EntryKind(str, Enum):
    IDEA = "idea"
    REFLECTION = "reflection"
    PROJECT = "project"
    REFERENCE = "reference"
    NOTE = "note"


class EntryStatus(str, Enum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


def _id(value: str, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise WorkbenchError(f"{field} must be a nonempty stable identifier")
    return value


def _text(value: str, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise WorkbenchError(f"{field} must be nonblank and at most {limit} characters")
    return value


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise WorkbenchError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _sources(value: tuple[str, ...], *, required: bool) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise WorkbenchError("source_ids must be a tuple")
    for source_id in value:
        _id(source_id, "source_id")
    if len(set(value)) != len(value) or len(value) > 32:
        raise WorkbenchError("source_ids must be unique and contain at most 32 IDs")
    if required and not value:
        raise WorkbenchError("a reflection or idea needs a recorded source/event ID")
    return value


@dataclass(frozen=True)
class Item:
    id: str
    kind: ItemKind
    title: str
    owner_id: str
    revision: int
    created_at: datetime
    archived: bool = False

    def __post_init__(self) -> None:
        _id(self.id, "item ID")
        _id(self.owner_id, "owner ID")
        if not isinstance(self.kind, ItemKind):
            raise WorkbenchError("unknown item kind")
        _text(self.title, "title", 160)
        if type(self.revision) is not int or self.revision < 1:
            raise WorkbenchError("revision must be a positive integer")
        object.__setattr__(self, "created_at", _time(self.created_at))
        if type(self.archived) is not bool:
            raise WorkbenchError("archived must be boolean")


@dataclass(frozen=True)
class Entry:
    id: str
    item_id: str
    kind: EntryKind
    content: str
    source_ids: tuple[str, ...]
    status: EntryStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    presented: bool = False

    def __post_init__(self) -> None:
        _id(self.id, "entry ID")
        _id(self.item_id, "item ID")
        if not isinstance(self.kind, EntryKind) or not isinstance(self.status, EntryStatus):
            raise WorkbenchError("unknown entry kind or status")
        _text(self.content, "content", 16000)
        _sources(self.source_ids, required=self.kind in (EntryKind.REFLECTION, EntryKind.IDEA))
        if type(self.revision) is not int or self.revision < 1:
            raise WorkbenchError("revision must be a positive integer")
        object.__setattr__(self, "created_at", _time(self.created_at))
        object.__setattr__(self, "updated_at", _time(self.updated_at))
        if self.updated_at < self.created_at:
            raise WorkbenchError("updated_at cannot precede created_at")
        if type(self.presented) is not bool:
            raise WorkbenchError("presented must be boolean")


class Workbench:
    """In-memory owner-only object store; snapshots are data, not authority.

    All mutations require the configured owner actor and unique operation IDs.
    Future shared/multi-user scopes must use separately reviewed access logic;
    no `shared=True` shortcut exists here. Real authentication, persistence,
    encryption, backups, and host-level stop belong outside this class.
    """

    def __init__(
        self,
        owner_id: str,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.owner_id = _id(owner_id, "owner ID")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._items: dict[str, Item] = {}
        self._entries: dict[str, Entry] = {}
        self._operation_ids: set[str] = set()

    def _authorize(self, actor_id: str) -> None:
        if not isinstance(actor_id, str) or actor_id != self.owner_id:
            raise AccessDenied("workbench item is not accessible to this actor")

    def _operation(self, operation_id: str) -> None:
        _id(operation_id, "operation ID")
        if operation_id in self._operation_ids:
            raise ConflictError("operation ID was already applied")

    def _now(self) -> datetime:
        return _time(self._clock())

    def items(self, *, actor_id: str) -> tuple[Item, ...]:
        self._authorize(actor_id)
        return tuple(self._items.values())

    def entries(self, *, actor_id: str, item_id: str) -> tuple[Entry, ...]:
        self._authorize(actor_id)
        self.get_item(actor_id=actor_id, item_id=item_id)
        return tuple(e for e in self._entries.values() if e.item_id == item_id)

    def presented_entries(self, *, actor_id: str, item_id: str) -> tuple[Entry, ...]:
        """Client-safe entries; internal candidates never appear by default."""
        return tuple(e for e in self.entries(actor_id=actor_id, item_id=item_id)
                     if e.presented)

    def get_item(self, *, actor_id: str, item_id: str) -> Item:
        self._authorize(actor_id)
        _id(item_id, "item ID")
        try:
            return self._items[item_id]
        except KeyError as error:
            raise WorkbenchError("unknown item") from error

    def create_item(
        self, *, actor_id: str, operation_id: str, item_id: str,
        kind: ItemKind, title: str,
    ) -> Item:
        self._authorize(actor_id)
        self._operation(operation_id)
        if item_id in self._items:
            raise ConflictError("item ID already exists")
        item = Item(item_id, kind, title, self.owner_id, 1, self._now())
        self._items[item.id] = item
        self._operation_ids.add(operation_id)
        return item

    def add_entry(
        self, *, actor_id: str, operation_id: str, item_id: str,
        expected_revision: int, entry_id: str, kind: EntryKind,
        content: str, source_ids: tuple[str, ...] = (),
    ) -> Entry:
        item = self.get_item(actor_id=actor_id, item_id=item_id)
        self._operation(operation_id)
        self._check_revision(item, expected_revision)
        if item.archived:
            raise WorkbenchError("cannot edit an archived item")
        if entry_id in self._entries:
            raise ConflictError("entry ID already exists")
        now = self._now()
        entry = Entry(entry_id, item_id, kind, content, source_ids,
                      EntryStatus.CANDIDATE, 1, now, now)
        self._entries[entry.id] = entry
        self._bump(item, operation_id)
        return entry

    def revise_entry(
        self, *, actor_id: str, operation_id: str, entry_id: str,
        expected_entry_revision: int, expected_item_revision: int,
        content: str, source_ids: tuple[str, ...],
    ) -> Entry:
        self._authorize(actor_id)
        self._operation(operation_id)
        _id(entry_id, "entry ID")
        try:
            current = self._entries[entry_id]
        except KeyError as error:
            raise WorkbenchError("unknown entry") from error
        item = self.get_item(actor_id=actor_id, item_id=current.item_id)
        self._check_revision(item, expected_item_revision)
        if item.archived or current.status in (EntryStatus.REJECTED, EntryStatus.SUPERSEDED):
            raise WorkbenchError("entry cannot be revised")
        if type(expected_entry_revision) is not int or current.revision != expected_entry_revision:
            raise ConflictError("stale entry revision")
        now = self._now()
        if now < current.updated_at:
            raise WorkbenchError("time cannot move backwards for an entry")
        updated = replace(current, content=_text(content, "content", 16000),
                          source_ids=_sources(source_ids, required=current.kind in
                                              (EntryKind.REFLECTION, EntryKind.IDEA)),
                          status=EntryStatus.CANDIDATE,
                          revision=current.revision + 1, presented=False, updated_at=now)
        self._entries[entry_id] = updated
        self._bump(item, operation_id)
        return updated

    def set_status(
        self, *, actor_id: str, operation_id: str, entry_id: str,
        expected_entry_revision: int, expected_item_revision: int,
        status: EntryStatus,
    ) -> Entry:
        """Owner review action; REVIEWED means approved by owner, not proven true."""
        self._authorize(actor_id)
        self._operation(operation_id)
        _id(entry_id, "entry ID")
        if entry_id not in self._entries:
            raise WorkbenchError("unknown entry")
        current = self._entries[entry_id]
        item = self.get_item(actor_id=actor_id, item_id=current.item_id)
        self._check_revision(item, expected_item_revision)
        if item.archived or type(expected_entry_revision) is not int or current.revision != expected_entry_revision:
            raise ConflictError("item is archived or entry revision is stale")
        if not isinstance(status, EntryStatus) or current.status != EntryStatus.CANDIDATE or status == EntryStatus.CANDIDATE:
            raise WorkbenchError("only a candidate can transition to a final status")
        now = self._now()
        if now < current.updated_at:
            raise WorkbenchError("time cannot move backwards for an entry")
        updated = replace(current, status=status, revision=current.revision + 1,
                          updated_at=now)
        self._entries[entry_id] = updated
        self._bump(item, operation_id)
        return updated

    def present_entry(
        self, *, actor_id: str, operation_id: str, entry_id: str,
        expected_entry_revision: int, expected_item_revision: int,
    ) -> Entry:
        """Record an explicit decision to present a reviewed entry to Sparks.

        This is not a network send, permission grant, or proof of factual truth.
        """
        self._authorize(actor_id)
        self._operation(operation_id)
        _id(entry_id, "entry ID")
        if entry_id not in self._entries:
            raise WorkbenchError("unknown entry")
        current = self._entries[entry_id]
        item = self.get_item(actor_id=actor_id, item_id=current.item_id)
        self._check_revision(item, expected_item_revision)
        if (item.archived or current.status != EntryStatus.REVIEWED
                or current.presented or type(expected_entry_revision) is not int
                or current.revision != expected_entry_revision):
            raise ConflictError("entry cannot be presented in its current state")
        now = self._now()
        if now < current.updated_at:
            raise WorkbenchError("time cannot move backwards for an entry")
        updated = replace(current, presented=True, revision=current.revision + 1,
                          updated_at=now)
        self._entries[entry_id] = updated
        self._bump(item, operation_id)
        return updated

    def archive_item(
        self, *, actor_id: str, operation_id: str, item_id: str,
        expected_revision: int,
    ) -> Item:
        item = self.get_item(actor_id=actor_id, item_id=item_id)
        self._operation(operation_id)
        self._check_revision(item, expected_revision)
        if item.archived:
            raise WorkbenchError("already archived")
        updated = replace(item, archived=True, revision=item.revision + 1)
        self._items[item_id] = updated
        self._operation_ids.add(operation_id)
        return updated

    @staticmethod
    def _check_revision(item: Item, expected_revision: int) -> None:
        if type(expected_revision) is not int or expected_revision != item.revision:
            raise ConflictError("stale item revision")

    def _bump(self, item: Item, operation_id: str) -> None:
        self._items[item.id] = replace(item, revision=item.revision + 1)
        self._operation_ids.add(operation_id)

    def snapshot(self, *, actor_id: str) -> dict[str, object]:
        """Return plain, private data for an authorized persistence adapter.

        This data MUST NOT be sent to shared/public clients or trusted as an
        authentication token. The adapter owns encryption and atomic storage.
        """
        self._authorize(actor_id)
        return {
            "schema": 1,
            "owner_id": self.owner_id,
            "items": [
                {"id": i.id, "kind": i.kind.value, "title": i.title,
                 "owner_id": i.owner_id, "revision": i.revision,
                 "created_at": i.created_at.isoformat(), "archived": i.archived}
                for i in self._items.values()
            ],
            "entries": [
                {"id": e.id, "item_id": e.item_id, "kind": e.kind.value,
                 "content": e.content, "source_ids": list(e.source_ids),
                 "status": e.status.value, "revision": e.revision,
                 "created_at": e.created_at.isoformat(),
                 "updated_at": e.updated_at.isoformat(),
                 "presented": e.presented}
                for e in self._entries.values()
            ],
            "operation_ids": sorted(self._operation_ids),
        }

    @classmethod
    def from_snapshot(
        cls, snapshot: dict[str, object], *, expected_owner_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> Workbench:
        """Validate a snapshot fully before publishing a restored instance."""
        _id(expected_owner_id, "owner ID")
        if not isinstance(snapshot, dict) or set(snapshot) != {
            "schema", "owner_id", "items", "entries", "operation_ids"
        } or type(snapshot["schema"]) is not int or snapshot["schema"] != 1:
            raise WorkbenchError("unsupported snapshot schema")
        if snapshot["owner_id"] != expected_owner_id:
            raise AccessDenied("snapshot belongs to a different owner")
        if not all(isinstance(snapshot[k], list) for k in ("items", "entries", "operation_ids")):
            raise WorkbenchError("malformed snapshot collections")
        result = cls(expected_owner_id, clock=clock)
        try:
            for raw in snapshot["items"]:
                if not isinstance(raw, dict) or set(raw) != {
                    "id", "kind", "title", "owner_id", "revision", "created_at", "archived"
                }:
                    raise WorkbenchError("invalid item fields")
                item = Item(raw["id"], ItemKind(raw["kind"]), raw["title"],
                            raw["owner_id"], raw["revision"],
                            datetime.fromisoformat(raw["created_at"]), raw["archived"])
                if item.owner_id != expected_owner_id or item.id in result._items:
                    raise WorkbenchError("foreign or duplicate item")
                result._items[item.id] = item
            for raw in snapshot["entries"]:
                if not isinstance(raw, dict) or set(raw) != {
                    "id", "item_id", "kind", "content", "source_ids", "status",
                    "revision", "created_at", "updated_at", "presented"
                } or not isinstance(raw["source_ids"], list):
                    raise WorkbenchError("invalid entry fields")
                entry = Entry(raw["id"], raw["item_id"], EntryKind(raw["kind"]),
                              raw["content"], tuple(raw["source_ids"]),
                              EntryStatus(raw["status"]), raw["revision"],
                              datetime.fromisoformat(raw["created_at"]),
                              datetime.fromisoformat(raw["updated_at"]), raw["presented"])
                if entry.item_id not in result._items or entry.id in result._entries:
                    raise WorkbenchError("orphaned or duplicate entry")
                if entry.presented and entry.status != EntryStatus.REVIEWED:
                    raise WorkbenchError("only reviewed entries can be presented")
                result._entries[entry.id] = entry
            operations = [_id(o, "operation ID") for o in snapshot["operation_ids"]]
            if len(set(operations)) != len(operations):
                raise WorkbenchError("duplicate operation ID")
            result._operation_ids = set(operations)
        except WorkbenchError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise WorkbenchError("invalid snapshot contents") from error
        return result
