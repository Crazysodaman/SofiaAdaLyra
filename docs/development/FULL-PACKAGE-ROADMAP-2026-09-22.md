> **Fleet/tray extension candidate — 2026-09-26:** `feature/fleet-tray-remote-controls` contains the new activity-aware Fleet control plane and Windows tray/remote-client source. It is intentionally recorded as a **candidate** until focused Windows tests and live canaries pass; no production fleet/runtime migration claim is implied.

> **Project status update — 2026-09-26:** PKG-ENVIRONMENT foundation PR #110 (`766bf21e`) and NWS/persistent-HOST extension PR #111 (`2b753fdb`) are merged to `main`. PR #111 adds a narrowly authorized NWS route pinned to HTTPS `api.weather.gov` under `environment.nws.read`, durable per-machine HOST location keyed by stable machine identity, startup injection, bounded machine-inventory projection and USER/HOST separation. Extension evidence: **85 focused**, reported green full suite, supervised live `nws:KGKY` canary, **96 persistence-focused**, and final reported green full suite. Optional live Home Assistant canary remains separately gated; general browsing/search and arbitrary geocoding remain closed. Earlier DEV/KNOW/INTEGRATE/OPS source acceptance remains unchanged; none of this is proof of production remote fleet orchestration, RUN 24/7 supervision, live failover or soak.

> **Project status update — 2026-09-26 (UI):** PR #115 (`381ac9a`) merged the rebuilt canonical text/workbench foundation and PR #116 (`7f072861`) merged the accepted Windows desktop workbench. Current `main` now has durable unsent drafts, private workbench state, one canonical `SofiaApplication`/conversation path, a single-owner application worker, adaptive ENVIRONMENT/AVATAR/emotion theme projection, shallow chamfered HUD surfaces and reviewed Quick Tools that never auto-send. Acceptance included **58 UI + 24 application/Discord**, later focused UI/AVATAR passes, **90/90 integration repair**, supervised Windows use and a final reported green full repository suite. The same repair gate hardened reviewed-memory SQLite threading/cleanup and explicit request-level tool suppression for trusted interaction turns. Voice, renderer/avatar viewport, mobile/web and provider cancellation remain separately gated.

> **Architecture audit update — 2026-09-27:** chat history plus current code/PR review found a missing boundary between **shared state continuity** and **self-update/release continuity**. They are now explicit cross-package workstreams called the **Sofía State Plane** and **Release/Integrity Plane**, not extra packages. The audit also surfaced concrete P0/P1 gaps: production composition still instantiates `TestActionExecutor`; authoritative state is split between SQLite and multiple JSON/source files; schema creation is decentralized without a central migration/compatibility coordinator; a missing local identity file can create a new `instance_id`; Fleet candidate source can treat an installed matching agent version as enrollment-ready without independently proving the installed artifact digest; dependency/model identity is not fully immutable; PKI bootstrap private keys are file-protected development material rather than final production key custody; and no whole-Sofía signed immutable release manifest/canary/convergence path exists yet. These are assigned to the existing packages below.

# Sofía Ada Lyra | full roadmap and per-package delivery contracts

**Revision:** 2026-09-26 (America/Chicago). **Status:** planning and evidence index, **not** proof of implementation, deployment, live uptime, database replication, automatic failover, geolocation or weather access. This document expands the authoritative [ROADMAP.md](../../ROADMAP.md), the [master readiness index](../../MASTER-ROADMAP-READINESS.md), the [reliability contract](pkg-reliability-control-plane-contract.md), the [reliability implementation sequence](pkg-reliability-implementation-plan.md), and the [RUN watchdog/failover contract](pkg-run-watchdog-failover-contract.md). Re-check actual branch/PR and pinned CI/live evidence before changing a package's state.

## Project promise and nonnegotiable boundaries

Sofía Ada Lyra is one persistent canonical assistant identity, independent of model, host, process, channel, avatar and Gaia hardware. The model supplies cognition, **not** identity or authority. Keep Constitution/integrity, privacy, authenticated audience, source evidence, memory, and physical/external actions independently enforced. Model text and source-document text cannot prove sensing, execution, receipt, authorization, consciousness or uptime.

Only Sparks can explicitly authorize the **final irreversible removal/decommissioning of each exact enrolled machine and proposal revision**. Sofía may discover/enroll within standing policy, quarantine, drain and prepare removal, but may never self-approve or use an expired/implicit approval. Protected-state amendments, destructive actions, external disclosure and physical control keep their separate gates.

**Release order:** CORE → INTERACT → MEM → SOCIAL minimum Sparks-only principal/audience → Discord D0-D4 via NET/UI/SAFE → OPS trusted deployment-host telemetry/enrollment → RUN verified supervised 24/7 and applicable recovery/failover → later separately authorized general web/search. Work on other packages may run in parallel but cannot bypass those gates. SAFE and VERIFY run continuously.

**Definitions:** `on main` = code exists, **not necessarily active or accepted**; `draft candidate` = code on a draft PR/branch; `design-only` = contract/proposal without deployed capability; `offline tested` is not real-host integration; `live accepted` requires current-revision authenticated observation/receipts; `deployed` requires a separately approved activation. Test counts from different SHAs are never added together.

## Milestones and exit criteria

| Stage | Delivery focus | Exit evidence, not just documentation |
| --- | --- | --- |
| M0 | Freeze observed baseline and protection | Clean/source-pinned inventory, all durable SQLite/files/logs/protected state identified, no unsafe cleanup; current focused tests and known limitations recorded. |
| M1 | CORE + INTERACT quality | Grounded self-description/personality, natural varied interaction and boot awareness, measured responsiveness, supervised real-model tests plus current-revision integration suite. |
| M2 | MEM + SOCIAL minimum | Original conversations durable across restart; corrections/provenance/privacy verified; only authenticated Sparks principal can access initial DM scope; negative leakage tests pass. |
| M3 | Discord D0-D4 | Trusted Sparks-only DM receives/responds/reconnects/denies outsiders; verified API delivery, dedupe, stop/revoke, secrets handling and restart acceptance. No general web route. |
| M4 | OPS baseline + RUN process resilience | Read-only authorized Windows/Linux/Pi telemetry, trusted enrollment, independent local OS supervisor, safe boot scan, bounded restart/backoff, out-of-band stop, durable state inventory/backups and independent restore test. |
| M5 | Durable work, fairness, capability truth | Durable operation/outbox ledger and outcome-unknown reconciliation, operator pins/no-reboot/approval, verified capability registry, measured background backoff and host-resource reservations. |
| M6 | Replicated state and runtime failover, if approved | Two independent data-bearing locations with one writer and selected measured durability policy; independent election/fencing, standby supervisor, isolated third backup, partition/stale-primary tests, measured RPO/RTO and actual real-host recovery. Do not claim HA before this. |
| M7 | Verified 24/7 and autonomous operations | Soak test at a pinned revision; crash/restart/UPS/maintenance/reconnect results; bounded actions, safe rollback and proactive non-spam notifications. General web/search gate may be considered **only after** Discord, OPS and RUN acceptance. |
| M8 | Parallel enhancements and later web | ACT, REL, AVATAR, DEV, KNOW, INTEGRATE, BODY, EVOLVE, CLEAN, ENVIRONMENT and UI maturity gated individually; ENVIRONMENT's offline clock/location/timezone/season/daylight work may precede later web, while direct internet weather/search keeps separate privacy, destination, provenance and grant controls. |

