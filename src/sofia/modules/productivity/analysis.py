"""MOD-PRODUCTIVITY: bounded proposed task order over opaque owner-supplied IDs.

No scheduling, goal mutation, task creation, reminder emission or persisted state.
Tasks are unverified projections and never override Core priorities or decisions.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-PRODUCTIVITY'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'productivity.review_task_dependencies.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref','observed_at','tasks'})
_TASK_FIELDS = frozenset({'task_id','priority','status','depends_on','due_at'})
_STATUSES = frozenset({'todo','in_progress','done','blocked'})


def _timestamp(value: object, name: str) -> datetime:
    if not isinstance(value,str):
        raise ValueError('invalid '+name)
    try: t = datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('invalid '+name) from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('timezone required for '+name)
    return t.astimezone(timezone.utc)


def review_task_dependencies(snapshot: Mapping[str,object], *, now:datetime,
                             max_age_seconds:int=3600)->dict[str,object]:
    if not isinstance(snapshot,Mapping) or set(snapshot)!=_FIELDS:
        raise ValueError('exact task projection fields required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:
        raise ValueError('invalid max age')
    source=snapshot['source_ref']
    if not isinstance(source,str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed=_timestamp(snapshot['observed_at'],'observed_at')
    raw=snapshot['tasks']
    if type(raw) is not list or len(raw)>128:
        raise ValueError('tasks must be bounded list')
    tasks={}
    for item in raw:
        if not isinstance(item,Mapping) or set(item)!=_TASK_FIELDS:
            raise ValueError('invalid task')
        tid=item['task_id']
        if not isinstance(tid,str) or not _REF.fullmatch(tid) or tid in tasks:
            raise ValueError('invalid or duplicate task_id')
        priority=item['priority']
        if type(priority) is not int or not 1<=priority<=5:
            raise ValueError('priority must be 1..5')
        status=item['status']
        if type(status) is not str or status not in _STATUSES:
            raise ValueError('invalid status')
        deps=item['depends_on']
        if type(deps) is not list or len(deps)>32 or any(
            type(dep) is not str or not _REF.fullmatch(dep) for dep in deps
        ) or len(set(deps))!=len(deps) or tid in deps:
            raise ValueError('invalid task dependencies')
        due=_timestamp(item['due_at'],'due_at') if item['due_at'] is not None else None
        tasks[tid]=(priority,status,deps,due)
    for _,_,deps,_ in tasks.values():
        if any(dep not in tasks for dep in deps):
            raise ValueError('unresolved task dependency')
    # Detect dependency cycles, including cycles through already-done tasks.
    seen,stack=set(),set()
    def visit(task_id:str)->None:
        if task_id in stack:
            raise ValueError('cyclic dependency')
        if task_id in seen:
            return
        stack.add(task_id)
        for dep in tasks[task_id][2]:
            visit(dep)
        stack.remove(task_id)
        seen.add(task_id)
    for tid in tasks:
        visit(tid)
    age=(now.astimezone(timezone.utc)-observed).total_seconds()
    freshness='future' if age < -5 else 'stale' if age>max_age_seconds else 'fresh'
    base={'schema':'sofia.productivity.task_review.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
          'module_id':MODULE_ID,'source_ref':source,'freshness':freshness,
          'evidence_class':'supplied_unverified','effect':'none',
          'tasks_modified':False,'reminders_sent':False,'core_goals_modified':False}
    if freshness!='fresh':
        return base|{'status':'unknown','ready_task_ids':[],'waiting_task_ids':[],
                     'overdue_task_ids':[],'completed_count':None}
    ready,waiting,overdue=[],[],[]
    for tid,(priority,status,deps,due) in tasks.items():
        if status=='done':
            continue
        if due is not None and due < now.astimezone(timezone.utc):
            overdue.append(tid)
        if status=='blocked' or any(tasks[dep][1]!='done' for dep in deps):
            waiting.append(tid)
        elif status in ('todo','in_progress'):
            ready.append((priority,due or datetime.max.replace(tzinfo=timezone.utc),tid))
    ready.sort(key=lambda x:(-x[0],x[1],x[2]))
    return base|{'status':'reviewed','ready_task_ids':[t[2] for t in ready],
                'waiting_task_ids':sorted(waiting),'overdue_task_ids':sorted(overdue),
                'completed_count':sum(status=='done' for _,status,_,_ in tasks.values())}


def capability_registrations():
    capability=Capability(CAPABILITY_ID,'Review bounded task dependencies without scheduling or changing Core goals.')
    def handler(request:CapabilityRequest):
        if not isinstance(request,CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid productivity capability request')
        return review_task_dependencies(request.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((capability,handler),)
