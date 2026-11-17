"""Bounded client-local draft state, never canonical Core memory.

Remote clients may persist drafts only in their own private preference store.
This class rejects canonical database paths by accepting an explicit persistence
port instead of a filesystem database location.
"""
from __future__ import annotations

from dataclasses import dataclass

from sofia.platform.chat_clients.contracts import normalize_core_id
from sofia.platform.chat_clients.ports import DraftPersistencePort

_MAX_DRAFT = 8_000
_MAX_ENTRIES = 64


@dataclass(frozen=True, slots=True)
class ClientDraft:
    client_id: str
    core_id: str
    room_id: str
    content: str


class ClientDraftStore:
    def __init__(
        self,
        *,
        client_id: str,
        persistence: DraftPersistencePort | None = None,
        max_entries: int = _MAX_ENTRIES,
    ) -> None:
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be nonempty")
        if type(max_entries) is not int or not 1 <= max_entries <= _MAX_ENTRIES:
            raise ValueError("max_entries must be 1..64")
        self._client_id = client_id
        self._persistence = persistence
        self._max_entries = max_entries
        self._drafts: dict[tuple[str, str], str] = {}

    @property
    def client_id(self) -> str:
        return self._client_id

    def _pair(self, core_id: str, room_id: str) -> tuple[str, str]:
        core = normalize_core_id(core_id)
        if not isinstance(room_id, str) or not room_id.strip():
            raise ValueError("room_id must be nonempty")
        return core, room_id

    def _trim(self) -> None:
        while len(self._drafts) > self._max_entries:
            self._drafts.pop(next(iter(self._drafts)))

    def load(self, *, core_id: str, room_id: str) -> ClientDraft | None:
        key = self._pair(core_id, room_id)
        if key in self._drafts:
            content = self._drafts[key]
        elif self._persistence is not None:
            content = self._persistence.load_draft(
                client_id=self._client_id, core_id=key[0], room_id=key[1]
            )
            if content is not None:
                self._drafts[key] = content
        else:
            content = None
        if content is None:
            return None
        return ClientDraft(
            client_id=self._client_id,
            core_id=key[0],
            room_id=key[1],
            content=content,
        )

    def save(self, *, core_id: str, room_id: str, content: str) -> ClientDraft | None:
        key = self._pair(core_id, room_id)
        if not isinstance(content, str):
            raise TypeError("draft content must be text")
        if len(content) > _MAX_DRAFT:
            raise ValueError("draft content exceeds the client bound")
        if not content.strip():
            self.clear(core_id=core_id, room_id=room_id)
            return None
        self._drafts.pop(key, None)
        self._drafts[key] = content
        self._trim()
        if self._persistence is not None:
            self._persistence.save_draft(
                client_id=self._client_id, core_id=key[0], room_id=key[1],
                content=content,
            )
        return self.load(core_id=key[0], room_id=key[1])

    def clear(self, *, core_id: str, room_id: str) -> None:
        key = self._pair(core_id, room_id)
        self._drafts.pop(key, None)
        if self._persistence is not None:
            self._persistence.clear_draft(
                client_id=self._client_id, core_id=key[0], room_id=key[1]
            )

    def __len__(self) -> int:
        return len(self._drafts)


class MemoryDraftPersistence:
    """Test/desktop preference substitute; holds no Core conversation history."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str, str], str] = {}

    def load_draft(self, *, client_id: str, core_id: str, room_id: str) -> str | None:
        return self._values.get((client_id, core_id, room_id))

    def save_draft(
        self, *, client_id: str, core_id: str, room_id: str, content: str
    ) -> None:
        self._values[(client_id, core_id, room_id)] = content

    def clear_draft(self, *, client_id: str, core_id: str, room_id: str) -> None:
        self._values.pop((client_id, core_id, room_id), None)
