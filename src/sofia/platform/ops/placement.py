from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from .activity import ActivityMode, HostActivityState
from .model import FleetHost, HostLifecycle, WorkloadContract
from sofia.platform.resources import (
    CapabilityRequirement, ResourceSupply, evaluate_resource_requirements,
)

@dataclass(frozen=True)
class PlacementDecision:
    workload_id:str; host_id:str|None; eligible_hosts:tuple[str,...]; rejected:tuple[tuple[str,str],...]

class PlacementEngine:
    @staticmethod
    def _activity_pressure(
        host_id:str, *, allow_interactive_host:bool,
        activities:Mapping[str,HostActivityState], now:datetime|None,
    )->int:
        if allow_interactive_host:
            return 0
        state=activities.get(host_id)
        if state is None:
            return 3 if now is not None else 0
        if now is not None and state.override is ActivityMode.AUTO:
            observed=state.observed_at
            if observed is None or observed.tzinfo is None or observed.utcoffset() is None:
                return 3
            age=now.astimezone(timezone.utc)-observed.astimezone(timezone.utc)
            if not -timedelta(seconds=30)<=age<=timedelta(seconds=120):
                return 3
        return state.interactive_pressure

    def choose_resources(
        self, *, workload_id:str, supplies:tuple[ResourceSupply,...],
        requirements:tuple[CapabilityRequirement,...],
        activities:Mapping[str,HostActivityState]|None=None,
        benchmark_scores:Mapping[str,float]|None=None,
        allowed_host_ids:tuple[str,...]=(), denied_host_ids:tuple[str,...]=(),
        allow_interactive_host:bool=False, now:datetime,
    )->PlacementDecision:
        """Select from typed per-host supply; this decision grants no authority."""
        if not isinstance(workload_id,str) or not workload_id.strip():
            raise ValueError("workload_id required")
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("placement clock must be timezone-aware")
        if type(supplies) is not tuple or any(not isinstance(item,ResourceSupply) for item in supplies):
            raise TypeError("supplies must be ResourceSupply values")
        if len({item.host_id for item in supplies}) != len(supplies):
            raise ValueError("one resource supply per host required")
        if type(requirements) is not tuple or any(
            not isinstance(item,CapabilityRequirement) for item in requirements
        ):
            raise TypeError("requirements must be CapabilityRequirement values")
        activity_map=activities or {}; scores=benchmark_scores or {}
        eligible:list[ResourceSupply]=[]; rejected:list[tuple[str,str]]=[]
        for supply in supplies:
            if supply.host_id in denied_host_ids:
                rejected.append((supply.host_id,"host denied by workload policy")); continue
            if allowed_host_ids and supply.host_id not in allowed_host_ids:
                rejected.append((supply.host_id,"host not in workload allowlist")); continue
            assessment=evaluate_resource_requirements(supply,requirements,now=now)
            if not assessment.compatible:
                reasons=tuple(reason for _,reason in assessment.rejected+assessment.unknown)
                rejected.append((supply.host_id,"; ".join(reasons) or "resource requirements not met"))
                continue
            pressure=self._activity_pressure(
                supply.host_id, allow_interactive_host=allow_interactive_host,
                activities=activity_map, now=now,
            )
            if pressure > 0:
                rejected.append((supply.host_id,"foreground activity is not eligible for background placement"))
                continue
            eligible.append(supply)
        eligible.sort(key=lambda supply:(
            self._activity_pressure(
                supply.host_id, allow_interactive_host=allow_interactive_host,
                activities=activity_map, now=now,
            ),
            supply.host_id not in scores,
            -float(scores.get(supply.host_id,0.0)),
            supply.host_id,
        ))
        return PlacementDecision(
            workload_id, eligible[0].host_id if eligible else None,
            tuple(item.host_id for item in eligible), tuple(rejected),
        )

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
        # A stale AUTO observation is not proof that the user stopped gaming.
        # Penalize missing, stale or future activity when we have an actual
        # placement clock, while respecting an explicit operator override.
        def key(host:FleetHost):
            pressure=self._activity_pressure(
                host.host_id, allow_interactive_host=workload.allow_interactive_host,
                activities=activity_map, now=now,
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
