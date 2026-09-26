> **Project status update — 2026-09-26:** PKG-ENVIRONMENT foundation PR #110 (`766bf21e`) and NWS/persistent-HOST extension PR #111 (`2b753fdb`) are merged to `main`. PR #111 adds a narrowly authorized NWS route pinned to HTTPS `api.weather.gov` under `environment.nws.read`, durable per-machine HOST location keyed by stable machine identity, startup injection, bounded machine-inventory projection and USER/HOST separation. Extension evidence: **85 focused**, reported green full suite, supervised live `nws:KGKY` canary, **96 persistence-focused**, and final reported green full suite. Optional live Home Assistant canary remains separately gated; general browsing/search and arbitrary geocoding remain closed. Earlier DEV/KNOW/INTEGRATE/OPS source acceptance remains unchanged; none of this is proof of production remote fleet orchestration, RUN 24/7 supervision, live failover or soak.

> **Project status update — 2026-09-26 (UI):** PR #115 (`381ac9a`) merged the rebuilt canonical text/workbench foundation and PR #116 (`7f072861`) merged the accepted Windows desktop workbench. Current `main` now has durable unsent drafts, private workbench state, one canonical `SofiaApplication`/conversation path, a single-owner application worker, adaptive ENVIRONMENT/AVATAR/emotion theme projection, shallow chamfered HUD surfaces and reviewed Quick Tools that never auto-send. Acceptance included **58 UI + 24 application/Discord**, later focused UI/AVATAR passes, **90/90 integration repair**, supervised Windows use and a final reported green full repository suite. The same repair gate hardened reviewed-memory SQLite threading/cleanup and explicit request-level tool suppression for trusted interaction turns. Voice, renderer/avatar viewport, mobile/web and provider cancellation remain separately gated.

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

- **Current:** Waves 1–5 plus toolbox/fleet-transport source completion are merged via PRs #99/#103/#104. Fleet lifecycle/placement, machine/system telemetry, machine inventory cognition, fleet status/telemetry, placement/drift/migration planning, typed local/remote maintenance and the pinned mTLS remote agent/transport are repository accepted. Real heterogeneous-host deployment, workload execution, RUN integration and soak/failover proof remain open.
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

### Two data locations and an independent watchdog (architecture, not a package)

A **data-bearing primary and synchronous data-bearing standby** in separate measured failure domains are a candidate strict durability topology, with **one authoritative writer**, an independent witness/equivalent proven fencing authority, an already-running standby supervisor, and **a third isolated versioned backup**. Distinguish role: watchdog detects; supervisor starts; witness/consensus/fencing establishes authority; replica holds committed data; backup recovers corruption/deletion. Two VMs on Artemis or two copies on the same NAS are not physical redundancy. Two independent active SQLite writers or live SQLite file mirroring are prohibited. PostgreSQL is a candidate for an isolated comparison, not a present deployment decision.

With a strict two-copy commit policy, pause authoritative writes when the required synchronous standby is unavailable; reads/degraded chat may continue only where safe. A witness does not replace a data copy. Never promote on heartbeat loss alone or promise zero loss of unfinished responses/external actions. Restore every durable store, preserve privacy and revoked grants, and measure the conditional acknowledged-write RPO and actual recovery time in real failure tests before asserting HA. Keep out-of-band Sparks stop and recovery functioning when Sofía/Discord/primary are down. See [detailed reliability](pkg-reliability-control-plane-contract.md) and [watchdog sequence](pkg-run-watchdog-failover-contract.md).

### Source/document/tool lifecycle

Local authorized docs may be read before general web. KNOW preserves provenance; DEV drafts a tool/doc; INTEGRATE supplies typed semantics; SAFE classifies grant; VERIFY tests; an approved policy or exact human approval activates side effects; RUN/OPS observes and can roll back. No self-granted network, machine, filesystem or physical access. General web/search remains **after** real Discord + OPS host enforcement + RUN 24/7 acceptance, with its own permissions and provenance.

## Immediate engineering order from the current baseline

1. **CORE/INTERACT quality repair:** replace the stale doc-only PR #68 with a current-`main` implementation branch for natural greetings, varied closings, personality persistence in technical mode, and matched CLI/Discord behavior without reopening accepted safety semantics.
2. **SOCIAL minimum:** add authenticated `principal_id` / audience projection into shared cognition so the enrolled Discord owner is actually represented as Sparks; bind person-scoped MEM/REL/ACT behavior to it. General second-user rollout remains deferred.
3. **MEM + SAFE + CLEAN recovery baseline:** inventory every durable store, define retention/erasure/encryption, create verified backup/restore, then migrate live runtime databases out of tracked Git state. Do not delete or untrack `sofia.db` / `state/sofia.db` until recovery is proved.
4. **Wire accepted primitives:** connect RUN's local lease/supervisor/periodic gate, ACT's queue/delivery ledger, and EVOLVE's approval/execution boundaries into one application-owned orchestration path with no duplicate schedulers or self-approval.
5. **VERIFY foundation:** rebuild VERIFY from current `main`, add revision-pinned evidence manifests and GitHub Actions CI for full/static gates, then add resource/latency, restore, outage, denial and crash-matrix evidence.
6. **REL consolidation:** rebuild stale PRs #12/#13 as one authenticated, non-clingy relationship pipeline using MEM originals and SOCIAL principal evidence. Keep absence/reunion present-tense and source-grounded.
7. **CLEAN branch/doc hygiene:** rebuild stale PR #14; classify tracked DB/log/migration artifacts and old branches/PRs. Retain provenance, but stop treating 300+ commit-behind drafts as merge candidates.
8. **AVATAR/UI next offline lane:** rebuild AVATAR #7 and UI #6 on current `main`; preserve one presentation state across wardrobe, hairstyle, hair/tail color and renderer receipts. Emotion may influence presentation but does not control it. No discrete sexual mode; intimate/emotional dimensions remain context/consent-bound.
9. **OPS/RUN/NET live fleet lane:** deploy the signed agent on Windows/Linux/Pi, prove attestation/enrollment, standing-policy upkeep, workload movement, local service restart, independent watchdog, cross-host fencing, restore and multi-day soak. Only Sparks approves final machine removal.
10. **INTEGRATE/DEV/KNOW live activation:** canary Home Assistant, JMRI, GitHub, Portainer/Hyper-V/Ollama/storage and OpenCode/document workflows with real receipts, rollback and scoped authority. Cloudflare remains deferred.
11. **Reliability/data redundancy:** implement and test the chosen two-data-copy + witness/fencing + independent backup design; measure RPO/RTO rather than promising zero loss.
12. **BODY later hardware phase:** rebuild BODY on current `main`, then real Gaia SSC-32/servo calibration, sensors/power, bounded gait and independent physical E-stop.
13. **ENVIRONMENT operational follow-through:** the shared foundation, narrow NWS provider and persistent HOST location are accepted on `main`; next, optionally canary Home Assistant through INTEGRATE with explicit `environment.home_assistant.read`, then wire machine-location administration into OPS/RUN fleet state. General browsing/search and arbitrary geocoding remain for the later separately authorized NET/web gate.
14. **General web/search last:** only after real 24/7 RUN/OPS acceptance, with separate authorization, provenance and revocation. PR #111 is the already accepted narrow NWS-only exception; it does not broaden into general browsing/search or arbitrary geocoding.

**No implementation, deployment, new data stores, full-suite rerun or live hardware failover test is performed by this roadmap update.**