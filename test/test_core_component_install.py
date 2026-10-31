"""G2-B.3 authorized Core component installation tests.

Covers the authority gate, trusted signature verification (forged, wrong
signer, tampered), content compatibility, downgrade rejection, platform-local
receipt registry, and the overlay health probe against the live Platform.
"""

from __future__ import annotations

import base64
from pathlib import Path
from datetime import datetime, timezone
import sqlite3

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
    CoreComponentReceipt,
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
    assert installer.verify_installed(
        _artifact(component_wheels["core"], signer), component_wheels["core"]
    ) == receipt


def test_core_restart_verification_rejects_missing_or_tampered_install(
    tmp_path, component_wheels, signer, verifier
):
    import shutil

    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    receipt = installer.execute(
        artifact, component_wheels["core"],
        authority=InstallAuthority.STANDING_POLICY,
    )
    registry = CoreComponentRegistry(installer.registry.path)
    restarted = CoreComponentInstaller(
        registry, verifier, installation_root=installer.installation_root,
    )
    assert restarted.verify_installed(artifact, component_wheels["core"]) == receipt

    installation = installer.installation_root / (
        f"core-{artifact.version}-{artifact.sha256}"
    )
    core_asset = next(installation.rglob("sofia/core/constitution/constitution.md"))
    core_asset.write_bytes(b"tampered after receipt")
    with pytest.raises(CoreComponentInstallError, match="installed Core bytes mismatch"):
        restarted.verify_installed(artifact, component_wheels["core"])
    # Neither the verifier nor the stored receipt can erase tampering evidence.
    assert registry.installed() == receipt

    shutil.rmtree(installation)
    with pytest.raises(CoreComponentInstallError, match="absent or redirected"):
        restarted.verify_installed(artifact, component_wheels["core"])
    assert registry.installed() == receipt


