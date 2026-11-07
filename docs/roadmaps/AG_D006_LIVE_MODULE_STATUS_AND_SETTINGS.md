# AG-D006 | Live module presence and settings synchronization (GUI + TUI)

**Status:** OWNER-DESIRED UI behavior (2026-11-07), DESIGN CAPTURED, NOT IMPLEMENTED/VERIFIED.
**Owner request:** When a module connects, disconnects, starts, stops, pauses, crashes, is installed, or is removed, **both Aegis GUI and ASCII TUI Settings/Module Manager update automatically without restarting the Platform, either interface, or the Settings view**.
**Existing TODO:** This is an AG-D006 Module Manager refinement and AG-D007/AG-D022 shared UI contract, **not** a separate module manager, canonical registry or new Platform-only #201 gate.
**Affects:** AG-D024 parity review, AG-D023 Core setting changes, AG-D020 Jobs, AG-D016 Diagnostics. Shared colors come from [AEGIS_SHARED_GUI_TUI_THEME.md](AEGIS_SHARED_GUI_TUI_THEME.md).

## 1. What automatically updates

- A module's **installed lifecycle**: discovered, reviewed, staged, installed disabled, activating, active, draining, paused, quarantined, updating, rolling back and removed, using existing lifecycle enums and authoritative receipts. Not every lifecycle state means executable/connected.
- **Runtime connection/health** (a separate axis): health verified from fresh observations, unavailable, unhealthy, observation expired, unknown; do not collapse `ACTIVE` lifecycle into `CONNECTED` without runtime evidence.
- Module **visibility** in the available/installable list versus installed settings list; signed module contract/version/digest/permissions and the associated lifecycle/settings revision.
- Per-module settings availability, saved value, effective revision, pending apply/restart state, last observation time, and actual authorizing actor/receipt as permitted.
- Module actions becoming available or unavailable as active identity, host, lifecycle, package revision, STOP, owner grants and SDK/ABI compatibility change; stale editors can never save against a vanished, replaced or revoked module.
- Offline remote hosts: preserve a clearly labelled last-known snapshot if authorized but show **STALE/UNKNOWN**, not `CONNECTED` or live settings. Fresh source observation alone may only verify a process, not every module capability.

## 2. Target GUI behavior

The GUI Settings > Modules and dedicated Module Manager automatically adds/reorders a module by stable ID as its authoritative catalog changes; keep user-selected module row where it still exists. A newly installed module appears without reopening settings.

- If a module changes to **PAUSED, STOPPED, DISABLED, QUARANTINED or health UNKNOWN**, show its identity and configuration history where authorized, but disable/guard settings that require an active runtime or an exact current signed package. Do not automatically uninstall it or erase saved values.
- If a module is **REMOVED**, remove it from the active Installed list after an authoritative remove receipt, retain independently permitted history/tombstone, and dismiss or invalidate its editable settings panel. Do not infer removal from temporary network loss or missing heartbeat.
- If package digest, module revision, settings schema or active Core/host generation changes during an edit, display the new status and an explicit `REVIEW CHANGES AGAIN` / conflict banner. Preserve typed-but-unsaved user input only in an untrusted local draft; do not silently apply it.
- Show **lifecycle** and **observed health** in separate columns with source and age. Status color uses the shared theme plus text: green for actually verified live, amber for transitional/pending, gray for stale/unknown, red accent for verified faults/quarantine. Never color disabled/stopped as an error without reason.
- Status indicators and menu entries update while window stays open and while detached manager windows are open. If no Core is installed, Platform's module management remains functional.

## 3. Target TUI and command behavior

- The same updates appear in `aegis tui > Modules`, `aegis settings > Modules`, and status indicators without restarting or reconnecting SSH.
- A TUI running in plain numbered-line mode should refresh at menu navigation boundaries and via bounded periodic observation; full-screen TUI may redraw the affected row live, without stealing keyboard focus or scrambling a typed value.
- `aegis modules list`, `aegis modules status <module-id>`, `aegis modules settings <module-id>` and `aegis modules watch` are **PROPOSED CLI**; snapshot-only commands are fresh on each invocation, while `watch` would stream authorized changes and show timestamps until Ctrl-C.
- Changes during a field edit must trigger review/revalidate before submit. No UI or TUI direct database writes. Existing SAFE/STOP/permission checks remain authoritative.

### Proposed ASCII rendering (illustrative, not live health)

```text
+-----------------------------------------------------------------+
| AEGIS > SETTINGS > MODULES                   [AUTO REFRESH: ON]  |
+-----------------------------------------------------------------+
| NAME          LIFECYCLE    RUNTIME HEALTH        OBSERVED        |
| Research      ACTIVE       VERIFIED HEALTHY     fresh           |
| Example       PAUSED       NOT RUNNING           current         |
| Remote        ACTIVE       UNKNOWN / STALE       last seen       |
+-----------------------------------------------------------------+
| [1] Research     [2] Example     [3] Remote     [R] Refresh    |
| [H] History      [W] Watch       [B] Back                       |
+-----------------------------------------------------------------+
```

## 4. Authoritative update protocol (to design and implement, not shipped)

