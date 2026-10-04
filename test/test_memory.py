from datetime import datetime
from pathlib import Path
import pytest
from sofia.memory.model import MemoryRecord
from sofia.memory.provenance_store import DurableMemoryCandidateStore
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


def test_memory_system_recall_relevant_rejects_invalid_limit(tmp_path):
    system = MemorySystem(
        DurableMemoryCandidateStore(tmp_path / "sofia.db")
    )

    with pytest.raises(ValueError):
        system.recall_relevant(
            "architecture",
            limit=0,
        )