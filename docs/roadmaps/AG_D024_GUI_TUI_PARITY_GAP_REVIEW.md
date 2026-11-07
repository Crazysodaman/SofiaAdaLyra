# AG-D024 | Aegis GUI/TUI parity and operator-experience gap review

**Status:** OWNER-REQUESTED DESIGN AUDIT (2026-11-07); owner wants the same palette on GUI and TUI and asked what else is missing. **CAPTURED**, NOT A NEW PRODUCT MANAGER OR CODING AUTHORIZATION.
**Baseline:** GitHub `main` `5fea1df38bc6e1f2cd5c7744c7be7b222c45fe0f` inspected for this audit; subsequent shared-theme docs are design commits only. This is source/docs inspection, **not** executable acceptance, exact-SHA Windows/Debian UI CI or deployed-host observation.
**Authoritative targets:** AG-D007 (GUI), AG-D011 (installer), AG-D022 (headless terminal), AG-D023 (Core self-settings), AG-D013 (security), AG-D020 (jobs), AG-D016 (diagnostics); Platform-only #201 remains independent and not automatically expanded.
**Shared colors:** [Canonical Aegis GUI + CLI/TUI theme](AEGIS_SHARED_GUI_TUI_THEME.md), with separate [terminal rendering rules](AEGIS_CLI_TUI_COLOR_THEME.md).

## 1. Verified design inventory: don't duplicate it

The following **already exist in current specs** and should be refined rather than recreated:
- **Manager navigation:** AG-D007 GUI has Overview, Fleet, Cores, Models, Modules, Catalog, Jobs, Hardware, Updates, Security, Backups, Diagnostics, Lab, Workshop and Platform Settings. AG-D022 TUI has corresponding numbered menus. No new separate dashboard category is needed.
- **Always-visible target / trust state:** AG-D007 and its layout specification already require stable Platform/Core IDs, remote trust, freshness and Core-free empty states. AG-D022 has local/remote health and explicit UNKNOWN/STALE. Finish shared interaction behavior rather than add new stores.
- **Keyboard and accessibility baseline:** AG-D007 has Ctrl+K/search, responsive UI, scaling, detaching windows and focus expectations; AG-D022 has numeric fallback, help, search, `NO_COLOR`, line mode and SSH.
- **Safe action taxonomy:** AG-D007 and AG-D022 already distinguish read-only, proposals, approval, executable effect and actual receipts. Existing SAFE, STOP and 256-bit owner-secret code is independent of UX.
- **Backends:** `src/sofia/platform/config/settings_authority.py` has revisions, ownership, CAS, idempotency and effective apply states; `platform/core_link/conversation.py` has scoped authenticated Core Link settings operations; `platform/modules/settings.py` has signed module settings; `platform/safe/approval_inbox.py` and `approval_inbox_cli.py` cover existing pending approvals; `platform/ops/backup.py` and `backup_cli.py` cover backup foundations; `platform/ops/callsigns.py` holds local Fleet naming. Preserve them.
- **Existing presentation fragments:** `src/sofia/modules/ui/settings_window.py` (Tk Sofía-specific), `src/sofia/modules/ui/core_link_settings.py` (authenticated GUI projections), `src/sofia/modules/ui/theme.py` (personal adaptive theme; partial purple/cyan/lime), `src/sofia/platform/ui_launchers.py` (per-user launcher handling). `rust/crates/sofia-ui-broker/` is policy/journal foundation, not a complete neutral Control Center desktop UI.
- **Installer style:** AG-D011 already defines one-script ASCII installer and explicitly separate owner approval, repair and recovery, and now the terminal color palette.

These pieces are **partial implementations or design coverage**, not proof that a complete neutral GUI/TUI or installed native management service exists.

## 2. Real gaps / cross-cutting requirements

