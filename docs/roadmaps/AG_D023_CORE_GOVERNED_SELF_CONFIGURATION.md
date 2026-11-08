# AG-D023 | Governed Core self-configuration and owner controls

**Status:** OWNER-DESIRED DESIGN (2026-11-07); CAPTURED, NOT IMPLEMENTED or SCHEDULED.
**Owner intent:** A Core, such as Sofía, should be able to adjust its own settings when safe and permitted, while the owner can inspect and control those decisions from ASCII CLI/TUI, GUI and approved APIs.
**Depends on:** AG-D022 terminal UI, AG-D007 shared GUI, AG-D013 Security & Approvals, existing canonical settings authority, SAFE permission grants, #201 independent Platform service management and existing SDK/Core Link contracts.
**Release fence:** This proposal does not authorize automatic production setting changes, new grants, software release updates, owner secret access, Core movement or G8; it does not change the Platform-only shakedown definition.

## 1. Governing principle

**Settings ownership is not permission.** Existing `SettingsOwner.CORE` class means the stored value belongs to the Core settings domain and may be exposed to appropriately scoped clients. It does **not** give an autonomous Core a blanket ability to rewrite configuration. A Core must never issue or approve its own privileges.

The owner can grant a **bounded per-Core self-configuration policy** naming allowed fields, allowable values/ranges, duration, required reason/evidence, frequency and resource limits, and permitted application classes. A security/service authority outside the model independently verifies each request against active identity, grant, current field revision, current STOP state, expiry, scope and host/Core generation.

A Core is not defined by its selected model: changing allowed inference preferences may be considered, but cannot change Constitution, identity, protected memory lineage, owner authority or trust.

## 2. Configurable autonomy profiles

The *default before owner enrollment/approval* is **Observe/Propose**, with no persistent autonomous write permissions. After an attended, independently verified owner decision, an owner may choose:

| Profile | Behavior | Security consequence |
| --- | --- | --- |
| **Observe** | Core reads its authorized, redacted settings and explains possible changes. | No self-writes. |
| **Suggest** | Core proposes a structured before/after change and reason; owner explicitly approves each. | No self-writes before approval. |
| **Adaptive** | Core may apply a small explicit allowlist of low-risk reversible settings within owner-set bounds. Owner sees receipts. | A bounded, expiring grant; no permission expansion. |
| **Delegated** | Core may adjust a named, wider but still reversible list under per-field values/budgets, expiry and rollback controls. | Standing grant requires exact owner authorization; never implicit. |
| **Locked** | Owner locks selected fields or all self-configuration. | Owner protections always win; cannot be undone by the Core. |

**No single global 'everything auto' switch**; every authorized profile is resolved per Core identity and field/policy revision. Core name/nickname and LLM output are not authentication. The owner may set policy for different Cores independently, with separate host and shared resource limits.

## 3. Suggested authorization classes

| Class | Illustrative settings | Decision |
| --- | --- | --- |
| A: Reversible Core-private | Bounded temporary response length/verbosity, optional internal scheduling intervals within allowed ranges, presentation preferences that do not alter owner privacy policy. Exact existing fields need mapping; names are design candidates. | Autonomous only when allowlisted with limits. |
| B: Scoped or restart-bound | Approved reasoning/model-role preferences, per-Core inference sampling/keepalive and budget choices within resource constraints; Core-owned feature toggles where policy permits. | Expiring owner delegation, possibly component restart approval; no instant applied claim. |
| C: Consequential/host-owned | New model download, provider endpoint/host change, increased RAM/VRAM/CPU budget, service or module install/restart, outbound notifications, network/Fleet changes. | Require fresh scoped owner approval and/or separately approved narrow host delegation; no implied permission from Core ownership. |
| D: Never self-authorized | SAFE/STOP override, permissions/grants, secret/key rotation, enrollment/trust, identity or Constitution amendment, memory purge, private-state relocation, canonical writer selection, remote host migration, production release signing, active trust policy changes. | Owner/Platform governed ceremony, or categorically forbidden to Core; no Core self-authorizing path. |

