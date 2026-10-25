"""Focused offline tests for independent, no-effect Batch 8 modules.

SDK and Platform shape stubs are local test fixtures only, not production proof.
"""
from datetime import datetime, timedelta, timezone
import pytest
from sofia.platform.capability.model import CapabilityRequest
from sofia.modules.finance import review_budget_aggregates
from sofia.modules.finance.analysis import capability_registrations as fin_reg
from sofia.modules.calendar import review_schedule_conflicts
from sofia.modules.calendar.analysis import capability_registrations as cal_reg
from sofia.modules.communications import review_delivery_receipts
from sofia.modules.communications.analysis import capability_registrations as com_reg
from sofia.modules.productivity import review_task_dependencies
from sofia.modules.productivity.analysis import capability_registrations as prod_reg

NOW = datetime(2026,10,25,16,0,tzinfo=timezone.utc)
T = lambda n: (NOW + timedelta(minutes=n)).isoformat()


def finance(**updates):
    return dict(source_ref='firefly:review',observed_at=T(0),currency='USD',
                period='2026-10',income_cents=700000,categories=[
                    dict(category_id='food',spent_cents=52000,budget_cents=45000),
                    dict(category_id='rent',spent_cents=180000,budget_cents=180000),
                    dict(category_id='utilities',spent_cents=17000,budget_cents=20000)]) | updates


def event(id, start, end, busy=True):
    return dict(event_id=id,start_at=T(start),end_at=T(end),busy=busy)


def calendar(**updates):
    return dict(source_ref='cal:approved',observed_at=T(0),events=[
        event('a',10,30),event('b',20,35),event('c',35,50),event('free',15,25,False)]) | updates


def receipt(id,status='sent',start=0,upd=1,recipient='opaque:1'):
    return dict(message_id=id,recipient_ref=recipient,status=status,
                submitted_at=T(start),status_at=T(upd))


def comms(**updates):
    return dict(source_ref='mail:review',observed_at=T(3),messages=[
        receipt('m1','sent'),receipt('m2','delivered'),receipt('m3','failed')]) | updates


def task(id,p=3,status='todo',deps=None,due=None):
    return dict(task_id=id,priority=p,status=status,depends_on=deps or [],due_at=T(due) if due is not None else None)


def productivity(**updates):
    return dict(source_ref='tasks:review',observed_at=T(0),tasks=[
        task('done',status='done'),task('blocked_by_dep',deps=['open']),
        task('open',p=5),task('urgent',p=4,due=-60),task('manual',status='blocked')]) | updates


def test_finance_aggregation_and_limits():
    result=review_budget_aggregates(finance(),now=NOW)
    assert result['total_spent_cents']==249000
    assert result['net_cashflow_cents']==451000
    assert result['total_budget_cents']==245000
    assert result['categories_over_budget']==[{'category_id':'food','over_by_cents':7000}]
    assert not result['accounts_accessed'] and not result['transactions_executed']
    assert result['financial_advice'] is False and result['stored'] is False


def test_finance_zero_empty_budget():
    result=review_budget_aggregates(finance(categories=[],income_cents=0),now=NOW)
    assert result['total_spent_cents']==0 and result['net_cashflow_cents']==0


def test_finance_max_cents_and_deterministic_categories():
    result=review_budget_aggregates(finance(categories=[
        dict(category_id='z',spent_cents=12,budget_cents=10),
        dict(category_id='a',spent_cents=4,budget_cents=2)]),now=NOW)
    assert [r['category_id'] for r in result['categories_over_budget']]==['a','z']


