"""MOD-DATA-ANALYTICS: deterministic aggregate-only numeric table analysis.

No filesystem, SQL, Python evaluation, chart rendering, arbitrary user code or
raw-row echo. Supplied rows have unverified provenance and need Platform admission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
import statistics
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-DATA-ANALYTICS'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'data_analytics.summarize_numeric.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 100), ('ram_mib', 64), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_COLUMN = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'columns', 'rows'})


def summarize_numeric(snapshot: Mapping[str, object], *, now: datetime,
                      max_age_seconds: int = 86400) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact numeric table required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    try:
        observed = datetime.fromisoformat(snapshot['observed_at'])
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid observed_at') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('timezone required')
    columns = snapshot['columns']
    rows = snapshot['rows']
    if type(columns) is not list or not 1 <= len(columns) <= 8 or any(
        not isinstance(k, str) or not _COLUMN.fullmatch(k) for k in columns
    ) or len(set(columns)) != len(columns):
        raise ValueError('invalid numeric column identifiers')
    if type(rows) is not list or not 1 <= len(rows) <= 512:
        raise ValueError('numeric rows must be bounded nonempty list')
    samples: dict[str, list[float]] = {k: [] for k in columns}
    missing = dict.fromkeys(columns, 0)
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != set(columns):
            raise ValueError('numeric row fields do not match columns')
        for key in columns:
            val = row[key]
            if val is None:
                missing[key] += 1
            elif type(val) not in (int, float) or not math.isfinite(val) or abs(val) > 1e12:
                raise ValueError('invalid finite numeric value')
            else:
                samples[key].append(float(val))
    age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.data_analytics.numeric_summary.v1',
            'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'module_id': MODULE_ID,
            'source_ref': source, 'freshness': freshness,
            'evidence_class': 'supplied_unverified', 'effect': 'none',
            'raw_rows_returned': False, 'data_persisted': False}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'row_count': None, 'statistics': {}}
    stats = {}
    for key in columns:
        nums = samples[key]
        stats[key] = {
            'count': len(nums), 'missing': missing[key],
            'mean': statistics.fmean(nums) if nums else None,
            'median': statistics.median(nums) if nums else None,
            'minimum': min(nums) if nums else None, 'maximum': max(nums) if nums else None,
            'sample_stddev': statistics.stdev(nums) if len(nums) > 1 else None,
        }
    return base | {'status': 'summarized', 'row_count': len(rows), 'statistics': stats}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Summarize supplied bounded numeric rows without storing or returning raw rows.')
    def handler(request: CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid data analytics capability request')
        return summarize_numeric(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
