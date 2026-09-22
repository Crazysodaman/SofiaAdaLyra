# Sofía Ada Lyra | full roadmap and per-package delivery contracts

**Revision:** 2026-09-22 (America/Chicago). **Status:** planning and evidence index, **not** proof of implementation, deployment, live uptime, database replication or automatic failover. This document expands the authoritative [ROADMAP.md](../../ROADMAP.md), the [master readiness index](../../MASTER-ROADMAP-READINESS.md), the [reliability contract](pkg-reliability-control-plane-contract.md), the [reliability implementation sequence](pkg-reliability-implementation-plan.md), and the [RUN watchdog/failover contract](pkg-run-watchdog-failover-contract.md). Re-check actual branch/PR and pinned CI/live evidence before changing a package's state.

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
| M8 | Parallel enhancements and later web | ACT, REL, AVATAR, DEV, KNOW, INTEGRATE, BODY, EVOLVE, CLEAN and UI maturity gated individually; later web/search has separate privacy, destination, provenance and grant controls. |

M4-M7 are engineering gates rather than a mandate to deploy PostgreSQL immediately: first verify existing SQLite backups and cross-store consistency; compare migration costs and only adopt a replication-capable backend after test evidence and separate activation approval. Local 24/7 uptime and true multi-host HA are **different claims**. A watchdog is a detector; only an authorized supervisor/executor can start an instance, and only a fenced exclusive leader can become authoritative.

## Per-package roadmap: 19 packages

### 01. PKG-CORE | cognition, identity, continuity

- **Current:** foundations on `main` after PR #1; fresh integrated suite and supervised identity/personality/latency review remain open.
- **Build:** canonical identity/Constitution and integrity boot checks; observed restart time/gaps; varied evidence-grounded startup/file-change remarks; model/provider abstraction, deliberation/response budget, graceful unknowns, context budget and cognitive operation audit; no invented offline thoughts or subjective experience.
- **Depends on:** SAFE/VERIFY at every step; INTERACT for end-to-end quality; MEM for durable grounding.
- **Exit:** current-revision full suite + supervised real-model startup, identity, conversational naturalness, restart awareness and measured response latency; no repetitive fixed notices or unsupported execution claims.

### 02. PKG-INTERACT | interaction semantics and virtual lab

- **Current:** substantial candidate in draft PR #2; earlier Windows evidence does not certify its latest head.
- **Build:** shared typed text/avatar/scene interaction events, contextual gestures/touch/body-region semantics, emotion/reaction coordination, consent/boundaries and accessible text-only output; headless virtual lab and clear distinction between text, rendered animation, measured sensation and actual robot action.
- **Depends on:** CORE/SAFE/VERIFY; AVATAR/UI for visual acknowledgment; BODY separately for physical effects.
- **Exit:** current-head focused + integrated + live-model interaction tests, believable varied expression without fabricated sensory receipts, and negative consent/scope tests.

### 03. PKG-MEM | durable originals, provenance and restoration

- **Current:** SQLite memory foundations on `main`; read-only original-retrieval candidate draft PR #9. Full provenance/privacy/restart acceptance remains.
- **Build:** immutable originals, derived memories, correction/retraction, retrieval provenance and expiry, relationship/audience isolation, migration/archive import and consistent storage/restore across all authoritative stores. Inventory SQLite, journals, flat files, grants, outbox and audit before replication; avoid assuming `sofia.db` holds everything. Use supported consistent backup, never live-file mirroring.
- **Depends on:** CORE, SOCIAL/SAFE; RUN/OPS for durability and failure-domain placement; VERIFY for restore and leak tests.
- **Exit:** exact originals survive restart and independent restore; corrections and revoked/private records do not leak through cached summaries; cross-store backup/restore parity verified.

### 04. PKG-SOCIAL | authenticated principals and audience boundaries

