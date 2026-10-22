# Sofía 2.0: detailed non-Core development plan

**Purpose:** specify the capability and platform roadmap outside Sofía's persistent personal Core. These are **design contracts and candidate releases**, not assertions that they are fully coded. They use existing proof-of-concept packages where possible. The 780-task ledger supplies original requirements and evidence, not automatic completion.

## 1. Three non-Core classes

| Class | Delivery role | Absence/failure policy |
| --- | --- | --- |
| PLATFORM | required shared runtime and governance foundation | Core cannot operate normally without the minimum state, authority and supervisor |
| RELEASE_MODULE | supported companion-facing modules bundled with initial Sofía 2.0 | degraded channel is explicit; other channels and Core continue |
| OPTIONAL_MODULE | separately versioned, permission-scoped abilities | Core retains identity, memory and ordinary conversation when unavailable |

**Core does not become a giant plugin host.** Its desire/goal loop requests module capabilities through the gateway, with SAFE/RUN doing authority and effects. Autonomous choice of an interest is distinct from consent to download, execute, spend or publish.

## 2. Platform work packages

### PLAT-01: Runtime, supervision and composition
Own the single application root, dependency composition, heartbeat, lifecycle, graceful shutdown/restart, watchdog supervision and startup diagnostics. Reuse existing RUN/runtime and service code. **Acceptance:** application starts without optional modules; no duplicate Core, model or DB writer; restart preserves identity/conversation; failure and safe-mode tests; actual host restart pending separate approval.

### PLAT-02: Canonical state, history and recovery
Own reviewed SQLite schemas, migrations, backup manifests, restore verification, correct optimistic revisions, bounded retention and durable receipts. Reuse canonical State Plane. **Acceptance:** simulated interrupted write and backup/restore preserve history; no second writer; no state changes during simple module discovery; live migration/promotion never implicit.

### PLAT-03: SAFE, identity and policy
Own authenticated principals/audiences, approval scope, operator STOP, credential revocation and least-privilege grants. **Acceptance:** unauthenticated or mis-scoped module requests fail closed; revoked credentials cannot execute; guest input cannot inherit owner authority; real credential enrollment remains owner-supervised.

### PLAT-04: RUN/ACT durable effect broker
Own task queue, leases, retry policy, idempotency, cancellation, budgets, delivery/effect receipts and uncertain-outcome reconciliation. **Acceptance:** crash after remote dispatch never creates fictitious completion or blind retry; cancellation under load is deterministic; STOP prevents new optional effects.

### PLAT-05: Module SDK and lifecycle broker
Own manifest validation, immutable artifact/digest handling, dependency resolution, platform compatibility, reviewed sandbox profiles, staging, enable/disable, downgrade and health projection. Reuse existing CapabilitySystem/Gateway and OPS dependencies. **Acceptance:** manifest metadata cannot execute code; untrusted module cannot self-register privileged handlers; cross-module name collisions rejected; failed initialization cannot break Core.

### PLAT-06: Model and provider orchestration
Own replaceable cognitive workers, explicit model routing, unload/reload resource policy, provider outages and bounded fallback reporting. No silent provider failover or identity substitution. **Acceptance:** provider unavailable yields truthful status; switch preserves persisted Core state; workload/gaming caps enforced and recorded.

### PLAT-07: Fleet, OS compatibility and host governance
Own approved host discovery, endpoint identity, telemetry freshness, trusted enrollment and placement advice. Observe only by default. **Acceptance:** unknown host never becomes trusted by discovery; Artemis, Venus and approved guest host operations stay scoped; no accidental runtime ownership transfer.

### PLAT-08: Observability, verification and releases
Own structured logs, trace IDs, sanitized diagnostics, source/task evidence projection, signed release manifests, sandboxed candidate tests, update activation broker and rollback. **Acceptance:** reproducible pinned test results; independent artifact signatures; roll-forward/rollback and restart health checks; no unsigned release deployment.

**Platform sequencing:** PLAT-01/02/03/04 prerequisites; PLAT-05 before adding new module runtime installers; PLAT-06/07/08 can reuse current owners and mature in bounded slices.

## 3. Initial companion release modules