| Gap | Current foundation / design | What is still needed | Priority / existing tracking |
| --- | --- | --- | --- |
| **01. Shared GUI + TUI design tokens** | Existing CLI theme and partial personal `theme.py`; GUI earlier had near-black/teal design. | Adopt the **same exact Aegis dark tokens** on all neutral GUI/TUI/installer screens, with per-renderer contrast/ANSI/high-contrast behavior. Do not let Core emotion recolor security controls. | **P1**, this AG-D024 + shared theme, AG-D007/022/011. |
| **02. One actual authenticated management contract** | Canonical settings / SAFE and Core Link foundations; #201 row for local authenticated CLI/IPC is not accepted. | Common read/preview/commit/receipt semantics for native GUI/TUI, protected by service-side identity/revocation, not frontend SQL or shell hacks. | **P0 dependency**, #201 / AG-D007/022. |
| **03. First launch, disconnected service, bootstrap/repair** | AG-D011 installer, GUI first-open Core-free, diagnostics. | Distinguish **NOT INSTALLED / INSTALLED SERVICE STOPPED / NO AUTH / INCOMPATIBLE API / OFFLINE / UPGRADE REQUIRED / READY** and offer only safe grounded next steps. Separate user-session UI launch from machine service activation. | **P1**, AG-D011/007/022/016. |
| **04. Host + Core scope selector** | Stable identity/trust and stale handling already specified, local Fleet callsign authority partially built. | One clear identity breadcrumb/selector with an explicit local/remote badge, independent Core selector, permission level, verified timestamp and revalidation on every action/window/terminal reconnect. Never silently act on previous host. | **P1**, AG-D007/012/022. |
| **05. Settings preview with effective-state parity** | Existing CAS revision, field-owner, apply-class, event and receipt contracts; GUI/TUI settings views proposed. | One typed field catalog shared by GUI forms and terminal menus: current vs proposed, pending apply/restart, constraints, precedence, last actor, rejected/conflicting revisions, undo where policy allows. | **P1**, AG-D007/022/023. |
| **06. Secure owner authentication on headless/remote hosts** | Existing attended 256-bit owner-secret mechanism is signed-in Venus Windows bounded; owner browser/inbox foundations. | Review remote/headless approval ceremony (e.g. approved owner-side challenge and one-use signed grant) without entering secrets into logs, argv, model, environment, untrusted SSH prompts or using the TUI as its own authority. No blanket admin login. | **P0 security prerequisite**, #201 + AG-D013/022. |
| **07. Unified operations + notification inbox** | Existing approval inbox, jobs/OPS receipts, Sofía-specific tray/notifications. | One per-principal activity surface for both clients, with exact operation state, cross-session continuation, cancellation/unknown-outcome reconciliation, bounded notices, quiet-hours/privacy and a notification-to-job/approval deep link. Do not build a second job engine. | **P1**, AG-D013/020/007/022. |
| **08. Offline/stale/no-Core empty states** | AG-D007/022 documents these concepts. | Consistent reusable screens: disconnected remote target, no local service, no Core/model, missing plugin, wrong version, revoked access, stale telemetry and unknown service health, with safe refresh and read-only cached evidence labels. | **P1**, AG-D007/022/016. |
| **09. Safety and destructive operations UX** | Existing owner approval and design dialogs, scoped SAFE, Core retention policy AG-D008. | Shared preview sequence, exact target, affected data, permission expiry, backup state, side-effect/rollback bounds, state change and separate irrecoverable purge flow; identical trust semantics across GUI/TUI. | **P1**, AG-D007/008/013/014/022. |
| **10. Search, help and keyboard workflows** | GUI command palette Ctrl+K and TUI `/`, `?`, numeric navigation already proposed. | One reviewed nonsecret command/setting metadata catalog for searchable help, contextual docs, accessible shortcut reference and consistent search permission filtering. Search results are navigation, not implicit execution. | **P2 UX**, AG-D007/022. |
| **11. Backup/recovery/diagnostics presentation** | OPS backup CLI/engine, doctor/health and incident docs. | Read-only backup integrity, last restore test, lineage, sanitized diagnostics export and explicit state-recovery plan surfaced in both UIs; distinguish available recovery from proven restore. | **P1/P2**, AG-D014/016/007/022. |
| **12. Core autonomy policy visibility** | AG-D023 spec, canonical settings and permission stores. | Per-Core permissions/allowed ranges/expiry/current grant/pause/proposal/undo in both GUI and TUI; bounded Core self-adjust executor after separate approval and negative testing. Core is not an administrator. | **P2, after security**, AG-D023/013/007/022. |
| **13. Unified distribution + update UX** | Per-user GUI launcher, AG-D011 installer; Rust broker policy; staged signed release components. | Signed GUI/TUI packages, optional headless install, installer selection, executable entrypoints, version compatibility warnings, UI-only uninstall, crash-safe updates and controlled OS-tray/start-at-login behavior. | **P1/P2**, AG-D011/015/007/022. |
| **14. Accessibility, performance and test evidence** | Existing specs include scaling/keyboard/ANSI fallback but no complete integrated native acceptance. | Keyboard-only + reader + screen reader + zoom, 40/80-col + SSH + `NO_COLOR`, truecolor/16/256 fallback, offline/revoked/null states, multiple GUI windows, resource limits and no fake UI success; cross-client contract tests on disposable Windows/Debian. | **P1 acceptance**, AG-D007/022, separate GUI/TUI acceptance not silently merged into #201. |

