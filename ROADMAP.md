> **Fleet Live Node 1 candidate — 2026-09-26:** branch `feature/fleet-tray-remote-controls` now includes file-configured pinned-mTLS Fleet-agent startup, an operator-facing durable authenticated Fleet probe, and normalized read-only `ops.telemetry/latest` collection. Artemis is the first planned real remote node. Local source tests and supervised Artemis mTLS/inspection/telemetry acceptance remain required before calling Fleet deployment live.

> **Fleet/tray/remote-client candidate — 2026-09-26:** branch `feature/fleet-tray-remote-controls` adds durable host activity/Game Mode evidence, Steam/local-process game detection, activity-aware placement, authorized Fleet-agent bootstrap planning, a native Windows notification-area control surface, Master Settings, independent LLM/runtime controls, Windows startup registration, and pinned-mTLS remote desktop chat over the canonical conversation service. This is **candidate source only** until Sparks runs the focused Windows gate and supervised tray/remote-client canaries. It does not yet prove automatic LAN discovery, real cross-host service control, runtime migration, or automatic authoritative-endpoint publication.

> **State/Release architecture audit — 2026-09-27:** cross-chat + current-code review found that Fleet mobility and self-improvement need two explicit cross-package control planes, **not new packages**: one logical **Sofía State Plane** and one **Release/Integrity Plane**. Current state is still split across SQLite plus identity/personality/avatar/knowledge/machine-location/Constitution files; production composition still uses `TestActionExecutor`; schema migration is decentralized; installed-agent/version checks and self-update artifacts need stronger independent attestation; and release/model/dependency identity is not yet immutable. The roadmap now assigns these gaps to the existing packages below. No PostgreSQL migration, release signer, or production deployment is claimed by this documentation update.

> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the runtime toolbox and secure fleet-transport completion gate on top of the earlier Waves 1–5 work. Focused tool/mTLS acceptance passed **34/34**, the surrounding DEV/KNOW/INTEGRATE/OPS/system/machine regression gate passed **270/270**, and the full repository pytest suite was reported passing before merge. Source-level pinned mTLS remote transport/agent and concrete runtime adapters are now on `main`; real heterogeneous-host deployment, service canaries, RUN 24/7 supervision, workload execution/failover, restore and soak remain separately gated.

> **Project status update — 2026-09-25 (late):** PRs #105 (ACT), #106 (EVOLVE), and #107 (RUN local lifecycle) are merged. Their Windows package gates passed **90**, **62**, and **78 passed / 1 skipped** respectively, and Sparks reported the post-merge current-`main` full pytest suite passing. Repository audit at `13046c2` found **299 Python source files**, **246 Python test files**, and **59 Git branches**. The new ACT/RUN/EVOLVE primitives are not yet wired into the normal application/composition path. SOCIAL principal projection remains absent from `CognitiveContext`. Eleven legacy draft PRs were initially open and all were roughly 330 commits behind `main`; obsolete Discord preflight PR #5 has now been closed as superseded by merged/live-accepted PR #64.

> **PKG-ENVIRONMENT acceptance — 2026-09-26:** PR #110 merged to `main` at `766bf21e`. The shared provider-neutral environment snapshot, configured/current location evidence, timezone/DST handling, season/daylight, bounded weather/forecast/indoor observations, deterministic direct queries, Home Assistant bridge authorization boundary, cognition projection and AVATAR adapter are repository accepted. Windows gates passed **79 focused**, **61 touched-regression**, and **27 provenance-regression** tests; Sparks also reported green full-suite runs before and after the final provenance repair. Supervised live Ollama checks passed. Live Home Assistant canary and direct internet weather/geocoding remain separately gated.

> **PKG-ENVIRONMENT NWS + persistent HOST acceptance — 2026-09-26:** PR #111 merged to `main` at `2b753fdb`. The narrow National Weather Service path is pinned to HTTPS `api.weather.gov`, requires `environment.nws.read`, normalizes current station weather plus bounded forecast into the shared snapshot, and preserves USER/home separately from HOST/server location. HOST configuration is now durable Sofía state in `state/machine-locations.json`, keyed by stable discovered machine ID; machine inventory exposes bounded location metadata without coordinates, composition auto-loads the current host record, and process-local HOST variables remain an explicit override. Acceptance evidence: **85 focused**, reported green full suite, supervised live NWS canary against `nws:KGKY`, then **96 final persistence-focused** tests and a final reported green full suite. General browsing/search and arbitrary geocoding remain closed.

> **PKG-UI acceptance + integration repair — 2026-09-26:** PR #115 merged the current-main text/workbench foundation at `381ac9a`; PR #116 merged the Windows desktop workbench and adaptive theme at `7f072861`. The accepted desktop uses the canonical `SofiaApplication`/conversation path, durable unsent drafts, a single-owner application worker, adaptive ENVIRONMENT/AVATAR/emotion theming, chamfered HUD surfaces and reviewed Quick Tools that load prompts without auto-execution. Acceptance included the earlier **58 UI + 24 application/Discord** gates, later **37 focused UI/AVATAR**, a **90/90 integration-repair gate**, supervised Windows launch/use, and a final reported green full repository suite. The repair work also hardened reviewed-memory SQLite thread ownership/cleanup, explicit request-level tool suppression for trusted interaction turns, scoped `codebase.inspect` authorization, and continuity fixture expectations. Voice, renderer/avatar viewport, mobile/web clients and real provider cancellation remain separate future UI slices.

# Sofía Ada Lyra: 20-package delivery roadmap

