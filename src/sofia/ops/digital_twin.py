"""Host-grounded, strictly simulation-only homelab dependency twin.

Sofía can study *hypothetical* faults using already-reviewed OPS Fleet nodes
and owner-declared links. No broad network probing, no Docker/VM side effects,
no real host outage assertion, no authority from synthetic results.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from sofia.ops.model import FleetHost
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

_SCENARIOS=frozenset({
    "dns_outage", "fleet_agent_unreachable", "disk_pressure",
    "sqlite_lock", "container_crash", "stale_clock",
    "weather_sensor_failure", "conflicting_node_identity",
})
_EDGE_TYPES=frozenset({"dns","fleet_transport","data","service","storage"})
_SCENARIO_EDGE_TYPES={
    "dns_outage":frozenset({"dns"}),
    "fleet_agent_unreachable":frozenset({"fleet_transport"}),
    "disk_pressure":frozenset({"storage","data"}),
    "sqlite_lock":frozenset({"data"}),
    "container_crash":frozenset({"service"}),
    "stale_clock":frozenset({"fleet_transport"}),
    "weather_sensor_failure":frozenset({"service"}),
    "conflicting_node_identity":frozenset({"fleet_transport"}),
}
# Dependency direction: child depends on parent. A parent disruption can
# hypothetically impact its direct/indirect descendants. Not actual network.
MAX_HOSTS=64
MAX_EDGES=128


@dataclass(frozen=True,slots=True)
class TwinHostObservation:
    host_id: str
    observed_at: datetime | None
    lifecycle: str
    trusted: bool
    cpu_percent: float | None
    storage_free_bytes: int | None
    source: str = "OPS_FLEET_CANONICAL"

    def __post_init__(self):
        if not isinstance(self.host_id,str) or not 1<=len(self.host_id)<=160:
            raise ValueError("bounded canonical OPS host ID required")
        if self.observed_at is not None and (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("host telemetry time must be aware")
        if self.source!="OPS_FLEET_CANONICAL":
            raise ValueError("unverified network discovery cannot enter the twin")


@dataclass(frozen=True,slots=True)
class TwinReviewedDependency:
    dependent_host_id: str
    prerequisite_host_id: str
    kind: str
    reviewed_at: datetime
    approval_ref: str
    provenance: str = "owner_declared"

    def __post_init__(self):
        if (
            self.dependent_host_id==self.prerequisite_host_id
            or any(not isinstance(x,str) or not 1<=len(x)<=160
                   for x in (self.dependent_host_id,self.prerequisite_host_id))
        ):
            raise ValueError("distinct bounded Fleet host IDs required")
        if self.kind not in _EDGE_TYPES:
            raise ValueError("unsupported dependency category")
        if self.reviewed_at.tzinfo is None or self.reviewed_at.utcoffset() is None:
            raise ValueError("review time must be aware")
        if (
            not isinstance(self.approval_ref,str)
            or not self.approval_ref.startswith("owner-ui:")
            or len(self.approval_ref)>140
        ):
            raise PermissionError("explicit reviewed dependency receipt required")
        if self.provenance!="owner_declared":
            raise PermissionError("dependency is not an observed machine fact")


@dataclass(frozen=True,slots=True)
class TwinSnapshot:
    hosts: tuple[TwinHostObservation,...]
    dependencies: tuple[TwinReviewedDependency,...]
    generated_at: datetime
    fidelity: str = "dependency_graph_v1"

    def __post_init__(self):
        if (
            self.fidelity!="dependency_graph_v1"
            or len(self.hosts)>MAX_HOSTS
            or len(self.dependencies)>MAX_EDGES
        ):
            raise ValueError("bounded explicit simulation fidelity required")
        if not isinstance(self.generated_at,datetime) or (
            self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise ValueError("snapshot needs source time")
        ids=[item.host_id for item in self.hosts]
        if len(set(ids))!=len(ids):
            raise ValueError("duplicate simulated host identity")
        if any(
            edge.dependent_host_id not in ids
            or edge.prerequisite_host_id not in ids
            for edge in self.dependencies
        ):
            raise ValueError("unreviewed or unknown dependent hosts denied")

    @property
    def digest(self)->str:
        raw=json.dumps({
            "hosts":[{
                **asdict(host),
                "observed_at":None if host.observed_at is None
                    else host.observed_at.astimezone(timezone.utc).isoformat(),
            } for host in self.hosts],
            "edges":[{
                **asdict(edge),
                "reviewed_at":edge.reviewed_at.astimezone(timezone.utc).isoformat(),
            } for edge in self.dependencies],
            "fidelity":self.fidelity,
        },sort_keys=True,separators=(",", ":"),allow_nan=False).encode("utf-8")
        return sha256(raw).hexdigest()


@dataclass(frozen=True,slots=True)
class TwinSimulationResult:
    scenario: str
    initial_host_id: str
    affected_host_ids: tuple[str,...]
    assumed_dependencies: tuple[tuple[str,str,str],...]
    telemetry_stale_or_missing: tuple[str,...]
    fidelity: str
    source_snapshot_sha256: str
    outcome: str = "modeled_only"
    may_execute_real_actions: bool = False
    may_grant_authority: bool = False
    may_claim_real_outage: bool = False


class TwinDependencyStore:
    """Canonical owner-reviewed links, never discovered by scanning the LAN."""
    def __init__(self,state_path:Path|str):
        self.path=Path(state_path)
        self._guard=CanonicalSQLiteGuard(self.path)
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS ops_twin_reviewed_dependency("
                "dependent_host_id TEXT NOT NULL,"
                "prerequisite_host_id TEXT NOT NULL,"
                "kind TEXT NOT NULL,reviewed_at TEXT NOT NULL,"
                "approval_ref TEXT NOT NULL UNIQUE,"
                "PRIMARY KEY(dependent_host_id,prerequisite_host_id,kind))"
            )

    def reviewed(self)->tuple[TwinReviewedDependency,...]:
        with closing(self._guard.connect(timeout=10)) as db:
            rows=db.execute(
                "SELECT dependent_host_id,prerequisite_host_id,kind,"
                "reviewed_at,approval_ref FROM ops_twin_reviewed_dependency "
                "ORDER BY dependent_host_id,prerequisite_host_id,kind "
                "LIMIT ?",(MAX_EDGES+1,),
            ).fetchall()
        if len(rows)>MAX_EDGES:
            raise ValueError("too many owner-reviewed topology dependencies")
        return tuple(TwinReviewedDependency(
            dependent_host_id=d,prerequisite_host_id=p,kind=k,
            reviewed_at=datetime.fromisoformat(at),approval_ref=ref,
        ) for d,p,k,at,ref in rows)

    def record_owner_review(self,edge:TwinReviewedDependency,
                            *,known_host_ids:tuple[str,...])->None:
        if not isinstance(edge,TwinReviewedDependency):
            raise TypeError("typed owner-reviewed dependency required")
        if (
            edge.dependent_host_id not in known_host_ids
            or edge.prerequisite_host_id not in known_host_ids
        ):
            raise ValueError("owner may only relate existing canonical OPS hosts")
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            size=db.execute(
                "SELECT COUNT(*) FROM ops_twin_reviewed_dependency"
            ).fetchone()[0]
            existing=db.execute(
                "SELECT approval_ref FROM ops_twin_reviewed_dependency "
                "WHERE dependent_host_id=? AND prerequisite_host_id=? AND kind=?",
                (edge.dependent_host_id,edge.prerequisite_host_id,edge.kind),
            ).fetchone()
            if existing is not None or size>=MAX_EDGES:
                raise PermissionError("reviewed dependency cannot be silently replaced")
            db.execute(
                "INSERT INTO ops_twin_reviewed_dependency VALUES(?,?,?,?,?)",
                (edge.dependent_host_id,edge.prerequisite_host_id,
                 edge.kind,edge.reviewed_at.astimezone(timezone.utc).isoformat(),
                 edge.approval_ref),
            )


def snapshot_from_ops(
    hosts: tuple[FleetHost,...],
    reviewed_edges: tuple[TwinReviewedDependency,...],
    *, at:datetime,
)->TwinSnapshot:
    if not isinstance(hosts,tuple) or any(
        not isinstance(host,FleetHost) for host in hosts
    ):
        raise TypeError("canonical OPS Fleet host objects required")
    if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("simulation observation time required")
    # Candidate/decommissioned or unauthenticated nodes cannot silently
    # become a factual input to a hosted experiment.
    hosts=tuple(
        host for host in hosts
        if host.trusted and host.lifecycle.value not in (
            "candidate","decommissioned",
        )
    )
    observations=tuple(TwinHostObservation(
        host_id=host.host_id,
        observed_at=None if host.telemetry is None else host.telemetry.observed_at,
        lifecycle=host.lifecycle.value,
        trusted=host.trusted,
        cpu_percent=None if host.telemetry is None else host.telemetry.cpu_percent,
        storage_free_bytes=(
            None if host.telemetry is None
            else host.telemetry.storage_free_bytes
        ),
    ) for host in hosts)
    ids=set(item.host_id for item in observations)
    selected=tuple(
        edge for edge in reviewed_edges
        if edge.dependent_host_id in ids and edge.prerequisite_host_id in ids
    )
    # Do not create synthetic inferred edges for hosts not currently trusted.
    return TwinSnapshot(observations,selected,at)


def simulate_hypothetical_failure(
    snapshot:TwinSnapshot, *, scenario:str, target_host_id:str,
    at:datetime,
)->TwinSimulationResult:
    if not isinstance(snapshot,TwinSnapshot):
        raise TypeError("source-grounded Fleet snapshot required")
    if scenario not in _SCENARIOS:
        raise ValueError("one of eight reviewed synthetic scenarios required")
    if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("synthetic run time required")
    known={host.host_id:host for host in snapshot.hosts}
    if target_host_id not in known:
        raise PermissionError("simulation target must be a known OPS Fleet host")
    affected={target_host_id}
    # Only explicitly reviewed edges can propagate a hypothetical fault.
    for _ in range(len(known)):
        expansion={
            edge.dependent_host_id
            for edge in snapshot.dependencies
            if (
                edge.prerequisite_host_id in affected
                and edge.kind in _SCENARIO_EDGE_TYPES[scenario]
            )
        }
        updated=affected|expansion
        if updated==affected:
            break
        affected=updated
    missing=tuple(sorted(
        host.host_id
        for host in snapshot.hosts
        if host.host_id in affected and (
            host.observed_at is None
            or not timedelta(0)<=at-host.observed_at<=timedelta(minutes=30)
        )
    ))
    return TwinSimulationResult(
        scenario=scenario,initial_host_id=target_host_id,
        affected_host_ids=tuple(sorted(affected)),
        assumed_dependencies=tuple(
            (edge.dependent_host_id,edge.prerequisite_host_id,edge.kind)
            for edge in snapshot.dependencies
            if edge.dependent_host_id in affected
            and edge.prerequisite_host_id in affected
            and edge.kind in _SCENARIO_EDGE_TYPES[scenario]
        ),
        telemetry_stale_or_missing=missing,
        fidelity=snapshot.fidelity,
        source_snapshot_sha256=snapshot.digest,
    )


@dataclass(frozen=True,slots=True)
class TwinExperimentDisposition:
    decision: str
    reasons: tuple[str,...]
    requires_operator_review: bool = True
    may_launch_real_experiment: bool = False


def assess_twin_experiment(
    *,snapshot:TwinSnapshot,result:TwinSimulationResult,
    at:datetime,verified_hypothesis:bool=True,
    repeated_failure_count:int=0,host_cpu_budget_ms:int=100,
    observed_cpu_ms:float=0,
) -> TwinExperimentDisposition:
    """Stop synthetic research when evidence is not adequate for interpretation."""
    if not isinstance(snapshot,TwinSnapshot) or not isinstance(result,TwinSimulationResult):
        raise TypeError("source-grounded hypothetical experiment required")
    if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("aware experiment time required")
    if (
        type(repeated_failure_count) is not int
        or repeated_failure_count<0 or repeated_failure_count>100
        or type(host_cpu_budget_ms) is not int
        or not 1<=host_cpu_budget_ms<=10000
        or type(observed_cpu_ms) not in {int,float}
        or not 0<=observed_cpu_ms<=100_000
    ):
        raise ValueError("bounded experiment failure and compute observations required")
    reasons=[]
    if not verified_hypothesis:
        reasons.append("hypothesis lacks independent falsification rule")
    if not timedelta(0)<=at-snapshot.generated_at<=timedelta(minutes=5):
        reasons.append("source topology snapshot expired or future-dated")
    if result.telemetry_stale_or_missing:
        reasons.append("source telemetry stale or missing")
    if repeated_failure_count>=3:
        reasons.append("repeated failures without independent learning evidence")
    if observed_cpu_ms>host_cpu_budget_ms:
        reasons.append("simulation would displace foreground resource budget")
    if len(snapshot.dependencies)==0:
        reasons.append("no owner-reviewed dependency edges; only an isolated node is modeled")
    return TwinExperimentDisposition(
        decision="ABANDON_RESEARCH" if reasons else "REVIEW_SYNTHETIC_ONLY",
        reasons=tuple(reasons),
    )


class TwinExperimentStore:
    """Immutable bounded reproducibility capsule in canonical state."""

    def __init__(self,state_path:Path|str):
        self.path=Path(state_path)
        self._guard=CanonicalSQLiteGuard(self.path)
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS ops_twin_experiment_capsule("
                "capsule_id TEXT PRIMARY KEY, capsule_sha256 TEXT NOT NULL,"
                "source_sha256 TEXT NOT NULL, capsule_json TEXT NOT NULL,"
                "created_at TEXT NOT NULL)"
            )

    def record(self,*,snapshot:TwinSnapshot,result:TwinSimulationResult,
               disposition:TwinExperimentDisposition,at:datetime)->str:
        if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("aware experiment receipt time required")
        if result.source_snapshot_sha256!=snapshot.digest:
            raise PermissionError("simulation result did not come from supplied snapshot")
        if disposition.may_launch_real_experiment:
            raise PermissionError("synthetic result cannot authorize action")
        capsule={
            "schema":"homelab-twin-capsule-v1",
            "source":"OPS_FLEET_CANONICAL and owner_declared_edges",
            "tool_version":"sofia.ops.digital_twin:dependency_graph_v1",
            "fixed_seed":0,
            "fidelity":snapshot.fidelity,
            "input_digest":snapshot.digest,
            "observed_input_hosts":tuple({
                "host_id":item.host_id,
                "telemetry_at":item.observed_at.isoformat()
                    if item.observed_at is not None else None,
                "lifecycle":item.lifecycle,
                "trusted":item.trusted,
            } for item in snapshot.hosts),
            "owner_reviewed_edges":tuple({
                "dependent_host_id":edge.dependent_host_id,
                "prerequisite_host_id":edge.prerequisite_host_id,
                "kind":edge.kind,
                "reviewed_at":edge.reviewed_at.isoformat(),
                "receipt":edge.approval_ref,
            } for edge in snapshot.dependencies),
            "scenario":result.scenario,
            "target_host_id":result.initial_host_id,
            "result":asdict(result),
            "disposition":asdict(disposition),
            "evaluator":"hypothetical dependency reachability only",
            "real_world_implementation":"NOT EXECUTED",
            "approved_host_action":False,
        }
        document=json.dumps(
            capsule,sort_keys=True,separators=(",", ":"),allow_nan=False,
        )
        if len(document)>65_536:
            raise ValueError("experiment capsule exceeds reviewed bound")
        digest=sha256(document.encode("utf-8")).hexdigest()
        capsule_id="twin:"+uuid4().hex
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO ops_twin_experiment_capsule VALUES(?,?,?,?,?)",
                (capsule_id,digest,snapshot.digest,document,
                 at.astimezone(timezone.utc).isoformat()),
            )
            db.execute(
                "DELETE FROM ops_twin_experiment_capsule WHERE capsule_id NOT IN "
                "(SELECT capsule_id FROM ops_twin_experiment_capsule "
                "ORDER BY created_at DESC,capsule_id DESC LIMIT 32)"
            )
        return capsule_id

    def recent(self,*,limit:int=8)->tuple[dict,...]:
        if type(limit) is not int or not 1<=limit<=32:
            raise ValueError("capsule limit must be 1..32")
        with closing(self._guard.connect(timeout=10)) as db:
            rows=db.execute(
                "SELECT capsule_id,capsule_sha256,capsule_json "
                "FROM ops_twin_experiment_capsule "
                "ORDER BY created_at DESC,capsule_id DESC LIMIT ?",(limit,),
            ).fetchall()
        reports=[]
        for capsule_id,digest,raw in rows:
            if sha256(raw.encode("utf-8")).hexdigest()!=digest:
                raise RuntimeError("synthetic experiment capsule hash corruption")
            item=json.loads(raw)
            reports.append({
                "capsule_id":capsule_id,"capsule_sha256":digest,
                "scenario":item["scenario"],
                "target_host_id":item["target_host_id"],
                "fidelity":item["fidelity"],
                "decision":item["disposition"]["decision"],
                "actual_host_action":False,
                "source_digest":item["input_digest"],
            })
        return tuple(reports)


def run_digital_twin_scenario(*,service,scenario:str,target_host_id:str,
                              at:datetime)->dict:
    """Read actual canonical OPS host inventory; compute ONLY hypothetical effects."""
    hosts=tuple(service.registry.hosts())
    edges=TwinDependencyStore(service.state_path).reviewed()
    current=snapshot_from_ops(hosts,edges,at=at)
    result=simulate_hypothetical_failure(
        current,scenario=scenario,target_host_id=target_host_id,at=at,
    )
    disposition=assess_twin_experiment(
        snapshot=current,result=result,at=at,
    )
    capsule_id=TwinExperimentStore(service.state_path).record(
        snapshot=current,result=result,disposition=disposition,at=at,
    )
    report=asdict(result)
    report["experiment_capsule_id"]=capsule_id
    report["review_disposition"]=asdict(disposition)
    report["source_host_count"]=len(current.hosts)
    report["source_reviewed_edge_count"]=len(current.dependencies)
    report["scientific_limit"]=(
        "Synthetic dependency-graph response, NOT an observed outage, "
        "network reachability measurement, acceptance test or permission grant."
    )
    return report


def read_digital_twin_fleet(*,service,at:datetime)->dict:
    hosts=tuple(service.registry.hosts())
    edges=TwinDependencyStore(service.state_path).reviewed()
    snapshot=snapshot_from_ops(hosts,edges,at=at)
    return {
        "source":"canonical OPS Fleet",
        "fidelity":snapshot.fidelity,
        "digest":snapshot.digest,
        "hosts":tuple({
            "host_id":item.host_id,
            "lifecycle":item.lifecycle,
            "trusted":item.trusted,
            "telemetry_at":(
                item.observed_at.isoformat() if item.observed_at else None
            ),
        } for item in snapshot.hosts),
        "reviewed_dependency_count":len(snapshot.dependencies),
        "observed_network_topology":"UNKNOWN (no automatic probing)",
        "simulation_only":True,
        "may_execute_real_actions":False,
    }
