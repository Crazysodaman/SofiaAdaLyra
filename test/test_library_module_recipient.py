"""Synthetic recipient proof for D028 module acquisition, never installed-host PASS."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.modules.library_recipient import (
    ModuleRecipientPin, ModuleRecipientRejected, review_signed_module_recipient,
)
from test.test_module_package_v1 import manifest, signed


NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def fixture(tmp_path, *, source="LOCAL_VERIFIED_CACHE", license="permitted"):
    package_root = tmp_path / "incoming"
    package_root.mkdir()
    artifact = package_root / "module.py"
    artifact.write_bytes(b"MODULE = 'signed test only'\n")
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    value = signed(manifest(
        (("module.py", sha256(artifact.read_bytes()).hexdigest()),),
        module_id="org.sofia.test-library",
    ), key)
    pin = ModuleRecipientPin(
        module_id=value.module_id, version=value.version,
        package_digest=value.package_identity_digest(),
        publisher=value.publisher, trust_ref=value.trust_ref,
        publisher_key_sha256=sha256(public).hexdigest(),
        source_kind=source, license_distribution=license, data_class="public",
        catalog_revision=9, metadata_fresh_until=NOW + timedelta(minutes=1),
    )
    return pin, value, package_root, public


def review(pin, value, root, pub, **overrides):
    defaults = dict(
        pin=pin, manifest=value, package_root=root, now=NOW,
        catalog_revision_floor=9, catalog_admit=lambda _: True,
        publisher_current=lambda _: True,
        publisher_key_lookup=lambda _: pub,
        remote_source_current=lambda _: True,
        internet_enabled=False,
    )
    defaults.update(overrides)
    return review_signed_module_recipient(**defaults)


def test_receiver_verifies_signature_and_real_file_digest_no_install(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    before = sorted((p.as_posix(), p.stat().st_size)
                    for p in tmp_path.rglob("*") if p.is_file())
    valid = review(pin, value, root, public)
    assert valid.package_digest == pin.package_digest
    assert valid.manifest.publisher == "owner-reviewed"
    after = sorted((p.as_posix(), p.stat().st_size)
                   for p in tmp_path.rglob("*") if p.is_file())
    assert before == after
    assert not hasattr(valid, "activate")
    assert not hasattr(valid, "install")
    assert not hasattr(valid, "accept_peer")


def test_catalog_denial_prevents_package_open_or_key_lookup(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="catalog"):
        review(
            pin, value, root / "missing", public,
            catalog_admit=lambda _: calls.append("catalog") or False,
            publisher_current=lambda _: calls.append("publisher") or True,
            publisher_key_lookup=lambda _: calls.append("key") or public,
        )
    assert calls == ["catalog"]


@pytest.mark.parametrize("kind,license", [
    ("AUTHORIZED_PEER", "restricted"),
    ("AUTHORIZED_PEER", "non_redistributable"),
    ("OWNER_SELECTED_HUB", "unknown"),
    ("OWNER_SELECTED_HUB", "restricted"),
    ("LOCAL_VERIFIED_CACHE", "unknown"),
])
def test_license_blocks_unreviewed_distribution_without_io(tmp_path, kind, license):
    pin, value, root, public = fixture(tmp_path, source=kind, license=license)
    with pytest.raises(ModuleRecipientRejected, match="license"):
        review(pin, value, root / "missing", public)


def test_private_artifact_cannot_be_redistributed_from_peer(tmp_path):
    pin, value, root, public = fixture(tmp_path, source="AUTHORIZED_PEER")
    with pytest.raises(ModuleRecipientRejected, match="private"):
        review(replace(pin, data_class="private"), value, root, public)


@pytest.mark.parametrize("source", ["AUTHORIZED_PEER", "OWNER_SELECTED_HUB", "OFFICIAL_REMOTE"])
def test_remote_source_denial_fences_before_file_verification(tmp_path, source):
    pin, value, root, public = fixture(tmp_path, source=source)
    with pytest.raises(ModuleRecipientRejected):
        review(
            pin, value, root / "missing", public,
            internet_enabled=source == "OFFICIAL_REMOTE",
            remote_source_current=lambda _: False,
        )


def test_no_internet_fallback_when_wan_is_disabled(tmp_path):
    pin, value, root, public = fixture(tmp_path, source="OFFICIAL_REMOTE")
    with pytest.raises(ModuleRecipientRejected, match="Internet"):
        review(pin, value, root, public)
    assert review(pin, value, root, public,
                  internet_enabled=True).package_digest == pin.package_digest


def test_replay_stale_catalog_and_revoked_signer_are_rejected(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    with pytest.raises(ModuleRecipientRejected, match="expired"):
        review(pin, value, root, public, now=NOW + timedelta(minutes=2))
    with pytest.raises(ModuleRecipientRejected, match="rolled back"):
        review(pin, value, root, public, catalog_revision_floor=10)
    with pytest.raises(ModuleRecipientRejected, match="revoked"):
        review(pin, value, root, public, publisher_current=lambda _: False)


def test_cross_target_catalog_identity_and_root_pin_refused(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    with pytest.raises(ModuleRecipientRejected, match="differs"):
        review(replace(pin, version="99.0.0"), value, root, public)
    with pytest.raises(ModuleRecipientRejected, match="key pin"):
        review(replace(pin, publisher_key_sha256="c" * 64), value, root, public)


def test_changed_bytes_and_forged_signature_rejected_even_if_catalog_admitted(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    (root / "module.py").write_bytes(b"malicious changed bytes")
    with pytest.raises(ModuleRecipientRejected, match="signature or file digest"):
        review(pin, value, root, public)
    (root / "module.py").write_bytes(b"MODULE = 'signed test only'\n")
    fake_key = Ed25519PrivateKey.generate()
    forged = signed(value, fake_key)
    with pytest.raises(ModuleRecipientRejected, match="signature or file digest"):
        review(pin, forged, root, public)


def test_unknown_missing_authority_or_nonboolean_trust_refused(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    with pytest.raises(ModuleRecipientRejected, match="canonical .*catalog"):
        review(pin, value, root, public, catalog_admit=lambda _: None)
    with pytest.raises(ModuleRecipientRejected, match="publisher revoked"):
        review(pin, value, root, public, publisher_current=lambda _: "yes")
    with pytest.raises(ModuleRecipientRejected, match="required"):
        review(pin, value, root, public, publisher_key_lookup=None)
    with pytest.raises(ModuleRecipientRejected):
        replace(pin, catalog_revision=True)


def test_source_is_never_a_permission_or_publisher_signature(tmp_path):
    pin, value, root, public = fixture(tmp_path, source="AUTHORIZED_PEER")
    with pytest.raises(ModuleRecipientRejected, match="source"):
        review(pin, value, root, public, remote_source_current=None)
    attacker_key = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    with pytest.raises(ModuleRecipientRejected, match="key pin"):
        review(pin, value, root, attacker_key)



def test_expiry_at_exact_catalog_deadline_denies_before_any_file_or_key_read(tmp_path):
    pin, value, root, public = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="expired"):
        review(
            pin, value, root / "absent", public,
            now=pin.metadata_fresh_until,
            catalog_admit=lambda _: calls.append("catalog") or True,
            publisher_current=lambda _: calls.append("publisher") or True,
            publisher_key_lookup=lambda _: calls.append("key") or public,
        )
    assert calls == []
