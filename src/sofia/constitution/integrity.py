from hashlib import sha256
from pathlib import Path

from sofia.constitution.model import Constitution


class ConstitutionIntegrityError(Exception):
    """Raised when the Constitution fails integrity verification."""


class ConstitutionIntegrityVerifier:
    """Verifies a Constitution against a trusted SHA-256 hash."""

    def __init__(self, expected_hash_path: Path):
        self.expected_hash_path = expected_hash_path

    def verify(self, constitution: Constitution) -> None:
        expected_hash = self.expected_hash_path.read_text(
            encoding="utf-8"
        ).strip().lower()

        if len(expected_hash) != 64:
            raise ConstitutionIntegrityError(
                "Trusted Constitution hash is invalid."
            )

        try:
            int(expected_hash, 16)
        except ValueError as exc:
            raise ConstitutionIntegrityError(
                "Trusted Constitution hash is invalid."
            ) from exc

        if constitution.content_hash != expected_hash:
            raise ConstitutionIntegrityError(
                "Constitution integrity verification failed."
            )