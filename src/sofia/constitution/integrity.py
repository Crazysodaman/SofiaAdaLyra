from pathlib import Path

from sofia.constitution.model import Constitution


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
        self._hash_path = Path(hash_path)

    def verify(self, constitution: Constitution) -> None:
        expected_hash = self._hash_path.read_text(
            encoding="utf-8"
        ).strip()

        if constitution.content_hash.lower() != expected_hash.lower():
            raise ConstitutionIntegrityError(
                "Constitution integrity verification failed."
            )