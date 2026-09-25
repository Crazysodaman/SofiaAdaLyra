"""Typed local Hyper-V adapter for Windows hosts."""
from __future__ import annotations
import json,platform,subprocess
from typing import Any

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
        self._name(name); self._runner(f"Start-VM -Name {self._ps(name)} -ErrorAction Stop | Out-Null")
    def stop(self,name:str,*,force:bool=False)->None:
        self._name(name)
        cmd=f"Stop-VM -Name {self._ps(name)} -ErrorAction Stop"
        if force: cmd+=" -TurnOff"
        self._runner(cmd+" | Out-Null")
    @staticmethod
    def _name(name:str)->None:
        if not isinstance(name,str) or not name.strip(): raise ValueError("VM name required")
        if len(name)>128 or any(ch in name for ch in "\r\n\0"): raise ValueError("invalid VM name")
    @staticmethod
    def _ps(value:str)->str:
        return "'"+value.replace("'","''")+"'"
    @staticmethod
    def _powershell(command:str)->str:
        if platform.system()!="Windows": raise HyperVError("Hyper-V adapter requires Windows")
        cp=subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",command],
            text=True,capture_output=True,timeout=30,check=False)
        if cp.returncode: raise HyperVError(cp.stderr.strip() or "Hyper-V command failed")
        return cp.stdout