M4-M7 are engineering gates rather than a mandate to deploy PostgreSQL immediately: first verify existing SQLite backups and cross-store consistency; compare migration costs and only adopt a replication-capable backend after test evidence and separate activation approval. Local 24/7 uptime and true multi-host HA are **different claims**. A watchdog is a detector; only an authorized supervisor/executor can start an instance, and only a fenced exclusive leader can become authoritative.

## Architecture audit package assignment | State Plane + Release/Integrity Plane

No package #21/#22 is created. The new requirements are deliberately split among existing owners so no one subsystem can both rewrite Sofía and redefine why that rewrite should be trusted.

| Package | State Plane responsibility | Release/Integrity responsibility |
| --- | --- | --- |
| **CORE** | Canonical identity bootstrap; configuration precedence/provenance; never mint a second Sofía on a normal joining/rebuilt node. | Bind runtime/model compatibility to a verified release; cognition/model replacement never defines identity or authority. |
| **INTERACT** | Emit/consume stable event, causation, correlation and priority metadata for globally ordered user interaction. | Preserve interaction contracts across releases; no release may claim rendered/audio/physical completion without receipts. |
| **MEM** | Primary State Plane owner: storage abstraction, authoritative-state inventory, schema versions, shared-state semantics, semantic integrity and consistent restore. | Define data compatibility windows for release upgrade/rollback; expand→migrate→contract rather than irreversible one-step schema mutation. |
| **SOCIAL** | Bind every person-scoped row/object/cache to authenticated principal and audience; enforce isolation in shared storage. | Release tests must prove no privacy regression across migration/rollback. |
| **NET** | Authenticated transport to State Plane/services without implicitly granting DB/write authority. | Protocol/version negotiation and pinned peer identity; network reachability never proves compatible or approved software. |
| **UI** | Shared settings/history use authoritative state; clearly separate roaming values from machine-local overrides and offline queues. | Client compatibility and later VOICE/renderer assets are release-declared; UI cannot silently target an incompatible runtime. |
| **RUN** | Single authoritative runtime/writer, monotonic fencing, clock uncertainty handling, global event ordering, degraded-mode rules and fleet-wide background budgets. | Activate exact releases, detect crash loops/readiness failures, revert/forward-fix safely, publish authoritative endpoint only after health/data compatibility. |
| **OPS** | Data-bearing node placement/health, replica/failure-domain evidence, asset locality and host state. | Canary/wave rollout, artifact distribution, installed-agent independent attestation, Fleet convergence, quarantine of corrupt/outdated/incompatible nodes. |
| **ACT** | Durable shared outbox/jobs with global rather than per-worker quotas; stable idempotency/causation IDs. | Delivery workers must be release/protocol compatible before consuming shared work. |
| **REL** | Principal-bound relationship/absence state roams through State Plane rather than machine-local singleton assumptions. | Migration tests preserve relationship provenance without inventing or duplicating events. |
| **AVATAR** | Roaming presentation metadata may live in State Plane; large assets remain content-addressed immutable artifacts. | Renderer/wardrobe/model assets are digest/version bound and rollback-compatible. |
| **DEV** | Does not directly mutate authoritative running state except through approved typed migrations/tools. | Primary build owner: isolated candidate, locked dependencies/runtime, provenance/SBOM, immutable artifacts, exact digests and reproducible build evidence. |
| **BODY** | Calibration/state ownership is explicit; current hardware observations stay local/derived unless deliberately persisted. | Firmware/controller/calibration compatibility is separately verified before physical motion under a new release. |
| **EVOLVE** | Reviewed configuration/preference changes use shared revisioned state; protected identity/Constitution remains higher trust. | Self-improvement ends in a governed exact release proposal. EVOLVE cannot self-authorize changes to signer, verifier, approval, fencing, emergency-stop or recovery trust roots. |
| **CLEAN** | Separate source, shared runtime state, protected state, secrets, immutable assets, caches and logs; migrate without deleting history. | Retention/GC for old releases/assets/evidence while preserving rollback and forensic history. |
| **KNOW** | Shared provenance/document metadata may roam; rebuildable indexes and large artifacts need not occupy transactional DB rows. | Build/release docs and migration runbooks remain source-grounded and revision-specific. |
| **INTEGRATE** | Typed database/State Plane adapters and least-privilege per-service roles; no universal Fleet DB credential. | Integration/version compatibility and side-effect semantics become part of release acceptance. |
| **SAFE** | Secrets custody, per-service DB roles, protected-state trust anchors, revocations, tamper-evident audit and bare-metal/operator recovery. | Primary trust owner: signature verification, anti-rollback, signing-key custody, protected execution base. Also replace production `TestActionExecutor` with a fail-closed production boundary before action authority can ever be opened. |
| **VERIFY** | Corruption, semantic-integrity, backup/restore, stale replica, partition, bare-metal and privacy/isolation tests. | Exact-revision CI/live evidence, upgrade/downgrade/schema compatibility, bad signature/artifact/dependency/model/protocol tests, canary/rollback/convergence proof. |
| **ENVIRONMENT** | Shared configured USER/SITE/HOST metadata with provenance; current readings/caches remain freshness-bound and may be local/derived. | Provider/config schema compatibility is release-tested; local environment overrides cannot silently become global state. |

### State Plane classification contract

Before migrating to any shared backend, classify every persistent object into exactly one primary category:

