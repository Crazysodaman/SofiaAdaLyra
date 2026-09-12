import hashlib
from pathlib import Path

from sofia.constitution.store import ConstitutionStore


def test_constitution_store_loads_constitution():
    constitution_path = (
        Path(__file__).parent.parent
        / "src"
        / "sofia"
        / "constitution"
        / "constitution.md"
    )

    store = ConstitutionStore(constitution_path)
    constitution = store.load()

    assert constitution.version == "1.0"
    assert constitution.content

    expected_hash = hashlib.sha256(
        constitution_path.read_bytes()
    ).hexdigest()

    assert constitution.content_hash == expected_hash