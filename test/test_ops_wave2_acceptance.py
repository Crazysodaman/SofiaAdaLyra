from pathlib import Path
from sofia.ops.model import FleetHost,HostLifecycle
from sofia.ops.state_registry import StatePlaneFleetRegistry
from sofia.state.sqlite_plane import SQLiteStatePlane

def host():
    return FleetHost("venus","windows","amd64",HostLifecycle.CANDIDATE,True)

def test_fleet_registry_round_trip(tmp_path:Path):
    s=StatePlaneFleetRegistry(SQLiteStatePlane(tmp_path/"sofia.db")); s.register_candidate(host())
    assert StatePlaneFleetRegistry(SQLiteStatePlane(tmp_path/"sofia.db")).host("venus")==host()


def test_persisted_decommission_still_needs_sparks(tmp_path:Path):
    s=StatePlaneFleetRegistry(SQLiteStatePlane(tmp_path/"sofia.db")); s.register_candidate(host())
    s.transition("venus",HostLifecycle.ENROLLED); s.transition("venus",HostLifecycle.HEALTHY); s.transition("venus",HostLifecycle.DRAINING)
    try: s.transition("venus",HostLifecycle.DECOMMISSIONED)
    except PermissionError: pass
    else: raise AssertionError("removal gate bypassed")



def test_fleet_registry_round_trip_preserves_authenticated_node_binding(tmp_path:Path):
    from uuid import uuid4
    node_id=uuid4()
    bound=FleetHost(
        "terra",
        "linux",
        "x86_64",
        HostLifecycle.CANDIDATE,
        True,
        node_id=node_id,
    )
    path=tmp_path/"sofia.db"
    store=StatePlaneFleetRegistry(SQLiteStatePlane(path))
    store.register_candidate(bound)

    restored=StatePlaneFleetRegistry(SQLiteStatePlane(path)).host("terra")

    assert restored is not None
    assert restored.node_id==node_id