def test_core_restart_verification_rejects_stale_receipt(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    with pytest.raises(CoreComponentInstallError, match="current Core receipt"):
        installer.verify_installed(
            _artifact(component_wheels["core"], signer), component_wheels["core"]
        )


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


def test_core_rollback_rejects_never_installed_signed_artifact(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    monkeypatch.setattr(installer, "_verify_health", lambda _wheel: True)
    with pytest.raises(CoreComponentInstallError, match="previously verified"):
        installer.execute(
            artifact,
            component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
            operation=InstallOperation.ROLLBACK,
        )
    assert installer.registry.history() == ()
    assert not installer.installation_root.exists()


def test_core_rollback_rejects_history_matching_version_but_not_digest(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    from dataclasses import replace

    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    prior = _synthetic_receipt("prior-other-digest", artifact.version)
    installer.registry.record(replace(prior, artifact_sha256="b" * 64))
    monkeypatch.setattr(installer, "_verify_health", lambda _wheel: True)
    with pytest.raises(CoreComponentInstallError, match="previously verified"):
        installer.execute(
            artifact,
            component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
            operation=InstallOperation.ROLLBACK,
        )
    assert installer.registry.history() == (replace(prior, artifact_sha256="b" * 64),)
    assert not installer.installation_root.exists()


def test_core_rollback_exact_signed_history_reuses_verified_artifact(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    from dataclasses import replace
    from hashlib import sha256

    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    old = replace(
        _synthetic_receipt("prior-exact-wheel", artifact.version),
        artifact_sha256=artifact.sha256,
    )
    current = _synthetic_receipt("current-newer", "0.2.0")
    installer.registry.record(old)
    installer.registry.record(current)

    staged = tmp_path / "validated-core-environment"
    observed = []
    monkeypatch.setattr(installer, "_verify_health", lambda _wheel: True)
    monkeypatch.setattr(
        installer, "_stage_verified_install",
        lambda wheel, item: observed.append((wheel.name, sha256(wheel.read_bytes()).hexdigest(), item)) or staged,
    )
    receipt = installer.execute(
        artifact,
        component_wheels["core"],
        authority=InstallAuthority.STANDING_POLICY,
        operation=InstallOperation.ROLLBACK,
    )
    assert observed == [(component_wheels["core"].name, artifact.sha256, artifact)]
    assert receipt.operation is InstallOperation.ROLLBACK
    assert receipt.artifact_sha256 == old.artifact_sha256
    assert installer.registry.history() == (old, current, receipt)
    assert installer.registry.installed() == receipt


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


def _synthetic_receipt(receipt_id: str, version: str) -> CoreComponentReceipt:
    """Storage-only fixture: does not represent authorization or an installed wheel."""
    return CoreComponentReceipt(
        receipt_id=receipt_id,
        artifact_id=CORE_DISTRIBUTION,
        version=version,
        operation=InstallOperation.INSTALL,
        outcome=InstallOutcome.SUCCEEDED,
        artifact_sha256="a" * 64,
        authority=InstallAuthority.STANDING_POLICY,
        approval_id=None,
        health_verified=True,
        installed_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
        detail="storage test fixture",
    )


def test_core_registry_preserves_append_only_install_history_across_restart(tmp_path):
    path = tmp_path / "core-components.sqlite"
    registry = CoreComponentRegistry(path)
    first = _synthetic_receipt("install-first", "0.1.0")
    second = _synthetic_receipt("install-second", "0.2.0")
    registry.record(first)
    registry.record(second)

    assert registry.installed() == second
    assert registry.history() == (first, second)

    restarted = CoreComponentRegistry(path)
    assert restarted.installed() == second
    assert restarted.history() == (first, second)

    # Replaying an already-recorded event cannot overwrite the current
    # projection or its evidence. Both inserts live in one transaction.
    with pytest.raises(sqlite3.IntegrityError):
        restarted.record(first)
    assert restarted.installed() == second
    assert restarted.history() == (first, second)


def test_core_registry_upgrades_legacy_single_receipt_without_duplication(tmp_path):
    path = tmp_path / "core-components.sqlite"
    registry = CoreComponentRegistry(path)
    previous = _synthetic_receipt("install-legacy", "0.1.0")
    registry.record(previous)
    # Simulate the existing pre-history schema by removing its historical row.
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM core_component_receipt_history")
    upgraded = CoreComponentRegistry(path)
    assert upgraded.history() == (previous,)
    assert upgraded.installed() == previous

    upgraded_again = CoreComponentRegistry(path)
    assert upgraded_again.history() == (previous,)


def test_core_registry_records_distinct_attempts_of_same_version(tmp_path):
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    first = _synthetic_receipt("install-attempt-one", "0.1.0")
    second = _synthetic_receipt("install-attempt-two", "0.1.0")
    registry.record(first)
    registry.record(second)
    assert registry.history() == (first, second)
    assert registry.installed() == second



def test_core_install_success_joins_durable_attempt_to_receipt(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    receipt = installer.execute(
        artifact, component_wheels["core"],
        authority=InstallAuthority.STANDING_POLICY,
    )
    attempts = installer.registry.attempts()
    assert len(attempts) == 1
    assert attempts[0].artifact_sha256 == artifact.sha256
    assert attempts[0].outcome is InstallOutcome.SUCCEEDED
    assert attempts[0].completed_at is not None
    assert installer.registry.pending_attempts() == ()
    assert installer.registry.history() == (receipt,)

    restarted = CoreComponentRegistry(installer.registry.path)
    assert restarted.attempts() == attempts
    assert restarted.installed() == receipt


def test_core_install_crash_retains_unresolved_attempt_and_blocks_retry(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    monkeypatch.setattr(installer, "_verify_health", lambda _wheel: True)

    def crash(_wheel, _artifact):
        raise SystemExit("simulated process termination after reservation")

    monkeypatch.setattr(installer, "_stage_verified_install", crash)
    with pytest.raises(SystemExit, match="simulated process termination"):
        installer.execute(
            artifact, component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
        )
    restarted = CoreComponentRegistry(installer.registry.path)
    attempts = restarted.pending_attempts()
    assert len(attempts) == 1
    assert attempts[0].outcome is None
    assert attempts[0].artifact_sha256 == artifact.sha256
    assert restarted.installed() is None
    assert restarted.history() == ()

    with pytest.raises(CoreComponentInstallError, match="unresolved"):
        installer.execute(
            artifact, component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
        )
    assert restarted.pending_attempts() == attempts


def test_core_restart_refuses_stale_success_during_unresolved_stage(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    receipt = installer.execute(
        artifact, component_wheels["core"],
        authority=InstallAuthority.STANDING_POLICY,
    )
    assert installer.verify_installed(artifact, component_wheels["core"]) == receipt

    # A second staging attempt crashes after reserving a pending operation.
    # A previous success receipt alone must not green-light the same Core
    # for a new worker while stage reconciliation is unresolved.
    monkeypatch.setattr(installer, "_verify_health", lambda _wheel: True)

    def crash(_wheel, _artifact):
        raise SystemExit("simulated interrupted re-install")

    monkeypatch.setattr(installer, "_stage_verified_install", crash)
    with pytest.raises(SystemExit):
        installer.execute(
            artifact, component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
        )
    restarted = CoreComponentInstaller(
        CoreComponentRegistry(installer.registry.path),
        verifier,
        installation_root=installer.installation_root,
    )
    assert restarted.registry.installed() == receipt
    assert len(restarted.registry.pending_attempts()) == 1
    with pytest.raises(CoreComponentInstallError, match="reconciliation required"):
        restarted.verify_installed(artifact, component_wheels["core"])


def test_core_install_handled_failure_logged_without_success_receipt(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    monkeypatch.setattr(installer, "_verify_health", lambda _wheel: True)

    def fail(_wheel, _artifact):
        raise OSError("simulated staging I/O failure")

    monkeypatch.setattr(installer, "_stage_verified_install", fail)
    with pytest.raises(OSError, match="simulated staging I/O failure"):
        installer.execute(
            artifact, component_wheels["core"],
            authority=InstallAuthority.STANDING_POLICY,
        )
    attempts = installer.registry.attempts()
    assert len(attempts) == 1
    assert attempts[0].outcome is InstallOutcome.FAILED
    assert "staging I/O failure" in attempts[0].detail
    assert attempts[0].completed_at is not None
    assert installer.registry.pending_attempts() == ()
    assert installer.registry.installed() is None

    # A handled failure should not permanently block an authorized retry.
    retry = installer.registry.begin_attempt(
        artifact, InstallOperation.INSTALL, InstallAuthority.STANDING_POLICY, None
    )
    installer.registry.finish_failed_attempt(retry, "operator cancelled retry")
    assert [a.outcome for a in installer.registry.attempts()] == [
        InstallOutcome.FAILED, InstallOutcome.FAILED,
    ]


def test_core_attempt_receipt_mismatch_rolls_back_transaction(
    tmp_path, component_wheels, signer, verifier
):
    installer = _installer(tmp_path, verifier)
    artifact = _artifact(component_wheels["core"], signer)
    attempt = installer.registry.begin_attempt(
        artifact, InstallOperation.INSTALL, InstallAuthority.STANDING_POLICY, None
    )
    wrong = _synthetic_receipt("wrong-version", "9.9.9")
    with pytest.raises(CoreComponentInstallError, match="does not match pending"):
        installer.registry.record(wrong, attempt_id=attempt)
    assert installer.registry.installed() is None
    assert installer.registry.history() == ()
    assert installer.registry.pending_attempts()[0].attempt_id == attempt


def test_g2_rejects_symlinked_installation_root_before_side_effect(tmp_path, verifier):
    target = tmp_path / "redirect-target"
    target.mkdir()
    redirected = tmp_path / "component-home"
    try:
        redirected.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host cannot create symlink")
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    with pytest.raises(CoreComponentInstallError, match="root must not be redirected"):
        CoreComponentInstaller(
            registry, verifier, installation_root=redirected,
            authorization_check=lambda *_: True,
        )
    assert list(target.iterdir()) == []


def test_g2_rejects_symlinked_installation_parent(tmp_path, verifier):
    target = tmp_path / "external"
    target.mkdir()
    parent = tmp_path / "redirect-parent"
    try:
        parent.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host cannot create symlink")
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    with pytest.raises(CoreComponentInstallError, match="root must not be redirected"):
        CoreComponentInstaller(
            registry, verifier, installation_root=parent / "core",
        )
    assert list(target.iterdir()) == []


def test_g2_install_rejects_changed_wheel_after_signed_review(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    """An approved digest must still match the bytes pip will consume."""
    import shutil

    original = component_wheels["core"]
    wheel = tmp_path / original.name
    shutil.copyfile(original, wheel)
    artifact = _artifact(wheel, signer)
    installer = _installer(tmp_path, verifier)

    def mutate_after_review(_authority, _approval, _artifact, _operation):
        wheel.write_bytes(wheel.read_bytes() + b"changed after authorization")
        return True

    installer.authorization_check = mutate_after_review
    with pytest.raises(
        CoreComponentInstallError, match="changed after signature verification"
    ):
        installer.execute(artifact, wheel, authority=InstallAuthority.STANDING_POLICY)
    assert installer.registry.installed() is None
    assert installer.registry.history() == ()
    assert installer.registry.attempts() == ()
    assert not installer.installation_root.exists()


def test_g2_pip_installs_private_digest_pinned_snapshot(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    """The pip argument cannot be the mutable externally supplied wheel."""
    import subprocess
    from hashlib import sha256

    installer = _installer(tmp_path, verifier)
    wheel = component_wheels["core"]
    artifact = _artifact(wheel, signer)
    real_run = subprocess.run
    observed_snapshots = []

    def inspect_pip(*args, **kwargs):
        command = args[0]
        if "-m" in command and "pip" in command and "install" in command:
            snapshot = Path(command[-1])
            assert snapshot != wheel.resolve()
            assert snapshot.is_file()
            assert sha256(snapshot.read_bytes()).hexdigest() == artifact.sha256
            observed_snapshots.append(snapshot)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", inspect_pip)
    receipt = installer.execute(
        artifact, wheel, authority=InstallAuthority.STANDING_POLICY
    )
    assert receipt.outcome is InstallOutcome.SUCCEEDED
    assert len(observed_snapshots) == 1
    assert installer.verify_installed(artifact, wheel) == receipt


def test_g2_rechecks_installation_parent_if_redirected_after_construction(
    tmp_path, component_wheels, signer, verifier
):
    """A safe constructor check cannot authorize a later symlink swap."""
    parent = tmp_path / "component-home"
    parent.mkdir()
    target = tmp_path / "external"
    target.mkdir()
    registry = CoreComponentRegistry(tmp_path / "core-components.sqlite")
    installer = CoreComponentInstaller(
        registry,
        verifier,
        installation_root=parent / "installed",
        authorization_check=lambda *_: True,
    )
    parent.rmdir()
    try:
        parent.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("host cannot create symlink")
    wheel = component_wheels["core"]
    with pytest.raises(CoreComponentInstallError, match="root must not be redirected"):
        installer.execute(
            _artifact(wheel, signer), wheel,
            authority=InstallAuthority.STANDING_POLICY,
        )
    assert list(target.iterdir()) == []
    assert registry.installed() is None
    assert registry.pending_attempts() == ()


def test_g2_health_probe_never_imports_mutated_external_wheel(
    tmp_path, component_wheels, signer, verifier, monkeypatch
):
    """A changed source after review cannot change the Core health candidate."""
    import shutil
    from hashlib import sha256

    original = component_wheels["core"]
    wheel = tmp_path / original.name
    shutil.copyfile(original, wheel)
    artifact = _artifact(wheel, signer)
    installer = _installer(tmp_path, verifier)
    health_inputs = []

    def probe(reviewed):
        assert reviewed != wheel
        assert reviewed.is_file()
        assert sha256(reviewed.read_bytes()).hexdigest() == artifact.sha256
        health_inputs.append(reviewed.name)
        wheel.write_bytes(wheel.read_bytes() + b"external source mutated")
        return True

    monkeypatch.setattr(installer, "_verify_health", probe)
    receipt = installer.execute(
        artifact, wheel, authority=InstallAuthority.STANDING_POLICY,
    )
    assert receipt.outcome is InstallOutcome.SUCCEEDED
    assert health_inputs == [wheel.name]
    assert installer.registry.installed() == receipt
    # A later reconciliation must still reject the now-invalid source.
    with pytest.raises(CoreComponentInstallError, match="artifact digest mismatch"):
        installer.verify_installed(artifact, wheel)
