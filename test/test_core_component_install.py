"""G2-B.3 authorized Core component installation tests.

Covers the authority gate, trusted signature verification (forged, wrong
signer, tampered), content compatibility, downgrade rejection, platform-local
receipt registry, and the overlay health probe against the live Platform.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.bootstrap import InstallAuthority
from sofia.platform.ops.component_install import (
    CORE_DISTRIBUTION,
    CoreComponentArtifact,
    CoreComponentInstallError,
    CoreComponentInstaller,
    CoreComponentRegistry,
    Ed25519ComponentSignatureVerifier,
    verify_core_component_content,
)
from sofia.platform.ops.platform_install import InstallOperation, InstallOutcome
from sofia.platform.verify.component_artifacts import (
    build_all_components,
    build_component,
    load_component_manifest,
    repository_root,
)

ROOT = Path(__file__).resolve().parents[1]

_SIGNER_KEY_ID = "release-signing-key"


@pytest.fixture(scope="session")
def component_wheels(tmp_path_factory) -> dict[str, Path]:
    output_dir = tmp_path_factory.mktemp("component-install-wheels")
    return build_all_components(output_dir, repo=ROOT)


@pytest.fixture(scope="session")
def signer() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture(scope="session")
def verifier(signer: Ed25519PrivateKey) -> Ed25519ComponentSignatureVerifier:
    public_pem = signer.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return Ed25519ComponentSignatureVerifier({_SIGNER_KEY_ID: public_pem})


def _artifact(
    wheel_path: Path,
    signer: Ed25519PrivateKey,
    *,
    version: str = "0.1.0",
    digest: str | None = None,
    key_id: str = _SIGNER_KEY_ID,
) -> CoreComponentArtifact:
    observed = Path(wheel_path).read_bytes()
    from hashlib import sha256

    observed_digest = sha256(observed).hexdigest()
    return CoreComponentArtifact(
        artifact_id=CORE_DISTRIBUTION,
        version=version,
        sha256=digest if digest is not None else observed_digest,
        signature_b64=base64.b64encode(
            signer.sign(observed_digest.encode("ascii"))
        ).decode(),
        signer_key_id=key_id,
        source="offline-cache",
    )


def _installer(tmp_path, verifier) -> CoreComponentInstaller:
    return CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "core-components.sqlite"),
        verifier,
        installation_root=tmp_path / "installed-components",
        authorization_check=lambda authority, approval_id, artifact, operation: True,
    )


def test_authorized_install_records_platform_local_receipt(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    receipt = installer.execute(
        _artifact(component_wheels["core"], signer),
        component_wheels["core"],
        authority=InstallAuthority.OPERATOR_APPROVED,
        approval_id="approval:core-1",
    )
    assert receipt.outcome is InstallOutcome.SUCCEEDED
    assert receipt.health_verified is True
    recorded = installer.registry.installed(CORE_DISTRIBUTION)
    assert recorded is not None
    assert recorded.version == "0.1.0"
    assert recorded.artifact_sha256 == receipt.artifact_sha256


def test_install_requires_explicit_authority(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    with pytest.raises(PermissionError):
        installer.execute(
            _artifact(component_wheels["core"], signer),
            component_wheels["core"],
            authority=InstallAuthority.NONE,
        )
    with pytest.raises(PermissionError):
        installer.execute(
            _artifact(component_wheels["core"], signer),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
        )
    assert installer.registry.installed(CORE_DISTRIBUTION) is None


def test_forged_signature_is_rejected(tmp_path, component_wheels, signer, verifier):
    installer = _installer(tmp_path, verifier)
    forged = Ed25519PrivateKey.generate()
    with pytest.raises(CoreComponentInstallError, match="does not verify"):
        installer.execute(
            _artifact(component_wheels["core"], forged),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="approval:forged",
        )


def test_wrong_signer_key_is_rejected(tmp_path, component_wheels, signer, verifier):
    installer = _installer(tmp_path, verifier)
    with pytest.raises(CoreComponentInstallError, match="not trusted"):
        installer.execute(
            _artifact(component_wheels["core"], signer, key_id="untrusted-key"),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="approval:untrusted",
        )


def test_tampered_wheel_is_rejected(tmp_path, component_wheels, signer, verifier):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    tampered = tmp_path / "tampered-core.whl"
    tampered.write_bytes(component_wheels["core"].read_bytes() + b"\x00tamper")
    from hashlib import sha256

    tampered_digest = sha256(tampered.read_bytes()).hexdigest()
    with pytest.raises(CoreComponentInstallError, match="digest does not match"):
        installer.execute(
            artifact,
            tampered,
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="approval:tampered",
        )
    stale_signature = base64.b64encode(
        signer.sign(artifact.sha256.encode("ascii"))
    ).decode()
    with pytest.raises(CoreComponentInstallError, match="does not verify"):
        installer.execute(
            CoreComponentArtifact(
                artifact_id=CORE_DISTRIBUTION,
                version="0.1.0",
                sha256=tampered_digest,
                signature_b64=stale_signature,
                signer_key_id=_SIGNER_KEY_ID,
                source="offline-cache",
            ),
            tampered,
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="approval:tampered-2",
        )


def test_core_component_rejects_wrong_artifact_identity(
    tmp_path, component_wheels, signer, verifier
):
    from dataclasses import replace

    installer = _installer(tmp_path, verifier)
    artifact = replace(
        _artifact(component_wheels["core"], signer),
        artifact_id="sofia-other",
    )
    with pytest.raises(CoreComponentInstallError, match="artifact ID"):
        installer.execute(
            artifact,
            component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
        )
    assert installer.registry.installed(CORE_DISTRIBUTION) is None


def test_core_component_rejects_signed_version_mismatch(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(
        component_wheels["core"], signer, version="9.9.9",
    )
    with pytest.raises(CoreComponentInstallError, match="version.*wheel metadata"):
        installer.execute(
            artifact,
            component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
        )
    assert installer.registry.installed(CORE_DISTRIBUTION) is None


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


def test_downgrade_requires_rollback_authority(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    newer_output = tmp_path / "newer"
    newer_output.mkdir()
    newer_wheel = build_component(
        "core", newer_output, repo=ROOT, version="0.2.0",
    )
    installer.execute(
        _artifact(newer_wheel, signer, version="0.2.0"),
        newer_wheel,
        authority=InstallAuthority.STANDING_POLICY,
    )
    with pytest.raises(CoreComponentInstallError, match="downgrade"):
        installer.execute(
            _artifact(component_wheels["core"], signer, version="0.1.0"),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="approval:core-2",
        )


def test_core_install_requires_physical_target(tmp_path, component_wheels, signer, verifier):
    installer = CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "registry.sqlite"),
        verifier,
        authorization_check=lambda authority, approval_id, artifact, operation: True,
    )
    with pytest.raises(CoreComponentInstallError, match="installation_root"):
        installer.execute(_artifact(component_wheels["core"], signer), component_wheels["core"], authority=InstallAuthority.STANDING_POLICY)
    assert installer.registry.installed() is None


def test_core_install_interrupted_records_no_success(tmp_path, component_wheels, signer, verifier, monkeypatch):
    import subprocess
    installer = _installer(tmp_path, verifier)
    monkeypatch.setattr(installer, "_verify_health", lambda wheel: True)
    real_run = subprocess.run
    observed_install = []

    def interrupted(*args, **kwargs):
        command = args[0]
        if "-m" in command and "pip" in command and "install" in command:
            observed_install.append(command)
            raise subprocess.CalledProcessError(1, command)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", interrupted)
    with pytest.raises(CoreComponentInstallError, match="physical Core installation failed"):
        installer.execute(_artifact(component_wheels["core"], signer), component_wheels["core"], authority=InstallAuthority.STANDING_POLICY)
    assert observed_install, "pip installation must be reached before interruption"
    assert installer.registry.installed() is None


def test_core_install_rejects_tampered_installed_bytes(tmp_path, component_wheels, signer, verifier, monkeypatch):
    installer = _installer(tmp_path, verifier)
    monkeypatch.setattr(installer, "_verify_health", lambda wheel: True)
    original = installer._verify_installed_bytes
    def corrupt(root, artifact, wheel):
        original(root, artifact, wheel)
        core = next(root.rglob("sofia/core/constitution/constitution.md"))
        core.write_bytes(b"tampered")
        original(root, artifact, wheel)
    monkeypatch.setattr(installer, "_verify_installed_bytes", corrupt)
    with pytest.raises(CoreComponentInstallError, match="installed Core bytes mismatch"):
        installer.execute(_artifact(component_wheels["core"], signer), component_wheels["core"], authority=InstallAuthority.STANDING_POLICY)
    assert installer.registry.installed() is None



def test_core_install_without_trusted_authorizer_fails_closed(
    tmp_path, component_wheels, signer, verifier
):
    installer = CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "registry.sqlite"),
        verifier,
        installation_root=tmp_path / "installed-components",
    )
    with pytest.raises(PermissionError, match="trusted Core installation authorizer"):
        installer.execute(
            _artifact(component_wheels["core"], signer),
            component_wheels["core"],
            authority=InstallAuthority.OPERATOR_APPROVED,
            approval_id="invented-but-nonempty",
        )
    assert installer.registry.installed() is None
    assert not (tmp_path / "installed-components").exists()


@pytest.mark.parametrize(
    "authority,approval_id",
    [
        (InstallAuthority.OPERATOR_APPROVED, "fabricated-approval"),
        (InstallAuthority.STANDING_POLICY, None),
    ],
)
def test_core_install_requires_independent_approval_or_policy_proof(
    tmp_path, component_wheels, signer, verifier, authority, approval_id
):
    observed = []

    def deny(incoming_authority, incoming_approval_id, incoming_artifact, incoming_operation):
        observed.append(
            (incoming_authority, incoming_approval_id, incoming_artifact.sha256, incoming_operation)
        )
        return False

    installer = CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "registry.sqlite"),
        verifier,
        installation_root=tmp_path / "installed-components",
        authorization_check=deny,
    )
    artifact = _artifact(component_wheels["core"], signer)
    with pytest.raises(PermissionError, match="authority denied"):
        installer.execute(
            artifact, component_wheels["core"],
            authority=authority, approval_id=approval_id,
        )
    assert observed == [
        (authority, approval_id, artifact.sha256, InstallOperation.INSTALL)
    ]
    assert installer.registry.installed() is None
    assert not (tmp_path / "installed-components").exists()
