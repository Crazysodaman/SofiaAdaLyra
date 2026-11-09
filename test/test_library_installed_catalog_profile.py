"""D028 owner-private signed catalog profile, independently pinned B1 trust.

Disposable signing keys and profiles are only test evidence. They do NOT
sign a real release or authorize production Platform enrollment.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import timedelta
import json
import os

import pytest

from sofia.platform.run.library_installed_catalog import InstalledLibraryCatalogProvider
from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
from test.library_fixture_support import make_signed_catalog_fixture


@pytest.fixture
def installed_profile(tmp_path):
    envelope, sign, keys = make_signed_catalog_fixture()
    path = tmp_path / "catalog-profile.json"
    profile = {
        "schema": "aegis.platform.library.installed-catalog-profile.v1",
        "signed_index_b64": b64encode(sign()).decode(),
        "publisher_public_key_b64": b64encode(
            keys["trusted_publisher_public_key"]
        ).decode(),
    }
    path.write_text(json.dumps(profile, sort_keys=True), encoding="utf-8")
    path.chmod(0o600)
    policy = {
        "profile": path,
        "expected_publisher_key_sha256": keys["expected_publisher_key_sha256"],
        "expected_source_platform_id": "primary-library",
        "expected_target_platform_id": "enrolled-recipient",
        "expected_catalog_generation": 3,
        "minimum_catalog_revision": 7,
        "publisher_key_current": lambda _: True,
        "clock": lambda: keys["now"],
    }
    return path, profile, policy


@pytest.mark.skipif(os.name == "nt", reason="POSIX profile ownership and inode test")
def test_installed_profile_requires_independent_b1_trust_not_self_signing(installed_profile):
    path, profile, policy = installed_profile
    source = InstalledLibraryCatalogProvider(**policy)()
    assert source.expected_source_platform_id == "primary-library"
    assert source.expected_catalog_generation == 3
    assert len(source.raw_signed_index) > 100

    with pytest.raises(PermissionError, match="independent installed B1"):
        InstalledLibraryCatalogProvider(
            **{**policy, "expected_publisher_key_sha256": "a" * 64},
        )()


@pytest.mark.skipif(os.name == "nt", reason="POSIX profile ownership and inode test")
def test_owner_private_profile_wrong_target_and_revocation_fail(installed_profile):
    path, profile, policy = installed_profile
    with pytest.raises(SignedLibraryIndexRejected, match="mismatch"):
        InstalledLibraryCatalogProvider(
            **{**policy, "expected_target_platform_id": "other-platform"},
        )()
    with pytest.raises(SignedLibraryIndexRejected, match="revoked"):
        InstalledLibraryCatalogProvider(
            **{**policy, "publisher_key_current": lambda _: False},
        )()


@pytest.mark.skipif(os.name == "nt", reason="POSIX profile ownership and inode test")
def test_installed_catalog_profile_denies_nonprivate_or_linked_file(installed_profile, tmp_path):
    path, profile, policy = installed_profile
    path.chmod(0o644)
    with pytest.raises(PermissionError):
        InstalledLibraryCatalogProvider(**policy)()
    path.chmod(0o600)
    link = tmp_path / "profile-link"
    os.link(path, link)
    with pytest.raises(PermissionError, match="single-inode"):
        InstalledLibraryCatalogProvider(**policy)()


@pytest.mark.skipif(os.name == "nt", reason="POSIX profile ownership and inode test")
def test_installed_catalog_profile_denies_duplicate_field_and_bad_base64(installed_profile):
    path, profile, policy = installed_profile
    serialized = path.read_text()
    path.write_text(
        serialized.replace(
            '"schema":', '"schema":"forged","schema":', 1,
        ), encoding="utf-8",
    )
    path.chmod(0o600)
    with pytest.raises(PermissionError, match="duplicate"):
        InstalledLibraryCatalogProvider(**policy)()
    path.write_text(
        json.dumps({**profile, "signed_index_b64": "bad~"}),
        encoding="utf-8",
    )
    path.chmod(0o600)
    with pytest.raises(PermissionError, match="encoding"):
        InstalledLibraryCatalogProvider(**policy)()
