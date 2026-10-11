"""Owner-created Hyper-V Hephaestus handoff, separate from VM provisioning.

The VM has no OS and no agent. All inspection is host-side and identity-bound;
owner declaration of an empty disk is NOT technical evidence of emptiness.
The guarded bootstrap boundary may only act after independent Level-4 consent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import PureWindowsPath
from uuid import UUID

from sofia.ops.workshop_provision import (
    EXPECTED_SWITCH, EXPECTED_VM, _path, _SHA,
)


@dataclass(frozen=True, slots=True)
class WorkshopBlankVMHandoff:
    plan_id: str
    artemis_node_id: UUID
    hyperv_vm_id: UUID
    expected_os_disk_path: str
    installer_iso_path: str
    installer_sha256: str
    approved_boot_media_sha256: str
    created_at: datetime
    expires_at: datetime
    owner_declares_empty_disk: bool
    guest_name: str = EXPECTED_VM
    switch_name: str = EXPECTED_SWITCH
    vm_generation: int = 2
    min_vcpu: int = 2
    max_vcpu: int = 4
    min_memory_mb: int = 4096
    max_memory_mb: int = 8192
    min_disk_gib: int = 60
    max_disk_gib: int = 128
    desired_os: str = "Debian"
    installation_style: str = "approved_unattended_gen2_iso"
    existing_vm_only: bool = True
    may_enroll_fleet: bool = False
    may_modify_network: bool = False
    reviewed_boot_order_policy: str = "installer_dvd_first_only_after_owner_approval"

    def __post_init__(self):
        from re import fullmatch
        if not isinstance(self.plan_id, str) or not fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,120}", self.plan_id,
        ):
            raise ValueError("bounded unique handoff plan ID required")
        if (
            not isinstance(self.artemis_node_id, UUID)
            or not isinstance(self.hyperv_vm_id, UUID)
            or self.artemis_node_id == self.hyperv_vm_id
        ):
            raise ValueError("distinct authenticated Artemis and VM UUIDs required")
        if self.guest_name != EXPECTED_VM or self.switch_name != EXPECTED_SWITCH:
            raise PermissionError("only Hephaestus on dedicated private switch allowed")
        if (
            self.vm_generation != 2 or self.desired_os != "Debian"
            or self.installation_style != "approved_unattended_gen2_iso"
        ):
            raise PermissionError("only reviewed unattended Debian Hyper-V Gen2 install")
        if (
            not self.existing_vm_only or self.may_enroll_fleet
            or self.may_modify_network
        ):
            raise PermissionError("blank VM handoff cannot create VMs, enroll or change network")
        if self.reviewed_boot_order_policy != "installer_dvd_first_only_after_owner_approval":
            raise PermissionError("unreviewed Hyper-V firmware boot order changes denied")
        if (
            self.min_vcpu != 2 or self.max_vcpu != 4
            or self.min_memory_mb != 4096 or self.max_memory_mb != 8192
            or self.min_disk_gib != 60 or self.max_disk_gib != 128
        ):
            raise ValueError("fixed reviewed Hephaestus resource limits required")
        if type(self.owner_declares_empty_disk) is not bool:
            raise TypeError("explicit owner empty-disk declaration required")
        if not self.owner_declares_empty_disk:
            raise PermissionError("owner has not authorized overwrite of the empty OS disk")
        disk=_path(self.expected_os_disk_path)
        iso=_path(self.installer_iso_path)
        if (
            disk.suffix.casefold() != ".vhdx"
            or iso.suffix.casefold() != ".iso"
            or disk == iso or disk in iso.parents or iso in disk.parents
        ):
            raise ValueError("exact distinct VHDX OS disk and offline ISO required")
        for label,digest in (
            ("installer_sha256",self.installer_sha256),
            ("approved_boot_media_sha256",self.approved_boot_media_sha256),
        ):
            if not isinstance(digest,str) or _SHA.fullmatch(digest) is None:
                raise ValueError(f"{label} must be independently pinned SHA-256")
        for name in ("created_at","expires_at"):
            dt=getattr(self,name)
            if not isinstance(dt,datetime) or dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError("aware UTC handoff timestamps required")
        age=self.expires_at-self.created_at
        if not timedelta(0)<age<=timedelta(minutes=30):
            raise ValueError("handoff expires within 30 minutes")

    def exact_manifest(self) -> dict:
        data=asdict(self)
        data["artemis_node_id"]=str(self.artemis_node_id)
        data["hyperv_vm_id"]=str(self.hyperv_vm_id)
        for key in ("created_at","expires_at"):
            data[key]=data[key].astimezone(timezone.utc).isoformat()
        return data

    @property
    def fingerprint(self) -> str:
        encoded=json.dumps(
            self.exact_manifest(),sort_keys=True,separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkshopVMObservation:
    """From exact-name host-side Get-VM/Get-VHD/Get-VMSwitch, not a guest agent."""

    hyperv_vm_id: UUID
    name: str
    generation: int
    state: str
    processor_count: int | None
    startup_memory_mb: int | None
    os_disk_paths: tuple[str,...]
    os_disk_sizes_gib: tuple[int | None,...]
    nic_switches: tuple[tuple[str,str], ...]  # (name, host-observed type)
    dvd_paths: tuple[str,...]
    secure_boot: str | None
    observed_at: datetime
    firmware_boot_order: tuple[str,...] = ()

    def __post_init__(self):
        if not isinstance(self.hyperv_vm_id,UUID) or not isinstance(self.name,str):
            raise ValueError("observed exact VM identity required")
        if type(self.generation) is not int or self.generation not in (1,2):
            raise ValueError("valid observed Hyper-V VM generation required")
        for name in ("processor_count","startup_memory_mb"):
            val=getattr(self,name)
            if val is not None and (type(val) is not int or val<0):
                raise ValueError(f"invalid observed {name}")
        if (
            not isinstance(self.os_disk_paths,tuple)
            or not isinstance(self.os_disk_sizes_gib,tuple)
            or len(self.os_disk_paths)!=len(self.os_disk_sizes_gib)
            or not isinstance(self.nic_switches,tuple)
            or not isinstance(self.dvd_paths,tuple)
        ):
            raise ValueError("bounded observed disks, switches and media required")
        for size in self.os_disk_sizes_gib:
            if size is not None and (type(size) is not int or size < 0):
                raise ValueError("observed virtual disk size invalid")
        if (
            not isinstance(self.firmware_boot_order,tuple)
            or len(self.firmware_boot_order)>8
            or any(not isinstance(item,str) or not item
                   for item in self.firmware_boot_order)
        ):
            raise ValueError("bounded observed Hyper-V firmware boot order required")
        if (
            not isinstance(self.observed_at,datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("host observation time required")


@dataclass(frozen=True, slots=True)
class WorkshopHandoffReview:
    fingerprint: str
    ready_for_owner_bootstrap_review: bool
    blockers: tuple[str,...]
    may_install: bool = False
    may_enroll: bool = False


def inspect_blank_vm_handoff(
    handoff: WorkshopBlankVMHandoff,
    observation: WorkshopVMObservation | None,
    *, now: datetime,
) -> WorkshopHandoffReview:
    """Conservative and *non-executable* acceptance of owner-created blank VM."""
    if not isinstance(handoff,WorkshopBlankVMHandoff):
        raise TypeError("typed owner-created VM handoff required")
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("trusted time required")
    blockers=[]
    if not handoff.created_at<=now<handoff.expires_at:
        blockers.append("handoff expired")
    if observation is None:
        blockers.append("Artemis VM observation missing")
        return WorkshopHandoffReview(handoff.fingerprint,False,tuple(blockers))
    if not isinstance(observation,WorkshopVMObservation):
        raise TypeError("typed Hyper-V VM observation required")
    if not timedelta(0)<=now-observation.observed_at<=timedelta(minutes=3):
        blockers.append("Hyper-V VM observation stale or in future")
    if observation.hyperv_vm_id != handoff.hyperv_vm_id:
        blockers.append("VM GUID mismatch; name alone never authorizes installation")
    if observation.name != EXPECTED_VM:
        blockers.append("observed VM is not exact Hephaestus")
    if observation.generation != 2:
        blockers.append("Debian installation needs verified Generation-2 VM")
    if observation.state.casefold() not in ("off","offlined"):
        blockers.append("VM must be powered off for approved boot-media handoff")
    if (
        observation.processor_count is None
        or not handoff.min_vcpu <= observation.processor_count <= handoff.max_vcpu
    ):
        blockers.append("vCPU unknown or outside reviewed resource budget")
    if (
        observation.startup_memory_mb is None
        or not handoff.min_memory_mb <= observation.startup_memory_mb <= handoff.max_memory_mb
    ):
        blockers.append("RAM unknown or outside reviewed resource budget")
    try:
        expected_disk=str(_path(handoff.expected_os_disk_path)).casefold()
        observed_disk=tuple(
            str(_path(value)).casefold() for value in observation.os_disk_paths
        )
    except (TypeError,ValueError):
        blockers.append("host reported invalid OS disk path")
    else:
        if observed_disk != (expected_disk,):
            blockers.append("OS disk count/path mismatch; never replace existing disks")
    if (
        len(observation.os_disk_sizes_gib)!=1
        or observation.os_disk_sizes_gib[0] is None
        or not handoff.min_disk_gib <= observation.os_disk_sizes_gib[0] <= handoff.max_disk_gib
    ):
        blockers.append("OS disk size unknown or outside reviewed budget")
    if observation.nic_switches != ((EXPECTED_SWITCH,"Private"),):
        blockers.append("exactly one private Hephaestus NIC required; no LAN/NAT/external")
    if observation.dvd_paths:
        blockers.append("unexpected existing DVD attachment; refuse replacement")
    if not observation.firmware_boot_order:
        blockers.append("existing boot order unobserved; cannot preserve recovery evidence")
    if observation.secure_boot not in ("Off","On-MicrosoftUEFICertificateAuthority"):
        blockers.append("unreviewed secure boot configuration for Debian Gen2")
    # A declared blank disk cannot be cryptographically proven empty by VM
    # metadata; an independent Level-4 confirmation is always required.
    return WorkshopHandoffReview(
        handoff.fingerprint, not blockers, tuple(blockers),
        may_install=False,may_enroll=False,
    )


def observed_owner_vm(payload: dict) -> WorkshopVMObservation:
    """Strictly decode Artemis' read-only exact-name Hyper-V observation."""
    if not isinstance(payload,dict) or payload.get("Name")!=EXPECTED_VM:
        raise ValueError("host did not observe exact Hephaestus name")
    required=("VmId","Generation","State","Processors","StartupMemoryBytes",
              "Disks","NetworkAdapters","DvdPaths","ObservedAtUtc")
    if any(key not in payload for key in required):
        raise ValueError("incomplete Hyper-V VM observation")
    try:
        vm_id=UUID(str(payload["VmId"]))
        moment=datetime.fromisoformat(str(payload["ObservedAtUtc"]).replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("unverified VM UUID or observation time") from exc
    raw_disks=payload["Disks"]
    raw_networks=payload["NetworkAdapters"]
    raw_dvds=payload["DvdPaths"]
    if (
        not isinstance(raw_disks,list) or len(raw_disks)>8
        or not isinstance(raw_networks,list) or len(raw_networks)>8
        or not isinstance(raw_dvds,list) or len(raw_dvds)>8
    ):
        raise ValueError("Hyper-V disk, NIC or DVD inventory unbounded")
    disks=[]; sizes=[]
    for row in raw_disks:
        if not isinstance(row,dict) or not isinstance(row.get("Path"),str):
            raise ValueError("Hyper-V disk path unknown")
        disks.append(str(_path(row["Path"])))
        raw_size=row.get("Size")
        sizes.append(
            raw_size//(1024**3)
            if type(raw_size) is int and raw_size>=0 else None
        )
    network=[]
    for row in raw_networks:
        if (
            not isinstance(row,dict)
            or not isinstance(row.get("Name"),str)
            or not isinstance(row.get("SwitchType"),str)
        ):
            raise ValueError("Hyper-V switch identity unknown")
        network.append((row["Name"],row["SwitchType"]))
    if any(not isinstance(item,str) for item in raw_dvds):
        raise ValueError("invalid observed mounted media path")
    memory=payload["StartupMemoryBytes"]
    memory_mb=(
        memory//(1024**2)
        if type(memory) is int and memory>=0 else None
    )
    boot_order=payload.get("BootOrder")
    if (
        not isinstance(boot_order,list) or len(boot_order)>8
        or any(not isinstance(item,str) for item in boot_order)
    ):
        raise ValueError("Hyper-V firmware boot sources not observed")
    secure_boot=payload.get("SecureBoot")
    template=payload.get("SecureBootTemplate")
    if secure_boot=="Off":
        security="Off"
    elif secure_boot=="On" and template=="MicrosoftUEFICertificateAuthority":
        security="On-MicrosoftUEFICertificateAuthority"
    else:
        security=None
    return WorkshopVMObservation(
        hyperv_vm_id=vm_id,name=payload["Name"],
        generation=payload["Generation"],state=payload["State"],
        processor_count=payload["Processors"],
        startup_memory_mb=memory_mb,
        os_disk_paths=tuple(disks),
        os_disk_sizes_gib=tuple(sizes),
        nic_switches=tuple(network),
        dvd_paths=tuple(raw_dvds),
        secure_boot=security,observed_at=moment,
        firmware_boot_order=tuple(boot_order),
    )



@dataclass(frozen=True, slots=True)
class WorkshopHandoffPreview:
    handoff: WorkshopBlankVMHandoff
    observation: WorkshopVMObservation
    review: WorkshopHandoffReview
    observed_boot_sha256: str | None
    fleet_vm_receipt: str
    fleet_media_receipt: str | None

    def readable(self) -> str:
        return "\n".join((
            "OWNER-CREATED HEPHAESTUS: HYPER-V HANDOFF REVIEW ONLY",
            "VM exact GUID: "+str(self.handoff.hyperv_vm_id),
            "Artemis enrolled node UUID: "+str(self.handoff.artemis_node_id),
            "Handoff SHA-256: "+self.handoff.fingerprint,
            "VM state: "+self.observation.state,
            "OS target: Debian / Gen2 / UNATTENDED offline installer",
            "Disk: "+self.handoff.expected_os_disk_path,
            "Unattended boot media: "+self.handoff.installer_iso_path,
            "Media expected: "+self.handoff.approved_boot_media_sha256,
            "Media observed: "+str(self.observed_boot_sha256 or "UNKNOWN"),
            "Network: "+str(self.observation.nic_switches),
            "No self-created guest, network change, or implicit Fleet enrollment.",
            "Owner confirmed empty OS disk: "+str(self.handoff.owner_declares_empty_disk),
            "Eligible for separate boot approval: "
            +str(self.review.ready_for_owner_bootstrap_review),
            "May install now: FALSE; separate exact Level-4 grant required",
            "Blockers: "+("; ".join(self.review.blockers) or "none at read-only boundary"),
            "OS installed: UNKNOWN; guest heartbeats require later trust decision.",
        ))


def preview_owner_created_vm(
    *,
    remote_service,
    artemis_node_id: str,
    exact_vm_id: str,
    disk_path: str,
    boot_media_path: str,
    boot_media_sha256: str,
    owner_confirms_blank_disk: bool,
    at: datetime,
) -> WorkshopHandoffPreview:
    """Authenticated read-only handoff, no arbitrary hypervisor control."""
    from sofia.distributed.capability import RemoteFleetToolService
    from uuid import uuid4
    if not isinstance(remote_service,RemoteFleetToolService):
        raise TypeError("canonical pinned-mTLS Fleet service required")
    node=UUID(artemis_node_id)
    vm=UUID(exact_vm_id)
    handoff=WorkshopBlankVMHandoff(
        plan_id="hephaestus:handoff:"+uuid4().hex,
        artemis_node_id=node,hyperv_vm_id=vm,
        expected_os_disk_path=disk_path,
        installer_iso_path=boot_media_path,
        installer_sha256=boot_media_sha256,
        approved_boot_media_sha256=boot_media_sha256,
        created_at=at,expires_at=at+timedelta(minutes=15),
        owner_declares_empty_disk=owner_confirms_blank_disk,
    )
    response=remote_service.invoke(str(node),"workshop.inspect","blank_vm",{})
    if (
        not isinstance(response,dict)
        or response.get("node_id")!=str(node)
        or response.get("outcome")!="reported_success"
        or not isinstance(response.get("request_id"),str)
        or not isinstance(response.get("message"),str)
        or len(response["message"])>65_536
    ):
        raise RuntimeError("Artemis blank VM identity inspection unavailable")
    obs=observed_owner_vm(json.loads(response["message"]))
    review=inspect_blank_vm_handoff(handoff,obs,now=at)
    observed_hash=None
    media_receipt=None
    try:
        media=remote_service.invoke(
            str(node),"workshop.inspect","media",
            {"image_path":boot_media_path},
        )
        if (
            isinstance(media,dict)
            and media.get("node_id")==str(node)
            and media.get("outcome")=="reported_success"
            and isinstance(media.get("message"),str)
            and len(media["message"])<4096
        ):
            result=json.loads(media["message"])
            if isinstance(result,dict) and isinstance(result.get("sha256"),str):
                observed_hash=result["sha256"]
                media_receipt=media.get("request_id")
    except (PermissionError,ValueError,RuntimeError,LookupError,OSError):
        pass
    blockers=list(review.blockers)
    if observed_hash is None:
        blockers.append("offline unattended image SHA-256 not observed on Artemis")
    elif observed_hash != handoff.approved_boot_media_sha256:
        blockers.append("boot media SHA-256 changed or mismatched")
    final=WorkshopHandoffReview(
        handoff.fingerprint,not blockers,tuple(blockers),
        may_install=False,may_enroll=False,
    )
    return WorkshopHandoffPreview(
        handoff=handoff,observation=obs,review=final,
        observed_boot_sha256=observed_hash,
        fleet_vm_receipt=response["request_id"],
        fleet_media_receipt=media_receipt,
    )



class WorkshopHandoffStore:
    """Only non-executable owner-review evidence in the canonical sofia.db."""

    def __init__(self, state_path):
        from pathlib import Path
        from contextlib import closing
        from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
        self._guard=CanonicalSQLiteGuard(Path(state_path))
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS ops_workshop_blank_vm_handoff("
                "plan_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL,"
                "snapshot_json TEXT NOT NULL, observed_at TEXT NOT NULL)"
            )

    def record(self, preview: WorkshopHandoffPreview):
        from contextlib import closing
        if not isinstance(preview,WorkshopHandoffPreview):
            raise TypeError("observed pinned-mTLS handoff preview required")
        if (
            preview.review.fingerprint!=preview.handoff.fingerprint
            or preview.observation.hyperv_vm_id!=preview.handoff.hyperv_vm_id
        ):
            raise PermissionError("handoff observation and plan identity differ")
        o=asdict(preview.observation)
        o["hyperv_vm_id"]=str(preview.observation.hyperv_vm_id)
        o["observed_at"]=preview.observation.observed_at.astimezone(timezone.utc).isoformat()
        serialized=json.dumps({
            "plan":preview.handoff.exact_manifest(),
            "observation":o,
            "review":asdict(preview.review),
            "media_sha256":preview.observed_boot_sha256,
            "fleet_vm_receipt":preview.fleet_vm_receipt,
            "fleet_media_receipt":preview.fleet_media_receipt,
            "kind":"owner_provided_vm_handoff_read_only",
        },sort_keys=True,separators=(",", ":"))
        if len(serialized)>65_536:
            raise ValueError("bounded handoff evidence required")
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute(
                "SELECT snapshot_json FROM ops_workshop_blank_vm_handoff "
                "WHERE plan_id=?",(preview.handoff.plan_id,),
            ).fetchone()
            if existing is not None:
                if existing[0]!=serialized:
                    raise PermissionError("reviewed handoff cannot be rewritten")
                return
            db.execute(
                "INSERT INTO ops_workshop_blank_vm_handoff VALUES(?,?,?,?)",
                (preview.handoff.plan_id,preview.handoff.fingerprint,
                 serialized,o["observed_at"]),
            )
            db.execute(
                "DELETE FROM ops_workshop_blank_vm_handoff "
                "WHERE plan_id NOT IN (SELECT plan_id FROM "
                "ops_workshop_blank_vm_handoff ORDER BY observed_at DESC,"
                "plan_id DESC LIMIT 12)"
            )

    def read_model_brief(self)->dict:
        from contextlib import closing
        with closing(self._guard.connect(timeout=10)) as db:
            row=db.execute(
                "SELECT snapshot_json FROM ops_workshop_blank_vm_handoff "
                "ORDER BY observed_at DESC,plan_id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "status":"unobserved",
                "reason":"No owner-created Hyper-V VM handoff observed.",
                "may_install":False,"may_enroll":False,
            }
        data=json.loads(row[0])
        plan=data["plan"]
        review=data["review"]
        now=datetime.now(timezone.utc)
        expiry=datetime.fromisoformat(plan["expires_at"])
        observed=datetime.fromisoformat(data["observation"]["observed_at"])
        current=(
            now<expiry
            and timedelta(0)<=now-observed<=timedelta(minutes=3)
        )
        return {
            "status":"reviewed_read_only" if current else "expired_or_stale",
            "plan_id":plan["plan_id"],
            "plan_fingerprint_sha256":review["fingerprint"],
            "artemis_node_id":plan["artemis_node_id"],
            "guest_name":plan["guest_name"],
            "vm_guid":plan["hyperv_vm_id"],
            "state":data["observation"]["state"],
            "network":data["observation"]["nic_switches"],
            "boot_media_digest":data["media_sha256"],
            "ready_for_bootstrap_review":(
                bool(review["ready_for_owner_bootstrap_review"])
                if current else False
            ),
            "blockers":(
                tuple(review["blockers"])
                if current else ("VM review expired; inspect Artemis again",)
            ),
            "may_install":False,"may_enroll":False,
            "note":"No guest OS or agent proven. A separate owner Level-4 install "
                   "receipt is required; Fleet enrollment is a later decision.",
        }
