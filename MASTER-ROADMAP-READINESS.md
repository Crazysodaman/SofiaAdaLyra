> **Fleet control-plane candidate — 2026-09-26:** branch `feature/fleet-tray-remote-controls` adds Game Mode/foreground-activity evidence, gaming-aware OPS placement, typed Fleet bootstrap planning, a native Windows tray agent, Master Settings, independent LLM/runtime controls, Windows startup registration and pinned-mTLS remote desktop chat. Status remains **branch candidate**, not current-main acceptance, until Sparks runs the focused Windows gate and supervised canaries.

> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the runtime toolbox and secure fleet-transport completion gate on top of the earlier Waves 1–5 work. Focused tool/mTLS acceptance passed **34/34**, the surrounding DEV/KNOW/INTEGRATE/OPS/system/machine regression gate passed **270/270**, and the full repository pytest suite was reported passing before merge. Source-level pinned mTLS remote transport/agent and concrete runtime adapters are now on `main`; real heterogeneous-host deployment, service canaries, RUN 24/7 supervision, workload execution/failover, restore and soak remain separately gated.

> **Audit reconciliation — 2026-09-25:** ACT #105, EVOLVE #106 and RUN #107 are merged and passed their Windows package gates plus the reported post-merge full suite. Repository review distinguishes merged package primitives from application wiring/live deployment. Immediate gaps are CORE/INTERACT natural-quality repair, SOCIAL authenticated-principal projection, MEM privacy/recovery, SAFE/CLEAN/VERIFY foundations, ACT/RUN/EVOLVE runtime wiring, and stale legacy draft branches. See [ROADMAP.md](ROADMAP.md) for the authoritative package states and [the full package roadmap](docs/development/FULL-PACKAGE-ROADMAP-2026-09-22.md) for the reconciled execution order.

> **PKG-ENVIRONMENT acceptance — 2026-09-26:** PR #110 (`766bf21e`) merged the shared environment foundation, and PR #111 (`2b753fdb`) merged the narrow NWS weather/forecast route plus persistent per-machine HOST location. NWS is pinned to HTTPS `api.weather.gov` and requires `environment.nws.read`; HOST location is durable in `state/machine-locations.json`, keyed by stable machine identity, auto-loaded at composition, and kept separate from USER/home location. Evidence includes the original **79 focused / 61 touched / 27 provenance** gates, later **85 NWS-focused**, supervised live `nws:KGKY` canary, **96 persistence-focused**, and reported green full-suite runs. Live Home Assistant canary remains optional; general browsing/search and arbitrary geocoding remain open.

> **PKG-UI acceptance — 2026-09-26:** PR #115 (`381ac9a`) merged the canonical current-main text/workbench foundation and PR #116 (`7f072861`) merged the Windows desktop workbench. The accepted UI includes canonical conversation routing, durable drafts, private workbench state, single-owner application threading, adaptive ENVIRONMENT/AVATAR/emotion theme projection, shallow chamfered HUD controls and reviewed Quick Tools. The closing Windows repair gate passed **90/90** and Sparks reported the final full repository suite passing before merge. Renderer, voice, mobile/web and real cancellation remain separate gates.

> **State/Release architecture reconciliation — 2026-09-27:** Fleet mobility, one logical shared database, and governed self-improvement are now tracked as two cross-package contracts rather than new packages. **State Plane** ownership is centered on MEM with SOCIAL/RUN/OPS/SAFE support; **Release/Integrity Plane** ownership is centered on DEV/EVOLVE with SAFE/VERIFY/OPS/RUN enforcement. Immediate gaps found by the audit include fragmented SQLite+JSON/file state, no central schema migration coordinator, source/runtime/protected-state mixing, production `TestActionExecutor`, no immutable signed whole-Sofía release manifest, no model/dependency digest pinning, insufficient independent installed-agent attestation, and no safe new-node rule preventing accidental creation of a second canonical identity.

# Sofía Ada Lyra | master readiness index

