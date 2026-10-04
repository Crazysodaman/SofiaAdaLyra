import pytest
from hashlib import sha256
from pathlib import Path

from sofia.constitution.store import ConstitutionIntegrityError, ConstitutionIntegrityVerifier
from sofia.constitution.store import Constitution
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


def test_constitution_hash_is_stable_across_lf_and_crlf_checkouts(tmp_path):
    lf = "# Test Constitution\n\nOne rule.\n"
    crlf = lf.replace("\n", "\r\n")
    lf_path = tmp_path / "lf.md"
    crlf_path = tmp_path / "crlf.md"
    lf_path.write_bytes(lf.encode("utf-8"))
    crlf_path.write_bytes(crlf.encode("utf-8"))

    expected = sha256(lf.encode("utf-8")).hexdigest()
    assert ConstitutionStore(lf_path).load().content_hash == expected
    assert ConstitutionStore(crlf_path).load().content_hash == expected
    assert ConstitutionStore(crlf_path).load().content == lf


def test_constitution_hash_still_detects_real_content_changes(tmp_path):
    original = tmp_path / "original.md"
    changed = tmp_path / "changed.md"
    original.write_text("rule one\n", encoding="utf-8", newline="\n")
    changed.write_text("rule two\n", encoding="utf-8", newline="\n")

    assert (
        ConstitutionStore(original).load().content_hash
        != ConstitutionStore(changed).load().content_hash
    )