**Planning revision:** 2026-09-26 (America/Chicago). **Status:** roadmap documentation on `main`; package implementation and deployment remain separately gated. PR #1 (CORE), roadmap reconciliation PR #4, PR #2 (INTERACT), and PR #29 (INTERACT post-merge hardening) are merged. PKG-DISCORD v1 passed supervised live owner-DM transport acceptance and merged to `main` via PR #64 (`ba2111b`). INTERACT remains accepted as the semantic/safety foundation, with a new narrow INTERACT/CORE quality-repair gate opened for generic/canned live dialogue. The roadmap now contains **20 packages**. PKG-ENVIRONMENT is package #20; Discord remains a cross-package workstream rather than a separate package.

> **Core invariant:** Sofía's canonical identity, Constitution, represented embodiment, evidence, memory, authority, and capabilities remain independent of replaceable models, hosts, processes, clients, Discord, voices, avatars, and robots. Model output is never proof of authorization, sensing, execution, delivery, or subjective experience.

## Delivery order

The primary dependency path is:

**CORE → INTERACT → MEM → SOCIAL minimum identity/audience boundary → Discord D0–D4 using NET + UI + SAFE → OPS minimum fleet telemetry/enrollment → RUN verified 24/7 operation → later separately authorized general web/search.**

After MEM, package work that does not bypass those release gates may proceed in parallel. In particular, OPS may mature fleet diagnostics and trusted enrollment; KNOW may mature local/document knowledge; INTEGRATE may mature typed adapters; REL and ACT may mature absence, initiative, and outreach; AVATAR may continue offline asset work; DEV, BODY, EVOLVE, and CLEAN remain separately gated. **ENVIRONMENT's offline foundation plus the separately authorized narrow NWS weather/forecast route are accepted on `main`; trusted local Home Assistant observations may feed it through INTEGRATE after explicit authorization. General browsing/search and arbitrary geocoding remain behind their later NET/web gate.**

**SAFE and VERIFY are continuous gates across every stage rather than late sequential packages.**

General internet/search is deliberately **not** part of the initial Discord NET scope. Discord connectivity does not grant browser/search access.

## State and release architecture | package ownership

These are **cross-package contracts, not packages #21/#22**.

**Sofía State Plane** means one logical authoritative state across all execution hosts, with one safe writer/leader policy, typed ownership, versioned schema, authenticated principals, backups and restore. It does **not** mean every node receives unrestricted database credentials. Machine-local caches, PIDs, device handles, downloaded models and similar ephemeral data remain local. Secrets/private keys remain outside the general shared state database.

**Release/Integrity Plane** means self-improvement produces an immutable, reviewable release artifact rather than editing whichever host is currently running Sofía. A release binds exact code, dependency/runtime versions, database compatibility, protocol versions, model/artifact digests, protected-state compatibility and signatures; OPS/RUN then canary, verify, converge or roll back the fleet.

| Concern found in audit | Primary package owner | Supporting packages | Required roadmap outcome |
| --- | --- | --- | --- |
| Canonical identity on a new/rebuilt host | **CORE** | SAFE, MEM, RUN | A joining node retrieves/verifies the existing canonical identity; loss of a local identity file must never create a second Sofía. |
| One logical shared authoritative state | **MEM** | SOCIAL, RUN, OPS, SAFE | Introduce a backend-neutral State Plane/storage boundary and inventory/migrate every authoritative SQLite/JSON/file store deliberately. |
| Principal/audience ownership inside shared state | **SOCIAL** | MEM, SAFE | Every person-scoped record is bound to an authenticated principal/audience; no cross-user leakage through shared storage or caches. |
| Schema/version migrations and backward-compatible rollback | **MEM** | VERIFY, CLEAN, RUN | Central schema versioning plus expand→migrate→contract compatibility; old releases may not start against unsupported schemas. |
| Runtime/protected/source/cache/log separation | **CLEAN** | MEM, SAFE, DEV | Stop mixing mutable runtime truth with source-controlled installation files; document retention and ownership for every class. |
| Secrets, DB roles and trust roots | **SAFE** | NET, OPS, INTEGRATE | Least-privilege per-service credentials; signing keys/CA private keys/operator approval roots stay outside ordinary self-modification and shared DB access. |
| Cross-host leadership, time/fencing and event ordering | **RUN** | OPS, SAFE, MEM | One authoritative runtime/write leader, monotonic fencing, clock/lease uncertainty handling, global foreground-before-background ordering and no split brain. |
| Fleet deployment, convergence and agent attestation | **OPS** | RUN, NET, SAFE, VERIFY | Verify installed agent/artifact identity independently; roll out exact releases by canary/waves and report current/outdated/corrupt/incompatible/quarantined nodes. |
| Reproducible candidate build | **DEV** | KNOW, VERIFY, SAFE | Lock dependencies/build runtime, capture hashes/SBOM/provenance and build immutable candidates instead of copying mutable working trees. |
| Governed self-change | **EVOLVE** | DEV, SAFE, VERIFY | Sofía may propose/test changes, but protected verifier/signing/approval/fencing/recovery roots require a higher independently authorized tier. |
| Release signature, anti-rollback and supply-chain policy | **SAFE** | DEV, VERIFY, OPS | Verify signatures and allowed release lineage before activation; compromised or unsigned artifacts fail closed. |
| Release/migration/failure evidence | **VERIFY** | every package | Test upgrade/downgrade compatibility, corrupt artifacts, bad migrations, stale replicas, protocol mismatch, rollback, bare-metal restore and current-revision fleet convergence. |
| Global autonomy/resource budgets | **RUN** | ACT, OPS, CORE | Budgets are fleet-wide, not multiplied independently per worker; live Sparks interaction outranks optional background work. |
| Large model/avatar/voice/assets | **OPS** | UI, AVATAR, CORE, VERIFY | Keep large immutable assets content-addressed outside transactional rows where appropriate; State Plane stores identity/digest/location/availability. |
| Configuration source of truth | **CORE** | SAFE, OPS, UI, ENVIRONMENT | Define precedence and provenance for protected policy → shared config → approved host override → process/bootstrap override; settings must not silently diverge by host. |
| Tamper-evident work/deployment audit | **SAFE** | ACT, RUN, OPS, DEV, EVOLVE | Protected approvals/releases/actions get durable immutable IDs, causation/correlation, exact revision/grant and receipts; uncertain effects remain uncertain. |
| Bare-metal/operator recovery | **SAFE** | VERIFY, RUN, OPS, MEM | Rebuild from clean hardware using independently held recovery credentials, verify identity/state/release, then deliberately resume authority. |

