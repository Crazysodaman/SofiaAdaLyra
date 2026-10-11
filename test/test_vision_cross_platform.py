"""Actual capture contracts with fake OS boundaries, never real screen/input.

Real hardware acceptance remains a separately supervised operator gate.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import socket
from types import SimpleNamespace
import zlib

import pytest

from sofia.vision.capture import ScreenCaptureService, local_target_id
from sofia.vision.desktop_control import DesktopAction, DesktopInputService
from sofia.vision.journeys import ScreenJourney, propose_owner_screen_journey
from sofia.vision.linux_desktop import LinuxDesktop
from sofia.vision.windows_capture import _png_from_bgra


def one_pixel() -> bytes:
    return _png_from_bgra(bytes((32, 64, 128, 255)), 1, 1)


def test_win32_native_frame_encodes_real_png_with_bgra_to_rgb():
    image = one_pixel()
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert int.from_bytes(image[16:20], "big") == 1
    assert int.from_bytes(image[20:24], "big") == 1
    at = image.index(b"IDAT") + 4
    size = int.from_bytes(image[at-8:at-4], "big")
    assert zlib.decompress(image[at:at+size]) == bytes((0, 128, 64, 32))
    with pytest.raises(ValueError):
        _png_from_bgra(b"", 1, 1)


class FakeDesktop:
    def __init__(self, *, original=(42, 55), png=None):
        self.original = original
        self.calls = []
        self.png = png or one_pixel()
        self.switch = False

    def foreground(self):
        return (99, 55) if self.switch else self.original

    def select_and_capture(self, *, exact_window, exact_pid, recheck):
        assert (exact_window, exact_pid) == self.original
        self.calls.append("picker")
        recheck()
        return self.png


def signed_request():
    now = datetime.now(timezone.utc)
    target = local_target_id(socket.gethostname(), 42, 55)
    return propose_owner_screen_journey(
        journey=ScreenJourney.LOOK_AT_WINDOW,
        principal_id="person:sparks", audience_id="local:text",
        device_id=socket.gethostname(), target_id=target,
        purpose="Owner selected one window", at=now,
    )


def installed_capture(monkeypatch, *, stop=False, switched=False):
    from sofia.safe import execution_approval, operator_stop
    import sofia.vision.capture as cap
    import sofia.vision.linux_desktop as linux
    cap.sys.platform = "linux"
    backend = FakeDesktop()
    backend.switch = switched
    used = []
    persisted = []
    class Approval:
        def __init__(self, state):
            pass
        def consume(self, **kwargs):
            used.append(kwargs)
    class Stop:
        def __init__(self, state):
            pass
        def current(self):
            return SimpleNamespace(active=stop)
    class Receipt:
        def __init__(self, state):
            pass
        def record(self, evidence):
            persisted.append(evidence)
    monkeypatch.setattr(execution_approval, "ExecutionApprovalVerifier", Approval)
    monkeypatch.setattr(operator_stop, "OperatorStopStore", Stop)
    monkeypatch.setattr(linux, "require_linux_game_clear", lambda: None)
    monkeypatch.setattr(cap, "ScreenJourneyReceiptStore", Receipt)
    return ScreenCaptureService(
        "never-written-test.db", capture_backend=backend,
        foreground_backend=backend,
    ), backend, used, persisted


def test_scoped_signed_linux_frame_never_persists_pixels(monkeypatch):
    service, backend, used, persisted = installed_capture(monkeypatch)
    result = service.capture_once(signed_request(), approval_id="fido-once")
    assert result.pixels_png == one_pixel()
    assert result.evidence.receipt.digest_sha256 == sha256(one_pixel()).hexdigest()
    assert len(used) == 1
    assert used[0]["capability"] == "screen.capture_once"
    assert used[0]["parameters"]["target_id"] == local_target_id(
        socket.gethostname(), 42, 55
    )
    assert len(persisted) == 1
    assert persisted[0].pixel_content_persisted is False
    assert persisted[0].semantic_content_verified is False


@pytest.mark.parametrize("condition", ["stop", "switched", "wrong_host", "expired"])
def test_capture_refuses_before_pixels_and_owner_approval(monkeypatch, condition):
    service, backend, used, persisted = installed_capture(
        monkeypatch, stop=condition=="stop", switched=condition=="switched",
    )
    req = signed_request()
    from dataclasses import replace
    if condition == "wrong_host":
        req = replace(req, permit=replace(req.permit, device_id="other-host"))
    elif condition == "expired":
        req = replace(req, permit=replace(req.permit,
                      issued_at=datetime.now(timezone.utc)-timedelta(minutes=3),
                      expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)))
    with pytest.raises(PermissionError):
        service.capture_once(req, approval_id="fido-once")
    assert backend.calls == []
    assert used == [] and persisted == []


def test_hyprland_capture_uses_real_slurp_single_rect_then_grim(monkeypatch):
    calls = []
    box = {"handle": 0x1234, "pid": 90, "geometry": (11, 22, 200, 150)}
    def runner(argv, *, data=None, timeout=8, maximum=262144):
        calls.append((argv, data))
        if argv[0] == "slurp":
            assert argv == ("slurp", "-r")
            assert data == b"11,22 200x150\n"
            return b"11,22 200x150\n"
        if argv[0] == "grim":
            assert argv == ("grim", "-g", "11,22 200x150", "-")
            return one_pixel()
        raise AssertionError(argv)
    backend = LinuxDesktop(runner=runner, session=lambda: "wayland")
    monkeypatch.setattr(backend, "_hypr_window", lambda: box)
    checks = []
    actual = backend.select_and_capture(
        exact_window=0x1234, exact_pid=90,
        recheck=lambda: checks.append(True),
    )
    assert actual == one_pixel()
    assert len(checks) >= 2 and [c[0][0] for c in calls] == ["slurp", "grim"]


def test_hyprland_picker_cannot_change_target_or_geometry(monkeypatch):
    calls = []
    backend = LinuxDesktop(
        runner=lambda argv, **kwargs: (calls.append(argv) or b"12,22 200x150\n"),
        session=lambda: "wayland",
    )
    monkeypatch.setattr(backend, "_hypr_window", lambda: {
        "handle": 0x1234, "pid": 90, "geometry": (11,22,200,150)
    })
    with pytest.raises(PermissionError, match="different target"):
        backend.select_and_capture(
            exact_window=0x1234, exact_pid=90, recheck=lambda: None,
        )
    assert [x[0] for x in calls] == ["slurp"]


@pytest.mark.parametrize("method", ["key_press", "type_text", "mouse_click"])
def test_linux_wayland_input_is_bounded_and_rechecks_each_effect(monkeypatch, method):
    sent = []
    def runner(argv, *, data=None, **kwargs):
        sent.append((argv, data))
        return b""
    target = {"handle": 77, "pid": 88, "geometry": (0,0,500,400)}
    backend = LinuxDesktop(runner=runner, session=lambda: "wayland")
    monkeypatch.setattr(backend, "_hypr_window", lambda: target)
    action = DesktopAction(
        host_id=socket.gethostname(), window_handle=77, process_id=88,
        operation=method, key="tab" if method=="key_press" else "",
        text="AB" if method=="type_text" else "",
        x=20 if method=="mouse_click" else -1,
        y=30 if method=="mouse_click" else -1,
    )
    gates = []
    backend.execute(action, lambda: gates.append(1))
    assert len(gates) >= (3 if method=="type_text" else 2 if method=="mouse_click" else 1)
    assert all(command[0][0] == "ydotool" for command in sent)
    if method == "type_text":
        assert [data for _, data in sent] == [b"A",b"B"]


def test_linux_click_refuses_out_of_window_before_any_input(monkeypatch):
    sent=[]
    backend = LinuxDesktop(
        runner=lambda argv, **kwargs: sent.append(argv) or b"",
        session=lambda: "wayland",
    )
    monkeypatch.setattr(backend, "_hypr_window", lambda: {
        "handle":77,"pid":88,"geometry":(20,20,40,30)
    })
    action=DesktopAction(host_id=socket.gethostname(),window_handle=77,
                         process_id=88,operation="mouse_click",x=2,y=2)
    with pytest.raises(PermissionError,match="outside"):
        backend.execute(action,lambda:None)
    assert not sent


def test_local_only_inference_receives_owner_picked_pixels_without_tools(monkeypatch):
    from sofia.vision.capture import CapturedFrame
    from sofia.vision.journeys import accept_actual_picked_frame
    from sofia.vision.interpret import describe_frame
    req = signed_request()
    pixels = one_pixel()
    evidence = accept_actual_picked_frame(
        req, pixel_bytes=pixels, at=datetime.now(timezone.utc),
        actual_os_picker_selected_target_id=req.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    frame = CapturedFrame(pixels, evidence)
    calls = []
    class LocalClient:
        def chat(self, **kwargs):
            calls.append(kwargs)
            return {"message": {"content": "A title bar and two buttons."}}
    result = describe_frame(frame, model="vision-local-test", client=LocalClient())
    assert result.description == "A title bar and two buttons."
    assert result.trusted_instruction is False
    assert result.verified_app_state is False
    assert result.frame_sha256 == sha256(pixels).hexdigest()
    assert calls[0]["messages"][0]["images"] == [pixels]
    assert "tools" not in calls[0] and calls[0]["stream"] is False


def test_image_model_failure_does_not_fallback_to_other_models():
    from sofia.vision.capture import CapturedFrame
    from sofia.vision.journeys import accept_actual_picked_frame
    from sofia.vision.interpret import describe_frame
    req = signed_request()
    pixels = one_pixel()
    evidence = accept_actual_picked_frame(
        req, pixel_bytes=pixels, at=datetime.now(timezone.utc),
        actual_os_picker_selected_target_id=req.permit.target_id,
        confirmed_interactive_os_picker=True,
    )
    class Failing:
        attempts = 0
        def chat(self, **kwargs):
            self.attempts += 1
            raise OSError("model unavailable")
    client = Failing()
    with pytest.raises(RuntimeError, match="no model fallback"):
        describe_frame(CapturedFrame(pixels, evidence),
                       model="owner-chosen-model", client=client)
    assert client.attempts == 1