### RM-DESKTOP: Desktop text, tray and settings
**Purpose:** always-accessible Core communication and owner-facing controls on the selected host.
**Capabilities:** send/receive conversation turns, show grounded model/connection health, manage allowed user-facing preferences, show requested approvals, expose read-only task/module status.
**Integration:** authenticated local principal; canonical conversation/turn kernel; owner-only UI requests through SAFE; event/receipt separation.
**Failure plan:** Core persists through desktop UI crash; restart UI without starting a second Core.
**Acceptance:** real conversation enters one canonical session, no transcript cross-audience leak, UI service controls require permission, chat surface can clear without resetting memory.

### RM-DISCORD: Discord communication
**Purpose:** remote text channel for authorized personal conversation.
**Capabilities:** bounded DM/session routes, notifications/outreach where permitted, message delivery receipts, explicit unavailable behavior.
**Integration:** Discord principal credentials bound to canonical social audience, shared Core state but audience-specific memory retrieval.
**Failure plan:** bot outage never blocks desktop; queued notifications reconcile actual delivery.
**Acceptance:** DM authentication and scope tests, invalid/revoked binding refusal, message idempotency, message sent != message seen.

### RM-AVATAR2D: Fox avatar and wardrobe
**Purpose:** render Sofía's canonical 2D fox-girl form; Core decides expressive intent, renderer performs visible effects.
**Capabilities:** layered facial expressions, ear/tail/gaze/blink, clothing overlay, appearance preferences, wardrobe sets, click regions and render receipts.
**Integration:** Core expression/presentation projections; optional creative asset pipeline; independent renderer process as needed.
**Failure plan:** rendering crash doesn't remove text or identity; missing assets use approved fallback.
**Acceptance:** actual rendered frame/asset receipt before claiming a visual change; layered rigs verified; production UI renders independently of model text.

### RM-VOICE: Speech (initial release candidate, not automatic release blocker)
**Purpose:** natural, intelligible speech and optional listening using explicit consent.
**Capabilities:** configurable TTS/STT, latency/quality diagnostics, speaking-state and interruption receipts, mic capture gate.
**Integration:** approved TTS/STT engines as replaceable adapters, coupled to conversation turn IDs.
**Failure plan:** text remains available; no claim of speaking without synthesis/playback receipt.
**Acceptance:** voice interruption, speech quality, privacy, device loss and audio transport tests. Owner must decide whether voice is mandatory for initial Sofía 2.0 launch.

### RM-MOBILE: Android companion (post-initial unless ready)
**Purpose:** scoped mobile access, pairing and optional notifications.
**Capabilities:** independently authenticated device identity, chat, read-only health, explicitly approved sensor capture.
**Integration:** per-device credentials, canonical audience, no direct DB access.
**Failure plan:** revoked phone loses access without blocking Core.
**Acceptance:** revoke/re-pair, offline/reconnect, audience isolation, notification receipts and consent tests.

## 4. Optional expansion modules

### MOD-DEV: Source engineering and self-improvement tools
**Function:** read authorized source; propose changes; invoke bounded OpenCode/other reviewed executor; run isolated tests and produce patch/review bundles.
**Boundary:** Core holds the reason to improve; DEV owns workspace/tool execution; releases and Git publication require separate authority.
**Acceptance:** exact-path/diff scope, malicious instructions in source treated as data, test evidence pinned, no auto-install or unauthorized push.

### MOD-RESEARCH: Web and evidence collection
**Function:** authorized searches, document ingestion, citations, source freshness and competing explanations.
**Boundary:** external text remains untrusted, not canonical autobiographical truth or commands.
**Acceptance:** provenance, expiry, prompt injection tests, privacy restrictions and bounded network/token use.

### MOD-CREATIVE: Art, writing, sound and media creation
**Function:** prompt/asset workflows, optional ComfyUI process control, image revision, non-Core creative projects and finished artifact management.
**Boundary:** interest/creative choice arises in Core/LIFE; media generation occurs in module, with asset provenance and resource budgets.
**Acceptance:** repeatable workflow metadata, recover after generation crash, managed assets, no false claims of output, explicit permission for file/process effects.

