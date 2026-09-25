from __future__ import annotations
from datetime import datetime,timezone
from typing import Any,Mapping
from .model import HostTelemetry

def telemetry_from_snapshot(snapshot:Mapping[str,Any],*,observed_at:datetime|None=None)->HostTelemetry:
    """Normalize a trusted inspection snapshot without granting collection authority."""
    at=observed_at or datetime.now(timezone.utc)
    return HostTelemetry(observed_at=at,cpu_percent=snapshot.get("cpu_percent"),ram_used_bytes=snapshot.get("ram_used_bytes"),
        ram_total_bytes=snapshot.get("ram_total_bytes"),gpu_percent=snapshot.get("gpu_percent"),vram_used_bytes=snapshot.get("vram_used_bytes"),
        vram_total_bytes=snapshot.get("vram_total_bytes"),storage_free_bytes=snapshot.get("storage_free_bytes"),
        temperature_c=snapshot.get("temperature_c"),throttled=snapshot.get("throttled"))
