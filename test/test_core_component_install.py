"""G2-B.3 authorized Core component installation tests.

Covers the authority gate, signature evidence, content compatibility,
downgrade rejection, platform-local receipt registry, and the overlay health
probe against the live Platform.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.platform.ops.bootstrap import InstallAuthority
from sofia.platform.ops.component_install import (
    CORE_DISTRIBUTION,
    CoreComponentArtifact,
    CoreComponentInstallError,
    CoreComponentInstaller,
    CoreComponentRegistry,
    verify_core_component_content,
)
from sofia.platform.ops.platform_install import InstallOutcome
from sofia.platform.verify.component_artifacts import (
    build_all_components,
    build_component,
    load_component_manifest,
    repository_root,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def component_wheels(tmp_path_factory) -> dict[str, Path]:
    output_dir = tmp_path_factory.mktemp("component-install-wheels")
    return build_all_components(output_dir, repo=ROOT)


def _artifact(wheel_path: Path, version: str = "0.1.0") -> CoreComponentArtifact:
    import hashlib

    return CoreComponentArtifact(
        artifact_id=CORE_DISTRIBUTION,
        version=version,
        sha256=hashlib.sha256(wheel_path.read_bytes()).hexdigest(),
        signature_verified=True,
        signer_key_id="release-signing-key",
        source="offline-cache",
    )


def test_authorized_install_records_platform_local_receipt(tmp_path, component_wheels):
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    installer = CoreComponentInstaller(registry)
    receipt = installer.execute(
        _artifact(component_wheels["core"]),
        component_wheels["core"],
        authority=InstallAuthority.OPERATOR_APPROVED,
        approval_id="approval:core-1",
    )
    assert receipt.outcome is InstallOutcome.SUCCEEDED
    assert receipt.health_verified is True
    recorded = registry.installed(CORE_DISTRIBUTION)
    assert recorded is not None
    assert recorded.version == "0.1.0"
    assert recorded.artifact_sha256 == receipt.artifact_sha256


def test_install_requires_explicit_authority(tmp_path, component_wheels):
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    installer = CoreComponentInstaller(registry)
    with pytest.raises(PermissionError):
        installer.execute(
            _artifact(component_wheels["core"]),
            component_wheels["core"],
            authority=InstallAuthority.NONE,
        )
    with pytest.raises(PermissionError):
        installer.execute(
            _artifact(component_wheels["core"]),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
        )
    assert registry.installed(CORE_DISTRIBUTION) is None


def test_unverified_signature_evidence_is_rejected(tmp_path):
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    with pytest.raises(CoreComponentInstallError):
        CoreComponentArtifact(
            artifact_id=CORE_DISTRIBUTION,
            version="0.1.0",
            sha256="0" * 64,
            signature_verified=False,
            signer_key_id="release-signing-key",
            source="offline-cache",
        )


def test_registry_rejects_canonical_state_database(tmp_path):
    with pytest.raises(ValueError):
        CoreComponentRegistry(tmp_path / "sofia.db")


def test_core_wheel_missing_platform_dependency_is_rejected(tmp_path, component_wheels):
    components = load_component_manifest(ROOT)
    incompatible = dict(components)
    incompatible["core"] = {**components["core"], "dependencies": ["sofia-sdk"]}
    output_dir = tmp_path / "incompatible"
    output_dir.mkdir()
    wheel = build_component(
        "core", output_dir, repo=ROOT, manifest=incompatible,
    )
    with pytest.raises(CoreComponentInstallError, match="incompatible"):
        verify_core_component_content(wheel)


def test_core_wheel_containing_platform_files_is_rejected(tmp_path):
    components = load_component_manifest(ROOT)
    violating = dict(components)
    violating["core"] = {**components["core"], "packages": ["sofia.platform"]}
    output_dir = tmp_path / "violating"
    output_dir.mkdir()
    wheel = build_component(
        "core", output_dir, repo=ROOT, manifest=violating,
    )
    with pytest.raises(CoreComponentInstallError, match="must not contain"):
        verify_core_component_content(wheel)


def test_downgrade_requires_rollback_authority(tmp_path, component_wheels):
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    installer = CoreComponentInstaller(registry)
    newer_output = tmp_path / "newer"
    newer_output.mkdir()
    newer_wheel = build_component(
        "core", newer_output, repo=ROOT, version="0.2.0",
    )
    installer.execute(
        _artifact(newer_wheel, version="0.2.0"),
        newer_wheel,
        authority=InstallAuthority.STANDING_POLICY,
    )
    with pytest.raises(CoreComponentInstallError, match="downgrade"):
        installer.execute(
            _artifact(component_wheels["core"], version="0.1.0"),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="approval:core-2",
        )
