"""One-use protected owner-controlled Artemis Internal-link staging.

No model-facing execution route, no autonomous host change. Source reviewed
host network policy is immutable and pin-checked at SAFE and Artemis host.
A remote timeout yields UNCERTAIN and must not auto-retry.
"""
from __future__ import annotations
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sqlite3
from uuid import UUID,uuid4

from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capability import RemoteFleetToolService
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.ops.workshop_network import SWITCH_NAME,network_policy_digest
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.operator_stop import OperatorStopStore
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


@dataclass(frozen=True,slots=True)
class NetworkStageReceipt:
    artemis_node_id:str
    vm_id:str
    policy_sha256:str
    status:str
    request_id:str|None
    recorded_at:datetime
    guest_configured:bool=False
    lan_access_verified:bool=False
    guest_enrolled:bool=False

    def __post_init__(self):
        if (
            self.status not in {"RESERVED","HOST_STAGE_REPORTED","UNCERTAIN"}
            or self.guest_configured or self.lan_access_verified
            or self.guest_enrolled
        ):
            raise PermissionError("host staging cannot imply guest or network acceptance")


class WorkshopNetworkStageStore:
    def __init__(self,state_path:Path|str):
        self.guard=CanonicalSQLiteGuard(Path(state_path))
        with closing(self.guard.connect(timeout=10)) as db,db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS ops_workshop_internal_network_stage("
                "vm_id TEXT PRIMARY KEY,artemis_node_id TEXT NOT NULL,"
                "policy_sha256 TEXT NOT NULL,owner_approval_id TEXT NOT NULL UNIQUE,"
                "status TEXT NOT NULL CHECK(status IN "
                "('RESERVED','HOST_STAGE_REPORTED','UNCERTAIN')),"
                "request_id TEXT,recorded_at TEXT NOT NULL)"
            )

    def reserve(self,*,node:UUID,vm:UUID,approval_id:str,now:datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware owner stage time required")
        try:
            with closing(self.guard.connect(timeout=10)) as db,db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO ops_workshop_internal_network_stage "
                    "VALUES(?,?,?,?,?,?,?)",
                    (str(vm),str(node),network_policy_digest(),approval_id,
                     "RESERVED",None,now.astimezone(timezone.utc).isoformat()),
                )
        except sqlite3.IntegrityError as exc:
            # A prior RESERVED/UNCERTAIN stage, or a reused approval ID,
            # must remain an explicit authority denial. Never dispatch
            # another host mutation after an uncertain first attempt.
            raise PermissionError(
                "network stage already reserved for this VM or owner approval"
            ) from exc

    def settle(self,*,vm:UUID,status:str,request_id:str|None,now:datetime):
        if status not in {"HOST_STAGE_REPORTED","UNCERTAIN"}:
            raise ValueError("network stage cannot attest guest readiness")
        with closing(self.guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            cursor=db.execute(
                "UPDATE ops_workshop_internal_network_stage SET "
                "status=?,request_id=?,recorded_at=? "
                "WHERE vm_id=? AND status='RESERVED'",
                (status,request_id,now.astimezone(timezone.utc).isoformat(),
                 str(vm)),
            )
            if cursor.rowcount!=1:
                raise RuntimeError("network stage receipt was not reserved")

    def read(self,*,vm_id:str)->NetworkStageReceipt|None:
        with closing(self.guard.connect(timeout=10)) as db:
            row=db.execute(
                "SELECT artemis_node_id,vm_id,policy_sha256,status,"
                "request_id,recorded_at FROM ops_workshop_internal_network_stage "
                "WHERE vm_id=?",(vm_id,),
            ).fetchone()
        if row is None:return None
        return NetworkStageReceipt(
            artemis_node_id=row[0],vm_id=row[1],policy_sha256=row[2],
            status=row[3],request_id=row[4],
            recorded_at=datetime.fromisoformat(row[5]),
        )



def verified_host_stage_report(payload:object, *, vm:UUID, now:datetime)->bool:
    """Validate host-reported staging identity/freshness, NOT guest isolation.

    Failure means the host effect is UNKNOWN, not that it was rolled back.
    Only independent follow-up workshop.inspect can establish isolation.
    """
    if not isinstance(payload,dict) or not isinstance(vm,UUID):
        return False
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware source comparison time required")
    from sofia.ops.workshop_network import (
        HOST_ADDRESS,GUEST_ADDRESS,PREFIX_LENGTH,
    )
    if (
        payload.get("Outcome")!="host_internal_link_staged"
        or payload.get("VmState")!="Off"
        or payload.get("SwitchName")!=SWITCH_NAME
        or payload.get("SwitchType")!="Internal"
        or payload.get("HostIPv4")!=f"{HOST_ADDRESS}/{PREFIX_LENGTH}"
        or payload.get("GuestIPv4")!=f"{GUEST_ADDRESS}/{PREFIX_LENGTH}"
        or payload.get("GuestConfigured") is not False
        or payload.get("NatEnabled") is not False
    ):
        return False
    try:
        reported_vm=UUID(payload["VmId"])
        observed_at=datetime.fromisoformat(
            payload["ObservedAtUtc"].replace("Z","+00:00")
        )
    except (KeyError,AttributeError,TypeError,ValueError):
        return False
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        return False
    return (
        reported_vm==vm
        and timedelta(0)<=now-observed_at<=timedelta(minutes=3)
    )


def stage_approved_internal_network(
    *,state_path:Path|str,service:RemoteFleetToolService,
    artemis_node_id:str,hyperv_vm_id:str,approval_id:str,at:datetime,
)->NetworkStageReceipt:
    """One foreground owner action; all live proof remains host-observed."""
    if not isinstance(service,RemoteFleetToolService):
        raise TypeError("pinned authenticated production Fleet required")
    if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("aware owner intent time required")
    node=UUID(artemis_node_id)
    vm=UUID(hyperv_vm_id)
    if node==vm:
        raise ValueError("VM GUID must differ from Artemis enrolled node")
    if OperatorStopStore(state_path).current().active:
        raise PermissionError("operator STOP blocks Hyper-V network staging")
    params={
        "artemis_node_id":str(node),
        "vm_id":str(vm),
        "network_policy_digest":network_policy_digest(),
    }
    if not ExecutionApprovalVerifier(state_path).matches_unconsumed(
        approval_id=approval_id,
        capability="workshop.network.create",
        parameters=params,now=at,
    ):
        raise PermissionError("no exact unconsumed owner authorization for network stage")
    store=WorkshopNetworkStageStore(state_path)
    store.reserve(node=node,vm=vm,approval_id=approval_id,now=at)
    authority=DurableRemoteAuthorization(state_path)
    grant=RemoteGrant(
        uuid4(),node,"workshop.network","stage","owner:interactive",
        at+timedelta(minutes=3),
    )
    status="UNCERTAIN"
    request_id=None
    try:
        authority.add_approved_grant(grant)
        response=service.invoke(
            str(node),"workshop.network","stage",
            {
                "vm_id":str(vm),
                "network_policy_digest":network_policy_digest(),
                "approval_id":approval_id,
            },
        )
        if isinstance(response,dict):
            request_id=response.get("request_id")
            if (
                response.get("node_id")==str(node)
                and response.get("outcome")=="reported_success"
                and isinstance(response.get("message"),str)
                and len(response["message"])<4096
            ):
                import json
                host=json.loads(response["message"])
                if verified_host_stage_report(
                    host,vm=vm,now=datetime.now(timezone.utc),
                ):
                    status="HOST_STAGE_REPORTED"
    except Exception:
        # Host side effects may already exist; do not retry blindly.
        status="UNCERTAIN"
    finally:
        revoke_failed=False
        try:
            authority.revoke(grant.grant_id)
        except Exception:
            revoke_failed=True
        try:
            authority.close()
        except Exception:
            revoke_failed=True
        store.settle(
            vm=vm,status="UNCERTAIN" if revoke_failed else status,
            request_id=request_id,now=datetime.now(timezone.utc),
        )
    return store.read(vm_id=str(vm))
