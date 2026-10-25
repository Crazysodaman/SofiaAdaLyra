"""Review fictional railroad blocks and switch alignment, no JMRI action.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No real-world effects, authorized execution, persistence or identity assertions.
Existing Sofía V18 owner components retain control of all real operations.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-TRAINS'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'trains.review_route_projection.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))  # provisional admission request
_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid '+label)
    return value


def _exact(item: object, keys: tuple[str, ...]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != set(keys):
        raise ValueError('unexpected fields in supplied projection')
    return item


def _num(value: object, lo: float, hi: float, name: str = 'number') -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError('invalid '+name)
    return float(value)


def _int(value: object, lo: int, hi: int, name: str = 'integer') -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('invalid '+name)
    return value


def _bool(value: object, name: str = 'flag') -> bool:
    if type(value) is not bool:
        raise ValueError('invalid '+name)
    return value


def _choice(value: object, options: tuple[str, ...], label: str = 'choice') -> str:
    if type(value) is not str or value not in options:
        raise ValueError('invalid '+label)
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    try: date = datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('invalid timestamp') from exc
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError('timestamp requires timezone')
    return date.astimezone(timezone.utc)


def _base(snapshot: Mapping[str, object], now: datetime, max_age_seconds: int):
    _exact(snapshot, ('source_ref', 'observed_at', 'items'))
    _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    age = (now.astimezone(timezone.utc)-observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    items = snapshot['items']
    if type(items) is not list or len(items) > 128:
        raise ValueError('items must be a bounded list')
    return items, observed, freshness

def _review(item: Mapping[str, object]) -> dict[str, object]:
    row=_exact(item,('id','blocks','occupied_blocks','turnouts_aligned','power_state'))
    key=_identity(row['id']); blocks=row['blocks']; occupied=row['occupied_blocks']
    if type(blocks) is not list or not 1<=len(blocks)<=32 or any(not isinstance(v,str) or not _ID.fullmatch(v) for v in blocks) or len(set(blocks))!=len(blocks):
        raise ValueError('invalid route blocks')
    if type(occupied) is not list or any(not isinstance(v,str) or v not in blocks for v in occupied) or len(set(occupied))!=len(occupied):
        raise ValueError('invalid occupied blocks')
    aligned=_bool(row['turnouts_aligned']); power=_choice(row['power_state'],('on','off','unknown'))
    reasons=(['occupied_route'] if occupied else []) + (['turnout_alignment_unverified'] if not aligned else []) + (['power_not_confirmed'] if power!='on' else [])
    return dict(id=key, finding='hypothetically_clear' if not reasons else 'hypothetically_blocked', blocked_by=reasons, live_route_clearance_verified=False)



def review_trains(snapshot: Mapping[str, object], *, now: datetime,
              max_age_seconds: int = 3600) -> dict[str, object]:
    items, observed, freshness = _base(snapshot, now, max_age_seconds)
    results = [_review(item) for item in items]
    ids = [r['id'] for r in results]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate item identity')
    # In the fictional simulation, sharing a route block is never clear.
    original=snapshot['items']
    for left_index, left in enumerate(results):
        for right_index in range(left_index+1,len(results)):
            right=results[right_index]
            if set(original[left_index]['blocks']) & set(original[right_index]['blocks']):
                for record in (left,right):
                    record['finding']='hypothetically_blocked'
                    if 'competing_route_blocks' not in record['blocked_by']:
                        record['blocked_by'].append('competing_route_blocks')
    findings = sorted({r['finding'] for r in results})
    base = dict(schema='sofia.trains.projection_review.v1', module_id=MODULE_ID, sdk_protocol=str(SDK_PROTOCOL_VERSION),
                source_ref=snapshot['source_ref'], observed_at=observed.isoformat(),
                freshness=freshness, evidence_class='supplied_unverified', effect='none',
                action_authorized=False, data_persisted=False)
    if freshness != 'fresh':
        return base | dict(status='unknown', inspected_count=None, findings=['snapshot_timestamp_invalid'], results=[])
    return base | dict(status='reviewed', inspected_count=len(results), findings=findings, results=results)


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Review fictional railroad blocks and switch alignment, no JMRI action.')
    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return review_trains(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
