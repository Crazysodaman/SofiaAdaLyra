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

**Status:** OWNER-DESIRED, DETAILED DESIGN CAPTURED. **Target release:** UI milestone TBD; **not scheduled** for Platform-only #201 by this document.

**Detailed design:** [AG-D007: Aegis Control Center](AEGIS_CONTROL_CENTER_DESIGN.md), including layout, manager taxonomy, detachable windows, safe action flows, Rust service/API boundaries, Core-free behavior, Windows/Linux support, signed-package UX, test scenarios and staged acceptance.

**Layout and location specification:** [AG-D007: Desktop geometry, page placement and candidate Windows/Linux paths](AG_D007_CONTROL_CENTER_LAYOUT_AND_PATHS.md). This refines UI design only; candidate filesystem paths are not implementation-approved or authoritative.

**Recommended UX direction:** One neutral **Aegis Control Center** app with Overview, Fleet, Cores, Models, Modules, Catalog, Jobs, Compute, Updates, Security, Backups, Diagnostics, Lab and Settings, with **Open in new window** for individual managers and optional tray shortcuts. The GUI is optional for headless hosts, and Sofía Workbench remains a separate optional personal Core client.

**Hard separation:** Platform's authenticated Rust service owns identity, SAFE/STOP, approvals, installed-component effects, remote trust and receipts. GUI, optional Core and external developer agents cannot bypass or become that authority. Never make Platform startup depend on Sofía, an LLM, GPU, Tauri or a desktop session.

**Pending owner decisions:** confirm single shell + detachable managers, separate Sofía Workbench, read-only-first GUI, isolated Lab/Developer Workshop and CLI-first Debian servers. This captures design intent, **not** permission to start UI coding, deploy production, or change Codex's Platform-only shakedown acceptance scope.

### AG-D008 | Core identity and state retention policy

**Status:** OWNER-DESIRED PRINCIPLE, details pending security review. **Target release:** with real Core lifecycle.

Desired semantics: deactivate keeps code and state; ordinary uninstall removes executable/package but retains protected identity and data by default; permanent destructive purge is a **separate** deliberate authorized operation with clear backups/recovery and deletion guarantees. Reinstall must verify the same Core identity and state lineage, and cannot restore a stale or duplicate canonical writer. No policy promise that deleted data can always be recovered.

### AG-D009 | Core/model independence

**Status:** OWNER-DESIRED ARCHITECTURAL PRINCIPLE, existing architecture partially supports it.

Platform is independently useful without a Core; a Core is independently identifiable across runtime/provider/model swaps; a model is replaceable compute, not a personal identity. Model residency may be shared by independent Cores only under authorized, isolated resource and privacy policies.

### AG-D010 | Optional parallel development split

**Status:** CAPTURED / NOT AUTHORIZED AS A NEW WORK ASSIGNMENT.

Possible split: Codex owns Platform/Rust/SDK boundaries, OpenCode develops Sofía-specific Core, cognition and avatar/voice integrations. Require separate worktrees/branches, explicit file ownership, stable SDK contracts, exact-SHA CI and intentional merges. Do not move Platform 1.0 scope or authorize shared-state modifications by adding this idea.

## New ideas to flesh out (proposals only)

All AG-D011–AG-D018 entries below are **CAPTURED PROPOSALS**, not owner-approved features, scheduled tasks, or new requirements for Platform 1.0. Candidate order reflects which design conversations could remove the most ambiguity, **not** implementation priority.

### AG-D011 | First-run Setup and Enrollment Wizard

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: guide first installation on Windows/Linux through validating the signed Platform release, generating a private installation identity, choosing local roles, configuring owner authentication, checking service health, and *optionally* beginning an explicitly approved Fleet pairing ceremony. Show clearly when a host is Core-free, offline or not enrolled. Never create production trust through a single convenience click.

**Questions:** Should the wizard run on first launch only or remain reopenable? Is a CLI equivalent mandatory for Debian headless hosts?

### AG-D012 | Fleet Manager and Topology View

