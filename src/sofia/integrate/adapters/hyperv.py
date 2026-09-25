"""Typed local Hyper-V adapter using fixed PowerShell cmdlets."""
from __future__ import annotations
from datetime import datetime,timezone
import json
from re import fullmatch
import subprocess
from typing import Callable
from sofia.external.adapter import ExternalIntegrationAdapter
from sofia.external.model import ExternalObservationState,ExternalSystem,ExternalSystemAction,ExternalSystemObservation,ExternalSystemResult,ExternalSystemResultKind,ExternalSystemType

PowerShellRunner=Callable[[str],str]
_VM_NAME=r"[A-Za-z0-9_. ()-]+"

class HyperVAdapter(ExternalIntegrationAdapter):
    def __init__(self,*,runner:PowerShellRunner|None=None,system_id:str="hyper-v")->None:
        self._runner=runner or self._run_powershell
        self._system=ExternalSystem(system_id,"Hyper-V",ExternalSystemType.PLATFORM,"Microsoft Hyper-V")
    @property
    def name(self)->str: return "hyperv-powershell"
    @property
    def system(self)->ExternalSystem: return self._system
    @staticmethod
    def _run_powershell(command:str)->str:
        completed=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",command],capture_output=True,text=True,timeout=30,check=False)
        if completed.returncode!=0: raise RuntimeError(completed.stderr.strip() or "Hyper-V PowerShell failed")
        return completed.stdout.strip()
    @staticmethod
    def _vm_name(value:object)->str:
        if not isinstance(value,str) or fullmatch(_VM_NAME,value) is None: raise ValueError("invalid VM name")
        return value
    def observe(self)->ExternalSystemObservation:
        raw=self._runner("Get-VM | Select-Object Name,State,CPUUsage,MemoryAssigned,Uptime | ConvertTo-Json -Compress")
        payload=json.loads(raw) if raw else []
        if isinstance(payload,dict): payload=[payload]
        if not isinstance(payload,list): raise ValueError("invalid Hyper-V VM inventory")
        return ExternalSystemObservation(self.system,datetime.now(timezone.utc),ExternalObservationState.VERIFIED,
            {"virtual_machines":payload,"count":len(payload)},self.name)
    def execute_action(self,action:ExternalSystemAction)->ExternalSystemResult:
        if action.system_id!=self.system.system_id: raise ValueError("action targets a different Hyper-V system")
        cmdlet={"start_vm":"Start-VM","stop_vm":"Stop-VM"}.get(action.action_name)
        if cmdlet is None: raise ValueError("unsupported Hyper-V action")
        vm_name=self._vm_name(action.parameters.get("name"))
        escaped=vm_name.replace("'","''")
        self._runner(f"{cmdlet} -Name '{escaped}' -Confirm:$false")
        return ExternalSystemResult(self.system.system_id,ExternalSystemResultKind.SUCCESS,
            {"vm":vm_name,"operation":action.action_name},datetime.now(timezone.utc),self.name)
