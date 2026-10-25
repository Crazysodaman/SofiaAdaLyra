"""Offline tests for four independently installable, effect-free modules.

The container uses local SDK shape stand-ins; production SDK integration is not
certified by this focused test run.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math
import pytest

from sofia.platform.capability.model import CapabilityRequest
from sofia.modules.household import review_inventory
from sofia.modules.household.analysis import capability_registrations as hr
from sofia.modules.data_analytics import summarize_numeric
from sofia.modules.data_analytics.analysis import capability_registrations as ar
from sofia.modules.knowledge_library import plan_revision_index
from sofia.modules.knowledge_library.analysis import capability_registrations as kr
from sofia.modules.documents import render_safe_markdown
from sofia.modules.documents.analysis import capability_registrations as dr

NOW = datetime(2026, 10, 25, 15, tzinfo=timezone.utc)
D1 = 'a' * 64
D2 = 'b' * 64


def household(**changes):
    return {'source_ref': 'grocy:owner', 'observed_at': NOW.isoformat(), 'items': [
        {'item_id': 'milk', 'quantity': 1, 'minimum_quantity': 2, 'expires_on': '2026-10-27'},
        {'item_id': 'beans', 'quantity': 6, 'minimum_quantity': 2, 'expires_on': None},
        {'item_id': 'bread', 'quantity': 1, 'minimum_quantity': 0, 'expires_on': '2026-10-20'}]} | changes


def table(**changes):
    return {'source_ref': 'dataset:approved', 'observed_at': NOW.isoformat(),
            'columns': ['voltage', 'current'],
            'rows': [{'voltage': 1, 'current': 2}, {'voltage': 3, 'current': None},
                     {'voltage': 5, 'current': 4}]} | changes


def doc(doc_id='manual', revision=D2, indexed=D1, deleted=False, modified=None):
    return {'document_id': doc_id, 'source_ref': 'docs:manual', 'revision_sha256': revision,
            'indexed_sha256': indexed, 'modified_at': (modified or NOW).isoformat(), 'deleted': deleted}


def library(**changes):
    return {'source_ref': 'index:manifest', 'observed_at': NOW.isoformat(),
            'documents': [doc(), doc('unchanged', revision=D1, indexed=D1),
                          doc('removed', revision=None, indexed=D1, deleted=True)]} | changes


def document(**changes):
    return {'source_ref': 'owner:draft', 'observed_at': NOW.isoformat(),
            'title': 'My *Report*', 'sections': [{'heading': 'A <Heading>',
                     'paragraphs': ['This is 1+1.', '[see](evil) <script>']}]} | changes


def test_household_assessment_and_no_effect():
    result = review_inventory(household(), now=NOW)
    assert result['low_stock'] == ['milk']
    assert result['expired'] == ['bread']
    assert result['expiring_within_7_days'] == ['milk']
    assert result['observed_item_count'] == 3
    assert not result['shopping_authorized'] and not result['inventory_modified']


def test_household_no_items():
    assert review_inventory(household(items=[]), now=NOW)['observed_item_count'] == 0


def test_household_age_masks_outputs():
    for at in (NOW-timedelta(days=2), NOW+timedelta(hours=1)):
        result = review_inventory(household(observed_at=at.isoformat()), now=NOW)
        assert result['status'] == 'unknown' and not result['low_stock']
        assert result['observed_item_count'] is None


@pytest.mark.parametrize('mutation', [
    {'items': 'bad'}, {'items': [{}]}, {'items': [household()['items'][0]]*2},
    {'items': [{'item_id':'private name', 'quantity':1,'minimum_quantity':1,'expires_on':None}]},
    {'items': [{'item_id':'x','quantity':True,'minimum_quantity':1,'expires_on':None}]},
    {'items': [{'item_id':'x','quantity':float('nan'),'minimum_quantity':1,'expires_on':None}]},
    {'items': [{'item_id':'x','quantity':1,'minimum_quantity':-1,'expires_on':None}]},
    {'items': [{'item_id':'x','quantity':1,'minimum_quantity':1,'expires_on':'2026-02-31'}]},
    {'items': [{'item_id':'x','quantity':1,'minimum_quantity':1,'expires_on':'01/01/2027'}]},
    {'items': household()['items']*43}, {'source_ref':'bad\n'},
    {'observed_at':'2026-10-25'}, {'unexpected_action': True},
])
def test_household_rejects_invalid(mutation):
    with pytest.raises(ValueError): review_inventory(household(**mutation), now=NOW)


def test_analytics_summary_with_missing():
    result = summarize_numeric(table(), now=NOW)
    assert result['row_count'] == 3
    assert result['statistics']['voltage']['mean'] == 3
    assert result['statistics']['voltage']['median'] == 3
    assert result['statistics']['voltage']['sample_stddev'] == 2
    assert result['statistics']['current']['missing'] == 1
    assert result['statistics']['current']['mean'] == 3
    assert result['raw_rows_returned'] is False and result['data_persisted'] is False
    assert 'rows' not in result


def test_analytics_all_missing():
    r = summarize_numeric(table(columns=['m'],rows=[{'m':None}]),now=NOW)
    assert r['statistics']['m']['mean'] is None
    assert r['statistics']['m']['sample_stddev'] is None


def test_analytics_future_masks():
    r = summarize_numeric(table(observed_at=(NOW+timedelta(days=2)).isoformat()),now=NOW)
    assert r['row_count'] is None and not r['statistics']


@pytest.mark.parametrize('mutation', [
    {'columns':[]}, {'columns':['x','x']}, {'columns':['bad name']},
    {'rows':[]}, {'rows':[{}]}, {'rows':[{'voltage':2,'current':3,'extra':7}]},
    {'rows':[{'voltage':True,'current':0}]},
    {'rows':[{'voltage':float('nan'),'current':0}]},
    {'rows':[{'voltage':float('inf'),'current':0}]},
    {'rows':[{'voltage':1e40,'current':0}]},
    {'rows':[{'voltage':2,'current':3}]*513},
    {'rows':'x'}, {'source_ref':'invalid path?'}, {'observed_at':'naive'}, {'export_file':True},
])
def test_analytics_rejects_invalid(mutation):
    with pytest.raises(ValueError): summarize_numeric(table(**mutation),now=NOW)


def test_knowledge_revision_plan():
    r=plan_revision_index(library(),now=NOW)
    assert r['status']=='proposed_only'
    assert r['unchanged_count']==1
    assert [c['operation'] for c in r['candidate_operations']]==['candidate_update','tombstone']
    assert not r['index_written'] and not r['memory_promoted']
    assert not r['source_authenticity_verified']


def test_knowledge_deleted_without_index_noop():
    r=plan_revision_index(library(documents=[doc('n',revision=None,indexed=None,deleted=True)]),now=NOW)
    assert r['unindexed_deleted_count']==1 and not r['candidate_operations']


def test_knowledge_stale_masks():
    r=plan_revision_index(library(observed_at=(NOW-timedelta(days=2)).isoformat(),
                                  documents=[doc('old',modified=NOW-timedelta(days=3))]),now=NOW)
    assert r['status']=='unknown' and r['unchanged_count'] is None


@pytest.mark.parametrize('mutation', [
    {'documents':'x'}, {'documents':[{}]},
    {'documents':[doc(),doc()]},
    {'documents':[doc(doc_id='bad doc')]},
    {'documents':[doc(revision='xyz')]},
    {'documents':[doc(indexed='bad')]},
    {'documents':[doc(revision=None,deleted=False)]},
    {'documents':[doc(revision=D1,deleted=True)]},
    {'documents':[doc(deleted=1)]},
    {'documents':[doc(modified=NOW+timedelta(days=1))]},
    {'documents':[doc(doc_id='x')]*129},
    {'source_ref':'x\n'}, {'observed_at':'no timezone'}, {'index_now':True},
])
def test_knowledge_rejects_invalid(mutation):
    with pytest.raises(ValueError):plan_revision_index(library(**mutation),now=NOW)


def test_documents_render_and_determinism():
    r=render_safe_markdown(document(),now=NOW)
    assert r['status']=='rendered_in_memory'
    assert r['markdown'].startswith('# My \\*Report\\*\n\n## A \\<Heading\\>')
    assert r['sha256']==sha256(r['markdown'].encode()).hexdigest()
    assert '[see](evil)' not in r['markdown']
    assert '<script>' not in r['markdown']
    assert not r['file_written'] and not r['published']
    assert r==render_safe_markdown(document(),now=NOW)


def test_documents_escaping_prevents_headings():
    r=render_safe_markdown(document(title='# dangerous',sections=[{'heading':'x','paragraphs':['## forged heading']}]),now=NOW)
    assert '## forged heading' not in r['markdown']
    assert '\\#\\# forged heading' in r['markdown']


def test_documents_stale_masks():
    r=render_safe_markdown(document(observed_at=(NOW-timedelta(days=2)).isoformat()),now=NOW)
    assert r['status']=='unknown' and r['markdown'] is None and r['sha256'] is None


@pytest.mark.parametrize('mutation', [
    {'sections':[]}, {'sections':'bad'}, {'sections':[{}]},
    {'sections':[{'heading':'A','paragraphs':[]}]},
    {'sections':[{'heading':'A','paragraphs':['hi\nbye']}]},
    {'sections':[{'heading':'A','paragraphs':['<x>','ok'], 'html':True}]},
    {'sections':[{'heading':'A','paragraphs':['a'*2001]}]},
    {'sections':[{'heading':'A','paragraphs':['x']}]*33},
    {'sections':[{'heading':'A','paragraphs':['x']*17}]},
    {'title':'bad\rtitle'}, {'title':' '}, {'title':'x'*161},
    {'source_ref':'no space allowed'}, {'observed_at':'not date'}, {'publish':True},
])
def test_documents_rejects_invalid(mutation):
    with pytest.raises(ValueError): render_safe_markdown(document(**mutation),now=NOW)


@pytest.mark.parametrize('registration, factory', [
    (hr, household), (ar,table), (kr, library), (dr, document),
])
def test_capability_handlers(registration, factory):
    registrations=registration()
    assert len(registrations)==1
    capability,handler=registrations[0]
    now=datetime.now(timezone.utc)
    request=CapabilityRequest(capability, {'snapshot':factory(observed_at=now.isoformat())},None,'test')
    result=handler(request)
    assert result['effect']=='none'
    assert result['sdk_protocol']=='1.0'
    with pytest.raises(ValueError):handler(CapabilityRequest(capability,{'snapshot':factory(),'unsafe':True},None,'test'))


def test_invalid_age_bound():
    for fn, maker in ((review_inventory, household),(summarize_numeric,table),
                      (plan_revision_index,library),(render_safe_markdown,document)):
        with pytest.raises(ValueError): fn(maker(),now=NOW,max_age_seconds=True)
        with pytest.raises(ValueError): fn(maker(),now=datetime(2026,10,25))
