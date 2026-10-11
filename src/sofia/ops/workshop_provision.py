"""Immutable, source-grounded Hyper-V workshop provision planning.

This module never creates a VM or grants host authority. Plans for Artemis
are reusable by the separately protected Hyper-V executor after owner consent,
independent Fleet identity binding, resource proof and image attestation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import PureWindowsPath
import re


_SHA = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")
_DRIVE = re.compile(r"^[A-Za-z]:\\")
EXPECTED_VM = "Hephaestus"
EXPECTED_SWITCH = "Sofia-Hephaestus-Private"


def _path(value: str) -> PureWindowsPath:
    if (
        not isinstance(value, str)
        or not 4 <= len(value) <= 240
        or not _DRIVE.match(value)
        or "/" in value
        or any(ch in value for ch in "\r\n\x00'\";|*?<>")
    ):
        raise ValueError("exact local Windows path required, never UNC or shell")
    path = PureWindowsPath(value)
    if ".." in path.parts or "." in path.parts:
        raise ValueError("VM path may not traverse parent or current directories")
    if path.anchor == str(path):
        raise ValueError("VM path must be below a dedicated directory")
    return path


@dataclass(frozen=True, slots=True)
class WorkshopProvisionPlan:
    plan_id: str
    hypervisor_host_id: str
    hypervisor_version: str
    guest_name: str
    vm_root: str
    installer_image_path: str
    installer_image_sha256: str
    switch_name: str
    vcpu: int
    memory_mb: int
    disk_gib: int
    duration_minutes: int
    created_at: datetime
    expires_at: datetime
    hypervisor: str = "Hyper-V"
    guest_os: str = "Debian"
    firmware_generation: int = 2
    network_mode: str = "private"
    cleanup_scope: str = "plan_owned_assets_only"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.plan_id, str)
            or _SAFE_ID.fullmatch(self.plan_id) is None
        ):
            raise ValueError("bounded unique plan ID required")
        if (
            not isinstance(self.hypervisor_host_id, str)
            or _SAFE_ID.fullmatch(self.hypervisor_host_id) is None
        ):
            raise ValueError("cryptographically attested Artemis Fleet host ID required")
        if (
            not isinstance(self.hypervisor_version, str)
            or not 1 <= len(self.hypervisor_version) <= 100
            or any(c in self.hypervisor_version for c in "\r\n\x00")
        ):
            raise ValueError("observed Hyper-V version is required")
        if self.hypervisor != "Hyper-V":
            raise ValueError("Artemis host is Hyper-V, other hypervisors denied")
        if self.guest_name != EXPECTED_VM:
            raise ValueError("Hephaestus is the only reviewed workshop VM name")
        if self.guest_os != "Debian" or self.firmware_generation != 2:
            raise ValueError("reviewed Debian Generation-2 guest only")
        if self.network_mode != "private" or self.switch_name != EXPECTED_SWITCH:
            raise ValueError("only the dedicated private Hyper-V switch is permitted")
        if self.cleanup_scope != "plan_owned_assets_only":
            raise ValueError("cleanup cannot affect other VMs or host assets")
        root = _path(self.vm_root)
        media = _path(self.installer_image_path)
        if root == media or root in media.parents:
            raise ValueError("installer image must not be inside disposable VM root")
        if _SHA.fullmatch(self.installer_image_sha256) is None:
            raise ValueError("independently verified installer SHA-256 required")
        if type(self.vcpu) is not int or not 1 <= self.vcpu <= 4:
            raise ValueError("workshop vCPU must be 1..4")
        if type(self.memory_mb) is not int or not 2048 <= self.memory_mb <= 8192:
            raise ValueError("workshop RAM must be in 2..8 GiB")
        if type(self.disk_gib) is not int or not 32 <= self.disk_gib <= 128:
            raise ValueError("workshop disk must be 32..128 GiB")
        if type(self.duration_minutes) is not int or not 1 <= self.duration_minutes <= 1440:
            raise ValueError("bounded lab runtime required")
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
            or not isinstance(self.expires_at, datetime)
            or self.expires_at.tzinfo is None
            or self.expires_at.utcoffset() is None
            or not timedelta(0) < self.expires_at - self.created_at <= timedelta(minutes=30)
        ):
            raise ValueError("short-lived timezone-aware provision plan required")

    def exact_manifest(self) -> dict:
        payload = asdict(self)
        payload["created_at"] = self.created_at.astimezone(timezone.utc).isoformat()
        payload["expires_at"] = self.expires_at.astimezone(timezone.utc).isoformat()
        return payload

    @property
    def fingerprint_sha256(self) -> str:
        raw = json.dumps(
            self.exact_manifest(),sort_keys=True,separators=(",", ":"),
        ).encode("utf-8")
        return sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkshopHostObservation:
    """Host facts measured by authenticated, read-only Artemis operations."""

    host_id: str
    hypervisor_version: str
    logical_processors: int | None
    free_memory_mb: int | None
    total_memory_mb: int | None
    free_disk_gib: int | None
    existing_vm_names: tuple[str, ...]
    existing_switches: tuple[tuple[str, str], ...]
    image_sha256: str | None
    observed_at: datetime

    def __post_init__(self):
        if (
            not isinstance(self.host_id, str)
            or _SAFE_ID.fullmatch(self.host_id) is None
            or not isinstance(self.hypervisor_version, str)
            or not self.hypervisor_version
        ):
            raise ValueError("independent host identity and hypervisor version required")
        for name in ("logical_processors","free_memory_mb","total_memory_mb","free_disk_gib"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"observed {name} must be nonnegative or unknown")
        if (
            not isinstance(self.existing_vm_names, tuple)
            or not isinstance(self.existing_switches, tuple)
            or any(not isinstance(x, str) for x in self.existing_vm_names)
            or any(not isinstance(x, tuple) or len(x) != 2 for x in self.existing_switches)
        ):
            raise ValueError("observed VMs/switches must be exact tuples")
        if self.image_sha256 is not None and _SHA.fullmatch(self.image_sha256) is None:
            raise ValueError("observed installer digest invalid")
        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("host observation needs a source timestamp")



def observed_hyperv_host(
    *,
    payload: dict,
    authenticated_fleet_host_id: str,
    vm_root: str,
    image_sha256: str | None = None,
) -> WorkshopHostObservation:
    """Normalize only a completed Fleet mTLS Artemis host observation.

    The host identity comes from trusted Fleet transport, never the remote
    JSON. Missing/malformed fields remain unknown or are refused, never
    promoted into invented host capacity.
    """
    if not isinstance(payload, dict) or (
        payload.get("Platform") != "Hyper-V"
        or payload.get("HypervisorAvailable") is not True
    ):
        raise ValueError("Hyper-V not verified by host")
    root = _path(vm_root)
    version = payload.get("WindowsHostVersion")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("observed Windows Hyper-V build unknown")
    reported_at = payload.get("ObservedAtUtc")
    if not isinstance(reported_at, str):
        raise ValueError("Hyper-V host reported no timestamp")
    observed_at = datetime.fromisoformat(reported_at.replace("Z","+00:00"))
    if observed_at.tzinfo is None:
        raise ValueError("Hyper-V host timestamp lacks timezone")

    def count(name):
        val=payload.get(name)
        return val if type(val) is int and val >= 0 else None

    raw_vms=payload.get("Machines")
    raw_switches=payload.get("Switches")
    raw_drives=payload.get("Drives")
    if (
        not isinstance(raw_vms,list) or len(raw_vms)>256
        or not isinstance(raw_switches,list) or len(raw_switches)>64
        or not isinstance(raw_drives,list) or len(raw_drives)>32
    ):
        raise ValueError("unbounded or unknown Hyper-V host topology")
    vm_names=[]
    switches=[]
    for entry in raw_vms:
        if not isinstance(entry,dict) or not isinstance(entry.get("Name"),str):
            raise ValueError("Hyper-V VM name unobserved")
        vm_names.append(entry["Name"])
    for entry in raw_switches:
        if not isinstance(entry,dict) or any(
            not isinstance(entry.get(key),str) for key in ("Name","SwitchType")
        ):
            raise ValueError("Hyper-V switch name/type unobserved")
        switches.append((entry["Name"],entry["SwitchType"]))
    disk_free=None
    required_drive=root.drive.casefold()
    for drive in raw_drives:
        if not isinstance(drive,dict):
            raise ValueError("Hyper-V disk capacity unobserved")
        if str(drive.get("Drive","")).casefold()==required_drive:
            value=drive.get("FreeBytes")
            if type(value) is int and value>=0:
                disk_free=value//(1024**3)
            break
    return WorkshopHostObservation(
        host_id=authenticated_fleet_host_id,
        hypervisor_version="WindowsHyperV/"+version,
        logical_processors=count("LogicalProcessors"),
        free_memory_mb=count("FreeMemoryMB"),
        total_memory_mb=count("TotalMemoryMB"),
        free_disk_gib=disk_free,
        existing_vm_names=tuple(vm_names),
        existing_switches=tuple(switches),
        image_sha256=image_sha256,
        observed_at=observed_at,
    )


@dataclass(frozen=True, slots=True)
class WorkshopPreflight:
    plan_fingerprint_sha256: str
    review_eligible: bool
    blockers: tuple[str, ...]
    may_provision: bool = False


def inspect_workshop_plan(
    plan: WorkshopProvisionPlan, observation: WorkshopHostObservation | None,
    *, at: datetime,
) -> WorkshopPreflight:
    """Conservative read-only review; never confers VM creation authority."""
    if not isinstance(plan, WorkshopProvisionPlan):
        raise TypeError("exact typed workshop plan required")
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("trusted aware preflight time required")
    blockers = []
    if not plan.created_at <= at < plan.expires_at:
        blockers.append("plan expired or not yet active")
    if observation is None:
        blockers.append("Artemis read-only host observation missing")
        return WorkshopPreflight(plan.fingerprint_sha256,False,tuple(blockers))
    if not isinstance(observation, WorkshopHostObservation):
        raise TypeError("independent host observation required")
    if observation.host_id != plan.hypervisor_host_id:
        blockers.append("Fleet host identity changed or mismatched")
    if observation.hypervisor_version != plan.hypervisor_version:
        blockers.append("Hyper-V host version changed")
    age = at - observation.observed_at
    if age < timedelta(0) or age > timedelta(minutes=5):
        blockers.append("host capacity observation stale or in the future")
    if observation.logical_processors is None or observation.logical_processors < plan.vcpu + 2:
        blockers.append("logical CPU headroom unknown/insufficient")
    if observation.free_memory_mb is None or observation.free_memory_mb < plan.memory_mb + 8192:
        blockers.append("Artemis guest/host memory reserve unknown/insufficient")
    if observation.free_disk_gib is None or observation.free_disk_gib < plan.disk_gib + 40:
        blockers.append("Hyper-V volume free capacity unknown/insufficient")
    if observation.total_memory_mb is None or observation.total_memory_mb < 16384:
        blockers.append("host physical RAM inventory unknown/insufficient")
    if any(name.casefold() == plan.guest_name.casefold() for name in observation.existing_vm_names):
        blockers.append("Hephaestus VM name collision; no adoption or overwrite")
    for name, switch_type in observation.existing_switches:
        if name.casefold() == plan.switch_name.casefold():
            if switch_type.casefold() != "private":
                blockers.append("expected private switch collides with non-private network")
            else:
                blockers.append("existing switch ownership unproven; no silent adoption")
    if observation.image_sha256 is None:
        blockers.append("installer image hash has not been observed by Artemis")
    elif observation.image_sha256 != plan.installer_image_sha256:
        blockers.append("installer image digest differs from reviewed plan")
    return WorkshopPreflight(
        plan.fingerprint_sha256, not blockers, tuple(blockers),
        may_provision=False,
    )
