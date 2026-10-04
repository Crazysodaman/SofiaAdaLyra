from sofia.ops.history import SQLiteTelemetryHistory
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import pytest

from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.model import DistributedNode
from sofia.ops import AuthenticatedPeerEvidence, BackupEvidence, DesiredHostState, DesiredWorkloadPlacement, FleetEnrollmentService, FleetHost, FleetRegistry, FleetRemovalApproval, FleetRemovalApprovalRequired, HostLifecycle, MachineNodeBinding, MaintenanceOperation, MaintenancePolicy, MaintenanceRequest, RecoveryDenied, RecoveryGuard, RestoreVerification, WorkloadInstance, WorkloadPhase, detect_drift

NOW=datetime.now(timezone.utc)

def _fleet(host_id="venus",trusted=True):
    fleet=FleetRegistry()
    fleet.register_candidate(FleetHost(host_id,"windows","x86_64",HostLifecycle.CANDIDATE,trusted))
    if trusted:
        fleet.transition(host_id,HostLifecycle.ENROLLED)
        fleet.transition(host_id,HostLifecycle.HEALTHY)
    return fleet



def test_telemetry_history_round_trip(tmp_path:Path):
    from sofia.ops import HostTelemetry
    history=SQLiteTelemetryHistory(tmp_path/"sofia.db")
    telemetry=HostTelemetry(NOW,cpu_percent=12.0,ram_used_bytes=1,ram_total_bytes=2)
    history.append("venus",telemetry)
    assert history.latest("venus")==telemetry




def test_desired_state_reports_host_and_workload_drift():
    fleet=_fleet("venus")
    instance=WorkloadInstance("i1","worker","1","venus",WorkloadPhase.READY)
    drift=detect_drift(
        fleet,
        (instance,),
        (DesiredHostState("venus",HostLifecycle.MAINTENANCE),),
        (DesiredWorkloadPlacement("worker","terra"),),
    )
    assert {d.kind for d in drift}=={"host_lifecycle","workload_placement"}

def test_final_removal_requires_exact_sparks_host_and_revision():
    fleet=_fleet("venus")
    fleet.transition("venus",HostLifecycle.DRAINING)
    with pytest.raises(FleetRemovalApprovalRequired):
        fleet.transition("venus",HostLifecycle.DECOMMISSIONED)
    with pytest.raises(PermissionError):
        FleetRemovalApproval("a","venus","r1","Sofia",NOW)
    wrong=FleetRemovalApproval("a","terra","r1","Sparks",NOW)
    with pytest.raises(FleetRemovalApprovalRequired):
        fleet.decommission("venus",proposal_revision="r1",approval=wrong)
    stale=FleetRemovalApproval("b","venus","r0","Sparks",NOW)
    with pytest.raises(FleetRemovalApprovalRequired):
        fleet.decommission("venus",proposal_revision="r1",approval=stale)
    exact=FleetRemovalApproval("c","venus","r1","Sparks",NOW)
    assert fleet.decommission("venus",proposal_revision="r1",approval=exact).lifecycle is HostLifecycle.DECOMMISSIONED

def test_maintenance_is_typed_and_respects_no_reboot_pin():
    fleet=_fleet("venus")
    policy=MaintenancePolicy(fleet,no_reboot_hosts=frozenset({"venus"}))
    reboot=MaintenanceRequest("r1","venus",MaintenanceOperation.HOST_REBOOT,authorized=True)
    with pytest.raises(PermissionError):
        policy.require(reboot)
    service=MaintenanceRequest("r2","venus",MaintenanceOperation.SERVICE_RESTART,"Spooler",True)
    policy.require(service)


def test_authenticated_enrollment_binds_machine_node_and_peer_key():
    node_id=uuid4()
    pin="a"*64
    enrollment=NodeEnrollment(DistributedNode(node_id,"venus-node"),pin,NOW,"Sparks")
    candidate=FleetHost("venus","windows","x86_64",HostLifecycle.CANDIDATE,False)
    binding=MachineNodeBinding("venus",node_id,NOW,"authenticated-net-binding")
    peer=AuthenticatedPeerEvidence(node_id,pin,NOW,"NET authenticated transport")
    registry=FleetRegistry()
    enrolled=FleetEnrollmentService(registry).enroll(candidate,binding=binding,enrollment=enrollment,peer=peer)
    assert enrolled.trusted
    assert enrolled.lifecycle is HostLifecycle.ENROLLED
    assert enrolled.node_id == node_id

def test_authenticated_enrollment_rejects_wrong_peer_key():
    node_id=uuid4()
    enrollment=NodeEnrollment(DistributedNode(node_id,"venus-node"),"a"*64,NOW,"Sparks")
    candidate=FleetHost("venus","windows","x86_64",HostLifecycle.CANDIDATE,False)
    with pytest.raises(PermissionError):
        FleetEnrollmentService(FleetRegistry()).enroll(
            candidate,
            binding=MachineNodeBinding("venus",node_id,NOW,"binding"),
            enrollment=enrollment,
            peer=AuthenticatedPeerEvidence(node_id,"b"*64,NOW,"NET"),
        )

def test_recovery_requires_verified_restore_and_independent_failure_domain():
    backup=BackupEvidence("b1","venus","backup-physical",NOW,"c"*64)
    good=RestoreVerification("b1",NOW,"VERIFY",True)
    guard=RecoveryGuard()
    guard.require(backup,good,target_failure_domain="terra-physical")
    with pytest.raises(RecoveryDenied):
        guard.require(backup,good,target_failure_domain="backup-physical")
    failed=RestoreVerification("b1",NOW,"VERIFY",False)
    with pytest.raises(RecoveryDenied):
        guard.require(backup,failed,target_failure_domain="terra-physical")
