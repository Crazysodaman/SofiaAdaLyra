import json
from pathlib import Path
import pytest
from sofia.creative import comfyui_host as host

class FakeProc:
    def __init__(self, pid=42, exe="C:/Apps/ComfyUI.exe"):
        self.pid = pid
        self.info = {"pid": pid, "exe": exe}
    def is_running(self): return True
    def status(self): return "running"
    def create_time(self): return 1234.0
    def exe(self): return "C:/Apps/ComfyUI.exe"
    def username(self): return "owner"

class FakePS:
    STATUS_ZOMBIE = "zombie"
    Error = Exception
    def __init__(self, procs): self.procs = procs
    def process_iter(self, _fields): return self.procs
    def Process(self, pid): return next(p for p in self.procs if p.pid == pid)

def test_no_unowned_close(tmp_path, monkeypatch):
    monkeypatch.setattr(host.sys, "platform", "win32")
    ps = FakePS([FakeProc()])
    result = host.close(exe=Path("C:/Apps/ComfyUI.exe"), record_path=tmp_path/"missing.json",
                        psutil=ps, jobs_running=0)
    assert result["result"] == "not_owned"

def test_refuses_unknown_gpu_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(host.sys, "platform", "win32")
    with pytest.raises(host.ComfyHostError):
        host.close(exe=Path("C:/Apps/ComfyUI.exe"), record_path=tmp_path/"missing.json", psutil=FakePS([]))

def test_refuses_multi_instance(tmp_path, monkeypatch):
    monkeypatch.setattr(host.sys, "platform", "win32")
    path = tmp_path/"owned.json"
    path.write_text(json.dumps({"pid": 42, "created": 1234.0, "exe": "C:/Apps/ComfyUI.exe", "user": "owner"}))
    ps = FakePS([FakeProc(), FakeProc(pid=43)])
    with pytest.raises(host.ComfyHostError):
        host.close(exe=Path("C:/Apps/ComfyUI.exe"), record_path=path, psutil=ps, jobs_running=0,
                   send_close=lambda _: pytest.fail("should never send close"))
