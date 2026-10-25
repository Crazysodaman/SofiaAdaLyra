"""13 newly scoped ALPHA module capability checks against SDK-like local harness.

The actual GitHub Platform integration and effect authorization still require CI.
"""
from datetime import datetime, timedelta, timezone
from copy import deepcopy
import importlib
import pytest
from sofia.platform.capability.model import CapabilityRequest, Capability

NOW = datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)
TS = NOW.isoformat()
SHA = 'a'*64
SNAPSHOTS = {
    'development': [{'id':'patch1','path':'src/sofia/modules/cad/analysis.py','operation':'modify','tests_passed':True,'reviewed':True,'protected':False}],
    'creative_studio': [{'id':'scene1','start_s':0,'end_s':10,'asset_digest':SHA,'asset_reviewed':True}],
    'vision': [{'id':'detection1','class':'text','confidence':0.9,'x':0.2,'y':0.1,'width':0.3,'height':0.4,'consent_ref':'consent:1'}],
    'desktop_automation': [{'id':'click1','operation':'click','target_ref':'window:123','approval_ref':'receipt:abc','stop_clear':True,'gaming_status':'not_gaming'}],
    'trains': [{'id':'route1','blocks':['block1','block2'],'occupied_blocks':[],'turnouts_aligned':True,'power_state':'on'}],
    'games': [{'id':'objective1','progress':7,'target':10,'failed':False,'evidence_ref':'session1'}],
    'ml_evaluation': [{'id':'holdout1','tp':12,'fp':3,'tn':35,'fn':4,'split_kind':'holdout','leakage_check_passed':True}],
    'generalization': [{'id':'transfer1','baseline_successes':6,'candidate_successes':9,'trial_count':10,'novel_task':True,'independent_holdout':True}],
    'virtual_world': [{'id':'chair','x':1.0,'y':2.0,'width':0.8,'height':0.5,'space_id':'room:1'}],
    'mentor_review': [{'id':'rubric1','criterion':'grounding','score':4,'maximum':5,'evidence_digest':SHA,'reviewer_independent':True}],
    'media': [{'id':'clip1','start_ms':0,'end_ms':4000,'source_duration_ms':4500,'licensed':True}],
    'avatar3d': [{'id':'head1','joint':'head','angle_deg':30,'minimum_deg':-60,'maximum_deg':60,'rig_digest':SHA}],
    'avatar_studio': [{'id':'layer1','slot':'eyes','layer_order':10,'content_class':'public','reviewed':True,'alpha_present':True}],
}
MODULES = {pkg: 'sofia.modules.'+pkg+('.projection_review' if pkg=='vision' else '.analysis') for pkg in SNAPSHOTS}

def call(pkg, changes=None, **kw):
    module=importlib.import_module(MODULES[pkg])
    snapshot={'source_ref':'source:review','observed_at':TS,'items':deepcopy(SNAPSHOTS[pkg])}
    if changes: snapshot.update(changes)
    return module, module.__dict__['review_vision' if pkg=='vision' else 'review_'+pkg](snapshot, now=NOW, **kw)

@pytest.mark.parametrize('pkg',list(SNAPSHOTS))
def test_valid_review_without_effect(pkg):
    _, result = call(pkg)
    assert result['status']=='reviewed' and result['inspected_count']==1
    assert result['effect']=='none' and not result['action_authorized'] and not result['data_persisted']
    assert result['sdk_protocol']=='1.0' and result['evidence_class']=='supplied_unverified'

@pytest.mark.parametrize('pkg',list(SNAPSHOTS))
def test_stale_masks_supplied_private_values(pkg):
    module,result=call(pkg,{'observed_at':(NOW-timedelta(hours=3)).isoformat()})
    assert result['status']=='unknown' and result['results']==[] and result['inspected_count'] is None

@pytest.mark.parametrize('pkg',list(SNAPSHOTS))
def test_future_masks_result(pkg):
    _,result=call(pkg,{'observed_at':(NOW+timedelta(minutes=10)).isoformat()})
    assert result['freshness']=='future' and not result['results']

