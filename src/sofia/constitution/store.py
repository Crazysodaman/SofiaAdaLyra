from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from sofia.constitution.model import Constitution


def canonical_constitution_text(content: str) -> str:
    """Normalize platform-only newline differences before integrity hashing."""
    if not isinstance(content, str):
        raise TypeError("Constitution content must be text.")
    return content.replace("\r\n", "\n").replace("\r", "\n")


class ConstitutionStore:
    """
    Loads and verifies Sofía's Constitution.
    """

    def __init__(self, constitution_path: Path):
        self.constitution_path = constitution_path

    def load(self) -> Constitution:
        raw = self.constitution_path.read_bytes()
        content = canonical_constitution_text(raw.decode("utf-8"))
        content_hash = sha256(content.encode("utf-8")).hexdigest()

        return Constitution(
            version="1.0",
            content=content,
            content_hash=content_hash,
            loaded_at=datetime.now(timezone.utc),
        )