Actual field classification requires a reviewed allowlist built from `runtime_settings_contracts()`, the canonical permission policy and each signed module's settings contract. Existing field names and apply classes must be checked individually, **not** assigned based on broad categories alone. For instance, the existing `provider_temperature` is classified CORE-owned but COMPONENT_RESTART; that fact alone does not make it safe for automatic changes.

Client-only UI settings live with the client and are not writable through Core canonical settings. Platform-owned host and trust settings must never be changed by a Core pretending to own HOST scope.

## 4. Owner-facing ASCII management screen

```text
+--------------------------------------------------------------------+
| AEGIS > CORE MANAGER > SOFIA > SELF-MANAGEMENT                      |
+--------------------------------------------------------------------+
| Core identity: <verified ID>      Current generation: <actual>    |
| Policy mode: ADAPTIVE            State: ENABLED / PAUSED          |
| Policy revision: <n>             Grant expiry: <timestamp>       |
+--------------------------------------------------------------------+
| [1] Allowed settings and ranges                                  |
| [2] Current values / effective values                            |
| [3] Change proposals awaiting approval                           |
| [4] Recent changes and reasons                                   |
| [5] Pending apply or restart requirements                        |
| [6] Edit policy (fresh owner approval)                            |
| [7] Pause self-adjustments (effective revocation)                 |
| [8] Revert an eligible change (reviewed operation)                |
| [0] Back                                                          |
+--------------------------------------------------------------------+
```

Sample event presentation (all data illustrative):

```text
+--------------------------------------------------------------------+
| SELF-CONFIGURATION EVENT                                           |
+--------------------------------------------------------------------+
| Requested by: <signed Core identity>                               |
| Setting:      <explicit allowlisted field ID>                      |
| Was:          <old value>                                           |
| Proposed:     <new value within owner-set bounds>                  |
| Reason:       <Core-provided explanation, labeled PROPOSAL>        |
| Evidence:     <independently referenced observation / none>        |
| Grant:        <current grant ID, approved scope, expiry>            |
| Revision:     <expected current settings revision>                 |
| Apply class:  LIVE / NEXT_OPERATION / COMPONENT_RESTART            |
| Result:       APPLIED / PENDING / DENIED / FAILED / UNKNOWN        |
+--------------------------------------------------------------------+
```

The Core's *reason* may be its own interpretation; this is not independent verification. The actual changed state and effective application must come from authoritative receipts.

## Terminal presentation palette

Both the graphical and ASCII Core self-configuration menus, approval/change-history screens and policy controls use the same default [shared Aegis GUI/TUI visual theme](AEGIS_SHARED_GUI_TUI_THEME.md), with additional [terminal-specific rendering and monochrome rules](AEGIS_CLI_TUI_COLOR_THEME.md). Status remains textual and evidence-backed in monochrome. Purple headers, cyan current-selection indicators, lime verified success, amber pending/review and dark red danger accents must never override the actual grant/STOP or authoritative change receipt. Use readable light main text for all critical content; do not use low-contrast colored text alone for errors or approval boundaries.

## 5. Proposed Core -> service workflow

