"""Governed synthetic Core lifecycle contracts.

These tests use the existing signed component wheel fixture and a fake process
backend. No real Sofía Core, personal state or production credential is used.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.ops.component_install import (
    CORE_DISTRIBUTION,
    CoreComponentArtifact,
    CoreComponentInstallError,
    CoreComponentInstaller,
    CoreComponentRegistry,
    Ed25519ComponentSignatureVerifier,
)
from sofia.platform.ops.platform_install import InstallAuthority
from sofia.platform.ops.synthetic_core_lifecycle import (
    CoreProcessObservation,
    SyntheticCoreBackendUncertain,
    SyntheticCoreLifecycle,
    SyntheticCoreLifecycleConflict,
    SyntheticCoreOperation,
    SyntheticCoreOutcome,
    SyntheticCorePendingReconciliation,
    SyntheticCoreState,
)
from sofia.platform.verify.component_artifacts import build_component

ROOT = Path(__file__).resolve().parents[1]
SIGNER_KEY_ID = "release-signing-key"
PLATFORM = str(uuid4())
OWNER = "owner:synthetic-core-tests"


@pytest.fixture(scope="module")
def core_wheel(tmp_path_factory) -> Path:
    return build_component(
        "core", tmp_path_factory.mktemp("synthetic-core-wheels"), repo=ROOT
    )


@pytest.fixture(scope="module")
def signer() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.fixture(scope="module")
def verifier(signer: Ed25519PrivateKey) -> Ed25519ComponentSignatureVerifier:
    public_pem = signer.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return Ed25519ComponentSignatureVerifier({SIGNER_KEY_ID: public_pem})


def _artifact(
    wheel: Path,
    signer: Ed25519PrivateKey,
    *,
    key_id: str = SIGNER_KEY_ID,
) -> CoreComponentArtifact:
    import base64
    from hashlib import sha256

    digest = sha256(wheel.read_bytes()).hexdigest()
    return CoreComponentArtifact(
        artifact_id=CORE_DISTRIBUTION,
        version="0.1.0",
        sha256=digest,
        signature_b64=base64.b64encode(
            signer.sign(digest.encode("ascii"))
        ).decode(),
        signer_key_id=key_id,
        source="synthetic-offline-cache",
    )


class FakeBackend:
    def __init__(self) -> None:
        self.running: dict[str, int] = {}
        self.start_calls = 0
        self.stop_calls = 0
        self.start_mode = "running"
        self.stop_mode = "stopped"
        self.observe_unknown = False

    def start(self, *, core_id: str, lineage_id: str, generation: int):
        self.start_calls += 1
        self.running[core_id] = generation
        if self.start_mode == "raise_after_start":
            raise RuntimeError("simulated crash after process start")
        if self.start_mode == "unknown":
            return CoreProcessObservation.UNKNOWN
        if self.start_mode == "stopped":
            self.running.pop(core_id, None)
            return CoreProcessObservation.STOPPED
        return CoreProcessObservation.RUNNING

    def stop(self, *, core_id: str, lineage_id: str, generation: int):
        self.stop_calls += 1
        self.running.pop(core_id, None)
        if self.stop_mode == "unknown":
            return CoreProcessObservation.UNKNOWN
        return CoreProcessObservation.STOPPED

    def observe(self, *, core_id: str, lineage_id: str, generation: int):
        if self.observe_unknown:
            return CoreProcessObservation.UNKNOWN
        return (
            CoreProcessObservation.RUNNING
            if core_id in self.running
            else CoreProcessObservation.STOPPED
        )


class RecordingAuthorizer:
    def __init__(self) -> None:
        self.allowed = True
        self.calls: list[tuple[str, str, int]] = []

    def __call__(self, operation: str, fingerprint: str, generation: int) -> bool:
        self.calls.append((operation, fingerprint, generation))
        return self.allowed


def _lifecycle(
    tmp_path: Path,
    verifier: Ed25519ComponentSignatureVerifier,
    backend: FakeBackend,
    *,
    store_path: Path | None = None,
    authorizer: RecordingAuthorizer | None = None,
    freshness: list[bool] | None = None,
    platform_healthy: bool = True,
) -> SyntheticCoreLifecycle:
    installer = CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "core-components.sqlite"),
        verifier,
        installation_root=tmp_path / "installed-components",
        authorization_check=lambda authority, approval_id, artifact, operation: True,
    )
    auth = authorizer or RecordingAuthorizer()
    fresh = freshness if freshness is not None else [True]
    return SyntheticCoreLifecycle(
        store_path=store_path or (tmp_path / "synthetic-core-lifecycle.sqlite"),
        platform_id=PLATFORM,
        installer=installer,
        backend=backend,
        authorization=auth,
        freshness=lambda: fresh[0],
        platform_health_check=lambda: platform_healthy,
    )


def _install(
    lifecycle: SyntheticCoreLifecycle,
    wheel: Path,
    signer: Ed25519PrivateKey,
    *,
    core_id: str | None = None,
    lineage_id: str | None = None,
    artifact: CoreComponentArtifact | None = None,
):
    core_id = core_id or str(uuid4())
    lineage_id = lineage_id or str(uuid4())
    receipt = lifecycle.install(
        owner_id=OWNER,
        core_id=core_id,
        lineage_id=lineage_id,
        artifact=artifact or _artifact(wheel, signer),
        wheel_path=wheel,
        authority=InstallAuthority.STANDING_POLICY,
    )
    return core_id, lineage_id, receipt


def test_install_signed_synthetic_core_binds_distinct_durable_identity(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    authorizer = RecordingAuthorizer()
    lifecycle = _lifecycle(tmp_path, verifier, backend, authorizer=authorizer)
    core_id, lineage_id, receipt = _install(lifecycle, core_wheel, signer)

    assert receipt.operation is SyntheticCoreOperation.INSTALL
    assert receipt.outcome is SyntheticCoreOutcome.SUCCEEDED
    assert receipt.state is SyntheticCoreState.INSTALLED
    assert receipt.generation == 0
    assert receipt.install_receipt is not None
    assert receipt.install_receipt.artifact_sha256 == receipt.artifact_sha256

    binding = lifecycle.store.binding(OWNER, core_id)
    assert binding is not None
    assert binding.core_id != lifecycle.platform_id
    assert binding.lineage_id not in {binding.core_id, lifecycle.platform_id}
    assert binding.artifact_sha256 == receipt.artifact_sha256
    assert lifecycle.installer.registry.installed(CORE_DISTRIBUTION) is not None
    assert authorizer.calls == [
        ("install", receipt.artifact_sha256, 0)
    ]

    restarted = _lifecycle(
        tmp_path, verifier, backend, store_path=lifecycle.store.path
    )
    assert restarted.store.binding(OWNER, core_id) == binding


def test_duplicate_and_forged_artifacts_are_denied(
    tmp_path, core_wheel, signer, verifier
):
    lifecycle = _lifecycle(tmp_path, verifier, FakeBackend())
    core_id, lineage_id, _ = _install(lifecycle, core_wheel, signer)
    artifact = _artifact(core_wheel, signer)

    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.install(
            owner_id=OWNER,
            core_id=core_id,
            lineage_id=lineage_id,
            artifact=artifact,
            wheel_path=core_wheel,
            authority=InstallAuthority.STANDING_POLICY,
        )
    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.install(
            owner_id=OWNER,
            core_id=str(uuid4()),
            lineage_id=str(uuid4()),
            artifact=artifact,
            wheel_path=core_wheel,
            authority=InstallAuthority.STANDING_POLICY,
        )

    forged_key = Ed25519PrivateKey.generate()
    forged_core = str(uuid4())
    with pytest.raises(CoreComponentInstallError):
        lifecycle.install(
            owner_id="owner:forged-artifact",
            core_id=forged_core,
            lineage_id=str(uuid4()),
            artifact=_artifact(core_wheel, forged_key),
            wheel_path=core_wheel,
            authority=InstallAuthority.STANDING_POLICY,
        )
    assert lifecycle.store.binding("owner:forged-artifact", forged_core) is None
    assert lifecycle.store.bindings("owner:forged-artifact") == ()
    assert len(lifecycle.store.bindings(OWNER)) == 1


def test_activation_requires_authorization_and_freshness(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    authorizer = RecordingAuthorizer()
    freshness = [True]
    lifecycle = _lifecycle(
        tmp_path, verifier, backend,
        authorizer=authorizer, freshness=freshness,
    )
    core_id, _, receipt = _install(lifecycle, core_wheel, signer)

    authorizer.allowed = False
    with pytest.raises(PermissionError):
        lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
    assert backend.start_calls == 0
    assert lifecycle.store.binding(OWNER, core_id).state is SyntheticCoreState.INSTALLED

    authorizer.allowed = True
    freshness[0] = False
    with pytest.raises(PermissionError):
        lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
    assert backend.start_calls == 0

    freshness[0] = True
    started = lifecycle.start(
        owner_id=OWNER, core_id=core_id, expected_generation=0
    )
    assert started.state is SyntheticCoreState.ACTIVE
    assert started.generation == 1
    assert backend.start_calls == 1
    assert ("start", receipt.artifact_sha256, 0) in authorizer.calls


def test_one_writer_fencing_rejects_duplicate_and_stale_start(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, _, _ = _install(lifecycle, core_wheel, signer)

    first = lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    assert first.generation == 1
    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert backend.start_calls == 1

    other = _lifecycle(
        tmp_path, verifier, backend, store_path=lifecycle.store.path
    )
    with pytest.raises(SyntheticCoreLifecycleConflict):
        other.start(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert backend.start_calls == 1

    stopped = lifecycle.stop(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert stopped.state is SyntheticCoreState.STOPPED
    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)

    second = lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert second.generation == 2
    assert backend.start_calls == 2


def test_stop_is_idempotent_with_truthful_outcome(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, _, _ = _install(lifecycle, core_wheel, signer)

    never_started = lifecycle.stop(
        owner_id=OWNER, core_id=core_id, expected_generation=0
    )
    assert never_started.outcome is SyntheticCoreOutcome.ALREADY_STOPPED
    assert backend.stop_calls == 0

    lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    stopped = lifecycle.stop(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert stopped.outcome is SyntheticCoreOutcome.SUCCEEDED
    assert stopped.state is SyntheticCoreState.STOPPED
    assert backend.stop_calls == 1

    again = lifecycle.stop(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert again.outcome is SyntheticCoreOutcome.ALREADY_STOPPED
    assert backend.stop_calls == 1
    assert core_id not in backend.running


def test_detach_and_removal_preserve_platform_installation(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    lifecycle = _lifecycle(tmp_path, verifier, backend, platform_healthy=True)
    core_id, _, _ = _install(lifecycle, core_wheel, signer)

    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.remove(owner_id=OWNER, core_id=core_id, expected_generation=0)

    lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    with pytest.raises(SyntheticCoreLifecycleConflict):
        lifecycle.detach(owner_id=OWNER, core_id=core_id, expected_generation=1)
    lifecycle.stop(owner_id=OWNER, core_id=core_id, expected_generation=1)

    detached = lifecycle.detach(
        owner_id=OWNER, core_id=core_id, expected_generation=1
    )
    assert detached.state is SyntheticCoreState.DETACHED
    removed = lifecycle.remove(
        owner_id=OWNER, core_id=core_id, expected_generation=1
    )
    assert removed.outcome is SyntheticCoreOutcome.SUCCEEDED
    assert removed.state is SyntheticCoreState.REMOVED
    assert removed.platform_healthy is True
    assert lifecycle.installer.registry.installed(CORE_DISTRIBUTION) is not None
    assert lifecycle.store.binding(OWNER, core_id).state is SyntheticCoreState.REMOVED


def test_crash_after_start_is_reconciled_without_a_second_writer(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    backend.start_mode = "raise_after_start"
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, _, _ = _install(lifecycle, core_wheel, signer)

    with pytest.raises(SyntheticCoreBackendUncertain):
        lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    assert backend.start_calls == 1
    assert lifecycle.store.binding(OWNER, core_id).state is SyntheticCoreState.INSTALLED
    assert lifecycle.store.unresolved_operations(core_id)

    restarted = _lifecycle(
        tmp_path, verifier, backend, store_path=lifecycle.store.path
    )
    binding = restarted.store.binding(OWNER, core_id)
    assert binding is not None
    assert binding.state is SyntheticCoreState.ACTIVE
    assert binding.generation == 1
    assert restarted.store.unresolved_operations(core_id) == ()
    assert backend.start_calls == 1

    with pytest.raises(SyntheticCoreLifecycleConflict):
        restarted.start(owner_id=OWNER, core_id=core_id, expected_generation=1)
    assert backend.start_calls == 1


def test_unknown_outcome_blocks_blind_retry_until_observed(
    tmp_path, core_wheel, signer, verifier
):
    backend = FakeBackend()
    backend.start_mode = "raise_after_start"
    backend.observe_unknown = True
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, _, _ = _install(lifecycle, core_wheel, signer)

    with pytest.raises(SyntheticCoreBackendUncertain):
        lifecycle.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    assert backend.start_calls == 1
    assert lifecycle.store.unresolved_operations(core_id)

    restarted = _lifecycle(
        tmp_path, verifier, backend, store_path=lifecycle.store.path
    )
    with pytest.raises(SyntheticCorePendingReconciliation):
        restarted.start(owner_id=OWNER, core_id=core_id, expected_generation=0)
    assert backend.start_calls == 1
    assert restarted.store.unresolved_operations(core_id)

    backend.observe_unknown = False
    receipts = restarted.reconcile()
    assert len(receipts) == 1
    assert receipts[0].outcome is SyntheticCoreOutcome.SUCCEEDED
    binding = restarted.store.binding(OWNER, core_id)
    assert binding is not None
    assert binding.state is SyntheticCoreState.ACTIVE
    assert binding.generation == 1
    assert restarted.store.unresolved_operations(core_id) == ()
    assert backend.start_calls == 1
