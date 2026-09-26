> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the runtime toolbox and secure fleet-transport completion gate on top of the earlier Waves 1–5 work. Focused tool/mTLS acceptance passed **34/34**, the surrounding DEV/KNOW/INTEGRATE/OPS/system/machine regression gate passed **270/270**, and the full repository pytest suite was reported passing before merge. Source-level pinned mTLS remote transport/agent and concrete runtime adapters are now on `main`; real heterogeneous-host deployment, service canaries, RUN 24/7 supervision, workload execution/failover, restore and soak remain separately gated.

> **Project status update — 2026-09-25 (late):** PRs #105 (ACT), #106 (EVOLVE), and #107 (RUN local lifecycle) are merged. Their Windows package gates passed **90**, **62**, and **78 passed / 1 skipped** respectively, and Sparks reported the post-merge current-`main` full pytest suite passing. Repository audit at `13046c2` found **299 Python source files**, **246 Python test files**, and **59 Git branches**. The new ACT/RUN/EVOLVE primitives are not yet wired into the normal application/composition path. SOCIAL principal projection remains absent from `CognitiveContext`. Eleven legacy draft PRs were initially open and all were roughly 330 commits behind `main`; obsolete Discord preflight PR #5 has now been closed as superseded by merged/live-accepted PR #64.

> **Architecture update — 2026-09-25:** current-code review confirmed tested runtime-clock evidence is already injected into the live conversation path, while authoritative geographic location, season/daylight, weather/forecast and a shared environment snapshot are absent. **PKG-ENVIRONMENT is added as package #20** without renumbering packages 1–19.

# Sofía Ada Lyra: 20-package delivery roadmap

**Planning revision:** 2026-09-25 (America/Chicago). **Status:** roadmap documentation on `main`; package implementation and deployment remain separately gated. PR #1 (CORE), roadmap reconciliation PR #4, PR #2 (INTERACT), and PR #29 (INTERACT post-merge hardening) are merged. PKG-DISCORD v1 passed supervised live owner-DM transport acceptance and merged to `main` via PR #64 (`ba2111b`). INTERACT remains accepted as the semantic/safety foundation, with a new narrow INTERACT/CORE quality-repair gate opened for generic/canned live dialogue. The roadmap now contains **20 packages**. PKG-ENVIRONMENT is package #20; Discord remains a cross-package workstream rather than a separate package.

> **Core invariant:** Sofía's canonical identity, Constitution, represented embodiment, evidence, memory, authority, and capabilities remain independent of replaceable models, hosts, processes, clients, Discord, voices, avatars, and robots. Model output is never proof of authorization, sensing, execution, delivery, or subjective experience.

## Delivery order

The primary dependency path is:

**CORE → INTERACT → MEM → SOCIAL minimum identity/audience boundary → Discord D0–D4 using NET + UI + SAFE → OPS minimum fleet telemetry/enrollment → RUN verified 24/7 operation → later separately authorized general web/search.**

After MEM, package work that does not bypass those release gates may proceed in parallel. In particular, OPS may mature fleet diagnostics and trusted enrollment; KNOW may mature local/document knowledge; INTEGRATE may mature typed adapters; REL and ACT may mature absence, initiative, and outreach; AVATAR may continue offline asset work; DEV, BODY, EVOLVE, and CLEAN remain separately gated. **ENVIRONMENT may begin offline clock/location/timezone/season/daylight work now; trusted local Home Assistant observations may feed it through INTEGRATE, while direct internet weather remains behind separate NET/web authorization.**

**SAFE and VERIFY are continuous gates across every stage rather than late sequential packages.**

General internet/search is deliberately **not** part of the initial Discord NET scope. Discord connectivity does not grant browser/search access.

## Ordered package roster