**Updated:** 2026-09-26 (America/Chicago). **Status:** documentation and implementation-state index, not evidence of deployed capability. PR #1 and the roadmap reconciliation PR #4 are merged. The package roster is now **20 packages** after adding PKG-ENVIRONMENT; watchdog and replicated-database reliability remain cross-package architecture rather than extra packages.

## Authoritative planning and acceptance documents

1. [ROADMAP.md](ROADMAP.md): canonical 20-package roster, invariant release order, package ownership and fleet/removal constraints.
2. [Full roadmap and individual package contracts](docs/development/FULL-PACKAGE-ROADMAP-2026-09-22.md): expanded 20-package scope, dependencies, current status, proposed deliverables, acceptance criteria, milestones and next engineering order.
3. [Six reliability gates and state replication](docs/development/pkg-reliability-control-plane-contract.md): recovery, operation ledger, operator stop/approval, resource fairness, failure lab, capability truth, replication/fencing/backup.
4. [Reliability implementation stages](docs/development/pkg-reliability-implementation-plan.md): recoverable SQLite baseline before any candidate database migration; staged proofs.
5. [RUN independent watchdog and standby recovery](docs/development/pkg-run-watchdog-failover-contract.md): local supervisor, independent monitor, fenced leader promotion, standby startup, rejoin and failure acceptance.
6. [PKG-ENVIRONMENT readiness](docs/development/pkg-environment-readiness-roadmap.md): shared time/location/season/daylight/weather state, provenance/freshness, consumer boundaries and staged provider activation.
7. Package-specific branch docs, PRs and revision-pinned tests: implementation evidence, not an excuse to combine unrelated test runs.

**Primary release path:** CORE → INTERACT → MEM → SOCIAL minimum Sparks-only principal/audience → Discord D0-D4 through NET + UI + SAFE → OPS trusted host telemetry/enrollment → RUN verified supervised 24/7 and applicable recovery/failover → later separately authorized general web/search.

**SAFE + VERIFY are continuous gates.** KNOW/INTEGRATE/REL/ACT/AVATAR/DEV/BODY/EVOLVE/CLEAN/ENVIRONMENT can proceed in parallel without bypassing release, privacy or authority gates. ENVIRONMENT's shared foundation and the separately authorized narrow NWS route are accepted; trusted local Home Assistant observations may enter through INTEGRATE. General browsing/search and arbitrary geocoding remain behind separate NET/web authorization. Reading local authorized documentation does not grant web browsing. Discord connectivity is not a general web grant.

## Status definitions

- **Merged foundation:** code is on `main`, but real-host or integrated acceptance may remain.
- **Draft candidate:** code is on a feature branch/PR, not merged to `main`.
- **Design-only:** a documented outcome/contract, with no certified corresponding deployed behavior.
- **Offline tested:** a particular isolated revision passed; not proof of current Windows/full-suite/live behavior.
- **Integrated:** tested against the actual intended repository revision and dependencies.
- **Live accepted:** witnessed real component/system behavior at a pinned revision with appropriate receipts.
- **Released/deployed:** separately approved activation/deployment, distinct from merged docs or source.

Never combine test counts from unrelated revisions into a fictional mega-pass. Reconfirm actual PR heads, CI and live evidence before changing these states.

## State Plane + Release/Integrity Plane readiness

These are **architecture workstreams across the existing 20 packages**, not new package numbers.

### State Plane

**Goal:** one logical authoritative Sofía state shared by eligible runtimes, with strict ownership and least privilege.

- **CORE:** canonical identity bootstrap and configuration precedence. A new/rebuilt node must verify/join the existing Sofía identity, never silently mint a replacement identity because a local file is missing.
- **MEM:** backend-neutral storage boundary, authoritative-state inventory, shared database semantics, schema/version migration and cross-store consistency.
- **SOCIAL:** principal/audience ownership on all person-scoped state.
- **RUN:** single writer/runtime leadership, global event ordering, monotonic fencing, safe degraded/offline behavior and fleet-wide background budgets.
- **OPS:** placement of data-bearing nodes, replica health, convergence, machine state and workload locality.
- **SAFE:** per-service database roles, secrets isolation, trust roots, revocations, protected state and out-of-band recovery.
- **CLEAN:** separate source-controlled installation files from mutable runtime/protected/cache/log state and preserve migration/rollback.
- **VERIFY:** restore, corruption, stale-replica, partition, migration compatibility and bare-metal recovery evidence.
- **UI/ENVIRONMENT/AVATAR/KNOW/ACT/REL:** migrate only their authoritative roaming state; keep caches, device handles and large immutable assets out of transactional state where appropriate.

