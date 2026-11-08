"""D028-01 / LIB-01-02 precursor: signed offline Core-free seed policy.

This verifies signed fixture bytes and package exclusions, not a clean-host
native bootstrap. Actual Windows/Debian12 host evidence belongs to Team E.
"""
from __future__ import annotations

from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import shutil
import tomllib
import zipfile

import pytest

from sofia.platform.ops.platform_installer_offline_seed import (
    review_core_free_offline_seed,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.sdk.artifact import ArtifactReference
from sofia.sdk.platform_release import PlatformReleaseAsset
from test.test_ops_platform_installer_bundle import reviewed  # shared disposable test fixture

pytestmark = pytest.mark.pkg_ops
ROOT = Path(__file__).resolve().parents[1]


def test_package_manifest_separates_platform_sdk_and_optional_core():
    manifest = tomllib.loads((ROOT / "packaging/components.toml").read_text())
    components = manifest["components"]
    assert components["sdk"]["distribution"] == "sofia-sdk"
    assert components["platform"]["distribution"] == "sofia-platform"
    assert components["core"]["distribution"] == "sofia-core"
    assert "sofia.core" not in components["platform"]["packages"]
    assert "sofia.core" not in components["sdk"]["packages"]
    assert "sofia-core" not in components["platform"]["dependencies"]
    assert "sofia-core" not in components["sdk"]["dependencies"]


def test_signed_offline_seed_reviews_without_install_or_download(reviewed, tmp_path):
    builder, root, manifest, params = reviewed
    review = review_core_free_offline_seed(
        root, **params, source_kind="offline_media",
    )
    assert review["review_kind"] == "CORE_FREE_OFFLINE_SEED_ONLY"
    assert review["manifest_sha256"] == manifest.digest
    assert review["neutral_components"] == ("sofia-sdk", "sofia-platform")
    assert review["optional_core_count"] == 0
    assert review["optional_module_count"] == 0
    assert review["model_count"] == 0
    assert review["network_requested"] is False
    assert review["installation_performed"] is False
    assert review["service_registered"] is False
    assert not (tmp_path / "sofia.db").exists()


@pytest.mark.parametrize("source", ("Internet", "hub", "peer", "unverified_cache", ""))
def test_offline_seed_refuses_remote_or_unreviewed_source(reviewed, source):
    builder, root, manifest, params = reviewed
    with pytest.raises(PlatformReleaseRejected, match="explicitly local"):
        review_core_free_offline_seed(root, **params, source_kind=source)


@pytest.mark.parametrize("bad_package", ("sofia-core", "ollama", "sofia-modules", "sofia-ada-lyra"))
def test_even_validly_signed_seed_cannot_smuggle_optional_core_or_model_dependency(
    reviewed, tmp_path, bad_package,
):
    builder, root, manifest, params = reviewed
    # Software test signer is deliberately NOT production trust.
    target = tmp_path / ("offline-seed-" + bad_package)
    shutil.copytree(root, target)
    wheel_name = bad_package.replace("-", "_") + "-1.0.0-py3-none-any.whl"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            bad_package.replace("-", "_") + "-1.0.0.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {bad_package}\nVersion: 1.0.0\n",
        )
    raw = buffer.getvalue()
    (target / "assets" / wheel_name).write_bytes(raw)
    addition = PlatformReleaseAsset(
        "dependency",
        ArtifactReference(wheel_name, sha256(raw).hexdigest(), len(raw)),
    )
    modified = replace(manifest, assets=manifest.assets + (addition,))
    signature = b64encode(builder._key.sign(modified.digest.encode("ascii"))).decode("ascii")
    (target / "release-manifest.json").write_bytes(modified.canonical_bytes)
    (target / "release-signature.json").write_text(json.dumps({
        "signer_key_id": builder.signer_key_id,
        "signature_b64": signature,
    }))
    with pytest.raises(PlatformReleaseRejected, match="personal Core/model"):
        review_core_free_offline_seed(target, **params)


def test_offline_seed_requires_independent_root_and_exact_signed_source(reviewed):
    builder, root, manifest, params = reviewed
    altered = dict(params, trusted_key_sha256="f" * 64)
    with pytest.raises(PlatformReleaseRejected, match="fingerprint"):
        review_core_free_offline_seed(root, **altered)
    altered = dict(params, expected_source_sha="0" * 40)
    with pytest.raises(PlatformReleaseRejected):
        review_core_free_offline_seed(root, **altered)


@pytest.mark.parametrize("defect", ("traversal", "case-duplicate", "core-nested", "symlink"))
def test_signed_offline_seed_rejects_malicious_dependency_archive(
    reviewed, tmp_path, defect,
):
    import stat
    builder, root, manifest, params = reviewed
    target = tmp_path / ("malicious-dependency-" + defect)
    shutil.copytree(root, target)
    name = "neutral_extra-1.0.0-py3-none-any.whl"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("neutral_extra-1.0.0.dist-info/METADATA",
                         "Metadata-Version: 2.1\nName: neutral-extra\nVersion: 1.0.0\n")
        if defect == "traversal":
            archive.writestr("../sofia.db", "forbidden")
        elif defect == "case-duplicate":
            archive.writestr("Neutral/Config", "a")
            archive.writestr("neutral/config", "b")
        elif defect == "core-nested":
            archive.writestr("vendor/sofia/core/private.py", "forbidden")
        else:
            link = zipfile.ZipInfo("package/redirect")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../private")
    raw = buffer.getvalue()
    (target / "assets" / name).write_bytes(raw)
    extra = PlatformReleaseAsset(
        "dependency", ArtifactReference(name, sha256(raw).hexdigest(), len(raw)),
    )
    signed = replace(manifest, assets=manifest.assets + (extra,))
    signature = b64encode(builder._key.sign(signed.digest.encode("ascii"))).decode("ascii")
    (target / "release-manifest.json").write_bytes(signed.canonical_bytes)
    (target / "release-signature.json").write_text(json.dumps({
        "signer_key_id": builder.signer_key_id,
        "signature_b64": signature,
    }))
    with pytest.raises(PlatformReleaseRejected):
        review_core_free_offline_seed(target, **params)