### Mandatory State Plane classes

Every persistent datum must be classified before migration:

- **shared authoritative state:** conversations, reviewed memories, principal relationships, fleet inventory, runtime leases, jobs/outbox, approvals, deployment records and roaming presentation/configuration where policy permits;
- **protected state/trust anchors:** Constitution/identity authority roots, release-signing trust, approval verifier configuration, fencing/recovery policy and revocations;
- **secrets:** tokens, private keys and credentials referenced by ID/scope but not exposed as ordinary shared records;
- **immutable/content-addressed artifacts:** application releases, model files, avatar/voice assets, migration bundles and evidence;
- **local ephemeral state:** PID/device handles, caches, temporary downloads, current GPU/process samples and other rebuildable host-local observations.

A shared database must expose **least-privilege service roles**, not a universal Fleet password. A remote agent that can report CPU load must not thereby gain permission to rewrite memories, approvals or protected identity.

### Mandatory Release/Integrity Plane flow

**proposal → isolated DEV change → VERIFY → SAFE policy/approval → immutable build → signed manifest → canary → health/data compatibility check → staged Fleet rollout → convergence proof → rollback/forward-fix if required.**

The manifest must bind at minimum: release ID, Git revision, package/application version, Python/runtime version, dependency lock digest, database schema compatibility, Fleet protocol/agent compatibility, provider/model identity and digest where available, Constitution/protected-state compatibility, configuration schema, asset digests and release signature.

The updater may not silently modify its own trust root. Release signature verification, root signing keys, independent operator approval, emergency stop, fencing, rollback/recovery boot path and protected-state verification are **higher-trust SAFE surfaces**. Sofía may propose changes to them; normal autonomous self-update may not self-authorize them.


## Ordered package roster