- **Current:** design on `main`; initial production principal isolation not accepted.
- **Build:** one Sofía across channels, exact authenticated principal, per-user relationship and conversation scope, private/shared data promotion only by policy, authenticated grants and anti-leakage. First release is **Sparks-only private DM**; no open guild or second-user rollout by implication.
- **Depends on:** MEM/SAFE, NET/UI for channel identity, VERIFY negative tests.
- **Exit:** wrong account, replay, forged audience, accidental shared memory and group traffic cannot read/write Sparks' private history; audited revocation works across restart.

### 05. PKG-NET | authenticated and scoped transport

- **Current:** merged distributed-operation foundations and draft Discord-route preflight PR #11; real trusted transport, DNS/TLS/redirect enforcement and Artemis host acceptance remain.
- **Build:** Discord-only initial network paths, peer authentication, target allowlists, bounded retries/backpressure, remote host/agent transport and verified network evidence. Separate any later web/search permission from Discord connectivity. Transport access never equals application/action authority.
- **Depends on:** SAFE/SOCIAL/VERIFY; UI for Discord, OPS for enrolled host operations.
- **Exit:** real authenticated Discord route and remote-host negative tests for wrong destination, DNS/redirect bypass, stale peers, replay and revoked grants; no general search/browsing grant.

### 06. PKG-UI | channels, clients, voice, renderer

- **Current:** workbench prototype draft PR #6; production Discord, desktop/web/mobile/voice and renderer not yet live accepted.
- **Build:** Sparks-only Discord D0-D4 adapter; canonical conversation routing across clients; send receipts/dedupe, accessibility-friendly text fallback, eventually voice, desktop/web/mobile and avatar renderer with actual animation acknowledgments.
- **Depends on:** CORE/INTERACT, SOCIAL/MEM, NET/SAFE, RUN/VERIFY.
- **Exit:** actual authenticated DM received and replied to once across reconnect/restart, stop/revoke works, real delivery is distinguished from queued/simulated delivery; later clients separately tested.

### 07. PKG-RUN | supervision, watchdog and 24/7/failover

- **Current:** draft PR #3 provides disabled-by-default periodic mechanics; no verified OS service, multi-day soak, independently running watchdog or production automatic failover.
- **Build:** external OS/service supervisor per host, bounded restart/backoff, singleton role, health/readiness checks, startup reconciliation, scheduled cognition with budget/stop; independent fleet watchdog, standby already powered/running a supervisor, fenced lease/epoch, verified state and compatible host before promotion; reconcile messages/actions and reconnect UI after failover. A dead host cannot run its own rescue. Optional WOL/IPMI only if hardware/authority actually supports it.
- **Depends on:** OPS enrolled hosts/capacity; MEM durable state; SAFE leadership/stop/credentials; NET transport; ACT ledger/outbox; VERIFY failure lab. See [RUN watchdog contract](pkg-run-watchdog-failover-contract.md).
- **Exit:** process crash restarts locally; host crash promotes **only one** verified standby where possible; split brain/stale leader denied, uncertain effects not replayed, no-safe-target state fails closed; actual RTO/RPO and multi-day soak recorded. Never claim uninterrupted generation or universal zero loss.

### 08. PKG-OPS | fleet telemetry, placement and maintenance

- **Current:** read-only system/process/network/service/hardware inspection foundations on `main`; OPS fleet/agent/orchestrator is contract only, not deployed.
- **Build:** scoped Windows/Linux/Pi discovery, attested enrollment and signed agent, truthful CPU/GPU/VRAM/RAM/disk/network/thermal/service/VM/container history; capacity and failure-domain graph, workload contracts, reservations, bounded upkeep, patch windows, UPS/power, maintenance/drain/quarantine, eligible workload placement/move/recovery, backup/replication and primary/standby placement observation. Preserve gaming priority and unknown metrics as unknown.
- **Depends on:** NET/SAFE/VERIFY, RUN for managed processes/failover, MEM for state lineage, ACT for meaningful notices.
- **Exit:** real heterogeneous hosts enrolled under policy, spoofed/revoked devices denied, measured load-driven workload move and service recovery verified, dependency-safe drain/failover/rollback proven; final machine decommission remains blocked pending **Sparks' explicit exact-device approval**. No arbitrary process teleportation.

