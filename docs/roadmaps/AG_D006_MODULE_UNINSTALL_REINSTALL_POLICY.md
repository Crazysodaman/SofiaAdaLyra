# AG-D006 | Module uninstall, do-not-reinstall policy, and governed reinstall

**Status:** OWNER-DESIRED DESIGN (2026-11-07), CAPTURED, NOT IMPLEMENTED OR SCHEDULED.
**Owner request:** When uninstalling a module, offer a choice to **allow reinstallation later** or **never automatically reinstall it**, with a deliberate owner-controlled route for reinstallation if the owner changes their mind.
**Existing home:** This refines AG-D006 Module Manager, AG-D006 live module status, AG-D007 GUI, AG-D022 ASCII headless TUI and AG-D023 bounded Core autonomy. Do not create another module lifecycle manager, package registry, settings writer, or hidden #201 release blocker.
**Release fence:** This document captures desired UX and policy; no production uninstall, disable, install, retention purge, trust change or protected state operation is authorized merely by its existence.

## 1. Semantics: uninstall and reinstall eligibility are distinct decisions

Module **uninstall** means an independently authorized lifecycle operation deactivates/stops the exact module, unregisters its capabilities, and removes its installed executable/service surface according to retained-package policy. Its durable audit/release evidence remains unless independently approved retention cleanup occurs.

An **installation deny policy** is separate, durable authorization state that tells every governed installation path to refuse matching candidates until an independently authorized owner changes that rule. The rule is **not** software availability, a model prompt, a UI-only hidden flag, an anti-malware blacklist, or a promise the physical host can never be manually modified by its human OS administrator.

### User choices at uninstall

1. **Uninstall and allow future reinstall** (recommended default): remove the module from active/installed service. Keep signed package/audit lineage according to retention policy; allow **future approved** installation, not automatic reinstall by default.
2. **Uninstall and block future installs**: first durably commit the exact module install-deny rule, then attempt governed deactivation/removal with its own receipt. The deny rule prevents automatic and manual *Aegis-governed* installs until **owner-authorized unblock**. If uninstall fails or status is unknown, report **BLOCKED BUT STILL INSTALLED / OUTCOME_UNKNOWN**, never pretend removal completed.
3. **Cancel**: no effects; if a partial operation has already started, show its real reconciliation receipt rather than calling it cancelled.

**Independent data decision:** For either uninstall option, default to **retain module settings/private data**. Advanced **purge module data** is a separate destructive exact-scope ceremony with backup dependency and resource/retention preview; it never piggybacks on a checkbox or on `block`. Removal from the active catalog does not erase authorized audit history, grants, security logs, or encrypted backed-up copies.

Neither `ALLOW` nor unblocking grants a Core an installer permission. A Core may propose a reinstall only under its separate capabilities; owner authorizations remain required for actual package installation/activation.

### When a Core requests the uninstall

The owner additionally wants to consider Core-initiated removal. Follow [AG-D006 Core-Initiated Module Removal](AG_D006_CORE_INITIATED_MODULE_REMOVAL.md): an authenticated Core may propose a precise uninstall, but cannot authorize or perform production `module.remove` itself. The current SAFE classification is **PROTECTED** (not standing-grant reversible), and module RUN requires owner authority. GUI/TUI show Core identity, reason, independently observed dependencies and capability impact; owner chooses **remove/allow later approved reinstall**, **remove/block future Aegis installs**, **defer** or **deny** through exact approval. The Core cannot purge data, block/unblock, reinstall, change grant scope or bypass STOP. Any future autonomous disposable LAB cleanup must be separately designed and authorized. Even an owner-approved `remove()` records `REMOVED` while retaining package bytes; physical purge is not part of it.

## 2. Proposed GUI/TUI uninstall review

```text
+-----------------------------------------------------------------------+
| AEGIS > MODULES > <VERIFIED MODULE ID> > UNINSTALL                      |
+-----------------------------------------------------------------------+
| Host:      <VERIFIED LOCAL OR REMOTE PLATFORM ID>                       |
| Module:    <SIGNED MODULE ID AND PUBLISHER>                             |
| Version:   <SIGNED VERSION / EXACT PACKAGE DIGEST>                     |
| Runtime:   <LIVE HEALTH EVIDENCE / UNKNOWN>                             |
| Dependents:<VERIFIED DEPENDENCY COUNT / UNAVAILABLE>                    |
+-----------------------------------------------------------------------+
| What should happen after uninstall?                                   |
|                                                                       |
| [1] REMOVE, ALLOW FUTURE REINSTALL     [default]                       |
| [2] REMOVE, BLOCK ALL FUTURE INSTALLS OF THIS MODULE                  |
| [0] CANCEL                                                            |
|                                                                       |
| Module data: [KEEP SETTINGS AND DATA]  (default)                      |
| [D] Review independent destructive data-purge options                 |
| [V] View dependencies / signed identity / exact permissions          |
+-----------------------------------------------------------------------+
| [P] Preview effects     [A] Authorized review     [B] Back            |
+-----------------------------------------------------------------------+
```

