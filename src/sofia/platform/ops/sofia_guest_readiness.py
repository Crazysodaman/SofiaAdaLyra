"""Read-only Hyper-V production guest inventory admission for future VM Sofia.

A Hyper-V VM object is NOT proof of an installed Debian guest, working guest
agent, or authority to run the canonical database. Never infer those from a
boot disk, VM state, attached ISO, or untrusted guest-reported name.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any
from uuid import UUID

VM_NAME = "Sofia"


@dataclass(frozen=True, slots=True)
class SofiaGuestReadiness:
    observed_vm_id: str | None
    inventory_eligible_for_review: bool
    host_blockers: tuple[str, ...]
    guest_os_verified: bool = False
    migration_authorized: bool = False
    may_activate_canonical_writer: bool = False


def review_sofia_guest_inventory(
    observation: Mapping[str, Any] | None,
) -> SofiaGuestReadiness:
    """Review bounded host metadata; never authorize provisioning or cutover.

    The independent enrolled Debian guest and privileged fencing broker will
    later supply signed evidence. This host-level read alone cannot do either.
    """
    issues: list[str] = []
    if observation is None:
        return SofiaGuestReadiness(None, False, ("hyperv_vm_not_observed",))
    if not isinstance(observation, Mapping):
        raise TypeError("typed Hyper-V observation required")
    if observation.get("Name") != VM_NAME:
        issues.append("wrong_production_vm_name")
    vm_id = observation.get("VmId")
    try:
        parsed = str(UUID(vm_id)) if isinstance(vm_id, str) else None
    except ValueError:
        parsed = None
    if parsed is None:
        issues.append("hyperv_vm_id_missing_or_invalid")
    generation = observation.get("Generation")
    if type(generation) is not int or generation != 2:
        issues.append("hyperv_generation_2_not_verified")
    cpu = observation.get("Processors")
    if type(cpu) is not int or cpu < 1:
        issues.append("guest_vcpu_not_observed")
    memory = observation.get("StartupMemoryBytes")
    if type(memory) is not int or memory < 512 * 1024 * 1024:
        issues.append("guest_memory_below_minimum_or_unknown")
    disks = observation.get("Disks")
    if (
        not isinstance(disks, list) or not disks or
        any(
            not isinstance(disk, dict) or
            not isinstance(disk.get("Path"), str) or
            not disk["Path"].strip() or
            type(disk.get("Size")) is not int or disk["Size"] <= 0
            for disk in disks
        )
    ):
        issues.append("guest_boot_disk_not_verified")
    nics = observation.get("NetworkAdapters")
    if (
        not isinstance(nics, list) or not nics or
        any(
            not isinstance(nic, dict)
            or not isinstance(nic.get("SwitchType"), str)
            or nic["SwitchType"] not in {"Internal", "Private", "External"}
            for nic in nics
        )
    ):
        issues.append("guest_network_topology_not_observed")
    # External connectivity is possible, but needs separately verified ACLs
    # and approved mTLS routing. An adapter attached to an external switch
    # does not constitute firewall/identity approval.
    if isinstance(nics, list) and any(
        isinstance(nic, dict) and nic.get("SwitchType") == "External"
        for nic in nics
    ):
        issues.append("external_virtual_switch_requires_operator_review")

    return SofiaGuestReadiness(
        observed_vm_id=parsed,
        inventory_eligible_for_review=not issues,
        host_blockers=tuple(issues),
        guest_os_verified=False,
        migration_authorized=False,
        may_activate_canonical_writer=False,
    )
