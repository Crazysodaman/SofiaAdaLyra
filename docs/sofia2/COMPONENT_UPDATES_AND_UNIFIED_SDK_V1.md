# Sofía 2.0 — Component-isolated updates and unified SDK V1

**Owner decision:** Approved architecture/implementation target, 2026-10-24 (America/Chicago).
**Status:** Design/acceptance specification, **not** evidence of a working isolated Core, independently hot-updatable modules, live Platform restart, deployed SDK, real release or host acceptance.
**Owners:** PLAT-01 supervisor, PLAT-02 state, PLAT-03 SAFE/identity, PLAT-04 RUN/ACT, PLAT-05 module manager and SDK contracts, PLAT-08 release/certification, Core's provider-neutral cognition contract, existing DEV/EVOLVE workshop and optional developer tools.
**Related contracts:** ARCHITECTURE.md; PLATFORM_AND_MODULE_CATALOG_V1.md; HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md; CORE_1_0_PLAN.md. This contract does not approve canonical-state migration, new installation privileges or live production updates.

## 1. Owner requirement and honest boundary

**Desired operating rule:** A new Platform executable/shared host release is generally the only ordinary update that requires restarting the Platform process. Updating the isolated Core service or one independently hosted module **must not** restart the Platform, unrelated module processes, Fleet workers or the canonical host supervisor.

