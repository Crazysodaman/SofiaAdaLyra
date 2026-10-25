"""Batch 9 isolated-source verification. SDK/Platform stand-ins not production admission."""
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import pytest
from sofia.platform.capability.model import CapabilityRequest
from sofia.modules.research.analysis import compare_claim_sources,capability_registrations as research_regs
from sofia.modules.browser.analysis import review_navigation_candidates,capability_registrations as browser_regs
from sofia.modules.workshop.analysis import review_experiment_plan,capability_registrations as workshop_regs
from sofia.modules.project_forge.analysis import review_artifact_manifest,capability_registrations as forge_regs

NOW=datetime(2026,10,25,18,0,tzinfo=timezone.utc)
def at(sec=0):return (NOW+timedelta(seconds=sec)).isoformat()
def evidence(i,origin='publisher:a',stance='supports',published=None):
    return dict(evidence_id=i,origin_ref=origin,published_at=at(-86400) if published is None else published,
                stance=stance,citation_ref='citation:'+i)
def research(**kwargs):
    return dict(source_ref='research:1',observed_at=at(),claim_id='claim:a',evidence=[
        evidence('one'),evidence('two','publisher:b','disputes')])|kwargs
def browser(**kwargs):
    return dict(source_ref='browser:1',observed_at=at(),allowed_hosts=['example.com','docs.python.org'],
                candidates=[dict(candidate_id='a',url='https://example.com/a'),
                            dict(candidate_id='b',url='https://other.example/file')])|kwargs
def workshop(**kwargs):
    return dict(source_ref='workshop:plan',observed_at=at(),experiment_id='test-run',
                host_class='disposable_workshop_guest',network_mode='isolated_none',
                disk_gib=32,memory_mib=2048,vcpus=2,
                steps=['prepare_image','verify_isolation','snapshot_clean','run_offline_tests',
                       'collect_sanitized_results','destroy_disposable_guest'],
                destruction_reviewed=True)|kwargs
def art(id,digest='a'*64,test='passed',reviewed=True):
    return dict(artifact_id=id,digest_sha256=digest,reviewed=reviewed,test_result=test)
def criterion(id,aid='one',met=True):
    return dict(criterion_id=id,artifact_id=aid,met=met)
def forge(**kwargs):
    return dict(source_ref='forge:artifact',observed_at=at(),project_ref='project:one',
                artifacts=[art('one')],criteria=[criterion('r1')])|kwargs

def test_research_conflict():
    r=compare_claim_sources(research(),now=NOW)
    assert r['conflicting_stances'] and r['source_count']==2
    assert r['stance_counts']=={'disputes':1,'supports':1,'uncertain':0}
    assert not r['claims_fact_checked'] and not r['external_requests_sent']

def test_research_uncertainty_not_truth():
    r=compare_claim_sources(research(evidence=[evidence('a',stance='uncertain')]),now=NOW)
    assert not r['conflicting_stances'] and r['finding']=='no_supplied_contradiction'
    assert r['claims_fact_checked'] is False

def test_research_distinct_origin_count():
    r=compare_claim_sources(research(evidence=[evidence('a'),evidence('b')]),now=NOW)
    assert r['source_count']==1 and r['stance_counts']['supports']==2

def test_research_old_sources_flagged():
    r=compare_claim_sources(research(evidence=[evidence('old',published=at(-86400*800))]),now=NOW)
    assert r['older_source_refs']==['old']

@pytest.mark.parametrize('delta',[-200000,3600])
def test_research_stale_future_masks(delta):
    r=compare_claim_sources(research(observed_at=at(delta),evidence=[evidence('a',published=at(delta-86400))]),now=NOW)
    assert r['status']=='unknown' and r['source_count'] is None and not r['review_items']

@pytest.mark.parametrize('change',[{'source_ref':'bad\n'}, {'claim_id':'evil hacker'}, {'evidence':[]},
 {'evidence':'bad'},{'evidence':[{}]},{'evidence':[evidence('a')]*2},
 {'evidence':[evidence('a',stance='unknown')]},
 {'evidence':[evidence('a',published=at(3600))]},
 {'evidence':[evidence('a',published='2026-10-25')]},
 {'evidence':[evidence(str(i)) for i in range(65)]},
 {'observed_at':'2026-10-25'}, {'grant':True}])
def test_research_bad_payloads(change):
    with pytest.raises(ValueError):compare_claim_sources(research(**change),now=NOW)

def test_browser_allowlist_and_denial():
    r=review_navigation_candidates(browser(),now=NOW)
    assert r['allowed_count']==1
    assert r['reviewed'][0]['url']=='https://example.com/a'
    assert r['reviewed'][1]['url'] is None
    assert not r['requests_sent'] and not r['navigation_authorized'] and not r['dns_verified']

def test_browser_exact_host_not_subdomain():
    r=review_navigation_candidates(browser(candidates=[dict(candidate_id='sub',url='https://evil.example.com/')]),now=NOW)
    assert r['allowed_count']==0

def test_browser_https_normalize_path():
    r=review_navigation_candidates(browser(candidates=[dict(candidate_id='a',url='https://example.com')]),now=NOW)
    assert r['reviewed'][0]['url']=='https://example.com/'

@pytest.mark.parametrize('url',['http://example.com','https://127.0.0.1/','https://[::1]/',
 'https://localhost/','https://admin:secret@example.com','https://example.com:444/',
 'https://example.com/a#fragment','https://example.com/?token=secret',
 'https://example.com\\@localhost','https://example.com/a%0a',
 'https://example.com/a%2fb','https://example.com/a\n',
 'https://intranet.local/','https://example.com.evil.local/',
 'https://EXAMPLE.com/','ftp://example.com/'])