@pytest.mark.parametrize('change',[
    {'categories':'bad'}, {'categories':[{}]},
    {'categories':[finance()['categories'][0]]*2},
    {'categories':[dict(category_id='food',spent_cents=1.5,budget_cents=1)]},
    {'categories':[dict(category_id='food',spent_cents=True,budget_cents=1)]},
    {'categories':[dict(category_id='food',spent_cents=-1,budget_cents=1)]},
    {'categories':[dict(category_id='Food Dollar',spent_cents=1,budget_cents=1)]},
    {'categories':finance()['categories']*22},
    {'income_cents':False}, {'income_cents':10**14}, {'income_cents':-1},
    {'currency':'usd'}, {'currency':'USDX'}, {'period':'2026-13'},
    {'period':'2026-1'}, {'source_ref':'not safe\n'}, {'observed_at':'naive'},
    {'execute_payment':True},
])
def test_finance_rejects_untrusted(change):
    with pytest.raises(ValueError):review_budget_aggregates(finance(**change),now=NOW)


@pytest.mark.parametrize('at',[T(-100000),T(40)])
def test_finance_stale_masks_sensitive(at):
    result=review_budget_aggregates(finance(observed_at=at),now=NOW,max_age_seconds=3600)
    assert result['status']=='unknown' and result['total_spent_cents'] is None
    assert 'income_cents' not in result and not result['categories_over_budget']


def test_calendar_half_open_and_free_ignored():
    result=review_schedule_conflicts(calendar(),now=NOW)
    assert result['conflicts']==[{'event_ids':['a','b'],'overlap_seconds':600}]
    assert result['busy_event_count']==3
    assert not result['invitations_sent'] and not result['events_modified']


def test_calendar_utc_offset_overlap():
    first=dict(event_id='one',start_at='2026-10-25T10:00:00-05:00',end_at='2026-10-25T11:00:00-05:00',busy=True)
    second=dict(event_id='two',start_at='2026-10-25T15:30:00+00:00',end_at='2026-10-25T16:30:00+00:00',busy=True)
    result=review_schedule_conflicts(calendar(events=[first,second]),now=NOW)
    assert result['conflicts'][0]['overlap_seconds']==1800


def test_calendar_empty():
    result=review_schedule_conflicts(calendar(events=[]),now=NOW)
    assert result['event_count']==0 and result['conflicts']==[]


@pytest.mark.parametrize('change',[
    {'events':'bad'}, {'events':[{}]}, {'events':[event('a',0,10)]*2},
    {'events':[event('a',10,10)]}, {'events':[event('a',10,9)]},
    {'events':[event('a',0,1,busy=1)]},
    {'events':[event('a',0,1)|{'location':'secret'}]},
    {'events':[event('with space',0,1)]},
    {'events':[event('a',0,1)|{'start_at':'2026-10-25T12:00:00'}]},
    {'events':[event('a',0,1)]*129},
    {'source_ref':'bad\t'}, {'observed_at':'2026-10-25'}, {'modify':True},
])
def test_calendar_rejects_invalid(change):
    with pytest.raises(ValueError):review_schedule_conflicts(calendar(**change),now=NOW)


def test_calendar_stale_mask():
    result=review_schedule_conflicts(calendar(observed_at=T(-2000)),now=NOW)
    assert result['status']=='unknown' and not result['conflicts']


def test_comms_states_and_unverified_delivery():
    result=review_delivery_receipts(comms(),now=NOW+timedelta(minutes=3))
    assert result['counts']['sent']==1 and result['counts']['delivered']==1
    assert result['undelivered_message_ids']==['m1','m3']
    assert result['delivered_message_ids']==['m2']
    assert not result['recipient_read_verified'] and not result['delivery_authenticated']
    assert not result['messages_sent'] and not result['recipient_details_returned']
    assert 'opaque:1' not in str(result)


def test_comms_empty():
    result=review_delivery_receipts(comms(messages=[]),now=NOW+timedelta(minutes=3))
    assert sum(result['counts'].values())==0


