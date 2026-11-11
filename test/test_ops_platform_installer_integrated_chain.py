"""Integrated signed B1 code publication -> separately approved native service.

The signed assets and owner proofs are disposable fixtures. The OS backend is
simulated. This is a cross-component source test, NOT a release or host PASS.
No Core, network, live service, or production trust root is created here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import pytest

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore,
)
from sofia.platform.ops.platform_installer_code_install import (
    publish_owner_approved_code, signed_code_publication_request,
)
from sofia.platform.ops.platform_installer_native_transaction import (
    apply_owner_approved_native_service, native_service_operation_request,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier,
)
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels
from test.test_platform_service_session import provision

pytestmark = [
    pytest.mark.pkg_ops,
    pytest.mark.skipif(os.name == "nt", reason="disposable Debian B1 fixture"),
]


def test_signed_code_then_native_service_needs_two_distinct_owner_proofs(
        tmp_path, platform_wheels, canonical_state_path):
    now = datetime.now(timezone.utc)
    builder = SignedReleaseBuilder(tmp_path / "signed", platform_wheels)
    staged, manifest, _signature = builder.stage(revision=6)
    identity_store, initial, state = provision(tmp_path / "host")
    before = InstallationIdentityStore(identity_store.home).load()
    b1 = PlatformInstallationStore(tmp_path / "b1.db")
    release = tmp_path / "installed-v6"
    code = dict(
        staged_candidate=staged, destination=release,
        identity_home=identity_store.home, state_path=canonical_state_path,
        store=b1, verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
    )

    def approve(request, approval_id):
        entry = ExecutionApproval(
            approval_id=approval_id,
            capability=request["capability"],
            request_fingerprint=request["fingerprint"],
            approved_by="person:sparks",
            approved_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(minutes=5),
        )
        record_verified_owner_approval(
            ExecutionApprovalVerifier(canonical_state_path), entry,
        )
        return approval_id

    code_request = signed_code_publication_request(**code)
    publish_approval = approve(
        code_request, "approval:integrated-signed-code-v6",
    )
    code_receipt = publish_owner_approved_code(
        **code, approval_id=publish_approval, now=now,
    )
    assert code_receipt["owner_proof_consumed"] is True
    assert code_receipt["os_service_registered"] is False
    assert code_receipt["core_activated"] is False
    assert b1.checkpoint().active_release_id is None

    native = dict(
        operation="register", store=b1, verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        destination=release, identity_home=identity_store.home,
        local_state=state, canonical_safe_state=canonical_state_path,
    )
    driver = DebianSystemdNativeService()
    effects = []

    def simulated_native_register(spec):
        effects.append((spec.platform_id, spec.manifest_sha256))
        return {
            "schema": "aegis.native-service-receipt.v1",
            "service": spec.service_name, "process_state": "RUNNING",
            "platform_id": spec.platform_id,
            "release_manifest_sha256": spec.manifest_sha256,
            "service_health": "UNKNOWN", "core_activated": False,
        }

    driver.register = simulated_native_register
    with pytest.raises((PlatformInstallationDenied, PermissionError)):
        apply_owner_approved_native_service(
            **native, backend=driver, approval_id=publish_approval, now=now,
        )
    assert effects == []  # Publishing code never authorized OS installation.

    native_request = native_service_operation_request(**native)
    assert native_request["fingerprint"] != code_request["fingerprint"]
    native_approval = approve(
        native_request, "approval:integrated-native-register-v6",
    )
    service_receipt = apply_owner_approved_native_service(
        **native, backend=driver, approval_id=native_approval, now=now,
    )
    assert service_receipt["owner_approval_consumed"] is True
    assert service_receipt["full_health_certified"] is False
    assert service_receipt["service_health"] == "UNKNOWN"
    assert service_receipt["core_activated"] is False
    assert effects == [(initial.identity.canonical_uuid, manifest.digest)]
    assert b1.checkpoint().active_release_id is None
    retained = InstallationIdentityStore(identity_store.home).load()
    assert retained == before

    # Repeat registration cannot reuse an approval or adopt the OS service.
    with pytest.raises((PlatformInstallationDenied, PermissionError)):
        apply_owner_approved_native_service(
            **native, backend=driver, approval_id=native_approval,
            now=now + timedelta(seconds=1),
        )
    assert len(effects) == 1


    # Repair is a different native capability fingerprint from registration.
    # Each phase must be requested and authorized independently.
    native["operation"] = "repair"
    driver.restart_verified = simulated_native_register
    repair_request = native_service_operation_request(**native)
    repair_approval = approve(
        repair_request, "approval:integrated-native-repair-v6",
    )
    repaired = apply_owner_approved_native_service(
        **native, backend=driver, approval_id=repair_approval, now=now,
    )
    assert repaired["process_state"] == "RUNNING"
    assert repaired["service_health"] == "UNKNOWN"
    assert len(effects) == 2

    native["operation"] = "unregister"
    def simulated_native_remove(spec):
        effects.append((spec.platform_id, spec.manifest_sha256))
        return {
            "schema": "aegis.native-service-receipt.v1",
            "service": spec.service_name, "process_state": "REMOVED",
            "platform_id": spec.platform_id,
            "release_manifest_sha256": spec.manifest_sha256,
            "service_health": "UNKNOWN", "core_activated": False,
        }
    driver.stop_and_unregister = simulated_native_remove
    remove_request = native_service_operation_request(**native)
    remove_approval = approve(
        remove_request, "approval:integrated-native-unregister-v6",
    )
    removed = apply_owner_approved_native_service(
        **native, backend=driver, approval_id=remove_approval, now=now,
    )
    assert removed["process_state"] == "REMOVED"
    assert removed["protected_identity_retained"] is True
    assert len(effects) == 3
    assert InstallationIdentityStore(identity_store.home).load() == before

    # Reinstalling the exact same signed release must never mint a new
    # Platform identity or silently activate a Core.
    native["operation"] = "register"
    reinstall_request = native_service_operation_request(**native)
    reinstall_approval = approve(
        reinstall_request, "approval:integrated-native-reinstall-v6",
    )
    again = apply_owner_approved_native_service(
        **native, backend=driver, approval_id=reinstall_approval, now=now,
    )
    assert again["process_state"] == "RUNNING"
    assert again["core_activated"] is False
    assert again["full_health_certified"] is False
    assert len(effects) == 4
    assert InstallationIdentityStore(identity_store.home).load() == before
    assert b1.checkpoint().active_release_id is None
