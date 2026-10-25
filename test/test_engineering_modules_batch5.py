"""Offline tests of four simulation-only module handlers. No devices used."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import math
import pytest
from sofia.modules.engineering import simulate_dc_circuit
from sofia.modules.engineering.analysis import capability_registrations as eng_regs
from sofia.modules.electronics import analyze_adc_divider
from sofia.modules.electronics.analysis import capability_registrations as elec_regs
from sofia.modules.printing3d import estimate_material
from sofia.modules.printing3d.analysis import capability_registrations as print_regs
from sofia.modules.robotics_gaia import simulate_leg_ik
from sofia.modules.robotics_gaia.kinematics import capability_registrations as gaia_regs
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)


def circuit(**extra):
    return dict(source_ref='designer:1', observed_at=NOW.isoformat(), topology='series',
                source_voltage_v=12.0, resistances_ohm=[2.0, 4.0],
                design_current_limit_a=3.0) | extra


def divider(**extra):
    return dict(source_ref='designer:1', observed_at=NOW.isoformat(), input_voltage_v=12,
                r_top_ohm=10_000, r_bottom_ohm=10_000, adc_reference_v=3.3,
                adc_bits=12, adc_input_limit_v=3.6) | extra


def printing(**extra):
    return dict(source_ref='slicer:1', observed_at=NOW.isoformat(), filament_length_mm=1000,
                filament_diameter_mm=1.75, density_g_cm3=1.24,
                slicer_duration_seconds=600, hotend_flow_limit_mm3_s=5.0,
                layer_height_mm=0.2, nozzle_diameter_mm=0.4) | extra


def leg(**extra):
    return dict(source_ref='virtual:gaia', observed_at=NOW.isoformat(),
                coxa_mm=20, femur_mm=70, tibia_mm=90,
                target_xyz_mm=[100, 0, -40],
                joint_limits_deg={'yaw':[-180,180], 'femur':[-180,180], 'knee':[0,180]}) | extra


def test_series_ideal_kirchhoff_balance():
    result = simulate_dc_circuit(circuit(), now=NOW)
    assert result['status'] == 'simulated'
    assert result['equivalent_resistance_ohm'] == pytest.approx(6)
    assert result['total_current_a'] == pytest.approx(2)
    assert result['total_power_w'] == pytest.approx(24)
    assert sum(x['voltage_v'] for x in result['components']) == pytest.approx(12)
    assert sum(x['power_w'] for x in result['components']) == pytest.approx(24)
    assert result['design_code_compliance'] == 'not_assessed'


def test_parallel_ideal_kirchhoff_balance():
    result = simulate_dc_circuit(circuit(topology='parallel'), now=NOW)
    assert result['equivalent_resistance_ohm'] == pytest.approx(4/3)
    assert result['total_current_a'] == pytest.approx(9)
    assert sum(x['current_a'] for x in result['components']) == pytest.approx(9)
    assert 'user_supplied_current_limit_exceeded' in result['findings']


def test_zero_voltage_not_failure():
    assert simulate_dc_circuit(circuit(source_voltage_v=0), now=NOW)['total_current_a'] == 0


@pytest.mark.parametrize('bad',[
    {'resistances_ohm':[]}, {'resistances_ohm':[0]}, {'resistances_ohm':[float('nan')]},
    {'resistances_ohm':[True]}, {'resistances_ohm':[2]*33}, {'source_voltage_v':-1},
    {'source_voltage_v':float('inf')}, {'topology':'bridge'}, {'source_ref':'secret\n'},
    {'design_current_limit_a':True}, {'observed_at':'yesterday'}, {'observed_at':NOW.replace(tzinfo=None).isoformat()},
    {'extra_execute':'ON'},
])
def test_circuit_invalid_rejected(bad):
    with pytest.raises(ValueError):
        simulate_dc_circuit(circuit(**bad), now=NOW)


def test_stale_circuit_not_calculated():
    result=simulate_dc_circuit(circuit(observed_at=(NOW-timedelta(days=2)).isoformat()),now=NOW)
    assert result['status']=='unknown' and result['total_current_a'] is None


def test_divider_voltage_overrange_and_clipping():
    result=analyze_adc_divider(divider(),now=NOW)
    assert result['divider_voltage_v']==pytest.approx(6)
    assert result['adc_code_ideal']==4095
    assert 'adc_reference_overrange_ideal_clipping' in result['findings']
    assert 'input_exceeds_user_supplied_adc_limit' in result['findings']
    assert not result['hardware_tolerance_verified']


def test_divider_ideal_midscale():
    r=analyze_adc_divider(divider(input_voltage_v=3.3,adc_input_limit_v=3.3),now=NOW)
    assert r['divider_voltage_v']==pytest.approx(1.65)
    assert r['adc_code_ideal'] in (2047,2048)
    assert r['thevenin_ohm']==pytest.approx(5000)
    assert r['findings']==[]


@pytest.mark.parametrize('bad',[
    {'r_top_ohm':0}, {'r_bottom_ohm':True}, {'adc_bits':0}, {'adc_bits':25},
    {'adc_bits':True}, {'adc_reference_v':0}, {'input_voltage_v':-1},
    {'adc_input_limit_v':float('nan')}, {'source_ref':'bad\n'}, {'unexpected':'PIN_ON'},
])
def test_divider_invalid_rejected(bad):
    with pytest.raises(ValueError):analyze_adc_divider(divider(**bad),now=NOW)


def test_divider_future_timestamp_unknown():
    r=analyze_adc_divider(divider(observed_at=(NOW+timedelta(minutes=10)).isoformat()),now=NOW)
    assert r['status']=='unknown' and r['adc_code_ideal'] is None


def test_material_calculation_physical_units():
    r=estimate_material(printing(),now=NOW)
    expected_mm3=math.pi*(1.75/2)**2*1000
    assert r['filament_volume_cm3']==pytest.approx(expected_mm3/1000)
    assert r['filament_mass_g']==pytest.approx(expected_mm3*1.24/1000)
    assert r['average_flow_mm3_s']==pytest.approx(expected_mm3/600)
    assert r['findings']==[]


def test_material_constraints_not_guaranteed_peak_flow():
    r=estimate_material(printing(hotend_flow_limit_mm3_s=1.0,layer_height_mm=0.5),now=NOW)
    assert set(r['findings'])=={'average_flow_above_user_supplied_hotend_limit',
                               'layer_height_above_80_percent_nozzle_diameter'}
    assert r['effect']=='none'


def test_zero_filament_valid_no_material():
    assert estimate_material(printing(filament_length_mm=0),now=NOW)['filament_mass_g']==0


@pytest.mark.parametrize('bad',[
    {'filament_length_mm':True}, {'filament_length_mm':-1}, {'filament_diameter_mm':0},
    {'density_g_cm3':float('inf')}, {'slicer_duration_seconds':0},
    {'hotend_flow_limit_mm3_s':True}, {'layer_height_mm':float('nan')},
    {'nozzle_diameter_mm':-1}, {'source_ref':'unsafe/\n'}, {'firmware_command':'G28'},
])
def test_print_invalid_rejected(bad):
    with pytest.raises(ValueError):estimate_material(printing(**bad),now=NOW)


def test_print_stale_masks_material_estimate():
    r=estimate_material(printing(observed_at=(NOW-timedelta(days=2)).isoformat()),now=NOW)
    assert r['status']=='unknown' and r['filament_mass_g'] is None


def test_leg_reach_and_forward_kinematics():
    r=simulate_leg_ik(leg(),now=NOW)
    assert r['status']=='reachable_simulated'
    a=r['angles_deg']
    femur=math.radians(a['femur']); knee=math.radians(a['knee']);yaw=math.radians(a['yaw'])
    distance=20+70*math.cos(femur)+90*math.cos(femur+knee)
    z=70*math.sin(femur)+90*math.sin(femur+knee)
    assert distance*math.cos(yaw)==pytest.approx(100,abs=1e-8)
    assert distance*math.sin(yaw)==pytest.approx(0,abs=1e-8)
    assert z==pytest.approx(-40,abs=1e-8)
    assert r['servo_commands'] is None
    assert not r['hardware_actuation_authorized']


def test_leg_unreachable_is_not_clamped_to_target():
    r=simulate_leg_ik(leg(target_xyz_mm=[600,0,0]),now=NOW)
    assert r['status']=='unreachable' and r['angles_deg'] is None


def test_leg_limit_violation_retains_inert_simulated_solution():
    r=simulate_leg_ik(leg(joint_limits_deg={'yaw':[-180,180], 'femur':[0,90], 'knee':[0,180]}),now=NOW)
    assert r['status']=='joint_limits_exceeded'
    assert 'femur_outside_user_supplied_limits' in r['findings']


@pytest.mark.parametrize('bad',[
    {'femur_mm':0}, {'tibia_mm':True}, {'coxa_mm':float('inf')},
    {'target_xyz_mm':[0,0]}, {'target_xyz_mm':[0,0,float('nan')]},
    {'joint_limits_deg':{'yaw':[-90,90],'knee':[0,180]}},
    {'joint_limits_deg':{'yaw':[90,-90],'femur':[-180,180],'knee':[0,180]}},
    {'source_ref':'no\n'}, {'ssc32_pulse':1500},
])
def test_leg_invalid_rejected(bad):
    with pytest.raises(ValueError):simulate_leg_ik(leg(**bad),now=NOW)


def test_leg_stale_does_not_issue_solution():
    r=simulate_leg_ik(leg(observed_at=(NOW-timedelta(days=2)).isoformat()),now=NOW)
    assert r['status']=='unknown' and r['angles_deg'] is None


@pytest.mark.parametrize('registrations,param_key,input_builder',[
    (eng_regs,'plan',circuit), (elec_regs,'plan',divider),
    (print_regs,'plan',printing), (gaia_regs,'plan',leg),
])
def test_capability_registration_inert_and_identity_checked(registrations,param_key,input_builder):
    ((cap,handler),)=registrations()
    assert isinstance(cap,Capability) and callable(handler)
    with pytest.raises(ValueError):
        handler(CapabilityRequest(Capability(cap.name,'forged'),{param_key:input_builder()},None,'test'))
    live=input_builder(observed_at=datetime.now(timezone.utc).isoformat())
    outcome=handler(CapabilityRequest(cap,{param_key:live},None,'authorized fixture'))
    assert outcome['sdk_protocol']=='1.0'
    assert outcome['effect']=='none'
