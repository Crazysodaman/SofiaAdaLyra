"""MOD-FILE-WATCH: advisory summarizer for supplied Platform file-change records.

Never opens files, crawls directories, or executes an event-driven workflow.
In particular, sensitive paths are counted but not repeated in responses.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-FILE-WATCH'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'file_watch.summarize_changes.v1'
PROFILE = 'OBSERVE'
RESOURCES = (('cpu_millicores',50),('ram_mib',32),('gpu_mib',0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref','observed_at','root_ref','events'})
_EVENT_FIELDS = frozenset({'path','kind','is_directory'})
_TYPES = frozenset({'created','modified','deleted','renamed'})
_SENSITIVE = frozenset({'.env','.ssh','.gnupg','.aws','.azure','id_rsa','id_ed25519',
                        'secrets','secrets.json','credentials','credentials.json','private.key'})


def _relative(value: object) -> str:
    if not isinstance(value,str) or not 1 <= len(value) <= 240 or '\\' in value or '\0' in value:
        raise ValueError('invalid portable relative file path')
    p, w = PurePosixPath(value), PureWindowsPath(value)
    if not p.parts or p.is_absolute() or w.is_absolute() or w.drive or '..' in p.parts or '.' in p.parts or p.as_posix()!=value:
        raise ValueError('file path must be normalized and within approved root')
    if any(part in ('', '.', '..') or any(ord(c)<32 for c in part) for part in p.parts):
        raise ValueError('invalid file path component')
    return value


def summarize_changes(snapshot: Mapping[str,object], *, now:datetime,
                      max_age_seconds:int=600)->dict[str,object]:
    if not isinstance(snapshot,Mapping) or set(snapshot)!=_FIELDS:
        raise ValueError('exact change snapshot fields required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError('invalid freshness bound')
    for k in ('source_ref','root_ref'):
        v=snapshot[k]
        if not isinstance(v,str) or not _REF.fullmatch(v):
            raise ValueError('invalid '+k)
    try: observed=datetime.fromisoformat(snapshot['observed_at'])
    except (ValueError,TypeError) as exc: raise ValueError('invalid timestamp') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('observed_at must be timezone-aware')
    age=(now.astimezone(timezone.utc)-observed.astimezone(timezone.utc)).total_seconds()
    freshness='future' if age < -5 else 'stale' if age>max_age_seconds else 'fresh'
    events=snapshot['events']
    if type(events) is not list or len(events)>256:
        raise ValueError('events must be bounded list')
    counts={kind:0 for kind in sorted(_TYPES)}
    directory_count=0
    sensitive=0
    reviewed=[]
    for event in events:
        if not isinstance(event,Mapping) or set(event)!=_EVENT_FIELDS:
            raise ValueError('invalid change event')
        path=_relative(event['path'])
        kind=event['kind']
        if kind not in _TYPES or type(event['is_directory']) is not bool:
            raise ValueError('invalid change event type')
        hidden=any(part.lower() in _SENSITIVE or part.lower().endswith(('.pem','.key','.pfx'))
                   for part in PurePosixPath(path).parts)
        if hidden: sensitive+=1
        counts[kind]+=1
        directory_count+=int(event['is_directory'])
        if not hidden:
            reviewed.append({'path':path,'kind':kind,'is_directory':event['is_directory']})
    base={'schema':'sofia.file_watch.advisory.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
          'module_id':MODULE_ID,'source_ref':snapshot['source_ref'],
          'root_ref':snapshot['root_ref'],'freshness':freshness,
          'evidence_class':'supplied_unverified','effect':'none','workflow_triggered':False}
    if freshness!='fresh':
        return base|{'status':'unknown','counts':None,'visible_events':[],
                     'redacted_sensitive_count':None,'findings':['observation_timestamp_invalid']}
    return base|{'status':'observed_supplied','counts':counts,'directory_events':directory_count,
                 'visible_events':reviewed,'redacted_sensitive_count':sensitive,
                 'findings':['sensitive_paths_redacted'] if sensitive else []}


def capability_registrations():
    capability=Capability(CAPABILITY_ID,'Summarize a reviewed-root file change feed; no filesystem access or triggers.')
    def handler(request:CapabilityRequest):
        if request.capability!=capability or set(request.parameters)!={'snapshot'}:
            raise ValueError('invalid file-watch capability request')
        return summarize_changes(request.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((capability,handler),)