**Evidence scope:** The words "still needed" mean required for the owner-desired finished cross-surface product, not that every underlying helper/function is absent from the repository. Existing components must be inspected/reused during implementation. No row is declared shipped merely because a source module or existing test exists.

### Module live-status synchronization refinement (2026-11-07)

The owner additionally requires that **GUI and TUI Module Manager/Settings automatically show connected/disconnected, lifecycle and runtime-health transitions without restarting either UI or Platform**. This is a refinement of existing AG-D006 and the shared-settings/offline/empty-state gaps, **not** a new module manager. See [AG-D006 live module status design](AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md). Existing module lifecycle event table, read-only observer and authenticated settings catalog are reusable, but the legacy Tk module-settings catalog presently exposes a manual Refresh button, so production auto-subscription is not verified. Use one canonical host-scoped event/snapshot contract with revision/cursor resynchronization and bounded polling fallback. Test installed/active/paused/removed and ACTIVE-but-health-unknown transitions across both clients without service restart, plus a concurrent settings edit to confirm safe invalidation.

### Persistent Module uninstall and reinstallation policy

The owner also requires distinct **uninstall/allow reinstall** and **uninstall/block reinstall** choices, a separate retained-data/purge decision and an owner-only unblock. This expands the existing AG-D006 Module Manager lifecycle UX, **not** a duplicate installer or a new manager. [AG-D006 uninstall/reinstall policy](AG_D006_MODULE_UNINSTALL_REINSTALL_POLICY.md) specifies parity in GUI/TUI, block priority over Core requests/auto-update/dependencies, accurate interrupted removal, and exact signed-package/data migration before any approved reinstall. Current module lifecycle already has `REMOVED`; a persistent install-deny policy and a verified reinstall workflow have not been established. Both client frontends must observe the same policy/receipts without a restart.

## 3. Concrete shared interaction pattern

### Status / navigation

1. **Select target:** immutable Platform ID + trusted callsign, location LOCAL or explicitly authorized REMOTE, observed timestamp/health/trust label.
2. **Select manager:** Overview/Fleet/Cores/Models/Modules/Security/Jobs/Backups/Updates/Diagnostics/Settings. Same information model in both clients, different widgets.
3. **Read detail:** current settings revision, effective state, permission read scope and source of truth; no direct Core/Platform canonical DB from clients.
4. **Preview change:** old/new value, constraints, actor, target identity/generation, required approval and whether effect is live or restart-bound. No mutation yet.
5. **Authorize if necessary:** actual owner-specific one-use/trust ceremony; TUI/GUI buttons do not substitute for a fresh grant.
6. **Dispatch and observe:** submit idempotent request through canonical Platform operation owner; show QUEUED/PENDING/UNKNOWN vs final VERIFIED; reopen a job after closing UI.
7. **Reconcile:** if remote UI loses connection, do not infer failure or replay a potentially executed operation. Refresh the authoritative receipt; if unknown, show recovery path.

