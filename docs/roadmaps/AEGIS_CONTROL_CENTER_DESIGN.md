# AG-D007 | Aegis Control Center

**Status:** OWNER-DESIRED DESIGN; detailed specification captured, implementation **NOT SCHEDULED** by this document.
**Design snapshot:** 2026-11-06. **Repository:** `Crazysodaman/SofiaAdaLyra`.
**Tracking:** [Aegis Design TODO](AEGIS_DESIGN_TODO.md), [Platform-only acceptance #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201), [full release #120](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120).

> This is a UI and capability design, NOT evidence of completed code, an authorization for live Fleet enrollment, an addition to the #201 shakedown gate, or a Codex/OpenCode implementation assignment.

## 1. Product decision and core promise

**One Aegis Control Center application**, with a common sidebar/navigation and **detachable manager windows** using the same components and authenticated Platform API. The OS-native tray offers quick status and opens the relevant page. Windows and supported Linux desktops get a GUI; headless Windows/Debian hosts retain the CLI/API, with no graphical dependency required by the service.

The **Aegis Platform** is operational with no Core, model or GUI installed. The **Sofía Workbench** (chat, avatar, personality, personal memory) remains a separate optional Core client/workspace. Aegis branding, identity and permissions are neutral and must not import Sofía personal Core code for startup.

Proposed implementation: Rust-owned Platform service, management/authorization API and process boundaries; a Tauri desktop client *if engineering review confirms OS/accessibility/security compatibility*. Reuse existing Python presentation pieces during migration, but do not preserve their Core-dependent assumptions in the new Core-free app. The definitive desktop framework and package topology require a separate review.

## 2. Navigation

| Group | Destination | Linked TODO | Default purpose |
| --- | --- | --- | --- |
| HOME | Overview | AG-D001 / AG-D016 | Local Platform status, identity, warnings, next actions, real last observed time |
| INFRASTRUCTURE | Fleet | AG-D012 | Enrolled Platforms, untrusted candidates, callsigns, health and topology |
| COMPONENTS | Cores | AG-D003 / AG-D004 / AG-D008 | Installed Core identities, signed packages, lifecycle and retained data |
| COMPONENTS | Models | AG-D005 / AG-D009 | Model inventory, inference hosts, approved downloads, role assignment |
| COMPONENTS | Modules | AG-D006 | Signed module installation, scopes, status and upgrade/rollback |
| COMPONENTS | Catalog | AG-D021 | Signed/compatible package preview; discovery is not install permission |
| OPERATIONS | Jobs & Activity | AG-D020 | Requested/approved/running/verified/denied/unknown jobs and exact receipts |
| OPERATIONS | Hardware & Compute | AG-D017 | Observed resource state, GPU/VRAM headroom, reservations and placement proposals |
| OPERATIONS | Updates | AG-D015 | Signed downloads, staged upgrades, compatibility and rollback |
| SAFETY | Security & Approvals | AG-D013 | Permissions, STOP, trust, explicit consent, pending approval review |
| SAFETY | Backups & Recovery | AG-D014 | Platform and per-Core protected recovery without writer duplication |
| SUPPORT | Diagnostics | AG-D016 | Health timelines, degraded services, provenance, safe export |
| SUPPORT | Aegis Lab | AG-D018 | Disposable synthetic test environments only, strong LAB/PROD separation |
| SUPPORT | Developer Workshop | AG-D019 | Reviewed Core-suggested code/test proposals, PR/test receipts |
| SETTINGS | Platform Settings | AG-D011 | Local appearance, enrolled host settings, notifications, privacy |

Core-dependent pages must show **Not installed / Not available** with explanation, never render an imaginary Core. Optional panes may be hidden in simplified navigation, but remain discoverable. The Home screen must work before any Core is installed.

## Unified color and cross-interface parity decision (2026-11-07)

**Owner decision:** The neutral Aegis GUI uses the exact same default dark palette as **all Aegis CLI/TUI interfaces**, installer and headless controls. [Shared GUI/TUI Visual Theme](AEGIS_SHARED_GUI_TUI_THEME.md) is authoritative for purple `#9400D3`, cyan `#00C2FF`, lime `#39FF14`, black `#000000`, cards `#0B1020`, light `#E5E7EB` text, muted `#94A3B8`, amber HUD `#FFB000`, red danger `#9F0202`, hover/focus and all highlight tokens. Include readable text labels for warning/error, keyboard focus and accessible contrast instead of assuming the owner colors work as small-text foregrounds everywhere. The previous general near-black/teal/violet suggestions are superseded for neutral Aegis GUI *defaults*; separate Sofía Workbench styling is not changed.

**Missing shared operator behavior:** See [AG-D024 GUI/TUI parity and gaps](AG_D024_GUI_TUI_PARITY_GAP_REVIEW.md) for existing backend/code overlap and specific work still required: unified authorization, first-run/disconnected service, cross-host/Core selector, typed setting editor and apply receipts, notification/job continuity, owner auth from headless clients, safety, access and parity testing. This is a design refinement, not a new Platform 1.0 release gate or an order to reimplement existing managers.

## 3. Desktop layout and navigation behavior

Desktop: compact title/status bar; persistent sidebar with collapsible groups; main content view; optional contextual details/inspector pane; bottom job/notification indicator; global command/search field for local *authorized* resources. Selecting an item opens details in-place; an **Open in new window** option detaches a manager using the same backend session and permissions. Detaching does not create new Core runtimes, owner authority or extra canonical writers.

Proposed low-fidelity layout:

```text
AEGIS Control Center               [Platform: local] [SAFE] [Jobs 2]
+------------------+----------------------------------------------------+
| Overview         | Platform identity: AEG-P-...   Health: VERIFIED  |
| Fleet            |----------------------------------------------------|
| Cores            | Fleet: 2 enrolled, 1 unverified, 1 offline         |
| Models           | Cores: None installed on this Platform            |
| Modules          | Models: Provider status unknown / not configured  |
| Catalog          |----------------------------------------------------|
| Jobs & Activity  | Recent operations, approvals and verified events |
| Hardware         | Actions: View diagnostics / Discover hosts       |
| Updates          |                                                    |
| Security         |                                                    |
| Backups          |                                                    |
| Diagnostics      |                                                    |
| Lab              |                                                    |
+------------------+----------------------------------------------------+
Footer: Connected to LOCAL Aegis service | Last verified: timestamp
```

These counts, labels and values are **illustrative only**, never observed live Fleet/host data.

**Global context:** Always display the exact local Platform ID; when showing a remote host or Core, display its verified stable ID, trust and evidence freshness next to friendly names. Never persist a silently changed remote target after refresh, revocation or tab/window switch. Local and remote scopes should be visually distinct.

**Multiple windows:** Windows share a single service and notification/job backend; authorization and revocations must be rechecked by the service for each protected operation, independent of stale UI state. Closing any Control Center window does not stop Platform. A tray exit only closes tray process unless a separate reviewed service-stop operation is performed.

**Visual/interaction preferences:** Clean, high contrast, keyboard accessible, reduced-motion support, sensible font scaling, light/dark/system theme, responsive smaller windows, inline empty states, clear dangerous-action confirmation, unobtrusive notification badge. Avoid arbitrary Core personality themes in global security screens.

## 4. Three action classes

1. **Read-only observation:** list Platform, Fleet, component and health status where already authorized. Show source, timestamp, last verified generation and Unknown if no fresh observation. A discovery candidate is not an enrolled host.
2. **Configuration/proposal:** draft settings, installation plans, placement plans, named component selection, approval requests. Drafting and previewing have no executor side effects.
3. **Protected effect:** install/activate/deactivate a Core, enroll/revoke a host, change privileged settings, stop a service, transfer protected state, launch an upgrade, remove a module or erase protected data. The service must verify exact owner principal, requested operation, target immutable ID, selected artifact digest, expected revision/generation, scoped fresh approval, resource admission and SAFE/STOP immediately before effects.

User-visible action states must distinguish **PROPOSED**, **AWAITING_APPROVAL**, **ACCEPTED**, **RUNNING**, **SUCCEEDED_VERIFIED**, **DENIED**, **FAILED**, **CANCELLED**, and **OUTCOME_UNKNOWN**. Requested is not completed. Do not automatically retry unknown-outcome effects.

**Owner authentication:** Respect the approved, independently verified 256-bit-secret-backed procedure through a secure interactive credential entry/credential provider, **never** command-line args, logs, URLs, configuration exports or prompts. FIDO2 remains optional/dormant unless separately enabled. A UI session token alone is not fresh authority for all sensitive effects. This document does not implement or weaken that ceremony.

## 5. Service/API boundaries

- Core-free Aegis Rust service is the local authority for Platform lifecycle, identity, IPC, grants, named components, STOP, audit and job receipts. UI cannot write protected SQLite/state, bypass the service or access a Core's canonical writer store.
- The UI client authenticates to local IPC with scope and bound instance/session. Local interactive OS identity is not by itself proof of Aegis owner permission. Use encrypted/pinned authenticated endpoints for permitted remote read/control, and revalidate at execution.
- API contracts separate Platform identity, Core identity, component manifest, inference host, trust state, runtime health and operation status. All returned mutable states carry revision/generation and freshness.
- A versioned SDK and CLI expose the **same semantics** as GUI actions. No UI-only privileged operation. API errors return clear denied/unreachable/unsupported/not-installed/unknown outcomes rather than success-looking fallbacks.
- No silent offline promotion, automatic Fleet enrollment, model download, Core selection, Core activation, credential rotation or live-state transfer.
- Cross-platform desktop UI connects remotely only via explicit, authenticated authorized pairing, never raw discovery/hostname as a trust shortcut.

**Live Module Manager/Settings refresh requirement:** [AG-D006 live module status](AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md). Opening the GUI once is enough: when a signed module is installed, activated, paused, fails, disconnects, reconnects, updates or is removed, the existing Module Manager/Settings UI should update from authoritative lifecycle, settings and fresh runtime-health sources, without restarting the UI or Platform. Do not conflate ACTIVE lifecycle with verified runtime connectivity. Coalesce events, reconcile missed events with bounded polling, and invalidate stale editing drafts on package/lifecycle/revision change. Applying a particular setting may still require a separately approved component restart; merely displaying a status update never does.

## 6. Core-free, multiple-Core and remote-host rules

- **Zero Cores:** Control Center and all Platform-local management remain usable. Show an empty Cores page and optional signed package installation plan; no Sofía state, LLM or GPU needed.
- **One Core:** Display its immutable Core ID, current worker generation, lifecycle, selected authorized model/provider and protected data-retention state. Core status cannot substitute for Platform status.
- **Several Cores:** Separate identity, permissions, model roles, runtime generations, state lineages and private data. Never auto-select the first, sole, same-name or recently used Core for a protected action. A manager row must include stable ID suffix/host.
- **Disconnected remote Platform:** Show last verified snapshot as STALE and remote effects unavailable until authenticated/authorized; never replay an old effect or silently switch hosts.
- **Detached manager:** No extra service instance or trust. A manager refresh must not inadvertently create a Core or local personal database.

## 7. Important user journeys

| Journey | Expected observable result |
| --- | --- |
| First open on clean Core-free Windows/Debian Platform | Aegis identity, service status, empty Cores, clear Fleet enrollment state; no Core imports |
| Open Core Manager and inspect `.corepkg` | Signed bytes/compatibility reviewed, no activation before separate exact approval |
| Install synthetic Core then deactivate/uninstall | Revisions and receipt shown; Platform keeps running; protected data follows explicit retention policy |
| Select model for a Core | Exact provider/model/host assignment proposal; no identity swap, unauthorized model pull or silent fallback |
| See discovered Fleet host | UNVERIFIED until owner-approved enrollment and committed receipt |
| Revoke host during running operation | Stale request/result fenced; dashboard remains accurate and refreshes trust |
| Start remote protected operation | Show target UUID, expected effect, authority, execution receipt, unknown-outcome recovery path |
| Stop UI or tray | UI closes while Platform service persists; explicit service stop separate |
| Provider/core crash or network loss | Informative degraded/unknown states, no fabricated health or hidden restart |
| Open Lab | Strong synthetic/production separation; production credentials/state unavailable |

## 8. Implementation gates (not automatically scheduled)

**CC-0 | Design acceptance:** owner reviews navigation taxonomy, Core-free empty states, identity displays, secure actions, pop-out behavior and OS support. No implementation claim.

**CC-1 | Read-only shell:** independent Windows/Linux client launches without `sofia-core`; authenticates to local Platform service; shows truthful local identity, status, diagnostics and immutable evidence snapshots. CLI remains usable on headless Debian. No protected effects.

**CC-2 | Manager views:** Fleet, Core, Model, Module and Jobs screens consume real versioned API projections. Detachable views, keyboard navigation and stale-state handling. Reuse existing foundations rather than cloning canonical state.

**CC-3 | Governed effects:** begin with reviewed low-risk effects, then separately authorize core/package operations and Fleet/security workflows. All use service-side approvals, exact identity/generation, auditable receipts, revocation and rollback fences. Never approve from UI alone.

**CC-4 | Installer/desktop polish:** signed desktop artifacts and shortcuts, tray lifecycle, start-at-login policy distinct from OS service, Windows and Debian desktop clean install/uninstall, upgrades, recovery, accessibility and resource testing.

**CC-5 | Independent acceptance:** actual installed-host Windows/Linux tests, Core-free and synthetic Core tests, multiple windows and session revocation, offline Fleet, denied effects, process crash, startup without GPU/Ollama and exact-SHA CI. Real production Fleet/G8 remains separately authorized.

**Release fence:** Platform-only #201 remains primary; CC-0 design can happen in parallel. Do not mark GUI CC-1 through CC-5 as shakedown blockers unless the owner separately approves expanding #201; do not reclassify existing Platform service/security acceptance as optional because a GUI can be deferred.

## 9. Existing source and migration notes (2026-11-06 source review)

- `src/sofia/modules/ui/control_center.py`: tray commands, Fleet health counters and a categorized Settings hierarchy. Useful UI/behavior references but mostly Sofía-personal, not a Core-free native shell.
- `src/sofia/modules/ui/settings_window.py`: existing Tk settings and Fleet candidate list, model controls, approvals. Reuse contracts only after validating host/authority separation and owner-auth changes.
- `src/sofia/modules/ui/core_link_control_center.py`: authenticated remote Core status in Tk, not the full Fleet/Core Manager.
- `rust/crates/sofia-ui-broker/`: durable Rust broker journal foundation from merged PR #198; authenticated runtime broker, full tray and desktop UI remain incomplete.
- `src/sofia/platform/ops/callsigns.py`: local durable callsign authority; remote naming transport still absent.
- [Platform 1.0 source-backed acceptance matrix](../development/PLATFORM_1_0_ACCEPTANCE.md): standalone Platform/SDK installation and distinct development gate; no full native Control Center acceptance.
- PR #202: draft Rust-owned Platform service work. Do not assume its in-progress changes are merged or accepted.

## 10. Open decisions for owner review

1. Confirm default **single Control Center + pop-out manager windows + optional tray**; this document recommends that layout.
2. Confirm **Sofía Workbench separate from Aegis security/management UI**. Shared launcher entry is fine, but no Core is required.
3. Confirm minimum first GUI milestone: read-only Overview, Fleet, Cores, Security status, Diagnostics, Jobs before full manager write actions.
4. Confirm a separate developer-only Lab and Workshop rather than granting those capabilities by default.
5. Confirm CLI-first on Debian server and optional graphical desktop packages on Windows/Linux.

## 11. Status and traceability

AG-D007 design is **fleshed out**, not implemented, merged as product code, verified, or approved as a new Platform 1.0 gate. Capture decisions in `AEGIS_DESIGN_TODO.md`; use GitHub PRs/issues and exact test evidence for implementation later. Keep the current Codex shakedown campaign and existing #201/#120 statuses unchanged.
