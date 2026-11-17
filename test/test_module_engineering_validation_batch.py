"""Offline validation-only tests for electronics, 3D printing and trains.

No netlist analyzer, printer, JMRI connection or physical device is touched.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.electronics.analysis import (
    VALIDATOR_CAPABILITY_ID as ELECTRONICS_VALIDATOR_ID,
    capability_registrations as electronics_regs,
    validate_netlist_bom,
)
from sofia.modules.printing3d.analysis import (
    GCODE_CAPABILITY_ID as GCODE_VALIDATOR_ID,
    capability_registrations as printing_regs,
    validate_gcode_bounds,
)
from sofia.modules.trains.analysis import (
    TIMETABLE_CAPABILITY_ID as TIMETABLE_VALIDATOR_ID,
    capability_registrations as trains_regs,
    validate_timetable,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def netlist(**extra):
    return dict(
        source_ref='designer:netlist-1',
        observed_at=NOW.isoformat(),
        supply_voltage_v=12.0,
        components=[
            dict(ref='R1', part_class='resistor', quantity=1, rated_voltage_v=50),
            dict(ref='C1', part_class='capacitor', quantity=2, rated_voltage_v=25),
        ],
        connections=[dict(net_id='net1', members=['R1', 'C1'])],
    ) | extra


def gcode(**extra):
    return dict(
        source_ref='slicer:job-1',
        observed_at=NOW.isoformat(),
        lines=['G90', 'M104 S200', 'G1 X10 Y10 Z0.2 E1.0', 'G1 X20 Y10 E1.5'],
        estimated_duration_seconds=600,
        limits=dict(max_temperature_c=250, max_coordinate_mm=100,
                    max_extrusion_per_move_mm=2, max_duration_seconds=3600),
    ) | extra


def timetable(**extra):
    return dict(
        source_ref='rail:plan-1',
        observed_at=NOW.isoformat(),
        services=[dict(service_id='s1', route_blocks=['b1', 'b2'],
                       turnout_requirements=[dict(turnout_id='t1',
                                                   required_position='normal')],
                       scheduled_departure_s=0, scheduled_arrival_s=3600)],
        turnouts=[dict(turnout_id='t1', position='normal')],
        occupancies=[dict(block_id='b1', state='clear'),
                     dict(block_id='b2', state='clear')],
    ) | extra


def entry(registrations, capability_id):
    return next(item for item in registrations() if item[0].name == capability_id)


def test_netlist_consistent_without_electrical_exercise():
    result = validate_netlist_bom(netlist(), now=NOW)
    assert result['status'] == 'validated_consistent'
    assert result['findings'] == []
    assert result['missing_part_refs'] == []
    assert result['effect'] == 'none'
    assert result['netlist_electrically_exercised'] is False
    assert result['hardware_validation_verified'] is False


def test_netlist_missing_parts_and_voltage_overstress_are_advisory_findings():
    components = [
        dict(ref='R1', part_class='resistor', quantity=1, rated_voltage_v=5),
        dict(ref='C1', part_class='capacitor', quantity=1, rated_voltage_v=None),
    ]
    result = validate_netlist_bom(
        netlist(components=components,
                connections=[dict(net_id='net1', members=['R1', 'C1', 'R9'])]),
        now=NOW,
    )
    assert result['status'] == 'validated_with_findings'
    assert result['missing_part_refs'] == ['R9']
    assert result['voltage_overstress_refs'] == ['R1']
    assert result['voltage_unknown_refs'] == ['C1']
    assert set(result['findings']) == {
        'missing_bom_parts', 'supply_exceeds_component_rated_voltage',
        'component_voltage_rating_unknown',
    }
    assert result['effect'] == 'none'


@pytest.mark.parametrize('change', [
    {'supply_voltage_v': -1},
    {'supply_voltage_v': float('inf')},
    {'components': []},
    {'components': [dict(ref='R1', part_class='resistor', quantity=True,
                         rated_voltage_v=50)]},
    {'components': [dict(ref='R1', part_class='mystery', quantity=1,
                         rated_voltage_v=50)]},
    {'components': [
        dict(ref='R1', part_class='resistor', quantity=1, rated_voltage_v=50),
        dict(ref='R1', part_class='resistor', quantity=1, rated_voltage_v=50),
    ]},
    {'components': [dict(ref=f'R{n}', part_class='resistor', quantity=1,
                         rated_voltage_v=50) for n in range(129)]},
    {'connections': [dict(net_id='net1', members=['R1', 'R1'])]},
    {'connections': [dict(net_id='net1', members=['R1'])]},
    {'connections': [dict(net_id='net1', members=[f'R{n}' for n in range(17)])]},
    {'connections': [dict(net_id=f'net{n}', members=['R1', 'C1'])
                     for n in range(257)]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'extra_execute': True},
])
def test_netlist_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        validate_netlist_bom(netlist(**change), now=NOW)


def test_netlist_stale_or_future_is_unknown():
    for stamp in (NOW - timedelta(days=2), NOW + timedelta(minutes=10)):
        result = validate_netlist_bom(netlist(observed_at=stamp.isoformat()), now=NOW)
        assert result['status'] == 'unknown'
        assert result['component_count'] is None
        assert result['findings'] == ['netlist_timestamp_invalid']


def test_gcode_bounds_validated_without_execution():
    result = validate_gcode_bounds(gcode(), now=NOW)
    assert result['status'] == 'bounds_validated'
    assert result['findings'] == []
    assert result['highest_temperature_c'] == 200
    assert result['largest_extrusion_delta_mm'] == pytest.approx(1.0)
    assert result['largest_coordinate_mm'] == pytest.approx(20)
    assert result['executed'] is False
    assert result['sent_to_device'] is False
    assert result['physical_effect_authorized'] is False
    assert result['effect'] == 'none'


@pytest.mark.parametrize('change,finding', [
    ({'lines': ['G90', 'M104 S300', 'G1 X1 Y1 Z0.2 E0.1']},
     'temperature_exceeds_user_supplied_limit'),
    ({'lines': ['G90', 'G1 X200 Y1 Z0.2 E0.1']},
     'coordinate_outside_user_supplied_bounds'),
    ({'lines': ['G90', 'G1 X1 Y1 Z0.2 E5']},
     'extrusion_per_move_exceeds_user_supplied_limit'),
    ({'estimated_duration_seconds': 3601},
     'estimated_duration_exceeds_user_supplied_limit'),
])
def test_gcode_unsafe_bounds_are_reported(change, finding):
    result = validate_gcode_bounds(gcode(**change), now=NOW)
    assert result['status'] == 'bounds_violated'
    assert finding in result['findings']
    assert result['executed'] is False


def test_gcode_relative_positioning_is_explicitly_not_fully_bounded():
    result = validate_gcode_bounds(gcode(lines=['G91', 'G1 X5 E0.2']), now=NOW)
    assert result['status'] == 'bounds_validated'
    assert 'relative_positioning_not_fully_bounded' in result['findings']
    assert result['executed'] is False


@pytest.mark.parametrize('change', [
    {'lines': 'G1 X1'},
    {'lines': []},
    {'lines': ['G1'] * 2001},
    {'lines': [123]},
    {'lines': ['G1 X1\nY1']},
    {'lines': ['G1 ' + 'X1 ' * 100]},
    {'lines': ['G1 Xnan']},
    {'limits': dict(max_temperature_c=250)},
    {'limits': dict(max_temperature_c=250, max_coordinate_mm=100,
                    max_extrusion_per_move_mm=2, max_duration_seconds=3600,
                    extra_limit=True)},
    {'limits': dict(max_temperature_c=-1, max_coordinate_mm=100,
                    max_extrusion_per_move_mm=2, max_duration_seconds=3600)},
    {'limits': dict(max_temperature_c=250, max_coordinate_mm=0,
                    max_extrusion_per_move_mm=2, max_duration_seconds=3600)},
    {'limits': dict(max_temperature_c=250, max_coordinate_mm=100,
                    max_extrusion_per_move_mm=2, max_duration_seconds=0)},
    {'estimated_duration_seconds': -1},
    {'source_ref': 'bad\nref'},
    {'execute_now': True},
])
def test_gcode_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        validate_gcode_bounds(gcode(**change), now=NOW)


def test_gcode_stale_or_future_is_unknown():
    for stamp in (NOW - timedelta(days=2), NOW + timedelta(minutes=10)):
        result = validate_gcode_bounds(gcode(observed_at=stamp.isoformat()), now=NOW)
        assert result['status'] == 'unknown'
        assert result['inspected_line_count'] is None
        assert result['findings'] == ['gcode_timestamp_invalid']


def test_timetable_clear_is_hypothetical_only():
    result = validate_timetable(timetable(), now=NOW)
    assert result['status'] == 'validated'
    assert result['services'][0]['status'] == 'hypothetically_clear'
    assert result['findings'] == []
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['jmri_contacted'] is False
    assert result['live_route_clearance_verified'] is False
    assert result['services'][0]['live_clearance_verified'] is False


def test_timetable_occupied_route_and_misaligned_turnout_are_blocked():
    occupied = validate_timetable(
        timetable(occupancies=[dict(block_id='b1', state='occupied')]), now=NOW)
    assert occupied['services'][0]['status'] == 'hypothetically_blocked'
    assert 'route_occupied' in occupied['services'][0]['blocked_by']
    misaligned = validate_timetable(
        timetable(turnouts=[dict(turnout_id='t1', position='reverse')]), now=NOW)
    assert misaligned['services'][0]['status'] == 'hypothetically_blocked'
    assert 'turnout_misaligned' in misaligned['services'][0]['blocked_by']


def test_timetable_unknown_state_is_preserved_not_converted_to_clear():
    unknown_occupancy = validate_timetable(
        timetable(occupancies=[dict(block_id='b1', state='unknown')]), now=NOW)
    assert unknown_occupancy['services'][0]['status'] == 'unknown'
    assert 'route_occupancy_unknown' in unknown_occupancy['findings']
    unknown_turnout = validate_timetable(
        timetable(turnouts=[dict(turnout_id='t1', position='unknown')]), now=NOW)
    assert unknown_turnout['services'][0]['status'] == 'unknown'
    assert 'turnout_state_unknown' in unknown_turnout['findings']
    missing_turnout = validate_timetable(timetable(turnouts=[]), now=NOW)
    assert missing_turnout['missing_turnout_refs'] == ['t1']
    assert 'turnout_reference_missing' in missing_turnout['findings']
    assert missing_turnout['services'][0]['status'] == 'unknown'


def test_timetable_overlapping_services_are_conflicted():
    overlapping = timetable(services=[
        dict(service_id='s1', route_blocks=['b1'], turnout_requirements=[],
             scheduled_departure_s=0, scheduled_arrival_s=3600),
        dict(service_id='s2', route_blocks=['b1'], turnout_requirements=[],
             scheduled_departure_s=600, scheduled_arrival_s=4200),
    ])
    result = validate_timetable(overlapping, now=NOW)
    assert 'timetable_conflict' in result['findings']
    assert [row['status'] for row in result['services']] == [
        'hypothetically_conflicted', 'hypothetically_conflicted']
    assert result['action_authorized'] is False


@pytest.mark.parametrize('change', [
    {'services': []},
    {'services': [dict(service_id='s1', route_blocks=['b1'], turnout_requirements=[],
                       scheduled_departure_s=0, scheduled_arrival_s=1)] * 65},
    {'services': [
        dict(service_id='s1', route_blocks=['b1'], turnout_requirements=[],
             scheduled_departure_s=0, scheduled_arrival_s=1),
        dict(service_id='s1', route_blocks=['b2'], turnout_requirements=[],
             scheduled_departure_s=0, scheduled_arrival_s=1),
    ]},
    {'services': [dict(service_id='s1', route_blocks=['b1', 'b1'],
                       turnout_requirements=[], scheduled_departure_s=0,
                       scheduled_arrival_s=1)]},
    {'services': [dict(service_id='s1', route_blocks=[],
                       turnout_requirements=[], scheduled_departure_s=0,
                       scheduled_arrival_s=1)]},
    {'services': [dict(service_id='s1',
                       route_blocks=[f'b{n}' for n in range(33)],
                       turnout_requirements=[], scheduled_departure_s=0,
                       scheduled_arrival_s=1)]},
    {'services': [dict(service_id='s1', route_blocks=['b1'],
                       turnout_requirements=[dict(turnout_id='t1',
                                                  required_position='normal')] * 2,
                       scheduled_departure_s=0, scheduled_arrival_s=1)]},
    {'services': [dict(service_id='s1', route_blocks=['b1'],
                       turnout_requirements=[dict(turnout_id='t1',
                                                  required_position='sideways')],
                       scheduled_departure_s=0, scheduled_arrival_s=1)]},
    {'services': [dict(service_id='s1', route_blocks=['b1'],
                       turnout_requirements=[], scheduled_departure_s=10,
                       scheduled_arrival_s=10)]},
    {'turnouts': [dict(turnout_id='t1', position='normal'),
                  dict(turnout_id='t1', position='reverse')]},
    {'turnouts': [dict(turnout_id='t1', position='sideways')]},
    {'occupancies': [dict(block_id='b1', state='clear'),
                     dict(block_id='b1', state='occupied')]},
    {'occupancies': [dict(block_id='b1', state='maybe')]},
    {'source_ref': 'bad\nref'},
    {'extra_execute': True},
])
def test_timetable_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        validate_timetable(timetable(**change), now=NOW)


def test_timetable_stale_or_future_is_unknown():
    for stamp in (NOW - timedelta(days=2), NOW + timedelta(minutes=10)):
        result = validate_timetable(timetable(observed_at=stamp.isoformat()), now=NOW)
        assert result['status'] == 'unknown'
        assert result['service_count'] is None
        assert result['services'] == []
        assert result['findings'] == ['snapshot_timestamp_invalid']


@pytest.mark.parametrize('registrations,capability_id,parameters', [
    (electronics_regs, ELECTRONICS_VALIDATOR_ID, {'snapshot': netlist()}),
    (printing_regs, GCODE_VALIDATOR_ID, {'plan': gcode()}),
    (trains_regs, TIMETABLE_VALIDATOR_ID, {'snapshot': timetable()}),
])
def test_validator_registration_is_inert_and_identity_checked(
        registrations, capability_id, parameters):
    capability, handler = entry(registrations, capability_id)
    assert isinstance(capability, Capability)
    assert capability.name == capability_id
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, parameters, None, 'forged fixture'))
    live_parameters = dict(parameters)
    key = next(iter(live_parameters))
    live_parameters[key] = dict(live_parameters[key],
                                observed_at=datetime.now(timezone.utc).isoformat())
    outcome = handler(CapabilityRequest(capability, live_parameters, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
