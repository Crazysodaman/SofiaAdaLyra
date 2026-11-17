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
TIMETABLE_CAPABILITY_ID = 'trains.validate_timetable.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))  # provisional admission request
_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_TIMETABLE_FIELDS = frozenset({'source_ref', 'observed_at', 'services', 'turnouts', 'occupancies'})
_SERVICE_FIELDS = frozenset({'service_id', 'route_blocks', 'turnout_requirements',
                             'scheduled_departure_s', 'scheduled_arrival_s'})
_REQUIREMENT_FIELDS = frozenset({'turnout_id', 'required_position'})
_TURNOUT_FIELDS = frozenset({'turnout_id', 'position'})
_OCCUPANCY_FIELDS = frozenset({'block_id', 'state'})


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


def _id_list(value: object, label: str, low: int, high: int) -> list[str]:
    if type(value) is not list or not low <= len(value) <= high:
        raise ValueError(f'invalid {label}')
    if any(not isinstance(item, str) or _ID.fullmatch(item) is None for item in value):
        raise ValueError(f'invalid {label}')
    if len(set(value)) != len(value):
        raise ValueError(f'duplicate {label}')
    return value


def validate_timetable(snapshot: Mapping[str, object], *, now: datetime,
                       max_age_seconds: int = 3600) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _TIMETABLE_FIELDS:
        raise ValueError('timetable snapshot requires exact fields')
    _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    services = snapshot['services']
    if type(services) is not list or not 1 <= len(services) <= 64:
        raise ValueError('services must be a bounded non-empty list')
    checked_services = []
    service_ids: set[str] = set()
    for item in services:
        row = _exact(item, tuple(_SERVICE_FIELDS))
        service_id = _identity(row['service_id'], 'service_id')
        if service_id in service_ids:
            raise ValueError('duplicate service identity')
        service_ids.add(service_id)
        blocks = _id_list(row['route_blocks'], 'route blocks', 1, 32)
        requirements = row['turnout_requirements']
        if type(requirements) is not list or len(requirements) > 16:
            raise ValueError('turnout requirements must be a bounded list')
        checked_requirements = []
        requirement_ids: set[str] = set()
        for requirement in requirements:
            req = _exact(requirement, tuple(_REQUIREMENT_FIELDS))
            turnout_id = _identity(req['turnout_id'], 'turnout_id')
            if turnout_id in requirement_ids:
                raise ValueError('duplicate turnout requirement')
            requirement_ids.add(turnout_id)
            required = _choice(req['required_position'], ('normal', 'reverse'),
                               'required_position')
            checked_requirements.append((turnout_id, required))
        departure = _int(row['scheduled_departure_s'], 0, 604800, 'scheduled_departure_s')
        arrival = _int(row['scheduled_arrival_s'], 0, 604800, 'scheduled_arrival_s')
        if arrival <= departure:
            raise ValueError('scheduled arrival must follow departure')
        checked_services.append((service_id, blocks, checked_requirements, departure, arrival))
    turnouts = snapshot['turnouts']
    if type(turnouts) is not list or len(turnouts) > 64:
        raise ValueError('turnouts must be a bounded list')
    turnout_positions: dict[str, str] = {}
    for item in turnouts:
        row = _exact(item, tuple(_TURNOUT_FIELDS))
        turnout_id = _identity(row['turnout_id'], 'turnout_id')
        if turnout_id in turnout_positions:
            raise ValueError('duplicate turnout identity')
        turnout_positions[turnout_id] = _choice(row['position'], ('normal', 'reverse', 'unknown'),
                                                'turnout position')
    occupancies = snapshot['occupancies']
    if type(occupancies) is not list or len(occupancies) > 128:
        raise ValueError('occupancies must be a bounded list')
    occupancy_states: dict[str, str] = {}
    for item in occupancies:
        row = _exact(item, tuple(_OCCUPANCY_FIELDS))
        block_id = _identity(row['block_id'], 'block_id')
        if block_id in occupancy_states:
            raise ValueError('duplicate occupancy identity')
        occupancy_states[block_id] = _choice(row['state'], ('occupied', 'clear', 'unknown'),
                                             'occupancy state')
    observed = _timestamp(snapshot['observed_at'])
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = dict(schema='sofia.trains.timetable_validation.v1', module_id=MODULE_ID,
                sdk_protocol=str(SDK_PROTOCOL_VERSION), source_ref=snapshot['source_ref'],
                observed_at=observed.isoformat(), freshness=freshness,
                evidence_class='supplied_unverified', effect='none',
                simulation_only=True, action_authorized=False,
                jmri_contacted=False, live_route_clearance_verified=False)
    if freshness != 'fresh':
        return base | dict(status='unknown', service_count=None, services=[],
                           findings=['snapshot_timestamp_invalid'])
    reasons_by_service: dict[str, set[str]] = {row[0]: set() for row in checked_services}
    missing_turnout_refs: set[str] = set()
    for service_id, blocks, requirements, _, _ in checked_services:
        reasons = reasons_by_service[service_id]
        for block in blocks:
            state = occupancy_states.get(block)
            if state == 'occupied':
                reasons.add('route_occupied')
            elif state is None or state == 'unknown':
                reasons.add('route_occupancy_unknown')
        for turnout_id, required in requirements:
            actual = turnout_positions.get(turnout_id)
            if actual is None:
                missing_turnout_refs.add(turnout_id)
                reasons.add('turnout_state_unknown')
            elif actual == 'unknown':
                reasons.add('turnout_state_unknown')
            elif actual != required:
                reasons.add('turnout_misaligned')
    for left_index, left in enumerate(checked_services):
        for right in checked_services[left_index + 1:]:
            if (set(left[1]) & set(right[1])
                    and max(left[3], right[3]) < min(left[4], right[4])):
                reasons_by_service[left[0]].add('timetable_conflict')
                reasons_by_service[right[0]].add('timetable_conflict')
    results = []
    all_findings: set[str] = set()
    for service_id, blocks, _, departure, arrival in checked_services:
        reasons = reasons_by_service[service_id]
        if 'timetable_conflict' in reasons:
            status = 'hypothetically_conflicted'
        elif reasons & {'route_occupied', 'turnout_misaligned'}:
            status = 'hypothetically_blocked'
        elif reasons:
            status = 'unknown'
        else:
            status = 'hypothetically_clear'
        all_findings.update(reasons)
        results.append(dict(service_id=service_id, status=status,
                            blocked_by=sorted(reasons), route_block_count=len(blocks),
                            scheduled_departure_s=departure,
                            scheduled_arrival_s=arrival,
                            live_clearance_verified=False))
    if missing_turnout_refs:
        all_findings.add('turnout_reference_missing')
    return base | dict(status='validated', service_count=len(results), services=results,
                       missing_turnout_refs=sorted(missing_turnout_refs),
                       findings=sorted(all_findings))


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Review fictional railroad blocks and switch alignment, no JMRI action.')
    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return review_trains(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    validator = Capability(TIMETABLE_CAPABILITY_ID,
                           'Validate supplied timetable, turnout and occupancy consistency without JMRI access.')
    def validator_handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != validator
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid timetable capability request')
        return validate_timetable(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler), (validator, validator_handler))
