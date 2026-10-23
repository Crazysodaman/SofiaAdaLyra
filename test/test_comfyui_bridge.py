import json
import pytest
from sofia.core.creative.comfyui_bridge import ComfyUIBridge, ComfyBridgeError

PID = "550e8400-e29b-41d4-a716-446655440000"

class FakeTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, request):
        self.calls.append((request.full_url, request.get_method()))
        path = request.full_url.split(":8188")[-1]
        if path == "/system_stats":
            return b'{"devices":[{}]}'
        if path == "/queue" and request.get_method() == "GET":
            return b'{"queue_running":[],"queue_pending":[1]}'
        if path == "/prompt":
            return json.dumps({"prompt_id": PID}).encode()
        if path == "/queue":
            return b'{}'
        if path == "/history/" + PID:
            return json.dumps({PID: {"outputs": {"3": {"images": [
                {"filename": "out.png", "type": "output"}]}}}}).encode()
        raise AssertionError(path)

def test_local_status_queue():
    fake = FakeTransport()
    bridge = ComfyUIBridge(transport=fake)
    assert bridge.status() == {"connected": True, "devices": 1}
    assert bridge.queue() == {"running": 0, "pending": 1}
    assert all("127.0.0.1" in call[0] for call in fake.calls)

def test_submit_gated():
    fake = FakeTransport()
    bridge = ComfyUIBridge(transport=fake)
    workflow = {"1": {"class_type": "KSampler", "inputs": {}}}
    with pytest.raises(PermissionError):
        bridge.submit(workflow, approved=True)
    assert not fake.calls
    assert bridge.submit(workflow, approved=True, resources_clear=True)["prompt_id"] == PID

def test_history_and_cancel():
    bridge = ComfyUIBridge(transport=FakeTransport())
    assert bridge.history(PID)["files"] == [{"filename": "out.png", "type": "output"}]
    with pytest.raises(PermissionError):
        bridge.cancel_pending(PID)
    assert bridge.cancel_pending(PID, approved=True)["scope"] == "pending_only"

def test_bad_inputs():
    with pytest.raises(ValueError):
        ComfyUIBridge(port=80)
    with pytest.raises(ValueError):
        ComfyUIBridge().history("../../foo")
    with pytest.raises(ValueError):
        ComfyUIBridge().submit({"1": {"class_type": "KSampler"}}, approved=True, resources_clear=True)

def test_filter_unsafe_file():
    class Fake:
        def __call__(self, _req):
            return json.dumps({PID: {"outputs": {"1": {"images": [
                {"filename": "../evil", "type": "output"},
                {"filename": "ok.png", "type": "output"}]}}}}).encode()
    assert ComfyUIBridge(transport=Fake()).history(PID)["files"] == [{"filename": "ok.png", "type": "output"}]
