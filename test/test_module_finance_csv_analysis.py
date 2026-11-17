"""Bounded CSV transaction tests. No account provider, network or transfers."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.finance.parsing import (
    CAPABILITY_ID,
    MAX_CSV_BYTES,
    MAX_TRANSACTION_ROWS,
    analyze_transaction_csv,
    capability_registrations,
)
from sofia.platform.capability.model import CapabilityRequest

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
HEADER = 'date,account_id,category,amount_cents'


def csv_text(rows):
    return '\n'.join([HEADER, *rows]) + '\n'


def snapshot(content, **changes):
    return {
        'source_ref': 'finance:supplied',
        'observed_at': NOW.isoformat(),
        'currency': 'USD',
        'budgets': {'food': 45000, 'rent': 180000, 'utilities': 20000},
        'content': content,
    } | changes


def test_csv_aggregates_by_month_category_and_budget_without_account_leak():
    content = csv_text([
        '2026-10-01,acct-SECRET-123,food,52000',
        '2026-10-02,acct-SECRET-123,food,1000',
        '2026-11-03,acct-OTHER-999,rent,180000',
    ])
    result = analyze_transaction_csv(snapshot(content), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['row_count'] == 3
    assert result['total_cents'] == 233000
    assert result['totals_by_month'] == [
        {'month': '2026-10', 'total_cents': 53000, 'transaction_count': 2},
        {'month': '2026-11', 'total_cents': 180000, 'transaction_count': 1},
    ]
    assert result['totals_by_category'] == [
        {'category_id': 'food', 'total_cents': 53000, 'transaction_count': 2},
        {'category_id': 'rent', 'total_cents': 180000, 'transaction_count': 1},
    ]
    assert result['budget_variance'] == [
        {'category_id': 'food', 'budget_cents': 45000, 'spent_cents': 53000,
         'variance_cents': -8000, 'over_budget': True},
        {'category_id': 'rent', 'budget_cents': 180000, 'spent_cents': 180000,
         'variance_cents': 0, 'over_budget': False},
        {'category_id': 'utilities', 'budget_cents': 20000, 'spent_cents': 0,
         'variance_cents': 20000, 'over_budget': False},
    ]
    assert result['effect'] == 'none'
    assert result['accounts_accessed'] is False
    assert result['account_ids_returned'] is False
    assert result['account_ids_redacted'] is True
    assert result['transactions_executed'] is False
    assert result['network_used'] is False
    assert result['raw_rows_returned'] is False
    assert result['stored'] is False
    text = str(result)
    assert 'acct-SECRET-123' not in text
    assert 'acct-OTHER-999' not in text


def test_csv_accepts_bytes_and_header_only_zero_rows():
    content = (HEADER + '\n').encode('utf-8')
    result = analyze_transaction_csv(snapshot(content, budgets={}), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['row_count'] == 0
    assert result['total_cents'] == 0
    assert result['content_bytes'] == len(content)


def test_csv_accepts_exact_row_limit():
    rows = [f'2026-10-01,acct-opaque,food,{index}' for index in range(1000)]
    result = analyze_transaction_csv(snapshot(csv_text(rows)), now=NOW)
    assert result['row_count'] == MAX_TRANSACTION_ROWS
    assert result['total_cents'] == sum(range(1000))


def test_csv_rejects_row_and_byte_overflow():
    rows = [f'2026-10-01,acct-opaque,food,{index}' for index in range(1001)]
    with pytest.raises(ValueError, match='limit'):
        analyze_transaction_csv(snapshot(csv_text(rows)), now=NOW)
    with pytest.raises(ValueError, match='size'):
        analyze_transaction_csv(snapshot(b'x' * (MAX_CSV_BYTES + 1)), now=NOW)


@pytest.mark.parametrize('content', [
    '',
    'date,account,category,amount_cents\n2026-10-01,a,food,1\n',
    csv_text(['2026-10-01,a,food']),
    csv_text(['2026-10-01,a,food,1,extra']),
    csv_text(['2026-13-01,a,food,1']),
    csv_text(['2026-02-31,a,food,1']),
    csv_text(['2026-10-01,john@example.com,food,1']),
    csv_text(['2026-10-01,acct with space,food,1']),
    csv_text(['2026-10-01,a,Food,1']),
    csv_text(['2026-10-01,a,food,1.5']),
    csv_text(['2026-10-01,a,food,1e3']),
    csv_text(['2026-10-01,a,food,0001']),
    csv_text(['2026-10-01,a,food,100000000000000']),
    csv_text(['2026-10-01,a,food,1', '2026-10-01,a,food,1']),
    b'\xff',
    'date,account_id,category,amount_cents\n2026-10-01,a,food,1\x00\n',
])
def test_csv_rejects_malformed_or_duplicate_content(content):
    with pytest.raises(ValueError):
        analyze_transaction_csv(snapshot(content), now=NOW)


@pytest.mark.parametrize('changes', [
    {'currency': 'usd'},
    {'currency': 'USDX'},
    {'budgets': []},
    {'budgets': {'Food': 1}},
    {'budgets': {'food': True}},
    {'budgets': {'food': -1}},
    {'budgets': {f'cat{index}': 1 for index in range(65)}},
    {'source_ref': 'bad\n'},
    {'observed_at': '2026-10-25'},
    {'command': 'transfer'},
])
def test_csv_rejects_invalid_snapshot_fields(changes):
    content = csv_text(['2026-10-01,a,food,1'])
    with pytest.raises(ValueError):
        analyze_transaction_csv(snapshot(content, **changes), now=NOW)


def test_csv_rejects_non_text_content():
    with pytest.raises(ValueError):
        analyze_transaction_csv(snapshot(123), now=NOW)


def test_csv_stale_and_future_observations_are_unknown_but_still_validated():
    content = csv_text(['2026-10-01,acct-opaque,food,1'])
    for observed in (NOW - timedelta(hours=1), NOW + timedelta(minutes=1)):
        result = analyze_transaction_csv(
            snapshot(content, observed_at=observed.isoformat()),
            now=NOW,
            max_age_seconds=60,
        )
        assert result['status'] == 'unknown'
        assert result['row_count'] is None
        assert result['total_cents'] is None
        assert result['totals_by_month'] == []
        assert result['totals_by_category'] == []
        assert result['budget_variance'] == []
    with pytest.raises(ValueError):
        analyze_transaction_csv(
            snapshot('bad header',
                     observed_at=(NOW - timedelta(hours=1)).isoformat()),
            now=NOW,
            max_age_seconds=60,
        )


def test_csv_capability_registration_shape_and_handler():
    entries = capability_registrations()
    assert len(entries) == 1
    capability, handler = entries[0]
    assert capability.name == CAPABILITY_ID
    assert capability.name.endswith('.v1')
    now = datetime.now(timezone.utc)
    live = snapshot(
        csv_text(['2026-10-01,acct-opaque,food,1']),
        observed_at=now.isoformat(),
    )
    result = handler(CapabilityRequest(
        capability, {'snapshot': live}, requested_scope=None, rationale='test'
    ))
    assert result['status'] == 'reviewed' and result['effect'] == 'none'
    assert result['sdk_protocol'] == '1.0'
    for parameters in ({}, {'snapshot': live, 'unsafe': True}):
        with pytest.raises(ValueError):
            handler(CapabilityRequest(
                capability, parameters, requested_scope=None, rationale='test'
            ))
