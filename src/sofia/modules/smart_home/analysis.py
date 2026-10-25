"""MOD-SMART-HOME: non-actuating audit of bounded Home Assistant state projections.

Locks, cameras, alarms and doors are NOT authorized to actuate via this module.
Unverified, stale or absent telemetry never establishes a physical device state.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID='MOD-SMART-HOME'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='smart_home.review_entities.v1'
PROFILE='OBSERVE'
RESOURCES=(('cpu_millicores',50),('ram_mib',32),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_ENTITY=re.compile(r'^(?:light|switch|sensor|binary_sensor|climate|lock|alarm_control_panel|camera|cover|fan)\.[a-z0-9_]{1,80}$')
_FIELDS=frozenset({'source_ref','observed_at','entities'})
_ENTITY_FIELDS=frozenset({'entity_id','state','last_changed','expected_state'})
_PROTECTED=frozenset({'lock','alarm_control_panel','camera','cover'})
_UNKNOWN=frozenset({'unknown','unavailable','none'})


def _timestamp(value:object, label:str)->datetime:
    try: t=datetime.fromisoformat(value)
    except (ValueError,TypeError) as exc: raise ValueError('invalid '+label) from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(label+' requires timezone')
    return t.astimezone(timezone.utc)


def review_entities(snapshot:Mapping[str,object],*,now:datetime,max_age_seconds:int=600)->dict[str,object]:
    if not isinstance(snapshot,Mapping) or set(snapshot)!=_FIELDS:
        raise ValueError('exact entity observation fields required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError('invalid freshness bound')
    source=snapshot['source_ref']
    if not isinstance(source,str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed=_timestamp(snapshot['observed_at'],'observed_at')
    age=(now.astimezone(timezone.utc)-observed).total_seconds()
    freshness='future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    entities=snapshot['entities']
    if type(entities) is not list or len(entities)>128:
        raise ValueError('entities must be bounded list')
    inspected=[]
    seen=set()
    for entity in entities:
        if not isinstance(entity,Mapping) or set(entity)!=_ENTITY_FIELDS:
            raise ValueError('invalid entity projection')
        eid=entity['entity_id']
        if not isinstance(eid,str) or not _ENTITY.fullmatch(eid) or eid in seen:
            raise ValueError('invalid or duplicate entity_id')
        seen.add(eid)
        state=entity['state']
        expected=entity['expected_state']
        if not isinstance(state,str) or not 1<=len(state)<=64 or any(ord(c)<32 for c in state):
            raise ValueError('invalid state')
        if expected is not None and (not isinstance(expected,str) or not 1<=len(expected)<=64
                                     or any(ord(c)<32 for c in expected)):
            raise ValueError('invalid expected state')
        last=_timestamp(entity['last_changed'],'last_changed')
        delta=(now.astimezone(timezone.utc)-last).total_seconds()
        domain=eid.split('.',1)[0]
        protected=domain in _PROTECTED
        # A quiet device can retain its last_changed for months. Last changed is NOT telemetry freshness.
        # Only invalid future timestamps and unknown states are flagged; snapshot age governs freshness.
        invalid_time=delta < -5 or last > observed + timedelta(seconds=5)
        issue='timestamp_inconsistent' if invalid_time else ('unavailable' if state.lower() in _UNKNOWN else
              'expected_state_mismatch' if expected is not None and expected != state else None)
        inspected.append({'entity_id':eid,'domain':domain,'protected':protected,
                          'reported_state':state if not protected else '[redacted_protected_domain]',
                          'issue':issue})
    base={'schema':'sofia.smart_home.advisory.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
          'module_id':MODULE_ID,'source_ref':source,'freshness':freshness,
          'evidence_class':'supplied_unverified','effect':'none',
          'devices_controlled':False,'physical_state_verified':False}
    if freshness!='fresh':
        return base|{'status':'unknown','entities':[], 'findings':['snapshot_timestamp_invalid']}
    return base|{'status':'reported_states_reviewed', 'entities':inspected,
                'findings':sorted({item['issue'] for item in inspected if item['issue']})}


def capability_registrations():
    capability=Capability(CAPABILITY_ID,'Inspect supplied HA entity states; no service calls, locks or alarm operations.')
    def handler(request:CapabilityRequest):
        if request.capability!=capability or set(request.parameters)!={'snapshot'}:
            raise ValueError('invalid smart-home capability request')
        return review_entities(request.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((capability,handler),)
