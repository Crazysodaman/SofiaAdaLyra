"""AG-D011 canonical installer CLI adapter against disposable signed fixtures.

The publisher key, release and owner approvals are disposable test material. The
OS backend is simulated exactly as in the existing native transaction tests.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization

from sofia.platform.ops.platform_installation import (
    PlatformInstallationStore, install_staged_release, platform_rollback_request,
)
from sofia.platform.ops.platform_installer_bundle import PlatformReleaseRejected
from sofia.platform.ops.platform_installer_cli import (
    InstallerInputs, execute_command, main, staging_candidate_path,
)
from sofia.platform.ops.platform_installer_code_install import (
    signed_code_publication_request,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService,
)
from sofia.platform.ops.platform_installer_native_transaction import (
    native_service_operation_request, native_service_reconciliation_request,
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

pytestmark = pytest.mark.pkg_ops
TARGET = PlatformReleaseTarget.DEBIAN12_X86_64


@pytest.fixture
def debian_host(monkeypatch):
    import sofia.platform.ops.platform_installer_bundle as bundle
    monkeypatch.setattr(bundle, "host_release_target", lambda: TARGET)


def _pinned_public(builder, root):
    root.mkdir(parents=True, exist_ok=True)
    public = builder._key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = root / "publisher.pem"
    path.write_bytes(public)
    return path, sha256(public).hexdigest()


@pytest.fixture
def scope(tmp_path, platform_wheels, canonical_state_path, debian_host):
    builder = SignedReleaseBuilder(tmp_path / "signed", platform_wheels)
    release_root, manifest, _signature = builder.stage(
        release_id="cli-disposable-release", revision=4,
    )
    key, fingerprint = _pinned_public(builder, tmp_path / "trust-root")
    identity, current, local_state = provision(tmp_path / "host")
    store_path = tmp_path / "b1.db"
    inputs = InstallerInputs(
        release_root=release_root,
        publisher_key=key,
        publisher_key_sha256=fingerprint,
        publisher_signer=builder.signer_key_id,
        expected_source_sha=manifest.source_sha,
        target=TARGET.value,
        minimum_revision=4,
        destination=tmp_path / "installed",
        identity_home=identity.home,
        local_state=local_state,
        canonical_safe_state=canonical_state_path,
        store_path=store_path,
    )
    return SimpleNamespace(
        tmp_path=tmp_path, builder=builder, release_root=release_root,
        manifest=manifest, key=key, key_sha256=fingerprint, identity=identity,
        current=current, local_state=local_state, safe=canonical_state_path,
        store_path=store_path, inputs=inputs,
    )


def _store(scope):
    return PlatformInstallationStore(scope.store_path)


def _approve(scope, capability, fingerprint, approval_id):
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=approval_id,
        capability=capability,
        request_fingerprint=fingerprint,
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(scope.safe), approval,
    )
    return approval_id


def _code_request(scope):
    stage = staging_candidate_path(
        scope.store_path, scope.manifest.release_id, scope.manifest.revision,
    )
    return signed_code_publication_request(
        staged_candidate=stage, destination=scope.inputs.destination,
        identity_home=scope.identity.home, state_path=scope.safe,
        store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, previous_destination=None,
    )


def _native_request(scope, operation="register", previous=None):
    return native_service_operation_request(
        operation=operation, store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, destination=scope.inputs.destination,
        identity_home=scope.identity.home, local_state=scope.local_state,
        canonical_safe_state=scope.safe, previous_destination=previous,
    )


def _fake_backend(effects, *, fail_register=False):
    backend = DebianSystemdNativeService()
    backend.unit_path = Path("/etc/systemd/system/aegis-platform.service")

    def receipt(spec, state):
        effects.append((state, spec.platform_id, spec.manifest_sha256))
        return {
            "schema": "aegis.native-service-receipt.v1",
            "service": spec.service_name,
            "origin": "OWNED_CONFIG_VERIFIED",
            "process_state": state,
            "process_id": 1 if state == "RUNNING" else None,
            "platform_id": spec.platform_id,
            "release_manifest_sha256": spec.manifest_sha256,
            "service_health": "UNKNOWN",
            "core_activated": False,
            "fully_healthy": False,
        }

    def register(spec):
        if fail_register:
            raise RuntimeError("simulated interrupted native registration")
        return receipt(spec, "RUNNING")

    backend.register = register
    backend.restart_verified = lambda spec: receipt(spec, "RUNNING")
    backend.replace_verified = lambda previous, candidate: receipt(candidate, "RUNNING")
    backend.stop_and_unregister = lambda spec: receipt(spec, "REMOVED")
    backend.observe = lambda spec: {
        **receipt(spec, "RUNNING"),
        "origin": "OWNED_CONFIG_VERIFIED",
    }
    return backend


def _install(scope, backend):
    first = execute_command("install", scope.inputs, backend=backend)
    assert first["outcome"] == "DENIED"
    assert first["required_approval"] == "code"
    request = _code_request(scope)
    assert request["fingerprint"] == first["approval_fingerprint"]
    code_approval = _approve(
        scope, request["capability"], request["fingerprint"], "approval:cli-code",
    )
    second = execute_command(
        "install", replace(scope.inputs, code_approval_id=code_approval),
        backend=backend,
    )
    assert second["outcome"] == "DENIED"
    assert second["required_approval"] == "native"
    native = _native_request(scope)
    assert native["fingerprint"] == second["approval_fingerprint"]
    native_approval = _approve(
        scope, native["capability"], native["fingerprint"], "approval:cli-native",
    )
    third = execute_command(
        "install", replace(scope.inputs, approval_id=native_approval),
        backend=backend,
    )
    assert third["outcome"] == "INSTALLED"
    return third, code_approval, native_approval


def test_verify_accepts_only_independently_pinned_signed_release(scope):
    result = execute_command("verify", scope.inputs)
    assert result["outcome"] == "VERIFIED"
    assert result["executed"] is False
    assert result["owner_approved"] is False
    assert result["manifest_sha256"] == scope.manifest.digest
    assert result["release_id"] == scope.manifest.release_id


@pytest.mark.parametrize("defect", ("signer", "digest", "source", "target", "parent"))
def test_verify_denies_untrusted_release_inputs(scope, defect):
    invalid = replace(scope.inputs)
    if defect == "signer":
        invalid = replace(invalid, publisher_signer="attacker")
    elif defect == "digest":
        invalid = replace(invalid, publisher_key_sha256="0" * 64)
    elif defect == "source":
        invalid = replace(invalid, expected_source_sha="0" * 40)
    elif defect == "target":
        invalid = replace(invalid, target=PlatformReleaseTarget.WINDOWS_X86_64.value)
    else:
        invalid = replace(invalid, expected_parent_manifest_sha256="f" * 64)
    result = execute_command("verify", invalid)
    assert result["outcome"] == "DENIED"
    assert result["executed"] is False and result["owner_approved"] is False


def test_verify_denies_unsupported_architecture(scope, monkeypatch):
    import sofia.platform.ops.platform_installer_bundle as bundle

    def unsupported():
        raise PlatformReleaseRejected("unsupported architecture for Aegis Platform 1.0")

    monkeypatch.setattr(bundle, "host_release_target", unsupported)
    result = execute_command("verify", scope.inputs)
    assert result["outcome"] == "DENIED"


def test_install_requires_code_then_native_owner_approval_and_fences_duplicates(scope):
    effects = []
    backend = _fake_backend(effects)
    result, _code, native = _install(scope, backend)
    assert result["executed"] is True
    assert result["owner_approved"] is True
    assert result["native_process_state"] == "RUNNING"
    assert result["service_health"] == "UNKNOWN"
    assert result["core_activated"] is False
    assert len(effects) == 1
    assert scope.inputs.destination.is_dir()
    assert InstallationIdentityStore(scope.identity.home).load() == scope.current
    duplicate = execute_command(
        "install", replace(scope.inputs, approval_id=native), backend=backend,
    )
    assert duplicate["outcome"] == "DENIED"
    assert len(effects) == 1


def test_install_without_approval_never_claims_success(scope):
    effects = []
    result = execute_command("install", scope.inputs, backend=_fake_backend(effects))
    assert result["outcome"] == "DENIED"
    assert result["required_approval"] == "code"
    assert result["executed"] is False and result["owner_approved"] is False
    assert not scope.inputs.destination.exists()
    assert effects == []


def test_status_and_doctor_read_b1_state_without_os_mutation(scope):
    effects = []
    _install(scope, _fake_backend(effects))
    status = execute_command("status", scope.inputs)
    assert status["outcome"] == "OK"
    assert status["installed_verified"] is True
    assert status["service_state"] == "NOT_OBSERVED"
    assert status["executed"] is False
    doctor = execute_command("doctor", scope.inputs)
    assert doctor["outcome"] == "OK"
    assert doctor["manifest_sha256"] == scope.manifest.digest
    assert len(effects) == 1


def test_downgrade_below_durable_floor_is_refused(scope, platform_wheels):
    store = _store(scope)
    install_staged_release(
        scope.release_root, scope.inputs.destination,
        store=store, verifier=scope.builder.verifier,
    )
    older = SignedReleaseBuilder(scope.tmp_path / "older-build", platform_wheels)
    older_root, older_manifest, _ = older.stage(release_id="older-release", revision=3)
    key, fingerprint = _pinned_public(older, scope.tmp_path / "older-trust")
    invalid = replace(
        scope.inputs, release_root=older_root, publisher_key=key,
        publisher_key_sha256=fingerprint,
        publisher_signer=older.signer_key_id,
        expected_source_sha=older_manifest.source_sha,
        destination=scope.tmp_path / "downgrade-target",
    )
    result = execute_command("install", invalid, backend=_fake_backend([]))
    assert result["outcome"] == "DENIED"
    assert not invalid.destination.exists()


def test_stale_native_generation_is_refused(scope):
    effects = []
    backend = _fake_backend(effects)
    first = execute_command("install", scope.inputs, backend=backend)
    assert first["required_approval"] == "code"
    code_request = _code_request(scope)
    code_approval = _approve(
        scope, code_request["capability"], code_request["fingerprint"],
        "approval:stale-code",
    )
    second = execute_command(
        "install", replace(scope.inputs, code_approval_id=code_approval),
        backend=backend,
    )
    assert second["required_approval"] == "native"
    native = _native_request(scope)
    native_approval = _approve(
        scope, native["capability"], native["fingerprint"], "approval:stale-native",
    )
    with sqlite3.connect(scope.store_path) as db:
        db.execute(
            "UPDATE ops_platform_installation_checkpoint"
            " SET generation=generation+1 WHERE singleton=1"
        )
    stale = execute_command(
        "install", replace(scope.inputs, approval_id=native_approval),
        backend=backend,
    )
    assert stale["outcome"] == "DENIED"
    assert effects == []


def test_reconcile_clears_only_interrupted_native_outcome(scope):
    effects = []
    backend = _fake_backend(effects)
    execute_command("install", scope.inputs, backend=backend)
    code_request = _code_request(scope)
    code_approval = _approve(
        scope, code_request["capability"], code_request["fingerprint"],
        "approval:reconcile-code",
    )
    execute_command(
        "install", replace(scope.inputs, code_approval_id=code_approval),
        backend=backend,
    )
    native = _native_request(scope)
    native_approval = _approve(
        scope, native["capability"], native["fingerprint"], "approval:reconcile-native",
    )
    interrupted = execute_command(
        "install", replace(scope.inputs, approval_id=native_approval),
        backend=_fake_backend(effects, fail_register=True),
    )
    assert interrupted["outcome"] == "DENIED"
    request = native_service_reconciliation_request(
        store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, destination=scope.inputs.destination,
        identity_home=scope.identity.home, local_state=scope.local_state,
        canonical_safe_state=scope.safe, backend=backend,
    )
    approval = _approve(
        scope, request["capability"], request["fingerprint"],
        "approval:reconcile-attended",
    )
    reconciled = execute_command(
        "reconcile", replace(scope.inputs, approval_id=approval), backend=backend,
    )
    assert reconciled["outcome"] == "RECONCILED"
    assert reconciled["journal_reconciled"] is True
    assert reconciled["native_service_mutated"] is False
    assert reconciled["executed"] is True


def test_repair_refuses_to_switch_signed_releases(scope, platform_wheels):
    effects = []
    backend = _fake_backend(effects)
    _install(scope, backend)
    next_builder = SignedReleaseBuilder(scope.tmp_path / "next-build", platform_wheels)
    next_root, next_manifest, _ = next_builder.stage(
        release_id="next-release", revision=5,
        parent_manifest_sha256=scope.manifest.digest,
    )
    key, fingerprint = _pinned_public(next_builder, scope.tmp_path / "next-trust")
    switched = replace(
        scope.inputs, release_root=next_root, publisher_key=key,
        publisher_key_sha256=fingerprint,
        publisher_signer=next_builder.signer_key_id,
        expected_source_sha=next_manifest.source_sha,
        minimum_revision=4,
    )
    result = execute_command("repair", switched, backend=backend)
    assert result["outcome"] == "DENIED"
    assert len(effects) == 1


def test_uninstall_and_reinstall_retain_exact_identity_and_protected_state(scope):
    effects = []
    backend = _fake_backend(effects)
    _install(scope, backend)
    before = InstallationIdentityStore(scope.identity.home).load()
    removal = _native_request(scope, operation="unregister")
    removal_approval = _approve(
        scope, removal["capability"], removal["fingerprint"],
        "approval:uninstall",
    )
    uninstalled = execute_command(
        "uninstall", replace(scope.inputs, approval_id=removal_approval),
        backend=backend,
    )
    assert uninstalled["outcome"] == "UNINSTALLED"
    assert uninstalled["protected_identity_policy"] == "RETAIN"
    assert uninstalled["protected_state_policy"] == "RETAIN"
    assert InstallationIdentityStore(scope.identity.home).load() == before
    assert scope.local_state.is_file()
    assert scope.inputs.destination.is_dir()
    reinstall_request = _native_request(scope)
    reinstall_approval = _approve(
        scope, reinstall_request["capability"], reinstall_request["fingerprint"],
        "approval:reinstall",
    )
    reinstalled = execute_command(
        "reinstall", replace(scope.inputs, approval_id=reinstall_approval),
        backend=backend,
    )
    assert reinstalled["outcome"] == "REINSTALLED"
    assert reinstalled["identity_policy"] == "REUSE_EXACT"
    assert InstallationIdentityStore(scope.identity.home).load() == before
    assert len(effects) == 3


def test_update_refuses_wrong_signed_predecessor(scope, platform_wheels):
    effects = []
    backend = _fake_backend(effects)
    _install(scope, backend)
    next_builder = SignedReleaseBuilder(scope.tmp_path / "wrong-parent", platform_wheels)
    next_root, next_manifest, _ = next_builder.stage(
        release_id="wrong-parent-release", revision=5,
        parent_manifest_sha256="0" * 64,
    )
    key, fingerprint = _pinned_public(next_builder, scope.tmp_path / "wrong-trust")
    invalid = replace(
        scope.inputs, release_root=next_root, publisher_key=key,
        publisher_key_sha256=fingerprint,
        publisher_signer=next_builder.signer_key_id,
        expected_source_sha=next_manifest.source_sha,
        destination=scope.tmp_path / "update-target",
        previous_destination=scope.inputs.destination,
        minimum_revision=5,
    )
    result = execute_command("update", invalid, backend=backend)
    assert result["outcome"] == "DENIED"
    assert not invalid.destination.exists()


def test_update_then_rollback_reuses_verified_release_history(scope):
    effects = []
    backend = _fake_backend(effects)
    _install(scope, backend)
    next_root, next_manifest, _signature = scope.builder.stage(
        release_id="cli-disposable-release-v5", revision=5,
        parent_manifest_sha256=scope.manifest.digest,
    )
    next_destination = scope.tmp_path / "installed-v5"
    update_inputs = replace(
        scope.inputs, release_root=next_root, destination=next_destination,
        previous_destination=scope.inputs.destination, minimum_revision=5,
    )
    first = execute_command("update", update_inputs, backend=backend)
    assert first["required_approval"] == "code"
    request = signed_code_publication_request(
        staged_candidate=staging_candidate_path(
            scope.store_path, next_manifest.release_id, 5,
        ),
        destination=next_destination, identity_home=scope.identity.home,
        state_path=scope.safe, store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, previous_destination=scope.inputs.destination,
    )
    assert request["fingerprint"] == first["approval_fingerprint"]
    code_approval = _approve(
        scope, request["capability"], request["fingerprint"], "approval:update-code",
    )
    second = execute_command(
        "update", replace(update_inputs, code_approval_id=code_approval),
        backend=backend,
    )
    assert second["required_approval"] == "native"
    native = native_service_operation_request(
        operation="update", store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, destination=next_destination,
        identity_home=scope.identity.home, local_state=scope.local_state,
        canonical_safe_state=scope.safe,
        previous_destination=scope.inputs.destination,
    )
    assert native["fingerprint"] == second["approval_fingerprint"]
    native_approval = _approve(
        scope, native["capability"], native["fingerprint"], "approval:update-native",
    )
    updated = execute_command(
        "update", replace(update_inputs, approval_id=native_approval),
        backend=backend,
    )
    assert updated["outcome"] == "UPDATED"
    assert updated["revision"] == 5
    assert _store(scope).revision_floor() == 5
    assert next_destination.is_dir()

    rollback_inputs = replace(
        scope.inputs, release_root=scope.release_root,
        destination=scope.inputs.destination,
        previous_destination=next_destination, minimum_revision=5,
    )
    first_rollback = execute_command("rollback", rollback_inputs, backend=backend)
    assert first_rollback["required_approval"] == "native"
    rollback = native_service_operation_request(
        operation="rollback", store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, destination=scope.inputs.destination,
        identity_home=scope.identity.home, local_state=scope.local_state,
        canonical_safe_state=scope.safe, previous_destination=next_destination,
    )
    assert rollback["fingerprint"] == first_rollback["approval_fingerprint"]
    rollback_approval = _approve(
        scope, rollback["capability"], rollback["fingerprint"],
        "approval:rollback-native",
    )
    rolled_back = execute_command(
        "rollback", replace(rollback_inputs, approval_id=rollback_approval),
        backend=backend,
    )
    assert rolled_back["outcome"] == "ROLLED_BACK"
    assert rolled_back["revision"] == 4
    assert _store(scope).revision_floor() == 5
    assert InstallationIdentityStore(scope.identity.home).load() == scope.current


def test_cli_output_scrubs_paths_and_exceptions(capsys, scope):
    missing = replace(scope.inputs, release_root=scope.tmp_path / "absent-release")
    code = main([
        "verify", "--release-root", str(missing.release_root),
        "--publisher-key", str(missing.publisher_key),
        "--publisher-key-sha256", missing.publisher_key_sha256,
        "--publisher-signer", missing.publisher_signer,
        "--expected-source-sha", missing.expected_source_sha,
        "--target", missing.target,
        "--minimum-revision", "4", "--json",
    ])
    output = capsys.readouterr().out
    assert code == 3
    document = json.loads(output)
    assert document["outcome"] == "DENIED"
    assert document["executed"] is False and document["owner_approved"] is False
    assert str(scope.tmp_path) not in output
    assert "Traceback" not in output




def test_install_denies_wrong_signed_host_target_before_any_effect(scope):
    effects = []
    invalid = replace(scope.inputs, target=PlatformReleaseTarget.WINDOWS_X86_64.value)
    result = execute_command("install", invalid, backend=_fake_backend(effects))
    assert result["outcome"] == "DENIED"
    assert result["executed"] is False and result["owner_approved"] is False
    assert effects == []
    assert not invalid.destination.exists()


@pytest.mark.parametrize("defect", ("asset", "signature"))
def test_tampered_release_bytes_deny_before_publication(scope, defect):
    effects = []
    if defect == "asset":
        asset = next(item for item in (scope.release_root / "assets").rglob("*")
                     if item.is_file())
        asset.write_bytes(asset.read_bytes() + b"tampered")
    else:
        (scope.release_root / "release-signature.json").write_text(
            "{}", encoding="utf-8")
    result = execute_command("install", scope.inputs, backend=_fake_backend(effects))
    assert result["outcome"] == "DENIED"
    assert result["executed"] is False and result["owner_approved"] is False
    assert effects == []
    assert not scope.inputs.destination.exists()
    assert _store(scope).history() == []


def test_rollback_refuses_unattested_older_release(scope):
    effects = []
    backend = _fake_backend(effects)
    _install(scope, backend)
    older_root, older_manifest, _ = scope.builder.stage(
        release_id="unattested-rollback-target", revision=3,
    )
    destination = scope.tmp_path / "unattested-rollback"
    inputs = replace(
        scope.inputs, release_root=older_root, destination=destination,
        previous_destination=scope.inputs.destination,
        expected_source_sha=older_manifest.source_sha, minimum_revision=5,
    )
    first = execute_command("rollback", inputs, backend=backend)
    assert first["outcome"] == "DENIED"
    assert first["required_approval"] == "code"
    request = platform_rollback_request(
        staging_candidate_path(scope.store_path, older_manifest.release_id, 3),
        destination, scope.safe, store=_store(scope),
        verifier=scope.builder.verifier,
    )
    assert request["fingerprint"] == first["approval_fingerprint"]
    approval = _approve(
        scope, request["capability"], request["fingerprint"],
        "approval:unattested-rollback",
    )
    denied = execute_command(
        "rollback", replace(inputs, code_approval_id=approval), backend=backend,
    )
    assert denied["outcome"] == "DENIED"
    assert len(effects) == 1
    assert not destination.exists()


def test_native_owner_approval_cannot_be_replayed(scope):
    effects = []
    backend = _fake_backend(effects)
    _installed, _code, install_native = _install(scope, backend)
    removal = _native_request(scope, operation="unregister")
    removal_approval = _approve(
        scope, removal["capability"], removal["fingerprint"],
        "approval:replay-uninstall",
    )
    uninstalled = execute_command(
        "uninstall", replace(scope.inputs, approval_id=removal_approval),
        backend=backend,
    )
    assert uninstalled["outcome"] == "UNINSTALLED"
    before = len(effects)
    replayed_register = execute_command(
        "reinstall", replace(scope.inputs, approval_id=install_native),
        backend=backend,
    )
    assert replayed_register["outcome"] == "DENIED"
    assert len(effects) == before
    replayed_removal = execute_command(
        "uninstall", replace(scope.inputs, approval_id=removal_approval),
        backend=backend,
    )
    assert replayed_removal["outcome"] == "DENIED"
    assert len(effects) == before


def test_unresolved_native_journal_blocks_replay_and_is_visible_to_status(scope):
    effects = []
    backend = _fake_backend(effects)
    first = execute_command("install", scope.inputs, backend=backend)
    assert first["required_approval"] == "code"
    code_request = _code_request(scope)
    code_approval = _approve(
        scope, code_request["capability"], code_request["fingerprint"],
        "approval:journal-code",
    )
    second = execute_command(
        "install", replace(scope.inputs, code_approval_id=code_approval),
        backend=backend,
    )
    assert second["required_approval"] == "native"
    native = _native_request(scope)
    native_approval = _approve(
        scope, native["capability"], native["fingerprint"],
        "approval:journal-native",
    )
    interrupted = execute_command(
        "install", replace(scope.inputs, approval_id=native_approval),
        backend=_fake_backend(effects, fail_register=True),
    )
    assert interrupted["outcome"] == "DENIED"
    assert effects == []
    status = execute_command("status", scope.inputs)
    assert status["outcome"] == "RECONCILIATION_REQUIRED"
    assert status["pending_native_attempts"] == 1
    assert status["native_journal_phase"] == "OUTCOME_UNKNOWN"
    assert status["native_service_registered"] is False
    replay = execute_command(
        "install",
        replace(scope.inputs, code_approval_id=code_approval,
                approval_id=native_approval),
        backend=backend,
    )
    assert replay["outcome"] == "DENIED"
    assert effects == []


def test_signed_installer_end_to_end_lifecycle_retains_identity_and_floor(scope):
    effects = []
    backend = _fake_backend(effects)
    installed, _code, _install_native = _install(scope, backend)
    assert installed["outcome"] == "INSTALLED"
    identity_before = InstallationIdentityStore(scope.identity.home).load()
    status = execute_command("status", scope.inputs)
    assert status["outcome"] == "OK"
    assert status["installed_verified"] is True
    assert status["history_entries"] == 1
    assert status["pending_attempts"] == 0
    assert status["pending_native_attempts"] == 0
    assert status["native_journal_phase"] == "SERVICE_OBSERVED"
    assert status["native_service_registered"] is True
    assert status["release_id"] == scope.manifest.release_id

    next_root, next_manifest, _ = scope.builder.stage(
        release_id="cli-e2e-release-v5", revision=5,
        parent_manifest_sha256=scope.manifest.digest,
    )
    next_destination = scope.tmp_path / "installed-e2e-v5"
    update_inputs = replace(
        scope.inputs, release_root=next_root, destination=next_destination,
        previous_destination=scope.inputs.destination, minimum_revision=5,
    )
    first_update = execute_command("update", update_inputs, backend=backend)
    assert first_update["required_approval"] == "code"
    update_code_request = signed_code_publication_request(
        staged_candidate=staging_candidate_path(
            scope.store_path, next_manifest.release_id, 5,
        ),
        destination=next_destination, identity_home=scope.identity.home,
        state_path=scope.safe, store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, previous_destination=scope.inputs.destination,
    )
    assert update_code_request["fingerprint"] == first_update["approval_fingerprint"]
    update_code_approval = _approve(
        scope, update_code_request["capability"],
        update_code_request["fingerprint"], "approval:e2e-update-code",
    )
    second_update = execute_command(
        "update", replace(update_inputs, code_approval_id=update_code_approval),
        backend=backend,
    )
    assert second_update["required_approval"] == "native"
    update_native = native_service_operation_request(
        operation="update", store=_store(scope), verifier=scope.builder.verifier,
        expected_target=TARGET, destination=next_destination,
        identity_home=scope.identity.home, local_state=scope.local_state,
        canonical_safe_state=scope.safe,
        previous_destination=scope.inputs.destination,
    )
    assert update_native["fingerprint"] == second_update["approval_fingerprint"]
    update_native_approval = _approve(
        scope, update_native["capability"], update_native["fingerprint"],
        "approval:e2e-update-native",
    )
    updated = execute_command(
        "update", replace(update_inputs, approval_id=update_native_approval),
        backend=backend,
    )
    assert updated["outcome"] == "UPDATED"
    assert updated["revision"] == 5
    assert _store(scope).revision_floor() == 5
    update_status = execute_command("status", update_inputs)
    assert update_status["outcome"] == "OK"
    assert update_status["installed_verified"] is True
    assert update_status["release_id"] == next_manifest.release_id
    assert update_status["history_entries"] == 2
    assert update_status["minimum_accepted_revision"] == 5

    rollback_inputs = replace(
        scope.inputs, release_root=scope.release_root,
        destination=scope.inputs.destination,
        previous_destination=next_destination, minimum_revision=5,
    )
    first_rollback = execute_command("rollback", rollback_inputs, backend=backend)
    assert first_rollback["required_approval"] == "native"
    rollback_request = native_service_operation_request(
        operation="rollback", store=_store(scope),
        verifier=scope.builder.verifier, expected_target=TARGET,
        destination=scope.inputs.destination,
        identity_home=scope.identity.home, local_state=scope.local_state,
        canonical_safe_state=scope.safe, previous_destination=next_destination,
    )
    assert rollback_request["fingerprint"] == first_rollback["approval_fingerprint"]
    rollback_approval = _approve(
        scope, rollback_request["capability"], rollback_request["fingerprint"],
        "approval:e2e-rollback-native",
    )
    rolled_back = execute_command(
        "rollback", replace(rollback_inputs, approval_id=rollback_approval),
        backend=backend,
    )
    assert rolled_back["outcome"] == "ROLLED_BACK"
    assert rolled_back["revision"] == 4
    assert _store(scope).revision_floor() == 5
    rollback_status = execute_command("status", scope.inputs)
    assert rollback_status["outcome"] == "OK"
    assert rollback_status["installed_verified"] is True
    assert rollback_status["release_id"] == scope.manifest.release_id
    assert rollback_status["minimum_accepted_revision"] == 5
    history_before_uninstall = len(_store(scope).history())

    removal = _native_request(scope, operation="unregister")
    removal_approval = _approve(
        scope, removal["capability"], removal["fingerprint"],
        "approval:e2e-uninstall",
    )
    uninstalled = execute_command(
        "uninstall", replace(scope.inputs, approval_id=removal_approval),
        backend=backend,
    )
    assert uninstalled["outcome"] == "UNINSTALLED"
    assert uninstalled["protected_identity_policy"] == "RETAIN"
    assert uninstalled["protected_state_policy"] == "RETAIN"
    assert InstallationIdentityStore(scope.identity.home).load() == identity_before
    assert scope.inputs.destination.is_dir() and scope.local_state.is_file()
    assert _store(scope).revision_floor() == 5

    reinstall_request = _native_request(scope)
    reinstall_approval = _approve(
        scope, reinstall_request["capability"], reinstall_request["fingerprint"],
        "approval:e2e-reinstall",
    )
    reinstalled = execute_command(
        "reinstall", replace(scope.inputs, approval_id=reinstall_approval),
        backend=backend,
    )
    assert reinstalled["outcome"] == "REINSTALLED"
    assert reinstalled["identity_policy"] == "REUSE_EXACT"
    assert reinstalled["revision"] == 4
    assert InstallationIdentityStore(scope.identity.home).load() == identity_before
    assert _store(scope).revision_floor() == 5
    assert len(_store(scope).history()) == history_before_uninstall
    assert [entry[0] for entry in effects] == [
        "RUNNING", "RUNNING", "RUNNING", "REMOVED", "RUNNING",
    ]
