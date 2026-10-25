"""MOD-PROJECT-FORGE: deterministic artifact review, no Core goal decisions.

Input manifests are untrusted. Only proposes corrections and evaluates supplied
review criteria; never asserts a genuine test run or publishes artifacts.
"""
from __future__ import annotations
from datetime import datetime,timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability,CapabilityRequest

MODULE_ID='MOD-PROJECT-FORGE'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='project_forge.review_artifact_manifest.v1'
PROFILE='ADVISORY'
RESOURCES=(('cpu_millicores',75),('ram_mib',48),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SHA=re.compile(r'^[0-9a-f]{64}$')
_FIELDS=frozenset({'source_ref','observed_at','project_ref','artifacts','criteria'})
_ART=frozenset({'artifact_id','digest_sha256','reviewed','test_result'})
_CRIT=frozenset({'criterion_id','artifact_id','met'})


def review_artifact_manifest(snapshot:Mapping[str,object],*,now:datetime,
                             max_age_seconds:int=86400)->dict[str,object]:
    if not isinstance(snapshot,Mapping) or set(snapshot)!=_FIELDS:
        raise ValueError('exact forge manifest required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=604800:
        raise ValueError('invalid freshness limit')
    source,project=snapshot['source_ref'],snapshot['project_ref']
    if any(not isinstance(v,str) or not _REF.fullmatch(v) for v in (source,project)):
        raise ValueError('invalid project reference')
    try: obs=datetime.fromisoformat(snapshot['observed_at'])
    except (TypeError,ValueError) as exc: raise ValueError('invalid observed_at') from exc
    if obs.tzinfo is None or obs.utcoffset() is None: raise ValueError('timestamp requires timezone')
    arts=snapshot['artifacts']; criteria=snapshot['criteria']
    if type(arts) is not list or not 1<=len(arts)<=32: raise ValueError('1..32 artifacts required')
    if type(criteria) is not list or not 1<=len(criteria)<=128:
        raise ValueError('1..128 acceptance criteria required')
    seen=set(); parts={}
    for item in arts:
        if not isinstance(item,Mapping) or set(item)!=_ART:raise ValueError('exact artifact fields required')
        key=item['artifact_id']
        if not isinstance(key,str) or not _REF.fullmatch(key) or key in seen:
            raise ValueError('invalid or duplicate artifact_id')
        seen.add(key)
        digest=item['digest_sha256']
        if not isinstance(digest,str) or not _SHA.fullmatch(digest):raise ValueError('invalid digest')
        if type(item['reviewed']) is not bool:raise ValueError('reviewed must be bool')
        if item['test_result'] not in ('passed','failed','unverified'):
            raise ValueError('invalid test_result')
        parts[key]=item
    seen_criteria=set(); by_art={key:[] for key in parts}
    for item in criteria:
        if not isinstance(item,Mapping) or set(item)!=_CRIT:raise ValueError('exact criterion fields required')
        key=item['criterion_id']; aid=item['artifact_id']
        if not isinstance(key,str) or not _REF.fullmatch(key) or key in seen_criteria:
            raise ValueError('invalid or duplicate criterion_id')
        seen_criteria.add(key)
        if aid not in parts:raise ValueError('criterion refers to unknown artifact')
        if type(item['met']) is not bool:raise ValueError('criterion met must be bool')
        by_art[aid].append((key,item['met']))
    age=(now.astimezone(timezone.utc)-obs.astimezone(timezone.utc)).total_seconds()
    freshness='future' if age < -5 else 'stale' if age>max_age_seconds else 'fresh'
    base={'schema':'sofia.project_forge.artifact_review.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
          'module_id':MODULE_ID,'source_ref':source,'project_ref':project,'freshness':freshness,
          'evidence_class':'supplied_unverified','effect':'none','artifacts_opened':False,
          'test_executed':False,'delivery_authorized':False,'core_goal_changed':False}
    if freshness!='fresh':return base|{'status':'unknown','artifacts':[],
                                      'candidate_ready_count':None,'all_acceptance_verified':False}
    reviewed=[]
    for aid,item in sorted(parts.items()):
        blockers=[]
        if not item['reviewed']: blockers.append('human_review_missing')
        if item['test_result']!='passed':blockers.append('test_evidence_unverified_or_failed')
        if not by_art[aid]:blockers.append('acceptance_criteria_missing')
        if any(not met for _,met in by_art[aid]):blockers.append('acceptance_criteria_unmet')
        reviewed.append({'artifact_id':aid,'digest_sha256':item['digest_sha256'],
                         'candidate_ready':not blockers,'blockers':blockers,
                         'criteria_met':sum(met for _,met in by_art[aid]),
                         'criteria_total':len(by_art[aid])})
    ready=sum(r['candidate_ready'] for r in reviewed)
    return base|{'status':'reviewed','artifacts':reviewed,'candidate_ready_count':ready,
                 'all_acceptance_verified':False,
                 'meaning_of_ready':'candidate review only; no trusted external attestations'}


def capability_registrations():
    c=Capability(CAPABILITY_ID,'Review supplied project artifacts without running work or changing Core goals.')
    def handle(req:CapabilityRequest):
        if not isinstance(req,CapabilityRequest) or req.capability!=c or set(req.parameters)!={'snapshot'}:
            raise ValueError('invalid forge request')
        return review_artifact_manifest(req.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((c,handle),)
