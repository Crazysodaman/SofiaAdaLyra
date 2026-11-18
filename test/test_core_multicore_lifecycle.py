"""Verified Core definition registration and governed lifecycle adapters."""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.core.multicore.lifecycle import (
    LifecycleAuthorizationDenied,
    LifecycleEvidenceError,
    LifecycleOperation,
    LifecycleRegistrationConflict,
    LifecycleRegistrationRequired,
    MulticoreCoreLifecycle,
    MulticoreLifecycleError,
)
from sofia.core.multicore.profiles import mack_core_profile
from sofia.platform.ops.core_definition import CoreDefinitionVerifier
from sofia.platform.ops.platform_install import InstallAuthority
from sofia.platform.ops.synthetic_core_lifecycle import (
    CoreProcessObservation,
    SyntheticCoreBinding,
    SyntheticCoreLifecycleReceipt,
    SyntheticCoreOperation,
    SyntheticCoreOutcome,
    SyntheticCorePendingOperation,
    SyntheticCoreState,
)

MACK_ID = UUID("5e2c8b6d-7f90-4182-bdc4-cf3a4b5c6d7e")
OWNER = "owner:multicore-tests"
LINEAGE_ID = UUID("6f3d9c7e-8a01-4293-ced5-d04b5c6d7e8f")
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
ASSETS_ROOT = Path(__file__).resolve().parents[1] / "src" / "sofia" / "core"
RUNTIME_SHA = "a" * 64


@dataclass
class _Artifact:
    sha256: str = "b" * 64
    version: str = "0.1.0"


class _Auth:
    def __init__(self) -> None:
        self.allowed = True
        self.calls: list[tuple[str, str, str, int]] = []

    def __call__(self, operation, core_id, fingerprint, generation):
        self.calls.append((operation, core_id, fingerprint, generation))
        return self.allowed


class _Store:
    def __init__(self) -> None:
        self.bindings: dict[tuple[str, str], SyntheticCoreBinding] = {}
        self.pending: dict[str, tuple[SyntheticCorePendingOperation, ...]] = {}

    def binding(self, owner_id, core_id):
        return self.bindings.get((owner_id, core_id))

    def unresolved_operations(self, core_id=None):
        if core_id is None:
            return tuple(
                operation for values in self.pending.values() for operation in values
            )
        return self.pending.get(core_id, ())


class _Installer:
    def __init__(self) -> None:
        self.roots: set[tuple[str, str]] = set()

    def installed_component_root(self, version, artifact_sha256):
        return Path("/virtual/core") if (version, artifact_sha256) in self.roots else None


class _Backend:
    def __init__(self) -> None:
        self.running: set[str] = set()
        self.unknown = False

    def observe(self, *, core_id, lineage_id, generation):
        if self.unknown:
            return CoreProcessObservation.UNKNOWN
        return (
            CoreProcessObservation.RUNNING
            if core_id in self.running
            else CoreProcessObservation.STOPPED
        )


class _FakeSynthetic:
    def __init__(self) -> None:
        self.store = _Store()
        self.installer = _Installer()
        self.backend = _Backend()
        self.install_calls: list[dict[str, object]] = []
        self.activate_calls: list[dict[str, object]] = []
        self.stop_calls: list[dict[str, object]] = []
        self.remove_calls: list[dict[str, object]] = []
        self.reconcile_calls = 0
        self.install_receipt = None
        self.activate_receipt = None
        self.stop_receipt = None
        self.remove_receipt = None
        self.reconcile_receipts: tuple[SyntheticCoreLifecycleReceipt, ...] = ()

    def install(self, **kwargs):
        self.install_calls.append(kwargs)
        if self.install_receipt is not None:
            return self.install_receipt
        return _receipt(
            operation="install", outcome=SyntheticCoreOutcome.SUCCEEDED,
            state=SyntheticCoreState.INSTALLED, generation=0,
            artifact_sha256=kwargs["artifact"].sha256,
        )

    def activate(self, **kwargs):
        self.activate_calls.append(kwargs)
        if self.activate_receipt is not None:
            return self.activate_receipt
        return _receipt(
            operation="start", outcome=SyntheticCoreOutcome.SUCCEEDED,
            state=SyntheticCoreState.ACTIVE, generation=1,
        )

    def stop(self, **kwargs):
        self.stop_calls.append(kwargs)
        if self.stop_receipt is not None:
            return self.stop_receipt
        return _receipt(
            operation="stop", outcome=SyntheticCoreOutcome.SUCCEEDED,
            state=SyntheticCoreState.STOPPED, generation=1,
        )

    def remove(self, **kwargs):
        self.remove_calls.append(kwargs)
        if self.remove_receipt is not None:
            return self.remove_receipt
        return _receipt(
            operation="remove", outcome=SyntheticCoreOutcome.SUCCEEDED,
            state=SyntheticCoreState.REMOVED, generation=1,
        )

    def reconcile(self):
        self.reconcile_calls += 1
        return self.reconcile_receipts


