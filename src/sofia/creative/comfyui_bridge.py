"""Local, opt-in ComfyUI API adapter. Does not launch GPU jobs automatically."""
from __future__ import annotations
import argparse
import json
import re
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
from uuid import uuid4

MAX_RESPONSE = 2_000_000
MAX_REQUEST = 1_000_000
IDENT = re.compile(r"^[0-9a-fA-F-]{32,36}$")
FILENAME = re.compile(r"^[^/\\\x00-\x1f]{1,200}$")


class ComfyBridgeError(RuntimeError):
    """Sanitized local API error."""


class ComfyUIBridge:
    def __init__(self, *, port: int = 8188, transport=None):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError("invalid local ComfyUI port")
        self.base = f"http://127.0.0.1:{port}"
        self.transport = transport if transport is not None else self._http

    @staticmethod
    def _http(request):
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=8) as response:
                if response.status != 200:
                    raise ComfyBridgeError("ComfyUI returned non-success HTTP status")
                return response.read(MAX_RESPONSE + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ComfyBridgeError(f"local ComfyUI unavailable ({type(exc).__name__})") from None

    def _json(self, path, payload=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        if data is not None and len(data) > MAX_REQUEST:
            raise ComfyBridgeError("workflow payload too large")
        request = Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method="POST" if data is not None else "GET",
        )
        raw = self.transport(request)
        if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE:
            raise ComfyBridgeError("invalid ComfyUI response size")
        try:
            result = json.loads(raw)
        except (UnicodeError, ValueError):
            raise ComfyBridgeError("ComfyUI returned invalid JSON") from None
        if not isinstance(result, dict):
            raise ComfyBridgeError("ComfyUI response must be an object")
        return result

    def status(self):
        devices = self._json("/system_stats").get("devices")
        if not isinstance(devices, list):
            raise ComfyBridgeError("invalid device response")
        return {"connected": True, "devices": len(devices)}

    def queue(self):
        result = self._json("/queue")
        running, pending = result.get("queue_running"), result.get("queue_pending")
        if not isinstance(running, list) or not isinstance(pending, list):
            raise ComfyBridgeError("invalid queue response")
        return {"running": len(running), "pending": len(pending)}

    def submit(self, workflow, *, approved=False, resources_clear=False):
        # These flags must be backed by trusted owner authorization and real host telemetry.
        # Not exposed on CLI and not wired to the production scheduler.
        if approved is not True or resources_clear is not True:
            raise PermissionError("owner approval and GPU clearance required")
        if not isinstance(workflow, dict) or not workflow or any(
            not isinstance(k, str) or not isinstance(v, dict)
            or not isinstance(v.get("class_type"), str)
            or not isinstance(v.get("inputs"), dict)
            for k, v in workflow.items()
        ):
            raise ValueError("expected reviewed ComfyUI API-format workflow")
        response = self._json("/prompt", {"prompt": workflow, "client_id": uuid4().hex})
        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not IDENT.fullmatch(prompt_id):
            raise ComfyBridgeError("ComfyUI did not confirm job ID")
        return {"prompt_id": prompt_id, "queued": True}

    def history(self, prompt_id):
        if not isinstance(prompt_id, str) or not IDENT.fullmatch(prompt_id):
            raise ValueError("invalid ComfyUI prompt ID")
        job = self._json(f"/history/{prompt_id}").get(prompt_id)
        if job is None:
            return {"prompt_id": prompt_id, "found": False, "files": []}
        if not isinstance(job, dict) or not isinstance(job.get("outputs"), dict):
            raise ComfyBridgeError("invalid job history")
        files = []
        for output in job["outputs"].values():
            if not isinstance(output, dict):
                continue
            images = output.get("images", [])
            if not isinstance(images, list):
                continue
            for entry in images:
                if (isinstance(entry, dict) and isinstance(entry.get("filename"), str)
                    and FILENAME.fullmatch(entry["filename"])
                    and entry.get("type") in ("output", "temp")):
                    files.append({"filename": entry["filename"], "type": entry["type"]})
        return {"prompt_id": prompt_id, "found": True, "files": files}

    def cancel_pending(self, prompt_id, *, approved=False):
        if approved is not True:
            raise PermissionError("explicit approval required to cancel a pending job")
        if not isinstance(prompt_id, str) or not IDENT.fullmatch(prompt_id):
            raise ValueError("invalid ComfyUI prompt ID")
        self._json("/queue", {"delete": [prompt_id]})
        return {"cancel_requested": True, "prompt_id": prompt_id, "scope": "pending_only"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only local ComfyUI diagnostics")
    parser.add_argument("--port", type=int, default=8188)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--status", action="store_true")
    modes.add_argument("--queue", action="store_true")
    modes.add_argument("--history", metavar="PROMPT_ID")
    args = parser.parse_args(argv)
    try:
        bridge = ComfyUIBridge(port=args.port)
        result = bridge.status() if args.status else bridge.queue() if args.queue else bridge.history(args.history)
        print(json.dumps(result, indent=2))
        return 0
    except (ComfyBridgeError, ValueError) as exc:
        parser.exit(2, f"ComfyUI: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
