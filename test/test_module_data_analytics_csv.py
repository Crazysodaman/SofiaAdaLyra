"""Bounded numeric CSV statistics tests. No filesystem or network access."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.data_analytics.parsing import (
    CAPABILITY_ID,
    MAX_CSV_BYTES,
    MAX_CSV_COLUMNS,
    MAX_CSV_ROWS,
    capability_registrations,
    summarize_numeric_csv,
)
from sofia.platform.capability.model import CapabilityRequest

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def snapshot(content, **changes):
    return {
        'source_ref': 'dataset:supplied',
        'observed_at': NOW.isoformat(),
        'content': content,
    } | changes


def table(rows, header='value'):
    return header + '\n' + '\n'.join(rows) + '\n'


def test_csv_summary_matches_numeric_contract():
    content = 'voltage,current\n1,2\n3,\n5,4\n'
    result = summarize_numeric_csv(snapshot(content), now=NOW)
    assert result['status'] == 'summarized'
    assert result['row_count'] == 3
    assert result['statistics']['voltage'] == {
        'count': 3, 'missing': 0, 'mean': 3.0, 'median': 3.0,
        'minimum': 1.0, 'maximum': 5.0, 'sample_stddev': 2.0,
    }
    assert result['statistics']['current']['count'] == 2
    assert result['statistics']['current']['missing'] == 1
    assert result['statistics']['current']['mean'] == 3.0
    assert result['statistics']['current']['median'] == 3.0
    assert result['raw_rows_returned'] is False
    assert result['data_persisted'] is False
    assert result['effect'] == 'none'
    assert 'rows' not in result
    assert result['content_bytes'] == len(content.encode('utf-8'))


def test_csv_accepts_bytes_and_exact_limits():
    rows = [str(index) for index in range(MAX_CSV_ROWS)]
    content = table(rows).encode('utf-8')
    result = summarize_numeric_csv(snapshot(content), now=NOW)
    assert result['row_count'] == MAX_CSV_ROWS
    assert result['statistics']['value']['count'] == MAX_CSV_ROWS
    columns = ','.join(f'c{index}' for index in range(MAX_CSV_COLUMNS))
    values = ','.join('1' for _ in range(MAX_CSV_COLUMNS))
    result = summarize_numeric_csv(snapshot(columns + '\n' + values + '\n'), now=NOW)
    assert set(result['statistics']) == set(columns.split(','))


@pytest.mark.parametrize('content', [
    '',
    'value\n',
    'value,value\n1,2\n',
    '1value\n1\n',
    'bad name\n1\n',
    'a,b\n1\n',
    'a,b\n1,2,3\n',
    'a\nabc\n',
    'a\nnan\n',
    'a\ninf\n',
    'a\n-inf\n',
    'a\n1e999\n',
    'a\n0x10\n',
    'a\n 1\n',
    b'\xff',
    'a\n1\x00\n',
])
def test_csv_rejects_malformed_or_unsafe_content(content):
    with pytest.raises(ValueError):
        summarize_numeric_csv(snapshot(content), now=NOW)


def test_csv_rejects_row_column_and_byte_overflow():
    rows = [str(index) for index in range(MAX_CSV_ROWS + 1)]
    with pytest.raises(ValueError, match='limit'):
        summarize_numeric_csv(snapshot(table(rows)), now=NOW)
    columns = ','.join(f'c{index}' for index in range(MAX_CSV_COLUMNS + 1))
    with pytest.raises(ValueError, match='column'):
        summarize_numeric_csv(snapshot(columns + '\n' + '1,2,3,4,5,6,7,8,9\n'), now=NOW)
    with pytest.raises(ValueError, match='size'):
        summarize_numeric_csv(snapshot(b'x' * (MAX_CSV_BYTES + 1)), now=NOW)


@pytest.mark.parametrize('changes', [
    {'source_ref': 'bad\n'},
    {'observed_at': '2026-10-25'},
    {'export_file': True},
])
def test_csv_rejects_invalid_snapshot_fields(changes):
    with pytest.raises(ValueError):
        summarize_numeric_csv(snapshot(table(['1']), **changes), now=NOW)


def test_csv_rejects_non_text_content():
    with pytest.raises(ValueError):
        summarize_numeric_csv(snapshot(123), now=NOW)


def test_csv_stale_and_future_observations_mask_statistics():
    content = table(['1', '2', '3'])
    for observed in (NOW - timedelta(hours=1), NOW + timedelta(minutes=1)):
        result = summarize_numeric_csv(
            snapshot(content, observed_at=observed.isoformat()),
            now=NOW,
            max_age_seconds=60,
        )
        assert result['status'] == 'unknown'
        assert result['row_count'] is None
        assert result['statistics'] == {}


def test_csv_capability_registration_shape_and_handler():
    entries = capability_registrations()
    assert len(entries) == 1
    capability, handler = entries[0]
    assert capability.name == CAPABILITY_ID
    assert capability.name.endswith('.v1')
    now = datetime.now(timezone.utc)
    live = snapshot(table(['1']), observed_at=now.isoformat())
    result = handler(CapabilityRequest(
        capability, {'snapshot': live}, requested_scope=None, rationale='test'
    ))
    assert result['status'] == 'summarized' and result['effect'] == 'none'
    assert result['sdk_protocol'] == '1.0'
    for parameters in ({}, {'snapshot': live, 'unsafe': True}):
        with pytest.raises(ValueError):
            handler(CapabilityRequest(
                capability, parameters, requested_scope=None, rationale='test'
            ))
