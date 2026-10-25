"""MOD-RESEARCH: interpret externally gathered claim evidence, never browse.

Source text, source age, authenticity and authorship are NOT independently
established by this module. Source authority remains with Platform admission.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID='MOD-RESEARCH'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='research.compare_claim_sources.v1'
PROFILE='ADVISORY'
RESOURCES=(('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS=frozenset({'source_ref','observed_at','claim_id','evidence'})
_EVIDENCE=frozenset({'evidence_id','origin_ref','published_at','stance','citation_ref'})
_STANCE=frozenset({'supports','disputes','uncertain'})


def _aware(value:object,label:str)->datetime:
    if not isinstance(value,str): raise ValueError('invalid '+label)
    try: t=datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('invalid '+label) from exc
    if t.tzinfo is None or t.utcoffset() is None: raise ValueError(label+' requires timezone')
    return t.astimezone(timezone.utc)


def compare_claim_sources(snapshot:Mapping[str,object],*,now:datetime,max_age_seconds:int=86400,
                          max_source_age_days:int=365)->dict[str,object]:
    if not isinstance(snapshot,Mapping) or set(snapshot)!=_FIELDS: raise ValueError('exact research snapshot required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=604800:
        raise ValueError('invalid snapshot age limit')
    if type(max_source_age_days) is not int or not 1<=max_source_age_days<=3650:
        raise ValueError('invalid source age limit')
    source,claim=snapshot['source_ref'],snapshot['claim_id']
    if any(not isinstance(v,str) or not _REF.fullmatch(v) for v in (source,claim)):
        raise ValueError('invalid reference')
    now=now.astimezone(timezone.utc)
    observed=_aware(snapshot['observed_at'],'observed_at')
    raw=snapshot['evidence']
    if type(raw) is not list or not 1<=len(raw)<=64: raise ValueError('1..64 evidence entries required')
    seen=set(); evidence=[]
    for item in raw:
        if not isinstance(item,Mapping) or set(item)!=_EVIDENCE: raise ValueError('exact evidence fields required')
        eid, origin, citation=item['evidence_id'],item['origin_ref'],item['citation_ref']
        if any(not isinstance(v,str) or not _REF.fullmatch(v) for v in (eid,origin,citation)) or eid in seen:
            raise ValueError('duplicate or invalid evidence reference')
        seen.add(eid)
        stance=item['stance']
        if not isinstance(stance,str) or stance not in _STANCE: raise ValueError('invalid stance')
        published=_aware(item['published_at'],'published_at')
        if published>observed+timedelta(seconds=5):
            raise ValueError('source publication after snapshot')
        evidence.append((eid,origin,citation,published,stance))
    age=(now-observed).total_seconds()
    freshness='future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base={'schema':'sofia.research.claim_review.v1','module_id':MODULE_ID,'sdk_protocol':str(SDK_PROTOCOL_VERSION),
          'source_ref':source,'claim_id':claim,'freshness':freshness,'effect':'none',
          'evidence_class':'supplied_unverified','external_requests_sent':False,
          'claims_fact_checked':False,'source_authenticity_verified':False}
    if freshness!='fresh':
        return base|{'status':'unknown','stance_counts':{},'source_count':None,
                     'older_source_refs':[],'conflicting_stances':False,'review_items':[]}
    counts=dict.fromkeys(sorted(_STANCE),0); sources=set(); older=[]; reviewed=[]
    for eid,origin,citation,published,stance in evidence:
        counts[stance]+=1; sources.add(origin)
        if (now-published).total_seconds()>max_source_age_days*86400: older.append(eid)
        reviewed.append({'evidence_id':eid,'citation_ref':citation,'stance':stance,
                         'source_age_days':max(0,int((now-published).total_seconds()//86400))})
    contradiction=counts['supports']>0 and counts['disputes']>0
    return base|{'status':'reviewed', 'stance_counts':counts,'source_count':len(sources),
                 'older_source_refs':sorted(older),'conflicting_stances':contradiction,
                 'review_items':sorted(reviewed,key=lambda item:item['evidence_id']),
                 'finding':'mixed_supplied_stances' if contradiction else 'no_supplied_contradiction'}


def capability_registrations():
    c=Capability(CAPABILITY_ID,'Compare supplied source stances without autonomous browsing or truth claims.')
    def handle(req:CapabilityRequest):
        if not isinstance(req,CapabilityRequest) or req.capability!=c or set(req.parameters)!={'snapshot'}:
            raise ValueError('invalid research request')
        return compare_claim_sources(req.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((c,handle),)
