from datetime import datetime
from pathlib import Path
import pytest
from sofia.memory.model import MemoryRecord
from sofia.memory.store import MemoryStore
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


def test_memory_store_persists_memory_across_instances(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"
    created_at = datetime.now()

    memory = MemoryRecord(
        id="memory-1",
        content="Sparks prefers architecture-first development.",
        created_at=created_at,
    )

    first_store = MemoryStore(database_path)

    first_store.save(memory)

    second_store = MemoryStore(database_path)

    retrieved = second_store.get("memory-1")

    assert retrieved is not None
    assert retrieved.id == memory.id
    assert retrieved.content == memory.content
    assert retrieved.created_at == memory.created_at
def test_memory_store_lists_all_memories():
    store = MemoryStore()

    created_at = datetime.now()

    first = MemoryRecord(
        id="memory-1",
        content="Architecture first.",
        created_at=created_at,
    )

    second = MemoryRecord(
        id="memory-2",
        content="Testing comes before implementation.",
        created_at=created_at,
    )

    store.save(first)
    store.save(second)

    assert store.list_all() == (
        first,
        second,
    )


def test_memory_store_lists_persistent_memories(
    tmp_path: Path,
):
    database_path = tmp_path / "sofia.db"

    created_at = datetime.now()

    memory = MemoryRecord(
        id="memory-1",
        content="Persistent memory.",
        created_at=created_at,
    )

    first_store = MemoryStore(database_path)

    first_store.save(memory)
    first_store.close()

    second_store = MemoryStore(database_path)

    assert second_store.list_all() == (
        memory,
    )


def test_memory_system_recalls_relevant_memory():
    store = MemoryStore()
    system = MemorySystem(store)

    now = datetime.now()

    architecture = MemoryRecord(
        id="memory-1",
        content=(
            "Sparks prefers architecture-first development."
        ),
        created_at=now,
    )

    cooking = MemoryRecord(
        id="memory-2",
        content=(
            "Sparks likes spicy food."
        ),
        created_at=now,
    )

    system.remember(architecture)
    system.remember(cooking)

    result = system.recall_relevant(
        "How should we approach architecture?"
    )

    assert result == (
        architecture,
    )


def test_memory_system_recall_relevant_orders_by_score():
    store = MemoryStore()
    system = MemorySystem(store)

    now = datetime.now()

    weak = MemoryRecord(
        id="memory-1",
        content="Architecture.",
        created_at=now,
    )

    strong = MemoryRecord(
        id="memory-2",
        content=(
            "Architecture first development with "
            "architecture tests."
        ),
        created_at=now,
    )

    system.remember(weak)
    system.remember(strong)

    result = system.recall_relevant(
        "architecture development tests"
    )

    assert result == (
        strong,
        weak,
    )


def test_memory_system_recall_relevant_respects_limit():
    store = MemoryStore()
    system = MemorySystem(store)

    now = datetime.now()

    for index in range(5):
        system.remember(
            MemoryRecord(
                id=f"memory-{index}",
                content="Architecture testing.",
                created_at=now,
            )
        )

    result = system.recall_relevant(
        "architecture testing",
        limit=2,
    )

    assert len(result) == 2


def test_memory_system_recall_relevant_returns_empty_for_no_match():
    store = MemoryStore()
    system = MemorySystem(store)

    system.remember(
        MemoryRecord(
            id="memory-1",
            content="Architecture first.",
            created_at=datetime.now(),
        )
    )

    result = system.recall_relevant(
        "completely unrelated topic"
    )

    assert result == ()


def test_memory_system_recall_relevant_rejects_invalid_limit():
    system = MemorySystem(
        MemoryStore()
    )

    with pytest.raises(ValueError):
        system.recall_relevant(
            "architecture",
            limit=0,
        )