This is a **process/lifecycle contract**, not a claim that merely renaming packages makes updates hot-swappable. The current repository uses a shared in-process \`SofiaApplication\` composition and imports many \`sofia.core.*\` implementations from Platform and application code. The existing \`ComponentRuntimeSupervisor\` supports distinct Core, Platform and optional-module component kinds, but it **does not** by itself establish an independently process-hosted production Core, a release-grade SDK ABI or an atomic running-module update. The existing signed module \`ModuleLifecycleManager.update()\` requires an inactive package and only switches its staged pointer; activation is separate. Do not mark this requirement complete from existing interfaces alone.

**Scope caveats:**
- A Platform process may still need a coordinated restart for a security/runtime/ABI update, shared in-process dependency changes, host supervisor replacement or protected schema upgrade. Pure data/config/profile changes may be applied live only if their specific owner implements a verified, atomic reload.
- A Core update normally restarts **Core only**, giving a brief temporary generative-cognition interruption; Platform and unrelated modules continue. A module update normally restarts **that module only**. A provider module update does not mandate Core restart when the provider protocol remains compatible.
- If an update changes Platform-owned contracts, requires a non-backwards-compatible shared library or canonical-state migration, **do not pretend a single-component restart suffices**. Detect impact through a reviewed dependency/ABI graph and require the smallest safe approved maintenance scope, possibly a Platform restart.
- A component release does not imply instant replacement of loaded Python code in an existing interpreter. No unreviewed \`importlib.reload\`, executable code patching, direct DLL replacement under active process, or global \`sys.modules\` tricks. Use isolated process/container workers or a specifically reviewed safe reload interface for data-only state.
- Core's cognitive identity and memory remain conceptually Core-owned, but Platform's single-writer state API enforces persistent transactional ownership and principal/audience boundaries. Component isolation cannot give Core or plugins unmanaged direct writable \`sofia.db\` access.
- A stable Platform does not mean permanent 100% conversation availability. An updating Core is temporarily unavailable, and a Platform maintenance restart can interrupt multiple interfaces. Report these conditions truthfully.

## 2. Target process and control-plane layout

\`\`\`text
    OS service/watchdog (minimal independent restart monitor)
                     |
    PLATFORM PROCESS (canonical long-running host)
    - state ownership + one writer fence
    - trusted sessions / SAFE / STOP / permission
    - RUN/ACT work and effect reconciliation
    - signed release/admission + compatibility
    - process/component supervision
    - Fleet transport and resource reservations
    - versioned SDK protocol endpoint
                     |
    +----------------+-------------------+-------------------+
    |                |                   |                   |
CORE WORKER      MODULE WORKER A      MODULE WORKER B      INFERENCE WORKER
isolated          isolated             isolated             local or Fleet
version/generation/version/generation  version/generation   version/model digest
\`\`\`

A module or Core process may be hosted on the same VM or an explicitly approved different machine; this never transfers canonical-writer authority. Platform's worker/client API must be authenticated and versioned, with timeout/bounds, cancellation semantics, tracing, backpressure, audit and per-scope grants.

**Important:** A Core worker is not a second Platform service; Platform owns the sole durable request dispatch, state facade and active-Core generation. The OS watchdog is a minimal service manager, not a second database authority or independent scheduler.

Implement as a **staged migration**. First introduce isolation-safe APIs and tests around the existing composition, then move the smallest coherent Core worker entry point and representative modules to independent processes. Keep old mode working until real end-to-end isolation acceptance passes; do not claim separation when all core calls remain in the Platform interpreter.

## 3. Update-impact matrix and dependency policy

| Change | Normal action | Conditions or exception |
| --- | --- | --- |
| Platform process, security/ABI or shared host code | staged coordinated Platform restart and reconciliation | allow nonrestart change only for explicitly supported atomic data/config reload |
| Core worker code, Core-only dependencies or provider-neutral cognition implementation | drain/fence old active Core generation, activate verified replacement Core worker | Platform stays up; incompatibility or Platform-owned schema changes require broadened reviewed scope |
| Independent module package or module-only dependencies | drain/fence that exact module instance, stage/update/start/verify | Platform, Core and unrelated modules stay up; dependents may be paused/drained based on dependency graph |
| Inference provider adapter | restart/replace that adapter worker only | model identity/digest, mTLS and routing remain pinned; unavailable inference is honest outage |
| Model weights/role selection | reviewed model lifecycle load/unload/config | no Platform restart when protocol supports it; no silent substitution or unauthorized pull |
| SDK developer CLI/docs/templates | update developer tooling; no runtime restart | runtime consumer restarts only if its deployed API client or loaded binary changes |
| SDK API protocol/serialization schema | additive backward-compatible negotiated version first | breaking changes require compatibility window, explicit dependent-component plan; Platform restart if host endpoint code changes |
| Platform-owned canonical state schema | separately authorized, backed up migration with compatibility and rollback checks | never treat as Core/module-only update |

**Dependency-aware minimization:** Build a reverse dependency graph of component version/digest, SDK protocol/ABI version, signed module contracts, state schema and loaded third-party runtime libraries. A Core-only change must not force unrelated modules to restart merely because they are imported indirectly in legacy composition; that coupling must be fixed to meet the target. A changed shared platform library legitimately invalidates affected process generations. Negative/UNKNOWN compatibility blocks automatic activation.

## 4. Durable component update protocol

Use the existing signed release store, module lifecycle, RUN work manager, component supervisor and SAFE owner as the building blocks. Do not create a second update scheduler.

1. **Plan:** compute proposed exact source and target component ID/version/digest, signed package, expected generation/revision, compatible Platform/SDK API ranges, dependency impact, target host, resource budgets, approved permission scope, expected interruption and rollback limitations.
2. **Authorize:** exact authenticated operator/principal and audience, approved release signature and manifest, one-use effect approval when required, current STOP status, trusted target; model reasoning may request/propose but never authorize deployment.
3. **Stage:** immutable content-addressed package slot, validate full artifact set/signature, verify software bill of materials and dependency compatibility, prepare config/state changes without mutating active slot. No executable candidate imports during validation.
4. **Preflight:** run tests and inert readiness on isolated candidate; check Platform/SDK endpoint negotiations, state compatibility, device locks, active work leases, health probes, resource budgets and rollback artifact availability. Standby Core may be *read-only*, never a second acting or writing Core.
5. **Drain:** quiesce affected component's new admissions, let bounded in-flight work finish or cancel, preserve durable conversation/work receipts, mark uncertain external effects UNKNOWN without retry. Unaffected services continue.
6. **Fence:** invalidate old component generation, withdraw its capability registrations and tokens, revoke relevant leases, ensure no zombie process or stale IPC request may mutate state or external targets. Source process may exit after acknowledgment or enforced safe termination. Exactly one ACTIVE Core generation at a time.
7. **Activate:** start target release in an independent process/worker with least-privilege scoped credentials; negotiate interface version and register capabilities only after external readiness evidence. Platform proxies to the new generation.
8. **Verify:** independently test health, authenticated request/response, correct durable state continuity, model/provenance or device-specific effects, no stale registrations/duplicate jobs; record exact version and receipt.
9. **Commit:** atomically mark new active release generation, preserve signed previous artifact/rollback window, release temporary resources and publish status to the UI and Core awareness channel.
10. **Failure:** pre-effect failure safely restores old generation only when compatible, approved and verified; ambiguous external outcomes quarantine/drain pending review, do not blind replay. A failed Core update must not crash Platform. A failed module must not take down other modules.
11. **Restart recovery:** reconstruct exact active/staged/pending generation and effects from canonical state; reconcile process and adapter observations; no duplicate active Core, stale permissions, automatic re-execution or hidden status reset. Preserve audit provenance.

**Important:** No two active independent Core writers; generation fencing must be enforced by Platform state/IPC authority, not just a Python variable. No running worker is allowed direct unrestricted database handles that survive generation revocation. Handle long-running streams, speech, rendering and physical control separately with explicit interruption rules; do not promise seamless handoff where it cannot be proven.

## 5. Single SDK for Platform, Core and Modules

**Decision: ONE Sofía SDK family, not a privileged mandatory "SDK module".**

The SDK is a versioned **developer distribution and runtime protocol**, maintained with Platform's interface contract, with *separate consumer facades* for Platform extension development, Core development and Module development:

| SDK layer | Purpose | Runtime authorization |
| --- | --- | --- |
| \`sofia-sdk-contracts\` | portable, minimal typed schemas, generated clients, errors, version negotiation, capability and resource profile types, serialization, protocol fixtures | **none**; pure code cannot mint host permissions |
| \`sofia-sdk-platform\` | host service extension hooks, state transaction interfaces, release/placement/tracing/probe contracts | privileged functions only from explicit trusted Platform-controlled construction; never issued to untrusted plugins |
| \`sofia-sdk-core\` | provider-neutral cognition worker IPC, context/memory facade, state and outcome receipts, Core capability proposals, immutable identity projection types | only approved Core principal/scope; no direct Platform state writer |
| \`sofia-sdk-module\` | module manifest/profile, capability request/response, health, maintenance, resource needs, optional device interface and safe cancellation | all calls through authenticated Platform broker and SAFE/RUN; no direct effects from manifest |
| \`sofia-sdk-devtools\` | optional CLI scaffolding, SDK templates, static manifest validator, signing/staging helper, compatibility analyzer, local mock harness, conformance fixtures, documentation/codegen | no runtime authority; signing only via expressly permitted external key provider, never bundled secrets |
| Optional \`MOD-DEVELOPER-SDK\` / Workshop extension | UI/CLI developer portal making the same SDK tools available to Sofía under DEV/EVOLVE/Workshop policies | merely a tool client, approval required for privileged actions; not another platform SDK owner |

Distribution can initially be one repository/wheel with explicit subpackages, then multiple separately versioned wheels if dependency isolation/compatibility warrants. Names above are **proposed package identities**, not existing installed packages. Reuse existing \`sofia.platform.*\`, \`sofia.core.*\` and module types; do not immediately rip out the repo to force packaging aesthetics.

**Sofía herself may inspect the SDK and use the SDK's documented scaffolding, schema tests and module development harness** through existing authorized code-inspection/Workshop/DEV/EVOLVE capabilities. She may propose/test candidate modules within isolated approved workspaces. She must not acquire signing keys, deployment rights, arbitrary host file access, owner authentication tokens or bypass CI just because she can use the SDK.

**SDK API coverage:** versioned transport; principal/audience projection and request envelope; capability declarations and typed results; identity and memory *facades* (not raw tables); OS/host/device capability supply and module demand; resource leases; source/provenance and freshness; signing/package/profile/maintenance schemas; deterministic no-effect testing; request cancellation; idempotency; operation outcomes (including unknown); health/readiness; telemetry; diagnostics; model/provider inference contracts; schema compatibility; approved event subscriptions; upgrade/rollback planning.

**SDK ABI rules:** semantic versioning and explicit protocol negotiation; additive changes only within the compatible window; no dynamic importing arbitrary module code during validation; packages pin API minimum/maximum range; backward-compatible adapters only for reviewed behaviors; conformance fixtures on Windows and Linux; no user/private data or tokens in mock artifacts; avoid circular Core⇄Platform imports; stable error taxonomy; documented thread/process safety. Developer tools never directly write live canonical state.

## 6. Required engineering work slices

**ISO-01** audit process boundaries and runtime composition imports; source-level map of Core and module code still loaded in Platform interpreter, service/process ownership, real supervisor and staging semantics.

**ISO-02** shared IPC/API request, response, event, authority, generation, feature-negotiation and state facade contracts with versioned SDK types and negative security tests.

**ISO-03** isolate a Core worker in an independent process without creating a second canonical writer; same end-to-end Memory/Personality/conversation semantics, safe stop and restart, exactly one active fenced Core generation.

**ISO-04** isolate a representative real optional module worker and approved inference provider worker; same effect/permission/health semantics with Platform remaining up, including remote placement.

**ISO-05** signed immutable per-component release staging, drained activation, independent heartbeat/health, fault recovery and revert; integrate with existing component supervisor, module lifecycle and RUN without rewriting their owners.

**ISO-06** staged single-SDK family: typed contracts, platform/core/module facade, devtools, docs, fixtures, ABI compatibility and negative authority tests. Optional developer SDK module is a façade over these tools only.

**ISO-07** exact release impact analysis and restart planner: Core-only/module-only/inference-only/platform/shared-ABI/data-only updates, dependency pause handling, no restart of unaffected component and explicit exceptions.

**ISO-08** B08 and Platform acceptance with live disposable-state VM and authorized GPU worker, Windows/Linux worker and host trials, real model conversation, interrupted in-flight work, dependency failure, STOP, incomplete backup, crash-loop and rollback.

Treat these as **acceptance slices mapped to current PLAT/CORE requirements**, not an untracked duplicate roadmap.

## 7. Testing and evidence gates

For each applicable test, record exact revision, command, environment, active host/process generation, before/after health, request/correlation IDs, receipts and pass/fail/skip. Real process tests are mandatory for claims about independent process restarts; in-memory fake tests alone do not qualify.

- Core update: Platform PID and service uptime remain unchanged; unrelated module PIDs/versions unchanged; only old Core worker PID replaced; exactly one serving Core generation; conversation/memory continuity verified.
- Module update: Platform and Core PIDs unchanged; other module processes unaffected; changed module process/instance generation changed; dependency-aware pausing only where justified; module's old capabilities revoked.
- Provider update: Core/Platform remain; the exact model/digest preserved and a real post-update inference response verified.
- Platform update: independent OS watchdog coordinates supervised restart, single-writer lock reacquisition, durable RUN/ACT reconciliation, authenticated resumption and certified rollback or transparent unavailable state.
- Config-only update: only documented live-reload settings are applied atomically without component restart; invalid revisions roll back.
- SDK backwards-compatible update: old and new consumer negotiate correctly, no unrelated restarts; incompatible ABI update blocked or uses explicit impact plan.
- Failure injection: interrupted drain, worker crash mid-dispatch, lost health packet, stale IPC client, zombie process, heartbeat expiry, outdated SDK, revoked permission, stale DB handle, wrong package digest, dependency cycle, interrupted state migration, worker/outage while gaming and operator STOP.
- Security: no duplicate canonical writer or acting Core; no untrusted module SDK call becoming authenticated owner; no direct SDK bypass of SAFE/RUN; authorization rechecked at execution, scopes/audience maintained through IPC; secrets never in tracing.
- Integration: desktop/Discord/mobile clients receive bounded "Core updating/unavailable" or "Module updating/unavailable" statuses when affected and remain connected where transport permits. LLM provider unavailable does not fabricate text or silently select another model.
- CI: cross-platform packaging, published SDK protocol fixtures, exact revision CI, independent review and approved live-host acceptance required for release qualification.

## 7.1 Federation protocol compatibility in the unified SDK

The approved [Platform Federation and Autonomous Inter-Core Relationships V1](PLATFORM_PEER_FEDERATION_V1.md) adds **federation protocol contracts and client facades to the same Sofía SDK family**, not a separately privileged SDK service. The Platform-to-Platform peer envelope, independent \`platform_instance_id\` / \`core_identity_id\`, audience-bound message/data offer, durable receipt and peer identity negotiation are versioned SDK schemas. Core-owned relationship decisions are inert typed proposals handed to the existing Platform SAFE/ACT pipeline. Actual inbound peer text is lower-trust data, never an imported system instruction.

Core worker updates and signed module updates must preserve or explicitly migrate federation protocol/relationship-context schemas while Platform keeps its canonical state and unmodified peers running. Old peer/client generations must fail closed if incompatible. The peer federation work is FED-01–08; it must not create a second Core code-evolution workstream or duplicate CORE-35–38.

## 8. Sequence, rollout, and protected operations

1. Preserve existing Core B08 and Platform progress; audit current source and failed tests before changing process ownership. Implement SDK contracts and generation-aware Platform facade before splitting live Core.
2. Prove real Core↔Platform IPC using disposable state and fake provider; retain real Ollama local and Fleet integration tests, including exact model identity and privacy context.
3. Independently hosted Core and module lifecycle acceptance comes **before** claiming Core-only/module-only updates. Do not remove working single-process compatibility until replacement has equivalent verified behavior.
4. Implement per-component update coordinator with signed artifacts, verified readiness and safe rollback; do not let an optional module manage the Platform's own release.
5. Bundle UI/SDK developer tools only after their API contracts are stable; never let SDK version churn force unrelated runtime restarts.
6. Test on approved Windows/Linux/VM environments with disposable state first. Production canonical migration, protected release activation, service restarts, new host enrollment and actual physical device effects require **separate explicit authorization**.
7. Distinguish DESIGN/ALPHA/BETA/RELEASE CANDIDATE/PRODUCTION READY/BLOCKED honestly. Updating documentation is never proof of operational zero-downtime.

**Owner acceptance in plain English:** "Update only Core and leave Platform and all unrelated modules running; update one module and leave Core/Platform running; update the inference provider while retaining the exact approved model and worker policies; restart the Platform only when a Platform-owned executable/ABI or protected host change actually requires it; make the unified SDK usable to build/test Platform, Core and Modules without becoming a second authority."
