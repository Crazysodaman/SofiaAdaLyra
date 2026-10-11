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
    if observation.secure_boot not in ("Off","On-MicrosoftUEFICertificateAuthority"):
        blockers.append("unreviewed secure boot configuration for Debian Gen2")
    # A declared blank disk cannot be cryptographically proven empty by VM
    # metadata; an independent Level-4 confirmation is always required.
    return WorkshopHandoffReview(
        handoff.fingerprint, not blockers, tuple(blockers),
        may_install=False,may_enroll=False,
    )
