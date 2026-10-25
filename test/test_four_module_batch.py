from datetime import datetime, timedelta, timezone
import pytest
from sofia.modules.sensors import evaluate_readings
from sofia.modules.it_observability import correlate
from sofia.modules.it_systems import inspect_system
from sofia.modules.it_containers import inspect_containers

NOW = datetime(2026, 10, 25, 14, 0, tzinfo=timezone.utc)
def sensor(**x):
    return dict(source_ref='station:1', sensor_ref='probe:1', observed_at=NOW.isoformat(), kind='temperature_c', value=23.4, quality='calibrated') | x
def obs(**x):
    return dict(source_ref='platform:1', component_ref='app:1', observed_at=NOW.isoformat(), state='warning', signal='memory') | x
def system(**x):
    return dict(source_ref='platform:1', observed_at=NOW.isoformat(), cpu_percent=34, memory_percent=30, disk_percent=15, uptime_seconds=123) | x
def container(**x):
    return dict(source_ref='portainer:1', container_ref='service:1', observed_at=NOW.isoformat(), state='running', health='healthy', restart_count=0) | x

def test_sensor_good():
    result = evaluate_readings([sensor()], now=NOW)
    assert result['observations'][0]['value'] == 23.4
    assert result['effect'] == 'none'
def test_sensor_stale_masks_value():
    result = evaluate_readings([sensor(observed_at=(NOW-timedelta(hours=1)).isoformat())],now=NOW)
    assert result['observations'][0]['value'] is None
    assert result['observations'][0]['freshness'] == 'stale'
@pytest.mark.parametrize('change', [{'value':float('nan')},{'value':True},{'kind':'camera'},{'source_ref':'oops\n'},{'value':120.0,'kind':'humidity_percent'},{'observed_at':'nope'}])
def test_sensor_invalid_or_out_of_bounds(change):
    if change == {'value':120.0,'kind':'humidity_percent'}:
        assert evaluate_readings([sensor(**change)],now=NOW)['observations'][0]['status'] == 'out_of_range'
    else:
        with pytest.raises(ValueError):evaluate_readings([sensor(**change)],now=NOW)
def test_sensor_duplicate():
    with pytest.raises(ValueError):evaluate_readings([sensor(),sensor()],now=NOW)
def test_observability_correlated():
    result = correlate([obs(),obs(signal='cpu',state='critical')],now=NOW)
    assert result['incidents'][0]['correlated'] is True
    assert result['incidents'][0]['severity']=='critical'
def test_observability_stale_not_incident():
    result=correlate([obs(observed_at=(NOW-timedelta(hours=1)).isoformat())],now=NOW)
    assert result['incidents']==[] and result['excluded_out_of_window']==1
@pytest.mark.parametrize('change', [{'state':'red'},{'signal':'command'},{'observed_at':'now'}])
def test_observability_rejects(change):
    with pytest.raises(ValueError):correlate([obs(**change)],now=NOW)
def test_observability_duplicates_rejected():
    with pytest.raises(ValueError):correlate([obs(),obs()],now=NOW)
def test_system_pressure():
    result=inspect_system(system(cpu_percent=95),now=NOW)
    assert result['pressure_flags']==['cpu_pressure'] and result['effect']=='none'
def test_system_stale_never_declares_health():
    result=inspect_system(system(cpu_percent=99,observed_at=(NOW-timedelta(hours=1)).isoformat()),now=NOW)
    assert result['classification']=='unknown' and result['pressure_flags']==[]
@pytest.mark.parametrize('change',[{'cpu_percent':float('inf')},{'disk_percent':False},{'memory_percent':101},{'uptime_seconds':-1}])
def test_system_bad_inputs(change):
    with pytest.raises(ValueError):inspect_system(system(**change),now=NOW)
def test_container_healthy_and_degraded():
    result=inspect_containers([container(),container(container_ref='service:2',health='unhealthy')],now=NOW)
    assert [x['condition'] for x in result['containers']]==['observed_healthy','degraded']
def test_container_stale_does_not_claim_health():
    result=inspect_containers([container(observed_at=(NOW-timedelta(hours=1)).isoformat())],now=NOW)
    assert result['containers'][0]['condition']=='unknown'
@pytest.mark.parametrize('change',[{'restart_count':-1},{'restart_count':True},{'state':'broken'},{'health':'ok'},{'observed_at':'untrusted'}])
def test_container_bad_inputs(change):
    with pytest.raises(ValueError):inspect_containers([container(**change)],now=NOW)
def test_container_duplicates():
    with pytest.raises(ValueError):inspect_containers([container(),container()],now=NOW)