| Order | Package | Outcome | Current evidence-based state / next gate |
| ---: | --- | --- | --- |
| 1 | **PKG-CORE · Cognition and continuity** | Grounded identity/personality, startup/restart awareness, response performance, adaptive reasoning | Foundations merged in PR #1. A new joint INTERACT/CORE live-quality repair gate is open after Discord exposed generic assistant fallback in ordinary dialogue; identity/personality/latency review remains part of that gate. |
| 2 | **PKG-INTERACT · Text/avatar/screen interaction** | Shared canonical whole-body interaction semantics, contextual reactions, virtual lab, truthful expression | **Accepted semantic/safety foundation via PR #2 and PR #29.** A narrow live-quality repair gate is reopened with CORE because Discord exposed generic/canned wording in ordinary greetings. Existing interaction-policy, stop, ledger, source-attestation and embodiment acceptance remains intact. Staged offers remain disabled pending separate schema provisioning. |
| 3 | **PKG-MEM · Durable memory and learning** | Preserved originals, provenance-aware retrieval, correction, reviewed durable preferences, archive migration | **Original/provenance gate accepted and merged via PR #9.** Exact persisted originals, durable provenance candidates, explicit promotion/rejection/revocation, promoted-only projection/retrieval, source invalidation and reviewed source-to-candidate workflow are on `main`; 54/54 focused tests and the full repository suite were reported passing before merge. Archive import, retention/erasure/encryption policy, SOCIAL principal binding, backup/restore and live cognition-quality acceptance remain. |
| 4 | **PKG-SOCIAL · Principal, audience, and isolation** | One Sofía across people/channels with authenticated principals, per-user relationship state, private/shared scopes, no cross-user leakage | **Primary coding gap.** Discord authenticates the exact enrolled owner, but `CognitiveContext` has no principal/audience field and the normal conversation path therefore does not project the authenticated owner as `Sparks`. No dedicated SOCIAL runtime package is on `main`. Implement one shared principal projection plus negative audience/isolation tests; general second-user/multi-user rollout stays deferred. |
| 5 | **PKG-NET · Scoped networking and distributed operation** | Authenticated network routes and bounded remote capabilities | **Durable admission plus pinned mutual-TLS remote agent/transport are on `main` via PRs #11/#104.** CA validation, server public-key pinning, mutual TLS, durable node enrollment, exact endpoint approval, exact operation grants and replay protection are repository accepted. Real Windows/Linux/Pi deployment and outage/revocation acceptance remain. No general web/search grant. |
| 6 | **PKG-UI · Clients, Discord adapter, voice, and workbench** | Authenticated interfaces to the same Sofía, delivery/renderer acknowledgments, accessible text fallback | **Sparks-only Discord DM adapter is live accepted for v1 transport.** Workbench, desktop/web/mobile clients, voice, renderer, and proactive outbound UI remain separately unaccepted. |
| 7 | **PKG-RUN · 24/7 lifecycle and supervision** | External service supervision, single active instance, restart/backoff, bounded periodic cognition, health/recovery | **Repository primitives accepted via PR #107.** `main` has bounded periodic opportunities, local singleton lease/fencing epochs, stale-owner rejection, host-neutral supervisor, readiness timeout, restart backoff/window limits and durable supervisor events; Windows gate **78 passed / 1 skipped**, followed by a reported green full suite. **Not yet wired into `SofiaApplication`/composition and not an installed OS service.** Independent watchdog, cross-host leadership/fencing, standby/failover, RTO/RPO and soak remain open. |
| 8 | **PKG-OPS · Fleet operations, diagnostics, performance, and orchestration** | Cross-platform telemetry, trusted zero-touch enrollment/decommissioning, autonomous upkeep, configuration drift, workload placement/failover, and bounded maintenance | **Strong source foundation on `main` via PRs #99/#103/#104.** Fleet cognition currently exposes read-only fleet/telemetry/placement/drift/migration planning, while exact-grant remote service/reboot/package/VM/container operations exist through the distributed transport. The requested zero-touch discovery→attestation→enrollment→one-time ACT notice loop, standing-policy upkeep orchestration, actual workload movement, RUN supervisor integration, real heterogeneous deployment, failover/restore and soak remain open. |
| 9 | **PKG-ACT · Goals, initiative, and outreach** | Evidence-based goals, spontaneous candidate reflection, opt-in outreach, quiet/busy/stop controls, bounded helpers | **Repository primitives accepted via PR #105.** Source-linked outreach eligibility, immutable recipient/channel binding, durable attempts, bounded retry/dedupe, acknowledged receipts and fail-closed `outcome_unknown` are on `main`; Windows gate **90 passed**, followed by a reported green full suite. **ACT is not yet wired into the normal application, INTERACT goal queue, Discord sender, or RUN scheduling path.** Real opt-in delivery remains separately gated. |
| 10 | **PKG-REL · Relationship continuity** | Evidence-linked preferences, nuanced warmth/disagreement, absence/reunion awareness without clinginess or invented history | Main has evidence-linked emotional presence/reunion machinery, but no dedicated accepted REL package. Draft PRs #12/#13 are overlapping and now far behind `main`; rebuild/reconcile one pipeline after SOCIAL so absence, warmth and preferences are bound to an authenticated person rather than `current user`/first relationship fallback. |
| 11 | **PKG-AVATAR · Canonical virtual body and wardrobe** | Canonical adult avatar assets, wardrobe, rig, region mapping, renderer-ready scenes and props | Draft PR #7 contains substantial offline wardrobe/scene/body/tooling and the intended mutable presentation model, including hairstyle, hair color, tail color and Sofía-owned style preferences, but that branch is far behind `main` and no `src/sofia/avatar` package is integrated. Rebuild on current `main`; presentation should be **emotion-influenced, not emotion-controlled**, with durable preference/state separation and renderer truthfulness. Finished art, rig, renderer receipts and live acceptance remain. |
| 12 | **PKG-DEV · Self-improvement and engineering** | Evidence-linked diagnosis/proposal, approved bounded OpenCode execution, tests and rollback | **Waves 1–5 plus cognition-wired DEV status/build/apply/rollback/commit/push tooling are on `main` via PR #104.** Mutating actions remain separately gated. Live OpenCode host execution and end-to-end self-tooling acceptance remain. |
| 13 | **PKG-BODY · Gaia and physical robotics** | Authorized sensing/motion with calibration, watchdog, independent emergency stop | No BODY package is integrated on `main`; draft PR #16 is a stale simulation-only candidate. Rebuild from current `main` when hardware work resumes. Real SSC-32/servo mapping, calibration, sensor/power integration, bounded gait and independently verified physical E-stop remain open. |
| 14 | **PKG-EVOLVE · Governed evolution** | Reviewed preference/config evolution and separately protected identity/Constitution amendments | **Repository primitives accepted via PR #106.** Reversible reviewed preference/config revisions and independently authorized identity/Constitution apply/rollback with exact digests, backups and post-write verification are on `main`; Windows gate **62 passed**, followed by a reported green full suite. **No production approval verifier or normal-runtime wiring exists yet.** No self-approval path exists and no production protected state was modified. |
| 15 | **PKG-CLEAN · Maintenance and technical debt** | Evidence-backed cleanup without losing behavior, data, permissions, or recovery | **Needs attention.** Draft PR #14 is stale and not integrated. Current `main` still tracks both root `sofia.db` and `state/sofia.db`; `.gitignore` only excludes lab DBs, which explains recurring local `state/sofia.db` modifications. Root apply/repair scripts and `regression-failure.log` also need evidence-based disposition. First CLEAN delivery should inventory/backup/migrate runtime state, then untrack/ignore live DB artifacts without deleting history or user data. |
| 16 | **PKG-KNOW · Documents, reference knowledge, and provenance** | Read trusted manuals, PDFs, code/docs, project notes and later approved web material; preserve source/version/provenance, freshness, citations and correction state | **Waves 1–5 plus PDF/manual ingestion, provenance search/document inspection, version-aware document identities and bounded document writing are on `main` via PR #104.** Richer semantic retrieval/citation ranges, privacy/audience integration and live authoring/upkeep acceptance remain. No general web grant. |
| 17 | **PKG-INTEGRATE · Applications, services, and tool adapters** | Typed integrations to Home Assistant, JMRI, GitHub, Docker/Portainer, Hyper-V, databases/storage, Ollama, notifications and future services; includes governed self-tooling from documentation. **Cloudflare is deferred until Sparks explicitly requests it.** | **Waves 1–5 plus concrete cognition-wired adapters are on `main` via PR #104.** Home Assistant, JMRI, GitHub, Portainer/Docker, Hyper-V, Ollama, SQLite, NAS/storage, notifications and Discord operator tooling are repository accepted. Real service canary/health/version/rollback proof and the full KNOW→DEV→SAFE/VERIFY→activation loop remain. |
| 20 | **PKG-ENVIRONMENT · Time, location, season, weather, and ambient context** | One provenance-aware shared environment snapshot for cognition and package consumers | **New readiness package.** Tested runtime-clock evidence already exists and is projected into live conversation; authoritative geographic location, season/daylight, weather/forecast and a shared environment model are not implemented. Build offline location/timezone/season/daylight first; trusted Home Assistant evidence may enter through INTEGRATE; direct internet weather stays behind separate NET/web authorization. See [ENVIRONMENT readiness](docs/development/pkg-environment-readiness-roadmap.md). |
| Gate | **PKG-SAFE · Security, privacy, and recovery** | Authentication/authorization, secrets, privacy, revocation, backup/restore, external stops | Cross-cutting auth/mTLS/replay foundations exist, but there is no integrated `src/sofia/safe` package on `main`; draft PR #18 is stale. Secrets lifecycle, retention/erasure/encryption policy, independently enforced operator stop, consistent backup/restore, anti-rollback/revocation recovery and deployed failure drills remain major work. |
| Gate | **PKG-VERIFY · Evidence and real acceptance** | Revision-pinned offline/integration/live evidence, negative tests, deployment/latency/long-horizon validation | The repository has extensive pytest coverage, but no integrated `src/sofia/verify` package on `main`, draft PR #8 is stale, and there is currently **no `.github/workflows` CI workflow**. Build a current-main evidence manifest/runner, automate full-suite/static gates in CI, then add restore, resource/latency, authenticated host, outage/failure and soak evidence. |