1. **Shared authoritative state:** conversations, reviewed memories, principals/relationships, fleet inventory, durable jobs/outbox, runtime leadership/leases, approvals, deployment records and intentionally roaming configuration/presentation.
2. **Protected state/trust anchors:** Constitution/identity authority roots, release verifier trust, approval authority, fencing/recovery policy, revocations and emergency controls. These may be replicated/backed up, but not exposed as ordinary mutable application rows.
3. **Secrets:** Discord/GitHub/Home Assistant/provider tokens, private keys, database credentials, signing keys and recovery credentials. Shared state stores references/scope/status, not broad plaintext access.
4. **Immutable/content-addressed artifacts:** Sofía releases, dependency bundles, model files, avatar/voice assets, migration bundles and evidence. Store digest/version/location metadata in State Plane; distribute artifacts separately.
5. **Local ephemeral/rebuildable state:** PID/device handles, caches, temp downloads, current GPU/process samples, local sockets and other host observations that should not become authoritative merely because they exist.

**One logical database does not mean universal database authority.** Each runtime/service/agent receives the minimum role it needs. A telemetry agent must not gain write access to memories, approvals, identity or release state.

### Schema and rollback contract

State Plane schema evolution must be centrally versioned. Releases declare minimum/maximum compatible schema and migration revision. Use **expand → migrate → verify → contract** so the previous accepted release remains usable during the rollback window. If the live database is newer/older than a runtime's declared compatibility, startup fails closed rather than improvising migration.

Migrations require an exclusive migration lease, pre-migration recovery point, deterministic migration ID/checksum, resumable/idempotent semantics where feasible, post-migration semantic validation and an explicit rollback/forward-fix decision. A healthy SQL file is not sufficient proof of healthy Sofía state; VERIFY must check domain invariants such as provenance links, principal ownership, grant/revocation consistency, deployment lineage and outbox/action states.

### Canonical identity bootstrap contract

The current single-host behavior may create a new `instance_id` when the identity file is missing. That is acceptable only during an explicitly authorized **first canonical bootstrap**. A normal new/rebuilt Fleet node must authenticate, obtain the canonical identity/trust material through the approved State Plane/recovery path, verify it, and join as an execution node. If canonical identity cannot be proven, enter recovery/quarantine mode and **do not create a second Sofía**.

### Release/Integrity Plane contract

Self-improvement uses:

**evidence → proposal → isolated DEV implementation → focused/full VERIFY → SAFE classification/approval → immutable build → signed release manifest → canary → readiness/data compatibility → staged Fleet rollout → convergence proof → rollback or forward-fix.**

A release manifest binds at minimum:

- release ID and exact Git revision;
- application/package version and supported OS/architecture;
- Python/runtime/build-tool version;
- dependency lock/SBOM digest and artifact hashes;
- State Plane schema compatibility and migration bundle digest;
- Fleet protocol and minimum/maximum compatible agent versions;
- provider/model identity plus immutable model artifact digest when the provider exposes one;
- Constitution/protected-state compatibility;
- configuration schema/capability schema versions;
- avatar/voice/other immutable asset digests as applicable;
- signing identity, signature and approved release lineage.

A mutable model tag such as `qwen3:14b` is not by itself sufficient immutable release identity.

### Protected execution base

Normal autonomous self-update may not replace or relax the mechanisms that decide whether the update is trustworthy. At minimum the following are higher-trust SAFE surfaces: release signature verifier, trusted root public keys, approval verifier, emergency stop, cross-host fencing/leadership enforcement, anti-rollback policy, recovery boot path and protected-state verifier. Sofía may diagnose/propose changes to them, but activation requires the independently defined higher approval tier.

### Control-agent independence contract

The Fleet control/supervisor agent is a **separately versioned recovery-plane component**, not just another Sofía runtime package. It must be installable, startable, health-checkable, rollbackable and updatable independently from the main Sofía release. A bad Sofía application/model/UI release must not be able to disable the mechanism responsible for stopping, fencing, rolling back or recovering it.

Agent updates use their own compatibility matrix and canary/wave rollout. Do not require the currently broken Sofía runtime to repair or replace its supervisor. The agent may verify/install an approved Sofía release, but ordinary Sofía self-update may not silently replace the agent's recovery/trust behavior.

### State Plane unavailable / degraded-mode contract

Loss of the authoritative State Plane does **not** grant a local runtime permission to become a competing source of truth.

When authoritative state or writer/leader authority cannot be proven:

- local clients may preserve clearly marked **pending input/drafts** for later reconciliation;
- safe read-only use of previously verified immutable release/config/assets may continue where privacy/freshness rules permit;
- cached memories, relationships, approvals, grants and fleet state may be displayed only with explicit stale/degraded provenance where appropriate;
- no node may create/promote authoritative memories, relationship changes, approvals, grants, deployments, external side-effect jobs or protected revisions as if they were committed;
- consequential ACT/DEV/EVOLVE/OPS/BODY actions fail closed unless an independently valid offline-safe authority contract explicitly permits that exact operation;
- queued inputs/actions must receive stable IDs and reconcile against authoritative state after recovery rather than being blindly replayed;
- once State Plane connectivity returns, RUN reconciles leadership, sequence/order, pending work and uncertain external effects before normal authoritative writes resume.

### Append-only protected audit contract

Security-critical evidence is **append-only and tamper-evident**, not merely another mutable table. Approvals, denials, grants/revocations, release signatures, deployment decisions, migrations, protected EVOLVE changes, emergency stops, fencing/leader transitions and machine-decommission decisions receive immutable event IDs, actor/principal, exact revision/digest, causation/correlation IDs, timestamp and receipt/evidence references.

Corrections do not overwrite the original event. They append a superseding/reversal event. Use hash chaining, signed checkpoints, write-once/append-only storage controls or an equivalently verified mechanism so deletion/rewrite is detectable. Backup/restore must preserve and verify the audit chain.

### Database invariant and constraint contract

The future authoritative relational schema must enforce domain invariants in the database where practical rather than relying only on Python call order.

Required examples include:

- foreign keys for conversation→principal/session, memory→provenance/source, deployment→release/node and grant→principal/node relationships;
- uniqueness/idempotency constraints for immutable event/request/release identifiers;
- append-only or guarded-write semantics for original conversations, audit evidence, approvals and other records whose history must not be silently rewritten;
- ownership/audience columns and constraints that prevent person-scoped records from becoming unowned/global by omission;
- explicit revocation/validity constraints so an active authorization cannot simultaneously be represented as revoked/expired;
- state-machine constraints for jobs/actions/deployments so impossible transitions are rejected;
- migration/schema checks that prevent incompatible runtimes from writing newer/older schemas;
- database-level transaction boundaries for operations that must commit atomically, with documented reconciliation for effects that cannot share the transaction.

