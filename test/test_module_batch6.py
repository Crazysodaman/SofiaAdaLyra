"""Offline tests for four module-owned, authority-free capabilities."""
from datetime import datetime, timedelta, timezone
import math
import pytest
from sofia.platform.capability.model import CapabilityRequest
from sofia.modules.cad import simulate_plate
from sofia.modules.cad.analysis import capability_registrations as cad_regs
from sofia.modules.digital_twin import compare_scenarios
from sofia.modules.digital_twin.analysis import capability_registrations as twin_regs
from sofia.modules.file_watch import summarize_changes
from sofia.modules.file_watch.analysis import capability_registrations as watch_regs
from sofia.modules.smart_home import review_entities
from sofia.modules.smart_home.analysis import capability_registrations as home_regs
NOW=datetime(2026,10,25,18,0,tzinfo=timezone.utc)

def plate(**kw):
    return dict(source_ref='model:plate',observed_at=NOW.isoformat(),width_mm=100,
                height_mm=80,thickness_mm=3,density_g_cm3=2.7,edge_margin_mm=3,
                holes=[dict(x_mm=20,y_mm=20,diameter_mm=10)])|kw

def scenarios(**kw):
    return dict(source_ref='platform:projection',observed_at=NOW.isoformat(),
                critical_host_ids=['node_a','node_b'],scenarios=[
                    dict(scenario_id='dns',initial_host_id='node_a',affected_host_ids=['node_a','node_b','node_c'],
                         fidelity='dependency_graph_v1',outcome='modeled_only'),
                    dict(scenario_id='storage',initial_host_id='node_c',affected_host_ids=['node_c'],
                         fidelity='dependency_graph_v1',outcome='modeled_only')])|kw

def changes(**kw):
    return dict(source_ref='feed:1',root_ref='owner:approved_root',observed_at=NOW.isoformat(),
                events=[dict(path='project/README.md',kind='modified',is_directory=False),
                        dict(path='project/.env',kind='created',is_directory=False)])|kw

def home(**kw):
    return dict(source_ref='ha:1',observed_at=NOW.isoformat(),entities=[
        dict(entity_id='light.office',state='on',last_changed=NOW.isoformat(),expected_state='on'),
        dict(entity_id='lock.front_door',state='unlocked',last_changed=NOW.isoformat(),expected_state='locked')])|kw

def test_cad_area_volume_mass():
    r=simulate_plate(plate(),now=NOW)
    area=100*80-math.pi*5**2
    assert r['net_area_mm2']==pytest.approx(area)
    assert r['volume_cm3']==pytest.approx(area*3/1000)
    assert r['mass_g']==pytest.approx(area*3/1000*2.7)
    assert r['effect']=='none' and not r['manufacturing_approved']

def test_cad_empty_holes():
    assert simulate_plate(plate(holes=[]),now=NOW)['net_area_mm2']==8000

def test_cad_bad_edge():
    r=simulate_plate(plate(holes=[dict(x_mm=5,y_mm=5,diameter_mm=10)]),now=NOW)
    assert r['status']=='invalid_geometry' and r['mass_g'] is None

def test_cad_overlap():
    r=simulate_plate(plate(holes=[dict(x_mm=20,y_mm=20,diameter_mm=10),dict(x_mm=30,y_mm=20,diameter_mm=10)]),now=NOW)
    assert 'hole_0_1_clearance_below_margin' in r['findings']

def test_cad_tangent_with_no_margin():
    r=simulate_plate(plate(edge_margin_mm=0,holes=[dict(x_mm=20,y_mm=20,diameter_mm=10),dict(x_mm=30,y_mm=20,diameter_mm=10)]),now=NOW)
    assert r['status']=='simulated'

@pytest.mark.parametrize('bad',[
    {'width_mm':True}, {'height_mm':float('nan')},{'thickness_mm':0},{'density_g_cm3':float('inf')},
    {'edge_margin_mm':-1},{'holes':'none'},{'holes':[{}]},{'holes':[dict(x_mm=2,y_mm=2,diameter_mm=-2)]},
    {'holes':[dict(x_mm=30,y_mm=20,diameter_mm=10)]*33},{'source_ref':'bad\n'},
    {'extra_execute':'yes'},{'observed_at':'naive'},
])
def test_cad_rejects_malformed(bad):
    with pytest.raises(ValueError): simulate_plate(plate(**bad),now=NOW)

def test_cad_stale_or_future_mask_outputs():
    for date in (NOW-timedelta(days=2),NOW+timedelta(hours=2)):
        r=simulate_plate(plate(observed_at=date.isoformat()),now=NOW)
        assert r['status']=='unknown' and r['mass_g'] is None

def test_twin_ranking_and_no_outage_claim():
    r=compare_scenarios(scenarios(),now=NOW)
    assert [x['scenario_id'] for x in r['ranking']]==['dns','storage']
    assert r['ranking'][0]['critical_count']==2
    assert r['real_outage_verified'] is False and r['effect']=='none'

def test_twin_tie_break_deterministic():
    s=scenarios(critical_host_ids=[],scenarios=[dict(scenario_id=n,initial_host_id=n,affected_host_ids=[n],
                                               fidelity='dependency_graph_v1',outcome='modeled_only') for n in ('z','a')])
    r=compare_scenarios(s,now=NOW)
    assert [x['scenario_id'] for x in r['ranking']]==['a','z']

