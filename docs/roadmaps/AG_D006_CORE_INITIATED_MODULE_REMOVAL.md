# AG-D006 | Core-initiated module uninstall proposals and owner control

**Status:** OWNER-REQUESTED DESIGN REFINEMENT (2026-11-07), CAPTURED, NOT IMPLEMENTED OR SCHEDULED.
**Owner question:** What happens if Sofía or another Core is the actor that wants to uninstall a module?
**Scope:** Refines AG-D006 Module Manager, [uninstall/block/reinstall policy](AG_D006_MODULE_UNINSTALL_REINSTALL_POLICY.md), [live status](AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md), AG-D007 GUI, AG-D022 TUI, AG-D023 Core self-management and AG-D013 Security/Approval Inbox. Do not create a second uninstall engine or secret/permission authority.
**Baseline:** GitHub main checked 2026-11-07. Current `src/sofia/platform/safe/permissions.py` explicitly classifies `module.remove` as `PermissionLevel.PROTECTED`, **not** `REVERSIBLE_SCOPED`. Its ordinary standing grant API permits only `REVERSIBLE_SCOPED` capabilities. `src/sofia/platform/modules/operations.py` requires authenticated owner principal plus matching approval for admitted module operations. `src/sofia/platform/modules/lifecycle.py` authorizes removal against exact module ID/revision, refuses installed dependents and an active batch; `remove()` transitions to `REMOVED` **retaining package bytes for audit/rollback**. It is not a physical purge. No installed-host test proved Core-originated uninstall.
**Release fence:** No Core autonomous `module.remove` allowed under current SAFE. Recording the design does not create grants, alter the permission classification, enable background removals, touch any module or modify #201 acceptance.

## 1. Owner intent and recommended default

**A Core may initiate an uninstall PROPOSAL, but is not the removal authorizer.**

1. **Observe:** Core reads only its appropriately scoped installed-module and fresh runtime/dependency summaries.
2. **Suggest:** Core submits a structured reason for removing an optional, unused or malfunctioning module. This has zero module lifecycle, capability, service or disk side effects.
3. **Prepare:** Platform generates a reviewed, inert removal plan: exact signed module ID, publisher/signing lineage and digest, selected Platform ID, installed revision and state, dependents, active jobs and leases, what the Core would lose, recovery/rollback, retained settings/data policy, permissions to be revoked and any actual service interruptions.
4. **Owner decision:** GUI and TUI Owner Inbox shows who requested the change, complete target identity, source of suggestion, reason and evidence quality, exact plan and choices:
   - `[1] APPROVE REMOVE; allow only future separately authorized reinstall` (recommended default).
   - `[2] APPROVE REMOVE; durably block future Aegis-governed installs of this signed module identity`.
   - `[3] DEFER / ASK CORE WHY`.
   - `[4] DENY (no effects)`.
   The data retention default is KEEP; purge is not part of this request.
5. **Execute:** Only a current exact, one-use independent owner approval is admitted by Platform/Module Host SAFE authority, with identity, digest, host/generation, lifecycle revision, STOP, dependency graph, active leases and block policy rechecked before any effect. It may command reviewed drain/unregister/pause as required, then current guarded `ModuleLifecycleManager.remove` transitions to `REMOVED`. A module not in an allowable removal state gets a separate reviewed plan; the Core must not bypass it or call a generic OS shell.
6. **Report:** Core and GUI/TUI receive the same real receipt: `PROPOSED`, `AWAITING_APPROVAL`, `DENIED`, `RUNNING`, `REMOVED_VERIFIED`, `BLOCK_COMMITTED_BUT_REMOVAL_FAILED`, `OUTCOME_UNKNOWN`, or exact other evidence state. An issued approval, saved intent, stopped process or Core assertion is **not** a confirmed uninstall.
7. **Observe live:** Both clients update Installed/Available/Blocked/History automatically through AG-D006 authoritative event/snapshot feed. Leaving the GUI, TUI or SSH does not cancel an already approved job or authorize retry of an unknown one.

The owner-approved **block** is a durable Platform-level policy, not a preference chosen by the Core. A Core can *suggest* a block but cannot create, remove, expire or override it by itself. Unblock and subsequent reinstall are new owner-governed operations, not an automatic continuation.

## 2. Concrete request and example screen (illustrative)

Proposed bounded `module.removal.propose` request, **not implemented**:

