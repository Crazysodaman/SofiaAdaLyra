"""Read-only cognitive surface for OPS fleet state, telemetry and planning."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.model import (
    ApprovedEndpoint,
    DistributedNode,
    NodeEndpoint,
    NodeEnrollment,
    NodeTransport,
)
from sofia.safe.execution_approval import ExecutionApprovalVerifier

from .activity import HostActivityStore
from .desired import Drift,DesiredHostState,DesiredWorkloadPlacement,detect_drift
from .desired_store import DesiredFleetStateStore
from .discovery import FleetDiscoveryCoordinator
from .enrollment import (
    AuthenticatedPeerEvidence,
    FleetEnrollmentApproval,
    FleetEnrollmentService,
    MachineNodeBinding,
)
from .history import SQLiteTelemetryHistory
from sofia.ops.workload import MigrationPlan
from .model import HostLifecycle,WorkloadContract
from .state_registry import StatePlaneFleetRegistry
from .placement import PlacementEngine
from .reconcile import MaintenanceReceiptStore
from .repair_plan import FleetRepairPlanner
from .reconciliation_journal import FleetReconciliationJournal
from .workload import ManagedWorkload,StateMode,WorkloadInstance,WorkloadPhase
from .workload_store import WorkloadInstanceStore
from .migration import WorkloadMigrationExecutor, MigrationJournal
from .migration_grants import (
    migration_approval_parameters,
    migration_remote_grant_specs,
    temporary_migration_remote_grants,
)
from .workload_backend import (
    TypedWorkloadBackend,
    WorkloadExecutionCatalog,
    WorkloadOutcomeUncertain,
)
from sofia.state.plane import StatePlane
from sofia.state.sqlite_plane import SQLiteStatePlane
import os
from sofia.distributed.agent_tools import create_default_agent_dispatcher
from sofia.distributed.capability import create_configured_remote_fleet_service

class OpsToolService:
    def __init__(
        self,
        state_path:Path,
        *,
        state_plane:StatePlane|None=None,
        discovery_source=None,
        network_discovery_source=None,
    )->None:
        self.state_path=Path(state_path)
        plane=state_plane or SQLiteStatePlane(self.state_path)
        self.registry=StatePlaneFleetRegistry(
            plane,
            legacy_path=state_path.parent/"fleet.json",
        )
        self.enrollment=FleetEnrollmentService(self.registry)
        self.history=SQLiteTelemetryHistory(
            state_path,
            legacy_path=state_path.parent/"ops-telemetry.jsonl",
        )
        self.activity=HostActivityStore(state_path)
        self.placement=PlacementEngine()
        self.maintenance_receipts=MaintenanceReceiptStore(state_path)
        self.repair_planner=FleetRepairPlanner()
        self.desired_state=DesiredFleetStateStore(state_path)
        self.workloads=WorkloadInstanceStore(state_path)
        self.reconciliation_journal=FleetReconciliationJournal(state_path)
        self.discovery_source=discovery_source
        self.network_discovery_source=network_discovery_source
        self.execution_approvals=ExecutionApprovalVerifier(self.state_path)
        self.migration_executor=None
        self._workload_catalog=None
        self._local_host_id=""
        catalog_file=os.environ.get("SOFIA_WORKLOAD_CATALOG_FILE","").strip()
        if catalog_file:
            catalog=WorkloadExecutionCatalog.from_file(Path(catalog_file))
            local_host_id=os.environ.get("SOFIA_LOCAL_HOST_ID","").strip()
            self._workload_catalog=catalog
            self._local_host_id=local_host_id
            local_dispatcher=create_default_agent_dispatcher()
            remote_service=create_configured_remote_fleet_service(self.state_path)

            def invoke_workload(host_id,capability,operation,parameters):
                if local_host_id and host_id==local_host_id:
                    result=local_dispatcher.execute(capability,operation,parameters)
                    import json as _json
                    return {
                        "outcome":"reported_success",
                        "message":_json.dumps(result,default=str,ensure_ascii=False)
                        if result is not None else "{}",
                        "result":result,
                    }
                if remote_service is None:
                    raise RuntimeError(
                        "remote workload execution requires configured pinned-mTLS Fleet transport"
                    )
                return remote_service.invoke(
                    str(self.registry.host(host_id).node_id),
                    capability,
                    operation,
                    parameters,
                )

            self.migration_executor=WorkloadMigrationExecutor(
                backend=TypedWorkloadBackend(catalog,invoke_workload),
                state_plane=plane,
                instance_store=self.workloads,
            )

    @staticmethod
    def _host(host)->dict[str,Any]:
        return {
            "host_id":host.host_id,
            "platform":host.platform,
            "architecture":host.architecture,
            "lifecycle":host.lifecycle.value,
            "trusted":host.trusted,
            "telemetry":None if host.telemetry is None else {
                **asdict(host.telemetry),
                "observed_at":host.telemetry.observed_at.isoformat(),
            },
            "tags":host.tags,
            "node_id":None if host.node_id is None else str(host.node_id),
        }

    def fleet(self)->tuple[dict[str,Any],...]:
        return tuple(self._host(host) for host in self.registry.hosts())

    @staticmethod
    def _tag_value(tags:tuple[str,...],prefix:str)->str|None:
        for tag in tags:
            if tag.startswith(prefix):
                return tag[len(prefix):]
        return None

    def enrollment_evidence(self,host_id:str)->dict[str,Any]|None:
        host=self.registry.host(host_id)
        if host is None or host.lifecycle is not HostLifecycle.CANDIDATE:
            return None
        node_id=self._tag_value(host.tags,"observed-node:")
        key=self._tag_value(host.tags,"observed-key:")
        endpoint_host=self._tag_value(host.tags,"observed-endpoint-host:")
        endpoint_port=self._tag_value(host.tags,"observed-endpoint-port:")
        observed_at=self._tag_value(host.tags,"observed-at:")
        return {
            "host_id":host.host_id,
            "trusted":host.trusted,
            "node_id":node_id,
            "public_key_sha256":key,
            "endpoint_hostname":endpoint_host,
            "endpoint_port":None if endpoint_port is None else int(endpoint_port),
            "observed_at":observed_at,
            "capabilities_verified":"capabilities-verified" in host.tags,
            "ready":bool(
                not host.trusted
                and node_id
                and key
                and endpoint_host
                and endpoint_port
                and observed_at
                and "capabilities-verified" in host.tags
            ),
        }

    def enroll_candidate(self,p:dict[str,Any])->dict[str,Any]:
        host_id=p["host_id"]
        candidate=self.registry.host(host_id)
        if candidate is None:
            raise KeyError(f"unknown Fleet candidate: {host_id}")
        if candidate.lifecycle is not HostLifecycle.CANDIDATE or candidate.trusted:
            raise PermissionError("Fleet enrollment requires an untrusted candidate")

        evidence=self.enrollment_evidence(host_id)
        if evidence is None or evidence["ready"] is not True:
            raise PermissionError(
                "Fleet candidate lacks verified mTLS discovery evidence"
            )

        expected={
            "host_id":host_id,
            "node_id":p["node_id"],
            "public_key_sha256":p["public_key_sha256"],
            "endpoint_hostname":p["endpoint_hostname"],
            "endpoint_port":int(p["endpoint_port"]),
        }
        for key,value in expected.items():
            if evidence[key] != value:
                raise PermissionError(
                    f"Fleet enrollment evidence changed for {key}"
                )

        observed_at=datetime.fromisoformat(evidence["observed_at"])
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise PermissionError("Fleet discovery timestamp is not trustworthy")
        now=datetime.now(timezone.utc)
        if now-observed_at.astimezone(timezone.utc) > timedelta(minutes=30):
            raise PermissionError(
                "Fleet discovery evidence is stale; rediscover before enrollment"
            )

        node_id=UUID(expected["node_id"])
        endpoint=NodeEndpoint(
            expected["endpoint_hostname"],
            expected["endpoint_port"],
            NodeTransport.HTTPS,
        )
        enrollment=NodeEnrollment(
            DistributedNode(node_id,host_id),
            expected["public_key_sha256"],
            observed_at,
            "Sparks",
        )

        identities=DurableNodeIdentityRegistry(self.state_path)
        endpoints=DurableEndpointPolicy(self.state_path)
        try:
            existing_identity=identities.get(node_id)
            if (
                existing_identity is not None
                and existing_identity.public_key_sha256
                != enrollment.public_key_sha256
            ):
                raise PermissionError(
                    "Fleet node identity differs from approved discovery evidence"
                )
            existing_endpoint=endpoints.get(node_id)
            if existing_endpoint is not None and existing_endpoint != endpoint:
                raise PermissionError(
                    "Fleet endpoint differs from approved discovery evidence"
                )

            # Consume only after every deterministic trust/evidence preflight
            # check passes. A stale or conflicting candidate must not burn the
            # operator's one-time approval.
            exact_parameters=dict(expected)
            approval=self.execution_approvals.consume(
                approval_id=p["approval_id"],
                capability="fleet.enroll",
                parameters=exact_parameters,
                now=now,
            )
            if approval.approved_by!="Sparks":
                raise PermissionError(
                    "Fleet enrollment approval must come from Sparks"
                )

            if existing_identity is None:
                identities.enroll(enrollment)
            if existing_endpoint is None:
                endpoints.approve(
                    ApprovedEndpoint(node_id,endpoint,"Sparks")
                )
        finally:
            identities.close()
            endpoints.close()

        enrolled=self.enrollment.enroll(
            candidate,
            binding=MachineNodeBinding(
                host_id,
                node_id,
                observed_at,
                "verified-mtls-discovery",
            ),
            enrollment=enrollment,
            peer=AuthenticatedPeerEvidence(
                node_id,
                expected["public_key_sha256"],
                observed_at,
                "verified-mtls-discovery",
            ),
            approval=FleetEnrollmentApproval(
                approval.approval_id,
                host_id,
                node_id,
                expected["public_key_sha256"],
                approval.approved_by,
                approval.approved_at,
            ),
        )
        return self._host(enrolled)

    def host(self,host_id:str)->dict[str,Any]|None:
        host=self.registry.host(host_id)
        return None if host is None else self._host(host)

    def telemetry_latest(self,host_id:str)->dict[str,Any]|None:
        telemetry=self.history.latest(host_id)
        if telemetry is None:
            host=self.registry.host(host_id)
            telemetry=None if host is None else host.telemetry
        if telemetry is None: return None
        return {**asdict(telemetry),"observed_at":telemetry.observed_at.isoformat()}

    def discover_network(self)->dict[str,Any]:
        """Observe configured network scopes without changing Fleet membership."""
        if self.network_discovery_source is None:
            return {"configured":False,"observed":()}
        observations=self.network_discovery_source.discover()
        return {
            "configured":True,
            "observed":tuple({
                "host_id":item.host_id,
                "hostname":item.hostname,
                "platform":item.platform,
                "architecture":item.architecture,
                "source":item.source,
                "inside_approved_scope":item.inside_approved_scope,
                "agent_present":item.observed_node_id is not None,
                "capabilities_verified":item.capabilities_verified,
                "capability_names":item.capability_names,
            } for item in observations),
        }

    def discover_candidates(self)->dict[str,Any]:
        """Run bounded configured discovery without granting Fleet membership."""
        if self.discovery_source is None:
            return {
                "configured":False,
                "observed":(),
                "created_host_ids":(),
                "existing_host_ids":(),
                "rejected_host_ids":(),
            }
        result=FleetDiscoveryCoordinator(self.registry).run(
            self.discovery_source
        )
        return {
            "configured":True,
            "observed":tuple({
                "host_id":item.host_id,
                "hostname":item.hostname,
                "platform":item.platform,
                "architecture":item.architecture,
                "source":item.source,
                "inside_approved_scope":item.inside_approved_scope,
                "agent_present":item.observed_node_id is not None,
                "capabilities_verified":item.capabilities_verified,
                "capability_names":item.capability_names,
            } for item in result.observed),
            "created_host_ids":result.created_host_ids,
            "existing_host_ids":result.existing_host_ids,
            "rejected_host_ids":result.rejected_host_ids,
        }

    @staticmethod
    def _workload(raw:dict[str,Any])->WorkloadContract:
        return WorkloadContract(
            workload_id=raw["workload_id"],
            version=raw["version"],
            supported_platforms=tuple(raw["supported_platforms"]),
            supported_architectures=tuple(raw["supported_architectures"]),
            min_ram_bytes=int(raw.get("min_ram_bytes",0)),
            min_storage_bytes=int(raw.get("min_storage_bytes",0)),
            gpu_required=bool(raw.get("gpu_required",False)),
            min_vram_bytes=int(raw.get("min_vram_bytes",0)),
            singleton=bool(raw.get("singleton",False)),
            allowed_host_ids=tuple(raw.get("allowed_host_ids",())),
            denied_host_ids=tuple(raw.get("denied_host_ids",())),
            allow_interactive_host=bool(raw.get("allow_interactive_host",False)),
        )

    def choose_placement(self,raw:dict[str,Any])->dict[str,Any]:
        hosts=self.registry.hosts()
        activities={host.host_id:self.activity.state(host.host_id) for host in hosts}
        decision=self.placement.choose(
            self._workload(raw),
            hosts,
            activities=activities,
        )
        return asdict(decision)

    def drift(self,p:dict[str,Any])->tuple[dict[str,Any],...]:
        desired_hosts=tuple(
            DesiredHostState(x["host_id"],HostLifecycle(x["lifecycle"]))
            for x in p.get("desired_hosts",())
        )
        desired_workloads=tuple(
            DesiredWorkloadPlacement(x["workload_id"],x["host_id"])
            for x in p.get("desired_workloads",())
        )
        instances=tuple(
            WorkloadInstance(
                x["instance_id"],x["workload_id"],x["version"],x["host_id"],
                WorkloadPhase(x["phase"]),x.get("lease_epoch"),
            )
            for x in p.get("instances",())
        )
        return tuple(asdict(x) for x in detect_drift(self.registry,instances,desired_hosts,desired_workloads))

    def drift_with_proposals(self,p:dict[str,Any])->dict[str,Any]:
        drifts=self.drift(p)
        typed=tuple(
            Drift(
                item["kind"],
                item["subject_id"],
                item["expected"],
                item["observed"],
            )
            for item in drifts
        )
        proposals=self.repair_planner.propose_all(typed)
        return {
            "drift":drifts,
            "proposals":tuple({
                "kind":proposal.kind.value,
                "subject_id":proposal.drift.subject_id,
                "reason":proposal.reason,
                "workload_id":proposal.workload_id,
                "source_host_id":proposal.source_host_id,
                "target_host_id":proposal.target_host_id,
                "authorized":proposal.authorized,
            } for proposal in proposals),
        }

    def observe_reconciliation(self,*,now)->tuple:
        drifts=detect_drift(
            self.registry,
            self.workloads.instances(),
            self.desired_state.hosts(),
            self.desired_state.workloads(),
        )
        proposals=self.repair_planner.propose_all(drifts)
        return self.reconciliation_journal.observe(
            proposals,
            now=now,
        )

    def active_reconciliation(self)->tuple[dict[str,Any],...]:
        return tuple({
            "proposal_key":item.proposal_key,
            "drift_kind":item.drift_kind,
            "subject_id":item.subject_id,
            "expected":item.expected,
            "observed":item.observed,
            "proposal_kind":item.proposal_kind,
            "reason":item.reason,
            "first_seen":item.first_seen.isoformat(),
            "last_seen":item.last_seen.isoformat(),
            "active":item.active,
            "authorized":False,
        } for item in self.reconciliation_journal.active())

    def reconciliation_preview(self)->dict[str,Any]:
        drifts=detect_drift(
            self.registry,
            self.workloads.instances(),
            self.desired_state.hosts(),
            self.desired_state.workloads(),
        )
        proposals=self.repair_planner.propose_all(drifts)
        return {
            "desired_hosts":tuple(
                {
                    "host_id":item.host_id,
                    "lifecycle":item.lifecycle.value,
                }
                for item in self.desired_state.hosts()
            ),
            "desired_workloads":tuple(
                {
                    "workload_id":item.workload_id,
                    "host_id":item.host_id,
                }
                for item in self.desired_state.workloads()
            ),
            "observed_workloads":tuple(
                {
                    "instance_id":item.instance_id,
                    "workload_id":item.workload_id,
                    "version":item.version,
                    "host_id":item.host_id,
                    "phase":item.phase.value,
                    "lease_epoch":item.lease_epoch,
                }
                for item in self.workloads.instances()
            ),
            "drift":tuple(asdict(item) for item in drifts),
            "proposals":tuple({
                "kind":proposal.kind.value,
                "subject_id":proposal.drift.subject_id,
                "reason":proposal.reason,
                "workload_id":proposal.workload_id,
                "source_host_id":proposal.source_host_id,
                "target_host_id":proposal.target_host_id,
                "authorized":proposal.authorized,
            } for proposal in proposals),
        }

    def maintenance_receipt(self,request_id:str)->dict[str,Any]|None:
        receipt=self.maintenance_receipts.get(request_id)
        if receipt is None:
            return None
        return {
            "request_id":receipt.request_id,
            "host_id":receipt.host_id,
            "operation":receipt.operation,
            "target":receipt.target,
            "attempted_at":receipt.attempted_at.isoformat(),
            "completed_at":receipt.completed_at.isoformat(),
            "outcome":receipt.outcome.value,
            "execution_ref":receipt.execution_ref,
            "verification_ref":receipt.verification_ref,
            "observed":receipt.observed,
        }

    def migration_receipt(self,migration_id:str)->dict[str,Any]|None:
        plane=getattr(self.registry,"state_plane",None)
        if plane is None:
            return None
        return MigrationJournal(plane).get(migration_id)

    def execute_migration(self,p:dict[str,Any])->dict[str,Any]:
        if self.migration_executor is None:
            raise RuntimeError(
                "workload execution is not configured; set SOFIA_WORKLOAD_CATALOG_FILE"
            )
        contract=self._workload(p["workload"])
        managed=ManagedWorkload(
            contract,
            StateMode(p.get("state_mode","stateless")),
            checkpoint_required=bool(p.get("checkpoint_required",False)),
            failure_domain_spread=bool(p.get("failure_domain_spread",False)),
        )
        plan=MigrationPlan(
            p["migration_id"],
            managed,
            p["source_host_id"],
            p["target_host_id"],
        )
        # Deterministic preflight happens before consuming exact approval.
        self.migration_executor.preflight(plan)
        hosts={host.host_id:host for host in self.registry.hosts()}
        source=hosts.get(plan.source_host_id)
        target=hosts.get(plan.target_host_id)
        if source is None or target is None:
            raise KeyError("migration source/target must be Fleet members")
        if (
            not source.trusted or not target.trusted
            or source.lifecycle not in {HostLifecycle.ENROLLED,HostLifecycle.HEALTHY}
            or target.lifecycle not in {HostLifecycle.ENROLLED,HostLifecycle.HEALTHY}
        ):
            raise PermissionError("migration requires trusted active Fleet hosts")
        decision=self.placement.choose(
            contract,
            tuple(hosts.values()),
            activities={
                host.host_id:self.activity.state(host.host_id)
                for host in hosts.values()
            },
        )
        if plan.target_host_id not in decision.eligible_hosts:
            reason=dict(decision.rejected).get(plan.target_host_id,"not eligible")
            raise PermissionError(f"migration target is not eligible: {reason}")

        if self._workload_catalog is None:
            raise RuntimeError("workload execution catalog is unavailable")
        grant_specs=migration_remote_grant_specs(
            catalog=self._workload_catalog,
            plan=plan,
            host_node_ids={
                plan.source_host_id:source.node_id,
                plan.target_host_id:target.node_id,
            },
            local_host_id=self._local_host_id,
        )

        now=datetime.now(timezone.utc)
        exact=migration_approval_parameters(
            catalog=self._workload_catalog,
            plan=plan,
            workload_parameters=p["workload"],
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            grant_specs=grant_specs,
        )
        approval=self.execution_approvals.consume(
            approval_id=p["approval_id"],
            capability="ops.migration.execute",
            parameters=exact,
            now=now,
        )
        if approval.approved_by!="Sparks":
            raise PermissionError("migration execution approval must come from Sparks")
        with temporary_migration_remote_grants(
            state_path=self.state_path,
            specs=grant_specs,
            approved_by=approval.approved_by,
            now=now,
        ):
            result=self.migration_executor.execute(plan)
        return {
            "migration_id":result.migration_id,
            "stage":result.stage.value,
            "lease_epoch":result.lease_epoch,
            "checkpoint_ref":result.checkpoint_ref,
            "receipt_count":len(result.receipts),
        }

    def migration_plan(self,p:dict[str,Any])->dict[str,Any]:
        contract=self._workload(p["workload"])
        managed=ManagedWorkload(
            contract,
            StateMode(p.get("state_mode","stateless")),
            checkpoint_required=bool(p.get("checkpoint_required",False)),
            failure_domain_spread=bool(p.get("failure_domain_spread",False)),
        )
        plan=MigrationPlan(
            p["migration_id"],
            managed,
            p["source_host_id"],
            p["target_host_id"],
        )
        result={
            "migration_id":plan.migration_id,
            "workload_id":contract.workload_id,
            "source_host_id":plan.source_host_id,
            "target_host_id":plan.target_host_id,
            "stage":plan.stage.value,
            "state_mode":managed.state_mode.value,
            "checkpoint_required":managed.checkpoint_required,
            "failure_domain_spread":managed.failure_domain_spread,
        }
        if self._workload_catalog is None:
            return result

        hosts={host.host_id:host for host in self.registry.hosts()}
        source=hosts.get(plan.source_host_id)
        target=hosts.get(plan.target_host_id)
        if source is None or target is None:
            return result

        grant_specs=migration_remote_grant_specs(
            catalog=self._workload_catalog,
            plan=plan,
            host_node_ids={
                plan.source_host_id:source.node_id,
                plan.target_host_id:target.node_id,
            },
            local_host_id=self._local_host_id,
        )
        approval_parameters=migration_approval_parameters(
            catalog=self._workload_catalog,
            plan=plan,
            workload_parameters=p["workload"],
            source_node_id=source.node_id,
            target_node_id=target.node_id,
            grant_specs=grant_specs,
        )
        return {
            **result,
            "approval_capability":"ops.migration.execute",
            "approval_parameters":approval_parameters,
        }

class OpsCapabilitySet:
    NAMES=("ops.fleet.list","ops.fleet.get","ops.fleet.enrollment_evidence","fleet.enroll","ops.fleet.discover","network.discover","ops.telemetry.latest","ops.placement.choose","ops.drift.detect","ops.drift.propose","ops.reconcile.preview","ops.reconcile.active","ops.migration.plan","ops.migration.execute","ops.migration.receipt","ops.maintenance.receipt")
    def __init__(self,service:OpsToolService)->None: self.service=service
    def capabilities(self)->tuple[Capability,...]:
        descriptions={
            "ops.fleet.list":"List durable OPS fleet hosts and current state. Read-only.",
            "ops.fleet.get":"Inspect one durable OPS fleet host. Read-only.",
            "ops.fleet.enrollment_evidence":"Inspect exact discovery evidence for one untrusted Fleet candidate. Read-only.",
            "fleet.enroll":"Promote one exact untrusted Fleet candidate into trusted membership using one-time Sparks approval.",
            "ops.fleet.discover":"Run bounded configured Fleet/network discovery and persist only untrusted candidate observations. Safe-autonomous; never enrolls or trusts a machine.",
            "network.discover":"Observe configured network scopes and return discovered computers/devices without changing Fleet state. Read-only.",
            "ops.telemetry.latest":"Read the latest durable telemetry for one fleet host. Read-only.",
            "ops.placement.choose":"Evaluate eligible placement for a workload using current durable fleet and activity evidence. Read-only.",
            "ops.drift.detect":"Compare supplied desired state/workload placements with durable fleet evidence. Read-only.",
            "ops.drift.propose":"Compare desired state and return conservative non-authoritative repair proposals. Read-only.",
            "ops.reconcile.preview":"Preview canonical durable Fleet desired/observed drift and non-authoritative repair proposals. Read-only.",
            "ops.reconcile.active":"Read active deduplicated Fleet reconciliation observations. Read-only.",
            "ops.migration.plan":"Construct a migration plan without executing it. Read-only planning.",
            "ops.migration.execute":"Execute one exact approved workload migration through typed workload bindings.",
            "ops.migration.receipt":"Read durable workload migration stage/receipts. Read-only.",
            "ops.maintenance.receipt":"Read one durable verified maintenance receipt. Read-only.",
        }
        return tuple(Capability(name,descriptions[name]) for name in self.NAMES)
    def execute(self,request:CapabilityRequest)->Any:
        p=dict(request.parameters); name=request.capability.name
        if name=="ops.fleet.list": return self.service.fleet()
        if name=="ops.fleet.get": return self.service.host(p["host_id"])
        if name=="ops.fleet.enrollment_evidence": return self.service.enrollment_evidence(p["host_id"])
        if name=="fleet.enroll": return self.service.enroll_candidate(p)
        if name=="ops.fleet.discover": return self.service.discover_candidates()
        if name=="network.discover": return self.service.discover_network()
        if name=="ops.telemetry.latest": return self.service.telemetry_latest(p["host_id"])
        if name=="ops.placement.choose": return self.service.choose_placement(p["workload"])
        if name=="ops.drift.detect": return self.service.drift(p)
        if name=="ops.drift.propose": return self.service.drift_with_proposals(p)
        if name=="ops.reconcile.preview": return self.service.reconciliation_preview()
        if name=="ops.reconcile.active": return self.service.active_reconciliation()
        if name=="ops.migration.plan": return self.service.migration_plan(p)
        if name=="ops.migration.execute": return self.service.execute_migration(p)
        if name=="ops.migration.receipt": return self.service.migration_receipt(p["migration_id"])
        if name=="ops.maintenance.receipt": return self.service.maintenance_receipt(p["request_id"])
        raise ValueError("unsupported OPS capability")

def create_ops_tool_bindings()->tuple[CognitiveToolBinding,...]:
    def b(tool,cap,desc,props=None,required=()):
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(name=tool,description=desc,
                parameters={"type":"object","properties":props or {},"required":list(required),"additionalProperties":False}),
            capability_name=cap,
        )
    workload={"type":"object","properties":{}}
    return (
        b("list_fleet_hosts","ops.fleet.list","List OPS fleet hosts and durable state. Read-only."),
        b("inspect_fleet_host","ops.fleet.get","Inspect one OPS fleet host. Read-only.",
          {"host_id":{"type":"string"}},("host_id",)),
        b("inspect_fleet_enrollment_evidence","ops.fleet.enrollment_evidence","Inspect exact verified discovery evidence for one untrusted Fleet candidate.",
          {"host_id":{"type":"string"}},("host_id",)),
        b("enroll_fleet_candidate","fleet.enroll","Enroll one exact verified Fleet candidate. Requires a one-time Sparks approval bound to host, node, key, and endpoint.",
          {
            "host_id":{"type":"string"},
            "node_id":{"type":"string"},
            "public_key_sha256":{"type":"string"},
            "endpoint_hostname":{"type":"string"},
            "endpoint_port":{"type":"integer"},
            "approval_id":{"type":"string"},
          },
          ("host_id","node_id","public_key_sha256","endpoint_hostname","endpoint_port","approval_id")),
        b("discover_fleet_candidates","ops.fleet.discover","Run configured bounded discovery and record only untrusted candidate observations. Never enrolls or trusts a machine."),
        b("discover_network_computers","network.discover","Observe configured network scopes and return discovered computers/devices without adding them to Fleet."),
        b("inspect_fleet_telemetry","ops.telemetry.latest","Read latest durable telemetry for one fleet host. Read-only.",
          {"host_id":{"type":"string"}},("host_id",)),
        b("choose_workload_placement","ops.placement.choose","Evaluate workload placement against current fleet and foreground-activity evidence. Does not move anything.",
          {"workload":workload},("workload",)),
        b("detect_fleet_drift","ops.drift.detect","Compare supplied desired host/workload state with durable fleet evidence. Read-only.",
          {"desired_hosts":{"type":"array","items":{"type":"object"}},
           "desired_workloads":{"type":"array","items":{"type":"object"}},
           "instances":{"type":"array","items":{"type":"object"}}}),
        b("propose_fleet_repairs","ops.drift.propose","Compare Fleet drift and return conservative repair proposals without authority or execution.",
          {"desired_hosts":{"type":"array","items":{"type":"object"}},
           "desired_workloads":{"type":"array","items":{"type":"object"}},
           "instances":{"type":"array","items":{"type":"object"}}}),
        b("preview_fleet_reconciliation","ops.reconcile.preview","Preview canonical durable Fleet drift and repair proposals. Read-only."),
        b("list_active_fleet_reconciliation","ops.reconcile.active","Read active deduplicated Fleet reconciliation observations. Read-only."),
        b("plan_workload_migration","ops.migration.plan","Construct a workload migration plan without executing it.",
          {"migration_id":{"type":"string"},"workload":workload,"source_host_id":{"type":"string"},
           "target_host_id":{"type":"string"},"state_mode":{"type":"string"},
           "checkpoint_required":{"type":"boolean"},"failure_domain_spread":{"type":"boolean"}},
          ("migration_id","workload","source_host_id","target_host_id")),
        b("execute_workload_migration","ops.migration.execute","Execute one exact approved workload migration using typed host workload operations.",
          {"migration_id":{"type":"string"},"workload":workload,"source_host_id":{"type":"string"},
           "target_host_id":{"type":"string"},"state_mode":{"type":"string"},
           "checkpoint_required":{"type":"boolean"},"failure_domain_spread":{"type":"boolean"},
           "approval_id":{"type":"string"}},
          ("migration_id","workload","source_host_id","target_host_id","approval_id")),
        b("inspect_workload_migration","ops.migration.receipt","Read durable workload migration stage and receipts.",
          {"migration_id":{"type":"string"}},("migration_id",)),
        b("inspect_maintenance_receipt","ops.maintenance.receipt","Read one durable verified maintenance receipt.",
          {"request_id":{"type":"string"}},("request_id",)),
    )
