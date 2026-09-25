from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import pytest

from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.model import DistributedNode
from sofia.machine.model import (
    HardwareProfile,MachineIdentity,MachineProfile,MachineVerification,
    OperatingSystemInfo,PlatformFamily,VirtualizationInfo,
)
from sofia.ops import (
    AuthenticatedPeerEvidence,BackupEvidence,DesiredHostState,DesiredWorkloadPlacement,
    FailureDomain,FleetEnrollmentService,FleetHost,FleetRegistry,FleetRemovalApproval,
    FleetRemovalApprovalRequired,HostLifecycle,HostUpdateAssignment,JsonLeaseTable,LeaseTable,
    MachineNodeBinding,MaintenanceOperation,MaintenancePolicy,MaintenanceRequest,
    ManagedWorkload,MigrationCoordinator,MigrationPlan,MigrationStage,PromotionDenied,
    WorkloadOrchestrator,
    PromotionEvidence,PromotionGuard,RecoveryDenied,RecoveryGuard,RestoreVerification,
    SplitBrainRisk,StateMode,TelemetryHistory,UpdatePlanner,UpdateRing,WorkloadContract,
    WorkloadInstance,WorkloadPhase,detect_drift,
)
from sofia.ops.machine_bridge import fleet_host_from_machine,telemetry_from_system_result
from sofia.ops.remote import to_remote_operation
from sofia.system.model import SystemCapabilityName,SystemCapabilityResult,SystemCapabilityResultKind

NOW=datetime.now(timezone.utc)

def _fleet(host_id="venus",trusted=True):
    fleet=FleetRegistry()
    fleet.register_candidate(FleetHost(host_id,"windows","x86_64",HostLifecycle.CANDIDATE,trusted))
    if trusted:
        fleet.transition(host_id,HostLifecycle.ENROLLED)
        fleet.transition(host_id,HostLifecycle.HEALTHY)
    return fleet

def test_machine_observation_never_infers_trust():
    profile=MachineProfile(
        MachineIdentity("machine-1","venus"),
        OperatingSystemInfo(PlatformFamily.WINDOWS,"Windows 11","11","x86_64","kernel"),
        VirtualizationInfo(False),
        HardwareProfile(memory_bytes=32),
        MachineVerification(NOW,NOW,"test"),
    )
    host=fleet_host_from_machine(profile)
    assert host.host_id=="machine-1"
    assert host.trusted is False
    assert host.lifecycle is HostLifecycle.CANDIDATE

def test_system_hardware_result_normalizes_to_ops_telemetry():
    result=SystemCapabilityResult(
        SystemCapabilityName.HARDWARE_INSPECT,
        SystemCapabilityResultKind.SUCCESS,
        {
            "cpu":{"usage_percent":33.0,"temperature_c":61.0},
            "gpu":{"usage_percent":44.0,"vram_total_bytes":1000},
            "memory":{"used_bytes":40,"total_bytes":100},
            "storage":{"free_bytes":500},
            "network":None,
            "virtualization":None,
        },
        NOW,
        "test-backend",
        None,
    )
    telemetry=telemetry_from_system_result(result)
    assert telemetry.cpu_percent==33.0
    assert telemetry.gpu_percent==44.0
    assert telemetry.ram_total_bytes==100
    assert telemetry.storage_free_bytes==500

def test_telemetry_history_round_trip(tmp_path:Path):
    from sofia.ops import HostTelemetry
    history=TelemetryHistory(tmp_path/"telemetry.jsonl")
    telemetry=HostTelemetry(NOW,cpu_percent=12.0,ram_used_bytes=1,ram_total_bytes=2)
    history.append("venus",telemetry)
    assert history.latest("venus")==telemetry

def test_singleton_lease_blocks_split_brain_until_source_fenced():
    leases=LeaseTable()
    ttl=timedelta(minutes=1)
    first=leases.acquire("sofia","venus",now=NOW,ttl=ttl)
    with pytest.raises(SplitBrainRisk):
        leases.acquire("sofia","terra",now=NOW+timedelta(seconds=1),ttl=ttl)
    leases.fence("sofia","venus")
    second=leases.transfer("sofia","venus","terra",now=NOW+timedelta(seconds=2),ttl=ttl,state_verified=True)
    assert second.holder_host_id=="terra"
    assert second.epoch>first.epoch

