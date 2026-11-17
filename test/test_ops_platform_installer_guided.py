"""One-step guided installer orchestration against disposable signed fixtures.

Every publisher key, release, owner proof and OS backend here is disposable test
material. No administrator rights, real service, production trust root or host
state are used. This is a source-level orchestration test, not a release PASS.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization

import sofia.platform.ops.platform_installer_bundle as bundle_owner
import sofia.platform.ops.platform_installer_guided as guided
from sofia.platform.ops.platform_installation import (
    PlatformInstallationStore, install_staged_release,
)
from sofia.platform.ops.platform_installer_code_install import (
    CODE_PUBLISH_CAPABILITY,
)
from sofia.platform.ops.platform_installer_native_service import (
    DebianSystemdNativeService,
)
from sofia.platform.ops.platform_installer_operator_apps import (
    InMemoryPathAdapter, OPERATOR_APPS_CAPABILITY,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier,
)
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_platform_installation import SignedReleaseBuilder
from test.test_platform_release_verifier import platform_wheels
from test.test_platform_service_session import provision

pytestmark = pytest.mark.pkg_ops
TARGET = PlatformReleaseTarget.DEBIAN12_X86_64
WINDOWS = PlatformReleaseTarget.WINDOWS_X86_64


@pytest.fixture(autouse=True)
def debian_host(monkeypatch):
    monkeypatch.setattr(guided, "host_release_target", lambda: TARGET)
    monkeypatch.setattr(bundle_owner, "host_release_target", lambda: TARGET)


@pytest.fixture
def bundle(tmp_path, platform_wheels):
    builder = SignedReleaseBuilder(tmp_path / "signed", platform_wheels)
    staged, manifest, _signature = builder.stage(
        release_id="guided-disposable-release", revision=4,
    )
    root = tmp_path / "bundle"
    root.mkdir()
    shutil.copytree(staged, root / "release")
    installer = root / "installer"
    installer.mkdir()
    public = builder._key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (installer / "trusted-publisher.pem").write_bytes(public)
    (installer / "trust.json").write_text(json.dumps({
        "schema": guided.TRUST_SCHEMA,
        "publisher_key_sha256": sha256(public).hexdigest(),
        "signer_key_id": builder.signer_key_id,
    }), encoding="utf-8")
    return SimpleNamespace(
        root=root, release=root / "release", builder=builder,
        manifest=manifest, trust=installer,
    )


@pytest.fixture
def paths(tmp_path, canonical_state_path):
    identity, _current, local_state = provision(tmp_path / "provisioned-host")
    return guided.GuidedPaths(
        target=TARGET,
        destination=tmp_path / "opt/aegis/platform",
        identity_home=identity.home,
        local_state=local_state,
        safe_state=canonical_state_path,
        store_path=tmp_path / "var/lib/aegis/installation/platform-installation.db",
        operator_bin=tmp_path / "opt/aegis/bin",
        global_bin=tmp_path / "usr/local/bin",
        start_menu=None,
        desktop=tmp_path / "usr/share/applications",
        approved_roots=(tmp_path,),
    )


class RecordingApprovalAdapter:
    def __init__(self, safe_state):
        self.safe_state = Path(safe_state)
        self.requests = []
        self.open_host_password = "NEVER-EXPOSE-THIS-SECRET"

    def authorize(self, request):
        self.requests.append(request)
        now = datetime.now(timezone.utc)
        approval = ExecutionApproval(
            approval_id=f"approval:guided-{len(self.requests)}",
            capability=request["capability"],
            request_fingerprint=request["fingerprint"],
            approved_by="person:sparks",
            approved_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(minutes=5),
        )
        record_verified_owner_approval(
            ExecutionApprovalVerifier(self.safe_state), approval,
        )
        return approval.approval_id


class DenyingApprovalAdapter:
    def authorize(self, _request):
        raise RuntimeError("owner declined the attended ceremony")


class FakeShortcuts:
    def __init__(self):
        self.created = []
        self.removed = []

    def create(self, spec):
        self.created.append(spec)

    def remove(self, spec):
        self.removed.append(spec)
        spec.path.unlink(missing_ok=True)


def _fake_backend(effects):
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

    backend.register = lambda spec: receipt(spec, "RUNNING")
    backend.restart_verified = lambda spec: receipt(spec, "RUNNING")
    backend.replace_verified = lambda previous, candidate: receipt(candidate, "RUNNING")
    backend.stop_and_unregister = lambda spec: receipt(spec, "REMOVED")
    return backend


def _run(bundle, paths, **kwargs):
    return guided.run_guided(
        bundle.root, target=TARGET, paths=paths,
        elevation_check=lambda: True, **kwargs,
    )


def test_check_verifies_release_and_plan_with_zero_effects(bundle, paths):
    result = _run(bundle, paths, check=True)

    assert result["outcome"] == "PREVIEW_OK"
    assert result["executed"] is False
    assert result["owner_approved"] is False
    assert result["plan"]["source_sha"] == bundle.manifest.source_sha
    assert result["plan"]["revision"] == 4
    assert result["plan"]["minimum_revision"] == 4
    assert result["plan"]["manifest_sha256"] == bundle.manifest.digest
    assert result["plan"]["paths"]["destination"] == str(paths.destination)
    assert result["plan"]["identity_retention"] == "RETAIN"
    assert result["plan"]["state_retention"] == "RETAIN"
    assert result["plan"]["purge"] == "SEPARATE_NOT_DEFAULT"
    capabilities = {
        item["capability"] for item in result["plan"]["approvals_needed"]
    }
    assert capabilities == {
        CODE_PUBLISH_CAPABILITY, guided.NATIVE_CHANNEL_CAPABILITY,
        OPERATOR_APPS_CAPABILITY,
    }
    assert not paths.destination.exists()
    assert not paths.operator_bin.exists()
    assert not paths.store_path.exists()


def test_check_rejects_missing_installer_trust_anchor(bundle, paths):
    (bundle.trust / "trust.json").unlink()

    result = _run(bundle, paths, check=True)

    assert result["outcome"] == "DENIED"
    assert result["error"]["code"] == "TRUST_ANCHOR_MISSING"
    assert not paths.destination.exists()


def test_check_rejects_tampered_release_signature(bundle, paths):
    signature = bundle.release / "release-signature.json"
    document = json.loads(signature.read_text(encoding="utf-8"))
    document["signature_b64"] = "A" * 88
    signature.write_text(json.dumps(document), encoding="utf-8")

    result = _run(bundle, paths, check=True)

    assert result["outcome"] == "DENIED"
    assert result["error"]["code"] == "RELEASE_REJECTED"
    assert not paths.destination.exists()


def test_check_rejects_wrong_signer_and_wrong_key_pin(bundle, paths):
    trust_path = bundle.trust / "trust.json"
    original = json.loads(trust_path.read_text(encoding="utf-8"))

    trust_path.write_text(json.dumps({
        **original, "signer_key_id": "attacker",
    }), encoding="utf-8")
    wrong_signer = _run(bundle, paths, check=True)
    assert wrong_signer["outcome"] == "DENIED"
    assert wrong_signer["error"]["code"] == "RELEASE_REJECTED"

    trust_path.write_text(json.dumps({
        **original, "publisher_key_sha256": "0" * 64,
    }), encoding="utf-8")
    wrong_pin = _run(bundle, paths, check=True)
    assert wrong_pin["outcome"] == "DENIED"
    assert wrong_pin["error"]["code"] == "TRUST_ANCHOR_INVALID"


def test_flat_release_media_cannot_supply_its_own_trust_anchor(bundle, paths):
    flat = bundle.root / "flat"
    shutil.copytree(bundle.release, flat)
    shutil.copytree(bundle.trust, flat / "installer")

    result = guided.run_guided(flat, check=True, target=TARGET, paths=paths)

    assert result["outcome"] == "DENIED"
    assert result["error"]["code"] == "TRUST_NOT_INDEPENDENT"
    assert not paths.destination.exists()


def test_canonical_default_paths_are_approved_for_both_hosts():
    windows = guided.default_paths(WINDOWS, environ={
        "ProgramFiles": r"D:\Programs",
        "ProgramData": r"D:\ProgramData",
    })
    assert windows.destination == Path(r"D:\Programs\Aegis\platform")
    assert windows.identity_home == Path(r"D:\ProgramData\Aegis\identity")
    assert windows.store_path == Path(
        r"D:\ProgramData\Aegis\installation\platform-installation.db"
    )
    assert windows.operator_bin == Path(r"D:\Programs\Aegis\bin")

    debian = guided.default_paths(TARGET)
    assert debian.destination == Path("/opt/aegis/platform")
    assert debian.identity_home == Path("/var/lib/aegis/identity")
    assert debian.local_state == Path("/var/lib/aegis/state")
    assert debian.store_path == Path(
        "/var/lib/aegis/installation/platform-installation.db"
    )
    assert debian.global_bin == Path("/usr/local/bin")


def test_nonelevated_mutation_refuses_before_any_approval_or_effect(bundle, paths):
    approvals = RecordingApprovalAdapter(paths.safe_state)
    result = guided.run_guided(
        bundle.root, operation="install", target=TARGET, paths=paths,
        approval_adapter=approvals, elevation_check=lambda: False,
    )

    assert result["outcome"] == "ELEVATION_REQUIRED"
    assert result["error"]["code"] == "ELEVATION_REQUIRED"
    assert result["executed"] is False
    assert approvals.requests == []
    assert not paths.destination.exists()


def test_denied_owner_approval_produces_no_release_or_service_effect(bundle, paths):
    effects = []
    result = _run(
        bundle, paths, operation="install",
        approval_adapter=DenyingApprovalAdapter(),
        native_backend=_fake_backend(effects),
        operator_apps_path_adapter=InMemoryPathAdapter(),
        operator_apps_shortcut_adapter=FakeShortcuts(),
    )

    assert result["outcome"] == "DENIED"
    assert effects == []
    assert not paths.destination.exists()
    assert not paths.operator_bin.exists()


def test_successful_one_step_orchestration_uses_existing_owners(bundle, paths):
    effects = []
    approvals = RecordingApprovalAdapter(paths.safe_state)
    shortcuts = FakeShortcuts()
    result = _run(
        bundle, paths, operation="install", approval_adapter=approvals,
        native_backend=_fake_backend(effects),
        operator_apps_path_adapter=InMemoryPathAdapter(),
        operator_apps_shortcut_adapter=shortcuts,
    )

    assert result["outcome"] == "INSTALLED", json.dumps(result, sort_keys=True)
    assert result["executed"] is True
    assert result["owner_approved"] is True
    assert result["core_activated"] is False
    assert result["service_health"] == "UNKNOWN"
    assert len(effects) == 1 and effects[0][0] == "RUNNING"
    assert [item["capability"] for item in approvals.requests] == [
        CODE_PUBLISH_CAPABILITY,
        guided.NATIVE_CHANNEL_CAPABILITY,
        OPERATOR_APPS_CAPABILITY,
    ]
    assert result["operator_apps_result"]["outcome"] == "OK"
    assert (paths.operator_bin / "aegis").is_file()
    assert (paths.global_bin / "aegis").is_file()
    assert result["plan"]["identity_retention"] == "RETAIN"
    assert result["plan"]["state_retention"] == "RETAIN"
    encoded = json.dumps(result, sort_keys=True)
    assert approvals.open_host_password not in encoded
    assert "approval_id" not in encoded


def test_uninstall_retains_identity_and_protected_state(bundle, paths):
    effects = []
    approvals = RecordingApprovalAdapter(paths.safe_state)
    backend = _fake_backend(effects)
    installed = _run(
        bundle, paths, operation="install", approval_adapter=approvals,
        native_backend=backend,
        operator_apps_path_adapter=InMemoryPathAdapter(),
        operator_apps_shortcut_adapter=FakeShortcuts(),
    )
    assert installed["outcome"] == "INSTALLED"
    identity_before = {
        item.relative_to(paths.identity_home): item.read_bytes()
        for item in paths.identity_home.rglob("*") if item.is_file()
    }
    state_before = paths.local_state.read_bytes()

    removed = _run(
        bundle, paths, operation="uninstall", approval_adapter=approvals,
        native_backend=backend,
        operator_apps_path_adapter=InMemoryPathAdapter(),
        operator_apps_shortcut_adapter=FakeShortcuts(),
    )

    assert removed["outcome"] == "UNINSTALLED"
    assert removed["identity_retention"] == "RETAIN"
    assert removed["state_retention"] == "RETAIN"
    identity_after = {
        item.relative_to(paths.identity_home): item.read_bytes()
        for item in paths.identity_home.rglob("*") if item.is_file()
    }
    assert identity_after == identity_before
    assert paths.local_state.read_bytes() == state_before
    assert paths.destination.is_dir()
    assert not (paths.operator_bin / "aegis").exists()
    assert [item[0] for item in effects] == ["RUNNING", "REMOVED"]


def _seed_installed(paths, builder):
    staged, manifest, _signature = builder.stage(
        release_id="guided-existing-release", revision=2,
    )
    store = PlatformInstallationStore(paths.store_path)
    install_staged_release(
        staged, paths.destination, store=store, verifier=builder.verifier,
    )
    return manifest


@pytest.mark.parametrize("operation,expected_outcome", (
    ("install", "INSTALLED"),
    ("update", "UPDATED"),
    ("repair", "REPAIRED"),
    ("rollback", "ROLLED_BACK"),
    ("uninstall", "UNINSTALLED"),
))
def test_lifecycle_routing_uses_existing_commands_and_previous_destination(
        bundle, paths, operation, expected_outcome):
    if operation != "install":
        _seed_installed(paths, bundle.builder)
    calls = []

    def installer_command(command, inputs, *, backend=None,
                          operator_apps_path_adapter=None,
                          operator_apps_shortcut_adapter=None,
                          approval_provider=None):
        calls.append((command, inputs))
        if command == "status":
            return {"outcome": "OK", "service_state": "RUNNING"}
        destination = inputs.destination
        runtime = destination / "runtime/python/bin/python3.12"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_bytes(b"fake-installed-runtime")
        (destination / "assets").mkdir(parents=True, exist_ok=True)
        return {
            "outcome": expected_outcome,
            "service_health": "UNKNOWN",
            "core_activated": False,
        }

    app_calls = []

    def operator_apps_command(app_operation, inputs, *, path_adapter=None,
                              shortcut_adapter=None, approval_provider=None):
        app_calls.append((app_operation, inputs))
        return {"outcome": "OK"}

    result = _run(
        bundle, paths, operation=operation,
        installer_command=installer_command,
        operator_apps_command=operator_apps_command,
        operator_apps_path_adapter=InMemoryPathAdapter(),
        operator_apps_shortcut_adapter=FakeShortcuts(),
    )

    assert result["outcome"] == expected_outcome
    assert calls[0][0] == operation
    requested_inputs = calls[0][1]
    if operation in ("update", "rollback"):
        assert requested_inputs.previous_destination == paths.destination
        assert requested_inputs.destination != paths.destination
    else:
        assert requested_inputs.previous_destination is None
    assert app_calls and app_calls[0][0] == (
        "update" if operation == "rollback" else operation
    )
    assert any(command == "status" for command, _inputs in calls)


def test_json_entrypoint_has_no_ansi_and_exposes_plan(bundle, capsys):
    argv = [
        "--bundle-root", str(bundle.root), "--check", "--json",
    ]
    code = guided.main(argv)
    output = capsys.readouterr().out
    assert code == 0
    assert "\x1b" not in output
    document = json.loads(output)
    assert document["outcome"] == "PREVIEW_OK"
    assert document["schema"] == guided.GUIDED_SCHEMA
    assert document["plan"]["schema"] == guided.PLAN_SCHEMA
    assert document["plan"]["paths"]["destination"] == str(
        guided.default_paths(TARGET).destination
    )