def _receipt(
    *, operation: str, outcome: SyntheticCoreOutcome, state: SyntheticCoreState,
    generation: int, artifact_sha256: str = "b" * 64,
) -> SyntheticCoreLifecycleReceipt:
    return SyntheticCoreLifecycleReceipt(
        operation=SyntheticCoreOperation(operation),
        outcome=outcome,
        owner_id=OWNER,
        core_id=str(MACK_ID),
        lineage_id=str(LINEAGE_ID),
        generation=generation,
        state=state,
        artifact_sha256=artifact_sha256,
        happened_at=NOW,
        detail="test receipt",
    )


def _binding(
    *, state: SyntheticCoreState = SyntheticCoreState.INSTALLED,
    artifact_sha256: str = "b" * 64, version: str = "0.1.0",
    generation: int = 0,
) -> SyntheticCoreBinding:
    return SyntheticCoreBinding(
        owner_id=OWNER,
        core_id=str(MACK_ID),
        lineage_id=str(LINEAGE_ID),
        generation=generation,
        state=state,
        artifact_sha256=artifact_sha256,
        version=version,
        installed_at=NOW,
        updated_at=NOW,
    )


def _signed_definition(profile, *, revision: int = 1):
    definition = profile.core_definition(
        revision=revision, runtime_release_sha256=RUNTIME_SHA,
    )
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    signature = b64encode(private.sign(definition.digest.encode("ascii"))).decode()
    return definition, CoreDefinitionVerifier({"operator": public}), signature


def _registered_adapter(tmp_path, *, revision: int = 1):
    profile = mack_core_profile(MACK_ID)
    definition, verifier, signature = _signed_definition(profile, revision=revision)
    auth = _Auth()
    synthetic = _FakeSynthetic()
    adapter = MulticoreCoreLifecycle(synthetic=synthetic, authorization=auth, clock=lambda: NOW)
    registration = adapter.register_definition(
        profile, definition, verifier=verifier, signature_b64=signature,
        signer_key_id="operator", assets_root=ASSETS_ROOT,
        runtime_release_sha256=RUNTIME_SHA, minimum_revision=1,
    )
    return adapter, synthetic, auth, registration


def _wheel() -> Path:
    return Path("/virtual/core-wheel.whl")


def test_definition_registration_reuses_existing_verifier(tmp_path):
    adapter, _, _, registration = _registered_adapter(tmp_path)
    assert registration.profile.descriptor.core_id == MACK_ID
    assert registration.definition.identity.identity_id == MACK_ID
    assert adapter.registration(MACK_ID) is registration
    with pytest.raises(TypeError):
        adapter.register_definition(registration.profile, registration.definition,
            verifier=object(), signature_b64="", signer_key_id="operator",
            assets_root=ASSETS_ROOT, runtime_release_sha256=RUNTIME_SHA,
            minimum_revision=1)


def test_definition_registration_rejects_invalid_or_mismatched_evidence(tmp_path):
    profile = mack_core_profile(MACK_ID)
    definition, verifier, signature = _signed_definition(profile)
    auth = _Auth()
    adapter = MulticoreCoreLifecycle(synthetic=_FakeSynthetic(), authorization=auth)
    with pytest.raises(MulticoreLifecycleError):
        adapter.register_definition(
            profile, definition, verifier=verifier, signature_b64="not-a-signature",
            signer_key_id="operator", assets_root=ASSETS_ROOT,
            runtime_release_sha256=RUNTIME_SHA, minimum_revision=1,
        )
    with pytest.raises(LifecycleRegistrationRequired):
        adapter.registration(MACK_ID)

    other_profile = mack_core_profile(uuid4())
    with pytest.raises(MulticoreLifecycleError):
        adapter.register_definition(
            other_profile, definition, verifier=verifier, signature_b64=signature,
            signer_key_id="operator", assets_root=ASSETS_ROOT,
            runtime_release_sha256=RUNTIME_SHA, minimum_revision=1,
        )