1. Core obtains only its authenticated scope-limited snapshot, allowed fields and policy bounds.
2. Core submits a typed `settings.self_adjust.propose` request (PROPOSED API), with stable Core ID, current generation, exact fields, proposed values, expected revision, scoped purpose/evidence references, idempotency key and requested apply class. Never supply owner authentication material.
3. The Platform/Core Host authority independently validates exact identity, grant/policy, protected precedence, actor capabilities, current revocation/STOP, fresh settings revision, safe value constraints, rate/resource budget, permitted apply boundary and signed module compatibility.
4. If the request is safely allowlisted with a valid active owner grant, the authoritative service writes the original settings store through existing compare-and-swap code and returns a unique receipt. Otherwise, create a bounded owner approval proposal. **A proposed edit is not a saved or applied edit**.
5. Apply LIVE values only through a registered actual handler. For NEXT_OPERATION, COMPONENT_RESTART and PLATFORM_RESTART, show a pending receipt and require separate governed orchestration. Self-adjust permission never implies a service restart or install permission.
6. Recheck authority before effect execution and, for remote/personal exposures, before returning protected results. If uncertain (lost connection, crash, timeout, conflicting revision), return OUTCOME_UNKNOWN and reconcile. Never blind-retry a possibly completed write.
7. Publish an append-only redacted record showing old/new values where nonsecret, actor/identity, policy and settings revision, approved grant, effective revision, reason and observed apply result. Notify the owner according to separately approved notification limits, without flooding the channel.
8. Allow a verified owner to pause/revoke self-changes immediately and review/revert eligible reversible values. Revert is itself a new revisioned authorized write, never a silent SQLite rollback or a second writer.

## 6. Safety and drift controls

- Explicit **per-field** min/max/allowed-values, maximum change frequency, durable daily change budget, TTL and optional hysteresis/cooldown to prevent constant thrashing.
- No grant may widen itself or its parent's scope; no Core may issue/refresh/rotate owner grants or secrets.
- A change cannot disable logging, telemetry needed for policy checks, owner notifications, safeguards, STOP, audit retention, backups or required recovery.
- If the model/provider becomes unavailable, settings authority and TUI remain operational Core-free. Do not treat cached status as proof of a new change.
- After restart, reconstruct policy from owner-authenticated durable records; fail closed on missing/corrupt grant or unknown policy schema. No dormant grants resurrect after revocation, re-enrollment or host/Core generation change.
- No unrestricted filesystem/config editing; no direct SQLite access for a separately hosted Core and no public unauthenticated settings endpoint.
- Inference cost/performance decisions must respect actual observed CPU/RAM/VRAM and approved budgets; do not invent resource headroom or background downloads.
- Optional `auto_revert_on_failure` may apply only when the original prechange value and preconditions are verified and doing so is authorized. If the result is uncertain, preserve evidence and ask instead of pretending to roll back.
- Never allow dynamic prompts, source docs, plugin outputs, dev agents or the Core's own proposals to modify authorization policies.

## Module uninstall initiated by the Core

Self-management of Core-owned **settings** is distinct from uninstalling a **Platform-owned module**. See [AG-D006 Core-Initiated Module Removal](AG_D006_CORE_INITIATED_MODULE_REMOVAL.md). The Core may make an inert, reasoned module removal proposal, identify signed module/host and independently verified dependencies, and request owner review. Current `module.remove` is **PROTECTED** in SAFE, so neither Adaptive nor Delegated self-settings grant authorizes the uninstall; an actual effect requires independent exact owner approval. The Core cannot choose the owner's permanent no-reinstall policy, purge retained module/private data, remove security/management dependencies, or self-authorize broader powers. A future, separately reviewed LAB-only disposable cleanup capability is not shipped or authorized. GUI and TUI display proposal, approval and actual lifecycle receipts consistently without restart.

## 7. Reuse and implementation implications### Optional container/Portainer module is a service, not a Core self-setting

[AG-D025](AG_D025_PORTAINER_DOCKER_STACK_CONTROL.md) places Portainer as a **provider adapter in optional `MOD-IT-CONTAINERS` Platform module**. The Core can inspect authorized, sanitized observations and propose Compose patches but cannot obtain the Portainer token or execute production stack updates under its own AG-D023 self-settings grant. Platform SAFE authorizes separately scoped write jobs; the module executes exact approved effects. The Portainer module continues to operate through GUI/TUI while no Core is present, and removing it never deletes the external Portainer stack or Core identity.



