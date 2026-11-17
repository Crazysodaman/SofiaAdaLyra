"""MOD-DIGITAL-TWIN: supplied scenario graphs are compared as SIMULATE only."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.digital_twin.analysis import (
    CAPABILITY_ID,
    PROFILE,
    capability_registrations,
    compare_scenarios,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def scenario(sid='dns', initial='node_a', affected=None, **extra):
    return dict(
        scenario_id=sid,
        initial_host_id=initial,
        affected_host_ids=affected if affected is not None
        else ['node_a', 'node_b', 'node_c'],
        fidelity='dependency_graph_v1',
        outcome='modeled_only',
    ) | extra


def snapshot(**extra):
    return dict(
        source_ref='platform:projection-1',
        observed_at=NOW.isoformat(),
        critical_host_ids=['node_a', 'node_b'],
        scenarios=[scenario(),
                   scenario('storage', 'node_c', ['node_c'])],
    ) | extra


def entry():
    return next(row for row in capability_registrations()
                if row[0].name == CAPABILITY_ID)


def test_scenarios_are_ranked_without_claiming_a_real_outage():
    result = compare_scenarios(snapshot(), now=NOW)
    assert result['status'] == 'compared_simulated'
    assert result['freshness'] == 'fresh'
    assert [row['scenario_id'] for row in result['ranking']] == [
        'dns', 'storage']
    assert result['ranking'][0]['critical_count'] == 2
    assert result['ranking'][0]['critical_hosts_affected'] == [
        'node_a', 'node_b']
    assert result['ranking'][1]['critical_count'] == 0
    assert result['real_outage_verified'] is False
    assert result['platform_receipt_verified'] is False
    assert result['effect'] == 'none'
    assert result['evidence_class'] == 'hypothetical_supplied_unverified'
    assert PROFILE == 'SIMULATE'


def test_ranking_ties_break_deterministically_by_scenario_id():
    result = compare_scenarios(snapshot(
        critical_host_ids=[],
        scenarios=[scenario('z', 'z', ['z']), scenario('a', 'a', ['a'])]),
        now=NOW)
    assert [row['scenario_id'] for row in result['ranking']] == ['a', 'z']


@pytest.mark.parametrize('change', [
    {'scenarios': []},
    {'scenarios': [scenario(initial='node_a', affected=['node_b'])]},
    {'scenarios': [scenario(fidelity='full_vm_replica')]},
    {'scenarios': [scenario(outcome='real_outage')]},
    {'scenarios': [scenario(), scenario()]},
    {'scenarios': [scenario(affected=['node_a', 'node_a'])]},
    {'scenarios': [scenario(unknown='x')]},
    {'critical_host_ids': ['node_a', 'node_a']},
    {'critical_host_ids': ['bad host']},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'apply_changes': True},
])
def test_unsafe_or_malformed_scenarios_are_rejected(change):
    with pytest.raises(ValueError):
        compare_scenarios(snapshot(**change), now=NOW)


@pytest.mark.parametrize('change', [
    {'scenarios': [scenario(f's{n}', f'h{n}', [f'h{n}'])
                   for n in range(25)]},
    {'critical_host_ids': [f'host{n}' for n in range(65)]},
    {'scenarios': [scenario(affected=[f'host{n}' for n in range(65)])]},
])
def test_collection_bounds_are_enforced(change):
    with pytest.raises(ValueError):
        compare_scenarios(snapshot(**change), now=NOW)


@pytest.mark.parametrize('stamp', [NOW - timedelta(hours=2),
                                   NOW + timedelta(minutes=10)])
def test_stale_or_future_projection_masks_ranking(stamp):
    result = compare_scenarios(snapshot(observed_at=stamp.isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['ranking'] == []
    assert result['findings'] == ['scenario_snapshot_timestamp_invalid']
    assert result['real_outage_verified'] is False
    assert result['effect'] == 'none'


@pytest.mark.parametrize('policy', [{'max_age_seconds': 0},
                                    {'max_age_seconds': 86401},
                                    {'max_age_seconds': True}])
def test_freshness_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        compare_scenarios(snapshot(), now=NOW, **policy)


def test_duplicate_scenario_identity_is_rejected_and_input_is_not_mutated():
    original = snapshot()
    preserved = deepcopy(original)
    compare_scenarios(original, now=NOW)
    assert original == preserved
    with pytest.raises(ValueError):
        compare_scenarios(snapshot(scenarios=[scenario('same'),
                                              scenario('same')]), now=NOW)


def test_registration_is_inert_and_identity_checked():
    capability, handler = entry()
    assert isinstance(capability, Capability)
    assert capability.name == CAPABILITY_ID
    live = snapshot(observed_at=datetime.now(timezone.utc).isoformat())
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'snapshot': live, 'apply': True},
                                  None, 'scope creep'))
    outcome = handler(CapabilityRequest(capability, {'snapshot': live}, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