def test_duplicate_registration_of_a_different_definition_conflicts(tmp_path):
    adapter, _, _, first = _registered_adapter(tmp_path)
    profile = first.profile
    definition, verifier, signature = _signed_definition(profile, revision=2)
    with pytest.raises(LifecycleRegistrationConflict):
        adapter.register_definition(
            profile, definition, verifier=verifier, signature_b64=signature,
            signer_key_id="operator", assets_root=ASSETS_ROOT,
            runtime_release_sha256=RUNTIME_SHA, minimum_revision=1,
        )
    same, verifier, signature = _signed_definition(profile, revision=1)
    repeated = adapter.register_definition(
        profile, same, verifier=verifier, signature_b64=signature,
        signer_key_id="operator", assets_root=ASSETS_ROOT,
        runtime_release_sha256=RUNTIME_SHA, minimum_revision=1,
    )
    assert repeated is first


def test_install_and_activate_never_claim_without_receipt_evidence(tmp_path):
    adapter, synthetic, auth, _ = _registered_adapter(tmp_path)
    synthetic.install_receipt = _receipt(
        operation="install", outcome=SyntheticCoreOutcome.FAILED,
        state=SyntheticCoreState.INSTALLED, generation=0,
    )
    with pytest.raises(LifecycleEvidenceError):
        adapter.install(
            owner_id=OWNER, core_id=MACK_ID, lineage_id=LINEAGE_ID,
            artifact=_Artifact(), wheel_path=_wheel(),
            authority=InstallAuthority.STANDING_POLICY,
        )
    synthetic.install_receipt = None
    receipt = adapter.install(
        owner_id=OWNER, core_id=MACK_ID, lineage_id=LINEAGE_ID,
        artifact=_Artifact(), wheel_path=_wheel(),
        authority=InstallAuthority.STANDING_POLICY,
    )
    assert receipt.outcome is SyntheticCoreOutcome.SUCCEEDED
    assert len(synthetic.install_calls) == 2

    synthetic.activate_receipt = _receipt(
        operation="start", outcome=SyntheticCoreOutcome.FAILED,
        state=SyntheticCoreState.ACTIVE, generation=1,
    )
    with pytest.raises(LifecycleEvidenceError):
        adapter.activate(owner_id=OWNER, core_id=MACK_ID, expected_generation=0)
    synthetic.activate_receipt = None
    assert adapter.activate(
        owner_id=OWNER, core_id=MACK_ID, expected_generation=0,
    ).state is SyntheticCoreState.ACTIVE
    assert [call[0] for call in auth.calls] == ["install", "install", "activate", "activate"]


