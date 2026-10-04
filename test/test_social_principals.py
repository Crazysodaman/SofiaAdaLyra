import pytest

from sofia.social.principals import remote_sparks_principal


@pytest.mark.parametrize("digest", [None, 64, "a" * 63, "g" * 64, " " * 64, "é" * 64])
def test_remote_principal_rejects_invalid_sha256(digest):
    with pytest.raises(ValueError, match="SHA-256 digest"):
        remote_sparks_principal(digest)


def test_remote_principal_digest_case_preserves_audience_scope():
    digest = "abcdef0123456789" * 4
    lowercase = remote_sparks_principal(digest)
    uppercase = remote_sparks_principal(digest.upper())
    assert lowercase == uppercase
    assert lowercase.audience_id == "remote-chat:abcdef0123456789"
    assert lowercase.audience_scope == uppercase.audience_scope
