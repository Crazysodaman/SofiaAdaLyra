import pytest
from datetime import datetime, timezone

from sofia.constitution.model import Constitution


def test_constitution_can_be_created():
    constitution = Constitution(
        version="1.0",
        content="Sofía Ada Lyra Constitution",
        content_hash="test-hash",
        loaded_at=datetime.now(timezone.utc),
    )

    assert constitution.version == "1.0"
    assert constitution.content == "Sofía Ada Lyra Constitution"
    assert constitution.content_hash == "test-hash"


def test_constitution_is_immutable():
    constitution = Constitution(
        version="1.0",
        content="Sofía Ada Lyra Constitution",
        content_hash="test-hash",
        loaded_at=datetime.now(timezone.utc),
    )

    with pytest.raises(AttributeError):
        constitution.version = "2.0"