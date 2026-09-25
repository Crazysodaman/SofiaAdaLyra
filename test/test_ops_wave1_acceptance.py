from datetime import datetime, timezone
import pytest
from sofia.ops import FleetHost,FleetRegistry,FleetRemovalApproval,FleetRemovalApprovalRequired,HostLifecycle,HostTelemetry,PlacementEngine,WorkloadContract

def host(state=HostLifecycle.CANDIDATE,trusted=True,cpu=10):
    return FleetHost("venus","windows","x86_64",state,trusted,HostTelemetry(datetime.now(timezone.utc),cpu_percent=cpu,ram_used_bytes=4,ram_total_bytes=16,storage_free_bytes=100))

def test_untrusted_candidate_cannot_enroll():
    fleet=FleetRegistry(); fleet.register_candidate(host(trusted=False))
    with pytest.raises(PermissionError): fleet.transition("venus",HostLifecycle.ENROLLED)

def test_final_removal_requires_sparks_approval():
    fleet=FleetRegistry(); fleet.register_candidate(host()); fleet.transition("venus",HostLifecycle.ENROLLED); fleet.transition("venus",HostLifecycle.QUARANTINED); fleet.transition("venus",HostLifecycle.DRAINING)
    with pytest.raises(FleetRemovalApprovalRequired): fleet.transition("venus",HostLifecycle.DECOMMISSIONED)
    approval=FleetRemovalApproval("approve-venus","venus","rev-1","Sparks",datetime.now(timezone.utc))
    assert fleet.decommission("venus",proposal_revision="rev-1",approval=approval).lifecycle is HostLifecycle.DECOMMISSIONED

def test_placement_prefers_lower_cpu_eligible_host():
    now=datetime.now(timezone.utc)
    a=FleetHost("a","windows","x86_64",HostLifecycle.HEALTHY,True,HostTelemetry(now,cpu_percent=70,ram_used_bytes=4,ram_total_bytes=16,storage_free_bytes=100))
    b=FleetHost("b","windows","x86_64",HostLifecycle.HEALTHY,True,HostTelemetry(now,cpu_percent=20,ram_used_bytes=4,ram_total_bytes=16,storage_free_bytes=100))
    work=WorkloadContract("w","1",("windows",),("x86_64",))
    assert PlacementEngine().choose(work,(a,b)).host_id=="b"

def test_quarantined_host_is_never_placement_candidate():
    h=host(HostLifecycle.QUARANTINED)
    work=WorkloadContract("w","1",("windows",),("x86_64",))
    assert PlacementEngine().choose(work,(h,)).host_id is None