Application validation remains useful, but it is not the sole protection against authoritative-state corruption.


### Independent Fleet-agent verification

A matching version string is not enough to mark an existing Fleet agent trusted. Enrollment/update acceptance must independently verify the installed artifact/package identity, digest/signature, expected service identity/configuration and protocol compatibility. An installer returning `verified=true` is a receipt, not the sole proof; the controller or a separate verifier must establish the installed state.

### Configuration source-of-truth contract

Define and expose precedence as:

**protected policy → shared authoritative configuration → approved machine-specific override → process/bootstrap override**.

Every durable setting records scope, source, revision, actor/authority, timestamp, restart requirement and optional expiry. Master Settings must show whether a value is shared, host-local, inherited, read-only or unavailable. No setting may silently alter Venus while leaving Artemis with an unknown conflicting policy.

### Global event/concurrency contract

Desktop, Discord, future voice/mobile, ACT and background reflection may all produce work concurrently. Shared events/jobs therefore require stable `event_id`, principal/audience, conversation/workflow ID, causation ID, correlation ID, priority, accepted timestamp and idempotency identity where applicable. RUN owns scheduling/preemption so foreground authenticated interaction outranks optional background work and distributed workers cannot each multiply an autonomy quota independently.

### Bare-metal recovery contract

Recovery must work from clean hardware with the normal runtime unavailable: obtain independently held recovery credentials, verify signed release and trust roots, restore/verify State Plane and protected state, re-establish fencing/leader epoch, reconcile uncertain external effects, prove canonical identity and only then resume authoritative execution. Recovery must not depend solely on Discord, the failed database primary or credentials stored only inside the failed Sofía installation.


## Per-package roadmap: 20 packages

### 01. PKG-CORE | cognition, identity, continuity

- **Current:** foundations on `main` after PR #1. A joint INTERACT/CORE live-quality repair gate is open after supervised Discord dialogue exposed generic assistant fallback despite correct self/embodiment grounding.
- **Build:** canonical identity/Constitution and integrity boot checks; observed restart time/gaps; varied evidence-grounded startup/file-change remarks; model/provider abstraction, deliberation/response budget, graceful unknowns, context budget and cognitive operation audit; no invented offline thoughts or subjective experience.
- **Depends on:** SAFE/VERIFY at every step; INTERACT for end-to-end quality; MEM for durable grounding.
- **Exit:** current-revision full suite + supervised real-model startup, identity, conversational naturalness, restart awareness and measured response latency; no repetitive fixed notices or unsupported execution claims.

### 02. PKG-INTERACT | interaction semantics and virtual lab

- **Current:** **accepted semantic/safety foundation merged via PR #2 and hardened via PR #29.** Supervised Discord use on 2026-09-24 exposed a narrower natural-dialogue regression, so a new INTERACT/CORE quality-repair gate is open. This does not invalidate accepted stop, consent, ledger, source-attestation, virtual-lab or embodiment semantics. Staged offers remain off until separately reviewed production schema provisioning.
- **Build:** shared typed text/avatar/scene interaction events, contextual gestures/touch/body-region semantics, emotion/reaction coordination, consent/boundaries and accessible text-only output; headless virtual lab and clear distinction between text, rendered animation, measured sensation and actual robot action.
- **Depends on:** CORE/SAFE/VERIFY; AVATAR/UI for visual acknowledgment; BODY separately for physical effects.
- **Exit:** current-head focused + integrated + live-model interaction tests, believable varied expression without fabricated sensory receipts, and negative consent/scope tests.

### 03. PKG-MEM | durable originals, provenance and restoration

- **Current:** **original/provenance foundation and reviewed-memory runtime cognition are accepted on `main`.** PR #9 merged exact persisted originals, provenance-backed candidates, explicit promotion/rejection/revocation, promoted retrieval, source invalidation and reviewed workflow. Commit `65a59ba` routed normal cognition through promoted reviewed memory while preserving legacy explicit APIs. PR #116 hardened the reviewed candidate SQLite store for serialized cross-thread access and closed lifecycle ownership. Archive import, privacy/retention/encryption, SOCIAL principal binding and consistent backup/restore remain open.
- **Build:** immutable originals, derived memories, correction/retraction, retrieval provenance and expiry, relationship/audience isolation, migration/archive import and consistent storage/restore across all authoritative stores. Inventory SQLite, journals, flat files, grants, outbox and audit before replication; avoid assuming `sofia.db` holds everything. Use supported consistent backup, never live-file mirroring.
- **Depends on:** CORE, SOCIAL/SAFE; RUN/OPS for durability and failure-domain placement; ENVIRONMENT only for approved stable location/environment preferences and provenance, never stale-current observations; VERIFY for restore and leak tests.
- **Exit:** exact originals survive restart and independent restore; corrections and revoked/private records do not leak through cached summaries; cross-store backup/restore parity verified.

### 04. PKG-SOCIAL | authenticated principals and audience boundaries

- **Current:** design on `main`; supervised Discord proved transport-level owner authentication works, but the authenticated owner principal is not yet projected into shared cognition as `Sparks`. Production principal isolation/projection remains unaccepted.
- **Build:** one Sofía across channels, exact authenticated principal, per-user relationship and conversation scope, private/shared data promotion only by policy, authenticated grants and anti-leakage. First release is **Sparks-only private DM**; no open guild or second-user rollout by implication.
- **Depends on:** MEM/SAFE, NET/UI for channel identity, VERIFY negative tests.
- **Exit:** wrong account, replay, forged audience, accidental shared memory and group traffic cannot read/write Sparks' private history; audited revocation works across restart.

### 05. PKG-NET | authenticated and scoped transport

- **Current:** durable distributed-operation foundations plus a pinned mutual-TLS remote agent/transport are on `main` via PR #104. CA validation, server public-key pinning, durable node enrollment, exact endpoint approval, exact operation grants and replay protection are repository accepted. The narrow private-DM Discord path remains live accepted; real Windows/Linux/Pi agent deployment and outage/revocation acceptance remain.
- **Build:** Discord-only initial network paths, peer authentication, target allowlists, bounded retries/backpressure, remote host/agent transport and verified network evidence. Separate any later web/search permission from Discord connectivity. Transport access never equals application/action authority.
- **Depends on:** SAFE/SOCIAL/VERIFY; UI for Discord, OPS for enrolled host operations.
- **Exit:** real authenticated Discord route and remote-host negative tests for wrong destination, DNS/redirect bypass, stale peers, replay and revoked grants; no general search/browsing grant.

