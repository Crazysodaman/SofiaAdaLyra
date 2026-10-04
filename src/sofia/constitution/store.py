from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class Constitution:
    """
    Represents an immutable loaded version of Sofía's Constitution.
    """

    version: str
    content: str
    content_hash: str
    loaded_at: datetime


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


class ConstitutionIntegrityError(Exception):
    """
    Raised when the loaded Constitution does not match
    the trusted integrity hash.
    """


class ConstitutionIntegrityVerifier:
    """
    Verifies the integrity of a loaded Constitution.
    """

    def __init__(self, hash_path: str):
        self._expected_hash_path = Path(hash_path)

    @property
    def expected_hash_path(self) -> Path:
        return self._expected_hash_path

    def verify(self, constitution: Constitution) -> None:
        expected_hash = self.expected_hash_path.read_text(
            encoding="utf-8"
        ).strip()

        if len(expected_hash) != 64:
            raise ConstitutionIntegrityError(
                "Trusted Constitution hash must contain exactly "
                "64 hexadecimal characters."
            )

        try:
            int(expected_hash, 16)
        except ValueError as exc:
            raise ConstitutionIntegrityError(
                "Trusted Constitution hash must contain only "
                "hexadecimal characters."
            ) from exc

        if constitution.content_hash.lower() != expected_hash.lower():
            raise ConstitutionIntegrityError(
                "Constitution integrity verification failed."
            )