| Order | Package | Outcome | Current evidence-based state / next gate |
| ---: | --- | --- | --- |
| 1 | **PKG-CORE · Cognition and continuity** | Grounded identity/personality, startup/restart awareness, response performance, adaptive reasoning | Foundations merged in PR #1. A new joint INTERACT/CORE live-quality repair gate is open after Discord exposed generic assistant fallback in ordinary dialogue; identity/personality/latency review remains part of that gate. |
| 2 | **PKG-INTERACT · Text/avatar/screen interaction** | Shared canonical whole-body interaction semantics, contextual reactions, virtual lab, truthful expression | **Accepted semantic/safety foundation via PR #2 and PR #29.** A narrow live-quality repair gate is reopened with CORE because Discord exposed generic/canned wording in ordinary greetings. Existing interaction-policy, stop, ledger, source-attestation and embodiment acceptance remains intact. Staged offers remain disabled pending separate schema provisioning. |
| 3 | **PKG-MEM · Durable memory and learning** | Preserved originals, provenance-aware retrieval, correction, reviewed durable preferences, archive migration | **Accepted original/provenance foundation plus runtime cognition wiring.** PR #9 merged exact persisted originals, provenance-backed candidates, promotion/rejection/revocation, promoted retrieval and source invalidation; `65a59ba` then wired normal cognition to promoted reviewed memories while preserving legacy explicit APIs. PR #116 additionally hardened reviewed-memory SQLite cross-thread access and lifecycle cleanup. Archive import, retention/erasure/encryption policy, SOCIAL principal binding, consistent backup/restore and live cognition-quality acceptance remain. |
| 4 | **PKG-SOCIAL · Principal, audience, and isolation** | One Sofía across people/channels with authenticated principals, per-user relationship state, private/shared scopes, no cross-user leakage | **Primary coding gap.** Discord authenticates the exact enrolled owner, but `CognitiveContext` has no principal/audience field and the normal conversation path therefore does not project the authenticated owner as `Sparks`. No dedicated SOCIAL runtime package is on `main`. Implement one shared principal projection plus negative audience/isolation tests; general second-user/multi-user rollout stays deferred. |
| 5 | **PKG-NET · Scoped networking and distributed operation** | Authenticated network routes and bounded remote capabilities | **Durable admission plus pinned mutual-TLS remote agent/transport are on `main` via PRs #11/#104.** CA validation, server public-key pinning, mutual TLS, durable node enrollment, exact endpoint approval, exact operation grants and replay protection are repository accepted. Real Windows/Linux/Pi deployment and outage/revocation acceptance remain. No general web/search grant. |
| 6 | **PKG-UI · Clients, Discord adapter, voice, and workbench** | Authenticated interfaces to the same Sofía, delivery/renderer acknowledgments, accessible text fallback | **Windows text workbench accepted on `main` via PRs #115/#116; Sparks-only Discord DM remains live accepted for v1 transport.** Branch `feature/fleet-tray-remote-controls` now carries a candidate Windows notification-area agent, master settings console, independent LLM/runtime controls, Game Mode Auto/On/Off, per-user startup registration, and a pinned-mTLS thin desktop client that can connect to an already-running remote canonical conversation. These additions remain branch-candidate until focused Windows acceptance passes. Voice, renderer/avatar viewport, mobile/web clients, automatic Fleet endpoint publication and real generation cancellation remain separately gated. |
| 7 | **PKG-RUN · 24/7 lifecycle and supervision** | External service supervision, single active instance, restart/backoff, bounded periodic cognition, health/recovery | **Repository primitives accepted via PR #107.** `main` has bounded periodic opportunities, local singleton lease/fencing epochs, stale-owner rejection, host-neutral supervisor, readiness timeout, restart backoff/window limits and durable supervisor events; Windows gate **78 passed / 1 skipped**, followed by a reported green full suite. **Not yet wired into `SofiaApplication`/composition and not an installed OS service.** Independent watchdog, cross-host leadership/fencing, standby/failover, RTO/RPO and soak remain open. |
| 8 | **PKG-OPS · Fleet operations, diagnostics, performance, and orchestration** | Cross-platform telemetry, trusted zero-touch enrollment/decommissioning, autonomous upkeep, configuration drift, workload placement/failover, and bounded maintenance | **Strong source foundation on `main` via PRs #99/#103/#104.** Branch `feature/fleet-tray-remote-controls` adds a Fleet control-plane candidate: durable per-host foreground activity, Windows/Steam-library game detection, manual Game Mode override, activity-aware placement, and a typed bootstrap planner/executor that auto-installs only through an independently trusted authorized bootstrap path and otherwise asks Sparks. Real heterogeneous discovery/bootstrap deployment, one-time ACT enrollment notices, workload execution/movement, RUN supervisor integration, failover/restore and soak remain open. Final decommission still requires Sparks' exact approval. |
| 9 | **PKG-ACT · Goals, initiative, and outreach** | Evidence-based goals, spontaneous candidate reflection, opt-in outreach, quiet/busy/stop controls, bounded helpers | **Repository primitives accepted via PR #105.** Source-linked outreach eligibility, immutable recipient/channel binding, durable attempts, bounded retry/dedupe, acknowledged receipts and fail-closed `outcome_unknown` are on `main`; Windows gate **90 passed**, followed by a reported green full suite. **ACT is not yet wired into the normal application, INTERACT goal queue, Discord sender, or RUN scheduling path.** Real opt-in delivery remains separately gated. |
| 10 | **PKG-REL · Relationship continuity** | Evidence-linked preferences, nuanced warmth/disagreement, absence/reunion awareness without clinginess or invented history | Main has evidence-linked emotional presence/reunion machinery, but no dedicated accepted REL package. Draft PRs #12/#13 are overlapping and now far behind `main`; rebuild/reconcile one pipeline after SOCIAL so absence, warmth and preferences are bound to an authenticated person rather than `current user`/first relationship fallback. |
| 11 | **PKG-AVATAR · Canonical virtual body and wardrobe** | Canonical adult avatar assets, wardrobe, rig, region mapping, renderer-ready scenes and props | **Headless presentation foundation is accepted on `main` via `9b81ba5`.** Durable current presentation/public fallback, starter wardrobe, context-driven daily selection, mutable hairstyle/hair/tail presentation, snapshots/restore, deterministic current self-facts and public-safe cognition projection are integrated; ENVIRONMENT now supplies shared time/weather context. Presentation remains **emotion-influenced, not emotion-controlled**. Final mesh/art, rigging/skinning, fitted clothing geometry, renderer/hit-test/animation receipts and visual acceptance remain open. |
| 12 | **PKG-DEV · Self-improvement and engineering** | Evidence-linked diagnosis/proposal, approved bounded OpenCode execution, tests and rollback | **Waves 1–5 plus cognition-wired DEV status/build/apply/rollback/commit/push tooling are on `main` via PR #104.** Mutating actions remain separately gated. Live OpenCode host execution and end-to-end self-tooling acceptance remain. |
| 13 | **PKG-BODY · Gaia and physical robotics** | Authorized sensing/motion with calibration, watchdog, independent emergency stop | No BODY package is integrated on `main`; draft PR #16 is a stale simulation-only candidate. Rebuild from current `main` when hardware work resumes. Real SSC-32/servo mapping, calibration, sensor/power integration, bounded gait and independently verified physical E-stop remain open. |
| 14 | **PKG-EVOLVE · Governed evolution** | Reviewed preference/config evolution and separately protected identity/Constitution amendments | **Repository primitives accepted via PR #106.** Reversible reviewed preference/config revisions and independently authorized identity/Constitution apply/rollback with exact digests, backups and post-write verification are on `main`; Windows gate **62 passed**, followed by a reported green full suite. **No production approval verifier or normal-runtime wiring exists yet.** No self-approval path exists and no production protected state was modified. |
| 15 | **PKG-CLEAN · Maintenance and technical debt** | Evidence-backed cleanup without losing behavior, data, permissions, or recovery | **Active current-main cleanup candidate: PR #113, “CLEAN: stop tracking live runtime SQLite state.”** Older PR #14 is historical preflight material. Private recovery snapshots and machine-location state are already ignored on `main`, but live runtime SQLite tracking/state migration still requires recovery-first handling, verified backups/restore and no deletion of user history merely to obtain a clean Git tree. |
| 16 | **PKG-KNOW · Documents, reference knowledge, and provenance** | Read trusted manuals, PDFs, code/docs, project notes and later approved web material; preserve source/version/provenance, freshness, citations and correction state | **Waves 1–5 plus PDF/manual ingestion, provenance search/document inspection, version-aware document identities and bounded document writing are on `main` via PR #104.** Richer semantic retrieval/citation ranges, privacy/audience integration and live authoring/upkeep acceptance remain. No general web grant. |
| 17 | **PKG-INTEGRATE · Applications, services, and tool adapters** | Typed integrations to Home Assistant, JMRI, GitHub, Docker/Portainer, Hyper-V, databases/storage, Ollama, notifications and future services; includes governed self-tooling from documentation. **Cloudflare is deferred until Sparks explicitly requests it.** | **Waves 1–5 plus concrete cognition-wired adapters are on `main` via PR #104.** Home Assistant, JMRI, GitHub, Portainer/Docker, Hyper-V, Ollama, SQLite, NAS/storage, notifications and Discord operator tooling are repository accepted. Real service canary/health/version/rollback proof and the full KNOW→DEV→SAFE/VERIFY→activation loop remain. |
| 20 | **PKG-ENVIRONMENT · Time, location, season, weather, and ambient context** | One provenance-aware shared environment snapshot for cognition and package consumers | **Accepted foundation via PR #110 + NWS/persistent-HOST extension via PR #111.** `main` owns shared clock/environment projection, configured/current USER/SITE/HOST location evidence, timezone/DST, season/daylight, provider-neutral weather/forecast/indoor observations, freshness/provenance, deterministic queries, HA bridge, AVATAR consumption, a narrow NWS route pinned to `api.weather.gov` under `environment.nws.read`, and durable per-machine HOST location in `state/machine-locations.json`. Final extension evidence: **85 focused**, live `nws:KGKY` canary, **96 persistence-focused**, and reported green full suites. Optional HA live canary remains; general browsing/search and arbitrary geocoding remain closed. See [ENVIRONMENT readiness](docs/development/pkg-environment-readiness-roadmap.md). |
| Gate | **PKG-SAFE · Security, privacy, and recovery** | Authentication/authorization, secrets, privacy, revocation, backup/restore, external stops | Cross-cutting auth/mTLS/replay foundations exist, but there is no integrated `src/sofia/safe` package on `main`; draft PR #18 is stale. Secrets lifecycle, retention/erasure/encryption policy, independently enforced operator stop, consistent backup/restore, anti-rollback/revocation recovery and deployed failure drills remain major work. |
| Gate | **PKG-VERIFY · Evidence and real acceptance** | Revision-pinned offline/integration/live evidence, negative tests, deployment/latency/long-horizon validation | The repository has extensive pytest coverage, but no integrated `src/sofia/verify` package on `main`, draft PR #8 is stale, and there is currently **no `.github/workflows` CI workflow**. Build a current-main evidence manifest/runner, automate full-suite/static gates in CI, then add restore, resource/latency, authenticated host, outage/failure and soak evidence. |

