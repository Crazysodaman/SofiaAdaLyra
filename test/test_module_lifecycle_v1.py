from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.capability import Capability, CapabilitySystem
from sofia.platform.modules import (
    ModulePlatformTarget,
    ModuleLifecycle,
    ModuleLifecycleManager,
    OperationProfileKind,
    evaluate_module_compatibility,
    verify_module_package,
)
from test.test_module_package_v1 import manifest, signed
from sofia.platform.modules import DependencyRequirement


NOW = datetime(2026, 10, 22, 22, tzinfo=timezone.utc)


def verified_package(tmp_path):
    package = tmp_path / "source"
    package.mkdir()
    artifact = package / "module.py"
    artifact.write_text("MODULE = 'reviewed'\n", encoding="utf-8")
    value = manifest((("module.py", sha256(artifact.read_bytes()).hexdigest()),))
    key = Ed25519PrivateKey.generate()
    value = signed(value, key)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return verify_module_package(
        value, package_root=package, trusted_public_key=public,
    )


def verified_custom(tmp_path, *, directory, module_id="org.sofia.research",
                    version="9.0.0", content="MODULE = 'reviewed'\n",
                    dependencies=(), capabilities=("research.search",),
                    schema_version=1, settings_contract=None):
    package = tmp_path / directory
    package.mkdir()
    artifact = package / "module.py"
    artifact.write_text(content, encoding="utf-8")
    value = manifest(
        (("module.py", sha256(artifact.read_bytes()).hexdigest()),),
        module_id=module_id, version=version, dependencies=dependencies,
        capabilities=capabilities, schema_version=schema_version,
        settings_contract=settings_contract,
    )
    key = Ed25519PrivateKey.generate()
    value = signed(value, key)
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return verify_module_package(value, package_root=package, trusted_public_key=public)


def manager(path, store_root, system, *, allowed=True):
    calls = []
    instance = ModuleLifecycleManager(
        state_path=path, store_root=store_root, capability_system=system,
        authorizer=lambda request: (
            calls.append(
                (request.operation, request.module_id, request.operation_ref)
            )
            or allowed
        ),
    )
    return instance, calls


def compatibility(package):
    return evaluate_module_compatibility(
        package.manifest, profile=OperationProfileKind.OBSERVE,
        target=ModulePlatformTarget(
            "linux-x86_64", "1.0.0", (),
            (("cpu_millis", 100), ("ram_mib", 128)),
            ("subprocess-restricted",),
        ),
    )


def prepare(instance, package):
    found = instance.discover(package, now=NOW)
    approved = instance.approve(
        package.manifest.module_id, expected_revision=found.revision,
        operation_ref="approval:install", actor="principal:sparks", now=NOW,
    )
    return instance.stage(
        package, expected_revision=approved.revision,
        operation_ref="approval:stage", actor="principal:sparks", now=NOW,
    )


