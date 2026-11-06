# Aegis | Design TODO and Idea Inbox

> Living owner-design backlog. Capture ideas here without automatically adding work to an active release.
> Last initial review: 2026-11-06. This file records design intent, not implementation or acceptance evidence.

## Operating rules

- **Current implementation priority:** Aegis Platform 1.0, Core-free shakedown. Authoritative acceptance: [#201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201), parent [#120](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120).
- **No scope creep:** An entry here does **not** amend #201, instruct Codex/OpenCode to implement it, or grant deployment, security, state, or Fleet authority.
- **Capture first, schedule second:** New ideas enter **CAPTURED**. Record a user decision, release target, acceptance criteria and dependencies before promoting them to **APPROVED / SCHEDULED**.
- **Evidence separately:** Only link an item as **VERIFIED** after actual source, CI, installed-artifact and host evidence appropriate to that requirement. Do not equate an existing prototype with a finished cross-platform feature.
- **No real-host activation:** Production, owner-private protected state, real Fleet enrollment and G8 shakedown remain separately gated.
- **Roles:** Codex is currently focused on Rust-led Platform 1.0. A possible OpenCode Sofía-Core workstream is a coordination proposal, not an automatic assignment.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| CAPTURED | Discussed or requested, but not scheduled or approved as release scope. |
| OWNER-DESIRED | User explicitly expressed a UX/product preference; scope and acceptance are still pending. |
| APPROVED / SCHEDULED | User has approved the release scope and implementation priority. |
| IN PROGRESS | Work observable in a linked issue or PR. |
| VERIFIED | Accepted against evidence in the authoritative tracker. |
| DEFERRED | Explicitly excluded from the current milestone. |

## Current release fence: Platform-only shakedown

| ID | Item | Status | Release relationship / tracking |
| --- | --- | --- | --- |
| AG-D001 | Aegis Platform installs and operates with **no Core**, on Windows and Debian, using independent identity, Rust-owned service lifecycle, approved local modules, safe enrollment/recovery and diagnostics. | IN PROGRESS | Platform 1.0 #201; do not replace its 30-row acceptance matrix. |
| AG-D002 | Demonstrate signed **synthetic Core** installation/activation/deactivation/detachment without a real Sofía identity or second writer. | IN PROGRESS (acceptance pending) | Already part of the Platform-only acceptance target in #201; no production Core activation. |

## Owner-desired product experiences (not scheduled by this document)

### AG-D003 | Cross-platform Aegis Core CLI

**Status:** OWNER-DESIRED. **Target release:** decide after reviewing #201 dependencies.

Intended commands (interface proposal, **not currently certified working commands**):

    # Windows
    aegis core install .\Sofia.corepkg
    # Windows or Linux
    aegis core activate sofia
    aegis core status
    aegis core deactivate sofia
    aegis core uninstall sofia
    # Linux package path
    aegis core install ./Sofia.corepkg

Acceptance to define: one semantics-compatible CLI on Windows/Linux; signed bytes and exact Core identity/revision checks; distinct install vs. activation; fresh owner approval for privileged changes; current revocation/STOP enforcement; crash recovery; no automatic Core start from install; Platform remains healthy after deactivation/uninstall. Decide desired `list`, `update`, and per-Core `status` options separately.

### AG-D004 | Dedicated Aegis Core Manager GUI

**Status:** OWNER-DESIRED. **Target release:** TBD; not a hidden Platform-only shakedown blocker.

Design: native cross-platform management window, optionally reachable from tray, showing installed/available Cores, stable IDs, verified package versions, bindings, lifecycle status and actionable diagnostics. Offer install, activate, deactivate, update and uninstall through the **same governed service API** as the CLI. No GUI-only security bypass; no display-name-only authorization. Candidate technology: Rust backend + Tauri desktop shell, pending implementation review.

### AG-D005 | Aegis Model Manager

**Status:** CAPTURED. **Target release:** TBD; do not block the independent Platform service.

Design: Platform/provider-owned model inventory per inference host, local and approved remote Ollama endpoints, model identity/digest/license/size/status, owner-approved download/update/removal, load/unload/keep-alive, resource/VRAM/CPU/RAM budgets and capability/benchmark evidence. Explicit **per-Core model role assignments** (primary/secondary/etc.) must never redefine or replace a Core's identity, memory or permissions. Never silently download, switch providers, migrate a model or claim remote host trust.

Existing partial foundations to reuse: Python Settings Models tab, Ollama inventory/adapter, ModelLifecycleManager, Platform model/compute orchestration. These are **not** a standalone Rust-native Model Manager and do not certify live Fleet inference.

### AG-D006 | Aegis Module Manager

**Status:** CAPTURED. **Target release:** TBD.

Design: browse signed installed/available modules, versions and compatibility; install/enable/pause/update/remove with exact scoped approvals, health and recovery receipts. Reuse existing Platform module contracts and service authority. Keep a GUI optional when a headless CLI suffices for Platform 1.0.

### AG-D007 | Aegis Control Center navigation

**Status:** CAPTURED. **Target release:** TBD.

Design question: one Aegis app with **Platform / Cores / Models / Modules / Fleet / Security / Diagnostics** views, or separate launchable managers sharing the same service API? Support Windows and Linux; servers remain headless and manageable by CLI/API. Keep high-risk actions visibly distinct from read-only status.

### AG-D008 | Core identity and state retention policy

**Status:** OWNER-DESIRED PRINCIPLE, details pending security review. **Target release:** with real Core lifecycle.

Desired semantics: deactivate keeps code and state; ordinary uninstall removes executable/package but retains protected identity and data by default; permanent destructive purge is a **separate** deliberate authorized operation with clear backups/recovery and deletion guarantees. Reinstall must verify the same Core identity and state lineage, and cannot restore a stale or duplicate canonical writer. No policy promise that deleted data can always be recovered.

### AG-D009 | Core/model independence

**Status:** OWNER-DESIRED ARCHITECTURAL PRINCIPLE, existing architecture partially supports it.

Platform is independently useful without a Core; a Core is independently identifiable across runtime/provider/model swaps; a model is replaceable compute, not a personal identity. Model residency may be shared by independent Cores only under authorized, isolated resource and privacy policies.

### AG-D010 | Optional parallel development split

**Status:** CAPTURED / NOT AUTHORIZED AS A NEW WORK ASSIGNMENT.

Possible split: Codex owns Platform/Rust/SDK boundaries, OpenCode develops Sofía-specific Core, cognition and avatar/voice integrations. Require separate worktrees/branches, explicit file ownership, stable SDK contracts, exact-SHA CI and intentional merges. Do not move Platform 1.0 scope or authorize shared-state modifications by adding this idea.

## Questions to decide before promoting UX concepts

- Should Core Manager, Model Manager and Module Manager be three windows, or tabs inside one Aegis Control Center?
- Does Platform 1.0 need any GUI beyond an authenticated headless CLI and minimal status/tray?
- Which model providers are in the first supported Model Manager release (Ollama-only vs adapter-based multiple providers)?
- What are the exact approval and retention ceremonies for Core uninstall, data purge, remote model install and role reassignment?
- Which additional CLI operations beyond the five owner-preferred Core commands are actually needed?

## Known integration caution

- The existing legacy Python model download settings path still has FIDO2-specific UI calls. Owner preference is that FIDO2 remains disabled/optional and protected actions use independently verified, scoped 256-bit-secret authorization. Reconcile with the authoritative auth policy **before** shipping new management UI. Never expose the secret in logs, URLs, model prompts or CLI arguments.
- Existing Python/Ollama code is a foundation, not proof that a fully generic Core-free model-service implementation or Rust manager is complete.
- Track Platform-only readiness in #201 and full-project readiness in #120. Keep G8 #129 deferred until separately authorized.

## How to use this file

1. For every new idea, assign the next AG-D ID, summarize the desired behavior, label its decision/status, and identify what is explicitly **not** authorized.
2. Discuss feasibility and release scope before converting it into a tracked implementation issue/PR.
3. When approved, link the precise issue/PR and tests. Keep this file as the product-level index, not a duplicate of the acceptance ledger.
4. A new idea must **not** interrupt Codex's current Platform-only shakedown campaign unless the owner explicitly reprioritizes.