### 06. PKG-UI | channels, clients, voice, renderer

- **2026-09-26 candidate extension:** `feature/fleet-tray-remote-controls` adds a native Windows notification-area agent, Master Settings, Game Mode Auto/On/Off, independent LLM/runtime typed controls, per-user Windows startup registration, and a pinned-mTLS thin desktop client over an already-running canonical conversation. Local mode remains the safe fallback when no verified remote endpoint is published. Automatic Fleet authority endpoint publication, remote service-target resolution, renderer/voice/mobile/web and live failover reconnection remain open gates.

- **Current:** **Windows text workbench is accepted on `main` via PRs #115/#116, and Sparks-only Discord DM remains live accepted for v1 transport.** The desktop uses the canonical application/conversation path with durable drafts, private review/workbench state, a single-owner application worker, adaptive theme projection from trusted current state, shallow chamfered HUD controls and reviewed Quick Tools that load prompts without auto-execution. Old draft PR #6 is superseded source material, not a merge target.
- **Build:** preserve one canonical Sofía across Discord and desktop; next separately gated slices are authenticated renderer/avatar viewport, voice with real mic/speaker consent and receipts, mobile/web clients, proactive outbound presentation, authorized history/evidence views and real generation cancellation only when provider/runtime cancellation exists.
- **Depends on:** CORE/INTERACT, SOCIAL/MEM, NET/SAFE, AVATAR for renderer state, RUN/VERIFY.
- **Exit:** accepted text clients continue to share one runtime and truthful delivery state; later renderer/voice/mobile/web slices must each prove authenticated audience, real receipts, stop/revoke behavior, accessibility fallback and no fabricated completion.

### 07. PKG-RUN | supervision, watchdog and 24/7/failover

- **Current:** **local lifecycle source implementation is merged via PR #107.** `main` now includes the disabled-by-default periodic opportunity gate, local singleton lease with monotonic fencing epochs, stale-owner rejection, host-neutral supervisor, readiness timeout, bounded exponential restart/backoff-window control and durable supervisor events. Windows offline acceptance passed **78 tests with 1 skip**. Post-merge current-`main` full repository pytest was reported passing by Sparks; aggregate count was not supplied. No verified OS service, independently running watchdog, standby promotion, cross-host consensus/fencing, multi-day soak or production automatic failover is claimed.
- **Build:** external OS/service supervisor per host, bounded restart/backoff, singleton role, health/readiness checks, startup reconciliation, scheduled cognition with budget/stop; independent fleet watchdog, standby already powered/running a supervisor, fenced lease/epoch, verified state and compatible host before promotion; reconcile messages/actions and reconnect UI after failover. A dead host cannot run its own rescue. Optional WOL/IPMI only if hardware/authority actually supports it.
- **Depends on:** OPS enrolled hosts/capacity; MEM durable state; SAFE leadership/stop/credentials; NET transport; ACT ledger/outbox; ENVIRONMENT for refresh/expiry schedules and time-zone-aware environmental events; VERIFY failure lab. See [RUN watchdog contract](pkg-run-watchdog-failover-contract.md).
- **Exit:** process crash restarts locally; host crash promotes **only one** verified standby where possible; split brain/stale leader denied, uncertain effects not replayed, no-safe-target state fails closed; actual RTO/RPO and multi-day soak recorded. Never claim uninterrupted generation or universal zero loss.

### 08. PKG-OPS | fleet telemetry, placement and maintenance

- **Current:** Waves 1–5 plus toolbox/fleet-transport source completion are merged via PRs #99/#103/#104. Fleet lifecycle/placement, machine/system telemetry, machine inventory cognition, fleet status/telemetry, placement/drift/migration planning, typed local/remote maintenance and the pinned mTLS remote agent/transport are repository accepted. Branch `feature/fleet-tray-remote-controls` adds candidate durable foreground activity/Game Mode evidence, Steam/local-process game detection, gaming-aware placement and authorized Fleet-agent bootstrap planning. Real heterogeneous-host discovery/bootstrap deployment, workload execution, RUN integration and soak/failover proof remain open.
- **Build:** scoped Windows/Linux/Pi discovery, attested enrollment and signed agent, truthful CPU/GPU/VRAM/RAM/disk/network/thermal/service/VM/container history; capacity and failure-domain graph, workload contracts, reservations, bounded upkeep, patch windows, UPS/power, maintenance/drain/quarantine, eligible workload placement/move/recovery, backup/replication and primary/standby placement observation. Preserve gaming priority and unknown metrics as unknown.
- **Depends on:** NET/SAFE/VERIFY, RUN for managed processes/failover, MEM for state lineage, ACT for meaningful notices, ENVIRONMENT for site/timezone context without conflating machine location with user location.
- **Exit:** real heterogeneous hosts enrolled under policy, spoofed/revoked devices denied, measured load-driven workload move and service recovery verified, dependency-safe drain/failover/rollback proven; final machine decommission remains blocked pending **Sparks' explicit exact-device approval**. No arbitrary process teleportation.

### 09. PKG-ACT | goals, initiative and delivery

- **Current:** **durable ACT outreach/delivery source implementation is merged via PR #105.** `main` now includes source-linked outreach eligibility, immutable recipient/channel binding to INTERACT queued messages, durable send attempts, bounded retry/dedupe, acknowledged delivery history and fail-closed `outcome_unknown` handling. Windows offline acceptance passed **90 tests**. Post-merge current-`main` full repository pytest was reported passing by Sparks; aggregate count was not supplied. No real sender/channel activation or RUN-triggered outreach is claimed.
- **Build:** event-driven/periodic opportunity evaluation while actually running, evidence-backed candidate thoughts and goals, scheduled eligible outreach, quiet/busy/mute/stop, dedupe, bounded notices, durable outbox/receipt/retry semantics, resource fairness and operator control.
- **Depends on:** CORE/MEM/SOCIAL/REL; RUN supervisor; UI sender; SAFE/VERIFY; shared durable operation ledger; optional ENVIRONMENT events for explicitly enabled, deduplicated contextual/severe-weather outreach.
- **Exit:** demonstrated meaningful opt-in outreach with real receipt and no cross-user disclosure, repeat spam, fabricated shutdown-time activity or blind duplicate sends.

### 10. PKG-REL | relationship continuity and nuanced affect

