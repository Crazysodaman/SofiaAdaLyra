from datetime import datetime,timezone
from pathlib import Path
from sofia.ops.fleet import FleetRegistry
from sofia.ops.model import FleetHost,HostLifecycle
from sofia.ops.persistence import JsonFleetRegistry
from sofia.ops.telemetry import telemetry_from_snapshot

def host():
    return FleetHost("venus","windows","amd64",HostLifecycle.CANDIDATE,True)

def test_fleet_registry_round_trip(tmp_path:Path):
    s=JsonFleetRegistry(tmp_path/"fleet.json"); s.register_candidate(host()); s.flush()
    assert JsonFleetRegistry(tmp_path/"fleet.json").host("venus")==host()

def test_snapshot_normalizes_telemetry():
    t=telemetry_from_snapshot({"cpu_percent":42.0,"ram_total_bytes":100},observed_at=datetime.now(timezone.utc))
    assert t.cpu_percent==42.0 and t.ram_total_bytes==100

def test_persisted_decommission_still_needs_sparks(tmp_path:Path):
    s=JsonFleetRegistry(tmp_path/"fleet.json"); s.register_candidate(host())
    s.transition("venus",HostLifecycle.ENROLLED); s.transition("venus",HostLifecycle.HEALTHY); s.transition("venus",HostLifecycle.DRAINING)
    try: s.transition("venus",HostLifecycle.DECOMMISSIONED)
    except PermissionError: pass
    else: raise AssertionError("removal gate bypassed")
