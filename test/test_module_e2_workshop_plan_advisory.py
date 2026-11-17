"""MOD-WORKSHOP: supplied disposable-VM plans are reviewed, never provisioned."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.workshop.analysis import (
    CAPABILITY_ID,
    PROFILE,
    capability_registrations,
    review_experiment_plan,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
STEPS = ['prepare_image', 'verify_isolation', 'snapshot_clean',
         'run_offline_tests', 'collect_sanitized_results',
         'destroy_disposable_guest']


def plan(**extra):
    return dict(
        source_ref='workshop:plan-1',
        observed_at=NOW.isoformat(),
        experiment_id='experiment-1',
        host_class='disposable_workshop_guest',
        network_mode='isolated_none',
        disk_gib=32,
        memory_mib=2048,
        vcpus=2,
        steps=list(STEPS),
        destruction_reviewed=True,
    ) | extra


def entry():
    return next(row for row in capability_registrations()
                if row[0].name == CAPABILITY_ID)


def test_complete_plan_is_reviewed_but_not_provisioned():
    result = review_experiment_plan(plan(), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['freshness'] == 'fresh'
    assert result['procedurally_complete'] is True
    assert result['findings'] == []
    assert result['missing_steps'] == []
    assert result['resource_request'] == {'vcpus': 2, 'memory_mib': 2048,
                                          'disk_gib': 32}
    assert result['platform_acceptance_required'] is True
    assert result['host_accessed'] is False
    assert result['vm_created'] is False
    assert result['network_isolation_verified'] is False
    assert result['provisioning_authorized'] is False
    assert result['effect'] == 'none'
    assert PROFILE == 'ADVISORY'


def test_missing_steps_and_destruction_review_are_blocking_findings():
    result = review_experiment_plan(
        plan(steps=STEPS[:-1], destruction_reviewed=False), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['missing_steps'] == ['destroy_disposable_guest']
    assert 'missing_required_steps' in result['findings']
    assert 'no_destruction_review' in result['findings']
    assert result['procedurally_complete'] is False
    assert result['vm_created'] is False


def test_step_order_and_internal_isolation_are_flagged_for_platform_review():
    result = review_experiment_plan(
        plan(network_mode='isolated_internal', steps=list(reversed(STEPS))),
        now=NOW)
    assert 'experiment_steps_out_of_order' in result['findings']
    assert 'isolation_must_be_verified_by_platform' in result['findings']
    assert result['network_isolation_verified'] is False
    assert result['provisioning_authorized'] is False


@pytest.mark.parametrize('change', [
    {'host_class': 'canonical_host'},
    {'network_mode': 'bridged'},
    {'vcpus': True},
    {'vcpus': 0},
    {'disk_gib': 0},
    {'memory_mib': 255},
    {'steps': []},
    {'steps': ['run_offline_tests', 'run_offline_tests']},
    {'steps': ['start_core']},
    {'destruction_reviewed': 1},
    {'experiment_id': 'bad id'},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'provision_now': True},
])
def test_unsafe_or_out_of_range_plans_are_rejected(change):
    with pytest.raises(ValueError):
        review_experiment_plan(plan(**change), now=NOW)


@pytest.mark.parametrize('change', [
    {'disk_gib': 513},
    {'memory_mib': 16385},
    {'vcpus': 17},
    {'steps': ['prepare_image'] * 13},
])
def test_resource_and_step_bounds_are_enforced(change):
    with pytest.raises(ValueError):
        review_experiment_plan(plan(**change), now=NOW)


@pytest.mark.parametrize('stamp', [NOW - timedelta(days=2),
                                   NOW + timedelta(minutes=10)])
def test_stale_or_future_plan_masks_resources(stamp):
    result = review_experiment_plan(plan(observed_at=stamp.isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['resource_request'] is None
    assert result['findings'] == ['plan_timestamp_invalid']
    assert result['vm_created'] is False
    assert result['provisioning_authorized'] is False


@pytest.mark.parametrize('policy', [{'max_age_seconds': 0},
                                    {'max_age_seconds': 604801},
                                    {'max_age_seconds': True}])
def test_freshness_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        review_experiment_plan(plan(), now=NOW, **policy)


def test_duplicate_steps_are_rejected_and_input_is_not_mutated():
    original = plan()
    preserved = deepcopy(original)
    review_experiment_plan(original, now=NOW)
    assert original == preserved
    with pytest.raises(ValueError):
        review_experiment_plan(plan(steps=['prepare_image', 'prepare_image']),
                               now=NOW)


def test_registration_is_inert_and_identity_checked():
    capability, handler = entry()
    assert isinstance(capability, Capability)
    assert capability.name == CAPABILITY_ID
    live = plan(observed_at=datetime.now(timezone.utc).isoformat())
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'snapshot': live, 'create': True},
                                  None, 'scope creep'))
    outcome = handler(CapabilityRequest(capability, {'snapshot': live}, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