### MOD-VISION: Consent-based screen and environment perception
**Function:** capture approved windows/screens, extract scoped context and generate bounded observations.
**Boundary:** capture consent, redaction, retention and capture quotas are enforced by platform; no covert collection or indefinite image retention.
**Acceptance:** denied capture fails closed, multi-monitor restrictions, raw-media deletion policy, no secrets copied into memory.

### MOD-DESKTOP-ACT: OS/UI automation
**Function:** mouse/keyboard/screen workflows and tightly scoped process operations on permitted hosts.
**Boundary:** never automatic gaming interference, privilege elevation, or unrestricted screen control. Separate observation from effect.
**Acceptance:** user pause, STOP, exact application target, audit/receipt, safe cancellation and host-dependent tests.

### MOD-HOMELAB: Servers, VMs and services
**Function:** read telemetry, detect downtime, compare configs, request approved service/VM actions on Artemis and other enrolled hosts.
**Boundary:** OPS/Fleet owns trusted hosts; SAFE authorizes actions; no silent provisioning or canonical runtime migration.
**Acceptance:** offline/stale telemetry reported honestly, least privilege, rollback for reversible operations, protected backup and host isolation tests.

### MOD-ROBOTICS-GAIA: Gaia 2.0 hexapod
**Function:** typed SSC-32 servo abstraction, per-leg kinematics, virtual gait rehearsal, calibrated movement and future sensors.
**Boundary:** physical motors never driven directly from freeform LLM output; guarded action limits, emergency STOP and explicit hardware authorization.
**Acceptance:** offline simulator first, pulse/range and gait tests; supervised physical trials only after fail-safe validation.

### MOD-TRAINS: HO model railroad control
**Function:** JMRI/LocoNet observation, locomotive roster and power state, optional dispatcher/automation, track-aware safe commands.
**Boundary:** railroad hardware state is external evidence, not model-assumed; approvals for power or movement; independent interlock logic.
**Acceptance:** read-only roster/power projection first, lost connection and conflicting command tests, supervised layout command trials.

### MOD-GAMES: Game assistance and simulation
**Function:** context-aware strategy help, permitted game interfaces, optional Space Engineers/Factorio project tooling and performance-aware scheduling.
**Boundary:** no PC input or GPU-heavy background work during gaming without explicit authorization.
**Acceptance:** per-game adapters, correct game detection, resource policy, no nonconsensual automated input.

### MOD-PRODUCTIVITY: Personal projects and household tools
**Function:** goals/projects, reminders, home inventory, documents, calendars and approved productivity integrations.
**Boundary:** personal goals and interest evaluation remain in Core/LIFE; external SaaS tools require distinct grants and audience scope.
**Acceptance:** real artifact/receipt, no fabricated reminder/message, provenance and deletion behavior.

### MOD-ML: Training, experiment and candidate management
**Function:** reviewed datasets, train/evaluate small candidates, skill benchmarks, reproducible LoRA/ML experiments and cautious selection.
**Boundary:** no ambient training on raw personal conversations or unreviewed memories; every source and deploy operation needs purpose-scoped authority.
**Acceptance:** reproducible seed/lineage, held-out comparison, revoked-source handling, compute budget, no self-certified superiority.

### MOD-GENERALIZATION: Reusable learned skills
**Function:** evaluated transferable procedures, Windows/Linux adapters, failure recovery, long-horizon execution skill catalog.
**Boundary:** learned skill cannot mint execution permissions or mark a RUN effect complete; owner-approved tools still execute.
**Acceptance:** held-out unfamiliar tasks, cross-host transfer, negative trials, versioning and evidence of actual outcomes.

### MOD-VWORLD: Virtual workspace and simulation
**Function:** local virtual scenes, spatial or companion experiences and safe rehearsals before real actions.
**Boundary:** simulated observations must remain labeled simulation, never promoted to physical observations without evidence.
**Acceptance:** replayable scenes, source provenance, deterministic test fixtures and no fake real-world claim.

### MOD-MENTOR: Evaluation and feedback
**Function:** behavior/personality quality audits, regression challenge sets, sanitized review exchange and uncertainty reports.
**Boundary:** evaluator advice is evidence to review, not a source of authority, identity rewrite, success certification or live deployment permission.
**Acceptance:** blind/negative controls, exact rubric/test cases, result provenance, no overclaim of real-life acceptance.

### 4.1 Complete module inventory and parent boundaries

