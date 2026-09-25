"""Single-store durable lease/fence state.

This survives process restart but is not a distributed consensus service. Cross-host
promotion still requires PromotionGuard witness/fencing evidence.
"""
from __future__ import annotations
from datetime import datetime,timedelta
import json,os
from pathlib import Path
from .lease import AuthorityLease,LeaseTable

class JsonLeaseTable(LeaseTable):
    def __init__(self,path:Path)->None:
        super().__init__(); self.path=path
        if path.exists(): self._load()
    def _load(self)->None:
        raw=json.loads(self.path.read_text(encoding="utf-8"))
        self._epoch={str(k):int(v) for k,v in raw.get("epochs",{}).items()}
        self._fenced={(str(x[0]),str(x[1])) for x in raw.get("fenced",[])}
        for item in raw.get("leases",[]):
            lease=AuthorityLease(item["workload_id"],item["holder_host_id"],int(item["epoch"]),
                datetime.fromisoformat(item["acquired_at"]),datetime.fromisoformat(item["expires_at"]))
            self._leases[lease.workload_id]=lease
    def flush(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={
            "epochs":self._epoch,
            "fenced":[list(x) for x in sorted(self._fenced)],
            "leases":[{
                "workload_id":l.workload_id,"holder_host_id":l.holder_host_id,"epoch":l.epoch,
                "acquired_at":l.acquired_at.isoformat(),"expires_at":l.expires_at.isoformat(),
            } for l in self._leases.values()],
        }
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        with tmp.open("w",encoding="utf-8") as fh:
            json.dump(payload,fh,sort_keys=True,indent=2); fh.flush(); os.fsync(fh.fileno())
        tmp.replace(self.path)
    def fence(self,workload_id:str,host_id:str)->None:
        super().fence(workload_id,host_id); self.flush()
    def acquire(self,workload_id:str,host_id:str,*,now:datetime,ttl:timedelta)->AuthorityLease:
        lease=super().acquire(workload_id,host_id,now=now,ttl=ttl); self.flush(); return lease
    def transfer(self,workload_id:str,source_host_id:str,target_host_id:str,*,now:datetime,ttl:timedelta,state_verified:bool)->AuthorityLease:
        lease=super().transfer(workload_id,source_host_id,target_host_id,now=now,ttl=ttl,state_verified=state_verified)
        self.flush(); return lease