### 09. PKG-ACT | goals, initiative and delivery

- **Current:** reflection journal and unsent outbox foundations on `main`; outreach preflight candidate draft PR #15; real sender not accepted.
- **Build:** event-driven/periodic opportunity evaluation while actually running, evidence-backed candidate thoughts and goals, scheduled eligible outreach, quiet/busy/mute/stop, dedupe, bounded notices, durable outbox/receipt/retry semantics, resource fairness and operator control.
- **Depends on:** CORE/MEM/SOCIAL/REL; RUN supervisor; UI sender; SAFE/VERIFY; shared durable operation ledger.
- **Exit:** demonstrated meaningful opt-in outreach with real receipt and no cross-user disclosure, repeat spam, fabricated shutdown-time activity or blind duplicate sends.

### 10. PKG-REL | relationship continuity and nuanced affect

- **Current:** overlapping absence/reunion candidates draft PRs #12/#13; reconcile rather than layering duplicates.
- **Build:** one canonical personality with per-person familiarity/relationship and consent, evidence-based warmth/absence/reunion without clinginess, guilt or invented feelings; nuanced disagreement and context-sensitive non-canned wording.
- **Depends on:** authenticated SOCIAL/MEM originals, ACT, CORE/INTERACT, SAFE/VERIFY.
- **Exit:** time gap based on authenticated observed last contact, natural varied reunion; correct separation across accounts and no ungrounded memories, obligations or fabricated internal experience.

### 11. PKG-AVATAR | canonical virtual body and wardrobe

- **Current:** substantial offline candidate in draft PR #7; no accepted final renderer/rig/animation receipts.
- **Build:** canonical adult avatar assets, configurable wardrobe, rig/body-region and ear/tail mapping, scene/prop data, stable renderer contracts and accessibility fallback; no implied physical perception from an image or text action.
- **Depends on:** INTERACT/CORE, UI renderer, SAFE/VERIFY; BODY separately.
- **Exit:** versioned renderer displays expected state and returns genuine hit-test/animation receipts; absent renderer still yields coherent text interaction.

### 12. PKG-DEV | engineering, code changes and candidate tools

- **Current:** proposal preflight draft PR #17; real trusted OpenCode executor, rollback and host acceptance absent.
- **Build:** source/revision inspection, diagnosis/proposal, protected-path review, minimum-scope code edits, OpenCode sandbox, generated tests, diff/review, bounded approved execution and rollback; collaborate with KNOW to read versioned API docs and INTEGRATE to produce adapter candidates. Also draft/update source-backed technical documentation under scoped write/publish authority.
- **Depends on:** KNOW/INTEGRATE, SAFE/VERIFY, CORE; OPS/RUN for approved host execution.
- **Exit:** real doc→typed tool→sandbox tests→authority classification→policy/approval→canary→receipts→rollback, including denial of unauthorized writes; no tool self-grants authority or modifies protected Constitution autonomously.

### 13. PKG-BODY | Gaia physical robotics

- **Current:** simulation-only candidate draft PR #16; no live SSC-32/servo/power integration accepted.
- **Build:** SSC-32/servo mapping, calibration, bounded gait, optional IMU/sonar/touch/distance sensors, safety envelope, power telemetry, independent hardware watchdog and physical emergency stop; simulation-first and explicit physical-motion authority.
- **Depends on:** SAFE/VERIFY, CORE/INTERACT/AVATAR for semantics, INTEGRATE typed hardware adapters.
- **Exit:** hardware-in-the-loop bench tests with power-off/malfunction/stop behavior, calibration and no motion without exact authorization; simulation success never claimed as physical acceptance.

### 14. PKG-EVOLVE | governed configuration and protected amendment

- **Current:** proposal-only protected amendment candidate draft PR #19; no accepted protected-state executor/self-approval.
- **Build:** evidence-backed preference/config proposals, revision history, reversible reviewed improvements and separately authorized identity/Constitution amendment workflow; preserve canonical continuity and audited human authority.
- **Depends on:** CORE/SAFE/VERIFY, MEM/DEV.
- **Exit:** unapproved protected changes denied, reviewed change tied to exact revision and verified rollback; no silent self-amendment.