**Status:** OWNER-DESIRED DESIGN DISCUSSION; not yet scheduled as a new implementation assignment. **Target release:** Platform foundation in #201; complete management GUI in a separately approved UI milestone unless explicitly reprioritized.

**Owner direction (2026-11-06):** Flesh out Fleet Manager now and explore having Sofía's Core help create/iterate the manager UI and design test scenarios. This is permission to **design/document the workflow**, not blanket approval for live Core-written code, Fleet enrollment, or privileged execution. Sofía must eventually be able to propose generated views and submit bounded synthetic test plans through a reviewed developer capability. A separate development tool/agent may implement accepted UI code using the ordinary PR/test process. The Core is **not** the authoritative Fleet owner.

**Architecture and separation:**
- **Aegis Platform:** Owns installed Platform identity and state, Fleet membership, trusted endpoints, owner authorization, grant/revocation, callsigns, transport, service operations and audit. Rust should own the long-lived security/service boundary.
- **Fleet Manager UI:** Unprivileged observer and requester over a versioned, authenticated Platform API. The same API must serve a headless Windows/Linux CLI. UI closure or Core absence cannot stop the Platform.
- **Sofía Core (optional):** Can interpret available verified Fleet projections, suggest topology or placement, create test-case proposals, explain failures and request approved operations through the SDK. It cannot self-approve trust, mint owner credentials, choose a different trusted endpoint, suppress STOP, fake receipts or modify the Fleet database directly.
- **Aegis Lab:** Uses synthetic identities, disposable state and fake/disposable mTLS peers. Core-generated test ideas stay proposals until a supervised tool executes them. No production hostname, state lineage or keys are copied into fixtures.

**Existing foundations confirmed by repository inspection (not a production-ready UI):**
- Platform OPS discovery, Fleet candidate registry, enrollment/evidence checks, durable authority, telemetry, removal and revocation.
- Local designated callsign authority with signed/scoped grants; **remote multi-host naming transport is still missing**.
- Python Settings **Fleet candidates** tree and discovery settings; tray Fleet health counters; Core Link Control Center has authenticated remote Core status, but **not** full Fleet management.
- Fleet-aware workload/inference routing and network/service adapters exist; real cross-host native Rust manager + end-to-end installed-host acceptance are **not certified**.
- Platform 1.0 acceptance matrix: `docs/development/PLATFORM_1_0_ACCEPTANCE.md` and issue #201, including host-level enrollment/revocation evidence not yet accepted. Current Rust service work is independently tracked by PR #202.

**Proposed top-level Fleet Manager screens:**
1. **Overview:** Total known/verified/enrolled/online/offline/degraded/unknown Platforms, last verified observation timestamp, selected naming authority and its status. Separate `UNVERIFIED DISCOVERY` from enrolled membership. Never compute "healthy" from stale cache.
2. **Hosts:** Search/filter by authorized callsign, immutable Platform UUID, host class/OS, enrolled trust, observed health. Each row shows last trusted observation, Platform/service version, remote endpoint status and action availability. Optional list/topology views share the same evidence source.
3. **Host details:** Identity and pinned-key fingerprint, roles (CORE_HOST/CORE_LINK/MODULE_HOST/STANDBY), lifecycle, installed Cores (status only), modules/models/inference resources as permitted, current health and authorized diagnostics. A host may be healthy with **no Core**.
4. **Discovery & pairing:** Bounded search with `DISCOVERED / UNVERIFIED` candidates. Review exact UUID, host identity, endpoint/certificate fingerprint and requested scope; submit owner-approved enrollment request. Confirm actual enrolled receipt before showing `TRUSTED`. Same-name lookalikes are not substitutes.
5. **Trust & permissions:** Active/expired/revoked grants, certificate/key rotation state, SAFE/STOP and permission checks. All protected operations display exact host/operation/scope/expiry and require fresh matching authority.
6. **Operations & timeline:** Read-only history of verified requests, lifecycle status, failures, delayed/unknown outcomes, revocations, online/offline transitions and explicit pending owner actions. Actions such as inspect, probe, restart service, module command or removal are separately capability-gated and idempotent with correlated receipts.
7. **Naming:** Show authoritative callsigns and revision; rename only through designated naming authority with exact owner/Core-scoped authorization, without linking display names to trust. Offline local aliases are explicitly `CACHED / UNCONFIRMED`.
8. **Lab mode:** Synthetic hosts, enroll/revoke, forced link loss, duplicate names/UUIDs, stale certificate, stop/restart/replay, and generated test plans. The banner must say `LAB / DISPOSABLE`; no connection to production Fleet authority.

