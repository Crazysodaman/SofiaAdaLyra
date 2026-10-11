"""Typed local Hyper-V adapter for Windows hosts."""
from __future__ import annotations
import json,platform,subprocess
from typing import Any

from sofia.ops.workshop_policy import CANONICAL_RUNTIME_VM_NAME

class HyperVError(RuntimeError): pass

class HyperVAdapter:
    def __init__(self,runner=None)->None:
        self._default_runner=runner is None
        self._runner=runner if runner is not None else self._powershell
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
    def sofia_guest_inventory(self) -> dict[str, Any]:
        """Inspect reserved canonical VM only, WITHOUT guest OS assumptions.

        Source is the Hyper-V HOST, not evidence of an installed Debian guest.
        Neither this operation nor the returned plan can start, configure,
        provision, enroll, or promote a production writer.
        """
        from dataclasses import asdict
        from sofia.ops.sofia_guest_readiness import review_sofia_guest_inventory

        command = (
            "$ErrorActionPreference='Stop'; "
            "$v=Get-VM -Name 'Sofia' -ErrorAction Stop; "
            "if ($v.Name -cne 'Sofia') { throw 'VM identity mismatch' }; "
            "$disks=@(Get-VMHardDiskDrive -VMName 'Sofia' -ErrorAction Stop "
            "| ForEach-Object { "
            "$disk=Get-VHD -Path $_.Path -ErrorAction Stop; "
            "[pscustomobject]@{Path=[string]$_.Path; Size=[long]$disk.Size} }); "
            "$nics=@(Get-VMNetworkAdapter -VMName 'Sofia' -ErrorAction Stop "
            "| ForEach-Object { "
            "$kind='Unknown'; "
            "if ($_.SwitchName) { "
            "$sw=Get-VMSwitch -Name $_.SwitchName -ErrorAction Stop; "
            "$kind=[string]$sw.SwitchType }; "
            "[pscustomobject]@{SwitchName=[string]$_.SwitchName; "
            "SwitchType=$kind} }); "
            "$dvd=@(Get-VMDvdDrive -VMName 'Sofia' -ErrorAction Stop "
            "| Where-Object {$_.Path} | ForEach-Object {[string]$_.Path}); "
            "[pscustomobject]@{ "
            "VmId=[string]$v.Id; Name=[string]$v.Name; "
            "Generation=[int]$v.Generation; State=[string]$v.State; "
            "Processors=[int]$v.ProcessorCount; "
            "StartupMemoryBytes=[long]$v.MemoryStartup; "
            "Disks=$disks; NetworkAdapters=$nics; DvdPaths=$dvd; "
            "ObservedAtUtc=[DateTime]::UtcNow.ToString('o') "
            "} | ConvertTo-Json -Depth 5 -Compress"
        )
        raw = self._runner(command)
        try:
            observed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise HyperVError("invalid read-only Sofia VM observation") from exc
        if not isinstance(observed, dict) or observed.get("Name") != "Sofia":
            raise HyperVError("reserved Sofia VM identity not observed")
        return {
            "host_inventory": observed,
            "read_only_review": asdict(review_sofia_guest_inventory(observed)),
            "guest_os_installed": "unverified",
            "canonical_writer_active": False,
            "activation_authorized": False,
        }

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

    def bootstrap_existing_hephaestus(
        self, *, vm_id: str, os_disk_path: str,
        iso_path: str, iso_sha256: str,
    ) -> dict[str, Any]:
        """Boot reviewed unattended Debian ISO on the exact EXISTING VM.

        Host administrator configuration pins the VM GUID, OS disk and media
        root before agent registration.  No New-VM, networking or guest Fleet
        permissions. Success here means the installer STARTED, not that an OS
        has been installed, attested or enrolled.
        """
        from uuid import UUID
        from sofia.ops.workshop_provision import _path
        import re
        exact_id=str(UUID(vm_id))
        disk=str(_path(os_disk_path))
        media=str(_path(iso_path))
        if not disk.casefold().endswith(".vhdx") or not media.casefold().endswith(".iso"):
            raise ValueError("existing VHDX OS disk and unattended ISO required")
        if re.fullmatch(r"[0-9a-f]{64}",iso_sha256) is None:
            raise ValueError("exact approved ISO SHA-256 required")
        quote=self._ps
        # All parameters are quoted scalars. No arbitrary PowerShell commands
        # or user-selected VM names are admitted.
        script=(
            "$ErrorActionPreference='Stop'; "
            "$vm=Get-VM -Name 'Hephaestus' -ErrorAction Stop; "
            "if([string]$vm.Id -ne "+quote(exact_id)+") "
            "{throw 'VM_GUID_MISMATCH'}; "
            "if([string]$vm.State -ne 'Off') "
            "{throw 'VM_MUST_BE_POWERED_OFF'}; "
            "if([int]$vm.Generation -ne 2) {throw 'GEN2_REQUIRED'}; "
            "if([int]$vm.ProcessorCount -lt 2 -or "
            "[int]$vm.ProcessorCount -gt 4) {throw 'CPU_SCOPE_DRIFT'}; "
            "if([long]$vm.MemoryStartup -lt 4294967296 -or "
            "[long]$vm.MemoryStartup -gt 8589934592) "
            "{throw 'RAM_SCOPE_DRIFT'}; "
            "$disks=@(Get-VMHardDiskDrive -VMName 'Hephaestus' "
            "-ErrorAction Stop); "
            "if($disks.Count -ne 1) {throw 'OS_DISK_COUNT_DRIFT'}; "
            "if([string]$disks[0].Path -ine "+quote(disk)+") "
            "{throw 'OS_DISK_PATH_DRIFT'}; "
            "$vd=Get-VHD -Path "+quote(disk)+" -ErrorAction Stop; "
            "if([long]$vd.Size -lt 64424509440 -or "
            "[long]$vd.Size -gt 137438953472) "
            "{throw 'OS_DISK_SIZE_DRIFT'}; "
            "$nics=@(Get-VMNetworkAdapter -VMName 'Hephaestus' "
            "-ErrorAction Stop); "
            "if($nics.Count -ne 1 -or [string]$nics[0].SwitchName "
            "-cne 'Sofia-Hephaestus-Private') "
            "{throw 'NETWORK_SCOPE_DRIFT'}; "
            "$sw=Get-VMSwitch -Name 'Sofia-Hephaestus-Private' "
            "-ErrorAction Stop; "
            "if([string]$sw.SwitchType -ne 'Private') "
            "{throw 'NOT_PRIVATE_SWITCH'}; "
            "$firm=Get-VMFirmware -VMName 'Hephaestus' -ErrorAction Stop; "
            "if([string]$firm.SecureBoot -ne 'Off' -and "
            "([string]$firm.SecureBoot -ne 'On' -or "
            "[string]$firm.SecureBootTemplate -ne "
            "'MicrosoftUEFICertificateAuthority')) "
            "{throw 'UNREVIEWED_SECURE_BOOT'}; "
            "if(-not (Test-Path -LiteralPath "+quote(media)+
            " -PathType Leaf)) {throw 'ISO_UNAVAILABLE'}; "
            "$hash=(Get-FileHash -LiteralPath "+quote(media)+
            " -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant(); "
            "if($hash -cne "+quote(iso_sha256)+") "
            "{throw 'ISO_HASH_MISMATCH'}; "
            "$dvd=@(Get-VMDvdDrive -VMName 'Hephaestus' -ErrorAction Stop); "
            "if($dvd.Count -gt 1 -or "
            "@($dvd | Where-Object {$_.Path}).Count -gt 0) "
            "{throw 'UNREVIEWED_MOUNTED_MEDIA'}; "
            "if($dvd.Count -eq 0) { "
            "$drive=Add-VMDvdDrive -VMName 'Hephaestus' "
            "-Path "+quote(media)+" -Passthru -ErrorAction Stop "
            "} else { "
            "Set-VMDvdDrive -VMDvdDrive $dvd[0] -Path "+quote(media)+
            " -ErrorAction Stop; "
            "$drive=Get-VMDvdDrive -VMName 'Hephaestus' "
            "-ErrorAction Stop }; "
            "Set-VMFirmware -VMName 'Hephaestus' "
            "-FirstBootDevice $drive -ErrorAction Stop; "
            "Start-VM -Name 'Hephaestus' -ErrorAction Stop; "
            "$final=Get-VM -Name 'Hephaestus' -ErrorAction Stop; "
            "if([string]$final.Id -ne "+quote(exact_id)+") "
            "{throw 'POST_START_IDENTITY_CHANGED'}; "
            "[pscustomobject]@{VmId=[string]$final.Id; "
            "Name=[string]$final.Name; State=[string]$final.State; "
            "MediaSha256=$hash; Outcome='installer_boot_started'; "
            "OsInstalled=$false; FleetEnrolled=$false; "
            "ObservedAtUtc=[DateTime]::UtcNow.ToString('o')} "
            "| ConvertTo-Json -Depth 3 -Compress"
        )
        # Full-file hashing may take longer than a normal inspection.
        raw=(
            self._powershell(script,timeout_seconds=240)
            if self._default_runner
            else self._runner(script)
        )
        try:
            output=json.loads(raw)
        except (ValueError,TypeError) as exc:
            raise HyperVError("Hyper-V installer boot outcome uncertain") from exc
        if (
            not isinstance(output,dict)
            or str(output.get("VmId","")).lower()!=exact_id.lower()
            or output.get("Outcome")!="installer_boot_started"
            or output.get("OsInstalled") is not False
            or output.get("FleetEnrolled") is not False
        ):
            raise HyperVError("unexpected host installer start receipt")
        return output

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
            if self._default_runner
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