@pytest.mark.parametrize('change',[
    {'messages':'bad'},{'messages':[{}]},
    {'messages':[receipt('x')]*2},
    {'messages':[receipt('x',recipient='john@example.com')]},
    {'messages':[receipt('x',status='read')]},
    {'messages':[receipt('x',start=2,upd=1)]},
    {'messages':[receipt('x',start=0,upd=5)]},
    {'messages':[receipt('x')|{'content':'PRIVATE'}]},
    {'messages':[receipt('x')]*129},
    {'source_ref':'evil\n'}, {'observed_at':'no timezone'}, {'send':True},
])
def test_comms_rejects_untrusted(change):
    with pytest.raises(ValueError):review_delivery_receipts(comms(**change),now=NOW)


def test_comms_stale_mask():
    result=review_delivery_receipts(comms(observed_at=T(-90),messages=[receipt('m0',start=-100,upd=-95)]),now=NOW,max_age_seconds=600)
    assert result['status']=='unknown' and not result['counts']


def test_productivity_dependency_prio_and_overdue():
    result=review_task_dependencies(productivity(),now=NOW)
    assert result['ready_task_ids']==['open','urgent']
    assert result['waiting_task_ids']==['blocked_by_dep','manual']
    assert result['overdue_task_ids']==['urgent']
    assert result['completed_count']==1
    assert not result['tasks_modified'] and not result['core_goals_modified']


def test_productivity_dependencies_done():
    result=review_task_dependencies(productivity(tasks=[task('a',status='done'),task('b',deps=['a'])]),now=NOW)
    assert result['ready_task_ids']==['b']


def test_productivity_empty():
    result=review_task_dependencies(productivity(tasks=[]),now=NOW)
    assert result['completed_count']==0 and result['ready_task_ids']==[]


@pytest.mark.parametrize('change',[
    {'tasks':'bad'}, {'tasks':[{}]}, {'tasks':[task('a')]*2},
    {'tasks':[task('x',p=0)]}, {'tasks':[task('x',p=True)]},
    {'tasks':[task('x',status='approved')]},
    {'tasks':[task('x',deps=['missing'])]},
    {'tasks':[task('x',deps=['x'])]},
    {'tasks':[task('x',deps=['a','a']),task('a')]},
    {'tasks':[task('a',deps=['b']),task('b',deps=['a'])]},
    {'tasks':[task('x')|{'schedule_action':'run'}]},
    {'tasks':[task('x',due=4)|{'due_at':'2026-10-25T12:00:00'}]},
    {'tasks':[task('x')]*129},
    {'source_ref':'invalid\n'}, {'observed_at':'2026-10-25'}, {'execute':True},
])
def test_productivity_rejects_malformed(change):
    with pytest.raises(ValueError):review_task_dependencies(productivity(**change),now=NOW)


def test_productivity_stale_mask():
    result=review_task_dependencies(productivity(observed_at=T(-10000)),now=NOW)
    assert result['status']=='unknown' and not result['ready_task_ids']


@pytest.mark.parametrize('register', [fin_reg,cal_reg,com_reg,prod_reg])
def test_capability_registration_and_request_shape(register):
    entries=register()
    assert len(entries)==1
    capability,handler=entries[0]
    assert capability.name.endswith('.v1')
    with pytest.raises(ValueError):handler(CapabilityRequest(capability,{'execute':True},requested_scope=None,rationale='test'))
    with pytest.raises(ValueError):handler(CapabilityRequest(capability,{},requested_scope=None,rationale='test'))


def test_capability_handlers_success_live_clock():
    snapshots=[finance(observed_at=datetime.now(timezone.utc).isoformat()),
               calendar(observed_at=datetime.now(timezone.utc).isoformat(),events=[]),
               comms(observed_at=datetime.now(timezone.utc).isoformat(),messages=[]),
               productivity(observed_at=datetime.now(timezone.utc).isoformat(),tasks=[])]
    for register,snapshot in zip((fin_reg,cal_reg,com_reg,prod_reg),snapshots):
        cap,handler=register()[0]
        result=handler(CapabilityRequest(cap,{'snapshot':snapshot},requested_scope=None,rationale='test'))
        assert result['status']=='reviewed' and result['effect']=='none'
