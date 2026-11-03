"""Final optional-module receipt evidence remains bounded and effect-free."""
from datetime import datetime, timezone

from sofia.modules.energy.analysis import assess_ups
from sofia.modules.it_security import triage_findings
from sofia.modules.it_storage import analyze_volumes
from sofia.modules.smart_home import review_entities

NOW=datetime(2026,11,3,7,0,tzinfo=timezone.utc)


def test_storage_receipt_retains_capacity_and_error_basis():
    row=analyze_volumes([{'source_ref':'storage:probe','volume_ref':'volume:one',
        'observed_at':NOW.isoformat(),'total_bytes':1000,'used_bytes':950,
        'read_only':True,'io_errors':2}],now=NOW)['volumes'][0]
    assert (row['total_bytes'],row['used_bytes'],row['io_errors'])==(1000,950,2)
    assert row['read_only'] is True


def test_security_receipt_retains_reported_lifecycle_state():
    row=triage_findings([{'source_ref':'scanner:one','asset_ref':'host:one',
        'finding_ref':'finding:one','observed_at':NOW.isoformat(),
        'kind':'configuration_drift','severity':'high','state':'open'}],now=NOW)['findings'][0]
    assert row['reported_state']=='open' and row['classification']=='reported_open'


def test_smart_home_receipt_retains_snapshot_time_without_physical_claim():
    result=review_entities({'source_ref':'ha:projection','observed_at':NOW.isoformat(),
        'entities':[]},now=NOW)
    assert result['observed_at']==NOW.isoformat()
    assert result['physical_state_verified'] is False and result['effect']=='none'


def test_energy_receipt_retains_untrusted_measurements_without_shutdown_authority():
    result=assess_ups({'source_ref':'ups:probe','ups_ref':'ups:one',
        'observed_at':NOW.isoformat(),'mains_present':False,'battery_percent':19,
        'load_percent':90,'runtime_seconds':300,'self_test_state':'failed'},now=NOW)
    assert (result['battery_percent'],result['load_percent'],result['runtime_seconds'])==(19,90,300)
    assert result['mains_present'] is False and result['self_test_state']=='failed'
    assert result['estimate_is_not_a_shutdown_permission'] is True and result['effect']=='none'
