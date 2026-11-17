"""MOD-ROBOTICS-GAIA: ideal leg simulation validates supplied servo limits only."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.robotics_gaia.kinematics import (
    CAPABILITY_ID,
    PROFILE,
    capability_registrations,
    simulate_leg_ik,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def limits():
    return {'yaw': [-180, 180], 'femur': [-180, 180], 'knee': [0, 180]}


def plan(**extra):
    return dict(
        source_ref='gaia:leg-plan-1',
        observed_at=NOW.isoformat(),
        coxa_mm=20,
        femur_mm=70,
        tibia_mm=90,
        target_xyz_mm=[100, 0, -40],
        joint_limits_deg=limits(),
    ) | extra


def entry():
    return next(row for row in capability_registrations()
                if row[0].name == CAPABILITY_ID)


def test_reachable_pose_is_simulated_without_physical_output():
    result = simulate_leg_ik(plan(), now=NOW)
    assert result['status'] == 'reachable_simulated'
    assert result['freshness'] == 'fresh'
    assert result['findings'] == []
    assert set(result['angles_deg']) == {'yaw', 'femur', 'knee'}
    assert result['servo_commands'] is None
    assert result['hardware_actuation_authorized'] is False
    assert result['collision_check'] == 'not_performed'
    assert result['effect'] == 'none'
    assert result['evidence_class'] == 'hypothetical_supplied'
    assert PROFILE == 'SIMULATE'


def test_supplied_joint_limit_violation_is_flagged_not_clamped():
    result = simulate_leg_ik(
        plan(joint_limits_deg={'yaw': [-180, 180], 'femur': [0, 90],
                               'knee': [0, 180]}), now=NOW)
    assert result['status'] == 'joint_limits_exceeded'
    assert 'femur_outside_user_supplied_limits' in result['findings']
    assert result['angles_deg'] is not None
    assert result['servo_commands'] is None
    assert result['hardware_actuation_authorized'] is False


def test_unreachable_target_is_not_clamped_to_requested_position():
    result = simulate_leg_ik(plan(target_xyz_mm=[600, 0, 0]), now=NOW)
    assert result['status'] == 'unreachable'
    assert result['angles_deg'] is None
    assert result['findings'] == ['target_outside_ideal_two_link_workspace']
    assert result['servo_commands'] is None


@pytest.mark.parametrize('change', [
    {'coxa_mm': 0},
    {'femur_mm': 0},
    {'tibia_mm': True},
    {'coxa_mm': float('nan')},
    {'tibia_mm': float('inf')},
    {'target_xyz_mm': [0, 0]},
    {'target_xyz_mm': [0, 0, float('nan')]},
    {'target_xyz_mm': [5001, 0, 0]},
    {'joint_limits_deg': {'yaw': [-180, 180], 'femur': [-180, 180]}},
    {'joint_limits_deg': {'yaw': [90, -90], 'femur': [-180, 180],
                          'knee': [0, 180]}},
    {'joint_limits_deg': {'yaw': [-361, 361], 'femur': [-180, 180],
                          'knee': [0, 180]}},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'ssc32_pulse': 1500},
])
def test_out_of_range_or_unsafe_plans_are_rejected(change):
    with pytest.raises(ValueError):
        simulate_leg_ik(plan(**change), now=NOW)


@pytest.mark.parametrize('stamp', [NOW - timedelta(days=2),
                                   NOW + timedelta(minutes=10)])
def test_stale_or_future_model_never_issues_a_solution(stamp):
    result = simulate_leg_ik(plan(observed_at=stamp.isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['angles_deg'] is None
    assert result['findings'] == ['model_timestamp_invalid']
    assert result['servo_commands'] is None
    assert result['hardware_actuation_authorized'] is False


@pytest.mark.parametrize('policy', [{'max_age_seconds': 0},
                                    {'max_age_seconds': 86401},
                                    {'max_age_seconds': True}])
def test_freshness_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        simulate_leg_ik(plan(), now=NOW, **policy)


def test_input_is_not_mutated_across_repeated_calls():
    original = plan()
    preserved = deepcopy(original)
    first = simulate_leg_ik(original, now=NOW)
    second = simulate_leg_ik(original, now=NOW)
    assert original == preserved
    assert first == second


def test_registration_is_inert_and_identity_checked():
    capability, handler = entry()
    assert isinstance(capability, Capability)
    assert capability.name == CAPABILITY_ID
    live = plan(observed_at=datetime.now(timezone.utc).isoformat())
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'plan': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'plan': live, 'drive': True},
                                  None, 'scope creep'))
    outcome = handler(CapabilityRequest(capability, {'plan': live}, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
