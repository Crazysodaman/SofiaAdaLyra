"""CA-6608 approved runtime model transaction, tests authored but deferred."""
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256

import pytest

from sofia.cognition.model_switch_plan import (
    ModelPromotionUncertain, PreparedModelRoleChange,
    promote_prepared_model_role,
)
from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore


NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def prepared(baseline=None):
    old = baseline or RuntimeUserSettings()
    replacement = replace(
        old, cognitive_primary_model="approved-upgraded-cognition:9b",
    )
    return PreparedModelRoleChange(
        role="primary", old_model=old.cognitive_primary_model,
        new_model=replacement.cognitive_primary_model,
        previous_settings_sha256=sha256(
            RuntimeUserSettingsStore._encode(old).encode("utf-8")
        ).hexdigest(),
        proposed_settings=replacement, operator_approval_ref="owner-ref-12345678",
        rollback_model=old.cognitive_primary_model,
        independently_reviewed=True, can_apply_now=False,
    )


def _broker(plan, store, *, apply, health=lambda *_: True):
    return promote_prepared_model_role(
        plan=plan,settings_store=store,
        verify_operator_fence_and_install=lambda value: True,
        drain_active_role=lambda role: True,
        apply_runtime_settings=apply,
        health_and_continuity_ok=health,at=NOW,
    )


def test_accepted_model_role_change_is_atomic_source_with_durable_receipt(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    plan = prepared()
    changes = []
    result = _broker(
        plan,store,
        apply=lambda config: changes.append(config.cognitive_primary_model) or True,
    )
    assert result.status == "accepted"
    assert store.load().cognitive_primary_model == plan.new_model
    assert changes == [plan.new_model]
    again = _broker(plan, store, apply=lambda _: (
        pytest.fail("accepted receipt must not reload model again")
    ))
    assert again == result


def test_candidate_health_rejection_restores_previous_model_and_settings(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    plan = prepared()
    before = store.load()
    changes = []
    result = _broker(
        plan,store,
        apply=lambda config: changes.append(config.cognitive_primary_model) or True,
        health=lambda *_: False,
    )
    assert result.status == "rolled_back"
    assert changes == [plan.new_model,plan.old_model]
    assert store.load() == before
    with pytest.raises(ModelPromotionUncertain):
        _broker(plan,store,apply=lambda _: pytest.fail("must not replay"))


def test_revoked_owner_approval_never_writes_any_new_model(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    plan = prepared()
    with pytest.raises(PermissionError, match="owner approval"):
        promote_prepared_model_role(
            plan=plan,settings_store=store,
            verify_operator_fence_and_install=lambda value: False,
            drain_active_role=lambda role: pytest.fail("must not drain"),
            apply_runtime_settings=lambda value: pytest.fail("must not apply"),
            health_and_continuity_ok=lambda *_: False,at=NOW,
        )
    assert store.load().cognitive_primary_model == plan.old_model


def test_old_plan_cannot_override_changed_canonical_settings(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    plan = prepared()
    store.save(replace(
        RuntimeUserSettings(),
        cognitive_primary_model="another-operator-model:5b",
    ))
    with pytest.raises(RuntimeError, match="changed"):
        _broker(plan,store,apply=lambda _: pytest.fail("must not apply"))


def test_crash_during_provider_transition_refuses_automatic_replay(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    plan = prepared()
    def crash(_settings):
        raise KeyboardInterrupt("simulated host process death")

    with pytest.raises(KeyboardInterrupt):
        _broker(plan,store,apply=crash)
    assert store.load().cognitive_primary_model == plan.new_model
    with pytest.raises(ModelPromotionUncertain, match="no replayable"):
        _broker(plan,store,apply=lambda _: pytest.fail("must not replay"))
