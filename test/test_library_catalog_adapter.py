"""D028-00 candidate catalog / D028-02-04 module recipient boundary tests.

Fake callbacks stand in for A's signed-index service and B's independent
publisher/archive verification. They are NOT host or publisher authentication.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.modules.library_catalog_adapter import review_selected_library_catalog_module
from sofia.platform.modules.library_recipient import ModuleRecipientRejected
from sofia.platform.modules import DependencyRequirement, OperationProfileKind
from test.test_module_compatibility_v1 import target
from test.test_module_package_v1 import manifest, signed


NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def fixture(tmp_path, *, dependencies=()):
    root = tmp_path / "candidate"
    root.mkdir()
    asset = root / "module.py"
    asset.write_bytes(b"MODULE = 'safe synthetic fixture'\n")
    signer = Ed25519PrivateKey.generate()
    pub = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    value = signed(manifest(
        (("module.py", sha256(asset.read_bytes()).hexdigest()),),
        module_id="org.sofia.catalog-module", dependencies=dependencies,
    ), signer)
    manifest_digest = value.package_identity_digest()
    content_digest = "b" * 64  # test-only archive SHA pinned by simulated B verifier
    item = {
        "artifact_id": "artifact:module-approved", "kind": "module",
        "version": value.version, "revision": 3,
        "manifest_digest": manifest_digest, "content_digest": content_digest,
        "size_bytes": 4096, "publisher": value.publisher,
        "signer_key_id": "key:fixture-trusted", "signature_scheme": "ed25519",
        "signature_receipt_ref": "receipt:fixture-reviewed",
        "target_os_arch": "linux-x86_64", "sdk_range": "1.x",
        "abi_range": "1.x", "license_distribution": "permitted",
        "data_class": "public", "distribution_allowed": True,
    }
    data = {
        "catalog_revision": 22, "catalog_generation": 5,
        "catalog_fresh_until": (NOW + timedelta(seconds=30)).isoformat(),
        "target_platform_id": "platform:fixture-client",
        "source": {
            "kind": "LOCAL_VERIFIED_CACHE", "source_id": "source:local",
            "last_observed_at": NOW.isoformat(), "status": "CURRENT",
        },
        "page": {"limit": 4, "next_cursor": None, "cursor_state": "CURRENT"},
        "items": [item],
    }
    return data, value, root, pub


def review(data, value, root, pub, **changes):
    item = data["items"][0]
    kwargs = dict(
        catalog_data=data, selected_artifact_id=item["artifact_id"],
        selected_manifest_digest=value.package_identity_digest(),
        selected_content_digest="b" * 64,
        bound_platform_id="platform:fixture-client",
        expected_catalog_generation=5, minimum_catalog_revision=22,
        manifest=value, package_root=root, now=NOW,
        target=target(), profile=OperationProfileKind.OBSERVE,
        signed_index_admit=lambda _: True, signed_content_admit=lambda *_: True,
        current_host_scope_admit=lambda *_: True,
        license_policy_admit=lambda _: True,
        remote_source_preflight=lambda _: True,
        signer_binding_admit=lambda signer, ref: signer == "key:fixture-trusted"
                                               and ref == "trust:owner-modules",
        os_sdk_abi_admit=lambda row, host:
            row["target_os_arch"] == host.os_arch
            and row["sdk_range"] == "1.x" and row["abi_range"] == "1.x",
        catalog_admit=lambda _: True,
        publisher_key_lookup=lambda _: pub,
        publisher_current=lambda _: True,
    )
    kwargs.update(changes)
    return review_selected_library_catalog_module(**kwargs)


def test_exact_signed_index_selection_local_signature_and_abi(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    before = (root / "module.py").read_bytes()
    reviewed = review(data, value, root, pub)
    assert reviewed.package_digest == value.package_identity_digest()
    assert reviewed.manifest.module_id == "org.sofia.catalog-module"
    assert (root / "module.py").read_bytes() == before
    assert not hasattr(reviewed, "install") and not hasattr(reviewed, "activate")


@pytest.mark.parametrize("field,wrong", [
    ("manifest_digest", "a" * 64),
    ("content_digest", "c" * 64),
    ("kind", "core_runtime"),
    ("signature_scheme", "ecdsa-p256"),
    ("size_bytes", 512 * 1024 * 1024 + 1),
    ("size_bytes", True),
    ("license_distribution", "restricted"),
    ("data_class", "private"),
])
def test_unselected_or_incompatible_signed_item_never_admits(tmp_path, field, wrong):
    data, value, root, pub = fixture(tmp_path)
    data["items"][0][field] = wrong
    with pytest.raises(ModuleRecipientRejected):
        review(data, value, root, pub)


def test_index_signature_denial_precedes_archive_or_key_access(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="index"):
        review(data, value, root / "absent", pub,
               signed_index_admit=lambda _: calls.append("index") or False,
               signed_content_admit=lambda *_: calls.append("archive") or True,
               publisher_key_lookup=lambda _: calls.append("key") or pub)
    assert calls == ["index"]


def test_wrong_host_generation_catalog_revision_and_stale_source_refused(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    with pytest.raises(ModuleRecipientRejected, match="target"):
        review(data, value, root, pub, bound_platform_id="platform:attacker")
    with pytest.raises(ModuleRecipientRejected, match="generation"):
        review(data, value, root, pub, expected_catalog_generation=6)
    with pytest.raises(ModuleRecipientRejected, match="revision"):
        review(data, value, root, pub, minimum_catalog_revision=23)
    data["source"]["status"] = "STALE"
    with pytest.raises(ModuleRecipientRejected, match="stale"):
        review(data, value, root, pub)


def test_explicit_selection_requires_exact_digest_and_unique_item(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    with pytest.raises(ModuleRecipientRejected, match="selection"):
        review(data, value, root, pub, selected_artifact_id="artifact:other")
    with pytest.raises(ModuleRecipientRejected, match="content"):
        review(data, value, root, pub, selected_content_digest="d" * 64)
    data["items"].append(dict(data["items"][0]))
    with pytest.raises(ModuleRecipientRejected, match="ambiguous"):
        review(data, value, root, pub)


def test_abi_signer_revocation_and_archive_verification_required(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    with pytest.raises(ModuleRecipientRejected, match="ABI"):
        review(data, value, root, pub, os_sdk_abi_admit=lambda *_: False)
    with pytest.raises(ModuleRecipientRejected, match="signing key"):
        review(data, value, root, pub, signer_binding_admit=lambda *_: False)
    with pytest.raises(ModuleRecipientRejected, match="archive"):
        review(data, value, root, pub, signed_content_admit=lambda *_: False)
    with pytest.raises(ModuleRecipientRejected, match="publisher"):
        review(data, value, root, pub, publisher_current=lambda _: False)


def test_wrong_local_ed25519_signature_and_modified_file_fail(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    other = Ed25519PrivateKey.generate()
    bad = signed(value, other)
    with pytest.raises(ModuleRecipientRejected, match="signature"):
        review(data, bad, root, pub)
    (root / "module.py").write_bytes(b"wrong bytes")
    with pytest.raises(ModuleRecipientRejected, match="digest"):
        review(data, value, root, pub)


def test_dependency_must_be_satisfied_by_canonical_compatible_module(tmp_path):
    data, value, root, pub = fixture(
        tmp_path, dependencies=(DependencyRequirement(
            "org.sofia.other", "1.0.0", "2.0.0",
        ),),
    )
    data["items"][0]["manifest_digest"] = value.package_identity_digest()
    with pytest.raises(ModuleRecipientRejected, match="dependency missing"):
        review(data, value, root, pub)


def test_hub_peer_license_and_offline_are_not_signed_execution_grants(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    data["source"]["kind"] = "AUTHORIZED_PEER"
    with pytest.raises(ModuleRecipientRejected, match="source"):
        review(data, value, root, pub)
    data["items"][0]["license_distribution"] = "non_redistributable"
    data["items"][0]["distribution_allowed"] = False
    with pytest.raises(ModuleRecipientRejected, match="license"):
        review(data, value, root, pub, remote_source_current=lambda _: True)
    data["source"]["kind"] = "OFFICIAL_REMOTE"
    data["items"][0]["license_distribution"] = "permitted"
    data["items"][0]["distribution_allowed"] = True
    with pytest.raises(ModuleRecipientRejected, match="Internet"):
        review(data, value, root, pub, remote_source_current=lambda _: True)



def test_denied_current_safe_scope_has_zero_archive_or_key_access(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="SAFE/STOP"):
        review(
            data, value, root / "missing", pub,
            current_host_scope_admit=lambda *_: calls.append("safe") or False,
            signed_content_admit=lambda *_: calls.append("content") or True,
            publisher_key_lookup=lambda _: calls.append("key") or pub,
        )
    assert calls == ["safe"]


def test_remote_offer_disallowed_even_with_permitted_license(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    data["source"]["kind"] = "AUTHORIZED_PEER"
    data["items"][0]["distribution_allowed"] = False
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="remote offer"):
        review(
            data, value, root / "missing", pub,
            remote_source_current=lambda _: True,
            signed_content_admit=lambda *_: calls.append("archive") or True,
        )
    assert calls == []


def test_revoked_peer_preflight_prevents_first_byte_validation(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    data["source"]["kind"] = "AUTHORIZED_PEER"
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="enrolled source"):
        review(
            data, value, root / "missing", pub,
            remote_source_preflight=lambda _: calls.append("peer") or False,
            signed_content_admit=lambda *_: calls.append("archive") or True,
            remote_source_current=lambda _: True,
        )
    assert calls == ["peer"]


def test_license_policy_denial_before_key_or_archive(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="license"):
        review(
            data, value, root / "missing", pub,
            license_policy_admit=lambda _: calls.append("license") or False,
            signed_content_admit=lambda *_: calls.append("archive") or True,
            publisher_key_lookup=lambda _: calls.append("key") or pub,
        )
    assert calls == ["license"]



def test_revoked_publisher_never_reads_candidate_archive(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="revocation"):
        review(
            data, value, root / "missing", pub,
            publisher_current=lambda _: calls.append("revocation") or False,
            signed_content_admit=lambda *_: calls.append("archive") or True,
            publisher_key_lookup=lambda _: calls.append("key") or pub,
        )
    assert calls == ["revocation"]


def test_current_safe_rechecked_after_archive_review_for_midflight_revocation(tmp_path):
    data, value, root, pub = fixture(tmp_path)
    calls = []
    with pytest.raises(ModuleRecipientRejected, match="catalog"):
        review(
            data, value, root, pub,
            current_host_scope_admit=lambda *_: calls.append("initial-safe") or True,
            signed_content_admit=lambda *_: calls.append("archive") or True,
            catalog_admit=lambda _: calls.append("final-safe") or False,
        )
    assert calls == ["initial-safe", "archive", "final-safe"]
    # Verified local bytes are not accepted for install after SAFE revocation.