**State classes:** shared authoritative state; protected trust state; secrets; immutable/content-addressed artifacts; local ephemeral/rebuildable observations.

### Release/Integrity Plane

**Goal:** Sofía improves herself by producing and deploying an exact verified release, never by propagating whichever mutable working tree happens to be on a host.

- **DEV:** isolated candidate build, dependency/runtime lock, hashes, provenance/SBOM and reproducibility.
- **EVOLVE:** governed proposal/revision lineage and separately protected amendments.
- **SAFE:** release-signing trust, anti-rollback policy, protected verifier/emergency-stop/fencing/recovery roots and approval tiers.
- **VERIFY:** exact-revision tests, migration/rollback compatibility, corrupt-artifact/supply-chain negatives and release evidence.
- **OPS:** canary/wave rollout, installed-agent independent attestation, fleet release convergence and corrupt/outdated/incompatible quarantine.
- **RUN:** activation, health/readiness, crash-loop detection, release rollback/forward-fix and authoritative endpoint handoff.
- **NET:** compatible authenticated transport/protocol negotiation; transport trust never becomes release or database authority.
- **CORE/UI/AVATAR:** model/client/asset compatibility is bound into the release manifest rather than inferred from a friendly version string.

**Minimum release manifest:** release ID, Git revision, application/package version, runtime version, dependency lock digest, database schema compatibility, Fleet protocol/agent compatibility, model/provider identity and artifact digest where available, Constitution/protected-state compatibility, config schema, asset digests and signature.


## Fleet/self-update hardening checklist

The following reliability requirements are explicit roadmap gates, not optional implementation details:

- **Automatic bad-release rollback:** repeated post-update crash/readiness failure escalates from process restart to release rollback or controlled forward-fix.
- **Fleet protocol compatibility:** CORE/runtime, Fleet agent and remote control protocol versions must be checked before either side is activated.
- **Control-agent independence:** the small Fleet supervisor/control agent is separately versioned and independently updateable/rollbackable so a bad Sofía release cannot disable its own recovery path.
- **Semantic corruption checks:** verify domain invariants, not just SQLite/SQL structural integrity. Examples include valid memory provenance, principal ownership, grant/revocation consistency, conversation/session references and deployment lineage.
- **Append-only audit evidence:** approvals, protected changes, releases, migrations, fencing transitions, emergency stops and decommission decisions use tamper-evident append-only history; corrections append rather than overwrite.
- **Large-asset separation:** LLM weights, avatar/voice/render assets, generated artifacts and backups are content-addressed objects/files with verified hashes referenced by State Plane metadata rather than bloating transactional database rows.
- **Bare-metal recovery:** documented clean-host recovery must work with every normal Sofía runtime unavailable.
- **Offline/degraded behavior:** State Plane loss may allow clearly marked local drafts/read-only degraded behavior, but must not create competing authoritative memories, grants, actions, deployments or protected revisions.
- **Global autonomy budget:** quotas and background-work budgets are Fleet-wide so adding workers does not multiply autonomous activity.
- **Supply-chain verification:** dependency/runtime locks, artifact hashes, provenance, vulnerability/security checks and SBOM evidence are part of release acceptance.
- **Garbage collection/retention:** old releases, models/assets, backups, logs, snapshots and evidence have explicit retention/GC policy that preserves rollback, legal/privacy requirements and forensic history.
- **Database constraints:** the future authoritative relational schema uses foreign keys, uniqueness/idempotency, ownership/audience constraints, guarded append-only records, valid state transitions and transactional boundaries where the domain requires them.