1. **Service-owned catalog/snapshot:** Reuse `ModuleLifecycleManager` receipts/event table, `ModuleSettingsService.catalog()/snapshot()`, `CanonicalPlatformModuleObserver` runtime health and existing signed module settings/contracts. Do not create a second registry, writer or client-side source of truth.
2. **Read-only module change feed (proposed):** Provide a versioned, authenticated, host-scoped stream or bounded long-poll with monotonic event cursor and concrete change categories: lifecycle, package contract, settings revision, verified runtime health, source permission/revocation, resync required. Access-limited payload includes immutable module ID, exact source host/platform ID, digest, generation/revision, event sequence, event timestamp and permitted status; no secrets or unauthorized private Core details. Never treat an event notification as mutation authority.
3. **Client subscription:** GUI and full-screen TUI subscribe after authenticated snapshot; on an event, requery the authoritative affected module (or bounded catalog diff), coalesce bursts, update view **without restarting**. No arbitrary full-screen redraw while editing. Multiple manager windows share one subscribed view model per allowed user/session/target, not multiple state writers.
4. **Fallback:** If push/notification transport is absent, poll the authoritative catalog and health on a bounded interval (illustrative target 2–5 seconds on a local interactive view; choose measured rate limits in engineering review), with exponential backoff for remote/offline hosts. An event feed and polling are both just transport, never a competing authority.
5. **Reconciliation:** On reconnect, event gap, source restart, changed generation, permission revocation, overflow or an unknown cursor, resynchronize from a fresh authenticated snapshot and revision. Never mark stale state live or silently change the host/Core target. If no authorized source, show `UNKNOWN` and last verified observation.
6. **Runtime health:** Lifecycle status and actual runtime observation are separate and have bounded freshness. Existing observer's `ACTIVE` state without fresh verified adapter evidence must appear UNKNOWN, not CONNECTED. A module may remain installed/configurable even when its runtime worker is not executing.
7. **Editing and effect:** Before any module settings write, enforce exact module ID, signed package digest, lifecycle revision, settings expected revision, current approval, STOP and owner identity. Current module settings service already checks lifecycle/package/settings revisions; transport/GUI must not weaken it. A disappeared/updated module invalidates an old edit. **No silent module reload/restart**: a setting requiring COMPONENT_RESTART shows PENDING with a separate approved restart action.
8. **Durability and privacy:** Persist change receipts at existing canonical owner only; UI may cache nonsecret projections under per-user constraints, never live status without freshness, private Core settings outside authorized scope, or owner secret. UI exit leaves Platform and module processes untouched.

## 5. Source-backed overlap (2026-11-07 GitHub snapshot)

- `src/sofia/platform/modules/lifecycle.py`: real `ModuleLifecycleManager`, lifecycle enum and `platform_module_lifecycle_event` with authorized transitions. Preserve.
- `src/sofia/platform/modules/observer.py`: `CanonicalPlatformModuleObserver.health()` distinguishes fresh verified runtime ACTIVE evidence from `UNKNOWN_STATE`, with freshness bounds. Preserve.
- `src/sofia/platform/modules/settings.py`: `ModuleSettingsService.catalog()` provides module ID, package digest, lifecycle and revision, saved/effective settings revisions, settings contract/identity, excluding discovered/removed records. Preserve.
- `src/sofia/platform/modules/control_center.py`: bounded read-only module lifecycle/health/status text projection; not a live TUI. Reuse.
- `src/sofia/modules/ui/core_link_settings.py`: existing authenticated `module.settings.list` / `module.settings.snapshot` / `module.settings.update` client and a Tk **Refresh modules** button. The module window only queries the catalog at opening or on manual refresh, while its periodic `poll()` drains completion-queue updates; this is **not** a confirmed autonomous module lifecycle subscription. Existing parent window `settings.events` polling covers canonical settings updates, not proven module catalog auto-change behavior.
- `src/sofia/platform/core_link/conversation.py`: authenticated settings/modules control boundary; avoid unreviewed direct Core database access.
- No repository inspection here establishes a deployed/native GUI/TUI event feed, exact automatic refresh latency, or installed-host tests on Windows/Debian. The owner-requested end-to-end behavior is a **missing acceptance requirement**, not a currently guaranteed function.

## 6. Test/acceptance requirements

- Launch GUI and SSH/PowerShell TUI once, then **install, stage, activate, pause, resume, crash/quarantine, update, disable and uninstall a disposable signed module** via approved backend. Every transition appears in both interfaces without restarting either UI, Platform or unrelated modules. Verify exact target ID, lifecycle/health/recency, no fake health.
- Prove actual worker failure or lost health evidence changes the displayed **runtime health** to UNKNOWN/DEGRADED even if lifecycle remains ACTIVE. No fake CONNECTED status from lifecycle alone.
- Change a module settings value through an authorized client: both GUIs/terminal clients display matching saved and effective revisions, with PENDING RESTART if appropriate; no automatic worker/service restart merely because an event arrived.
- Test an edit race: module is updated/removed while a GUI or TUI field has unsaved input. Both refuse stale writes, show revision/identity conflict and retain typed input for safe user review without exposing secrets.
- Missing event, duplicate/out-of-order event, cursor gap, source restart, 2+ windows, SSH reconnect, UI crash, permission revoke, STOP, offline remote host, and long-lived low-activity sessions must resynchronize or show UNKNOWN correctly.
- Validate status color and plain ASCII labels using shared Aegis palette, `NO_COLOR`, narrow terminal and screen reader; no unbounded polling, CPU churn or credential leakage.
- Mark VERIFIED only with actual exact-SHA tests on independently installed Windows/Linux hosts; no inference from Tk existing refresh or module lifecycle unit tests.

**Scope fence:** This is UI/state observation and authorized settings synchronization. It does **not** promise arbitrary third-party hardware hotplug, OS driver hot reload, unattended module install, bypassing module approval, dynamic unsigned code loading or runtime/component restart-free application of every possible setting. Such effects remain individually governed.