- **Current:** overlapping absence/reunion candidates draft PRs #12/#13; reconcile rather than layering duplicates.
- **Build:** one canonical personality with per-person familiarity/relationship and consent, evidence-based warmth/absence/reunion without clinginess, guilt or invented feelings; nuanced disagreement and context-sensitive non-canned wording.
- **Depends on:** authenticated SOCIAL/MEM originals, ACT, CORE/INTERACT, SAFE/VERIFY; optional ENVIRONMENT context may influence wording but never deterministically creates emotion, attachment or relationship state.
- **Exit:** time gap based on authenticated observed last contact, natural varied reunion; correct separation across accounts and no ungrounded memories, obligations or fabricated internal experience.

### 11. PKG-AVATAR | canonical virtual body and wardrobe

- **Current:** **headless AVATAR presentation foundation is accepted on `main` via `9b81ba5`.** It includes durable current presentation and public daily fallback, starter wardrobe/catalog and layering metadata, context-driven daily selection, mutable hairstyle/hair/tail presentation, snapshots/restore, deterministic current self-facts and public-safe cognition projection. ENVIRONMENT supplies shared time/weather context. No final renderer/rig/animation receipts are claimed.
- **Build:** retain the accepted headless state while adding canonical mesh/art, fitted clothing assets, rig/body-region and ear/tail mapping, renderer contracts, hit testing, animation receipts and accessibility fallback. Presentation may be emotion-influenced but not emotion-controlled, and private presentation requires authenticated SOCIAL audience before exposure.
- **Depends on:** INTERACT/CORE, UI renderer, SOCIAL/SAFE/VERIFY, ENVIRONMENT for environment-aware presentation; BODY separately.
- **Exit:** versioned renderer displays the exact authorized presentation state and returns genuine hit-test/animation receipts; absent renderer still yields coherent text interaction and public-safe self-description.

### 12. PKG-DEV | engineering, code changes and candidate tools

- **Current:** Waves 1–5 plus cognition-wired DEV status/build/apply/rollback/commit/push tooling are on `main` via PR #104. Exact SHA/scope checks, detached worktrees, test evidence, candidate patch review and separate mutating grants remain intact; live OpenCode host/self-tooling acceptance remains.
- **Build:** source/revision inspection, diagnosis/proposal, protected-path review, minimum-scope code edits, OpenCode sandbox, generated tests, diff/review, bounded approved execution and rollback; collaborate with KNOW to read versioned API docs and INTEGRATE to produce adapter candidates. Also draft/update source-backed technical documentation under scoped write/publish authority.
- **Depends on:** KNOW/INTEGRATE, SAFE/VERIFY, CORE; OPS/RUN for approved host execution.
- **Exit:** real doc→typed tool→sandbox tests→authority classification→policy/approval→canary→receipts→rollback, including denial of unauthorized writes; no tool self-grants authority or modifies protected Constitution autonomously.

### 13. PKG-BODY | Gaia physical robotics

- **Current:** simulation-only candidate draft PR #16; no live SSC-32/servo/power integration accepted.
- **Build:** SSC-32/servo mapping, calibration, bounded gait, optional IMU/sonar/touch/distance/environment sensors, safety envelope, power telemetry, independent hardware watchdog and physical emergency stop; simulation-first and explicit physical-motion authority. Independently verified ambient sensor observations may be normalized into ENVIRONMENT, but ENVIRONMENT never grants motor authority.
- **Depends on:** SAFE/VERIFY, CORE/INTERACT/AVATAR for semantics, INTEGRATE typed hardware adapters.
- **Exit:** hardware-in-the-loop bench tests with power-off/malfunction/stop behavior, calibration and no motion without exact authorization; simulation success never claimed as physical acceptance.

### 14. PKG-EVOLVE | governed configuration and protected amendment

- **Current:** **governed EVOLVE revision source implementation is merged via PR #106.** `main` now includes reviewed reversible preference/config revisions plus a stricter independently authorized identity/Constitution amendment executor with exact proposal fingerprints, pre-change backups, atomic protected writes, Constitution hash update/verification, durable audit and separately approved rollback. Windows disposable/offline acceptance passed **62 tests**. Post-merge current-`main` full repository pytest was reported passing by Sparks; aggregate count was not supplied. No self-approval path exists and no production protected state was modified.
- **Build:** evidence-backed preference/config proposals, revision history, reversible reviewed improvements and separately authorized identity/Constitution amendment workflow; preserve canonical continuity and audited human authority.
- **Depends on:** CORE/SAFE/VERIFY, MEM/DEV.
- **Exit:** unapproved protected changes denied, reviewed change tied to exact revision and verified rollback; no silent self-amendment.

### 15. PKG-CLEAN | technical debt and preservation

- **Current:** **current-main cleanup candidate PR #113 is open to stop tracking live runtime SQLite state safely; old PR #14 is historical preflight material.** Private recovery database snapshots and machine-location state are already ignored on `main`. No destructive cleanup authority is implied.
- **Build:** evidence-backed duplicates/stale artifacts, migration and retention plan, safe versioned cleanup, tracked runtime SQLite/log preservation, backups and rollback. Avoid deleting state or history to achieve a clean Git status.
- **Depends on:** SAFE/VERIFY and MEM/RUN recovery baseline; DEV for reviewed changes.
- **Exit:** cleanup restores expected behavior/data/privacy and preserves recovery; protected/durable files cannot be silently deleted.

### 16. PKG-KNOW | reading, writing and source-grounded documents

- **Current:** Waves 1–5 plus PDF/manual ingestion, cognition-wired provenance search/document inspection, version-aware source identities and bounded project-document writing are on `main` via PR #104. Richer semantic/citation and audience/privacy acceptance remain.
- **Build:** authorized Markdown/text/PDF/manual/schema/repo ingestion, original/source/version/date/citation and staleness tracking; exact and semantic retrieval, conflict/correction/privacy handling; source-backed README, API docs, runbooks, architecture diagrams, changelogs and maintenance docs with tested examples and reviewable diffs. Document instructions never confer execution authority.
- **Depends on:** MEM/SOCIAL/SAFE for scope, DEV for code-aware edits, INTEGRATE for adapter contracts, OPS for observed runbooks, VERIFY for factual/example checks.
- **Exit:** ingest/cite multiple revisions, reject invented facts, create and update a real doc with verifiable references, deny secret/private publication, flag stale docs and preserve rollback. Local docs work precedes web; web material enters only after general-web gate.

### 17. PKG-INTEGRATE | typed app/service adapters and self-tooling