## Per-package readiness and immediate next gate

| Order | Package | Current evidence-based location/status | Next gate |
| ---: | --- | --- | --- |
| 1 | CORE | Foundations merged via PR #1 | Joint INTERACT/CORE live-quality repair for generic assistant fallback, then fresh integrated identity/personality/restart/latency evidence. |
| 2 | INTERACT | **Accepted foundation merged via PR #2 plus accepted hardening via PR #29** | New narrow live-quality repair gate with CORE for natural/non-canned dialogue; accepted interaction safety/ledger semantics remain closed. |
| 3 | MEM | **Accepted original/provenance foundation plus promoted-memory runtime cognition wiring on `main`**; reviewed candidate store is thread-safe and lifecycle-clean after PR #116 | ChatGPT/archive import, privacy/retention/encryption, SOCIAL principal binding, consistent cross-store backup and independent restore. |
| 4 | SOCIAL | Minimum principal/audience boundary designed; live Discord proved transport auth but missing cognition projection | Project the authenticated owner as Sparks in shared cognition and add negative cross-user/audience leakage tests. |
| 5 | NET | Durable admission foundations plus pinned mutual-TLS remote transport/agent source merged via PR #104; narrow Discord DM transport remains live accepted | Deploy the remote agent to real Windows/Linux/Pi hosts and prove endpoint/key/revocation/outage behavior; no general web. |
| 6 | UI | **Windows text workbench accepted via PRs #115/#116; Sparks-only Discord DM adapter live accepted for v1 transport** | Extend only through separately gated renderer/avatar viewport, voice, mobile/web, proactive outbound and real cancellation; preserve canonical shared runtime. |
| 7 | RUN | **Local lifecycle implementation merged via PR #107:** periodic opportunity gate, local singleton lease/fencing epochs, stale-owner rejection, host-neutral supervisor, readiness timeout and bounded restart policy; Windows offline gate **78 passed, 1 skipped**. Post-merge current-`main` full repository pytest was reported passing by Sparks. | Install/prove real OS supervision and independent watchdog; safe standby startup, cross-host exclusive leadership/fencing, ledger reconciliation, multi-day soak and measured host-failover/RTO/RPO proof. |
| 8 | OPS | **Waves 1–5 plus toolbox/fleet-transport source completion merged via PRs #99/#103/#104.** Branch `feature/fleet-tray-remote-controls` adds candidate durable activity/Game Mode evidence, gaming-aware placement and typed authorized Fleet-agent bootstrap planning. | Run focused Windows acceptance, then deploy discovery/bootstrap across real Windows/Linux/Pi hosts; verify maintenance, workload movement, RUN integration, failover/rollback, restore and soak. |
| 9 | ACT | **Durable outreach/delivery source merged via PR #105:** source-linked policy, exact envelope binding, attempt ledger, bounded retry/dedupe, acknowledged receipts and `outcome_unknown` handling; Windows offline gate **90 passed**. Post-merge current-`main` full repository pytest was reported passing by Sparks. | Activate a real authorized sender/channel and RUN scheduling; prove recipient isolation, receipt reconciliation and no duplicate/unsolicited spam under live faults. |
| 10 | REL | Overlapping absence/reunion candidates draft PRs #12/#13 | Reconcile one evidence-grounded, scoped and non-clingy relationship pipeline. |
| 11 | AVATAR | **Headless presentation/wardrobe foundation accepted on `main` via `9b81ba5`**, with durable public-safe presentation and deterministic current self-facts | Final mesh/art, rig/renderer/hit-test/animation receipts, authenticated private audience via SOCIAL and visual acceptance. |
| 12 | DEV | **Waves 1–5 plus cognition-wired DEV status/build/apply/rollback/commit/push tooling merged via PR #104.** Repository acceptance is green; mutating verbs remain separately authorized. | Live OpenCode execution on the intended host plus end-to-end KNOW→DEV→VERIFY candidate-tool acceptance; consequential publish/deploy/restart remains separately gated. |
| 13 | BODY | Simulation-only candidate draft PR #16 | Real Gaia SSC-32/calibration and independently verified hardware emergency stop. |
| 14 | EVOLVE | **Governed revision implementation merged via PR #106:** reversible preference/config changes plus independently approved protected identity/Constitution apply/rollback; Windows disposable/offline gate **62 passed**. Post-merge current-`main` full repository pytest was reported passing by Sparks. | Integrate with final SAFE approval/authentication mechanisms and VERIFY evidence; preserve no-self-approval and exact-revision rollback guarantees. |
| 15 | CLEAN | **Current-main cleanup candidate PR #113 is open for live SQLite tracking/state hygiene; old PR #14 is historical preflight** | Recovery-first state migration, verified backup/restore, safe untracking/ignore rules and rollback without deleting durable history. |
| 16 | KNOW | **Waves 1–5 plus PDF/manual ingestion, cognition-wired provenance search/document inspection, version-aware identities and bounded document writing merged via PR #104.** | Richer semantic retrieval/citation ranges, audience/privacy integration and live documentation-authoring/upkeep acceptance. |
| 17 | INTEGRATE | **Waves 1–5 plus concrete runtime adapters merged via PR #104:** Home Assistant, JMRI, GitHub, Portainer/Docker, Hyper-V, Ollama, SQLite, storage/NAS, notifications and Discord operator controls. Cloudflare is deferred until Sparks explicitly requests it. | Canary real configured services, prove destination/account scope, health/version behavior and rollback; then complete KNOW→DEV→SAFE/VERIFY→activation proof. |
| 20 | ENVIRONMENT | **Accepted foundation via PR #110 + PR #111.** Shared clock/environment projection, configured/current USER/SITE/HOST evidence, persistent per-machine HOST location, timezone/DST, season/daylight, provider-neutral weather/forecast/indoor observations, deterministic queries, HA bridge, AVATAR consumption and the narrow NWS route pinned to `api.weather.gov` under `environment.nws.read` are on `main`; supervised live NWS acceptance passed. | Optional live Home Assistant canary after explicit `environment.home_assistant.read`; later general browsing/search, arbitrary geocoding, NWS alert→ACT delivery, and fleet-managed location replication remain separate gates. |
| Gate | SAFE | Authority/integrity foundations; disclosure preflight draft PR #18 | Real identity, secrets, revocation, independent stop, backups/restore, fencing and protected exact-device approvals. |
| Gate | VERIFY | Active candidate draft PR #8; PR #10 superseded | Current-revision live negative/security and failure tests, integrated suite, restore, latency, RPO/RTO and soak evidence. |