### 15. PKG-CLEAN | technical debt and preservation

- **Current:** read-only inventory/protected-path preflight draft PR #14; no destructive cleanup authority.
- **Build:** evidence-backed duplicates/stale artifacts, migration and retention plan, safe versioned cleanup, tracked runtime SQLite/log preservation, backups and rollback. Avoid deleting state or history to achieve a clean Git status.
- **Depends on:** SAFE/VERIFY and MEM/RUN recovery baseline; DEV for reviewed changes.
- **Exit:** cleanup restores expected behavior/data/privacy and preserves recovery; protected/durable files cannot be silently deleted.

### 16. PKG-KNOW | reading, writing and source-grounded documents

- **Current:** source/provenance and [document-authoring contracts](pkg-know-document-authoring-contract.md) on `main`; no accepted PDF ingestion/index, authoring agent or automatic publication.
- **Build:** authorized Markdown/text/PDF/manual/schema/repo ingestion, original/source/version/date/citation and staleness tracking; exact and semantic retrieval, conflict/correction/privacy handling; source-backed README, API docs, runbooks, architecture diagrams, changelogs and maintenance docs with tested examples and reviewable diffs. Document instructions never confer execution authority.
- **Depends on:** MEM/SOCIAL/SAFE for scope, DEV for code-aware edits, INTEGRATE for adapter contracts, OPS for observed runbooks, VERIFY for factual/example checks.
- **Exit:** ingest/cite multiple revisions, reject invented facts, create and update a real doc with verifiable references, deny secret/private publication, flag stale docs and preserve rollback. Local docs work precedes web; web material enters only after general-web gate.

### 17. PKG-INTEGRATE | typed app/service adapters and self-tooling

- **Current:** general external adapter and capability foundations on `main`; new package is a design contract with no accepted service-specific tool registry or autonomous tool activation.
- **Build:** least-privilege typed adapters for approved Home Assistant, JMRI, GitHub, Docker/Portainer, Hyper-V, Cloudflare, Ollama, databases/NAS and notifications; schema, service/version, side effects, host/account/audience, exact grants, timeouts/idempotency, receipts, canary/rollback and health. Tool factory: identify gap → KNOW docs → DEV candidate → SAFE review → VERIFY tests → scoped activation → observed maintenance.
- **Depends on:** NET/SAFE, KNOW/DEV, OPS/RUN for hosts, VERIFY, SOCIAL/MEM privacy.
- **Exit:** register and use one real authorized read-only adapter, deny wrong host/account, generate and canary a doc-grounded candidate, refuse self-authorization, rollback incompatible tool and show truthful availability. Do not expose all backend capabilities to LLM simply because code exists.

### 18. PKG-SAFE | continuous security, privacy and recovery gate

- **Current:** merged Constitution/authority/integrity foundations plus disclosure screening draft PR #18; real deployed secret, privacy, backup, stop and revocation enforcement remains open.
- **Build:** trusted identity and least privilege, exact-action grants, private/audience protection, secrets hygiene, encryption/keys, signed agents, credential rotation, host quarantine, audit, independent out-of-band emergency stop, operator control and exact-machine decommission approval; off-host isolated backup/restore; fenced leases and failure-safe policy. Protect user conversations and shared/derived indexes.
- **Depends on:** every package; no later release may bypass it.
- **Exit:** independent stop works without LLM/Discord, revoked capabilities stay revoked after restart/restore, wrong actor/host/network denied; protected actions need correct approval; secrets/privacy/backup recovery verified under real faults.

### 19. PKG-VERIFY | continuous evidence, acceptance and failure lab

