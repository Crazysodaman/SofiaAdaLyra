"""Typed local maintenance executor.

No shell strings are accepted from callers. Every operation maps to a fixed
argv template with validated identifiers.
"""
from __future__ import annotations
import platform,re,shutil,subprocess
from dataclasses import dataclass
from typing import Sequence

class LocalMaintenanceError(RuntimeError): pass

_SAFE_IDENTIFIER=re.compile(r"^[A-Za-z0-9_.:@+-]{1,128}$")

def _identifier(value:str,label:str)->str:
    if not isinstance(value,str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} contains unsupported characters")
    return value

@dataclass(frozen=True)
class LocalCommandResult:
    argv:tuple[str,...]
    returncode:int
    stdout:str
    stderr:str

class LocalMaintenanceAdapter:
    def __init__(self,runner=None)->None:
        self._runner=runner or self._run
        self.system=platform.system()

    @staticmethod
    def _run(argv:Sequence[str])->LocalCommandResult:
        cp=subprocess.run(tuple(argv),text=True,capture_output=True,timeout=180,check=False)
        result=LocalCommandResult(tuple(argv),cp.returncode,cp.stdout,cp.stderr)
        if cp.returncode:
            raise LocalMaintenanceError(cp.stderr.strip() or cp.stdout.strip() or f"command failed: {argv[0]}")
        return result

    def service(self,name:str,action:str)->LocalCommandResult:
        name=_identifier(name,"service name")
        if action not in ("start","stop","restart"):
            raise ValueError("service action must be start, stop, or restart")
        if self.system=="Windows":
            if action=="restart":
                try: self._runner(("sc.exe","stop",name))
                except LocalMaintenanceError:
                    pass
                return self._runner(("sc.exe","start",name))
            return self._runner(("sc.exe",action,name))
        if self.system=="Linux":
            return self._runner(("systemctl",action,name))
        raise LocalMaintenanceError(f"local service control is unsupported on {self.system}")

    def reboot(self)->LocalCommandResult:
        if self.system=="Windows":
            return self._runner(("shutdown.exe","/r","/t","0"))
        if self.system=="Linux":
            return self._runner(("systemctl","reboot"))
        raise LocalMaintenanceError(f"local reboot is unsupported on {self.system}")

    def package_update(self,package:str)->LocalCommandResult:
        package=_identifier(package,"package")
        if self.system=="Windows":
            if shutil.which("winget") is None:
                raise LocalMaintenanceError("winget is unavailable")
            return self._runner((
                "winget","upgrade","--id",package,"--exact","--silent",
                "--accept-package-agreements","--accept-source-agreements",
            ))
        if self.system=="Linux":
            if shutil.which("apt-get"):
                return self._runner(("apt-get","install","--only-upgrade","-y",package))
            if shutil.which("pacman"):
                return self._runner(("pacman","-S","--noconfirm",package))
            if shutil.which("dnf"):
                return self._runner(("dnf","upgrade","-y",package))
            if shutil.which("zypper"):
                return self._runner(("zypper","--non-interactive","update",package))
            raise LocalMaintenanceError("no supported package manager found")
        raise LocalMaintenanceError(f"package update is unsupported on {self.system}")
