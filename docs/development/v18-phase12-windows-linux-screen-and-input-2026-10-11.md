# Phase 12: Windows and Linux screen capture plus GUI input

Status (2026-10-11): Production source backends and synthetic tests committed on main. Physical GUI acceptance and full live Sofía UI workflow remain outstanding. No live hosts or VMs modified.

## Supported backends

| Host | Capture | Input | Exact owner selection |
|---|---|---|---|
| Windows 11 desktop | Win32 PrintWindow/GDI to PNG in memory | SendInput | Native visible YES/NO confirmation; HWND+PID pinned |
| Hyprland on Arch/Debian | grim with exact compositor rectangle | ydotool via preexisting ydotoold | slurp -r restricted to one active window |
| Linux X11 | ImageMagick import -window | xdotool | xdotool selectwindow, foreground, geometry and pointer rechecked |
| Other Wayland compositors | Not implemented | Not implemented | xdg-desktop-portal integration still required |
| Headless Artemis | No GUI available | No GUI available | Use authenticated OPS/Fleet APIs instead |
| VMs | Inside each installed guest only | Inside each enrolled guest only | Hyper-V host cannot impersonate guest consent |

## Installation prerequisites

Windows requires no new third-party image package. Hyprland needs compositor IPC (hyprctl), grim, slurp, ydotool and a separately owner-configured ydotoold socket with proper uinput privileges. X11 needs xdotool and ImageMagick import. No service is automatically installed, no elevation is performed, and Sofía's GUI client must never run as root or via a remote SSH desktop.

All live requests use canonical sofia.db, exact host/window/PID and physical FIDO2 owner authentication. A screenshot additionally requires a short-lived permit and separate human OS selection. Input and capture do not share permissions.

## Operator sequence

Focus a harmless user-owned application on the same local graphical console, then inspect the target:

    python -m sofia.vision.desktop_control_cli --inspect

Using the exact returned HWND and PID, take ONE signed screenshot:

    python -m sofia.vision.desktop_control_cli --capture --window-handle 1234 --process-id 5678 --credential-id ENROLLED_KEY_ID

Optionally add --describe-model qwen3.5:9b. This requires a genuine vision-capable model served on localhost 127.0.0.1:11434. No image route to a remote LLM, automatic fallback, tool call, memory insertion or other network host is authorized by this option. The model's visual description is untrusted observation, not an executable instruction or verified app outcome.

For one bounded key:

    python -m sofia.vision.desktop_control_cli --operation key_press --window-handle 1234 --process-id 5678 --key tab --credential-id ENROLLED_KEY_ID

For a left click, replace the operation with mouse_click and add --x 200 --y 250. To enter at most 40 printable characters, use --operation type_text; text is read from stdin rather than visible command arguments.

Never use placeholder IDs literally. Every single action and capture requires a fresh owner approval.

## Safety and privacy

Venus denies actions and capture when gaming status is gaming, stale, overridden, unknown, or when games are still running even if paused. Linux GUI operations run a separate process-based game scan and deny uncertain or detected game states. No process scanner or capture library can guarantee zero anti-cheat bans. Dedicated non-gaming VM automation is the stricter alternative.

STOP, executing host, active window, current PID, current session, screen lock and capture expiry are checked independently. X11 clicks also verify window bounds and pointer hit. Screenshot PNG bytes remain transient in memory. The canonical database stores only source-bound digests, with no pixels; image-derived text cannot grant command authority.

Windows PrintWindow can fail or produce blank pixels for protected or GPU-rendered surfaces. The system must not claim semantic comprehension from a hash or unusable image. Submitted input does not prove that an app accepted it.

## Still to complete and accept

1. Real Windows 11 test of selected window pixels, FIDO2, STOP, session lock, focus switching, protected screens and gaming refusal.
2. Real Hyprland and X11 tests of owner picker, screenshot bytes, pointer/keyboard, daemon unavailable, permissions and gaming refusal.
3. Register a workbench UI that presents model-proposed actions for owner review. The current CLI is operator-driven, not autonomous conversation GUI control.
4. Add and verify xdg-desktop-portal ScreenCast/RemoteDesktop for other Wayland desktops if required.
5. Activate an independently enrolled graphical VM on Artemis for guest input. No live guest canary was executed.
6. Record passing CI and host acceptance receipts against the original V18 task IDs. Do not mark Phase 12 complete based only on source commits.

Code: src/sofia/vision/capture.py, windows_capture.py, linux_desktop.py, desktop_control.py, desktop_control_cli.py, interpret.py. Tests: test/test_vision_cross_platform.py, test/test_vision_desktop_control.py.