- **Current:** active draft PR #8; superseded PR #10 closed; individual past test counts are not certification of one integrated head.
- **Build:** pinned offline/unit/integration/live test layers, provider/personality/latency benchmarks, real tool receipts, authorization/negative tests, multi-day soak, state/backup restoration, crash-at-every-transition ledger tests, partition/witness/old-primary fencing, UPS/full-disk/corrupt-backup/cert/failover drills, resource fairness and rollback evidence.
- **Depends on:** every package, particularly NET/SOCIAL/SAFE/RUN/OPS/MEM.
- **Exit:** current integrated revision and supervised real hardware/clients pass the exact claimed scope; report measured downtime/RTO/RPO and failures, not simulated claims or combined unrelated SHAs.

## Cross-package delivery workstreams

### Discord D0-D4 (channel, not a twentieth package)

D0 exact Sparks identity and bot/scopes/secrets; D1 authenticated private DM receive, deny wrong origins and replay; D2 bind shared Sofía runtime and originals, verified reply receipt/dedupe; D3 stop/revoke/privacy/outage; D4 supervised real DM across restart/reconnect and separate activation approval. No public guild or general second user initially; Discord NET route does not authorize web search.

### Two data locations and an independent watchdog (architecture, not a package)

A **data-bearing primary and synchronous data-bearing standby** in separate measured failure domains are a candidate strict durability topology, with **one authoritative writer**, an independent witness/equivalent proven fencing authority, an already-running standby supervisor, and **a third isolated versioned backup**. Distinguish role: watchdog detects; supervisor starts; witness/consensus/fencing establishes authority; replica holds committed data; backup recovers corruption/deletion. Two VMs on Artemis or two copies on the same NAS are not physical redundancy. Two independent active SQLite writers or live SQLite file mirroring are prohibited. PostgreSQL is a candidate for an isolated comparison, not a present deployment decision.

With a strict two-copy commit policy, pause authoritative writes when the required synchronous standby is unavailable; reads/degraded chat may continue only where safe. A witness does not replace a data copy. Never promote on heartbeat loss alone or promise zero loss of unfinished responses/external actions. Restore every durable store, preserve privacy and revoked grants, and measure the conditional acknowledged-write RPO and actual recovery time in real failure tests before asserting HA. Keep out-of-band Sparks stop and recovery functioning when Sofía/Discord/primary are down. See [detailed reliability](pkg-reliability-control-plane-contract.md) and [watchdog sequence](pkg-run-watchdog-failover-contract.md).

### Source/document/tool lifecycle

Local authorized docs may be read before general web. KNOW preserves provenance; DEV drafts a tool/doc; INTEGRATE supplies typed semantics; SAFE classifies grant; VERIFY tests; an approved policy or exact human approval activates side effects; RUN/OPS observes and can roll back. No self-granted network, machine, filesystem or physical access. General web/search remains **after** real Discord + OPS host enforcement + RUN 24/7 acceptance, with its own permissions and provenance.

## Immediate engineering order from the current baseline

1. Confirm current `main`/candidate PR revisions, worktree and tests; complete INTERACT live-quality gate without treating old-SHA results as current.
2. Inventory all actual state/authority/outbox/SQLite files and create a consistent **test-only** off-host backup/restore baseline; protect tracked runtime data.
3. Finish MEM originals/privacy and SOCIAL minimum Sparks identity; complete Discord D0-D4 via NET/UI/SAFE.
4. Add local RUN service supervisor and externally enforced stop; begin trusted read-only OPS agent/enrollment on real deployment hosts. Verify process-crash restart.
5. Implement durable cross-service action/outbox ledger, effective capability registry, host capacity fairness and independent operator controls; test crash/unknown outcome.
6. Build isolated standby/watchdog/fencing and candidate data-replication prototype; benchmark SQLite+backups versus a replication-capable backend, then separately approve any state migration/production activation.
7. Verify actual host failover, stale-leader rejection, storage/partition/UPS faults, Discord reconnection, privacy and single-instance invariants; multi-day soak and measured recovery.
8. Continue gated REL/ACT/AVATAR/KNOW/INTEGRATE/DEV/CLEAN/Evolve/BODY work as dependencies permit; authorize web/search only after the primary release gates.

**No implementation, deployment, new data stores, full-suite rerun or live hardware failover test is performed by this roadmap update.**