## 2026-09-27 package assignment additions

| Package | Newly assigned/strengthened responsibility from audit |
| --- | --- |
| **CORE** | Canonical Fleet identity bootstrap; configuration precedence/provenance; adaptive cognition remains separate from host identity. |
| **INTERACT** | Global interaction causation/correlation metadata and foreground priority semantics consumed by RUN. |
| **MEM** | State Plane abstraction, schema migration, semantic integrity, one logical shared state and recovery consistency. |
| **SOCIAL** | Principal/audience ownership for shared rows, caches, memories and relationship state. |
| **NET** | Protocol compatibility and authenticated transport only; no implicit database or release authority. |
| **UI** | Shared settings backed by authoritative configuration, explicit local overrides, offline queue/degraded behavior, voice remains a later UI workstream. |
| **RUN** | Cross-host leader/writer fencing, clock uncertainty, global event ordering, crash-loop release rollback and fleet-wide autonomy budgets. |
| **OPS** | Canary rollout, fleet convergence, independently verified installed-agent identity, artifact distribution and content-addressed asset availability. |
| **ACT** | Fleet-wide rather than per-worker outreach budgets; durable causation/idempotency against shared state. |
| **REL** | Relationship state is principal-bound and migrates through the State Plane, not machine-local files. |
| **AVATAR** | Roaming presentation metadata in State Plane; large renderer/assets content-addressed and digest-verified. |
| **DEV** | Reproducible candidate releases, dependency locks, build/runtime provenance and immutable artifact generation. |
| **BODY** | Physical controller firmware/calibration compatibility becomes a separately verified release/asset dependency before motion. |
| **EVOLVE** | Self-improvement terminates in a governed release proposal; higher-trust verification/signing/fencing roots remain independently controlled. |
| **CLEAN** | Separate source, runtime state, protected state, secrets, cache and logs; retire direct source-tree mutation assumptions. |
| **KNOW** | Knowledge metadata/provenance may roam in State Plane; large/rebuildable indexes can remain derived/content-addressed. |
| **INTEGRATE** | Typed State Plane/database adapters and least-privilege service roles; no generic shared DB credential. |
| **SAFE** | Trust anchors, signing keys, secrets custody, anti-rollback, tamper-evident audit, protected execution base and bare-metal recovery. |
| **VERIFY** | Upgrade/downgrade/migration tests, signature/supply-chain negatives, semantic DB integrity, corruption/failover/restore and convergence proof. |
| **ENVIRONMENT** | Shared configured environment state with provenance; current observations/caches stay freshness-bound and may remain local/derived. |