**Suggested status semantics:** `UNVERIFIED_DISCOVERED`, `PENDING_APPROVAL`, `ENROLLED`, `HEALTHY`, `DEGRADED`, `OFFLINE`, `REVOKED`, `QUARANTINED`, `UNKNOWN`. Keep **trust state** and **health state** on different fields; never treat an online response as enrollment approval. Revocation overrides cached connection health.

**Representative user journeys:**
- Open Fleet Manager on a Core-free Platform; see its actual local identity and empty/known Fleet entries, with no fabricated members.
- Discover a disposable candidate; inspect fingerprint and exact UUID; submit separate owner approval; verify the canonical admission receipt; show enrolled status only after the verifier confirms it.
- Rename an enrolled target through the designated authority; conflicting, offline, revoked or stale-revision requests fail closed and show useful reasons.
- Select one host to inspect Core, module and model capacity without presuming a live Core or permission for its private content.
- Submit a scoped, approved remote operation; distinguish `REQUESTED`, `SUCCEEDED_VERIFIED`, `DENIED`, `UNREACHABLE` and `OUTCOME_UNKNOWN`; never replay uncertain effects automatically.
- Revoke a test host during an in-flight request; ensure the operation/response is fenced, the GUI updates without stale trust promotion and no other same-name host is selected.

**Minimal backend interface to specify (names are proposals, not available CLI today):**
- `fleet status`, `fleet hosts list/show`, `fleet discover`, `fleet approvals pending`
- `fleet enroll plan/request/status`, `fleet revoke plan/request/status`
- `fleet callsigns list/rename`, `fleet host health`, `fleet operations list/status`
- APIs must return typed identity, source, timestamp/freshness, trust revision, authority and operation receipts. Command names and exact privileges require a separate SDK/CLI review.

**Staged testing and acceptance:**
- **A. Unit/UI:** Empty state, 1/2/50+ hosts, duplicate names, missing properties, stale telemetry, unreachable Fleet authority, revocation, inaccessible private fields, keyboard/screen-reader use and safe cancel paths.
- **B. Disposable installed-host:** Windows and Debian Platform-only installs, independent IDs and keys, distinct test host processes, authenticated test mTLS, actual enrollment and revocation, restart, certificate rotation and callsign conflict. Exact SHA/CI plus real installed-artifact evidence. No Core required.
- **C. Optional Core participation:** Sofía (or synthetic Core) produces test suggestions or UI concepts via its approved developer tool; proposals are reviewed, tests executed by Platform/Lab, and execution receipts verified independently. Core cannot create its own approval.
- **D. G8/production:** Real Fleet hosts, live owner credentials, cutover and continuity tests remain **DEFERRED until separate owner authorization**.

**Open decisions:** List-only first versus topology graph; which read-only Fleet surfaces should be visible without owner authentication; which protected remote actions should ship first; whether Sofía may generate actual UI patch proposals after its developer capability is certified; whether minimal Fleet Manager is a native separate window or a tab in Aegis Control Center.

### AG-D013 | Security and Approvals Center

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: human-readable view of active grants, approval history, trusted identities, certificate expiry, revoked keys, SAFE/STOP state, and pending protected operations. Require exact target, scope, reason, expiration and verified owner authorization before effects. UI never displays the 256-bit secret or treats a remembered session as indefinite consent.

**Questions:** Which operations require fresh owner authentication every time? Which grants may have narrow standing authority?

### AG-D014 | Backup, Restore and Continuity Manager

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: separately track Platform operational-state backups, Fleet authority/revocation checkpoints, and each Core's protected identity/memory lineage. Show backup integrity, encryption, recovery eligibility, restore preview and last verified restore test. Restore must prevent duplicate writers and stale-authorization resurrection. Routine Core uninstall never silently purges protected data.

