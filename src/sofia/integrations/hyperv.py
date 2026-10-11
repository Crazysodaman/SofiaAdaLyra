"""Typed local Hyper-V adapter for Windows hosts."""
from __future__ import annotations
import json,platform,subprocess
from typing import Any

from sofia.ops.workshop_policy import CANONICAL_RUNTIME_VM_NAME

class HyperVError(RuntimeError): pass

class HyperVAdapter:
    def __init__(self,runner=None)->None:
        self._runner=runner or self._powershell
    def vms(self)->list[dict[str,Any]]:
        raw=self._runner("Get-VM | Select-Object Name,State,Status,CPUUsage,MemoryAssigned,Uptime | ConvertTo-Json -Compress")
        data=json.loads(raw) if raw.strip() else []
        if isinstance(data,dict): data=[data]
        if not isinstance(data,list): raise HyperVError("invalid Get-VM response")
        return data
    def vm(self,name:str)->dict[str,Any]|None:
        self._name(name)
        raw=self._runner(f"Get-VM -Name {self._ps(name)} -ErrorAction Stop | Select-Object Name,State,Status,CPUUsage,MemoryAssigned,Uptime | ConvertTo-Json -Compress")
        data=json.loads(raw) if raw.strip() else None
        if data is not None and not isinstance(data,dict): raise HyperVError("invalid VM response")
        return data
    def start(self,name:str)->None:
        self._name(name)
        self._reject_canonical_runtime_management(name)
        self._runner(f"Start-VM -Name {self._ps(name)} -ErrorAction Stop | Out-Null")
    def stop(self,name:str,*,force:bool=False)->None:
        self._name(name)
        self._reject_canonical_runtime_management(name)
        cmd=f"Stop-VM -Name {self._ps(name)} -ErrorAction Stop"
        if force: cmd+=" -TurnOff"
        self._runner(cmd+" | Out-Null")
    def workshop_handoff_vm(self) -> dict[str, Any]:
        """Read the exact OWNER-CREATED Hephaestus VM, no hypervisor writes.

        The VM may have no OS, guest tools, interpreter, IP or Fleet agent.
        This operation runs on Artemis with its own Hyper-V host credentials.
        """
        command=(
            "$ErrorActionPreference='Stop'; "
            "$v=Get-VM -Name 'Hephaestus' -ErrorAction Stop; "
            "if ($v.Name -cne 'Hephaestus') { throw 'VM identity mismatch' }; "
            "$disks=@(Get-VMHardDiskDrive -VMName 'Hephaestus' -ErrorAction Stop "
            "| ForEach-Object { "
            "$disk=Get-VHD -Path $_.Path -ErrorAction Stop; "
            "[pscustomobject]@{Path=[string]$_.Path; Size=[long]$disk.Size} }); "
            "$nics=@(Get-VMNetworkAdapter -VMName 'Hephaestus' "
            "-ErrorAction Stop | ForEach-Object { "
            "$sw=Get-VMSwitch -Name $_.SwitchName -ErrorAction Stop; "
            "[pscustomobject]@{Name=[string]$_.SwitchName; "
            "SwitchType=[string]$sw.SwitchType} }); "
            "$dvd=@(Get-VMDvdDrive -VMName 'Hephaestus' "
            "-ErrorAction Stop | Where-Object {$_.Path} | "
            "ForEach-Object {[string]$_.Path}); "
            "$fw=Get-VMFirmware -VMName 'Hephaestus' -ErrorAction Stop; "
            "[pscustomobject]@{ "
            "VmId=[string]$v.Id; Name=[string]$v.Name; "
            "Generation=[int]$v.Generation; State=[string]$v.State; "
            "Processors=[int]$v.ProcessorCount; "
            "StartupMemoryBytes=[long]$v.MemoryStartup; "
            "Disks=$disks; NetworkAdapters=$nics; DvdPaths=$dvd; "
            "SecureBoot=[string]$fw.SecureBoot; "
            "SecureBootTemplate=[string]$fw.SecureBootTemplate; "
            "ObservedAtUtc=[DateTime]::UtcNow.ToString('o') "
            "} | ConvertTo-Json -Depth 5 -Compress"
        )
        raw=self._runner(command)
        try:
            result=json.loads(raw)
        except (ValueError,TypeError) as exc:
            raise HyperVError("invalid read-only Hephaestus VM observation") from exc
        if not isinstance(result,dict) or result.get("Name")!="Hephaestus":
            raise HyperVError("wrong Hyper-V VM identity observed")
        return result

    def workshop_host(self) -> dict[str, Any]:
        """Host-only read-only Hyper-V capacity and topology observation.

        It cannot create a VM, install an OS, make a switch, change a disk
        or access the canonical Sofía guest. Output remains untrusted until
        the Fleet mTLS node identity and observation freshness are checked.
        """
        command = (
            "$ErrorActionPreference='Stop'; "
            "$hostInfo=Get-VMHost -ErrorAction Stop; "
            "$os=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop; "
            "$cpu=@(Get-CimInstance Win32_Processor -ErrorAction Stop | "
            "Measure-Object -Property NumberOfLogicalProcessors -Sum); "
            "$logical=[int]$cpu[0].Sum; "
            "$drives=@(Get-CimInstance Win32_LogicalDisk -Filter "
            "\"DriveType=3\" -ErrorAction Stop | ForEach-Object { "
            "[pscustomobject]@{Drive=[string]$_.DeviceID; "
            "FreeBytes=[long]$_.FreeSpace}}); "
            "$machines=@(Get-VM -ErrorAction Stop | ForEach-Object { "
            "[pscustomobject]@{Name=[string]$_.Name; "
            "State=[string]$_.State; "
            "AssignedBytes=[long]$_.MemoryAssigned}}); "
            "$switches=@(Get-VMSwitch -ErrorAction Stop | ForEach-Object { "
            "[pscustomobject]@{Name=[string]$_.Name; "
            "SwitchType=[string]$_.SwitchType}}); "
            "[pscustomobject]@{ "
            "Platform='Hyper-V'; "
            "HypervisorAvailable=($null -ne $hostInfo); "
            "WindowsHostVersion=[string]$os.Version; "
            "ObservedAtUtc=[DateTime]::UtcNow.ToString('o'); "
            "LogicalProcessors=$logical; "
            "FreeMemoryMB=[int][math]::Floor("
            "[double]$os.FreePhysicalMemory/1024); "
            "TotalMemoryMB=[int][math]::Floor("
            "[double]$os.TotalVisibleMemorySize/1024); "
            "Drives=$drives; Machines=$machines; Switches=$switches "
            "} | ConvertTo-Json -Depth 5 -Compress"
        )
        raw = self._runner(command)
        try:
            result = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise HyperVError("unparseable read-only Hyper-V host data") from exc
        if (
            not isinstance(result, dict)
            or result.get("Platform") != "Hyper-V"
            or result.get("HypervisorAvailable") is not True
            or not isinstance(result.get("WindowsHostVersion"), str)
        ):
            raise HyperVError("Hyper-V host presence could not be verified")
        return result

    def workshop_image_sha256(self, image_path: str) -> str:
        """Hash an exactly reviewed local image path, without loading it."""
        from sofia.ops.workshop_provision import _path
        verified_path = str(_path(image_path))
        # A fixed cmdlet and a quoted local path, never arbitrary scripts.
        command = (
            "Get-FileHash -LiteralPath " + self._ps(verified_path)
            + " -Algorithm SHA256 -ErrorAction Stop "
            "| Select-Object -ExpandProperty Hash"
        )
        # Large reviewed VM images may take longer than ordinary host
        # inventory. Only the fixed Get-FileHash operation gets this budget.
        result = (
            self._powershell(command, timeout_seconds=120)
            if self._runner is self._powershell
            else self._runner(command)
        ).strip().lower()
        import re
        if re.fullmatch(r"[0-9a-f]{64}", result) is None:
            raise HyperVError("image hash not observed or not SHA-256")
        return result

    @staticmethod
    def _reject_canonical_runtime_management(name: str) -> None:
        # This shared adapter serves both local and remote Fleet VM tools.
        # An ordinary model-facing VM action must never start/stop the sole
        # canonical writer. Privileged host recovery is an independent path.
        if name.strip().casefold() == CANONICAL_RUNTIME_VM_NAME.casefold():
            raise PermissionError(
                "canonical Sofia VM lifecycle requires independent "
                "operator-controlled host authority"
            )

    @staticmethod
    def _name(name:str)->None:
        if not isinstance(name,str) or not name.strip(): raise ValueError("VM name required")
        if len(name)>128 or any(ch in name for ch in "\r\n\0"): raise ValueError("invalid VM name")
    @staticmethod
    def _ps(value:str)->str:
        return "'"+value.replace("'","''")+"'"
    @staticmethod
    def _powershell(command:str,*,timeout_seconds:float=30)->str:
        if platform.system()!="Windows": raise HyperVError("Hyper-V adapter requires Windows")
        cp=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",command],
            text=True,capture_output=True,timeout=timeout_seconds,check=False)
        if cp.returncode: raise HyperVError(cp.stderr.strip() or "Hyper-V command failed")
        return cp.stdout
