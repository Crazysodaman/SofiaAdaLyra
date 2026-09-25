from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from .fleet import FleetRegistry
from .model import FleetHost,HostLifecycle,HostTelemetry

class JsonFleetRegistry(FleetRegistry):
    def __init__(self,path:Path)->None:
        super().__init__(); self.path=path
        if path.exists(): self._load()
    def _load(self)->None:
        data=json.loads(self.path.read_text(encoding="utf-8"))
        for raw in data.get("hosts",[]):
            tele=raw.pop("telemetry",None)
            if tele:
                tele["observed_at"]=datetime.fromisoformat(tele["observed_at"]); tele=HostTelemetry(**tele)
            raw["lifecycle"]=HostLifecycle(raw["lifecycle"]); raw["tags"]=tuple(raw.get("tags",()))
            self._hosts[raw["host_id"]]=FleetHost(telemetry=tele,**raw)
    def flush(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        hosts=[]
        for h in self.hosts():
            t=None if h.telemetry is None else {**h.telemetry.__dict__,"observed_at":h.telemetry.observed_at.isoformat()}
            hosts.append(dict(host_id=h.host_id,platform=h.platform,architecture=h.architecture,lifecycle=h.lifecycle.value,trusted=h.trusted,telemetry=t,tags=list(h.tags)))
        tmp=self.path.with_suffix(self.path.suffix+".tmp"); tmp.write_text(json.dumps({"hosts":hosts},sort_keys=True,indent=2),encoding="utf-8"); tmp.replace(self.path)