def test_signed_package_stages_immutably_and_activates_reviewed_adapter(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, calls = manager(
        canonical_state_path, tmp_path / "store", system,
    )
    staged = prepare(lifecycle, package)
    staged_root = tmp_path / "store" / package.package_digest
    assert staged.lifecycle is ModuleLifecycle.STAGED
    assert (staged_root / "module.py").read_text(encoding="utf-8") == "MODULE = 'reviewed'\n"

    handler = lambda request: {"ok": True}
    active = lifecycle.activate(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=((Capability("research.search", "search"), handler),),
        operation_ref="approval:activate", actor="principal:sparks", now=NOW,
    )
    assert active.lifecycle is ModuleLifecycle.ACTIVE
    assert system.capability_names() == ("research.search",)
    assert [item[0] for item in calls] == ["approve", "stage", "activate"]


def test_unauthorized_stage_creates_no_package_files(canonical_state_path, tmp_path):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, _ = manager(
        canonical_state_path, tmp_path / "store", system, allowed=False,
    )
    discovered = lifecycle.discover(package, now=NOW)
    with pytest.raises(PermissionError):
        lifecycle.approve(
            package.manifest.module_id, expected_revision=discovered.revision,
            operation_ref="not-approved", actor="principal:other", now=NOW,
        )
    assert list((tmp_path / "store").iterdir()) == []


def test_exact_verified_rediscovery_backfills_only_matching_signed_policy(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    lifecycle, _ = manager(
        canonical_state_path,
        tmp_path / "store",
        CapabilitySystem(authorization_checker=lambda request: True),
    )
    original = lifecycle.discover(package, now=NOW)
    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "DELETE FROM platform_module_policy WHERE module_id=?",
            (package.manifest.module_id,),
        )
        db.execute(
            "DELETE FROM platform_module_manifest_projection WHERE module_id=?",
            (package.manifest.module_id,),
        )

    rediscovered = lifecycle.discover(package, now=NOW)

    assert rediscovered == original
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT package_digest,placement_mode,isolation_profile "
            "FROM platform_module_policy WHERE module_id=?",
            (package.manifest.module_id,),
        ).fetchone() == (
            package.package_digest,
            package.manifest.placement_mode.value,
            package.manifest.isolation_profile,
        )
        projected = db.execute(
            "SELECT package_digest,manifest_json "
            "FROM platform_module_manifest_projection WHERE module_id=?",
            (package.manifest.module_id,),
        ).fetchone()
        assert projected is not None
        assert projected[0] == package.package_digest
        assert json.loads(projected[1]) == package.manifest.unsigned_document()
        db.execute(
            "UPDATE platform_module_policy SET placement_mode='HOST_PINNED' "
            "WHERE module_id=?",
            (package.manifest.module_id,),
        )
    with pytest.raises(RuntimeError, match="policy conflicts"):
        lifecycle.discover(package, now=NOW)


def test_rediscovery_rejects_changed_manifest_projection(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    lifecycle, _ = manager(
        canonical_state_path, tmp_path / "store",
        CapabilitySystem(authorization_checker=lambda request: True),
    )
    lifecycle.discover(package, now=NOW)
    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "UPDATE platform_module_manifest_projection "
            "SET manifest_json='{}' WHERE module_id=?",
            (package.manifest.module_id,),
        )

    with pytest.raises(RuntimeError, match="manifest projection conflicts"):
        lifecycle.discover(package, now=NOW)


def test_activation_capability_conflict_is_atomic(canonical_state_path, tmp_path):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    existing_handler = lambda request: None
    system.register(Capability("research.search", "existing"), existing_handler)
    lifecycle, _ = manager(canonical_state_path, tmp_path / "store", system)
    staged = prepare(lifecycle, package)
    with pytest.raises(ValueError, match="already registered"):
        lifecycle.activate(
            package, expected_revision=staged.revision,
            profile=OperationProfileKind.OBSERVE,
            compatibility=compatibility(package),
            registrations=((Capability("research.search", "new"), lambda request: None),),
            operation_ref="approval:activate", actor="principal:sparks", now=NOW,
        )
    assert lifecycle.describe(package.manifest.module_id).lifecycle is ModuleLifecycle.STAGED
    assert system.resolve("research.search").description == "existing"


