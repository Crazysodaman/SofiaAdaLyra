from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from .activity import HostActivityState
from .model import FleetHost, HostLifecycle, WorkloadContract

@dataclass(frozen=True)
class PlacementDecision:
    workload_id:str; host_id:str|None; eligible_hosts:tuple[str,...]; rejected:tuple[tuple[str,str],...]

class PlacementEngine:
    def choose(
        self,
        workload:WorkloadContract,
        hosts:tuple[FleetHost,...],
        *,
        activities:Mapping[str,HostActivityState]|None=None,
        now:datetime|None=None,
        max_telemetry_age_seconds:int=120,
    )->PlacementDecision:
        if now is not None and (not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None):
            raise ValueError("placement clock must be timezone-aware")
        if type(max_telemetry_age_seconds) is not int or not 10<=max_telemetry_age_seconds<=3600:
            raise ValueError("bounded telemetry freshness threshold required")
        eligible=[]; rejected=[]
        activity_map=activities or {}
        for host in hosts:
            reason=self._reject_reason(
                workload,host,now=now,max_age_seconds=max_telemetry_age_seconds,
            )
            if reason: rejected.append((host.host_id,reason))
            else: eligible.append(host)
        # Foreground use outranks momentary CPU idleness. A gaming/busy host is
        # deprioritized for ordinary movable background work whenever another
        # eligible host exists. Workloads may explicitly opt into foreground hosts.
        def key(host:FleetHost):
            state=activity_map.get(host.host_id)
            pressure=(
                state.interactive_pressure
                if state is not None and not workload.allow_interactive_host
                else 0
            )
            cpu=(
                101.0
                if host.telemetry is None or host.telemetry.cpu_percent is None
                else host.telemetry.cpu_percent
            )
            return (pressure,host.telemetry is None,cpu,host.host_id)
        eligible.sort(key=key)
        return PlacementDecision(workload.workload_id,eligible[0].host_id if eligible else None,tuple(h.host_id for h in eligible),tuple(rejected))
    @staticmethod
    def _reject_reason(
        w:WorkloadContract,h:FleetHost,*,now:datetime|None=None,
        max_age_seconds:int=120,
    )->str|None:
        if not h.trusted: return "host is not trusted"
        if h.lifecycle not in (HostLifecycle.ENROLLED,HostLifecycle.HEALTHY): return f"host lifecycle is {h.lifecycle.value}"
        if h.host_id in w.denied_host_ids: return "host denied by workload policy"
        if w.allowed_host_ids and h.host_id not in w.allowed_host_ids: return "host not in workload allowlist"
        if h.platform not in w.supported_platforms: return "unsupported platform"
        if h.architecture not in w.supported_architectures: return "unsupported architecture"
        t=h.telemetry
        if t is None: return "no current telemetry"
        if now is not None:
            age=now.astimezone(timezone.utc)-t.observed_at.astimezone(timezone.utc)
            if not -timedelta(seconds=30)<=age<=timedelta(seconds=max_age_seconds):
                return "telemetry expired or clock invalid"
        if w.min_ram_bytes:
            if (t.ram_total_bytes is None or t.ram_used_bytes is None
                or t.ram_used_bytes>t.ram_total_bytes
                or t.ram_total_bytes-t.ram_used_bytes<w.min_ram_bytes):
                return "RAM headroom unknown or insufficient"
        if w.min_storage_bytes and (
            t.storage_free_bytes is None or t.storage_free_bytes<w.min_storage_bytes
        ):
            return "storage headroom unknown or insufficient"
        if w.gpu_required:
            if (
                t.gpu_percent is None
                or t.vram_total_bytes is None
                or t.vram_used_bytes is None
                or t.vram_used_bytes>t.vram_total_bytes
            ):
                return "required GPU capacity unverified"
        if w.min_vram_bytes and (
            t.vram_total_bytes is None or t.vram_used_bytes is None
            or t.vram_used_bytes>t.vram_total_bytes
            or t.vram_total_bytes-t.vram_used_bytes<w.min_vram_bytes
        ):
            return "VRAM headroom unknown or insufficient"
        if t.throttled is True: return "host is throttled"
        return None
