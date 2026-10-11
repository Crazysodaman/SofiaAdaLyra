"""Owner-approved Hyper-V Debian installer bootstrap for an existing Hephaestus VM.

The approved blank VM already exists on Artemis. This code neither creates
a VM nor asks a nonexistent guest OS/agent to execute commands. A host
controller boots an owner-provided, SHA-256 reviewed unattended Debian ISO.
Actual guest install completion and subsequent Fleet enrollment are separate
attestations and independent owner decisions.

Runtime state remains in canonical sofia.db on Venus, with one-use SAFE
approval and explicit per-node Fleet grant. No unattended background launch.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID,uuid4

from sofia.distributed.authorization import RemoteGrant
from sofia.distributed.capability import RemoteFleetToolService
from sofia.distributed.durable import DurableRemoteAuthorization
from sofia.ops.workshop_handoff import (
    WorkshopBlankVMHandoff, WorkshopHandoffStore,
    inspect_blank_vm_handoff, observed_owner_vm,
)
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.operator_stop import OperatorStopStore
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


@dataclass(frozen=True,slots=True)
class WorkshopInstallerBootReceipt:
    plan_id: str
    handoff_fingerprint: str
    artemis_node_id: str
    exact_vm_id: str
    status: str
    remote_request_id: str | None
    observed_vm_state: str | None
    recorded_at: datetime
    os_installed: bool = False
    fleet_enrolled: bool = False

    def __post_init__(self):
        if self.status not in {"RESERVED","INSTALLER_BOOT_STARTED","UNCERTAIN"}:
            raise ValueError("installer state is not a verified OS state")
        if self.os_installed or self.fleet_enrolled:
            raise PermissionError("boot receipts cannot assert an installed OS or Fleet trust")


class WorkshopInstallerBootStore:
    def __init__(self,state_path:Path|str):
        self.path=Path(state_path)
        self._guard=CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db,db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS ops_workshop_installer_boot(
                    plan_id TEXT PRIMARY KEY,
                    handoff_fingerprint TEXT NOT NULL,
                    artemis_node_id TEXT NOT NULL,
                    hyperv_vm_id TEXT NOT NULL,
                    owner_approval_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK (
                        status IN ('RESERVED','INSTALLER_BOOT_STARTED','UNCERTAIN')
                    ),
                    remote_request_id TEXT,
                    observed_vm_state TEXT,
                    reserved_at TEXT NOT NULL,
                    settled_at TEXT
                )"""
            )

    def _connect(self):
        db=self._guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def reserve(self,*,handoff:WorkshopBlankVMHandoff,
                approval_id:str,at:datetime)->None:
        if not isinstance(handoff,WorkshopBlankVMHandoff):
            raise TypeError("owner handoff required")
        if not isinstance(approval_id,str) or not approval_id.strip() or len(approval_id)>160:
            raise ValueError("exact owner approval ID required")
        if not isinstance(at,datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("timezone-aware reservation required")
        with closing(self._connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO ops_workshop_installer_boot VALUES(?,?,?,?,?,?,?,?,?,?)",
                (handoff.plan_id,handoff.fingerprint,
                 str(handoff.artemis_node_id),str(handoff.hyperv_vm_id),
                 approval_id,"RESERVED",None,None,
                 at.astimezone(timezone.utc).isoformat(),None),
            )

    def settle(self,*,plan_id:str,status:str,
               request_id:str|None,vm_state:str|None,at:datetime)->None:
        if status not in {"INSTALLER_BOOT_STARTED","UNCERTAIN"}:
            raise ValueError("cannot declare guest installed from Hyper-V boot")
        with closing(self._connect()) as db,db:
            db.execute("BEGIN IMMEDIATE")
            changed=db.execute(
                "UPDATE ops_workshop_installer_boot SET "
                "status=?,remote_request_id=?,observed_vm_state=?,settled_at=? "
                "WHERE plan_id=? AND status='RESERVED'",
                (status,request_id,vm_state,
                 at.astimezone(timezone.utc).isoformat(),plan_id),
            )
            if changed.rowcount!=1:
                raise RuntimeError("installer boot reservation no longer owned")

    def inspect(self,*,plan_id:str)->WorkshopInstallerBootReceipt|None:
        with closing(self._connect()) as db:
            row=db.execute(
                "SELECT plan_id,handoff_fingerprint,artemis_node_id,"
                "hyperv_vm_id,status,remote_request_id,observed_vm_state,"
                "reserved_at,settled_at FROM ops_workshop_installer_boot "
                "WHERE plan_id=?",(plan_id,),
            ).fetchone()
        if row is None:return None
        return WorkshopInstallerBootReceipt(
            plan_id=row[0],handoff_fingerprint=row[1],
            artemis_node_id=row[2],exact_vm_id=row[3],
            status=row[4],remote_request_id=row[5],
            observed_vm_state=row[6],
            recorded_at=datetime.fromisoformat(row[8] or row[7]),
        )


def reviewed_handoff_from_store(state_path:Path|str,*,plan_id:str,
                                now:datetime)->tuple[WorkshopBlankVMHandoff,dict]:
    """Retrieve immutable source-bound handoff, not a model-made approval."""
    state_path=Path(state_path)
    WorkshopHandoffStore(state_path)
    guard=CanonicalSQLiteGuard(state_path)
    with closing(guard.connect(timeout=10)) as db:
        row=db.execute(
            "SELECT plan_hash,snapshot_json FROM "
            "ops_workshop_blank_vm_handoff WHERE plan_id=?",
            (plan_id,),
        ).fetchone()
    if row is None:
        raise PermissionError("owner-reviewed handoff does not exist")
    payload=json.loads(row[1])
    plan=payload["plan"]
    handoff=WorkshopBlankVMHandoff(
        plan_id=plan["plan_id"],
        artemis_node_id=UUID(plan["artemis_node_id"]),
        hyperv_vm_id=UUID(plan["hyperv_vm_id"]),
        expected_os_disk_path=plan["expected_os_disk_path"],
        installer_iso_path=plan["installer_iso_path"],
        installer_sha256=plan["installer_sha256"],
        approved_boot_media_sha256=plan["approved_boot_media_sha256"],
        created_at=datetime.fromisoformat(plan["created_at"]),
        expires_at=datetime.fromisoformat(plan["expires_at"]),
        owner_declares_empty_disk=plan["owner_declares_empty_disk"],
    )
    if (
        handoff.plan_id!=plan_id or handoff.fingerprint!=row[0]
        or payload["review"]["fingerprint"]!=handoff.fingerprint
        or not payload["review"]["ready_for_owner_bootstrap_review"]
        or not handoff.created_at<=now<handoff.expires_at
    ):
        raise PermissionError("handoff expired, modified or not eligible")
    observed_time=datetime.fromisoformat(payload["observation"]["observed_at"])
    if not timedelta(0)<=now-observed_time<=timedelta(minutes=3):
        raise PermissionError("host observation stale; repeat owner handoff review")
    return handoff,payload


def start_owner_approved_installer(
    *,
    state_path:Path|str,
    remote_service:RemoteFleetToolService,
    plan_id:str,
    approval_id:str,
    now:datetime,
)->WorkshopInstallerBootReceipt:
    """Exact, one-shot host installer START, not an installed guest receipt."""
    if not isinstance(remote_service,RemoteFleetToolService):
        raise TypeError("pinned-mTLS production Fleet service required")
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware owner decision required")
    state_path=Path(state_path)
    if OperatorStopStore(state_path).current().active:
        raise PermissionError("operator stop blocks VM installer bootstrap")
    handoff,previous=reviewed_handoff_from_store(
        state_path,plan_id=plan_id,now=now,
    )
    node=str(handoff.artemis_node_id)
    live=remote_service.invoke(
        node,"workshop.inspect","blank_vm",{},
    )
    if (
        not isinstance(live,dict) or live.get("node_id")!=node
        or live.get("outcome")!="reported_success"
        or not isinstance(live.get("message"),str)
        or len(live["message"])>65_536
    ):
        raise PermissionError("fresh authenticated VM inspection failed")
    observation=observed_owner_vm(json.loads(live["message"]))
    review=inspect_blank_vm_handoff(handoff,observation,now=now)
    if not review.ready_for_owner_bootstrap_review:
        raise PermissionError("reviewed blank VM is no longer eligible")

    # Compare material host facts with the owner-reviewed snapshot, excluding
    # the observation timestamp. Changing disks/VM resources requires a NEW
    # explicit review, even when both values fit broad safety ranges.
    from dataclasses import asdict
    material=asdict(observation)
    material["hyperv_vm_id"]=str(observation.hyperv_vm_id)
    material.pop("observed_at",None)
    recorded=dict(previous["observation"])
    recorded.pop("observed_at",None)
    for key in ("os_disk_paths","os_disk_sizes_gib","nic_switches","dvd_paths",
                "firmware_boot_order"):
        if isinstance(material.get(key),tuple):
            material[key]=json.loads(json.dumps(material[key]))
    if material!=recorded:
        raise PermissionError("VM changed since reviewed handoff; re-inspect")
    media=remote_service.invoke(
        node,"workshop.inspect","media",
        {"image_path":handoff.installer_iso_path},
    )
    if (
        not isinstance(media,dict) or media.get("node_id")!=node
        or media.get("outcome")!="reported_success"
        or not isinstance(media.get("message"),str)
        or len(media["message"])>4096
    ):
        raise PermissionError("approved unattended media unavailable")
    digest=json.loads(media["message"])
    if (
        not isinstance(digest,dict)
        or digest.get("sha256")!=handoff.installer_sha256
        or digest.get("kind")!=".iso"
    ):
        raise PermissionError("installer media digest/type has changed")
    parameters={
        "artemis_node_id":node,
        "vm_id":str(handoff.hyperv_vm_id),
        "disk_path":handoff.expected_os_disk_path,
        "iso_path":handoff.installer_iso_path,
        "iso_sha256":handoff.installer_sha256,
        "handoff_fingerprint":handoff.fingerprint,
    }
    if not ExecutionApprovalVerifier(state_path).matches_unconsumed(
        approval_id=approval_id,capability="workshop.guest.bootstrap",
        parameters=parameters,now=now,
    ):
        raise PermissionError("exact unconsumed owner installer grant required")

    # The canonical SAFE verifier is consumed by Fleet.invoke at the actual
    # transport boundary, even if a different caller somehow gains this grant.
    store=WorkshopInstallerBootStore(state_path)
    store.reserve(handoff=handoff,approval_id=approval_id,at=now)
    authority=DurableRemoteAuthorization(state_path)
    grant=RemoteGrant(
        uuid4(),handoff.artemis_node_id,
        "workshop.bootstrap","start","Sparks",
        now+timedelta(minutes=3),
    )
    remote_id=None
    state=None
    status="UNCERTAIN"
    try:
        authority.add_approved_grant(grant)
        result=remote_service.invoke(
            node,"workshop.bootstrap","start",
            {
                "vm_id":str(handoff.hyperv_vm_id),
                "disk_path":handoff.expected_os_disk_path,
                "iso_path":handoff.installer_iso_path,
                "iso_sha256":handoff.installer_sha256,
                "handoff_fingerprint":handoff.fingerprint,
                "approval_id":approval_id,
            },
        )
        if not isinstance(result,dict):
            raise RuntimeError("unparseable protected Hyper-V boot receipt")
        remote_id=result.get("request_id")
        if (
            result.get("node_id")==node
            and result.get("outcome")=="reported_success"
            and isinstance(result.get("message"),str)
            and len(result["message"])<4096
        ):
            received=json.loads(result["message"])
            if (
                isinstance(received,dict)
                and received.get("Outcome")=="installer_boot_started"
                and received.get("VmId")==str(handoff.hyperv_vm_id)
                and received.get("MediaSha256")==handoff.installer_sha256
                and received.get("OsInstalled") is False
                and received.get("FleetEnrolled") is False
            ):
                status="INSTALLER_BOOT_STARTED"
                state=received.get("State")
    except Exception:
        # After an installer boot request begins, transport errors can hide
        # a real host effect. Preserve UNCERTAIN, NEVER automatically retry.
        status="UNCERTAIN"
    finally:
        try:
            authority.revoke(grant.grant_id)
        finally:
            authority.close()
        store.settle(
            plan_id=handoff.plan_id,status=status,
            request_id=remote_id,vm_state=state,
            at=datetime.now(timezone.utc),
        )
    return store.inspect(plan_id=handoff.plan_id)



def inspect_existing_vm_installer(
    *,
    state_path:Path|str,
    remote_service:RemoteFleetToolService,
    plan_id:str,
    now:datetime,
)->dict:
    """Observe actual Artemis host state after boot, without a guest agent.

    Host integration services alone are not proof of a completed Debian OS,
    configured worker, valid guest identity or successful offline installer.
    """
    if not isinstance(remote_service,RemoteFleetToolService):
        raise TypeError("pinned Fleet service required")
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware inspection required")
    path=Path(state_path)
    store=WorkshopInstallerBootStore(path)
    receipt=store.inspect(plan_id=plan_id)
    if receipt is None:
        raise PermissionError("installer has not been initiated for this handoff")
    node=receipt.artemis_node_id
    answer=remote_service.invoke(
        node,"workshop.inspect","installer_status",{},
    )
    if (
        not isinstance(answer,dict)
        or answer.get("node_id")!=node
        or answer.get("outcome")!="reported_success"
        or not isinstance(answer.get("message"),str)
        or len(answer["message"])>16_384
        or not isinstance(answer.get("request_id"),str)
    ):
        raise RuntimeError("Artemis installer status could not be observed")
    observed=json.loads(answer["message"])
    if (
        not isinstance(observed,dict)
        or observed.get("Name")!="Hephaestus"
        or observed.get("VmId")!=receipt.exact_vm_id
        or observed.get("OsInstalled") is not None
        or observed.get("FleetEnrolled") is not None
        or not isinstance(observed.get("State"),str)
        or not isinstance(observed.get("ObservedAtUtc"),str)
    ):
        raise PermissionError("host status VM identity or evidence boundary changed")
    moment=datetime.fromisoformat(
        observed["ObservedAtUtc"].replace("Z","+00:00")
    )
    if (
        moment.tzinfo is None or moment.utcoffset() is None
        or not timedelta(0)<=now-moment<=timedelta(minutes=3)
    ):
        raise PermissionError("stale or future host status observation")
    # Store the actual host report in canonical state, bounded and separated
    # from any claim that the guest has finished installing.
    guard=CanonicalSQLiteGuard(path)
    with closing(guard.connect(timeout=10)) as db,db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS ops_workshop_installer_observation("
            "request_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL,"
            "host_report_json TEXT NOT NULL, observed_at TEXT NOT NULL)"
        )
        raw=json.dumps(
            {
                "source":"artemis_authenticated_hyperv_host",
                "vm_id":observed["VmId"],
                "state":observed["State"],
                "mounted_media":observed.get("Media"),
                "integration_services":observed.get("Services"),
                "boot_order":observed.get("BootOrder"),
                "os_installed":"UNKNOWN",
                "guest_identity":"UNKNOWN",
                "fleet_enrolled":"UNKNOWN",
            },separators=(",", ":"),sort_keys=True,
        )
        if len(raw)>12_000:
            raise ValueError("host observation too large")
        db.execute(
            "INSERT INTO ops_workshop_installer_observation VALUES(?,?,?,?)",
            (answer["request_id"],plan_id,raw,moment.astimezone(timezone.utc).isoformat()),
        )
        db.execute(
            "DELETE FROM ops_workshop_installer_observation WHERE "
            "request_id NOT IN (SELECT request_id FROM "
            "ops_workshop_installer_observation ORDER BY observed_at DESC,"
            "request_id DESC LIMIT 32)"
        )
    return {
        "plan_id":plan_id,
        "vm_id":observed["VmId"],
        "host_power_state":observed["State"],
        "mounted_installer_media":observed.get("Media"),
        "integration_services_observed":observed.get("Services"),
        "firmware_boot_order":observed.get("BootOrder"),
        "os_installed":"UNKNOWN",
        "guest_authenticated":"UNKNOWN",
        "fleet_enrolled":"UNKNOWN",
        "fleet_receipt":answer["request_id"],
    }
