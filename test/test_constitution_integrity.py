import pytest
from pathlib import Path

from sofia.constitution.integrity import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
)
from sofia.constitution.model import Constitution
from sofia.constitution.store import ConstitutionStore


CONSTITUTION_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

EXPECTED_HASH_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)


def test_constitution_integrity_verification_passes():
    store = ConstitutionStore(CONSTITUTION_PATH)
    constitution = store.load()

    verifier = ConstitutionIntegrityVerifier(EXPECTED_HASH_PATH)

    verifier.verify(constitution)


def test_invalid_trusted_hash_length_is_rejected(tmp_path):
    expected_hash_path = tmp_path / "constitution.sha256"
    expected_hash_path.write_text("abc", encoding="utf-8")

    constitution = Constitution(
        version="1.0",
        content="test",
        content_hash="abc",
        loaded_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )

    verifier = ConstitutionIntegrityVerifier(expected_hash_path)

    with pytest.raises(ConstitutionIntegrityError):
        verifier.verify(constitution)


def test_invalid_trusted_hash_hex_is_rejected(tmp_path):
    expected_hash_path = tmp_path / "constitution.sha256"
    expected_hash_path.write_text("g" * 64, encoding="utf-8")

    constitution = Constitution(
        version="1.0",
        content="test",
        content_hash="g" * 64,
        loaded_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )

    verifier = ConstitutionIntegrityVerifier(expected_hash_path)

    with pytest.raises(ConstitutionIntegrityError):
        verifier.verify(constitution)


def test_hash_mismatch_is_rejected(tmp_path):
    expected_hash_path = tmp_path / "constitution.sha256"
    expected_hash_path.write_text("0" * 64, encoding="utf-8")

    constitution = Constitution(
        version="1.0",
        content="test",
        content_hash="1" * 64,
        loaded_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )

    verifier = ConstitutionIntegrityVerifier(expected_hash_path)

    with pytest.raises(ConstitutionIntegrityError):
        verifier.verify(constitution)