"""Real-subprocess contracts for the supervised synthetic Core backend.

The entrypoint fixture under ``test/fixtures`` imports no Sofía production
state. Every test uses disposable temporary directories and deterministically
closes spawned processes.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.core_worker.synthetic_backend import (
    SyntheticCoreBackendError,
    SyntheticCoreProcessBackend,
)
from sofia.platform.ops.component_install import (
    CORE_DISTRIBUTION,
    CoreComponentArtifact,
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
    SyntheticCoreState,
)
from sofia.platform.verify.component_artifacts import build_component

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "test" / "fixtures" / "synthetic_core_entrypoint.py"
SIGNER_KEY_ID = "release-signing-key"
PLATFORM = str(uuid4())
OWNER = "owner:synthetic-core-backend-tests"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def core_wheel(tmp_path_factory) -> Path:
    return build_component(
        "core", tmp_path_factory.mktemp("synthetic-backend-wheels"), repo=ROOT
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

    digest = _digest(wheel)
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


class PlatformHealth:
    def __init__(self, marker: Path) -> None:
        self.marker = marker
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        try:
            return self.marker.is_file()
        except OSError:
            return False


def _backend(
    tmp_path: Path,
    *,
    mode: str = "ready",
    environment: dict[str, str] | None = None,
    entrypoint: Path = ENTRYPOINT,
    entrypoint_sha256: str | None = None,
    readiness_timeout: float = 15.0,
    stop_timeout: float = 5.0,
) -> SyntheticCoreProcessBackend:
    values = {"SOFIA_SYNTHETIC_CORE_MODE": mode}
    if environment:
        values.update(environment)
    return SyntheticCoreProcessBackend(
        argv=[sys.executable, str(entrypoint)],
        entrypoint_path=entrypoint,
        entrypoint_sha256=entrypoint_sha256 or _digest(entrypoint),
        working_root=tmp_path / "core-work",
        working_directory=tmp_path / "core-work" / "runtime",
        environment=values,
        readiness_timeout=readiness_timeout,
        stop_timeout=stop_timeout,
    )


def _lifecycle(
    tmp_path: Path,
    verifier: Ed25519ComponentSignatureVerifier,
    backend: SyntheticCoreProcessBackend,
    *,
    store_path: Path | None = None,
    platform_health: PlatformHealth | None = None,
) -> SyntheticCoreLifecycle:
    installer = CoreComponentInstaller(
        CoreComponentRegistry(tmp_path / "core-components.sqlite"),
        verifier,
        installation_root=tmp_path / "installed-components",
        authorization_check=lambda authority, approval_id, artifact, operation: True,
    )
    return SyntheticCoreLifecycle(
        store_path=store_path or (tmp_path / "synthetic-core-lifecycle.sqlite"),
        platform_id=PLATFORM,
        installer=installer,
        backend=backend,
        authorization=lambda operation, fingerprint, generation: True,
        freshness=lambda: True,
        platform_health_check=(
            platform_health if platform_health is not None else (lambda: True)
        ),
    )


def _install(
    lifecycle: SyntheticCoreLifecycle,
    wheel: Path,
    signer: Ed25519PrivateKey,
    *,
    core_id: str | None = None,
    lineage_id: str | None = None,
) -> tuple[str, str]:
    core_id = core_id or str(uuid4())
    lineage_id = lineage_id or str(uuid4())
    lifecycle.install(
        owner_id=OWNER,
        core_id=core_id,
        lineage_id=lineage_id,
        artifact=_artifact(wheel, signer),
        wheel_path=wheel,
        authority=InstallAuthority.STANDING_POLICY,
    )
    return core_id, lineage_id


def _wait_for_stopped(
    backend: SyntheticCoreProcessBackend, *, core_id: str, lineage_id: str,
    generation: int, timeout: float = 5.0,
) -> CoreProcessObservation:
    deadline = time.monotonic() + timeout
    observed = backend.observe(
        core_id=core_id, lineage_id=lineage_id, generation=generation
    )
    while observed is CoreProcessObservation.RUNNING and time.monotonic() < deadline:
        time.sleep(0.02)
        observed = backend.observe(
            core_id=core_id, lineage_id=lineage_id, generation=generation
        )
    return observed


def test_real_backend_starts_observes_and_stops(tmp_path):
    backend = _backend(tmp_path)
    core_id, lineage_id = str(uuid4()), str(uuid4())
    try:
        assert backend.observe(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.STOPPED

        assert backend.start(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.RUNNING
        pid = backend.pid_for(core_id)
        assert pid is not None and pid != os.getpid()
        assert backend.generation_for(core_id) == 1
        assert backend.observe(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.RUNNING

        assert backend.stop(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.STOPPED
        assert backend.pid_for(core_id) is None
        assert backend.observe(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.STOPPED
        assert backend.stop(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.STOPPED
        assert pid not in backend.running_pids()
    finally:
        backend.close()


def test_duplicate_start_is_denied_by_real_backend(tmp_path, core_wheel, signer, verifier):
    backend = _backend(tmp_path)
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, lineage_id = _install(lifecycle, core_wheel, signer)
    try:
        first = lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
        pid = backend.pid_for(core_id)
        assert first.generation == 1
        assert pid is not None

        with pytest.raises(SyntheticCoreLifecycleConflict):
            lifecycle.start(
                owner_id=OWNER, core_id=core_id, expected_generation=1
            )
        other = _lifecycle(
            tmp_path, verifier, backend, store_path=lifecycle.store.path
        )
        with pytest.raises(SyntheticCoreLifecycleConflict):
            other.start(
                owner_id=OWNER, core_id=core_id, expected_generation=1
            )
        assert backend.pid_for(core_id) == pid
    finally:
        backend.close()


def test_forced_crash_is_detected_and_restart_advances_generation(
    tmp_path, core_wheel, signer, verifier,
):
    backend = _backend(tmp_path, mode="crash-after-ready")
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, lineage_id = _install(lifecycle, core_wheel, signer)
    try:
        started = lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
        first_pid = backend.pid_for(core_id)
        assert started.generation == 1
        assert first_pid is not None

        observed = _wait_for_stopped(
            backend, core_id=core_id, lineage_id=lineage_id, generation=1
        )
        assert observed is CoreProcessObservation.STOPPED
        assert backend.pid_for(core_id) is None

        stopped = lifecycle.stop(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert stopped.outcome is SyntheticCoreOutcome.SUCCEEDED
        assert stopped.state is SyntheticCoreState.STOPPED
        again = lifecycle.stop(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert again.outcome is SyntheticCoreOutcome.ALREADY_STOPPED

        restarted = lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert restarted.generation == 2
        assert restarted.state is SyntheticCoreState.ACTIVE
        assert backend.pid_for(core_id) not in {None, first_pid}
    finally:
        backend.close()


def test_crash_before_readiness_requires_reconciliation(
    tmp_path, core_wheel, signer, verifier,
):
    backend = _backend(tmp_path, mode="crash-before-ready")
    lifecycle = _lifecycle(tmp_path, verifier, backend)
    core_id, _ = _install(lifecycle, core_wheel, signer)
    try:
        with pytest.raises(SyntheticCoreBackendUncertain):
            lifecycle.start(
                owner_id=OWNER, core_id=core_id, expected_generation=0
            )

        pending = lifecycle.store.unresolved_operations(core_id)
        assert len(pending) == 1
        assert pending[0].operation is SyntheticCoreOperation.START
        assert lifecycle.store.binding(OWNER, core_id).state is SyntheticCoreState.INSTALLED
        operation = lifecycle.store.operations(OWNER, core_id)[-1]
        assert operation["operation"] == "start"
        assert operation["outcome"] is None

        reconciled = _lifecycle(
            tmp_path, verifier, backend, store_path=lifecycle.store.path
        )
        assert reconciled.store.unresolved_operations(core_id) == ()
        binding = reconciled.store.binding(OWNER, core_id)
        assert binding is not None
        assert binding.state is SyntheticCoreState.INSTALLED
        assert binding.generation == 0
        operation = reconciled.store.operations(OWNER, core_id)[-1]
        assert operation["outcome"] == SyntheticCoreOutcome.FAILED.value
        assert operation["observed"] == "stopped"

        ready_backend = _backend(tmp_path)
        retry = _lifecycle(
            tmp_path, verifier, ready_backend, store_path=lifecycle.store.path
        )
        try:
            restarted = retry.start(
                owner_id=OWNER, core_id=core_id, expected_generation=0
            )
            assert restarted.generation == 1
            assert restarted.state is SyntheticCoreState.ACTIVE
        finally:
            ready_backend.close()
    finally:
        backend.close()


def test_detach_preserves_files_and_removal_reports_platform_health(
    tmp_path, core_wheel, signer, verifier,
):
    platform_marker = tmp_path / "platform-health.json"
    platform_marker.write_text('{"status":"healthy"}', encoding="utf-8")
    health = PlatformHealth(platform_marker)
    backend = _backend(tmp_path)
    lifecycle = _lifecycle(
        tmp_path, verifier, backend, platform_health=health
    )
    core_id, _ = _install(lifecycle, core_wheel, signer)
    try:
        lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
        lifecycle.stop(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        sentinel = backend.working_directory / "core-sentinel.bin"
        sentinel.write_bytes(b"detached-evidence")
        binding = lifecycle.store.binding(OWNER, core_id)
        component_root = lifecycle.installer.installation_root / (
            f"core-{binding.version}-{binding.artifact_sha256}"
        )

        detached = lifecycle.detach(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert detached.state is SyntheticCoreState.DETACHED
        assert sentinel.read_bytes() == b"detached-evidence"
        assert component_root.is_dir()
        assert lifecycle.installer.registry.installed(CORE_DISTRIBUTION) is not None

        removed = lifecycle.remove(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert removed.outcome is SyntheticCoreOutcome.SUCCEEDED
        assert removed.state is SyntheticCoreState.REMOVED
        assert removed.platform_healthy is True
        assert removed.removal_receipt is not None
        assert sentinel.read_bytes() == b"detached-evidence"
        assert not component_root.exists()
        assert lifecycle.installer.registry.installed(CORE_DISTRIBUTION) is None
        assert lifecycle.store.binding(OWNER, core_id).state is SyntheticCoreState.REMOVED
    finally:
        backend.close()


def test_platform_health_is_independent_of_core_stop_and_removal(
    tmp_path, core_wheel, signer, verifier,
):
    platform_status = tmp_path / "platform-status.json"
    platform_status.write_text('{"platform":"healthy"}', encoding="utf-8")
    snapshot = _digest(platform_status)
    health = PlatformHealth(platform_status)
    backend = _backend(tmp_path)
    lifecycle = _lifecycle(
        tmp_path, verifier, backend, platform_health=health
    )
    core_id, _ = _install(lifecycle, core_wheel, signer)
    try:
        lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
        lifecycle.stop(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert health() is True
        calls_before = health.calls

        removed = lifecycle.remove(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        assert removed.platform_healthy is True
        assert health.calls == calls_before + 1
        assert health() is True
        assert _digest(platform_status) == snapshot
        assert lifecycle.platform_id == PLATFORM
        assert removed.removal_receipt is not None
        assert lifecycle.installer.registry.installed(CORE_DISTRIBUTION) is None
    finally:
        backend.close()


def test_backend_does_not_leak_inherited_secrets_into_child(
    tmp_path, monkeypatch,
):
    dump_path = tmp_path / "child-environment.json"
    monkeypatch.setenv("SOFIA_TEST_SECRET_TOKEN", "must-not-reach-child")
    backend = _backend(
        tmp_path,
        environment={"SOFIA_SYNTHETIC_CORE_ENV_DUMP": str(dump_path)},
    )
    core_id, lineage_id = str(uuid4()), str(uuid4())
    try:
        assert backend.start(
            core_id=core_id, lineage_id=lineage_id, generation=1
        ) is CoreProcessObservation.RUNNING
        assert dump_path.is_file()
        child_environment = json.loads(dump_path.read_text("utf-8"))
        assert "SOFIA_TEST_SECRET_TOKEN" not in child_environment
        assert "must-not-reach-child" not in child_environment.values()
        assert child_environment["SOFIA_SYNTHETIC_CORE_MODE"] == "ready"
        assert child_environment["SOFIA_SYNTHETIC_CORE_GENERATION"] == "1"
    finally:
        backend.close()

    with pytest.raises(ValueError, match="credential-like"):
        _backend(
            tmp_path / "rejected",
            environment={"SERVICE_TOKEN": "must-be-refused"},
        )


def test_backend_rejects_path_traversal_identifiers(tmp_path):
    backend = _backend(tmp_path)
    try:
        with pytest.raises(ValueError, match="path-safe"):
            backend.start(
                core_id="..\\escape",
                lineage_id=str(uuid4()),
                generation=1,
            )
        with pytest.raises(ValueError, match="path-safe"):
            backend.observe(
                core_id="core/../../escape",
                lineage_id=str(uuid4()),
                generation=1,
            )
        assert backend.running_pids() == ()
    finally:
        backend.close()


def test_backend_rejects_tampered_entrypoint_before_spawn(tmp_path):
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_text(
        "import time\nwhile True:\n    time.sleep(0.05)\n", encoding="utf-8"
    )
    backend = _backend(
        tmp_path,
        entrypoint=entrypoint,
        entrypoint_sha256=_digest(entrypoint),
    )
    entrypoint.write_text("raise SystemExit(0)\n", encoding="utf-8")

    core_id, lineage_id = str(uuid4()), str(uuid4())
    with pytest.raises(SyntheticCoreBackendError, match="integrity"):
        backend.start(core_id=core_id, lineage_id=lineage_id, generation=1)
    assert backend.pid_for(core_id) is None
    assert backend.running_pids() == ()
    backend.close()
