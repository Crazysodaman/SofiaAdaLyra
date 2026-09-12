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