## Named workstreams, not extra packages

- **Discord D0-D4:** initial scope is authenticated Sparks-only private DM; no public guild/multi-user access implied. See [full roadmap](docs/development/FULL-PACKAGE-ROADMAP-2026-09-22.md).
- **Two data locations:** proposed single writer plus synchronous data-bearing standby on independently verified failure domains, a separate quorum/fencing witness and third isolated/versioned backup. SQLite first gets state inventory, safe consistent backups and independent restore; PostgreSQL is only one future candidate after benchmark, migration, and separate activation approval. Synchronous replication does not protect against replicated deletion/corruption.
- **Watchdog and standby:** local supervisor restarts local process; independent fleet monitor detects host failure; compatible standby supervisor starts a replacement only after exclusive leader fencing and durable-state validation. If exclusivity, quorum or data is uncertain, fail closed rather than boot two leaders. A witness is not a data copy. Two VMs on Artemis are not independent physical failure domains.
- **Operator authority:** Sparks can independently stop automation, pin hosts/workloads and prohibit reboots. Sofía may quarantine/drain/prepare a machine, but **only Sparks explicitly approves final removal of that exact device and proposal revision**.
- **General web/search:** only after genuine Discord, OPS deployment-host and RUN 24/7 acceptance, with distinct authorization and provenance. PR #111 is an explicitly authorized narrow exception for NWS weather/forecast only, pinned to `api.weather.gov` and `environment.nws.read`; it is not general browsing/search or arbitrary geocoding. Trusted local Home Assistant environment observations remain separately consumable through INTEGRATE/ENVIRONMENT.

## Reconciliation notes

- PR #103 merged on 2026-09-25 at `0cc067a`, integrating DEV/KNOW/INTEGRATE/OPS Waves 2–5 after 60/60 focused acceptance and a reported passing full repository suite. Source implementation is accepted; live NET/RUN deployment/failover claims remain open.

- PR #1 merged on 2026-09-20; older documents still describing it as open are historical.
- PR #2 merged on 2026-09-23 after Windows closure evidence: 97 focused, disposable real-Qwen four-turn pass, qualified repository 1665 passed / 2 skipped / 1 unrelated local test deselected, and final 60/60 closure audit.
- REL PRs #12/#13 overlap; reconcile them before merging both paths.
- VERIFY PR #8 is active; #10 is superseded/closed.
- PKG-ENVIRONMENT is package #20. Discord and watchdog/replication remain cross-package workstreams, **not packages #21/#22**.
- Runtime SQLite files and logs tracked by Git must be preserved and deliberately migrated under SAFE/CLEAN; never delete state just to tidy Git.

**A roadmap, unit test, mock transport, model statement or documentation-only merge is not proof of 24/7 operation, standby promotion, acknowledged-write RPO 0, or deployed high availability.**