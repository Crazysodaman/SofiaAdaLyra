# Phase 12: Exact owner-controlled GUI input

**Status:** source-coded Win32 local input plus CLI; not yet validated on real Windows hardware; not full Phase 12 screen vision.

## Owner-approved boundary

- No GUI input on Venus when a game is active, paused but still running, or game/activity evidence is unavailable, stale or overridden.
- Artemis and independently enrolled VMs may use a dedicated interactive OS session after separately approved scoped credentials. An OS-less VM has no usable guest desktop.
- Screenshot recognition, model output and user-facing vision requests do not authorize mouse or keyboard control.
- The existing SAFE `screen.act_exact` capability is never-self-authorized. Every input needs a fresh hardware-key-backed one-use exact request; canonical STOP is checked before and during the operation.

## Current local Windows operator entrypoint

Inspect the current foreground window and process:

```powershell
python -m sofia.vision.desktop_control_cli --inspect
```

After recording the exact HWND and PID, approve a single tab key for that window:

```powershell
python -m sofia.vision.desktop_control_cli --window-handle 12345 --process-id 6789 --operation key_press --key tab --credential-id YOUR_ENROLLED_KEY_ID
```

Replace the example HWND/PID with actual values returned by inspect. Click actions use `--operation mouse_click --x N --y N` and are refused outside the original window or where an overlay covers the point. `--operation type_text` reads up to 40 printable characters from stdin instead of from command-line arguments.

Each execution asks for the original independent owner WebAuthn proof, allows five seconds to refocus the window, consumes the one-use approval and rechecks foreground, STOP and Venus activity. The response `os_input_submitted` proves only OS input submission, not that an application consumed the input.

## Critical limitations

- Game detection relies on actual local process inspection, Steam game paths, a curated executable list and fresh existing tray evidence. Unknown status refuses input; **no universal anti-cheat or ban-free guarantee** is possible.
- The current backend is local Win32 console only, with no remote hypervisor/guest injection, no Linux/Hyprland support, and no installed screen OS-picker capture pipeline.
- No arbitrary hotkeys, clipboard transfer, command interpreter, password entry automation, persistent mouse macros, unattended model clicks or generic shell command control.
- Synthetic tests never send real OS events. Live owner-supervised Windows tests with actual game launch/pause, WindowFromPoint overlay, HWND reuse, process inspection failure, emergency STOP and FIDO2 denial/revocation are still mandatory.

See the exact source at `src/sofia/vision/desktop_control.py`, operator CLI at `src/sofia/vision/desktop_control_cli.py`, and synthetic regression tests at `test/test_vision_desktop_control.py`.
