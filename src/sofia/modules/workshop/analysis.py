"""MOD-WORKSHOP: review a supplied disposable VM experiment plan only.

Hephaestus provisioning, isolation verification, host capabilities, enrollment
and any live actions remain with the Platform workshop supervisor.
"""
from __future__ import annotations
from datetime import datetime,timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability,CapabilityRequest

MODULE_ID='MOD-WORKSHOP'
MODULE_VERSION='0.1.0'
CAPABILITY_ID='workshop.review_experiment_plan.v1'
PROFILE='ADVISORY'
RESOURCES=(('cpu_millicores',75),('ram_mib',48),('gpu_mib',0))
_REF=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS=frozenset({'source_ref','observed_at','experiment_id','host_class','network_mode',
                   'disk_gib','memory_mib','vcpus','steps','destruction_reviewed'})
_STEPS=frozenset({'prepare_image','verify_isolation','snapshot_clean','run_offline_tests',
                  'collect_sanitized_results','destroy_disposable_guest'})
_SEQUENCE=('prepare_image','verify_isolation','snapshot_clean','run_offline_tests',
           'collect_sanitized_results','destroy_disposable_guest')


def review_experiment_plan(plan:Mapping[str,object],*,now:datetime,
                           max_age_seconds:int=86400)->dict[str,object]:
    if not isinstance(plan,Mapping) or set(plan)!=_FIELDS: raise ValueError('exact workshop plan required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=604800:
        raise ValueError('invalid age limit')
    source,eid=plan['source_ref'],plan['experiment_id']
    if any(not isinstance(v,str) or not _REF.fullmatch(v) for v in (source,eid)):
        raise ValueError('invalid reference')
    try: t=datetime.fromisoformat(plan['observed_at'])
    except (TypeError,ValueError) as exc: raise ValueError('invalid observed_at') from exc
    if t.tzinfo is None or t.utcoffset() is None: raise ValueError('timestamp requires timezone')
    if plan['host_class']!='disposable_workshop_guest': raise ValueError('only disposable workshop guests supported')
    if plan['network_mode'] not in ('isolated_none','isolated_internal'):
        raise ValueError('offline isolated network mode required')
    for name,lo,hi in [('disk_gib',1,512),('memory_mib',256,16384),('vcpus',1,16)]:
        v=plan[name]
        if type(v) is not int or not lo<=v<=hi: raise ValueError('invalid '+name)
    steps=plan['steps']
    if type(steps) is not list or not 1<=len(steps)<=12 or any(
        not isinstance(s,str) or s not in _STEPS for s in steps
    ):raise ValueError('invalid plan steps')
    if len(steps)!=len(set(steps)):raise ValueError('duplicate plan steps')
    if type(plan['destruction_reviewed']) is not bool:
        raise ValueError('destruction_reviewed must be bool')
    idx={v:i for i,v in enumerate(_SEQUENCE)}
    correct_order=all(idx[a]<idx[b] for a,b in zip(steps,steps[1:]))
    missing=[s for s in _SEQUENCE if s not in steps]
    findings=[]
    if not correct_order: findings.append('experiment_steps_out_of_order')
    if missing: findings.append('missing_required_steps')
    if not plan['destruction_reviewed']: findings.append('no_destruction_review')
    if plan['network_mode']=='isolated_internal':findings.append('isolation_must_be_verified_by_platform')
    age=(now.astimezone(timezone.utc)-t.astimezone(timezone.utc)).total_seconds()
    freshness='future' if age < -5 else 'stale' if age>max_age_seconds else 'fresh'
    base={'schema':'sofia.workshop.plan_review.v1','module_id':MODULE_ID,
          'sdk_protocol':str(SDK_PROTOCOL_VERSION),'source_ref':source,'freshness':freshness,
          'evidence_class':'supplied_unverified','effect':'none','host_accessed':False,
          'vm_created':False,'network_isolation_verified':False,'provisioning_authorized':False}
    if freshness!='fresh':return base|{'status':'unknown','findings':['plan_timestamp_invalid'],
                                      'missing_steps':[],'resource_request':None}
    return base|{'status':'reviewed','findings':findings,'missing_steps':missing,
                 'resource_request':{k:plan[k] for k in ('vcpus','memory_mib','disk_gib')},
                 'procedurally_complete':not findings,
                 'platform_acceptance_required':True}


def capability_registrations():
    c=Capability(CAPABILITY_ID,'Review disposable workshop experiment plans without provisioning.')
    def handle(req:CapabilityRequest):
        if not isinstance(req,CapabilityRequest) or req.capability!=c or set(req.parameters)!={'snapshot'}:
            raise ValueError('invalid workshop request')
        return review_experiment_plan(req.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((c,handle),)
