"""Owner-controlled NEURO algorithm switch: production integration contracts.

Tests are source-authored only; do not run until the verification campaign.
"""
from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from sofia.application.bootstrap import SofiaApplication
from sofia.config.user_settings import (
    CURRENT_RUNTIME_SETTINGS_SCHEMA_VERSION,
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.neuro import NeuroRuntime, NeuralSignal


pytestmark = pytest.mark.pkg_core
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _signal(name, value):
    return NeuralSignal(
        source=name, kind="diagnostic", value=value, confidence=0.8,
        novelty=0.8, urgency=0.8, observed_at=NOW,
    )


def test_owner_neuro_toggle_persists_and_legacy_settings_migrate(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    baseline = store.load()
    assert baseline.neuro_competition_enabled is True
    store.save(replace(baseline, neuro_competition_enabled=False))
    assert RuntimeUserSettingsStore(tmp_path / "sofia.db").load().neuro_competition_enabled is False

    legacy = json.loads(RuntimeUserSettingsStore._encode(baseline))
    legacy["schema_version"] = CURRENT_RUNTIME_SETTINGS_SCHEMA_VERSION - 1
    legacy.pop("neuro_competition_enabled")
    assert RuntimeUserSettingsStore._decode(
        json.dumps(legacy)
    ).neuro_competition_enabled is True


def test_foreground_settings_refresh_applies_switch_without_weather_change(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    store.save(RuntimeUserSettings(neuro_competition_enabled=True))
    app = object.__new__(SofiaApplication)
    app._environment_settings_store = store
    app._environment_settings_fingerprint = app._environment_fingerprint(store.load())
    app._neuro = NeuroRuntime()
    store.save(replace(store.load(), neuro_competition_enabled=False))
    assert app._reload_environment_if_settings_changed() is False
    app._neuro.observe_signal(_signal("alpha", .90))
    snapshot = app._neuro.observe_signal(_signal("beta", .88))
    assert snapshot.selection_method == "salience-v1"
    assert "deterministic" in snapshot.selection_reason


def test_invalid_owner_switch_type_is_rejected():
    with pytest.raises(TypeError, match="neuro_competition_enabled"):
        RuntimeUserSettings(neuro_competition_enabled="yes")


def test_disabled_neuro_switch_can_be_reenabled_without_creating_new_runtime():
    runtime = NeuroRuntime(competition_enabled=False)
    runtime.observe_signal(_signal("alpha", .9))
    runtime.observe_signal(_signal("beta", .88))
    assert runtime.last_snapshot.selection_method == "salience-v1"
    runtime.set_competition_enabled(True)
    assert runtime.snapshot(now=NOW).selection_method != "salience-v1"


def test_owner_reset_epoch_hot_applies_without_erasing_trusted_attention(tmp_path):
    store = RuntimeUserSettingsStore(tmp_path / "sofia.db")
    store.save(RuntimeUserSettings())
    app = object.__new__(SofiaApplication)
    app._environment_settings_store = store
    app._environment_settings_fingerprint = app._environment_fingerprint(store.load())
    app._neuro_reset_generation = 0
    app._neuro = NeuroRuntime()
    app._neuro.observe_signal(_signal("alpha", .90))
    original = app._neuro._competition
    store.save(replace(store.load(), neuro_competition_reset_generation=1))
    assert app._reload_environment_if_settings_changed() is False
    assert app._neuro._competition is not original
    assert app._neuro.last_snapshot is not None
    assert app._neuro.snapshot(now=NOW).focus.key == "diagnostic:alpha"
    assert app._neuro_reset_generation == 1
    after = app._neuro._competition
    assert app._reload_environment_if_settings_changed() is False
    assert app._neuro._competition is after


def test_canonical_reset_epoch_migration_and_bounds():
    source = RuntimeUserSettings()
    document = json.loads(RuntimeUserSettingsStore._encode(source))
    document["schema_version"] = 9
    del document["neuro_competition_reset_generation"]
    restored = RuntimeUserSettingsStore._decode(json.dumps(document))
    assert restored.neuro_competition_reset_generation == 0
    with pytest.raises(ValueError, match="neuro_competition_reset_generation"):
        RuntimeUserSettings(neuro_competition_reset_generation=-1)
    with pytest.raises(ValueError, match="neuro_competition_reset_generation"):
        RuntimeUserSettings(neuro_competition_reset_generation=1_000_001)


def test_bounded_salience_features_are_explicit_and_versioned():
    from sofia.neuro.salience import SalienceNetwork
    assert SalienceNetwork.FEATURE_VERSION == "salience-feature-dictionary-v1"
    assert SalienceNetwork.FEATURE_WEIGHTS == (
        ("urgency", 0.30), ("novelty", 0.25),
        ("confidence", 0.25), ("value", 0.20),
    )
