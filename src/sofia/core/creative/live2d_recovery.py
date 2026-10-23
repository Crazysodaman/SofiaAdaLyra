"""Crash-safe, read-only recovery reconciliation for local ComfyUI jobs.

No automatic retry: a lost HTTP acknowledgement can still have queued work.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from uuid import uuid4

STATES = {"draft", "submitting", "queued", "running", "complete", "offline", "uncertain", "failed"}

def _atomic_json(path: Path, data: dict):
    tmp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with tmp.open("x", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)

def record_submission(job_folder: Path, *, prompt_id: str | None = None,
                      status: str = "submitting") -> dict:
    """Save intent BEFORE network submit; only a confirmed ID permits reconciliation."""
    if status not in {"submitting", "queued", "uncertain"}:
        raise ValueError("invalid submission state")
    path = job_folder / "comfyui_job.json"
    if not (job_folder / "manifest.json").is_file():
        raise ValueError("not a Live2D review job")
    if path.exists():
        raise FileExistsError("existing ComfyUI submission; reconcile before retry")
    obj = {"version": 1, "status": status, "prompt_id": prompt_id,
           "automatic_retry_allowed": False}
    _atomic_json(path, obj)
    return obj

def reconcile(job_folder: Path, bridge) -> dict:
    path = job_folder / "comfyui_job.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("status") not in STATES:
        raise ValueError("invalid saved ComfyUI job state")
    prompt_id = data.get("prompt_id")
    from sofia.core.creative.comfyui_bridge import IDENT, ComfyBridgeError
    try:
        health = bridge.status()
        queue = bridge.queue()
        if not isinstance(health, dict) or health.get("connected") is not True:
            raise ComfyBridgeError("ComfyUI unavailable")
        if not isinstance(queue, dict) or any(type(queue.get(k)) is not int or queue[k] < 0 for k in ("pending", "running")):
            raise ComfyBridgeError("invalid queue state")
        if not isinstance(prompt_id, str) or not IDENT.fullmatch(prompt_id):
            status = "uncertain" if data["status"] != "draft" else "draft"
            detail = "No confirmed prompt ID; inspect ComfyUI before a manual retry"
        else:
            result = bridge.history(prompt_id)
            if result.get("found"):
                status = "complete" if result.get("files") else "uncertain"
                detail = "Completed files found" if status == "complete" else "History exists without output files; review required"
            else:
                status = "uncertain"
                detail = "Not in history; may still be running or pending. Review queue manually"
    except (ComfyBridgeError, OSError, TimeoutError):
        status = "offline"
        detail = "ComfyUI offline; saved job preserved. No automatic retry"
    data.update(status=status, last_check=detail, automatic_retry_allowed=False)
    _atomic_json(path, data)
    return data