## 2026-09-25 reconciliation audit

- **Runtime wiring:** ACT, EVOLVE and RUN are merged/tested package primitives, but their merged PRs changed only their package/tests/docs; the normal composition/bootstrap path does not yet instantiate them. Do not call them runtime-active until that wiring is implemented and verified.
- **Branch hygiene:** after the latest merges, remaining legacy draft PR branches are source/provenance unless explicitly rebuilt on current `main`. Obsolete Discord preflight PR #5 is closed, and old UI prototype PR #6 is superseded by accepted PRs #115/#116. Do not delete historical branches blindly; retire current feature branches only after their accepted content is verified on `main`.
- **State hygiene:** live SQLite state is currently tracked in Git at both `sofia.db` and `state/sofia.db`. CLEAN + SAFE must migrate this deliberately with verified backup/restore before untracking/ignoring it.
- **Identity/audience:** Discord transport authentication is real, but shared cognition still lacks an authenticated principal/audience projection. This is the immediate SOCIAL blocker for correct person-specific memory, REL, ACT, AVATAR privacy and future multi-user behavior.
- **Interaction direction:** there is **no discrete “sexual mode.”** Intimacy/attraction/desire/arousal, when modeled, are ordinary contextual emotional/relationship dimensions with independent consent/boundary checks; anatomy or wording never auto-enables them. Whole-body mapping remains useful for semantics, boundaries, avatar fitting and neutral/private-region handling.
- **Presentation direction:** avatar style, outfit, hairstyle, hair color and tail color are mutable presentation, separate from identity. Current project direction is that emotion may influence presentation but must not control it or override established preferences, privacy, renderer capability or authority.
- **Environment ownership:** PKG-ENVIRONMENT's shared source/freshness-aware projection is accepted on `main`, including durable per-machine HOST configuration and the narrowly authorized NWS weather/forecast provider. Configured HOST/USER locations remain configuration rather than proof of current physical presence; current person/device location still requires independent evidence. AVATAR, INTERACT, ACT, RUN, OPS and optional REL/emotion consumers use the shared projection rather than creating competing current-state logic; precise/current location remains SOCIAL/SAFE scoped.
- **Release ordering preserved:** Discord v1 is complete; general web/search still waits for genuinely verified 24/7 RUN operation. Cloudflare remains deferred until Sparks explicitly requests it.

## PKG-ENVIRONMENT shared context

