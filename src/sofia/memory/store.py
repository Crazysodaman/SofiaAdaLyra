from sofia.memory.model import MemoryRecord


class MemoryStore:
    """
    In-memory storage for memory records.
    """

    def __init__(self) -> None:
        self._memories: dict[str, MemoryRecord] = {}

    def save(self, memory: MemoryRecord) -> None:
        self._memories[memory.id] = memory

    def get(self, memory_id: str) -> MemoryRecord | None:
        return self._memories.get(memory_id)