In GUI use a modal with the same meaning, exact issuer and host IDs, module publisher, digest, existing data size if known, affected dependents, and scoped approval. **Neither GUI button nor TUI `Y` is permission by itself.**

After removal, the active Installed list removes the module, the catalog records it as `AVAILABLE_FOR_APPROVED_REINSTALL` or `BLOCKED_BY_OWNER`, and the history retains its removal receipt. A revoked/unknown host is `UNKNOWN/STALE`, not `REMOVED`.

Proposed commands (NOT currently certified):

```text
aegis modules remove <module-id>             # interactive preview/choices
aegis modules policy <module-id>             # read-only eligibility and reason
aegis modules blocked                       # list owner blocks
aegis modules block <module-id>              # separately owner-authorized deny
aegis modules unblock <module-id>            # separately owner-authorized policy removal
aegis modules reinstall <module-id>          # independently approved signed reinstall
aegis modules history <module-id>            # authorized lifecycle receipts
```

The proposed `--block-reinstall` and `--keep-data` flags must never substitute for owner authorization. No general `--force` bypass of denials or SAFE/STOP.

## 3. Deny rule identity, scope, and priority

- **Identity:** key by signed **module ID plus trusted publisher identity/key lineage**, not display name or path. Reject attempts to impersonate the ID or change the spelling. Store package/signer evidence and policy revision. Explicitly decide whether aliases, package renames, re-signed releases or vendor changes are the same lineage; unknown identity equivalence must fail closed for automatic reinstallation and request owner review.
- **Policy target default:** block **all future versions** and all package digests under that module identity, including downgrade, upgrade, rollback, reinstallation as a transitive dependency, scheduled repair, reconciliation, auto-update and autonomous Core request. A narrow **exact-release block** can be a separately approved advanced option for a bad version; it must not appear to be a blanket module ban.
- **Scope default:** this Platform only. An optional **Fleet-wide block** requires separate multi-host authorization and positive acknowledgments from each enrolled target. Offline or untrusted hosts cannot truthfully be reported as blocked; report pending/incomplete. Do not confuse local block with a remote Fleet guarantee.
- **Precedence:** explicit owner block overrides package catalog suggestions, desired-state reconciliation, previous installation approvals, Core autonomy grants and standing installer permissions. SAFE/STOP and current owner revocation are never weakened. Installation and activation must independently recheck block policy at **planning, admission, effect and recovery** boundaries; a UI filter is insufficient.
- **Persistence:** canonical Platform policy store with owner identity, exact policy subject, reason (optional), revision/generation, timestamp, expiry policy (default **no expiry**), approval receipt and audit event. Persist across Platform/GUI/TUI restart, module removal and authorized software updates, with atomic durable transaction and backup/restore consistency. A restore/re-enrollment may not silently resurrect a previously revoked policy or erase an effective block; reconcile trusted policy lineage before activation.
- **Unblock:** only explicit attended owner-scoped reauthorization (through approved owner proof) creates a policy revision to allow future installations again. Unblocking **does not install, activate, or auto-start anything**.
- **Never means governed Aegis never auto-installs unless you deliberately change it.** This is not physically irreversible against the human OS owner; say that clearly in UI copy.

## 4. Reinstall options after allowed/unblocked removal

Opening a signed package or `aegis modules reinstall <module-id>` creates a **plan**, not an activation.

- **Restore retained settings/data (default only if safely compatible):** verify exact immutable module identity, signer trust, package/API compatibility, settings schema, state-namespace and migration contract, backup/lineage and private data audience. If any check is missing or conflicts, no restore; show `MIGRATION_REQUIRED` and ask for approved migration or fresh install. Never import a Core's protected memory or another module's namespace.
- **Fresh configuration:** install with clean module settings namespace only through an explicitly authorized replacement/migration procedure. Retained old state stays separately protected until independently purged. Never silently truncate the canonical settings row.
- **Choose version/provider:** display signed publisher, exact hash, granted scopes, current revocation, needed capabilities/dependencies and install/activation effects. No trust from friendly name or previous use alone.
- **Dependency check:** if a dependent module requires this removed or blocked module, show what will be inoperable and refuse implicit unblock. A reinstall may be planned only after all blocks/permissions/compatibility constraints are satisfied.
- **Separate effect:** signed install and module activation remain distinct approved steps; no silent enable/start from restore or unblock. A previously authorized permission grant should not automatically return merely because a package with the same name reappeared: revalidate package digest, generation, scope, expiry and current revocation.
- **Uncertain outcome:** interrupted install/uninstall, crashes or remote link loss remain `OUTCOME_UNKNOWN`; reconcile before retrying or claiming healthy. Block policy remains intact even if component teardown failed.

### Example eligibility labels