@pytest.mark.parametrize('pkg',list(SNAPSHOTS))
def test_invalid_schema_rejected(pkg):
    module=importlib.import_module(MODULES[pkg]); f=getattr(module, 'review_vision' if pkg=='vision' else 'review_'+pkg)
    with pytest.raises(ValueError): f({'source_ref':'source:review','observed_at':TS,'items':[], 'execute':True}, now=NOW)
    with pytest.raises(ValueError): f({'source_ref':'source:review','observed_at':TS,'items':'bad'}, now=NOW)
    with pytest.raises(ValueError): f({'source_ref':'bad\n','observed_at':TS,'items':[]}, now=NOW)
    with pytest.raises(ValueError): f({'source_ref':'source:review','observed_at':'naive','items':[]}, now=NOW)

@pytest.mark.parametrize('pkg',list(SNAPSHOTS))
def test_item_unknown_fields_and_duplicates_rejected(pkg):
    module=importlib.import_module(MODULES[pkg]); f=getattr(module, 'review_vision' if pkg=='vision' else 'review_'+pkg)
    malformed=deepcopy(SNAPSHOTS[pkg]);malformed[0]['secret_token']='example'
    with pytest.raises(ValueError): f({'source_ref':'source:review','observed_at':TS,'items':malformed},now=NOW)
    duplicates=deepcopy(SNAPSHOTS[pkg])*2
    with pytest.raises(ValueError): f({'source_ref':'source:review','observed_at':TS,'items':duplicates},now=NOW)

@pytest.mark.parametrize('pkg',list(SNAPSHOTS))
def test_registered_capability_with_real_request_fields(pkg):
    module=importlib.import_module(MODULES[pkg]); ((capability,handler),)=module.capability_registrations()
    assert isinstance(capability, Capability) and capability.name==module.CAPABILITY_ID
    snap={'source_ref':'source:review','observed_at':datetime.now(timezone.utc).isoformat(),
          'items':deepcopy(SNAPSHOTS[pkg])}
    request=CapabilityRequest(capability=capability,parameters={'snapshot':snap},requested_scope=None,rationale='safe offline test')
    got=handler(request)
    assert got['effect']=='none'
    with pytest.raises(ValueError): handler(CapabilityRequest(capability=capability,parameters={'run_code':True},requested_scope=None,rationale='invalid action'))


def test_dev_rejects_traversal_and_protected_scope():
    _,result=call('development',{'items':[dict(SNAPSHOTS['development'][0],protected=True)]})
    assert result['results'][0]['finding']=='hold'
    with pytest.raises(ValueError):call('development',{'items':[dict(SNAPSHOTS['development'][0],path='../secrets')]})


def test_creative_timeline_and_missing_approval():
    _,result=call('creative_studio',{'items':[dict(SNAPSHOTS['creative_studio'][0],asset_reviewed=False)]})
    assert result['results'][0]['finding']=='asset_review_missing'
    with pytest.raises(ValueError):call('creative_studio',{'items':[dict(SNAPSHOTS['creative_studio'][0],end_s=0)]})


def test_vision_cannot_verify_camera_frames_or_consent():
    _,result=call('vision',{'items':[dict(SNAPSHOTS['vision'][0],consent_ref=None)]})
    assert result['results'][0]['finding']=='consent_unverified'
    with pytest.raises(ValueError):call('vision',{'items':[dict(SNAPSHOTS['vision'][0],x=0.9)]})


def test_desktop_gaming_and_stop_deny():
    _,result=call('desktop_automation',{'items':[dict(SNAPSHOTS['desktop_automation'][0],gaming_status='unknown',stop_clear=False)]})
    assert result['results'][0]['finding']=='blocked' and not result['results'][0]['authorized']


def test_trains_occupied_route_never_clear():
    _,result=call('trains',{'items':[dict(SNAPSHOTS['trains'][0],occupied_blocks=['block1'])]})
    assert result['results'][0]['finding']=='hypothetically_blocked' and not result['results'][0]['live_route_clearance_verified']


