from __future__ import annotations
from dataclasses import dataclass
from .model import FleetHost, HostLifecycle, WorkloadContract

@dataclass(frozen=True)
class PlacementDecision:
    workload_id:str; host_id:str|None; eligible_hosts:tuple[str,...]; rejected:tuple[tuple[str,str],...]

class PlacementEngine:
    def choose(self,workload:WorkloadContract,hosts:tuple[FleetHost,...])->PlacementDecision:
        eligible=[]; rejected=[]
        for host in hosts:
            reason=self._reject_reason(workload,host)
            if reason: rejected.append((host.host_id,reason))
            else: eligible.append(host)
        # Prefer lower observed CPU pressure; unknown telemetry loses to known healthy evidence.
        eligible.sort(key=lambda h:(h.telemetry is None, 101.0 if h.telemetry is None or h.telemetry.cpu_percent is None else h.telemetry.cpu_percent,h.host_id))
        return PlacementDecision(workload.workload_id,eligible[0].host_id if eligible else None,tuple(h.host_id for h in eligible),tuple(rejected))
    @staticmethod
    def _reject_reason(w:WorkloadContract,h:FleetHost)->str|None:
        if not h.trusted: return "host is not trusted"
        if h.lifecycle not in (HostLifecycle.ENROLLED,HostLifecycle.HEALTHY): return f"host lifecycle is {h.lifecycle.value}"
        if h.host_id in w.denied_host_ids: return "host denied by workload policy"
        if w.allowed_host_ids and h.host_id not in w.allowed_host_ids: return "host not in workload allowlist"
        if h.platform not in w.supported_platforms: return "unsupported platform"
        if h.architecture not in w.supported_architectures: return "unsupported architecture"
        t=h.telemetry
        if t is None: return "no current telemetry"
        if t.ram_total_bytes is not None and t.ram_used_bytes is not None and t.ram_total_bytes-t.ram_used_bytes < w.min_ram_bytes: return "insufficient RAM headroom"
        if t.storage_free_bytes is not None and t.storage_free_bytes < w.min_storage_bytes: return "insufficient storage"
        if w.gpu_required and t.gpu_percent is None: return "required GPU unavailable"
        if w.min_vram_bytes and (t.vram_total_bytes is None or t.vram_used_bytes is None or t.vram_total_bytes-t.vram_used_bytes < w.min_vram_bytes): return "insufficient VRAM headroom"
        if t.throttled is True: return "host is throttled"
        return None
