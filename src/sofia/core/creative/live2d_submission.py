"""Durable, explicitly authorized ComfyUI submission for a Live2D review job.

This is a library boundary, not a chat command or an automatic scheduler.
Caller MUST provide a trusted owner approval and real host/GPU clearance.
"""
from __future__ import annotations
import json
from pathlib import Path
from sofia.core.creative.comfyui_bridge import ComfyUIBridge, IDENT
from sofia.core.creative.live2d_recovery import record_submission, _atomic_json


class Live2DSubmitError(RuntimeError):
    pass


def submit_reviewed_workflow(
    job_folder: Path, workflow_path: Path, *, owner_approved: bool = False,
    host_resources_clear: bool = False, bridge: ComfyUIBridge | None = None,
) -> dict:
    """Journal the submission BEFORE sending to ComfyUI, never retry ambiguities.

    A duplicate request always fails closed, even if the remote call returned an
    error. Inspect history/queue and create a NEW explicitly approved job to retry.
    """
    if owner_approved is not True or host_resources_clear is not True:
        raise PermissionError("trusted owner approval and verified host clearance required")
    if not (job_folder / "manifest.json").is_file() or not (job_folder / "source.png").is_file():
        raise Live2DSubmitError("invalid or incomplete Live2D job")
    if not workflow_path.is_file() or workflow_path.stat().st_size > 1_000_000:
        raise Live2DSubmitError("workflow file missing or oversized")
    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise Live2DSubmitError("invalid reviewed workflow JSON") from exc
    if not isinstance(workflow, dict) or not workflow:
        raise Live2DSubmitError("reviewed API workflow must be a nonempty mapping")
    # Persist the exact submitted graph for recovery and human inspection.
    # Do not allow an existing snapshot to be overwritten by a retry.
    snapshot = job_folder / "submitted_workflow.json"
    if snapshot.exists() or (job_folder / "comfyui_job.json").exists():
        raise FileExistsError("submission already recorded; inspect before retry")
    with snapshot.open("x", encoding="utf-8") as stream:
        json.dump(workflow, stream, indent=2, ensure_ascii=False)
    record_submission(job_folder)
    api = bridge if bridge is not None else ComfyUIBridge()
    try:
        response = api.submit(workflow, approved=True, resources_clear=True)
        prompt_id = response["prompt_id"]
        if not isinstance(prompt_id, str) or not IDENT.fullmatch(prompt_id):
            raise Live2DSubmitError("ComfyUI returned invalid prompt ID")
    except Exception:
        # HTTP failures might be post-acceptance; DO NOT retry automatically.
        # The existing submitting record remains and reconciles to uncertain/offline.
        raise
    path = job_folder / "comfyui_job.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    state.update(status="queued", prompt_id=prompt_id)
    _atomic_json(path, state)
    return {"prompt_id": prompt_id, "status": "queued", "automatic_retry_allowed": False}