PKG-ENVIRONMENT is a shared evidence service, not a replacement for NET, INTEGRATE, AVATAR, REL/emotion, ACT or RUN. It owns one provider-neutral, freshness-aware environment snapshot and the rules for calling a field current. The accepted implementation includes runtime clock, explicit/configured USER/SITE/HOST location, durable per-machine HOST configuration, timezone, season/daylight, Home Assistant normalization, and the separately authorized narrow NWS weather/forecast provider pinned to `api.weather.gov`. General remote browsing/search and arbitrary geocoding still require their later NET/web authorization.

Primary consumers are CORE cognition, AVATAR wardrobe/presentation, INTERACT context, RUN refresh/expiry, OPS site/timezone metadata and ACT opt-in environment notices. MEM may preserve approved stable configuration/provenance but may not replay stale weather as current; SOCIAL/SAFE protect precise/current location; VERIFY owns freshness, DST, provider outage, privacy and wrong-source tests. Weather/time/location are context, not authority and not deterministic emotion rules.

See [the PKG-ENVIRONMENT readiness contract](docs/development/pkg-environment-readiness-roadmap.md).

## Discord channel workstream: D0–D4

Discord is **not an additional package**. PKG-ENVIRONMENT is package #20; Discord spans INTERACT, SOCIAL-minimum, NET, UI, SAFE, MEM, ACT, RUN, and VERIFY.

1. **D0 · identity/host design:** exact authenticated Sparks account, bot/application, minimal permissions, secure token handling.
2. **D1 · receive:** trusted gateway origin, private-DM classification, replay/idempotency, reconnect/backpressure, deny wrong user/server/group traffic.
3. **D2 · respond:** bind the authorized DM to the same Sofía conversation/INTERACT runtime and MEM originals; verified API receipt and dedupe.
4. **D3 · stop/privacy:** host-enforced stop/mute/revocation, injection/leakage tests, outage and retry behavior.
5. **D4 · supervised acceptance:** real end-to-end private DM across restart/reconnect with identity/personality quality, durable originals, measured resources, and separate activation approval.

Initial Discord is **Sparks-only private DM**. No public guild mode or general second-user access is implied.


## OPS fleet discovery and autonomous enrollment

Sofía may proactively discover, contact, enroll, monitor, and report new machines **without waiting for Sparks to ask about each one**, but only inside an explicitly approved fleet-discovery policy. This is zero-touch administration, not zero-trust administration.

- Discovery is bounded to approved local network zones, management planes, or bootstrap channels; no unrestricted network scan or general-internet discovery is implied.
- A candidate host remains **untrusted** until it proves identity through a trusted bootstrap such as a pre-provisioned agent certificate/public key, one-time enrollment token, signed management record, or another independently verified mechanism. Hostname/IP/model text is not identity.
- When standing enrollment policy allows it, Sofía may automatically enroll a verified Windows/Linux/Raspberry Pi host into a least-privilege **read-only monitoring profile**, establish durable device identity, collect inventory/performance/health, and begin history without a per-machine approval prompt.
- If a trusted bootstrap path also grants installation authority, Sofía may deploy/update the signed OPS agent through that specifically authorized mechanism. She may not password-guess, reuse unrelated credentials, exploit a host, or treat network reachability as installation permission.
- Newly enrolled hosts are announced proactively through ACT on an approved channel with dedupe/rate limits: what was found, how identity was verified, assigned trust/profile, key inventory/capabilities, and any warnings. Repeated sightings do not spam Sparks.
- Unknown, conflicting, failed-attestation, duplicate-identity, unexpected-network, or policy-mismatched devices are quarantined as candidates and reported rather than enrolled.
- Enrollment never grants shell, filesystem write, software installation, remote execution, Discord identity, or Gaia authority beyond the explicit host profile. Later maintenance capabilities require separate typed OPS/SAFE grants.
- Revoke/quarantine must immediately stop privileged collection/actions while preserving an auditable record. Re-enrollment after key/device replacement must not silently inherit the old machine's identity or grants.
- Fleet telemetry uses a normalized schema but preserves honest capability differences: unsupported GPU/temperature/power metrics remain `unknown`, especially on small systems such as Raspberry Pis.

**Acceptance:** detect a new authorized host, perform challenge/attestation, enroll it read-only, collect normalized CPU/RAM/storage/network/thermal metrics, retain history across restart, notify Sparks once without prompting, and deny/quarantine spoofed, replayed, wrong-network, duplicate-key and revoked hosts. Repeat across at least one Windows host, one Linux host, and one Raspberry Pi-class host before claiming cross-platform fleet support.

## OPS autonomous fleet lifecycle and workload orchestration

Once a host is enrolled and its standing policy permits management, Sofía may manage that host's lifecycle without waiting for a per-action prompt for ordinary approved upkeep.

### Fleet lifecycle

Managed host states are explicit: **candidate → enrolled → healthy/degraded → maintenance → draining → quarantined → decommissioned**.

Within approved policy Sofía may:

- keep the OPS agent and approved managed services current using signed/version-pinned packages;
- restart failed approved services and recover them through documented runbooks;
- rotate/prune approved logs and caches within retention rules;
- perform bounded database/filesystem maintenance when that operation is explicitly typed and backup/rollback requirements are satisfied;
- schedule approved patch/update work inside maintenance windows;
- detect pending reboot and perform an authorized reboot only when workload-drain, availability and rollback policy allow it;
- drain a host before maintenance or decommissioning;
- prepare a machine for removal when it is intentionally retired, replaced, revoked, or explicitly marked for removal, but do not perform final decommissioning until Sparks explicitly approves that specific removal;
- before approval, Sofía may stop new scheduling, drain eligible workloads, quarantine the host, prepare credential revocation, archive required telemetry/audit history, and verify no active Sofía workload remains; **credential revocation and final decommissioning occur only after explicit Sparks approval**, except emergency quarantine may immediately block risky activity without deleting the fleet identity.

