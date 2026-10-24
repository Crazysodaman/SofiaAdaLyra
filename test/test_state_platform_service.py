from datetime import datetime, timezone

import pytest

from sofia.platform.ops.backup import BackupCipher, BackupEngine
from sofia.platform.state import (
    StateClass,
    StateNamespaceSpec,
    StatePlatformService,
    StateRecord,
    StateWrite,
)
from sofia.platform.state.component_schema import verify_production_component_schemas


NOW = datetime(2026, 10, 22, 21, tzinfo=timezone.utc)


PRIVATE = StateNamespaceSpec(
    "platform.test.private", "PLATFORM-TEST",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True, audience_scoped=True,
)
AUDIT = StateNamespaceSpec(
    "platform.test.audit", "PLATFORM-TEST",
    StateClass.PROTECTED,
    principal_scoped=False, audience_scoped=False, append_only=True,
)


def service(path, *, backup=False):
    verify_production_component_schemas(path)
    return StatePlatformService(
        state_path=path,
        namespaces=(PRIVATE, AUDIT),
        backup_engine=BackupEngine(BackupCipher(b"x" * 32)) if backup else None,
    )


def test_registered_namespace_enforces_principal_and_audience(canonical_state_path):
    state = service(canonical_state_path)
    with pytest.raises(PermissionError, match="principal"):
        state.namespace_open(
            PRIVATE.name, principal_id=None, audience="private",
        )
    with pytest.raises(PermissionError, match="audience"):
        state.namespace_open(
            PRIVATE.name, principal_id="principal:owner", audience=None,
        )
    handle = state.namespace_open(
        PRIVATE.name, principal_id="principal:owner", audience="private",
    )
    persisted, = state.write_transaction((StateWrite(StateRecord(
        key=handle.key("setting"),
        state_class=StateClass.SHARED_AUTHORITATIVE,
        revision=1, value=b"enabled", updated_at=NOW,
        source="test:platform-state",
    ), None),))
    assert persisted.value == b"enabled"


def test_unregistered_and_wrong_class_writes_fail_closed(canonical_state_path):
    state = service(canonical_state_path)
    handle = state.namespace_open(
        PRIVATE.name, principal_id="principal:owner", audience="private",
    )
    wrong = StateRecord(
        key=handle.key("setting"), state_class=StateClass.PROTECTED,
        revision=1, value=b"no", updated_at=NOW, source="test",
    )
    with pytest.raises(PermissionError, match="state class"):
        state.write_transaction((StateWrite(wrong, None),))


def test_append_only_namespace_cannot_revise_record(canonical_state_path):
    state = service(canonical_state_path)
    handle = state.namespace_open(AUDIT.name, principal_id=None, audience=None)
    first = StateRecord(
        key=handle.key("event-1"), state_class=StateClass.PROTECTED,
        revision=1, value=b"first", updated_at=NOW, source="test",
    )
    state.write_transaction((StateWrite(first, None),))
    revised = StateRecord(
        key=first.key, state_class=first.state_class, revision=2,
        value=b"changed", updated_at=NOW, source="test",
    )
    with pytest.raises(PermissionError, match="append-only"):
        state.write_transaction((StateWrite(revised, 1),))


def test_namespace_contract_change_requires_migration(canonical_state_path):
    service(canonical_state_path)
    changed = StateNamespaceSpec(
        PRIVATE.name, PRIVATE.owner, PRIVATE.state_class,
        principal_scoped=True, audience_scoped=True, append_only=True,
    )
    with pytest.raises(RuntimeError, match="reviewed migration"):
        StatePlatformService(
            state_path=canonical_state_path,
            namespaces=(changed, AUDIT),
        )


def test_migration_plan_is_pinned_and_inert(canonical_state_path):
    state = service(canonical_state_path)
    plan = state.migrate_plan(
        component="state-plane", target_revision=2,
        migration_document=b"reviewed state-plane migration v2",
    )
    assert plan.current_revision == 1
    assert plan.target_revision == 2
    assert plan.requires_backup is True
    assert plan.executable is False
    assert len(plan.migration_digest) == 64


def test_backup_and_restore_plan_use_verified_existing_engine(
    canonical_state_path, tmp_path,
):
    state = service(canonical_state_path, backup=True)
    backup_dir, evidence = state.backup(
        destination_root=tmp_path / "backups",
        source_host_id="test-host", failure_domain="test-domain", now=NOW,
    )
    manifest = state.verify_backup(backup_dir)
    assert manifest.backup_id == evidence.backup_id
    plan = state.restore_plan(
        backup_dir=backup_dir,
        target_state_path=tmp_path / "restored" / "sofia.db",
    )
    assert plan.backup_id == evidence.backup_id
    assert plan.executable is False
    assert plan.requires_replacement_approval is False