def test_browser_rejects_unsafe_urls(url):
    with pytest.raises(ValueError):
        review_navigation_candidates(browser(candidates=[dict(candidate_id='a',url=url)]),now=NOW)

@pytest.mark.parametrize('change',[{'allowed_hosts':[]},{'allowed_hosts':['example.com']*2},
 {'allowed_hosts':['localhost']},{'candidates':[]},{'candidates':'bad'},
 {'candidates':[dict(candidate_id='a',url='https://example.com/')]*2},
 {'candidates':[dict(candidate_id='a',url='https://example.com/')|{'execute':True}]},
 {'observed_at':'bad'}, {'source_ref':'invalid id'}, {'send_request':True}])
def test_browser_rejects_bad_payloads(change):
    with pytest.raises(ValueError):review_navigation_candidates(browser(**change),now=NOW)

@pytest.mark.parametrize('delta',[-7200,3600])
def test_browser_freshness_mask(delta):
    r=review_navigation_candidates(browser(observed_at=at(delta)),now=NOW)
    assert r['status']=='unknown' and r['allowed_count'] is None and not r['reviewed']

def test_workshop_valid_is_not_authorized():
    r=review_experiment_plan(workshop(),now=NOW)
    assert r['procedurally_complete'] is True and r['platform_acceptance_required']
    assert r['resource_request']=={'vcpus':2,'disk_gib':32,'memory_mib':2048}
    assert not r['vm_created'] and not r['provisioning_authorized']

def test_workshop_missing_destroy_blocks():
    steps=workshop()['steps'][:-1]
    r=review_experiment_plan(workshop(steps=steps,destruction_reviewed=False),now=NOW)
    assert 'destroy_disposable_guest' in r['missing_steps']
    assert 'no_destruction_review' in r['findings']
    assert not r['procedurally_complete']

def test_workshop_order_and_isolation():
    r=review_experiment_plan(workshop(network_mode='isolated_internal',steps=list(reversed(workshop()['steps']))),now=NOW)
    assert 'experiment_steps_out_of_order' in r['findings']
    assert 'isolation_must_be_verified_by_platform' in r['findings']

@pytest.mark.parametrize('change',[{'host_class':'canonical'}, {'network_mode':'bridged'},
 {'vcpus':True},{'disk_gib':0},{'memory_mib':40000},{'steps':[]},
 {'steps':['run_offline_tests','run_offline_tests']},{'steps':['start_core']},
 {'destruction_reviewed':1},{'experiment_id':'invalid id'},{'observed_at':'naive'},
 {'source_ref':'bad\n'},{'authorize':True}])
def test_workshop_invalid(change):
    with pytest.raises(ValueError):review_experiment_plan(workshop(**change),now=NOW)

@pytest.mark.parametrize('delta',[-200000,3600])
def test_workshop_stale_masks(delta):
    r=review_experiment_plan(workshop(observed_at=at(delta)),now=NOW)
    assert r['status']=='unknown' and r['resource_request'] is None

def test_forge_candidates_not_authoritative():
    r=review_artifact_manifest(forge(),now=NOW)
    assert r['candidate_ready_count']==1 and r['artifacts'][0]['candidate_ready']
    assert not r['test_executed'] and not r['all_acceptance_verified'] and not r['delivery_authorized']

def test_forge_blocked_reasons():
    r=review_artifact_manifest(forge(artifacts=[art('one',test='unverified',reviewed=False)],
                                  criteria=[criterion('r1',met=False)]),now=NOW)
    assert set(r['artifacts'][0]['blockers'])=={'human_review_missing','test_evidence_unverified_or_failed',
                                              'acceptance_criteria_unmet'}

def test_forge_missing_criteria_blocks():
    r=review_artifact_manifest(forge(criteria=[criterion('r2',aid='two')],artifacts=[art('one'),art('two')]),now=NOW)
    assert r['candidate_ready_count']==1
    assert 'acceptance_criteria_missing' in r['artifacts'][0]['blockers']

@pytest.mark.parametrize('change',[{'artifacts':[]},{'artifacts':[art('one')]*2},
 {'artifacts':[art('one',digest='x'*64)]},{'artifacts':[art('one',reviewed=1)]},
 {'artifacts':[art('one',test='real')]},{'criteria':[]},
 {'criteria':[criterion('r1')]*2},{'criteria':[criterion('r1',aid='missing')]},
 {'criteria':[criterion('r1',met=1)]},{'source_ref':'bad\n'},
 {'project_ref':'with space'},{'observed_at':'naive'},
 {'go_live':True}])
def test_forge_invalid(change):
    with pytest.raises(ValueError):review_artifact_manifest(forge(**change),now=NOW)

@pytest.mark.parametrize('delta',[-200000,3600])
def test_forge_stale_masks(delta):
    r=review_artifact_manifest(forge(observed_at=at(delta)),now=NOW)
    assert r['status']=='unknown' and r['candidate_ready_count'] is None and not r['artifacts']

@pytest.mark.parametrize('regs,snapshot',[ (research_regs,research),(browser_regs,browser),
                                            (workshop_regs,workshop),(forge_regs,forge)])
def test_real_shape_request_and_no_effect(regs,snapshot):
    capability,handler=regs()[0]
    request=CapabilityRequest(capability=capability,parameters={'snapshot':snapshot()},
                              requested_scope=None,rationale='review test-only evidence')
    result=handler(request)
    assert result['effect']=='none'
    with pytest.raises(ValueError):handler(CapabilityRequest(capability=capability,
                 parameters={'snapshot':snapshot(),'execute':True},requested_scope=None,rationale='bad input'))
