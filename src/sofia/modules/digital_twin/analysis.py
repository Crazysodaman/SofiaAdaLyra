"""MOD-DIGITAL-TWIN: compare bounded hypothetical scenario result projections.

The authoritative graph simulator stays with sofia.platform.ops.digital_twin.
These *supplied* projections are not authenticated Platform receipts or live faults.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-DIGITAL-TWIN'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'digital_twin.compare_scenarios.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref','observed_at','critical_host_ids','scenarios'})
_SCENARIO_FIELDS = frozenset({'scenario_id','initial_host_id','affected_host_ids','fidelity','outcome'})


def _ids(items: object, label: str, limit: int) -> tuple[str, ...]:
    if type(items) is not list or len(items)>limit or any(not isinstance(v,str) or not _REF.fullmatch(v) for v in items):
        raise ValueError(f'invalid {label}')
    if len(items) != len(set(items)):
        raise ValueError(f'duplicate {label}')
    return tuple(items)


def compare_scenarios(snapshot: Mapping[str, object], *, now: datetime,
                      max_age_seconds: int = 3600) -> dict[str, object]:
    if not isinstance(snapshot,Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact scenario snapshot fields required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source,str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    try: observed = datetime.fromisoformat(snapshot['observed_at'])
    except (TypeError,ValueError) as exc: raise ValueError('invalid timestamp') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('timestamp must include timezone')
    age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    critical = set(_ids(snapshot['critical_host_ids'], 'critical_host_ids', 64))
    scenarios = snapshot['scenarios']
    if type(scenarios) is not list or not 1 <= len(scenarios) <= 24:
        raise ValueError('scenarios must include 1..24 results')
    reviewed = []
    seen = set()
    for item in scenarios:
        if not isinstance(item,Mapping) or set(item) != _SCENARIO_FIELDS:
            raise ValueError('invalid scenario fields')
        sid, initial = item['scenario_id'], item['initial_host_id']
        if not all(isinstance(v,str) and _REF.fullmatch(v) for v in (sid,initial)) or sid in seen:
            raise ValueError('invalid or duplicate scenario id')
        seen.add(sid)
        affected = _ids(item['affected_host_ids'], 'affected_host_ids', 64)
        if initial not in affected:
            raise ValueError('scenario origin must be affected')
        if item['fidelity'] != 'dependency_graph_v1' or item['outcome'] != 'modeled_only':
            raise ValueError('unsupported scenario fidelity or outcome')
        reviewed.append((sid, affected))
    base = {'schema':'sofia.digital_twin.scenario_comparison.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
            'module_id':MODULE_ID,'source_ref':source,'freshness':freshness,
            'evidence_class':'hypothetical_supplied_unverified','effect':'none',
            'real_outage_verified':False, 'platform_receipt_verified':False}
    if freshness != 'fresh':
        return base | {'status':'unknown','ranking':[], 'findings':['scenario_snapshot_timestamp_invalid']}
    ranking = []
    for sid, affected in reviewed:
        overlap = sorted(critical.intersection(affected))
        ranking.append({'scenario_id':sid, 'affected_host_count':len(affected),
                        'critical_hosts_affected':overlap,'critical_count':len(overlap)})
    ranking.sort(key=lambda x:(-x['critical_count'],-x['affected_host_count'],x['scenario_id']))
    return base | {'status':'compared_simulated','ranking':ranking,'findings':[]}


def capability_registrations():
    capability=Capability(CAPABILITY_ID,'Rank supplied hypothetical Fleet dependency-simulation outputs; no host changes.')
    def handler(request:CapabilityRequest):
        if request.capability!=capability or set(request.parameters)!={'snapshot'}:
            raise ValueError('invalid digital twin capability request')
        return compare_scenarios(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability,handler),)