Existing code foundations to reuse:
- `src/sofia/platform/config/settings_authority.py`: `CanonicalSettingsService`, `SettingsOwner` classes, `SettingsApplyClass` and `SettingsApplyState`, CAS revisions, idempotency keys and revisioned event records. This is a single canonical Core-settings domain, not a license to open Core state from Platform-only hosts.
- `src/sofia/platform/core_link/conversation.py`: scoped `settings.snapshot`, `settings.update` and `settings.events` operations. Existing permission mapping includes `settings.read.core` and `settings.write.core` as authenticated client scopes; a Core actor should use a **separate constrained self-adjust capability**, not inherit an owner's broad writable scope.
- `src/sofia/platform/modules/settings.py`: settings contracts bound to signed module revisions; module settings changes are independently governed by module lifecycle and owner approval.
- `src/sofia/platform/config/authority.py`: precedence includes protected policy above host and process override, which should stay authoritative.
- `src/sofia/platform/safe/permissions.py`: classified permission levels, expiring standing grants, revocation and owner approval. Any new self-adjust scope must be explicitly reviewed/classified; not treated as a broadly available new capability.
- `src/sofia/platform/safe/owner_secret.py`: opt-in, attended 256-bit secret owner proof; current implementation is tied to a signed-in Venus Windows owner ceremony, so privileged remote Debian/SSH actions **require additional reviewed secure authorization integration**, not bypass.
- `src/sofia/modules/ui/core_link_settings.py`: existing GUI uses the authoritative snapshot/update/events, with no direct canonical DB access. AG-D022 and GUI should show the same governance.

Do not build a second Core settings store, let an LLM self-select `writable_owners`, treat `SettingsOwner.CORE` as a privilege grant, or move canonical writer authority to the CLI/GUI/model. Existing `settings.update` client flow is a foundation for approved writes, not proof Core-autonomous self-change admission is implemented.

## 8. CLI / UX contract (proposed, unimplemented)

```text
aegis core settings <core-id>
aegis core settings history <core-id>
aegis core settings proposals <core-id>
aegis core autonomy <core-id>
aegis core autonomy policy <core-id>
aegis core autonomy pause <core-id>       # needs appropriate independent owner authority
aegis core autonomy resume <core-id>      # needs exact owner approval
aegis core autonomy review <core-id>      # read-only recent changes
```

Interactive policy editor shows explicit per-field allowed ranges, actor, scope, expiry, apply class, generated preview and a non-secret one-use authorization ceremony. Make approval and apply state clear; neither a local `Y` nor `--yes` counts as independent owner proof.

Potential default suggested starter grant after the user opts in: only narrowly specified reversible, Core-private settings that can be applied LIVE or NEXT_OPERATION with verified handlers and an explicit rate limit. Unknown or unclassified fields default to PROPOSE; all protected changes require separate owner action or remain prohibited.

## 9. Acceptance tests / milestones

- **SELF-0** owner approves taxonomy and exact allowlist/policy schema; defaults are no autonomous writes.
- **SELF-1** Core can read and propose a bounded change with no standing grant; no writes occur; owner sees exact diff in CLI/TUI and GUI.
- **SELF-2** Owner issues expiring per-Core, per-field bounded grant; one allowed live update succeeds, verified old/new value and effective apply; one out-of-range, changed-contract or unknown-field request is DENIED.
- **SELF-3** Expiry, revocation, owner STOP, wrong Core ID, wrong host/generation, request replay, conflict, old revision, excessive rate, budget exhaustion and interrupted/corrupt state fail closed and never create a second writer.
- **SELF-4** Next-operation/restart-needed changes remain PENDING until separately authorized effect; no invented APPLIED status. Revert and notification obey existing owner/security and resource budgets.
- **SELF-5** Windows, Debian and Core-free/remote-link observations show equivalent policy and receipt; UI/CLI/core proposal remain different clients to the same state owner. Real-host change requires its own release and owner approval.

No production use or Core self-edit autonomy is authorized by saving this design document.