@pytest.mark.parametrize('bad',[
    {'scenarios':[]},{'scenarios':'bad'},{'critical_host_ids':['dup','dup']},
    {'scenarios':[dict(scenario_id='a',initial_host_id='x',affected_host_ids=[],
                       fidelity='dependency_graph_v1',outcome='modeled_only')]},
    {'scenarios':[dict(scenario_id='a',initial_host_id='x',affected_host_ids=['x'],
                       fidelity='full_vm_replica',outcome='modeled_only')]},
    {'scenarios':[dict(scenario_id='a',initial_host_id='x',affected_host_ids=['x'],
                       fidelity='dependency_graph_v1',outcome='real_outage')]},
    {'source_ref':'bad\n'}, {'unexpected':'permission'},
])
def test_twin_rejects_malformed(bad):
    with pytest.raises(ValueError): compare_scenarios(scenarios(**bad),now=NOW)

def test_twin_stale_masks_results():
    r=compare_scenarios(scenarios(observed_at=(NOW-timedelta(days=2)).isoformat()),now=NOW)
    assert r['status']=='unknown' and not r['ranking']

def test_file_watch_redacts_sensitive():
    r=summarize_changes(changes(),now=NOW)
    assert r['counts']['created']==1 and r['counts']['modified']==1
    assert r['redacted_sensitive_count']==1
    assert r['visible_events']==[dict(path='project/README.md',kind='modified',is_directory=False)]
    assert '.env' not in str(r)
    assert not r['workflow_triggered']

def test_file_watch_zero_events():
    r=summarize_changes(changes(events=[]),now=NOW)
    assert r['visible_events']==[] and r['redacted_sensitive_count']==0

@pytest.mark.parametrize('p',['../private','.','/absolute','C:/Users/file','project/../secret','a\\b','x\nname','x//y','a/.ssh/id_rsa/../x'])
def test_file_watch_path_rejected(p):
    with pytest.raises(ValueError): summarize_changes(changes(events=[dict(path=p,kind='modified',is_directory=False)]),now=NOW)

@pytest.mark.parametrize('bad',[
    {'events':'bad'},{'events':[{}]},{'events':[dict(path='x',kind='executed',is_directory=False)]},
    {'events':[dict(path='x',kind='created',is_directory=1)]},{'events':[dict(path='x',kind='created',is_directory=False)]*257},
    {'root_ref':'bad\n'}, {'execute':'yes'}
])
def test_file_watch_rejects_malformed(bad):
    with pytest.raises(ValueError):summarize_changes(changes(**bad),now=NOW)

def test_file_watch_stale_masks_sensitive_counts():
    r=summarize_changes(changes(observed_at=(NOW-timedelta(hours=1)).isoformat()),now=NOW)
    assert r['counts'] is None and r['visible_events']==[]

def test_smart_home_protected_redaction():
    r=review_entities(home(),now=NOW)
    assert r['status']=='reported_states_reviewed'
    assert r['entities'][1]['protected'] is True
    assert r['entities'][1]['reported_state']=='[redacted_protected_domain]'
    assert r['entities'][1]['issue']=='expected_state_mismatch'
    assert not r['devices_controlled'] and not r['physical_state_verified']

def test_smart_home_old_last_change_not_stale():
    r=review_entities(home(entities=[dict(entity_id='sensor.basement',state='72',
                 last_changed=(NOW-timedelta(days=30)).isoformat(),expected_state=None)]),now=NOW)
    assert r['entities'][0]['issue'] is None

def test_smart_home_unknown_state():
    r=review_entities(home(entities=[dict(entity_id='light.office',state='unavailable',
                                       last_changed=NOW.isoformat(),expected_state='on')]),now=NOW)
    assert r['findings']==['unavailable']

@pytest.mark.parametrize('bad',[
    {'entities':'bad'}, {'entities':[{}]},
    {'entities':[dict(entity_id='script.turn_on',state='on',last_changed=NOW.isoformat(),expected_state=None)]},
    {'entities':[dict(entity_id='light.office',state='on',last_changed=NOW.isoformat(),expected_state=None)]*2},
    {'entities':[dict(entity_id='light.office',state='on\n',last_changed=NOW.isoformat(),expected_state=None)]},
    {'entities':[dict(entity_id='light.office',state='on',last_changed='naive',expected_state=None)]},
    {'entities':[dict(entity_id='light.office',state='on',last_changed=NOW.isoformat(),expected_state=True)]},
    {'observed_at':'invalid'},{'source_ref':'bad\n'}, {'command':'turn_off'},
])
def test_smart_home_rejects_malformed(bad):
    with pytest.raises(ValueError):review_entities(home(**bad),now=NOW)

def test_smart_home_stale_hides_entities():
    r=review_entities(home(observed_at=(NOW-timedelta(hours=1)).isoformat()),now=NOW)
    assert r['status']=='unknown' and r['entities']==[]

def test_capability_registration_handler_and_scope():
    for reg,input_key,plan in ((cad_regs,'plan',plate()),(twin_regs,'snapshot',scenarios()),
                                (watch_regs,'snapshot',changes()),(home_regs,'snapshot',home())):
        capability,handler=reg()[0]
        assert capability.name.endswith('.v1')
        assert len(reg())==1
        request=CapabilityRequest(capability,{input_key:plan},requested_scope=None,rationale="test simulation")
        # Test injected clock by substituting source timestamp to current UTC in a separate request.
        plan_now=dict(plan,observed_at=datetime.now(timezone.utc).isoformat())
        assert handler(CapabilityRequest(capability,{input_key:plan_now},requested_scope=None,rationale="test simulation"))['effect']=='none'
        with pytest.raises(ValueError):handler(CapabilityRequest(capability,{input_key:plan,'execute':True},requested_scope=None,rationale="test simulation"))
