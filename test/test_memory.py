from datetime import datetime
from sofia.memory.store import MemoryStore
from sofia.memory.model import MemoryRecord
from sofia.memory.system import MemorySystem

def test_memory_record_stores_content():
    created_at = datetime.now()

    memory = MemoryRecord(
        id="memory-1",
        content="Sparks prefers architecture-first development.",
        created_at=created_at,
    )

    assert memory.id == "memory-1"
    assert memory.content == (
        "Sparks prefers architecture-first development."
    )
    assert memory.created_at is created_at

def test_memory_record_identity_is_based_on_id():
    created_at = datetime.now()

    first = MemoryRecord(
        id="memory-1",
        content="First version.",
        created_at=created_at,
    )

    second = MemoryRecord(
        id="memory-1",
        content="Second version.",
        created_at=created_at,
    )

    assert first.id == second.id
    assert first != second

def test_memory_store_saves_and_retrieves_memory():
    created_at = datetime.now()

    memory = MemoryRecord(
        id="memory-1",
        content="Sparks prefers architecture-first development.",
        created_at=created_at,
    )

    store = MemoryStore()

    store.save(memory)

    retrieved = store.get("memory-1")

    assert retrieved is memory

def test_memory_store_returns_none_for_missing_memory():
    store = MemoryStore()

    result = store.get("does-not-exist")

    assert result is None

def test_memory_store_keeps_multiple_memories_independent():
    store = MemoryStore()
    created_at = datetime.now()

    first = MemoryRecord(
        id="memory-1",
        content="First memory.",
        created_at=created_at,
    )

    second = MemoryRecord(
        id="memory-2",
        content="Second memory.",
        created_at=created_at,
    )

    store.save(first)
    store.save(second)

    assert store.get("memory-1") is first
    assert store.get("memory-2") is second

def test_memory_store_replaces_memory_with_same_id():
    store = MemoryStore()
    created_at = datetime.now()

    first = MemoryRecord(
        id="memory-1",
        content="Original memory.",
        created_at=created_at,
    )

    replacement = MemoryRecord(
        id="memory-1",
        content="Updated memory.",
        created_at=created_at,
    )

    store.save(first)
    store.save(replacement)

    assert store.get("memory-1") is replacement

def test_memory_system_remembers_memory():
    store = MemoryStore()
    system = MemorySystem(store)
    created_at = datetime.now()

    memory = MemoryRecord(
        id="memory-1",
        content="Sparks prefers architecture-first development.",
        created_at=created_at,
    )

    system.remember(memory)

    assert store.get("memory-1") is memory

def test_memory_system_recalls_memory():
    store = MemoryStore()
    system = MemorySystem(store)
    created_at = datetime.now()

    memory = MemoryRecord(
        id="memory-1",
        content="Sparks prefers architecture-first development.",
        created_at=created_at,
    )

    store.save(memory)

    result = system.recall("memory-1")

    assert result is memory