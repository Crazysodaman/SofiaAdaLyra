"""MOD-CALENDAR: event-ID-only conflict review; no provider, attendee or location access."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-CALENDAR'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'calendar.review_schedule_conflicts.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 48), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref','observed_at','events'})
_EVENT_FIELDS = frozenset({'event_id','start_at','end_at','busy'})


def _datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError('invalid ' + field)
    try: t = datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('invalid ' + field) from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('timezone required for ' + field)
    return t.astimezone(timezone.utc)


def review_schedule_conflicts(snapshot: Mapping[str, object], *, now: datetime,
                              max_age_seconds: int = 900) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact calendar snapshot fields required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid freshness limit')
    source = snapshot['source_ref']
    if not isinstance(source,str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _datetime(snapshot['observed_at'],'observed_at')
    raw_events = snapshot['events']
    if type(raw_events) is not list or len(raw_events) > 128:
        raise ValueError('events must be bounded list')
    events = []
    ids = set()
    for event in raw_events:
        if not isinstance(event, Mapping) or set(event) != _EVENT_FIELDS:
            raise ValueError('invalid event structure')
        eid = event['event_id']
        if not isinstance(eid, str) or not _REF.fullmatch(eid) or eid in ids:
            raise ValueError('invalid or duplicate event id')
        ids.add(eid)
        start = _datetime(event['start_at'], 'start_at')
        end = _datetime(event['end_at'], 'end_at')
        if end <= start or (end-start).total_seconds() > 31*86400:
            raise ValueError('invalid or excessive event duration')
        if type(event['busy']) is not bool:
            raise ValueError('busy must be boolean')
        events.append((start,end,eid,event['busy']))
    age = (now.astimezone(timezone.utc)-observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema':'sofia.calendar.conflict_review.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
            'module_id':MODULE_ID,'source_ref':source,'freshness':freshness,
            'evidence_class':'supplied_unverified','effect':'none',
            'events_modified':False,'invitations_sent':False,'private_contents_returned':False}
    if freshness != 'fresh':
        return base | {'status':'unknown','event_count':None,'busy_event_count':None,'conflicts':[]}
    busy = sorted((start,end,eid) for start,end,eid,is_busy in events if is_busy)
    # Half-open intervals: adjacent events are not conflicts. Deterministic opaque ID pairs.
    conflicts = []
    for index,(start,end,eid) in enumerate(busy):
        for other_start,other_end,other_id in busy[index+1:]:
            if other_start >= end: break
            if other_end > start:
                conflicts.append({'event_ids':sorted((eid,other_id)),
                                  'overlap_seconds':int((min(end,other_end)-max(start,other_start)).total_seconds())})
    conflicts.sort(key=lambda c:(c['event_ids'][0],c['event_ids'][1]))
    return base | {'status':'reviewed','event_count':len(events),
                   'busy_event_count':len(busy),'conflicts':conflicts}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Review opaque event-ID scheduling overlaps; no provider calls or invitations.')
    def handler(request:CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid calendar capability request')
        return review_schedule_conflicts(request.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((capability,handler),)