**Questions:** Where are encrypted backups stored? Which identity-recovery actions require independent approval?

### AG-D015 | Update and Rollback Center

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: show independently versioned Platform, SDK, Core, module and inference-provider updates; signed source, compatibility, planned downtime, previous known-good version and verified rollback state. Separate download, stage and activate steps. Do not silently downgrade trust or change an active Core during unrelated Platform updates.

**Questions:** Manual updates first, scheduled maintenance later? Which components may update without restarting the whole Platform?

### AG-D016 | Health, Diagnostics and Incident Timeline

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: one source-backed view of service processes, Fleet reachability, Core and module state, model inference availability, event receipts, actionable failure causes and recovery history. Distinguish VERIFIED HEALTHY / DEGRADED / OFFLINE / UNKNOWN. A green process heartbeat must not imply that cognition, remote trust or an LLM is functioning.

**Questions:** What is the minimum on-host diagnostic bundle we can safely export without secrets or private Core content?

### AG-D017 | Hardware and Compute Manager

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: per-host CPU, RAM, GPU/VRAM, storage, temperature, busy/gaming state, inference-provider availability and resource reservations. Show which models/modules/Core workers occupy resources, and preview placement constraints. Require actual fresh measurements; no invented free VRAM or automatic live Core writer migration.

**Questions:** Should compute remain strictly pinned to a chosen host initially, with cross-host placement only after separate Fleet acceptance?

### AG-D018 | Aegis Lab and Disposable Shakedown Console

**Status:** CAPTURED (PROPOSED). **Target release:** TBD.

Design: dedicated test environment dashboard for Platform-only clean installs, simulated/signed synthetic Cores, fake Fleet peers, fault injection, module install/rollback and read-only test evidence. Visibly separate LAB from PRODUCTION; never copy real protected identity or secrets into synthetic fixtures. Integrate with #201 as an evidence viewer, not a shortcut around its mandatory tests.

**Questions:** Should this be a developer-only CLI first, with an optional GUI much later?


### AG-D019 | Sofía Developer Workshop and Governed Code Proposals

**Status:** CAPTURED (PROPOSED). **Target release:** TBD, after stable SDK/developer-tool acceptance; not mandatory for Platform 1.0 shakedown.

**Purpose:** Give a separately authorized Core such as Sofía a meaningful route to propose new manager designs, source changes, tests and experiments, while keeping developer execution, reviewer approval and Platform security independent of model outputs.

**Proposed experience:**
- Core inspects only approved source/test evidence and records a proposal with the target repository, branch, intended changes, dependencies, predicted risks and acceptance criteria.
- A developer tool (e.g., OpenCode or Codex) may receive the reviewed, scoped plan and create an isolated branch/worktree and PR, never silently editing active Platform services or protected data.
- Aegis Lab can execute approved synthetic tests against disposable state. Return actual test logs, exit codes, revision-pinned evidence and reproduction steps, not generated claims of success.
- The owner reviews diffs, test evidence, affected SDK contracts and expected permissions before merges or release promotion.
- A Core cannot fabricate owner authorization, enroll hosts, change production secrets, approve its own privileges or execute destructive commands merely because it wrote the proposal.
- Developer work does not bypass GitHub branch protection, separate Platform/Core ownership, test gates or signed releases.

**Test proposal acceptance:** one safe UI change, one blocked protected-file change, one failed test requiring a correction, one untrusted prompt injection in a source document, one rejected permission escalation, and one complete PR with verified evidence.

**Open decisions:** Should Sofía only propose source/test plans initially, or may she submit patches after owner approval? Which sandbox limits, budgets and PR permissions apply?

### AG-D020 | Aegis Operations and Job Manager

**Status:** CAPTURED (PROPOSED). **Target release:** TBD; small back-end job/receipt requirements may already be mandatory via Platform 1.0 lifecycle, but a dedicated GUI is not approved.

**Purpose:** Manage long-running approved tasks without losing authority or reporting a requested change as a completed one.