### First-visit flows

- **Platform not installed:** link to independently signed installer/AG-D011, do not create an identity via a UI side effect.
- **Platform installed but service stopped:** explain actual service state, show permission-scoped start/diagnostics request, don't assume starting UI starts service.
- **Service ready, Core absent:** normal healthy Core-free Platform, with optional component planning and no Core automatic installation.
- **Core installed but model missing:** explicit Core degraded/no inference, Platform operational; don't mark conversation functional.
- **Disconnected Fleet:** show stale last observation and time, gray UNKNOWN, no protected remote execute.
- **Owner security unavailable:** show read-only inspection if authorized and an exact reason why protected effects cannot proceed, not a generic "click OK to bypass".

## 4. Suggested owner-reviewed implementation order

- **Dependency first:** Finish #201 Platform service, signed installer and authenticated management CLI/IPC, SAFE/STOP and owner authority. All UI effects depend on this; don't overwrite existing work.
- **UI-1 (read-only):** Common tokens + neutral Core-free Windows/Debian GUI/TUI overview, host selector, permission-filtered menu and diagnostics, verified session freshness, zero-Core states.
- **UI-2 (safe settings):** Shared typed settings editors and revision/effective receipts, keyboard/accessibility/small terminal, read-only jobs/approvals.
- **UI-3 (governed actions):** Owner-approved real effects across both, job tracking and recovery, remote target denial and identity fencing, exact signed package previews.
- **UI-4 (polish):** Notifications and contextual help, Core-autonomy management once independently accepted, multi-window/session recovery, distribution updates, light/high-contrast accessibility overrides.

Do not create a separate UI-only Platform authority, duplicate Fleet registry, duplicate settings engine, run remote shell to replace managed API, or schedule all UI as a new #201 release blocker. Each row requires actual source SHA, tests and installed-host evidence before VERIFIED.

## 5. Acceptance scenario set

A. Compare GUI vs TUI for the **same** authorized source snapshot on Windows and Debian: identical Platform/Core IDs, settings values/revisions/owners/apply states, trusted Fleet status, approved operation IDs and SAFE/STOP status.

B. Change one low-risk reversible setting in each interface using the same reviewed API and exact granted scope. Verify both observe the **same** canonical revision and truthful applied/pending outcome. Force a stale expected revision; the second edit must reject and offer refresh rather than overwrite.

C. Open remote host A, then switch to host B, close/reopen a detached GUI window or SSH TUI. No request targets the old host, nickname, old generation or stale authority. Revoke the grant mid-flow; both UIs block.

D. Start an authorized job, disconnect GUI/TUI and reconnect: accurate operation ID persists, outcome UNKNOWN stays unknown until receipt reconciliation, and no duplicate effect occurs.

E. Show error and STOP states in exact owner palette on native GUI and 24-bit terminal, then GUI high-contrast and 16-color/monochrome SSH; messages remain readable and complete without color.

F. Launch both UIs when no Core/GPU/model/GUI session exists. TUI must run headless and GUI on a desktop must run independent of the personal Core. Native service remains untouched when the client exits.

G. Test installer missing/stopped service, wrong signed release, no owner grant, missing Fleet trust, offline, incompatible API version, screen-reader navigation, 200% font scale and 40-column line mode.

**Release truth:** This is a design-level audit and owner backlog refinement, not a code/CI audit of completed GUI/TUI implementations, not a declaration that the release is ready, and not permission to touch protected state.
