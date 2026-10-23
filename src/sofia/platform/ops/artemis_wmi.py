"""Exactly scoped, read-only Hyper-V CIM observer for Artemis LocalService.

Windows Hyper-V PowerShell cmdlets require a broader privilege than
LocalService has, while Msvm_ComputerSystem can be read through the
root/virtualization/v2 CIM provider on this host. This is an identity/state
*observation* only: no guest/VM resource inventory or writer-fencing evidence.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from uuid import UUID

from sofia.modules.integrations.hyperv import HyperVAdapter


class ArtemisWmiObservationError(RuntimeError):
    """Scoped Hyper-V WMI query returned missing or untrusted data."""


class ArtemisWmiObserver:
    """Read only the single pinned Hyper-V VM; never discover arbitrary VMs."""

    def __init__(
        self,
        *,
        expected_vm_id: UUID,
        vm_name: str = "Sofia",
        runner: Callable[[str], str] | None = None,
    ) -> None:
        if not isinstance(expected_vm_id, UUID):
            raise TypeError("pinned Hyper-V VM UUID required")
        if vm_name != "Sofia":
            raise ArtemisWmiObservationError("only the canonical Sofia VM is permitted")
        self._vm_id = expected_vm_id
        self._name = vm_name
        self._runner = runner if runner is not None else HyperVAdapter._powershell

    def __call__(self) -> Mapping[str, Any]:
        # This string can interpolate only a UUID supplied by the
        # root-controlled config; never pass user text into PowerShell.
        pinned_id = str(self._vm_id)
        script = (
            "$ErrorActionPreference='Stop'; "
            "$vm=@(Get-CimInstance -Namespace 'root/virtualization/v2' "
            "-ClassName 'Msvm_ComputerSystem' "
            f"-Filter \"Name='{pinned_id}'\" -ErrorAction Stop); "
            "if($vm.Count -ne 1){throw 'EXACT_VM_GUID_NOT_OBSERVED'}; "
            "$item=$vm[0]; "
            "if([string]$item.ElementName -cne 'Sofia'){throw 'VM_NAME_MISMATCH'}; "
            "[pscustomobject]@{ "
            "VmId=[string]$item.Name; "
            "Name=[string]$item.ElementName; "
            "EnabledState=[int]$item.EnabledState "
            "} | ConvertTo-Json -Compress"
        )
        raw = self._runner(script)
        if not isinstance(raw, str) or len(raw) > 8192:
            raise ArtemisWmiObservationError("Hyper-V WMI response is unbounded")
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ArtemisWmiObservationError("Hyper-V WMI response invalid") from exc
        if not isinstance(data, dict) or set(data) != {
            "VmId", "Name", "EnabledState"
        }:
            raise ArtemisWmiObservationError("unexpected Hyper-V WMI response shape")
        try:
            vm_id = UUID(data["VmId"])
        except (TypeError, AttributeError, ValueError) as exc:
            raise ArtemisWmiObservationError("invalid Hyper-V WMI VM UUID") from exc
        if vm_id != self._vm_id or data["Name"] != self._name:
            raise ArtemisWmiObservationError("Hyper-V VM identity changed")
        enabled_state = data["EnabledState"]
        if type(enabled_state) is not int or not 0 <= enabled_state <= 65535:
            raise ArtemisWmiObservationError("Hyper-V WMI EnabledState unavailable")

        # Hyper-V WMI EnabledState is deliberately not translated into an
        # asserted fully running/ready Linux guest. We cannot inspect its
        # network switch, VHD contents, installed OS or signed state through
        # this restricted WMI class.
        return {
            "host_inventory": {
                "VmId": str(vm_id),
                "Name": self._name,
                "State": f"WMI.EnabledState:{enabled_state}",
            },
            "read_only_review": {
                "inventory_eligible_for_review": False,
                "host_blockers": [
                    "wmi_identity_and_enabled_state_only",
                    "full_hyperv_resources_and_network_not_verified",
                ],
                "may_activate_canonical_writer": False,
            },
            "guest_os_installed": "unverified",
            "canonical_writer_active": "unverified",
            "activation_authorized": False,
            "observation_source": "hyperv_wmi_read_only",
        }