- `NOT_INSTALLED / REINSTALL_ALLOWED`: may submit an approved reinstall request.
- `NOT_INSTALLED / BLOCKED_BY_OWNER`: deny plan/execute and show independent owner-only unblock.
- `INSTALLED / BLOCKED_BY_OWNER`: removal incomplete or separately blocked while installed; no auto-start, quarantine/stop as supported and show real operation state.
- `REINSTALL_PENDING_APPROVAL`: approved source not yet given execution authority.
- `MIGRATION_REQUIRED`: retained config incompatible with signed candidate.
- `RESTORE_UNVERIFIED`: data/restore has not passed evidence checks.
- `OUTCOME_UNKNOWN`: recovery is required before another effect.

The UI must display **installation eligibility**, **installed lifecycle** and **runtime health** as separate axes; it must never display green `CONNECTED` from only a package metadata row.

## 5. Live GUI/TUI behavior, no restart

- After owner block, uninstall, unblock or reinstall state is committed, active GUI and ASCII TUI show the revised catalog/permission state automatically using the [AG-D006 live status design](AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md) feed plus bounded polling fallback. No need to relaunch Settings, reconnect SSH or restart unrelated modules.
- Removing an item from Active Installed does not hide it from `History` or `Blocked`; keep safe read-only metadata. Once unblocked, it returns to `Available` but **not** to active runtime.
- A module blocked while install/repair/recovery is already in progress must be fenced before next effect. If start/stop outcome is unknown, show it honestly, not silently retry.
- If the user is editing settings when the module is removed/blocked/upgraded, invalidate the saved revision and prevent stale submission; preserve only nonsecret draft in UI until discarded.
- Sofía and other Cores may *recommend* a module under their proposal permissions, but cannot bypass a block or reissue an owner permission merely because the same capability becomes desirable.
- Shared theme: black `#000000`, purple `#9400D3`, cyan `#00C2FF`, lime `#39FF14` success, amber `#FFB000` pending, red `#9F0202` danger accent with readable light text. Blocked/denied states always have explicit labels.

## 6. Reuse existing implementation and identified gap

**Already in repository (2026-11-07):**
- `src/sofia/platform/modules/lifecycle.py`: `ModuleLifecycle.REMOVED`, `ModuleLifecycleManager.plan_remove()` and `remove()` with guarded allowed lifecycle states and dependent-module refusal. `remove()` retains package bytes for audit/rollback and is not a purge. `discover()` sees existing module ID and rejects a different digest; a removed same-digest row is returned unchanged. **Therefore true new-version reinstall after removal is not established simply by calling existing `discover()`.**
- `src/sofia/platform/modules/settings.py`: module settings catalog excludes discovered/removed rows; saved configuration is scoped to package identity/schema and different signed package requires reviewed migration.
- `src/sofia/platform/modules/package.py`: signed manifest has module ID, version, publisher and package digest/compatibility inputs to underpin policy subject and safe reinstall.
- `src/sofia/platform/modules/operations.py`: existing operation receipts and external worker lifecycle; do not bypass.
- `docs/roadmaps/AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md`: existing live status design for GUI/TUI.
- GitHub code search found no separate current `module blocklist` implementation. A persistent owner-deny rule, policy-aware install/activation, clear unblock process, reviewed reinstall state machine, Fleet coordination and installed-host end-to-end evidence are **design gaps**, not already finished code.

## 7. Acceptance and security tests (not run)

1. Owner-authorized `uninstall, allow reinstall` keeps protected audit/state; blocked alternative persists deny across restart/reboot, reinstall/rollback/update and automatic reconciliation.
2. A Core request, CLI installer, GUI, desired-state job, catalog auto-fix, dependency resolver and older queued install all **deny** the exact blocked identity with an auditable reason; no UI-only filter or bypass.
3. A block commit followed by failed/uncertain removal shows `INSTALLED/BLOCKED` or `OUTCOME_UNKNOWN` accurately; STOP and dependency constraints remain authoritative. Module is not marked removed or healthy without receipts.
4. Fresh owner-authorized unblock **alone** never reinstalls, activates, reassigns grants or starts dependencies. New signed install and separate activation work when eligible and compatible.
5. Block-all-versions policy handles different digest, approved update/downgrade, re-signed publisher, alias spoof, renamed package, and exact digest exception using reviewed identity/lineage rules.
6. Reinstall retained compatible module settings versus fresh config; incompatible schema prompts approved migration; protected private data/audit never erased by ordinary uninstall/block.
7. GUI + TUI open throughout transitions update `Installed`, `Available`, `Blocked`, `History`, pending status, signed identity and editability without UI/Platform restart, with revoked/stale/offline host handling.
8. Signed digest, exact host/owner approval/SAFE/STOP, current revocation, monotonic revision, interruption/power loss, backup restore, privacy redaction and denied unauthorized remote changes proven on disposable Windows/Linux hosts.
9. Fleet-wide denies must report individually verified per-host installation of the rule; offline/missing acknowledgments are pending, not done.

**Implementation status:** UI decision captured; code behavior not implemented or production-accepted. This does not authorize real-host module uninstall, identity purge, production Fleet operation or expansion of #201 release gates.
