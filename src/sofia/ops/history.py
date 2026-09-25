"""Durable append-only fleet telemetry history."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from .model import HostTelemetry

class TelemetryHistory:
    def __init__(self,path:Path)->None: self.path=path
    def append(self,host_id:str,telemetry:HostTelemetry)->None:
        if not host_id.strip(): raise ValueError("host_id required")
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload=asdict(telemetry); payload["observed_at"]=telemetry.observed_at.isoformat(); payload["host_id"]=host_id
        with self.path.open("a",encoding="utf-8") as fh:
            fh.write(json.dumps(payload,sort_keys=True)+"\n"); fh.flush()
    def latest(self,host_id:str)->HostTelemetry|None:
        if not self.path.exists(): return None
        found=None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            raw=json.loads(line)
            if raw.pop("host_id")!=host_id: continue
            raw["observed_at"]=datetime.fromisoformat(raw["observed_at"]); found=HostTelemetry(**raw)
        return found