## 2026-09-25 reconciliation audit

- **Runtime wiring:** ACT, EVOLVE and RUN are merged/tested package primitives, but their merged PRs changed only their package/tests/docs; the normal composition/bootstrap path does not yet instantiate them. Do not call them runtime-active until that wiring is implemented and verified.
- **Branch hygiene:** after the latest merges, the remaining legacy draft PR branches are hundreds of commits behind current `main`. Treat them as source/provenance to rebuild from current `main`, not direct merge candidates. Obsolete Discord preflight PR #5 is closed; do not delete historical branches blindly.
- **State hygiene:** live SQLite state is currently tracked in Git at both `sofia.db` and `state/sofia.db`. CLEAN + SAFE must migrate this deliberately with verified backup/restore before untracking/ignoring it.
- **Identity/audience:** Discord transport authentication is real, but shared cognition still lacks an authenticated principal/audience projection. This is the immediate SOCIAL blocker for correct person-specific memory, REL, ACT, AVATAR privacy and future multi-user behavior.
- **Interaction direction:** there is **no discrete “sexual mode.”** Intimacy/attraction/desire/arousal, when modeled, are ordinary contextual emotional/relationship dimensions with independent consent/boundary checks; anatomy or wording never auto-enables them. Whole-body mapping remains useful for semantics, boundaries, avatar fitting and neutral/private-region handling.
- **Presentation direction:** avatar style, outfit, hairstyle, hair color and tail color are mutable presentation, separate from identity. Current project direction is that emotion may influence presentation but must not control it or override established preferences, privacy, renderer capability or authority.
- **Environment ownership:** live clock evidence exists; current geographic location and weather do not. PKG-ENVIRONMENT owns the source/freshness-aware environment projection. AVATAR, INTERACT, ACT, RUN, OPS and optional REL/emotion consumers use that shared projection rather than creating competing current-state logic; precise/current location remains SOCIAL/SAFE scoped.
- **Release ordering preserved:** Discord v1 is complete; general web/search still waits for genuinely verified 24/7 RUN operation. Cloudflare remains deferred until Sparks explicitly requests it.

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

The search adapter must receive its own destination/tool permissions, privacy rules, provenance, rate limits, and VERIFY evidence. Discord-only NET routes remain narrow.

## Repository and documentation cleanup rules

- **PR #1 is merged.** Any document saying it is still open is stale.
- The authoritative roadmap package count is **19** after adding PKG-KNOW and PKG-INTEGRATE. Historical 13/14/15/16/17-package roadmaps remain in Git history.
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
7. Only then introduce separately authorized general web/search.

Parallel package work is permitted when it cannot bypass these gates or silently broaden authority.
