"""Deferred-free unit safety regressions for exact GUI input.

Uses a spy, never Windows user32: test execution MUST NOT move a mouse or
send a real key. Genuine interactive Windows acceptance is a separate gate.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import socket
import sys

import pytest

from sofia.vision import desktop_control as dc


def request(**changes):
    props = dict(host_id=socket.gethostname(), window_handle=77, process_id=88,
                 operation="key_press", key="tab")
    props.update(changes)
    return dc.DesktopAction(**props)


@pytest.mark.parametrize("overrides", [
    {"operation": "key_press", "key": "ctrl+alt+delete"},
    {"operation": "type_text", "key": "", "text": "x" * 41},
    {"operation": "type_text", "key": "", "text": "pass\nword"},
    {"operation": "mouse_click", "key": "", "x": -1, "y": 1},
    {"operation": "mouse_click", "key": "", "x": 1, "y": 99999},
    {"window_handle": 0},
    {"process_id": -1},
    {"operation": "shell"},
])
def test_input_schema_rejects_unbounded_and_privileged_operations(overrides):
    with pytest.raises((ValueError, TypeError)):
        request(**overrides)


def test_exact_approval_parameters_bind_host_target_and_original_input():
    action = request(operation="type_text", key="", text="draft")
    assert action.approval_parameters() == {
        "host_id": socket.gethostname(), "window_handle": 77,
        "process_id": 88, "operation": "type_text",
        "key": "", "text": "draft", "x": -1, "y": -1,
    }


class FakeBackend:
    def __init__(self, *, hwnd=77, pid=88, interrupt=False):
        self.hwnd = hwnd
        self.pid = pid
        self.interrupt = interrupt
        self.executed = []

    def foreground(self):
        return self.hwnd, self.pid

    def execute(self, action, recheck):
        recheck()
        if self.interrupt:
            self.hwnd = 91
            recheck()
        self.executed.append(action)


def installed_service(monkeypatch, *, stopped=False, window=77,
                      gaming=False, interrupt=False):
    from sofia.platform.safe import execution_approval, operator_stop
    backend = FakeBackend(hwnd=window, interrupt=interrupt)
    approvals = []
    class Approval:
        def __init__(self, _path):
            pass
        def consume(self, *, approval_id, capability, parameters, now):
            assert approval_id == "exact-fido-action"
            assert capability == "screen.act_exact"
            assert parameters["window_handle"] == 77
            assert now.tzinfo is not None
            approvals.append(parameters)
    class Stop:
        def __init__(self, _path):
            pass
        def current(self):
            return SimpleNamespace(active=stopped)
    monkeypatch.setattr(execution_approval, "ExecutionApprovalVerifier", Approval)
    monkeypatch.setattr(operator_stop, "OperatorStopStore", Stop)
    monkeypatch.setattr(dc, "require_workstation_clear",
                        lambda *_: (_ for _ in ()).throw(PermissionError("gaming"))
                        if gaming else None)
    monkeypatch.setattr(dc.sys, "platform", "win32")
    return dc.DesktopInputService("never-created-by-test.db", backend=backend), backend, approvals


def test_real_input_path_consumes_one_exact_fido_approval(monkeypatch):
    service, backend, approvals = installed_service(monkeypatch)
    result = service.execute(request(), approval_id="exact-fido-action")
    assert result["status"] == "os_input_submitted"
    assert result["effect_verified"] is False
    assert len(approvals) == 1
    assert backend.executed == [request()]


@pytest.mark.parametrize("scenario", ["stop", "gaming", "different_window"])
def test_refusal_is_before_approval_or_input(monkeypatch, scenario):
    service, backend, approvals = installed_service(
        monkeypatch, stopped=scenario == "stop",
        gaming=scenario == "gaming",
        window=100 if scenario == "different_window" else 77,
    )
    with pytest.raises(PermissionError):
        service.execute(request(), approval_id="exact-fido-action")
    assert approvals == []
    assert backend.executed == []


def test_changed_foreground_after_approval_rejects_effect(monkeypatch):
    service, backend, approvals = installed_service(monkeypatch, interrupt=True)
    with pytest.raises(PermissionError):
        service.execute(request(), approval_id="exact-fido-action")
    assert len(approvals) == 1
    assert backend.executed == []


def test_host_identity_mismatch_refused(monkeypatch):
    service, backend, approvals = installed_service(monkeypatch)
    with pytest.raises(PermissionError):
        service.execute(request(host_id="completely-different-host"),
                        approval_id="exact-fido-action")
    assert not approvals and not backend.executed


def test_venus_requires_fresh_non_override_and_game_clear(monkeypatch):
    from sofia.platform.ops import activity as act
    instant = datetime(2026, 10, 11, tzinfo=timezone.utc)

    observations = {"override": act.ActivityMode.AUTO,
                    "effective": act.ActivityMode.NORMAL,
                    "observed_at": instant,
                    "source": "windows-process-inspection"}

    class FakeActivityStore:
        def __init__(self, path):
            pass
        def state(self, host):
            assert host == "Venus"
            return SimpleNamespace(**observations)

    monkeypatch.setattr(act, "HostActivityStore", FakeActivityStore)
    monkeypatch.setattr(dc, "game_process_clear", lambda: True)
    dc.require_workstation_clear("canonical.db", "Venus",
                                  instant + timedelta(seconds=30))

    for field, value in (
        ("override", act.ActivityMode.NORMAL),
        ("effective", act.ActivityMode.GAMING),
        ("observed_at", instant - timedelta(seconds=60)),
        ("source", "operator-override"),
    ):
        original = observations[field]
        observations[field] = value
        with pytest.raises(PermissionError):
            dc.require_workstation_clear("canonical.db", "Venus", instant)
        observations[field] = original

    monkeypatch.setattr(dc, "game_process_clear", lambda: False)
    with pytest.raises(PermissionError, match="running game"):
        dc.require_workstation_clear("canonical.db", "Venus", instant)


def test_live_process_inspection_detects_running_nonsteam_game(monkeypatch):
    """No game detection depends on psutil or Steam membership alone."""
    from sofia.platform.system import capability as caps
    from sofia.platform.system.model import (
        ProcessInspection, SystemCapability, SystemCapabilityName,
        SystemCapabilityResultKind,
    )
    processes = [
        ProcessInspection(pid=10, name="explorer.exe",
                          executable=r"C:\Windows\explorer.exe"),
        ProcessInspection(pid=11, name="factorio.exe",
                          executable=r"D:\Games\Factorio\factorio.exe"),
    ]
    gate = SystemCapability(SystemCapabilityName.PROCESS_INSPECT, "Read running processes")
    class Backend:
        supported_capabilities = (gate,)
        def execute(self, request):
            assert request.capability == gate
            assert request.parameters == {"limit": 2048}
            return SimpleNamespace(
                kind=SystemCapabilityResultKind.SUCCESS,
                evidence={"processes": tuple(processes)},
            )
    monkeypatch.setattr(dc.sys, "platform", "win32")
    monkeypatch.setattr(caps, "create_local_system_backend", lambda: Backend())
    assert dc.game_process_clear() is False
    processes.pop()
    assert dc.game_process_clear() is True
    processes[:] = [ProcessInspection(pid=20, name=""),
                    ProcessInspection(pid=10, name="explorer.exe")]
    with pytest.raises(PermissionError, match="unknown running process"):
        dc.game_process_clear()


def test_live_process_inspection_failure_never_means_safe_to_click(monkeypatch):
    from sofia.platform.system import capability as caps
    from sofia.platform.system.model import (
        ProcessInspection, SystemCapability, SystemCapabilityName,
        SystemCapabilityResultKind,
    )
    gate = SystemCapability(SystemCapabilityName.PROCESS_INSPECT, "Read running processes")
    result = SimpleNamespace(
        kind=SystemCapabilityResultKind.UNAVAILABLE,
        evidence={},
    )
    class Backend:
        supported_capabilities = (gate,)
        def execute(self, _request):
            return result
    monkeypatch.setattr(dc.sys, "platform", "win32")
    monkeypatch.setattr(caps, "create_local_system_backend", lambda: Backend())
    with pytest.raises(PermissionError, match="not fully observable"):
        dc.game_process_clear()
    result.kind = SystemCapabilityResultKind.SUCCESS
    result.evidence = {"processes": ()}
    with pytest.raises(PermissionError, match="missing or truncated"):
        dc.game_process_clear()
    result.evidence = {"processes": tuple(
        ProcessInspection(pid=i + 1, name="process.exe") for i in range(2048)
    )}
    with pytest.raises(PermissionError, match="missing or truncated"):
        dc.game_process_clear()
