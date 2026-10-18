# ComfyUI Desktop host lifecycle (Venus)

This is a **manual, owner-session** Windows CLI. It does not run automatically from Sofía's dialogue, goals, or scheduler. The ComfyUI HTTP API remains on 127.0.0.1:8188.

Find the real ComfyUI Desktop executable with Windows Explorer, then from Sofía's virtual environment:

```powershell
git pull --ff-only
python -m pytest -q test/test_comfyui_host.py test/test_comfyui_bridge.py
python -m sofia.creative.comfyui_host --exe "C:\Path\To\ComfyUI.exe" --status
python -m sofia.creative.comfyui_host --exe "C:\Path\To\ComfyUI.exe" --launch
python -m sofia.creative.comfyui_host --exe "C:\Path\To\ComfyUI.exe" --close
```

Replace the example executable path with the real Desktop exe. **Do not assume** the program lives in the model-data directory.

Safety limits:

- An already running ComfyUI Desktop is treated as **not owned** and cannot be closed by Sofía.
- Only the precise PID, creation time, Windows user, and executable of a process Sofía launched may be closed. GUI `WM_CLOSE` is requested; no force kill.
- Desktop launcher wrappers may exit and spawn other processes. The code intentionally does not assume ownership transfers to those children, so close may refuse on some Desktop builds.
- Closing requires a successful live queue query reporting zero pending and running jobs. An unavailable API means no close.
- ComfyUI might still have work outside its queue or in an external worker; manual validation remains required.
- On Windows, install psutil in Sofía's environment if missing: `python -m pip install psutil`.
- Ownership state is stored in the current Windows profile. Stale records are not automatically erased to avoid accidentally taking ownership after PID recycling.
- No remote host control, background auto-launch, gaming detection, verified resource budget, or production conversational activation is implemented.

Until real Windows launch-and-close verification passes, this is **code-present, not production-accepted**.
