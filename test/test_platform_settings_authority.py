from datetime import datetime, timezone

import pytest

from sofia.platform.config.settings_authority import (
    CanonicalSettingsService, SettingsApplyState, SettingsOwner,
)
from sofia.platform.config.user_settings import RuntimeUserSettingsStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 25, 20, tzinfo=timezone.utc)
CORE = frozenset({SettingsOwner.CORE})
HOST = frozenset({SettingsOwner.HOST})


def service(tmp_path, apply=None):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return path, CanonicalSettingsService(path, live_apply=apply)


def update(authority, *, key="change:1", expected=0, changes=None, owners=CORE):
    return authority.update(
        client_id="client:windows-owner", principal_id="principal:sparks",
        audience_id="audience:owner-private", idempotency_key=key,
        expected_revision=expected,
        changes=changes or {"location_label": "Workshop"},
        writable_owners=owners, now=NOW,
    )


def test_live_update_is_cas_applied_and_idempotent(tmp_path):
    calls = []
    path, authority = service(
        tmp_path, lambda settings, fields: calls.append((settings, fields)),
    )

    first = update(authority)
    replay = update(authority)

    assert first == replay
    assert first.apply_state is SettingsApplyState.APPLIED
    assert first.revision == first.effective_revision == 1
    assert len(calls) == 1
    assert RuntimeUserSettingsStore(path).load().location_label == "Workshop"
    snapshot = authority.snapshot(owners=CORE)
    assert snapshot["revision"] == snapshot["effective_revision"] == 1
    assert snapshot["values"]["location_label"] == "Workshop"
    assert "adaptive_theme" not in snapshot["values"]


def test_stale_revision_and_changed_idempotency_payload_fail_closed(tmp_path):
    _, authority = service(tmp_path, lambda *_: None)
    update(authority)

    with pytest.raises(RuntimeError, match="revision conflict"):
        update(authority, key="change:stale", expected=0,
               changes={"location_label": "Elsewhere"})
    with pytest.raises(RuntimeError, match="idempotency key payload conflict"):
        update(authority, key="change:1", expected=0,
               changes={"location_label": "Elsewhere"})


def test_field_scope_and_client_owned_settings_are_enforced(tmp_path):
    _, authority = service(tmp_path, lambda *_: None)

    with pytest.raises(PermissionError, match="scope"):
        update(authority, changes={"fleet_bootstrap": None})
    with pytest.raises(PermissionError, match="not writable"):
        update(authority, changes={"adaptive_theme": False})
    host = update(
        authority, key="host:1", changes={"fleet_bootstrap": None}, owners=HOST,
    )
    assert host.apply_state is SettingsApplyState.PLATFORM_RESTART_REQUIRED
    assert host.effective_revision == 0


def test_component_restart_is_not_misreported_as_live(tmp_path):
    calls = []
    _, authority = service(tmp_path, lambda *args: calls.append(args))

    receipt = update(
        authority, changes={"cognitive_primary_model": "approved/model:v2"},
    )

    assert receipt.apply_state is SettingsApplyState.PENDING_COMPONENT_RESTART
    assert receipt.revision == 1
    assert receipt.effective_revision == 0
    assert calls == []


def test_failed_live_apply_preserves_saved_and_effective_distinction(tmp_path):
    def fail(*_):
        raise OSError("runtime unavailable")

    path, authority = service(tmp_path, fail)
    receipt = update(authority)

    assert receipt.apply_state is SettingsApplyState.FAILED
    assert receipt.revision == 1
    assert receipt.effective_revision == 0
    assert receipt.error == "OSError"
    assert RuntimeUserSettingsStore(path).load().location_label == "Workshop"
    events = authority.events(after_revision=0, owners=CORE, limit=20)
    assert events == [{
        "revision": 1, "effective_revision": 0,
        "changed_fields": ["location_label"], "apply_state": "failed",
        "error": "OSError", "created_at": NOW.isoformat(),
    }]


def test_event_projection_respects_field_owner(tmp_path):
    _, authority = service(tmp_path, lambda *_: None)
    update(authority, changes={"location_label": "Workshop"})
    update(
        authority, key="host:1", expected=1,
        changes={"fleet_bootstrap": None}, owners=HOST,
    )

    assert [event["revision"] for event in authority.events(
        after_revision=0, owners=CORE, limit=20,
    )] == [1]
    assert [event["revision"] for event in authority.events(
        after_revision=0, owners=HOST, limit=20,
    )] == [2]


def test_legacy_local_save_invalidates_remote_cas_and_is_auditable(tmp_path):
    path, authority = service(tmp_path, lambda *_: None)
    old_snapshot = authority.snapshot(owners=CORE)
    current = RuntimeUserSettingsStore(path).load()
    from dataclasses import replace
    RuntimeUserSettingsStore(path).save(replace(current, location_label="Studio"))

    refreshed = authority.snapshot(owners=CORE)

    assert old_snapshot["revision"] == 0
    assert refreshed["revision"] == 1
    assert refreshed["effective_revision"] == 0
    assert refreshed["values"]["location_label"] == "Studio"
    with pytest.raises(RuntimeError, match="revision conflict"):
        update(authority, expected=0)
    event = authority.events(after_revision=0, owners=CORE, limit=10)[0]
    assert event["changed_fields"] == ["location_label"]
    assert event["apply_state"] == "unknown"