As approved on October 22, 2026, the catalog now holds **55 named entries**, retaining the older 41 and adding 14: 5 release, 47 optional, 1 attached interaction submodule and 2 adapters. All ten formerly proposed IT and four maker/engineering entries are accepted **for design**, not deployed. See [full catalog](PLATFORM_AND_MODULE_CATALOG_V1.md) and the [55-entry ownership register](MODULE_OWNERSHIP_MATRIX.md).

The new entries are: `MOD-AVATAR3D`, `MOD-AVATAR-STUDIO`, `MOD-INTERACTION` (**Avatar submodule**), `MOD-VTUBER-BRIDGE` (**Avatar renderer adapter**), `MOD-WORKSHOP`, `MOD-DIGITAL-TWIN`, `MOD-KNOWLEDGE-LIBRARY`, `MOD-MEMORY-IMPORT` (**PLAT-02/MEM adapter**), `MOD-PROJECT-FORGE`, `MOD-FILE-WATCH`, `MOD-HOUSEHOLD`, `MOD-FINANCE`, `MOD-DATA-ANALYTICS`, and `MOD-CALENDAR`. These are not new Core emotions, gesture decisions, rights, autobiographical stores, or execution supervisors. All actual effects still use Platform SAFE/RUN, per-profile maintenance and interoperability tests. Public/private gesture assets are content packs within Avatar, not another new module.

## 5. Non-Core implementation waves

| Wave | Goal | Main dependencies | Exit criterion |
| --- | --- | --- | --- |
| N00 | Map existing non-Core task IDs and live code owners | original 780 inventory, source search | individually traceable owners; unverified marked unknown |
| N01 | Strengthen platform and establish safe Module SDK | Core B00/B01, SAFE/RUN | discover/validate/deny/fail tests; no implicit execution |
| N02 | Bundle Desktop, Discord and 2D Avatar | Core conversation/expression, N01 | cross-channel privacy, renderer and failure-isolation acceptance |
| N03 | Voice and Mobile readiness | N02, consent/device identity | intelligible speech, device revocation, explicit release inclusion decision |
| N04 | Research, Creative, Productivity and DEV integration | N01, scoped capabilities, resource budget | completed artifacts with real receipts and rollback/recovery |
| N05 | Homelab, vision, desktop actions, robotics, trains and games | N01, trusted hardware/host adapters | simulation and authority tests; physical actions remain gated |
| N06 | ML, generalization, virtual worlds and mentor/evaluation | N04/05 where relevant, learning grants | independent benchmarks and source lineage |
| N07 | Cross-module reliability and operational release | all chosen release modules | optional-module crash does not harm Core; exact-revision CI; authorized host trials |

Waves are **planning scopes**, not new original CA task IDs or permission to edit concurrently with the Core agent. Develop in owner-selected batches once prerequisites are available.

## 6. Shared acceptance matrix, required for every module

For each module record: module ID/version; mapped original task IDs; manifest and signature/digest; platform; canonical Core/Platform caller; typed capability names; required principal/audience permissions; dependencies; resource/cost budget; installation/upgrade/rollback; health/degraded states; full failure test; storage/retention and secrets handling; genuine effect/result receipt; test commands and environment; compatibility promise; support and removal behavior.

Five minimum fault cases: missing dependency, invalid manifest, unauthorized call, effect timeout/unknown result, and module crash during Core conversation. For hardware/network modules also test offline endpoints, stale telemetry and revocation.

No module counts as Core functionality simply because it exists or registers. No module is allowed to alter the Constitution, canonical owner, SAFE, run policy or memory through arbitrary persistence.

## 7. Priority and owner decisions

**Default priorities:** protect Core/Platform first; ship reliable text + 2D + Discord companion; stabilize voice next; then DEV/research/creative tools; then homelab/physical modules; finally advanced ML and generalization experiments.

**Explicit open decisions:** Is voice mandatory in Sofía 2.0 initial release? Should Android be bundled initially or deferred? Which single optional module should be developed first after N02? What is the permitted initial module installation/signing trust root? What class of homelab actions, if any, may use preapproved standing grants?

Until those are answered, use conservative choices and continue independently eligible design, tests and adapter work. Do not block B00–B08 development over optional-module decisions.