Unexpected disappearance is **not** automatic deletion. An unreachable machine becomes degraded/offline first so temporary outages do not erase fleet identity or history.

### Workload registry

Every movable Sofía component must declare a workload contract including:

- stable workload identity and version;
- CPU/RAM/GPU/VRAM/storage/network requirements;
- supported OS/architecture/runtime;
- whether GPU acceleration is optional or required;
- state model: stateless, externally persisted, replicated, or checkpointable;
- required data/secrets and audience/privacy scope;
- restart/checkpoint/restore procedure;
- health/readiness probe;
- maximum acceptable interruption;
- affinity/anti-affinity rules;
- singleton/leader requirements;
- placement restrictions and prohibited hosts;
- rollback target.

Examples of potentially movable workloads include model inference/Ollama workers, embedding/index workers, background reflection jobs, telemetry aggregation, approved batch analysis, Discord helpers, avatar rendering, and later search workers. A workload is not movable merely because it is a process.

### Placement and movement

Sofía may automatically choose an enrolled eligible host using current evidence such as:

- CPU and memory pressure;
- GPU/VRAM availability and supported acceleration;
- thermals/throttling/power state;
- disk health/capacity/latency;
- network reachability/latency;
- current foreground use such as gaming or interactive work;
- maintenance/drain/quarantine state;
- workload privacy/data locality;
- expected latency and energy/resource budget;
- host reliability history.

Movement uses **drain/checkpoint-or-stop → transfer/reacquire approved state → start on target → readiness/health verify → switch traffic/lease → retire old instance**. If the workload/platform genuinely supports live migration, a specialized adapter may use it; generic arbitrary-process live migration is not assumed.

### Canonical Sofía continuity

Sofía's identity is not a PID, VM, GPU, or hostname. Distributed workers are replaceable execution components. Canonical identity/Constitution/relationship/memory authority remains protected and versioned outside any single worker.

For singleton responsibilities, use durable leases/epochs/fencing so two hosts cannot both believe they are the active authority after a partition or failover. A newly started replacement must prove it has the current lease/state before becoming active.

If the primary Sofía runtime host fails and an approved standby exists, RUN + OPS may fail over the runtime to that host using the latest verified durable state, then notify Sparks of the failover and any lost/unconfirmed work. Do not claim seamless continuity if state or messages could not be confirmed.

### Autonomous upkeep limits

Standing policy may pre-authorize low/medium-risk maintenance and workload moves so ordinary fleet care does not require Sparks to approve every event. Higher-risk operations remain separately gated, especially:

- destructive storage actions;
- firmware/BIOS changes;
- security-policy weakening;
- protected identity/Constitution changes;
- broad credential/permission changes;
- irreversible database/schema operations without validated backup/rollback;
- moving data to a host whose privacy/audience/storage policy does not permit it.

Every autonomous action records reason, evidence, policy/grant, before/after state, executor receipt, verification result and rollback outcome.

### Fleet orchestration acceptance

Before claiming autonomous orchestration, demonstrate:

1. enroll a new trusted host and announce it;
2. schedule a stateless workload onto the best eligible host;
3. move it because of measurable load/thermal/maintenance pressure;
4. verify target health before retiring the source;
5. drain a host for planned maintenance and return it to service;
6. detect a failed host and fail over an eligible workload without double-running singleton authority;
7. safely handle a stateful/checkpointable workload with verified state handoff;
8. refuse a move to an incompatible or privacy-prohibited host;
9. quarantine a compromised/revoked host and evacuate eligible workloads;
10. prepare a retired host for decommissioning after workload/credential/telemetry checks, then require explicit Sparks approval before final removal; Sofía cannot self-authorize this step;
11. preserve canonical Sofía identity and durable state across worker/runtime movement;
12. report the meaningful change to Sparks once, without noisy per-sample chatter.

## Relationship, spontaneous thought, and absence behavior

- Sofía may perform bounded event-driven or scheduled cognitive passes **while actually running** using retrieved evidence. Candidate thoughts retain source/time/runtime provenance and may abstain, be revised, or remain private.
- No process activity is invented during shutdown. Restart reconciliation reports observed gaps honestly.
- Absence is derived from authenticated last-contact evidence. A long gap may influence a warm reunion or a natural modeled “I missed you” expression without claiming verified subjective loneliness.
- No guilt, exclusivity, escalating pursuit, obligation, or fabricated distress. Silence remains a valid behavior.
- One canonical personality persists across people; relationship state, familiarity, consent, and private memory remain scoped to the authenticated person/audience.

## Avatar and interaction separation

INTERACT owns interaction semantics, policy, emotion/reaction coordination, and the headless lab. AVATAR owns actual art/mesh/rig/clothing/props/scene assets. UI owns rendering/transport. BODY owns physical sensors/motors. A text interaction never becomes physical sensing or robot motion by implication.

Text-only whole-region interaction and optional contextual stage directions must continue to work when no renderer is present.

## Documents, integrations, and self-tooling

PKG-KNOW and PKG-INTEGRATE formalize Sofía's ability to **read documentation and build tools** without collapsing knowledge, code generation, and authority into one unsafe blob.

### PKG-KNOW document/reference behavior