def test_incompatible_target_cannot_activate_signed_package(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, calls = manager(canonical_state_path, tmp_path / "store", system)
    staged = prepare(lifecycle, package)
    incompatible = evaluate_module_compatibility(
        package.manifest, profile=OperationProfileKind.OBSERVE,
        target=ModulePlatformTarget(
            "windows-arm64", "1.0.0", (),
            (("cpu_millis", 100), ("ram_mib", 128)),
            ("subprocess-restricted",),
        ),
    )
    with pytest.raises(PermissionError, match="incompatible"):
        lifecycle.activate(
            package, expected_revision=staged.revision,
            profile=OperationProfileKind.OBSERVE,
            compatibility=incompatible,
            registrations=((Capability("research.search", "search"), lambda request: None),),
            operation_ref="approval:activate", actor="principal:sparks", now=NOW,
        )
    assert system.capability_names() == ()
    assert calls[-1][0] == "stage"


def test_pause_removes_exact_module_capabilities(canonical_state_path, tmp_path):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, _ = manager(canonical_state_path, tmp_path / "store", system)
    staged = prepare(lifecycle, package)
    handler = lambda request: None
    active = lifecycle.activate(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=((Capability("research.search", "search"), handler),),
        operation_ref="approval:activate", actor="principal:sparks", now=NOW,
    )
    paused = lifecycle.pause(
        package.manifest.module_id, expected_revision=active.revision,
        operation_ref="approval:pause", actor="principal:sparks", now=NOW,
    )
    assert paused.lifecycle is ModuleLifecycle.PAUSED
    assert system.capability_names() == ()


def test_restart_does_not_claim_stale_module_active(canonical_state_path, tmp_path):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, _ = manager(canonical_state_path, tmp_path / "store", system)
    staged = prepare(lifecycle, package)
    lifecycle.activate(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(package),
        registrations=((Capability("research.search", "search"), lambda request: None),),
        operation_ref="approval:activate", actor="principal:sparks", now=NOW,
    )

    restarted_system = CapabilitySystem(authorization_checker=lambda request: True)
    restarted, _ = manager(
        canonical_state_path, tmp_path / "store", restarted_system,
    )
    status = restarted.describe(package.manifest.module_id)
    assert status.lifecycle is ModuleLifecycle.PAUSED
    assert status.reason == "runtime restarted; adapter requires reconciliation"
    assert restarted_system.capability_names() == ()


def test_lifecycle_compare_and_swap_rejects_stale_revision(canonical_state_path, tmp_path):
    package = verified_package(tmp_path)
    lifecycle, _ = manager(
        canonical_state_path, tmp_path / "store",
        CapabilitySystem(authorization_checker=lambda request: True),
    )
    found = lifecycle.discover(package, now=NOW)
    lifecycle.approve(
        package.manifest.module_id, expected_revision=found.revision,
        operation_ref="approval:one", actor="principal:sparks", now=NOW,
    )
    with pytest.raises(RuntimeError, match="revision/state"):
        lifecycle.approve(
            package.manifest.module_id, expected_revision=found.revision,
            operation_ref="approval:stale", actor="principal:sparks", now=NOW,
        )


def test_existing_staged_manifest_must_match_verified_identity(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    lifecycle, _ = manager(
        canonical_state_path, tmp_path / "store",
        CapabilitySystem(authorization_checker=lambda request: True),
    )
    found = lifecycle.discover(package, now=NOW)
    approved = lifecycle.approve(
        package.manifest.module_id, expected_revision=found.revision,
        operation_ref="approval:install", actor="principal:sparks", now=NOW,
    )
    destination = tmp_path / "store" / package.package_digest
    destination.mkdir()
    (destination / "module.py").write_bytes((package.package_root / "module.py").read_bytes())
    (destination / "manifest.v1.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest conflicts"):
        lifecycle.stage(
            package, expected_revision=approved.revision,
            operation_ref="approval:stage", actor="principal:sparks", now=NOW,
        )
    assert lifecycle.describe(package.manifest.module_id).lifecycle is ModuleLifecycle.APPROVED


def test_existing_stage_rejects_undeclared_files(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    lifecycle, _ = manager(
        canonical_state_path, tmp_path / "store",
        CapabilitySystem(authorization_checker=lambda request: True),
    )
    found = lifecycle.discover(package, now=NOW)
    approved = lifecycle.approve(
        package.manifest.module_id, expected_revision=found.revision,
        operation_ref="approval:install", actor="principal:sparks", now=NOW,
    )
    destination = tmp_path / "store" / package.package_digest
    destination.mkdir()
    (destination / "undeclared.py").write_text("unexpected", encoding="utf-8")
    with pytest.raises(RuntimeError, match="undeclared"):
        lifecycle.stage(
            package, expected_revision=approved.revision,
            operation_ref="approval:stage", actor="principal:sparks", now=NOW,
        )


def test_pause_resume_quarantine_disable_and_remove_are_authorized_and_bounded(
    canonical_state_path, tmp_path,
):
    package = verified_package(tmp_path)
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, calls = manager(canonical_state_path, tmp_path / "store", system)
    staged = prepare(lifecycle, package)
    registrations = ((Capability("research.search", "search"), lambda request: None),)
    active = lifecycle.activate(
        package, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE, registrations=registrations,
        compatibility=compatibility(package),
        operation_ref="approval:activate", actor="principal:sparks", now=NOW,
    )
    paused = lifecycle.pause(
        package.manifest.module_id, expected_revision=active.revision,
        operation_ref="approval:pause", actor="principal:sparks", now=NOW,
    )
    resumed = lifecycle.resume(
        package, expected_revision=paused.revision,
        profile=OperationProfileKind.OBSERVE, registrations=registrations,
        compatibility=compatibility(package),
        operation_ref="approval:resume", actor="principal:sparks", now=NOW,
    )
    quarantined = lifecycle.quarantine(
        package.manifest.module_id, expected_revision=resumed.revision,
        operation_ref="maintenance:fault", actor="platform:supervisor",
        reason="health threshold exceeded", now=NOW,
    )
    disabled = lifecycle.disable(
        package.manifest.module_id, expected_revision=quarantined.revision,
        operation_ref="approval:disable", actor="principal:sparks", now=NOW,
    )
    removed = lifecycle.remove(
        package.manifest.module_id, expected_revision=disabled.revision,
        operation_ref="approval:remove", actor="principal:sparks", now=NOW,
    )
    assert removed.lifecycle is ModuleLifecycle.REMOVED
    assert system.capability_names() == ()
    assert (tmp_path / "store" / package.package_digest).is_dir()
    assert [call[0] for call in calls][-6:] == [
        "activate", "pause", "resume", "quarantine", "disable", "remove",
    ]


def test_verified_update_and_rollback_preserve_history_without_auto_activation(
    canonical_state_path, tmp_path,
):
    original = verified_custom(tmp_path, directory="original")
    replacement = verified_custom(
        tmp_path, directory="replacement", version="9.1.0",
        content="MODULE = 'replacement'\n",
    )
    system = CapabilitySystem(authorization_checker=lambda request: True)
    lifecycle, calls = manager(canonical_state_path, tmp_path / "store", system)
    staged = prepare(lifecycle, original)
    updated = lifecycle.update(
        replacement, expected_revision=staged.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(replacement),
        operation_ref="approval:update", actor="principal:sparks", now=NOW,
    )
    assert updated.version == "9.1.0"
    assert updated.lifecycle is ModuleLifecycle.STAGED
    assert system.capability_names() == ()
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT package_digest,placement_mode FROM platform_module_policy "
            "WHERE module_id=?",
            (updated.module_id,),
        ).fetchone() == (
            replacement.package_digest,
            replacement.manifest.placement_mode.value,
        )
        assert db.execute(
            "SELECT package_digest FROM platform_module_manifest_projection "
            "WHERE module_id=?", (updated.module_id,),
        ).fetchone() == (replacement.package_digest,)
    rolled_back = lifecycle.rollback(
        original, expected_revision=updated.revision,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(original),
        operation_ref="approval:rollback", actor="principal:sparks", now=NOW,
    )
    assert rolled_back.version == "9.0.0"
    assert rolled_back.lifecycle is ModuleLifecycle.STAGED
    with sqlite3.connect(canonical_state_path) as db:
        assert db.execute(
            "SELECT package_digest,placement_mode FROM platform_module_policy "
            "WHERE module_id=?",
            (rolled_back.module_id,),
        ).fetchone() == (
            original.package_digest,
            original.manifest.placement_mode.value,
        )
        assert db.execute(
            "SELECT package_digest FROM platform_module_manifest_projection "
            "WHERE module_id=?", (rolled_back.module_id,),
        ).fetchone() == (original.package_digest,)
    assert [item[0] for item in calls][-2:] == ["update", "rollback"]


def test_dependency_aware_removal_refuses_installed_dependents(
    canonical_state_path, tmp_path,
):
    library = verified_custom(
        tmp_path, directory="library", module_id="org.sofia.library",
        capabilities=("library.read",),
    )
    dependent = verified_custom(
        tmp_path, directory="dependent",
        dependencies=(DependencyRequirement("org.sofia.library", "9.0.0", "10.0.0"),),
    )
    lifecycle, _ = manager(
        canonical_state_path, tmp_path / "store",
        CapabilitySystem(authorization_checker=lambda request: True),
    )
    library_staged = prepare(lifecycle, library)
    disabled = lifecycle.disable(
        library.manifest.module_id, expected_revision=library_staged.revision,
        operation_ref="approval:disable", actor="principal:sparks", now=NOW,
    )
    prepare(lifecycle, dependent)
    with pytest.raises(RuntimeError, match="required by installed dependent"):
        lifecycle.remove(
            library.manifest.module_id, expected_revision=disabled.revision,
            operation_ref="approval:remove", actor="principal:sparks", now=NOW,
        )
