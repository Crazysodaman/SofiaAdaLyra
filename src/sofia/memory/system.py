from sofia.memory.model import MemoryRecord
from sofia.memory.store import MemoryStore


class MemorySystem:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def remember(self, memory: MemoryRecord) -> None:
        self._store.save(memory)

    def recall(self, memory_id: str) -> MemoryRecord | None:
        return self._store.get(memory_id)