def test_stateful_migration_requires_checkpoint_and_fencing_stage():
    contract=WorkloadContract("sofia","1",("windows",),("x86_64",),singleton=True)
    workload=ManagedWorkload(contract,StateMode.PERSISTENT,checkpoint_required=True)
    coord=MigrationCoordinator()
    plan=MigrationPlan("m1",workload,"venus","terra")
    plan=coord.advance(plan,MigrationStage.DRAINED)
    with pytest.raises(ValueError):
        coord.advance(plan,MigrationStage.TARGET_STARTED)
    for stage in (
        MigrationStage.CHECKPOINTED,
        MigrationStage.TARGET_STARTED,
        MigrationStage.READY,
        MigrationStage.SOURCE_FENCED,
        MigrationStage.COMPLETED,
    ):
        plan=coord.advance(plan,stage)
    assert plan.stage is MigrationStage.COMPLETED

def test_promotion_fails_closed_without_independent_domain_fence_state_and_witness():
    fleet=_fleet("terra")
    same=PromotionGuard(fleet,(FailureDomain("venus","artemis"),FailureDomain("terra","artemis")))
    evidence=PromotionEvidence("sofia","venus","terra",True,True,True)
    with pytest.raises(PromotionDenied):
        same.require(evidence)
    guard=PromotionGuard(fleet,(FailureDomain("venus","venus-physical"),FailureDomain("terra","terra-physical")))
    with pytest.raises(PromotionDenied):
        guard.require(PromotionEvidence("sofia","venus","terra",True,True,False))
    guard.require(evidence)

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
    remote=to_remote_operation(service,policy=policy,remote_request_id=uuid4(),node_id=uuid4(),grant_id=uuid4())
    assert remote.capability=="service.manage"
    assert remote.operation=="restart"
    assert remote.parameters["service"]=="Spooler"
    assert "command" not in remote.parameters
    assert "shell" not in remote.parameters

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

def test_update_rings_canary_before_general_and_require_health_and_rollback():
    planner=UpdatePlanner()
    ordered=planner.order((
        HostUpdateAssignment("prod",UpdateRing.GENERAL),
        HostUpdateAssignment("canary",UpdateRing.CANARY),
        HostUpdateAssignment("early",UpdateRing.EARLY),
    ))
    assert [x.host_id for x in ordered]==["canary","early","prod"]
    assert planner.next_ring_allowed(UpdateRing.CANARY,health_verified=True,rollback_ready=True)
    assert not planner.next_ring_allowed(UpdateRing.CANARY,health_verified=False,rollback_ready=True)

def test_durable_lease_and_fence_state_survive_restart(tmp_path:Path):
    path=tmp_path/"leases.json"
    table=JsonLeaseTable(path)
    first=table.acquire("sofia","venus",now=NOW,ttl=timedelta(minutes=1))
    table.fence("sofia","venus")
    restored=JsonLeaseTable(path)
    assert restored.current("sofia")==first
    assert restored.is_fenced("sofia","venus")
    second=restored.transfer("sofia","venus","terra",now=NOW+timedelta(seconds=1),ttl=timedelta(minutes=1),state_verified=True)
    assert second.epoch>first.epoch

def test_workload_orchestrator_executes_checkpoint_readiness_fence_and_lease_transfer():
    contract=WorkloadContract("sofia","1",("windows",),("x86_64",),singleton=True)
    workload=ManagedWorkload(contract,StateMode.PERSISTENT,checkpoint_required=True)
    plan=MigrationPlan("m-exec",workload,"venus","terra")
    leases=LeaseTable()
    leases.acquire("sofia","venus",now=NOW-timedelta(seconds=1),ttl=timedelta(minutes=5))
    events=[]
    class Backend:
        def drain(self,w,h): events.append(("drain",h))
        def checkpoint(self,w,h): events.append(("checkpoint",h)); return "cp-1"
        def start(self,w,h,cp): events.append(("start",h,cp))
        def ready(self,w,h): events.append(("ready",h)); return True
        def fence(self,w,h): events.append(("fence",h))
        def stop(self,w,h): events.append(("stop",h))
    receipt=WorkloadOrchestrator(leases).migrate(plan,Backend(),now=NOW,lease_ttl=timedelta(minutes=5))
    assert receipt.checkpoint_id=="cp-1"
    assert leases.current("sofia").holder_host_id=="terra"
    assert ("fence","venus") in events
    assert events[-1]==("stop","venus")
