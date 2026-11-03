"""Wave H reports retain experiment evidence without certifying it."""
from datetime import datetime, timezone

from sofia.modules.digital_twin import compare_scenarios
from sofia.modules.generalization import review_generalization
from sofia.modules.mentor_review import review_mentor_review
from sofia.modules.ml_evaluation import review_ml_evaluation
from sofia.modules.workshop import review_experiment_plan

NOW=datetime(2026,11,3,6,0,tzinfo=timezone.utc)
DIGEST="a"*64


def test_workshop_receipt_retains_inert_plan_identity():
    steps=['prepare_image','verify_isolation','snapshot_clean','run_offline_tests','collect_sanitized_results','destroy_disposable_guest']
    result=review_experiment_plan({'source_ref':'workshop:plan','observed_at':NOW.isoformat(),
        'experiment_id':'experiment:one','host_class':'disposable_workshop_guest',
        'network_mode':'isolated_none','disk_gib':32,'memory_mib':2048,'vcpus':2,
        'steps':steps,'destruction_reviewed':True},now=NOW)
    assert result['observed_at']==NOW.isoformat() and result['steps']==steps
    assert result['vm_created'] is False and result['provisioning_authorized'] is False


def test_digital_twin_receipt_retains_snapshot_time_without_outage_claim():
    result=compare_scenarios({'source_ref':'twin:projection','observed_at':NOW.isoformat(),
        'critical_host_ids':['host:a'],'scenarios':[{'scenario_id':'scenario:one',
        'initial_host_id':'host:a','affected_host_ids':['host:a'],
        'fidelity':'dependency_graph_v1','outcome':'modeled_only'}]},now=NOW)
    assert result['observed_at']==NOW.isoformat()
    assert result['real_outage_verified'] is False and result['effect']=='none'


def test_ml_and_transfer_receipts_retain_held_out_basis():
    ml=review_ml_evaluation({'source_ref':'ml:eval','observed_at':NOW.isoformat(),'items':[
        {'id':'eval:one','tp':8,'fp':2,'tn':9,'fn':1,'split_kind':'holdout',
         'leakage_check_passed':True}]},now=NOW)['results'][0]
    transfer=review_generalization({'source_ref':'transfer:eval','observed_at':NOW.isoformat(),'items':[
        {'id':'trial:one','baseline_successes':4,'candidate_successes':7,'trial_count':10,
         'novel_task':True,'independent_holdout':True}]},now=NOW)['results'][0]
    assert (ml['tp'],ml['fp'],ml['tn'],ml['fn'])==(8,2,9,1)
    assert ml['split_kind']=='holdout' and ml['release_verified'] is False
    assert (transfer['baseline_successes'],transfer['candidate_successes'],transfer['trial_count'])==(4,7,10)
    assert transfer['generalized_intelligence_verified'] is False


def test_mentor_receipt_retains_digest_and_independence_basis():
    item=review_mentor_review({'source_ref':'mentor:review','observed_at':NOW.isoformat(),'items':[
        {'id':'rubric:one','criterion':'grounding','score':4,'maximum':5,
         'evidence_digest':DIGEST,'reviewer_independent':True}]},now=NOW)['results'][0]
    assert (item['score'],item['maximum'],item['evidence_digest'])==(4.0,5.0,DIGEST)
    assert item['reviewer_independent'] is True and item['core_identity_changed'] is False