def test_every_source_operation_requires_authorization(tmp_path):
    adapter, synthetic, auth, _ = _registered_adapter(tmp_path)
    synthetic.store.bindings[(OWNER, str(MACK_ID))] = _binding(generation=1)
    auth.allowed = False
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.install(
            owner_id=OWNER, core_id=MACK_ID, lineage_id=LINEAGE_ID,
            artifact=_Artifact(), wheel_path=_wheel(),
            authority=InstallAuthority.STANDING_POLICY,
        )
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.activate(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.status(owner_id=OWNER, core_id=MACK_ID)
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.deactivate(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.recover(core_id=MACK_ID)
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.remove(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)
    assert synthetic.install_calls == []
    assert synthetic.activate_calls == []
    assert synthetic.stop_calls == []
    assert synthetic.remove_calls == []
    assert synthetic.reconcile_calls == 0
    assert {call[0] for call in auth.calls} == {
        "install", "activate", "status", "deactivate", "recover", "remove",
    }


def test_status_reports_only_observed_install_and_process_evidence(tmp_path):
    adapter, synthetic, auth, _ = _registered_adapter(tmp_path)
    empty = adapter.status(owner_id=OWNER, core_id=MACK_ID)
    assert empty.installed is False and empty.active is False
    assert empty.state is None

    synthetic.store.bindings[(OWNER, str(MACK_ID))] = _binding(
        state=SyntheticCoreState.ACTIVE, generation=1,
    )
    synthetic.backend.running.add(str(MACK_ID))
    no_root = adapter.status(owner_id=OWNER, core_id=MACK_ID)
    assert no_root.installed is False
    assert no_root.active is False
    assert any("process running" in item for item in no_root.uncertainties)

    synthetic.installer.roots.add(("0.1.0", "b" * 64))
    synthetic.backend.running.clear()
    stopped = adapter.status(owner_id=OWNER, core_id=MACK_ID)
    assert stopped.installed is True
    assert stopped.active is False
    assert any("observed stopped" in item for item in stopped.evidence)

    synthetic.backend.running.add(str(MACK_ID))
    active = adapter.status(owner_id=OWNER, core_id=MACK_ID)
    assert active.installed is True and active.active is True

    synthetic.backend.unknown = True
    unknown = adapter.status(owner_id=OWNER, core_id=MACK_ID)
    assert unknown.active is False
    assert any("unknown" in item for item in unknown.uncertainties)


def test_deactivate_and_remove_verify_stopped_and_removed_evidence(tmp_path):
    adapter, synthetic, _, _ = _registered_adapter(tmp_path)
    synthetic.store.bindings[(OWNER, str(MACK_ID))] = _binding(
        state=SyntheticCoreState.ACTIVE, generation=1,
    )
    stopped = adapter.deactivate(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)
    assert stopped.state is SyntheticCoreState.STOPPED

    synthetic.stop_receipt = _receipt(
        operation="stop", outcome=SyntheticCoreOutcome.SUCCEEDED,
        state=SyntheticCoreState.ACTIVE, generation=1,
    )
    with pytest.raises(LifecycleEvidenceError):
        adapter.deactivate(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)

    synthetic.remove_receipt = _receipt(
        operation="remove", outcome=SyntheticCoreOutcome.COMPONENT_RETAINED,
        state=SyntheticCoreState.STOPPED, generation=1,
    )
    with pytest.raises(LifecycleEvidenceError):
        adapter.remove(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)
    synthetic.remove_receipt = None
    removed = adapter.remove(owner_id=OWNER, core_id=MACK_ID, expected_generation=1)
    assert removed.state is SyntheticCoreState.REMOVED


def test_recovery_is_authorized_per_pending_core_and_never_retries_blindly(tmp_path):
    adapter, synthetic, auth, _ = _registered_adapter(tmp_path)
    pending = SyntheticCorePendingOperation(
        operation_id="op-1", owner_id=OWNER, core_id=str(MACK_ID),
        lineage_id=str(LINEAGE_ID), operation=SyntheticCoreOperation.START,
        generation=2, expected_generation=1, artifact_sha256="b" * 64,
        started_at=NOW, observed="", detail="",
    )
    synthetic.store.pending[str(MACK_ID)] = (pending,)
    auth.allowed = False
    with pytest.raises(LifecycleAuthorizationDenied):
        adapter.recover(core_id=MACK_ID)
    assert synthetic.reconcile_calls == 0
    auth.allowed = True
    assert adapter.recover(core_id=MACK_ID) == ()
    assert synthetic.reconcile_calls == 1
    assert auth.calls[-1] == ("recover", str(MACK_ID), "b" * 64, 1)


def test_operations_require_verified_registration_first(tmp_path):
    synthetic = _FakeSynthetic()
    adapter = MulticoreCoreLifecycle(synthetic=synthetic, authorization=_Auth())
    with pytest.raises(LifecycleRegistrationRequired):
        adapter.install(
            owner_id=OWNER, core_id=MACK_ID, lineage_id=LINEAGE_ID,
            artifact=_Artifact(), wheel_path=_wheel(),
            authority=InstallAuthority.STANDING_POLICY,
        )
    with pytest.raises(LifecycleRegistrationRequired):
        adapter.activate(owner_id=OWNER, core_id=MACK_ID, expected_generation=0)
    with pytest.raises(LifecycleRegistrationRequired):
        adapter.deactivate(owner_id=OWNER, core_id=MACK_ID, expected_generation=0)
    with pytest.raises(LifecycleRegistrationRequired):
        adapter.remove(owner_id=OWNER, core_id=MACK_ID, expected_generation=0)
    assert synthetic.install_calls == []
    assert synthetic.activate_calls == []
    assert synthetic.stop_calls == []
    assert synthetic.remove_calls == []


def test_platform_definition_and_lifecycle_imports_without_core():
    repository = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository / "src")
    code = (
        "import importlib.abc, sys\n"
        "class BlockCore(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'sofia.core' or fullname.startswith('sofia.core.'):\n"
        "            raise ImportError(fullname)\n"
        "        return None\n"
        "sys.meta_path.insert(0, BlockCore())\n"
        "import sofia.platform.ops.core_definition\n"
        "import sofia.platform.ops.synthetic_core_lifecycle\n"
        "assert not [name for name in sys.modules if name == 'sofia.core' "
        "or name.startswith('sofia.core.')]\n"
        "print('CORE-FREE-PLATFORM-OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], env=environment,
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "CORE-FREE-PLATFORM-OK" in result.stdout