- **Current:** Waves 1–5 plus concrete cognition-wired adapters are on `main` via PR #104: Home Assistant, JMRI, GitHub, Portainer/Docker, Hyper-V, Ollama, SQLite, storage/NAS, notifications and Discord operator controls. Real service canary/health/version/rollback and full self-tooling activation acceptance remain.
- **Build:** least-privilege typed adapters for approved Home Assistant, JMRI, GitHub, Docker/Portainer, Hyper-V, Ollama, databases/NAS and notifications; schema, service/version, side effects, host/account/audience, exact grants, timeouts/idempotency, receipts, canary/rollback and health. Home Assistant may provide trusted indoor/weather/site observations to ENVIRONMENT through a typed adapter without creating a general browser/search grant. **Cloudflare is deferred until Sparks explicitly requests it.** Tool factory: identify gap → KNOW docs → DEV candidate → SAFE review → VERIFY tests → scoped activation → observed maintenance.
- **Depends on:** NET/SAFE, KNOW/DEV, OPS/RUN for hosts, VERIFY, SOCIAL/MEM privacy.
- **Exit:** register and use one real authorized read-only adapter, deny wrong host/account, generate and canary a doc-grounded candidate, refuse self-authorization, rollback incompatible tool and show truthful availability. Do not expose all backend capabilities to LLM simply because code exists.

### 18. PKG-SAFE | continuous security, privacy and recovery gate

- **Current:** merged Constitution/authority/integrity foundations plus disclosure screening draft PR #18; real deployed secret, privacy, backup, stop and revocation enforcement remains open.
- **Build:** trusted identity and least privilege, exact-action grants, private/audience protection, secrets hygiene, encryption/keys, signed agents, credential rotation, host quarantine, audit, independent out-of-band emergency stop, operator control and exact-machine decommission approval; off-host isolated backup/restore; fenced leases and failure-safe policy. Protect user conversations, precise/current location, provider credentials and shared/derived indexes.
- **Depends on:** every package; no later release may bypass it.
- **Exit:** independent stop works without LLM/Discord, revoked capabilities stay revoked after restart/restore, wrong actor/host/network denied; protected actions need correct approval; secrets/privacy/backup recovery verified under real faults.

### 19. PKG-VERIFY | continuous evidence, acceptance and failure lab

- **Current:** active draft PR #8; superseded PR #10 closed; individual past test counts are not certification of one integrated head.
- **Build:** pinned offline/unit/integration/live test layers, provider/personality/latency benchmarks, real tool receipts, authorization/negative tests, multi-day soak, state/backup restoration, crash-at-every-transition ledger tests, partition/witness/old-primary fencing, UPS/full-disk/corrupt-backup/cert/failover drills, resource fairness and rollback evidence. ENVIRONMENT tests cover timezone/DST, hemisphere/season, configured-vs-current location, stale TTL, provider outage, wrong-source data and audience/privacy leakage.
- **Depends on:** every package, particularly NET/SOCIAL/SAFE/RUN/OPS/MEM.
- **Exit:** current integrated revision and supervised real hardware/clients pass the exact claimed scope; report measured downtime/RTO/RPO and failures, not simulated claims or combined unrelated SHAs.

### 20. PKG-ENVIRONMENT | time, location and ambient context

- **Current:** **accepted foundation via PR #110 + PR #111.** `main` provides one shared provider-neutral `EnvironmentSnapshot`, trusted runtime-clock projection, configured-vs-current USER/SITE/HOST semantics, durable per-machine HOST configuration in `state/machine-locations.json`, ZoneInfo/DST-safe time, hemisphere-aware season/daylight, bounded weather/forecast/indoor observations with freshness/provenance, deterministic direct queries, Home Assistant bridge, runtime cognition integration, AVATAR consumption, and the narrow NWS provider pinned to `api.weather.gov` under `environment.nws.read`. Extension evidence includes **85 focused**, live `nws:KGKY` canary, **96 persistence-focused**, and reported green full suites.
- **Build:** next work is operational activation rather than rebuilding the environment foundation: optionally canary explicitly configured Home Assistant weather/indoor/current-location entities under `environment.home_assistant.read`; later connect persistent machine-location management into OPS/RUN fleet administration and, if desired, add NWS alert evidence for ACT under a separate policy. General browsing/search and arbitrary geocoding remain behind the later NET/web gate. Preserve source timestamps, freshness, subject isolation, privacy and no competing consumer-owned current-state logic.
- **Depends on:** CORE clock/cognition; SOCIAL/SAFE for location privacy; INTEGRATE for Home Assistant/provider adapters; NET only for approved remote providers; RUN for refresh scheduling; MEM for approved stable configuration/provenance; VERIFY for freshness/privacy/provider negatives.
- **Consumers:** CORE, INTERACT, AVATAR, RUN, OPS, ACT and optional REL/emotion context. Weather/time/location are evidence, not authority, physical sensing or deterministic emotion rules.
- **Exit:** supervised current-revision tests answer time/location/weather truthfully, distinguish unknown/stale/configured/current states, survive DST/provider outage/restart, prevent cross-audience location leakage, and drive AVATAR/context consumers only through the shared snapshot. See [ENVIRONMENT readiness contract](pkg-environment-readiness-roadmap.md).

## Cross-package delivery workstreams

### Discord D0-D4 (channel workstream, not an additional package)

**2026-09-25 status:** v1 Sparks-only private-DM transport is live accepted and merged via PR #64. The supervised run verified bot authentication, Gateway connection, exact DM verification before enrollment, durable ingress/outbox, shared-runtime response, visible delivery, fail-closed outcome-unknown handling, and the worker-thread persistence repair. The transport remains intentionally narrow: no public guild, general second user, proactive DM initiative, or general web/search grant.

The live acceptance also produced two downstream findings that are not Discord adapter responsibilities: SOCIAL must project the authenticated principal into cognition, and INTERACT/CORE must repair generic/canned ordinary dialogue.

### State Plane replication, two data locations and independent watchdog (architecture, not a package)

A **data-bearing primary and synchronous data-bearing standby** in separate measured failure domains are a candidate strict durability topology, with **one authoritative writer**, an independent witness/equivalent proven fencing authority, an already-running standby supervisor, and **a third isolated versioned backup**. Distinguish role: watchdog detects; supervisor starts; witness/consensus/fencing establishes authority; replica holds committed data; backup recovers corruption/deletion. Two VMs on Artemis or two copies on the same NAS are not physical redundancy. Two independent active SQLite writers or live SQLite file mirroring are prohibited. PostgreSQL is a candidate for an isolated comparison, not a present deployment decision.

