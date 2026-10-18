import json
from pathlib import Path
import pytest
from sofia.creative.live2d_recovery import record_submission, reconcile
from sofia.creative.comfyui_bridge import ComfyBridgeError

ID = "11111111-2222-3333-4444-555555555555"
class Healthy:
    def status(self): return {"connected": True}
    def queue(self): return {"pending": 0, "running": 0}
    def history(self, prompt_id): return {"found": True, "files": [{"filename":"test.png","type":"output"}]}
class Offline(Healthy):
    def status(self): raise ComfyBridgeError("offline")

def job(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    (folder / "manifest.json").write_text("{}")
    return folder

def test_unconfirmed_submission_is_uncertain_and_not_retried(tmp_path):
    folder = job(tmp_path)
    record_submission(folder)
    out = reconcile(folder, Healthy())
    assert out["status"] == "uncertain"
    assert out["automatic_retry_allowed"] is False
    with pytest.raises(FileExistsError):
        record_submission(folder)

def test_offline_preserves_submission(tmp_path):
    folder = job(tmp_path)
    record_submission(folder, prompt_id=ID, status="queued")
    out = reconcile(folder, Offline())
    assert out["status"] == "offline"
    assert out["prompt_id"] == ID
    assert (folder / "comfyui_job.json").exists()

def test_completed_history(tmp_path):
    folder = job(tmp_path)
    record_submission(folder, prompt_id=ID, status="queued")
    assert reconcile(folder, Healthy())["status"] == "complete"