```text
actor_type:          CORE
actor_identity:      <authenticated stable Core ID>
actor_generation:    <selected current generation>
target_platform_id:  <verified local or enrolled remote Platform ID>
module_id:           <exact signed module ID>
package_digest:      <SHA-256 from current installed package>
lifecycle_revision:  <current authoritative revision>
reason:              <untrusted Core explanation>
evidence_refs:       <allowlisted, separately verified optional observations>
desired_action:      PROPOSE_UNINSTALL_ONLY
request_id:          <idempotent correlation ID>
deadline:            <bounded time>
```

Any field not supplied or unverifiable causes rejection or a non-executable proposal, never fabricated approval. The request has **no** owner approval reference, capability grant or claimed secret.

```text
+-------------------------------------------------------------------+
| AEGIS > SECURITY > MODULE REMOVAL REQUEST                          |
+-------------------------------------------------------------------+
| Requested by:  SOFIA CORE <verified-id/generation>                 |
| Target host:   <verified-platform-id>                              |
| Module:        <verified signed module-id/version/digest>          |
| Current state: <lifecycle> / health: <fresh observation or UNKNOWN>|
| Reason:        <Core claim, explicitly labelled as a suggestion>  |
| Dependencies:  <independent verified list / UNKNOWN>              |
| Core impact:   <lost abilities and recovery impact / UNKNOWN>     |
| Data policy:   KEEP settings and protected module data             |
+-------------------------------------------------------------------+
| [1] Approve removal; future approved reinstall permitted          |
| [2] Approve removal + persistent no-reinstall owner block         |
| [3] Request explanation / postpone                                |
| [4] Deny                                                          |
+-------------------------------------------------------------------+
| APPROVAL: requires real independent owner proof; NO implicit Y    |
+-------------------------------------------------------------------+
```

GUI uses same exact fields, labels, scope and receipt semantics, with owner theme accent colors; line-mode TUI remains usable without colors. For the blocked alternative, commit and verify policy FIRST and then attempt removal. If cleanup fails, UI reports **BLOCKED BUT INSTALLED**, never falsely removed. Default removal leaves package audit bytes retained; physical file deletion is a different reviewed retention workflow.

## 3. Security and autonomy boundaries

### Current rule (no permission rewrite)

- `module.remove` is **PROTECTED**. This document does **not** reclassify it as a reversible standing-grant action. Core proposals are read/propose capabilities and must be explicitly classified in a separate review; they are not a way to execute `module.remove` by proxy.
- The Core's existing AG-D023 self-configuration privileges are limited to owned, safe settings. They **do not** authorize module removal, module installation, permanent install blocks, secret access or changing SAFE permissions.
- The platform operator resolves the owner principal using the existing verifier; a Core/user message, selected Core name, language-model suggestion, generic `Y`, local admin session or sender-provided approval string is not owner authorization. Do not pass the owner's 256-bit secret to a Core, model prompt, GUI logs or untrusted SSH terminal.
- No universal background `auto cleanup` rule, no trust in Core-derived claims of inactivity, and no power to dismiss approval notifications or quietly self-approve.

### Dependencies, critical components and conflicts

- Never let a Core remove a module needed for Platform identity, trusted management, SAFE/STOP, owner authorization, audit, canonical writer fencing, backup/recovery, network control required to obtain approval or its own running communication route. Such foundational components are not ordinary removable modules, even if displayed alongside them.
- Check the full **runtime** dependency graph plus signed package dependencies, not just installation state: capability leases, scheduled jobs, other Cores, connected remote consumers and live placement. A Core's claim that it has not used something is not sufficient evidence of global unused status.
- If the removing Core is a current dependent, display **the exact capabilities the Core will lose** and potential loss of its own live session. Uninstall may proceed only through an independent approved Platform executor with its own communication/recovery route, not by the disappearing Core's own worker.
- If a Core crashes/disconnects between requesting removal and owner review, its suggestion remains an inert, expiring proposal. Do not execute after host/Core generation changed or identity revocation; require refresh and fresh approval.
- An approving owner can direct necessary draining/pause separately, with exact effects and timeouts. Fail closed if active jobs, foreign dependencies or STOP prevent safe removal.
- Removal plans must identify **module state** versus personal Core memory. Ordinary module uninstall cannot purge the Core identity, Constitution, protected memory, security journal, signing keys, or backup state.
- A module marked as blocked for future installs remains blocked even when another Core, repair job, installer or module manager requests it.