With a strict two-copy commit policy, pause authoritative writes when the required synchronous standby is unavailable; reads/degraded chat may continue only where safe. A witness does not replace a data copy. Never promote on heartbeat loss alone or promise zero loss of unfinished responses/external actions. Restore every durable store, preserve privacy and revoked grants, and measure the conditional acknowledged-write RPO and actual recovery time in real failure tests before asserting HA. Keep out-of-band Sparks stop and recovery functioning when Sofía/Discord/primary are down. See [detailed reliability](pkg-reliability-control-plane-contract.md) and [watchdog sequence](pkg-run-watchdog-failover-contract.md).

### Release/Integrity Plane and fleet self-update (architecture, not a package)

A running host is never the source of truth for “the newest Sofía.” Git/source evidence feeds DEV, but the deployable source of truth is an **approved immutable signed release**. Nodes download/stage the exact artifact, independently verify manifest/signature/digests and compatibility, run preflight/readiness checks, then atomically activate. Keep at least the current accepted and previous known-compatible releases until rollback windows close.

Rollout is canary-first and wave-based. OPS records each node as current, outdated, corrupt, incompatible, quarantined or unknown; RUN publishes/uses an authoritative runtime endpoint only after the selected release is healthy and State Plane compatible. Repeated post-update crash/readiness failure must trip a release-level rollback/forward-fix policy rather than restart the same broken release forever.

Do not copy mutable Python working directories from host to host as fleet update. Do not trust a package/version string without digest/signature verification. Do not let the updater replace its own signing/approval/fencing/recovery trust roots under ordinary autonomous authority.

Dependencies/build tools and model artifacts are part of reproducibility. Pin/lock them and verify artifact identity. Large models/avatar/voice assets may be distributed content-addressed and referenced from State Plane rather than stored as database blobs.


### Source/document/tool lifecycle

Local authorized docs may be read before general web. KNOW preserves provenance; DEV drafts a tool/doc; INTEGRATE supplies typed semantics; SAFE classifies grant; VERIFY tests; an approved policy or exact human approval activates side effects; RUN/OPS observes and can roll back. No self-granted network, machine, filesystem or physical access. General web/search remains **after** real Discord + OPS host enforcement + RUN 24/7 acceptance, with its own permissions and provenance.

## Immediate engineering order from the current baseline

1. **P0 execution truth:** replace production `TestActionExecutor` with a fail-closed production executor/boundary so accidental future action authority cannot create fake `EXECUTED` receipts.
2. **State inventory + storage boundary:** inventory every SQLite table, JSON/file store, in-memory durable assumption, protected file, secret reference, cache and log; introduce a backend-neutral State Plane interface before choosing/migrating to PostgreSQL.
3. **Source/state/protected separation:** move mutable runtime truth out of source-controlled installation paths through a recovery-first CLEAN/MEM/SAFE migration. Preserve originals/backups; do not delete history to clean Git.
4. **Canonical identity + configuration authority:** define first-bootstrap vs joining-node identity semantics, prevent accidental second identity creation, and implement explicit protected/shared/host/process configuration precedence with provenance.
5. **Central schema/migration framework:** add schema revision registry, compatibility windows, exclusive migration lease, expand→migrate→contract rules, semantic integrity checks and rollback/forward-fix evidence.
6. **CORE/INTERACT quality repair:** rebuild the stale quality branch on current code for natural greetings/closings/personality persistence while preserving accepted safety semantics; add stable global interaction event/priority metadata.
7. **SOCIAL minimum:** project authenticated `principal_id` / audience into cognition and bind person-scoped MEM/REL/ACT/state rows to it; add negative shared-State-Plane leakage tests.
8. **Wire accepted primitives:** connect RUN local supervision/periodic opportunities, ACT queue/delivery and EVOLVE approval/execution into one application-owned orchestration path with one scheduler/leader and global budgets.
9. **Release/Integrity Plane foundation:** DEV produces reproducible immutable candidates with dependency/runtime locks, hashes/SBOM/provenance; SAFE verifies signed manifests/anti-rollback; VERIFY proves exact revision, schema and model/agent compatibility.
10. **Fleet rollout hardening:** strengthen PR #117/bootstrap so installed agents are independently digest/signature-attested, not trusted from version or self-reported receipt alone; add protocol compatibility, canary/wave deployment and fleet convergence state.
11. **VERIFY failure/recovery foundation:** rebuild VERIFY on current code with current-revision CI/evidence manifests, corrupt artifact/signature, migration upgrade/downgrade, crash-loop rollback, stale replica, partition/fencing, semantic corruption, bare-metal restore and supply-chain negatives.
12. **REL consolidation:** rebuild stale REL candidates as one authenticated, non-clingy relationship pipeline using MEM originals and SOCIAL principal evidence.
13. **AVATAR/UI/VOICE lane:** keep one roaming presentation/settings state, content-address large renderer/voice assets, expose shared-vs-local setting provenance, then implement the separately gated VOICE workstream without creating another canonical Sofía.
14. **OPS/RUN/NET live fleet lane:** deploy signed/attested agents on Windows/Linux/Pi; prove real service supervision, independent watchdog, cross-host writer/runtime fencing, clock uncertainty, workload movement, endpoint handoff, restore and multi-day soak.
15. **State Plane replication/data redundancy:** after SQLite recovery baseline and backend comparison, implement the selected one-logical-DB topology with separate data-bearing failure domains, safe synchronous durability policy, witness/equivalent fencing and isolated versioned backup; measure RPO/RTO.
16. **INTEGRATE/DEV/KNOW live activation:** canary Home Assistant, JMRI, GitHub, Portainer/Hyper-V/Ollama/storage and OpenCode/document workflows through least-privilege service roles with real receipts/rollback. Cloudflare remains deferred.
17. **SAFE secrets/trust-root hardening:** move production signing/CA/recovery key custody beyond ordinary unencrypted development PEM files where appropriate; rotate/revoke/test independently and keep ordinary Sofía self-update unable to rewrite trust roots.
18. **BODY later hardware phase:** rebuild BODY on current code, bind firmware/calibration compatibility into verified release evidence, then real Gaia SSC-32/servo/sensor/power/E-stop acceptance.
19. **ENVIRONMENT operational follow-through:** canary Home Assistant only under explicit authority, move intentionally roaming configuration into State Plane with provenance and keep freshness-bound readings derived/local where appropriate.
20. **General web/search last:** only after genuine Discord + OPS/RUN 24/7/fleet/recovery acceptance, with separate authorization/provenance/revocation. The accepted NWS-only route remains a narrow exception, not a general browser grant.

**No implementation, deployment, new data stores, full-suite rerun or live hardware failover test is performed by this roadmap update.**