"""MOD-ENERGY: supplied UPS telemetry review has no switching authority."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.energy.analysis import (
    CAPABILITY_ID,
    PROFILE,
    assess_ups,
    capability_registrations,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def observation(**extra):
    return dict(
        source_ref='ups:telemetry-1',
        ups_ref='rack:ups-a',
        observed_at=NOW.isoformat(),
        mains_present=True,
        battery_percent=90.0,
        load_percent=25.0,
        runtime_seconds=3600,
        self_test_state='passed',
    ) | extra


def entry():
    return next(item for item in capability_registrations()
                if item[0].name == CAPABILITY_ID)


def test_healthy_ups_review_is_unknown_free_and_inert():
    result = assess_ups(observation(), now=NOW)
    assert result['freshness'] == 'fresh'
    assert result['classification'] == 'no_issue_observed'
    assert result['findings'] == []
    assert result['runtime_estimate_seconds'] == 3600
    assert result['evidence_class'] == 'supplied_unverified'
    assert result['effect'] == 'none'
    assert result['estimate_is_not_a_shutdown_permission'] is True
    assert PROFILE == 'OBSERVE'


def test_mains_absent_is_reported_without_transfer_or_shutdown():
    result = assess_ups(observation(mains_present=False), now=NOW)
    assert result['classification'] == 'attention'
    assert 'utility_power_absent_reported' in result['findings']
    assert result['effect'] == 'none'
    assert result['estimate_is_not_a_shutdown_permission'] is True


def test_unknown_telemetry_is_not_treated_as_healthy():
    result = assess_ups(observation(
        mains_present=None, battery_percent=None, load_percent=None,
        runtime_seconds=None, self_test_state='unknown'), now=NOW)
    assert result['classification'] == 'unknown'
    assert result['runtime_estimate_seconds'] is None
    assert set(result['findings']) == {
        'utility_state_unknown',
        'battery_state_unknown',
        'load_unknown',
        'runtime_estimate_unknown',
        'self_test_unverified',
    }
    assert result['effect'] == 'none'


@pytest.mark.parametrize('change', [
    {'battery_percent': -0.1},
    {'battery_percent': 100.1},
    {'battery_percent': float('nan')},
    {'load_percent': -1},
    {'load_percent': 101},
    {'runtime_seconds': -1},
    {'runtime_seconds': 604801},
    {'battery_percent': True},
    {'mains_present': 1},
    {'self_test_state': 'maybe'},
    {'source_ref': 'bad\nref'},
    {'ups_ref': ''},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'extra_switch_command': 'transfer'},
])
def test_out_of_range_or_unsafe_telemetry_is_rejected(change):
    with pytest.raises(ValueError):
        assess_ups(observation(**change), now=NOW)


@pytest.mark.parametrize('stamp', [NOW - timedelta(minutes=3),
                                   NOW + timedelta(minutes=1)])
def test_stale_or_future_telemetry_never_reuses_an_estimate(stamp):
    result = assess_ups(observation(observed_at=stamp.isoformat()), now=NOW,
                        max_age_seconds=120)
    assert result['freshness'] in {'stale', 'future'}
    assert result['classification'] == 'unknown'
    assert result['findings'] == ['stale_or_future_evidence']
    assert result['runtime_estimate_seconds'] is None
    assert result['effect'] == 'none'


@pytest.mark.parametrize('policy', [
    {'max_age_seconds': 0},
    {'max_age_seconds': 86401},
    {'max_age_seconds': True},
    {'reserve_seconds': 0},
    {'reserve_seconds': 86401},
])
def test_policy_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        assess_ups(observation(), now=NOW, **policy)


def test_input_is_not_mutated_across_repeated_calls():
    original = observation()
    snapshot = deepcopy(original)
    first = assess_ups(original, now=NOW)
    second = assess_ups(original, now=NOW)
    assert original == snapshot
    assert first == second


def test_registration_uses_existing_capability_and_rejects_scope_creep():
    capability, handler = entry()
    assert isinstance(capability, Capability)
    assert capability.name == CAPABILITY_ID
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    live = observation(observed_at=datetime.now(timezone.utc).isoformat())
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'observation': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability,
                                  {'observation': live, 'switch': True},
                                  None, 'scope creep'))
    outcome = handler(CapabilityRequest(capability, {'observation': live}, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