def test_games_objective_completion_is_reported_only():
    _,result=call('games',{'items':[dict(SNAPSHOTS['games'][0],progress=11)]})
    assert result['results'][0]['completion']==1 and not result['results'][0]['game_state_verified']


def test_ml_precision_recall_f1_and_leakage():
    _,result=call('ml_evaluation'); item=result['results'][0]
    assert item['precision']==pytest.approx(12/15) and item['recall']==pytest.approx(12/16)
    _,result=call('ml_evaluation',{'items':[dict(SNAPSHOTS['ml_evaluation'][0],leakage_check_passed=False)]})
    assert result['results'][0]['finding']=='not_independent_evidence'


def test_generalization_transfer_denied_without_novel_holdout():
    _,result=call('generalization');assert result['results'][0]['delta_success_rate']==pytest.approx(0.3)
    _,result=call('generalization',{'items':[dict(SNAPSHOTS['generalization'][0],novel_task=False)]})
    assert result['results'][0]['finding']=='not_independent_transfer'


def test_world_coordinates_are_simulated():
    _,result=call('virtual_world');assert result['results'][0]['bounds']==(1,2,1.8,2.5)
    assert not result['results'][0]['world_state_modified']


def test_mentor_review_not_identity_update():
    _,result=call('mentor_review');assert result['results'][0]['normalized_score']==0.8
    assert not result['results'][0]['core_identity_changed']


def test_media_bounds_and_rights_review():
    _,result=call('media',{'items':[dict(SNAPSHOTS['media'][0],end_ms=5000,licensed=False)]})
    assert set(result['results'][0]['issues'])=={'source_bounds_exceeded','rights_review_missing'}


def test_avatar3d_joint_limits():
    _,result=call('avatar3d',{'items':[dict(SNAPSHOTS['avatar3d'][0],angle_deg=100)]})
    assert result['results'][0]['finding']=='limit_exceeded' and not result['results'][0]['pose_rendered']


def test_avatar_studio_private_asset_requires_review():
    _,result=call('avatar_studio',{'items':[dict(SNAPSHOTS['avatar_studio'][0],content_class='private')]})
    assert result['results'][0]['finding']=='requires_review' and not result['results'][0]['wardrobe_modified']

def test_creative_studio_detects_overlapping_scenes():
    second=dict(SNAPSHOTS['creative_studio'][0],id='scene2',start_s=8,end_s=12)
    _,r=call('creative_studio',{'items':SNAPSHOTS['creative_studio']+[second]})
    assert r['findings']==['timeline_overlap_review']


def test_train_competing_routes_are_not_hypothetically_clear():
    second=dict(SNAPSHOTS['trains'][0],id='route2',occupied_blocks=[])
    _,r=call('trains',{'items':SNAPSHOTS['trains']+[second]})
    assert all('competing_route_blocks' in row['blocked_by'] for row in r['results'])


def test_world_overlap_in_same_space_only():
    second=dict(SNAPSHOTS['virtual_world'][0],id='table',x=1.5)
    _,r=call('virtual_world',{'items':SNAPSHOTS['virtual_world']+[second]})
    assert all(row['finding']=='footprint_overlap' for row in r['results'])
    second['space_id']='different_room'
    _,r=call('virtual_world',{'items':SNAPSHOTS['virtual_world']+[second]})
    assert r['findings']==['placement_candidate']


def test_avatar3d_multiple_samples_same_joint_flagged():
    second=dict(SNAPSHOTS['avatar3d'][0],id='head2')
    _,r=call('avatar3d',{'items':SNAPSHOTS['avatar3d']+[second]})
    assert r['results'][1]['finding']=='duplicate_joint_pose'


def test_avatar_studio_duplicate_slot_layer_flagged():
    second=dict(SNAPSHOTS['avatar_studio'][0],id='layer2')
    _,r=call('avatar_studio',{'items':SNAPSHOTS['avatar_studio']+[second]})
    assert r['results'][1]['finding']=='duplicate_slot_layer'