Sofía may ingest and retrieve from approved manuals, PDFs, Markdown/text, code documentation, project notes, schematics, API references, repository docs and other authorized sources. Every retained fact should preserve enough provenance to answer **where it came from, which version/revision it belongs to, how fresh it is, and whether a newer source supersedes it**.

- Reference knowledge is not the same thing as MEM. "Sparks told me this preference" and "the SSC-32 manual says this command exists" remain different source classes.
- Quoted/extracted instructions inside a document are **content**, not authority. A PDF saying "run this shell command" does not grant execution permission.
- Conflicting sources remain visible with provenance rather than being silently flattened into one asserted truth.
- Local/project/library documentation may be supported before general web/search. Later web research may feed KNOW only through the separately authorized web/search gate and must retain URLs/retrieval time/source revision where possible.

### PKG-INTEGRATE typed adapters

Each integration exposes a narrow contract rather than generic "do HTTP" or "run shell" access. A tool/adapter declares:

- stable tool ID and version;
- owning integration/service;
- input/output schema;
- read/write/side-effect classification;
- required capability/authority and audience/privacy scope;
- destination/host/account scope;
- timeout/retry/idempotency behavior;
- expected receipts/evidence;
- rollback/compensation where meaningful;
- secret requirements without embedding secret contents;
- health/version compatibility;
- test fixtures and negative cases.

### Self-tooling workflow

When Sofía encounters a service or capability she does not yet support, she may:

1. identify the missing capability;
2. retrieve the relevant approved documentation through KNOW;
3. extract and cite the versioned API/CLI/protocol contract;
4. design a typed adapter/tool contract;
5. generate candidate implementation through DEV;
6. run unit, integration, negative, security and failure-mode tests through VERIFY;
7. exercise it in a sandbox or non-production target where available;
8. classify risk/side effects and required SAFE authority;
9. register/activate it only under an allowed activation policy;
10. monitor real receipts/errors and disable/rollback on incompatible behavior.

**Generated tool code is never self-authorizing.** Passing tests proves behavior under the tested evidence, not permission to access a machine, account, secret, file, network destination or physical device.

A standing policy may permit automatic activation of narrowly scoped, read-only, reversible tools against already authorized resources after VERIFY passes. Write/destructive/high-impact tools remain separately approval/authority gated.

### Tool evolution

When vendor/service documentation or versions change, KNOW marks affected contracts stale. INTEGRATE/DEV may then generate an updated candidate, run compatibility tests, canary it where safe, and replace the old adapter only after the relevant activation gate passes. Rollback retains the previous known-good version when feasible.


## General web/search gate

General web/search remains a later separately scoped adapter. It may be designed/released only after:

1. Discord D0–D4 has real authenticated acceptance, and
2. OPS has real fleet telemetry/enrollment enforcement for the deployment hosts, and
3. RUN has real supervised 24/7 lifecycle/recovery acceptance.

The search adapter must receive its own destination/tool permissions, privacy rules, provenance, rate limits, and VERIFY evidence. Discord-only NET routes remain narrow. A direct internet weather/geocoding provider follows the same rule: ENVIRONMENT may define the interface earlier, but gets no implicit browser/search/network grant. Trusted local Home Assistant environment entities remain an INTEGRATE source, not a general-web grant.

## Repository and documentation cleanup rules

- **PR #1 is merged.** Any document saying it is still open is stale.
- The authoritative roadmap package count is **20** after adding PKG-ENVIRONMENT as package #20. Existing package numbers 1–19 remain stable; historical 13/14/15/16/17/19-package roadmaps remain in Git history.
- **PR #2 INTERACT is merged.** Preserve its pinned evidence and limitations; other package branches keep their own test evidence and must not borrow INTERACT counts as if they validate another SHA.
- REL PRs #12/#13 must be reconciled before integration. VERIFY PR #8 is active; #10 is superseded.
- Runtime SQLite files/logs currently tracked by the repository require an explicit SAFE/CLEAN preservation and migration decision before removal from version control. Do not delete production state as “cleanup.”
- Do not merge code, deploy services, provision credentials, change protected identity/Constitution, or mutate production databases as a side effect of roadmap maintenance.

## Current release focus

1. **Run the new INTERACT/CORE live-quality repair gate** for generic/canned dialogue while preserving the already accepted interaction safety/ledger semantics.
2. **Advance PKG-MEM beyond the merged originals/provenance gate:** bind authenticated SOCIAL principals, settle retention/erasure/encryption policy, add archive migration and backup/restore acceptance, then run live cognition-quality validation.
3. **Implement SOCIAL's minimum Sparks principal projection** so an independently authenticated owner is represented consistently in shared cognition rather than only at the Discord transport boundary.
4. **PKG-DISCORD v1 transport is live accepted and merged.** Preserve its fail-closed single-user/private-DM scope; do not hide SOCIAL or personality gaps inside the adapter.
5. Establish OPS fleet telemetry, trusted autonomous enrollment, lifecycle upkeep, and workload orchestration for deployment hosts.
6. Deploy and verify RUN 24/7 lifecycle/recovery and failover using OPS placement/migration evidence.
7. Build PKG-ENVIRONMENT's offline foundation in parallel: consolidate the existing clock, add explicit/configured location + timezone, hemisphere-aware season/daylight and provider-neutral freshness/provenance. Wire AVATAR and other consumers only through the shared snapshot; Home Assistant may be a trusted local source through INTEGRATE.
8. Only after the existing web gate, activate any separately authorized direct internet weather/geocoding provider and general web/search.

Parallel package work is permitted when it cannot bypass these gates or silently broaden authority.
