"""B-002: real canonical SAFE/B1 boundary around native OS operations.

Only disposable builder identities, synthetic owner credentials, and test-only
backends are used. No actual service is created by this suite.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import os

from sofia.platform.ops.platform_installation import (
    PlatformInstallationDenied, PlatformInstallationStore, install_staged_release,
)
from sofia.platform.ops.platform_installer_native_service import DebianSystemdNativeService
from sofia.platform.ops.platform_installer_native_transaction import (
    apply_owner_approved_native_service, native_service_operation_request,
)
from sofia.platform.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels
from test.test_platform_service_session import provision

pytestmark = [pytest.mark.pkg_ops, pytest.mark.skipif(os.name == "nt", reason="Debian signed-release fixture and systemd lifecycle contract")]


@pytest.fixture
def installed_scope(tmp_path, platform_wheels, canonical_state_path):
    builder = SignedReleaseBuilder(tmp_path / "signed", platform_wheels)
    staged, manifest, _ = builder.stage(revision=5)
    b1 = PlatformInstallationStore(tmp_path / "b1.db")
    release = tmp_path / "signed-release-v5"
    install_staged_release(staged, release, store=b1, verifier=builder.verifier)
    identity_store, identity, state = provision(tmp_path / "host")
    return dict(
        operation="register",
        store=b1, verifier=builder.verifier,
        expected_target=PlatformReleaseTarget.DEBIAN12_X86_64,
        destination=release, identity_home=identity_store.home, local_state=state,
        canonical_safe_state=canonical_state_path,
    )


def grant_for_request(scope, *, id, now):
    request = native_service_operation_request(**scope)
    approval = ExecutionApproval(
        approval_id=id,
        capability=request["capability"],
        request_fingerprint=request["fingerprint"],
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(scope["canonical_safe_state"]), approval)
    return approval


def fake_backend(*, error=None):
    backend = DebianSystemdNativeService()
    recorded = []

    def emit(spec, state="RUNNING"):
        recorded.append((state, spec.platform_id, spec.manifest_sha256))
        if error is not None:
            raise RuntimeError(error)
        return dict(schema="aegis.native-service-receipt.v1", service=spec.service_name,
                    process_state=state, platform_id=spec.platform_id,
                    release_manifest_sha256=spec.manifest_sha256,
                    service_health="UNKNOWN", core_activated=False)

    backend.register = emit
    backend.stop_and_unregister = lambda spec: emit(spec, "REMOVED")
    backend.restart_verified = lambda spec: emit(spec)
    backend.replace_verified = lambda prev, spec: emit(spec)
    return backend, recorded


def test_native_request_is_nonexecuting_signed_plan(installed_scope):
    scope = dict(installed_scope)
    request = native_service_operation_request(**scope)
    assert request["schema"] == "aegis.native-service-request.v1"
    assert request["owner_approved"] is False
    assert request["parameters"]["candidate"]["revision"] == 5
    assert request["parameters"]["native_generation"] == 0
    assert request["parameters"]["previous"] is None
    assert not (scope["store"].path.parent / "native-service-transaction.json").exists()


@pytest.mark.parametrize("approval_id", ("", "not-a-current-grant"))
def test_native_registration_without_real_scoped_grant_has_zero_effects(installed_scope, approval_id):
    scope = dict(installed_scope)
    backend, calls = fake_backend()
    with pytest.raises((PermissionError, PlatformInstallationDenied)):
        apply_owner_approved_native_service(
            **scope, backend=backend, approval_id=approval_id,
        )
    assert calls == []
    assert not (scope["store"].path.parent / "native-service-transaction.json").exists()


def test_native_register_remove_reinstall_retains_exact_uuid(installed_scope):
    scope = dict(installed_scope)
    backend, calls = fake_backend()
    original = InstallationIdentityStore(Path(scope["identity_home"])).load()
    now = datetime.now(timezone.utc)
    first = grant_for_request(scope, id="approval:b2-native-register-first", now=now)
    result = apply_owner_approved_native_service(
        **scope, backend=backend, approval_id=first.approval_id, now=now,
    )
    assert result["owner_approval_consumed"] is True
    assert result["full_health_certified"] is False
    assert result["service_health"] == "UNKNOWN"
    assert result["protected_identity_retained"] is True
    assert result["core_activated"] is False

    scope["operation"] = "unregister"
    second = grant_for_request(scope, id="approval:b2-native-unregister", now=now)
    removed = apply_owner_approved_native_service(
        **scope, backend=backend, approval_id=second.approval_id, now=now,
    )
    assert removed["process_state"] == "REMOVED"
    assert removed["protected_identity_retained"] is True

    scope["operation"] = "register"
    third = grant_for_request(scope, id="approval:b2-native-reinstall", now=now)
    again = apply_owner_approved_native_service(
        **scope, backend=backend, approval_id=third.approval_id, now=now,
    )
    assert again["process_state"] == "RUNNING"
    assert len(calls) == 3
    identity = InstallationIdentityStore(Path(scope["identity_home"])).load()
    assert identity.identity.canonical_uuid == original.identity.canonical_uuid
    assert identity.public_key_sha256 == original.public_key_sha256
    journal = scope["store"].path.parent / "native-service-transaction.json"
    assert '"generation":3' in journal.read_text()


def test_native_transaction_refuses_hardlinked_recovery_journal(
        installed_scope):
    scope = dict(installed_scope)
    backend, effects = fake_backend()
    now = datetime.now(timezone.utc)
    approved = grant_for_request(
        scope, id="approval:b2-journal-inode", now=now,
    )
    apply_owner_approved_native_service(
        **scope, backend=backend, approval_id=approved.approval_id, now=now,
    )
    assert len(effects) == 1
    journal = scope["store"].path.parent / "native-service-transaction.json"
    os.link(journal, journal.with_name("foreign-linked-journal.json"))
    scope["operation"] = "repair"
    with pytest.raises((PlatformInstallationDenied, PermissionError)):
        native_service_operation_request(**scope)
    assert len(effects) == 1


@pytest.mark.parametrize("field, forged", [
    ("platform_id", "forged-other-platform"),
    ("release_manifest_sha256", "0" * 64),
    ("core_activated", True),
    ("service_health", "HEALTHY"),
])
def test_native_rejects_wrong_platform_or_release_receipt(
        installed_scope, field, forged):
    scope = dict(installed_scope)
    backend, effects = fake_backend()
    original = backend.register

    def mismatched(spec):
        receipt = original(spec)
        receipt[field] = forged
        return receipt

    backend.register = mismatched
    now = datetime.now(timezone.utc)
    approved = grant_for_request(
        scope, id="approval:b2-receipt-" + field, now=now,
    )
    with pytest.raises(PlatformInstallationDenied):
        apply_owner_approved_native_service(
            **scope, backend=backend,
            approval_id=approved.approval_id, now=now,
        )
    assert len(effects) == 1
    journal = scope["store"].path.parent / "native-service-transaction.json"
    assert '"OUTCOME_UNKNOWN"' in journal.read_text()
    with pytest.raises(PlatformInstallationDenied, match="unresolved native"):
        native_service_operation_request(**scope)


@pytest.mark.parametrize("field, forged", [
    ("platform_id", "forged-removed-platform"),
    ("release_manifest_sha256", "0" * 64),
    ("service_health", "HEALTHY"),
])
def test_unregistration_receipt_must_match_exact_signed_identity(
        installed_scope, field, forged):
    scope = dict(installed_scope)
    backend, effects = fake_backend()
    now = datetime.now(timezone.utc)
    register = grant_for_request(
        scope, id="approval:b2-unregister-receipt-start-" + field, now=now,
    )
    apply_owner_approved_native_service(
        **scope, backend=backend, approval_id=register.approval_id, now=now,
    )
    assert len(effects) == 1
    scope["operation"] = "unregister"
    original = backend.stop_and_unregister

    def forged_receipt(spec):
        receipt = original(spec)
        receipt[field] = forged
        return receipt

    backend.stop_and_unregister = forged_receipt
    removal = grant_for_request(
        scope, id="approval:b2-unregister-receipt-stop-" + field, now=now,
    )
    with pytest.raises(PlatformInstallationDenied, match="receipt differs"):
        apply_owner_approved_native_service(
            **scope, backend=backend,
            approval_id=removal.approval_id, now=now,
        )
    assert len(effects) == 2
    journal = scope["store"].path.parent / "native-service-transaction.json"
    assert '"OUTCOME_UNKNOWN"' in journal.read_text()
    with pytest.raises(PlatformInstallationDenied, match="unresolved native"):
        native_service_operation_request(**scope)


def test_native_interrupted_registration_blocks_blind_retry(installed_scope):
    scope = dict(installed_scope)
    backend, calls = fake_backend(error="crash after possible SCM/systemd write")
    now = datetime.now(timezone.utc)
    approval = grant_for_request(scope, id="approval:b2-interrupted", now=now)
    with pytest.raises(RuntimeError, match="crash"):
        apply_owner_approved_native_service(
            **scope, backend=backend, approval_id=approval.approval_id, now=now,
        )
    assert len(calls) == 1
    journal = scope["store"].path.parent / "native-service-transaction.json"
    assert '"OUTCOME_UNKNOWN"' in journal.read_text()
    with pytest.raises(PlatformInstallationDenied, match="unresolved native"):
        native_service_operation_request(**scope)


def test_native_replay_cannot_act_again(installed_scope):
    scope = dict(installed_scope)
    backend, calls = fake_backend()
    now = datetime.now(timezone.utc)
    approval = grant_for_request(scope, id="approval:b2-replay", now=now)
    apply_owner_approved_native_service(
        **scope, backend=backend, approval_id=approval.approval_id, now=now,
    )
    with pytest.raises((PermissionError, PlatformInstallationDenied)):
        apply_owner_approved_native_service(
            **scope, backend=backend, approval_id=approval.approval_id,
            now=now + timedelta(seconds=1),
        )
    assert len(calls) == 1


def test_native_unknown_operation_refuses_any_backend(installed_scope):
    scope = dict(installed_scope)
    scope["operation"] = "purge"
    backend, calls = fake_backend()
    with pytest.raises(PlatformInstallationDenied, match="unsupported"):
        native_service_operation_request(**scope)
    assert calls == []


def test_revoked_credential_blocks_native_effect_even_with_saved_approval(
        installed_scope):
    import sqlite3
    scope = dict(installed_scope)
    backend, calls = fake_backend()
    now = datetime.now(timezone.utc)
    approval = grant_for_request(scope, id="approval:b2-revoked-credential", now=now)
    with sqlite3.connect(scope["canonical_safe_state"]) as conn:
        conn.execute("UPDATE safe_owner_credential SET revoked_at=?",
                     (now.isoformat(),))
    with pytest.raises(PermissionError, match="authentication"):
        apply_owner_approved_native_service(
            **scope, backend=backend, approval_id=approval.approval_id, now=now,
        )
    assert calls == []
    assert not (scope["store"].path.parent / "native-service-transaction.json").exists()


def test_operator_stop_before_effect_denies_native_registration(
        installed_scope, monkeypatch):
    import sofia.platform.ops.platform_installer_native_transaction as transaction
    from types import SimpleNamespace

    scope = dict(installed_scope)
    backend, calls = fake_backend()
    now = datetime.now(timezone.utc)
    approval = grant_for_request(scope, id="approval:b2-stop-before", now=now)
    monkeypatch.setattr(
        transaction.OperatorStopStore, "current",
        lambda self: SimpleNamespace(active=True),
    )
    with pytest.raises(PlatformInstallationDenied, match="STOP engaged"):
        apply_owner_approved_native_service(
            **scope, backend=backend, approval_id=approval.approval_id, now=now,
        )
    assert calls == []


def test_owner_credential_revoked_during_native_effect_requires_reconciliation(
        installed_scope):
    import sqlite3

    scope = dict(installed_scope)
    backend, effects = fake_backend()
    now = datetime.now(timezone.utc)
    approval = grant_for_request(
        scope, id="approval:b2-mid-effect-credential-revoked", now=now,
    )
    original = backend.register

    def register_then_revoke(spec):
        receipt = original(spec)
        # A separate owner action can revoke a previously verified
        # credential while a native OS call is still in progress.
        with sqlite3.connect(scope["canonical_safe_state"]) as connection:
            connection.execute(
                "UPDATE safe_owner_credential SET revoked_at=? "
                "WHERE revoked_at IS NULL",
                (now.isoformat(),),
            )
        return receipt

    backend.register = register_then_revoke
    with pytest.raises(PlatformInstallationDenied, match="owner authentication revoked"):
        apply_owner_approved_native_service(
            **scope, backend=backend,
            approval_id=approval.approval_id, now=now,
        )
    assert len(effects) == 1
    journal = scope["store"].path.parent / "native-service-transaction.json"
    assert '"OUTCOME_UNKNOWN"' in journal.read_text()
    with pytest.raises(PlatformInstallationDenied, match="unresolved native"):
        native_service_operation_request(**scope)


def test_operator_stop_during_service_effect_forces_unknown_outcome(
        installed_scope, monkeypatch):
    import sofia.platform.ops.platform_installer_native_transaction as transaction
    from types import SimpleNamespace

    scope = dict(installed_scope)
    backend, calls = fake_backend()
    now = datetime.now(timezone.utc)
    approval = grant_for_request(scope, id="approval:b2-stop-during", now=now)
    state = {"active": False}
    monkeypatch.setattr(
        transaction.OperatorStopStore, "current",
        lambda self: SimpleNamespace(active=state["active"]),
    )
    original = backend.register

    def interrupted(spec):
        observed = original(spec)
        state["active"] = True
        return observed

    backend.register = interrupted
    with pytest.raises(PlatformInstallationDenied, match="STOP changed"):
        apply_owner_approved_native_service(
            **scope, backend=backend, approval_id=approval.approval_id, now=now,
        )
    assert len(calls) == 1
    journal = scope["store"].path.parent / "native-service-transaction.json"
    assert '"OUTCOME_UNKNOWN"' in journal.read_text()
