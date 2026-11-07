# AG-D007 | Aegis Control Center: layout, locations and behavior

**Status:** OWNER-DESIRED UI DESIGN, NOT IMPLEMENTED OR SCHEDULED.  
**Date:** 2026-11-06.  
**Related:** [Main Control Center specification](AEGIS_CONTROL_CENTER_DESIGN.md), [Design TODO](AEGIS_DESIGN_TODO.md), [Platform-only acceptance #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201).

This is a design proposal, not permission to modify production installer paths or add new Platform 1.0 shakedown blockers.

## 1. Desktop window layout

One neutral Aegis Control Center app with detachable manager windows. Closing the app or tray does not stop the long-running Rust Platform service. It starts without any personal Core, model, Ollama, GPU or avatar.

| Element | Position | Starting size | Responsibility |
| --- | --- | --- | --- |
| Title / Platform status bar | Full top | 52 px high | Aegis logo, immutable local Platform ID, connection, alerts |
| Navigation rail | Left | 232 px expanded, 64 px collapsed | Overview, Fleet, Cores, Models, Modules, Catalog, Jobs, Hardware, Updates, Security, Backups, Diagnostics, Lab, Settings |
| Search and breadcrumbs | Main upper edge | 42 px each | Authorized search, exact selected host/Core ID, local/remote context |
| Main content | Middle | Fluid, desired minimum 480 px | Tables, cards, diagnostic timelines, empty states |
| Context inspector | Right | 320 px default, adjustable 280–380 px | Selected resource fingerprint, trust, permissions and live-data freshness |
| Activity / jobs strip | Full bottom | 36 px high | Pending work, SAFE/STOP, exact outcome and errors |
| Jobs drawer | Bottom overlay | Up to 360 px high | Operation receipts and recovery actions |
| Confirmation dialog | Center of initiating window | 480–640 px wide | Exact identity/operation/scope review and owner approval |
| Detached manager | Its own OS-native window | Start 1050 × 730 px | Same service and permissions, never another canonical writer |

**Initial main window:** 1440 × 900 logical pixels. **Comfortable minimum:** about 900 × 620 logical pixels, not a hard clipping rule. Respect font scaling and DPI. UI layouts may be adjusted after owner review.

## 2. Small windows, multiple displays, and keyboard

- Width at least 1380: expanded left sidebar, main pane, right-side inspector.
- Width 1060–1379: inspector becomes a tab or slide-out overlay.
- Width 900–1059: sidebar collapses to icon rail; inspector appears as an overlay.
- Narrower windows/accessibility zoom: single scrollable column, hamburger navigation and a dismissible detail panel.
- Tables scroll inside their content pane and retain stable identity and trust information. Do not require hover, dragging, or a mouse.
- Persist only window geometry/theme as per-user presentation settings. On a changed monitor configuration restore off-screen windows onto a visible display.
- Esc closes a dialog without a side effect. Ctrl+K can open an authorized-object search and command palette. Shortcut assignments remain subject to accessibility/OS review.
- Open in new window creates a second UI window only. Multiple windows recheck authorization and revisions through one Platform API. Closing a window never drains the Platform service.

## 3. Screen locations and actions

| Page | Main display | Primary button | Details/privileged actions |
| --- | --- | --- | --- |
| Overview | Platform identity and verified health, Fleet/Core/Model summary, jobs | Open relevant manager | Last evidence time, warnings, independent service status |
| Fleet | Enrolled / Unverified / Offline / Quarantined; list and topology | Discover (top right) | Inspect fingerprint, owner-approved enroll/revoke in selected host |
| Cores | Signed Core packages, identities, lifecycle, generations | Install .corepkg (top right) | Activate, deactivate, update, uninstall in selected Core pane |
| Models | Provider/host inventory, residency, assigned roles | Plan download (top right) | Owner-approved download, load/unload and model-role changes |
| Modules | Installed signed modules, health, dependencies | Install module (top right) | Capabilities, activation, permissions, version changes |
| Catalog | Signed artifacts and compatibility preview | Preview install | Separate install authorization; never auto-activate |
| Jobs | Requests, accepted work, unknown outcomes, verified receipts | View pending (top right) | Cancel or retry only where independently authorized |
| Hardware | Fresh CPU/RAM/GPU/VRAM, reservations and workloads | Refresh measurements | Placement proposals, no silent migration |
| Updates | Per-component release plans and rollback eligibility | Check approved sources | Stage/activate with signed release and owner policy |
| Security | SAFE/STOP, scoped grants, keys, pending approvals | Review pending | Strong exact-target approval dialog, no secrets displayed |
| Backups | Platform and per-Core lineage, integrity, recovery status | Verify backup | Restore plan and separate exact owner approval |
| Diagnostics | Subsystem health, traces, service/source errors | Refresh | Sanitized evidence export and safe recovery links |
| Aegis Lab | Synthetic Core/Fleet scenario and disposable-state banner | Create lab | Never use production keys or identity state |
| Settings | UI appearance and local presentation preferences | Save UI settings | No direct protected-state modification |

## 4. Permanent context and notification locations

- **Top left:** Aegis identity and navigation; no assumption Sofía is installed.
- **Top center:** local Platform UUID suffix and selected remote target ID, with authentication and trust/freshness.
- **Top right:** search, alerts, approvals, job count, settings.
- **Bottom left:** verified connection source, SAFE/STOP, current service state.
- **Bottom right:** latest actual operation receipt, or a clear UNKNOWN/FAILED status.
- **Toast notifications:** brief, low-distraction, with a link to Jobs/Diagnostics; no private Core memory or security secrets in ordinary tray notifications.
- **Confirmation dialogs:** never use only a friendly name; show immutable ID, exact signed package/operation, affected host/Core, permission, and consequences.
- **Dangerous actions:** separated from refresh/read-only actions. Use semantic color plus text/icons, not color alone.

## 5. Visual style

- Functional, uncluttered dark interface by default: near-black and charcoal surfaces; restrained teal interactive accent and violet optional secondary accent.
- Light mode and system theme supported. Use green for verified healthy, amber for pending/degraded, red for STOP/revoked/danger, gray for unknown/unobserved, always accompanied by labels.
- Spacing based on an 8 px rhythm; typical pane padding 12–16 px. Typography accessible at user-controlled zoom.
- Avoid automatic list reordering while an approval dialog or row selection is open.
- Animated loading indicators only reflect actual requests. No fake job progress or claimed "online" status from stale cached observations.

## 6. Candidate OS paths (not effective installation paths yet)

| Asset | Windows suggestion | Linux suggestion |
| --- | --- | --- |
| Desktop application | %ProgramFiles%/Aegis/ControlCenter/ | /usr/lib/aegis/ and /usr/bin/ launcher |
| Desktop launcher | Start Menu shortcut, optional desktop shortcut | /usr/share/applications/ .desktop entry |
| Per-user UI theme/layout | %LOCALAPPDATA%/Aegis/ControlCenter/ | $XDG_CONFIG_HOME/aegis/control-center/ (defaults to ~/.config/aegis/control-center/) |
| Per-user ephemeral cache | %LOCALAPPDATA%/Aegis/ControlCenter/Cache/ | $XDG_CACHE_HOME/aegis/control-center/ |
| Nonsecret machine config | %ProgramData%/Aegis/Config/ | /etc/aegis/ |
| Private Platform state | Protected %ProgramData%/Aegis/State/ | Owner-restricted /var/lib/aegis/ |
| System service logs | Protected ProgramData logs and Windows Event Log | systemd journal, optional /var/log/aegis/ |
| Credentials | Reviewed OS/service secret store, never in UI config | Reviewed service-owned secure storage, never in UI config |
| Protected Core state | Canonical per-Core writer/identity-owned state | Canonical per-Core writer/identity-owned state |

**Caution:** These are platform conventions for future installer review. The running project's existing roots, explicit identity storage, and AEGIS_PLATFORM_IDENTITY_HOME are authoritative where already implemented. Never silently relocate them. No secure credentials, approvals, canonical Fleet trust, personal memories, or Core writer data belong in UI theme/window files. Keep UI-only uninstall distinct from Platform service uninstall and from a separately authorized Core-data purge.

## 7. What the first real GUI milestone should prove

**Read-only milestone:** launch on clean installed Windows and Debian desktop environments with no Core, Ollama or model installed; authenticate to the local Rust service; display immutable local Platform identity, health, empty Cores, Fleet candidate/enrollment state and exact diagnostic freshness; close normally without stopping Platform.

Then add detached manager windows, model/module views and Jobs receipts. Later add controlled effects through versioned, authenticated APIs, with fresh permission and generation checks.

**Negative tests:** revoked session, stale/renamed host, disconnected remote Platform, second window with outdated selection, old IPC generation, missing provider, oversized text/font scale, screen reader navigation and restored window on a missing monitor. No UI success claim unless effect receipt is verified.

## 8. Still-open UX decisions

1. Confirm initial width, sidebar and inspector positions.
2. Should a single click select a resource while double-click opens a detached manager, or should a separate Open in New Window action be mandatory for accessibility?
3. Keep Sofía's Workbench separate, with an optional Open Sofía link only when installed?
4. Should the default Home view emphasize Fleet, active jobs, or installed Cores?
5. Should advanced features like Lab and Workshop live inside an expandable Tools group by default?
6. Approve eventual OS paths only after installer, ACL and state-migration review.
7. Keep Codex focused on Platform-only #201 unless the owner explicitly schedules CC implementation.
