# ComfyUI local integration: batch 1

This module adds an opt-in localhost-only client at `sofia.creative.comfyui_bridge`. It does not install or launch ComfyUI, alter the production runtime, write to sofia.db, or initiate GPU jobs.

On Venus, after pulling main:

```powershell
python -m pytest -q test/test_comfyui_bridge.py
python -m sofia.creative.comfyui_bridge --status
python -m sofia.creative.comfyui_bridge --queue
```

The CLI is read-only. Submissions require a trusted owner approval and independently verified GPU clearance, both supplied programmatically. The two boolean parameters are **not** themselves strong authentication or resource telemetry and must not be wired to an LLM or other untrusted caller. API-format workflow JSON may contain custom nodes and unsafe file paths; only pre-reviewed templates should be submitted once host authorization is integrated.

History currently returns sanitized filename metadata only. Persistent receipts, host gaming detection, automatic save/import, shutdown recovery, proactive scheduling, and production UI integration are **not completed**. No real Venus connection has yet been verified. ComfyUI should remain bound to loopback, not LAN or Cloudflare.
