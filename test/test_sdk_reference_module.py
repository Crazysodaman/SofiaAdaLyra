"""Golden SDK module conformance against real Platform lifecycle/services.

Test-only ephemeral Ed25519 signing + disposable canonical SQLite. No signing
identity, module approval, host process, UI, or operator secret is created.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from examples.sdk_reference_module.reference import (
    CAPABILITY_ID, MODULE_ID, MODULE_VERSION, ReferenceModule,
    capability_registrations, settings_contract,
)
from sofia.platform.capability import CapabilitySystem
from sofia.platform.capability.model import (
    CapabilityRequest, CapabilityResultKind,
)
from sofia.platform.config.settings_authority import SettingsApplyState
from sofia.platform.modules import (
    ModuleLifecycle, ModuleSettingsService, OperationProfileKind,
    verify_module_package,
)
from sofia.sdk import (
    SDK_PROTOCOL_VERSION, ProtocolVersion, ProtocolVersionRange,
    negotiate_protocol,
)
from test.test_module_lifecycle_v1 import compatibility, manager, prepare
from test.test_module_package_v1 import manifest, signed

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SOURCE = ROOT / "examples" / "sdk_reference_module" / "reference.py"


@pytest.fixture
def verified_reference(tmp_path):
    """Sign only copied example bytes with a throwaway in-memory test key."""
    root = tmp_path / "reference-package"
    root.mkdir()
    (root / "reference.py").write_bytes(REFERENCE_SOURCE.read_bytes())
    artifact_digest = sha256((root / "reference.py").read_bytes()).hexdigest()
    original = manifest(
        (("reference.py", artifact_digest),),
        module_id=MODULE_ID, version=MODULE_VERSION,
        capabilities=(CAPABILITY_ID,), schema_version=3,
        settings_contract=settings_contract(),
    )
    key = Ed25519PrivateKey.generate()
    approved = signed(original, key)
    public_key = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return verify_module_package(
        approved, package_root=root, trusted_public_key=public_key,
    )


def _ping(capability, nonce="request-1", *, rationale="owner-approved-test"):
    return CapabilityRequest(
        capability=capability, parameters={"nonce": nonce},
        requested_scope=None, rationale=rationale,
    )


def _settings_update(settings, package, lifecycle, *, changes, revision, key):
    return settings.update(
        module_id=MODULE_ID,
        expected_package_digest=package.package_digest,
        expected_lifecycle_revision=lifecycle.revision,
        expected_revision=revision,
        client_id="test:reference-owner",
        principal_id="principal:synthetic-owner",
        audience_id="audience:test-only",
        approval_ref="approval:test-only",
        idempotency_key=key,
        changes=changes,
        now=NOW,
    )


def test_reference_module_is_bounded_and_only_declares_current_sdk():
    sample = ReferenceModule()
    registers = sample.capability_registrations()
    assert len(registers) == 1
    capability, handler = registers[0]
    assert capability.name == CAPABILITY_ID
    assert capability_registrations()[0][0].name == CAPABILITY_ID
    response = handler(_ping(capability))
    assert response == {
        "schema": "aegis.sdk.reference.ping.v1",
        "module_id": MODULE_ID,
        "sdk_protocol": str(SDK_PROTOCOL_VERSION),
        "nonce": "request-1",
        "display_mode": "compact",
        "effect": "none",
        "data_persisted": False,
        "runtime_health_verified": False,
    }
    with pytest.raises(ValueError, match="nonce"):
        handler(_ping(capability, "a\nunsafe"))
    with pytest.raises(ValueError, match="nonce"):
        handler(_ping(capability, "a" * 65))
    with pytest.raises(ValueError, match="exact"):
        handler(CapabilityRequest(
            capability, {"nonce": "ok", "extra": "no"},
            None, "test-only",
        ))


def test_signed_reference_installs_activates_responds_and_unplugs(
    canonical_state_path, tmp_path, verified_reference,
):
    package = verified_reference
    sample = ReferenceModule()
    system = CapabilitySystem(
        authorization_checker=lambda req: req.rationale == "owner-approved-test",
    )
    lifecycle, operations = manager(
        canonical_state_path, tmp_path / "staged", system,
    )
    staged = prepare(lifecycle, package)
    assert staged.lifecycle is ModuleLifecycle.STAGED
    assert system.capability_names() == ()

    regs = sample.capability_registrations()
    active = lifecycle.activate(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=regs, operation_ref="approval:test-activate",
        actor="principal:synthetic-owner", now=NOW,
    )
    assert active.lifecycle is ModuleLifecycle.ACTIVE
    cap = system.resolve(CAPABILITY_ID)
    assert system.execute(_ping(cap)).kind is CapabilityResultKind.SUCCESS
    denied = system.execute(_ping(cap, rationale="denied"))
    assert denied.kind is CapabilityResultKind.UNAUTHORIZED
    assert denied.evidence is None

    paused = lifecycle.pause(
        MODULE_ID, expected_revision=active.revision,
        operation_ref="approval:test-pause",
        actor="principal:synthetic-owner", now=NOW,
    )
    assert system.capability_names() == ()
    assert system.execute(_ping(cap)).kind is CapabilityResultKind.UNAVAILABLE
    resumed = lifecycle.resume(
        package, expected_revision=paused.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=regs, operation_ref="approval:test-resume",
        actor="principal:synthetic-owner", now=NOW,
    )
    assert resumed.lifecycle is ModuleLifecycle.ACTIVE
    assert system.execute(_ping(cap)).kind is CapabilityResultKind.SUCCESS

    paused_again = lifecycle.pause(
        MODULE_ID, expected_revision=resumed.revision,
        operation_ref="approval:test-pause-again",
        actor="principal:synthetic-owner", now=NOW,
    )
    disabled = lifecycle.disable(
        MODULE_ID, expected_revision=paused_again.revision,
        operation_ref="approval:test-disable",
        actor="principal:synthetic-owner", now=NOW,
    )
    removed = lifecycle.remove(
        MODULE_ID, expected_revision=disabled.revision,
        operation_ref="approval:test-remove",
        actor="principal:synthetic-owner", now=NOW,
    )
    assert removed.lifecycle is ModuleLifecycle.REMOVED
    assert system.capability_names() == ()
    assert (tmp_path / "staged" / package.package_digest).is_dir()
    assert [entry[0] for entry in operations] == [
        "approve", "stage", "activate", "pause", "resume",
        "pause", "disable", "remove",
    ]
    assert lifecycle.transition_receipt(MODULE_ID, removed.revision).to_lifecycle is ModuleLifecycle.REMOVED


def test_reference_settings_live_pending_restart_and_stale_edit(
    canonical_state_path, tmp_path, verified_reference,
):
    package = verified_reference
    sample = ReferenceModule()
    system = CapabilitySystem(authorization_checker=lambda req: True)
    lifecycle, _ = manager(canonical_state_path, tmp_path / "staged", system)
    staged = prepare(lifecycle, package)
    active = lifecycle.activate(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=sample.capability_registrations(),
        operation_ref="approval:test-activate",
        actor="principal:synthetic-owner", now=NOW,
    )
    approvals = []
    settings = ModuleSettingsService(
        canonical_state_path, authorizer=lambda request, db: (
            approvals.append(request) or request.approval_ref == "approval:test-only"
        ),
    )
    assert settings.catalog()[0]["module_id"] == MODULE_ID
    settings.register_apply_handler(
        module_id=MODULE_ID, package_digest=package.package_digest,
        handler=sample.apply_live_settings,
    )
    first = _settings_update(
        settings, package, active,
        changes={"display.mode": "verbose"}, revision=0, key="set-display",
    )
    assert first.apply_state is SettingsApplyState.APPLIED
    assert first.revision == first.effective_revision == 1
    ping = system.execute(_ping(system.resolve(CAPABILITY_ID)))
    assert ping.evidence["display_mode"] == "verbose"
    replay = _settings_update(
        settings, package, active,
        changes={"display.mode": "verbose"}, revision=0, key="set-display",
    )
    assert replay == first
    assert len(approvals) == 1

    pending = _settings_update(
        settings, package, active,
        changes={"demo.transport": "isolated"}, revision=1,
        key="set-restart-mode",
    )
    assert pending.apply_state is SettingsApplyState.PENDING_COMPONENT_RESTART
    assert pending.revision == 2 and pending.effective_revision == 1
    assert settings.snapshot(module_id=MODULE_ID)["values"] == {
        "display.mode": "verbose", "demo.transport": "isolated",
    }
    assert lifecycle.describe(MODULE_ID).lifecycle is ModuleLifecycle.ACTIVE

    paused = lifecycle.pause(
        MODULE_ID, expected_revision=active.revision,
        operation_ref="approval:test-pause",
        actor="principal:synthetic-owner", now=NOW,
    )
    with pytest.raises(RuntimeError, match="lifecycle revision conflict"):
        _settings_update(
            settings, package, active, changes={"display.mode": "compact"},
            revision=2, key="stale-edit",
        )
    assert paused.lifecycle is ModuleLifecycle.PAUSED


def test_protocol_negotiation_and_rust_python_sdk_version_parity():
    """CI guard: explicit schema change cannot silently drift across languages."""
    rust = ROOT / "rust" / "crates" / "sofia-contracts" / "src" / "lib.rs"
    text = rust.read_text(encoding="utf-8")
    match = re.search(
        r'pub const SUPPORTED_PROTOCOL:\s*&str\s*=\s*"([0-9]+\.[0-9]+)"',
        text,
    )
    assert match is not None
    assert match.group(1) == str(SDK_PROTOCOL_VERSION)
    supported = ProtocolVersionRange(
        SDK_PROTOCOL_VERSION, SDK_PROTOCOL_VERSION,
    )
    assert negotiate_protocol(supported, supported) == SDK_PROTOCOL_VERSION
    with pytest.raises(RuntimeError, match="incompatible"):
        negotiate_protocol(
            supported,
            ProtocolVersionRange(ProtocolVersion(2, 0), ProtocolVersion(2, 1)),
        )