## 4. Future option: autonomous disposal of strictly disposable, low-risk modules

**Future idea only, not allowed by today's `module.remove` classification:** An owner may later request a narrowly bounded *separate* capability for self-cleaning **isolated disposable test modules** that the Core created and owns. This must NOT be implemented by simply allowing standing grants for `module.remove`.

Before permitting even that, separately approve:
- A new explicitly classified capability (candidate `module.disposable.cleanup.execute`) for **reviewed disposable LAB-only** instances, never an unrestricted installed production module. Its concrete executor is still Platform-owned, not generic code execution.
- Independent service-side evidence that the target is disposable, not protecting a host/Core, has no other dependents, no leases/jobs, no protected data, and is safe to remove.
- Exact scope of Core identity, Platform/LAB identity, module IDs/package digests, policy TTL, maximum operation count, quota and STOP behavior, with durable owner proof and visible receipts.
- Dry-run plan and revocable grant, with race/ABA replay, identity change, network loss, interrupted operation, remote host denial and retention tests.

Until a separate owner decision, **no Core auto-removes production modules**, even if they are optional or appear unused. Core-initiated requests still go to the Owner Inbox for per-action review.

## 5. Core-facing feedback and future reinstallation

- On accepted verified removal, tell the requesting Core **module removed by owner authorization**, new installed status, what capabilities are now absent, effective availability and whether future reinstallation proposals are eligible. This prevents the Core from blindly planning around the vanished capability.
- If `BLOCKED_BY_OWNER`, any `module.install`, `module.activate`, module repair, dependency resolver, update job, auto-recovery or Core suggestion fails safe at its actual effect boundary. The Core may see a redacted `blocked by owner` reason and must not repeatedly nag or seek alternative aliases.
- If `REINSTALL_ALLOWED`, the Core may **propose** a reviewed, signed install and compatible settings restore plan. The owner must independently approve it. Do not treat previously granted removal authority as future install/activation permission.
- If the owner asks why the Core suggested removal, show the recorded Core explanation separately from independently verified dependency/health evidence. Do not fabricate detailed reasoning not contained in the actual proposal.

## 6. Source-based implementation map and tests

**Reuse:** `platform/modules/lifecycle.py` revisioned guarded `remove()`; `platform/modules/operations.py` owner-auth and receipt pipeline; `platform/modules/observer.py` authoritative health; `platform/modules/settings.py` canonical settings and retained configuration identity; `platform/safe/permissions.py` PROTECTED classification; `platform/safe/approval_inbox.py`, GUI and CLI; `AG_D006_MODULE_UNINSTALL_REINSTALL_POLICY.md` install-block/reinstall semantics and `AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md` live UI refresh.

**Gaps requiring explicit future coding:** typed Core `module.removal.propose` operation, owner proposal inbox presentation, independent source-backed dependency/usage/lease plan, selected-host route with per-operation trust, completion reconciliation and verified cross-client updates. There is no evidence of a production Core-owned automatic removal loop. Do not implement this by allowing the Core to impersonate the owner's principal or by relaxing existing module permissions.

**Acceptance (NOT RUN):**
1. Core proposes optional module removal; both UIs show exact Core/host/module identity, suggested reason versus verified evidence; no code/service mutation before fresh owner approval.
2. Owner accepts ordinary removal: exact protected `module.remove` authorization consumed, safe drain/dependency checks enforced; compatible settings and audit retained; future reinstall remains separately approvable.
3. Owner selects permanently blocked removal: durable deny first, then removal; Core, update, repair, dependency and installer cannot reverse; if removal fails show BLOCKED BUT INSTALLED or OUTCOME_UNKNOWN.
4. Owner denies/ignores request or STOP/revocation occurs: no effect, stale request expires, Core gets denial without owner secret.
5. Other Core depends on module, module is host-critical, active lease exists, requestor is stale, host identity changes, signed digest differs, approved token replays: all fail closed.
6. Requesting Core's own communication module is the target: execution cannot depend on self-disappearing worker, and operation is refused unless independent executor/recovery and separate owner approval are proven.
7. Live GUI/TUI update correct installed/blocked/history/health states without reboot; Core receives accurate capability loss. No phantom auto-reinstall.
8. LAB-only hypothetical self-clean future does not pass through existing PROTECTED `module.remove`; separate reviewed grant and full tests necessary.

**No real uninstall, protected state purge, new grant, permission reclassification, Fleet action or production deployment performed.**
