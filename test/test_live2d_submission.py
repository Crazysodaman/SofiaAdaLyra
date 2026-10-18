import json
import pytest
from PIL import Image
from sofia.creative.live2d_submission import submit_reviewed_workflow
from sofia.ui.live2d_review import create_review_job

PROMPT_ID = "11111111-2222-3333-4444-555555555555"

class StubBridge:
    def __init__(self, *, fail=False):
        self.calls = 0
        self.fail = fail
    def submit(self, workflow, *, approved, resources_clear):
        self.calls += 1
        assert approved is True and resources_clear is True
        if self.fail:
            raise ConnectionError("transport lost after send")
        return {"prompt_id": PROMPT_ID, "queued": True}

@pytest.fixture
def inputs(tmp_path):
    source = tmp_path / "face.png"
    Image.new("RGB", (512, 512)).save(source)
    job = create_review_job(source, tmp_path / "job")
    workflow = tmp_path / "reviewed.json"
    workflow.write_text(json.dumps({"1": {"class_type": "KSampler", "inputs": {}}}))
    return job, workflow

def test_requires_both_gates_before_writing(inputs):
    job, workflow = inputs
    stub = StubBridge()
    with pytest.raises(PermissionError):
        submit_reviewed_workflow(job, workflow, owner_approved=True, bridge=stub)
    assert stub.calls == 0
    assert not (job / "comfyui_job.json").exists()

def test_records_real_confirmation_and_prevents_duplicate(inputs):
    job, workflow = inputs
    stub = StubBridge()
    result = submit_reviewed_workflow(job, workflow, owner_approved=True,
                                      host_resources_clear=True, bridge=stub)
    assert result["prompt_id"] == PROMPT_ID
    assert json.loads((job / "comfyui_job.json").read_text())["status"] == "queued"
    with pytest.raises(FileExistsError):
        submit_reviewed_workflow(job, workflow, owner_approved=True,
                                 host_resources_clear=True, bridge=stub)
    assert stub.calls == 1

def test_ambiguous_failure_never_resubmits(inputs):
    job, workflow = inputs
    stub = StubBridge(fail=True)
    with pytest.raises(ConnectionError):
        submit_reviewed_workflow(job, workflow, owner_approved=True,
                                 host_resources_clear=True, bridge=stub)
    saved = json.loads((job / "comfyui_job.json").read_text())
    assert saved["status"] == "submitting"
    assert saved["automatic_retry_allowed"] is False
    with pytest.raises(FileExistsError):
        submit_reviewed_workflow(job, workflow, owner_approved=True,
                                 host_resources_clear=True, bridge=stub)
    assert stub.calls == 1
