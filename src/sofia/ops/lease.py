"""Epoch leases and fencing for singleton workload authority."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta

class SplitBrainRisk(RuntimeError): pass

@dataclass(frozen=True)
class AuthorityLease:
    workload_id:str; holder_host_id:str; epoch:int; acquired_at:datetime; expires_at:datetime
    def __post_init__(self):
        if self.acquired_at.tzinfo is None or self.expires_at.tzinfo is None: raise ValueError("lease times must be timezone-aware")
        if self.expires_at<=self.acquired_at: raise ValueError("lease expiry must follow acquisition")
        if self.epoch<1: raise ValueError("lease epoch must be positive")
    def active(self,now:datetime)->bool: return now<self.expires_at

class LeaseTable:
    def __init__(self)->None:
        self._leases:dict[str,AuthorityLease]={}; self._fenced:set[tuple[str,str]] = set(); self._epoch:dict[str,int]={}
    def current(self,workload_id:str)->AuthorityLease|None: return self._leases.get(workload_id)
    def fence(self,workload_id:str,host_id:str)->None: self._fenced.add((workload_id,host_id))
    def is_fenced(self,workload_id:str,host_id:str)->bool: return (workload_id,host_id) in self._fenced
    def acquire(self,workload_id:str,host_id:str,*,now:datetime,ttl:timedelta)->AuthorityLease:
        if ttl<=timedelta(0): raise ValueError("ttl must be positive")
        current=self._leases.get(workload_id)
        if current is not None and current.active(now) and current.holder_host_id!=host_id and not self.is_fenced(workload_id,current.holder_host_id):
            raise SplitBrainRisk("active unfenced authority lease is held by another host")
        epoch=self._epoch.get(workload_id,0)+1; self._epoch[workload_id]=epoch
        lease=AuthorityLease(workload_id,host_id,epoch,now,now+ttl); self._leases[workload_id]=lease
        self._fenced.discard((workload_id,host_id)); return lease
    def transfer(self,workload_id:str,source_host_id:str,target_host_id:str,*,now:datetime,ttl:timedelta,state_verified:bool)->AuthorityLease:
        if not state_verified: raise SplitBrainRisk("state must be verified before authority transfer")
        current=self._leases.get(workload_id)
        if current is not None and current.holder_host_id==source_host_id and current.active(now) and not self.is_fenced(workload_id,source_host_id):
            raise SplitBrainRisk("source must be fenced before transfer")
        if not self.is_fenced(workload_id,source_host_id): raise SplitBrainRisk("source fencing evidence required")
        return self.acquire(workload_id,target_host_id,now=now,ttl=ttl)