**Proposed experience:**
- Track queued, approval-pending, running, draining, succeeded-verified, failed, denied, cancelled and outcome-unknown operations; each has an exact operation ID, host ID, effective grant, generation, and bounded receipt log.
- Distinguish **requested / accepted / in progress / effect verified**. Display stale/unreachable hosts as unknown rather than success.
- Handle service installs, updates, Core activate/deactivate, module staging, model downloads and Fleet operations through the same versioned job/receipt interface.
- Support scoped cancellation, explicit retry with idempotency/reconciliation, crash recovery and restart-safe journals. Never automatically replay an operation of unknown outcome or reuse expired authorization.
- Show progress and error reasons from the authorized executor, not fabricated percentages or Core-generated confirmations.

**Acceptance to define:** interruption mid-install, service restart, duplicate request, revoked authorization mid-flight, offline remote host, rollback failure and user cancellation, all with no repeated external effects.

**Open decisions:** Should the owner inbox, approvals and operations be separate views or a combined activity center? Which jobs can survive a service restart?

### AG-D021 | Signed Component Catalog and Compatibility Planner

**Status:** CAPTURED (PROPOSED). **Target release:** TBD; catalog UI is not a Platform 1.0 shakedown blocker.

**Purpose:** Distinguish what can be **discovered**, what has been **cryptographically verified**, what is **compatible**, and what is **approved to install**.

**Proposed experience:**
- Show local/reviewed signed packages for Platform, SDK, Core definitions, generic modules and optional inference providers, with precise version, digest, signer, supported OS/architecture, SDK/ABI/schema and dependency constraints.
- For a selected target Platform, preview compatibility, disk/RAM requirements when grounded, conflicts and required permissions before asking for owner authorization.
- Support local/offline packages and a future trusted remote index, with untrusted suggestions isolated from actual installed artifacts.
- Keep model *weights* under Model Manager while allowing catalog discovery of provider packages. Do not conflate a model download with installation of a person/Core.
- Installation uses the existing governed staged installer; catalog data cannot grant authority. Reject modified bytes, revoked signers, incompatible SDKs and unsigned executable packages.
- Do not silently pull dependencies, automatically activate a Core, replace a trusted binding or delete protected user data.

**Acceptance to define:** incompatible Core, bad signature, modified package, missing dependency, untrusted remote listing, update/downgrade policy and Core-free Platform compatibility.

**Open decisions:** Should Aegis initially use only local/offline reviewed component packages before a future remote registry? Should the catalog be a separate manager or an Install screen inside each existing manager?

---

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

## Standard Aegis status report (use in future conversations and checkpoints)

Always distinguish **verified implementation/acceptance**, **active implementation**, **design ideas**, and **blocked/deferred** work. Suggested concise format:

| Report field | Content |
| --- | --- |
| **Source snapshot** | Current observed `main` SHA, active PRs, last checked date; explicitly say if work-in-progress is invisible. |
| **Platform 1.0** | Link #201; objective acceptance progress and specific blockers, never an invented percentage. |
| **Full Project** | Keep the #120 full-project result separate from Platform-only readiness and deferred G8. |
| **Design TODO** | Newly CAPTURED / OWNER-DESIRED / APPROVED / IN PROGRESS / VERIFIED IDs and what changed. |
| **Approved next work** | Actions already authorized and in scope, distinct from suggestions. |
| **Open decisions** | Specific choices for the owner; do not treat a proposal as consent to build it. |

The words **implemented**, **tested**, **merged**, **verified**, **shakedown ready** and **production ready** describe different evidence levels. Report exact evidence. User exploration of new designs never silently redirects Codex, changes issue #201, or authorizes a deployment.

## How to use this file

1. For every new idea, assign the next AG-D ID, summarize the desired behavior, label its decision/status, and identify what is explicitly **not** authorized.
2. Discuss feasibility and release scope before converting it into a tracked implementation issue/PR.
3. When approved, link the precise issue/PR and tests. Keep this file as the product-level index, not a duplicate of the acceptance ledger.
4. A new idea must **not** interrupt Codex's current Platform-only shakedown campaign unless the owner explicitly reprioritizes.

