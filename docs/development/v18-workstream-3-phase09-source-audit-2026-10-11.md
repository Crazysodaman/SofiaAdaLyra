# Workstream 3 Phase 09: 66-task LIFE, GOALS, RUN source audit

**Date/head:** 2026-10-11, GitHub `main` `419fd9e7976b17dafb39a7ade9aa67e75cfc86e7`. This source-first audit covers all 66 original CA IDs in V18 Phase 09. The 700-task master and Workstream 1 global evidence ledger are not changed.

**Scope:** Source entrypoint inspection of canonical LIFE/GOALS/RUN/CREATIVE implementation, plus a full original-ID inventory. Detailed clauses above are verified only to the depth stated: several are real production traces, others are pending per-function audits or original research/acceptance. No tests, CI, LLM calls, host actions or deployments were performed. `code_present_unverified` is not `accepted`.

**Known production path:** `SofiaApplication → background_runtime → SelfDirectedLifeCoordinator.tick → LifeStore (canonical SQLite) / DurableWorkStore (original RUN events) → CreativeExplorer.verified_preview / life.validation typed objectives → scoped GOALS update or explicit review/abstention`. RUN admission uses canonical one-use creative authorization, original project revision CAS, and separate runtime SAFE execution authority.

## Original 66-task source matrix

| CA ID | Shared ledger state at audit | This pass assessment | Key source location |
|---|---|---|---|
| **CA-101** | partial_wiring | partial original source | `src/sofia/life/coordinator.py` |
| **CA-102** | unassessed | production source present, tests deferred | `src/sofia/life/coordinator.py` |
| **CA-103** | code_present_unverified | source-wired; tests deferred | `src/sofia/life/coordinator.py` |
| **CA-104** | partial_wiring | source-wired partially | `src/sofia/life/coordinator.py` |
| **CA-105** | partial_wiring | production partial traced | `src/sofia/life/coordinator.py` |
| **CA-106** | partial_wiring | production partial traced | `src/sofia/life/coordinator.py` |
| **CA-107** | unassessed | source candidate present | `src/sofia/life/coordinator.py` |
| **CA-108** | unassessed | source-wired, testing deferred | `src/sofia/life/coordinator.py` |
| **CA-109** | unassessed | verification deferred | `src/sofia/life/coordinator.py` |
| **CA-110** | partial_wiring | production partial traced | `src/sofia/life/coordinator.py` |
| **CA-111** | code_present_unverified | source-wired; tests deferred | `src/sofia/life/coordinator.py` |
| **CA-112** | partial_wiring | source-wired partially | `src/sofia/life/coordinator.py` |
| **CA-113** | partial_wiring | production partial traced | `src/sofia/life/coordinator.py` |
| **CA-114** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-115** | unassessed | verification deferred | `src/sofia/life/coordinator.py` |
| **CA-201** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-202** | unassessed | production partial, acceptance deferred | `src/sofia/run/work.py` |
| **CA-203** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-204** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-205** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-206** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-207** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-208** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-209** | unassessed | confirmed gap candidate | `src/sofia/run/work.py` |
| **CA-210** | unassessed | source-to-entrypoint trace open | `src/sofia/run/work.py` |
| **CA-601** | unassessed | production partial traced | `src/sofia/creative/service.py` |
| **CA-602** | unassessed | source-to-entrypoint trace open | `src/sofia/creative/service.py` |
| **CA-603** | unassessed | source-to-entrypoint trace open | `src/sofia/creative/service.py` |
| **CA-604** | unassessed | source-wired partially | `src/sofia/creative/service.py` |
| **CA-605** | unassessed | source-to-entrypoint trace open | `src/sofia/creative/service.py` |
| **CA-606** | unassessed | source candidate, UI missing | `src/sofia/creative/service.py` |
| **CA-607** | unassessed | source candidate present | `src/sofia/creative/service.py` |
| **CA-608** | unassessed | source-to-entrypoint trace open | `src/sofia/creative/service.py` |
| **CA-609** | unassessed | source-to-entrypoint trace open | `src/sofia/creative/service.py` |
| **CA-610** | unassessed | source-to-entrypoint trace open | `src/sofia/creative/service.py` |
| **CA-1301** | unassessed | source candidate present | `src/sofia/life/model.py` |
| **CA-1302** | unassessed | source-to-entrypoint trace open | `src/sofia/life/model.py` |
| **CA-1303** | unassessed | source candidate present | `src/sofia/life/model.py` |
| **CA-1304** | unassessed | source-to-entrypoint trace open | `src/sofia/life/model.py` |
| **CA-1305** | unassessed | source-to-entrypoint trace open | `src/sofia/life/model.py` |
| **CA-1306** | unassessed | source-to-entrypoint trace open | `src/sofia/life/model.py` |
| **CA-1307** | unassessed | source-to-entrypoint trace open | `src/sofia/life/model.py` |
| **CA-1601** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-1602** | unassessed | source candidate present | `src/sofia/life/coordinator.py` |
| **CA-1603** | unassessed | production partial traced | `src/sofia/life/coordinator.py` |
| **CA-1604** | unassessed | source candidate present | `src/sofia/life/coordinator.py` |
| **CA-1605** | unassessed | source-to-entrypoint trace open | `src/sofia/life/coordinator.py` |
| **CA-1606** | unassessed | production partial traced | `src/sofia/life/coordinator.py` |
| **CA-2401** | unassessed | confirmed unproven | `src/sofia/application/decision_trace.py` |
| **CA-2402** | unassessed | production partial traced | `src/sofia/application/decision_trace.py` |
| **CA-2403** | unassessed | source-to-entrypoint trace open | `src/sofia/application/decision_trace.py` |
| **CA-2404** | unassessed | source-to-entrypoint trace open | `src/sofia/application/decision_trace.py` |
| **CA-2405** | unassessed | verification deferred | `src/sofia/application/decision_trace.py` |
| **CA-2406** | unassessed | source-to-entrypoint trace open | `src/sofia/application/decision_trace.py` |
| **CA-2407** | unassessed | source partial traced | `src/sofia/application/decision_trace.py` |
| **CA-2408** | unassessed | production partial traced | `src/sofia/application/decision_trace.py` |
| **CA-3501** | partial_wiring | research gap remains | `src/sofia/life/validation.py` |
| **CA-3502** | unassessed | research gap remains | `src/sofia/life/validation.py` |
| **CA-3503** | unassessed | research gap remains | `src/sofia/life/validation.py` |
| **CA-3504** | unassessed | research/independent proof open | `src/sofia/life/validation.py` |
| **CA-3505** | unassessed | research gap remains | `src/sofia/life/validation.py` |
| **CA-3506** | unassessed | research/independent proof open | `src/sofia/life/validation.py` |
| **CA-3507** | unassessed | research/independent proof open | `src/sofia/life/validation.py` |
| **CA-3508** | unassessed | research/independent proof open | `src/sofia/life/validation.py` |
| **CA-3509** | unassessed | research/independent proof open | `src/sofia/life/validation.py` |
| **CA-3510** | unassessed | research gap remains | `src/sofia/life/validation.py` |

## Original wording and open evidence

### CA-101

- [ ] **CA-101 [GAP]** Connect trusted, eligible ordinary observations and experiences to LIFE interest creation/revision, with confidence, evidence, and optional retirement. `revise_interest()` exists, but production experience-to-interest wiring was not found.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** LIFE interest revision and source-linked experiences exist. Automatic eligible ordinary observation→interest policy must be checked at actual background ingestion.

**Audit state:** partial original source; tests not run; no acceptance conferred.

### CA-102

- [ ] **CA-102 [EXISTS → VERIFY]** Keep evidence-gated independent project suggestion and project activation from `consider_new_project()`, with busy/quiet/resource and daily-budget gating.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Daily idea attempt, resource and quiet gating and project admission are present; exact user-run restart/idle verification missing.

**Audit state:** production source present, tests deferred; tests not run; no acceptance conferred.

### CA-103

- [ ] **CA-103 [GAP]** Expand `SelfDirectedLifeCoordinator.tick()` beyond first-artifact scheduling to inspect finished jobs and enter automatic review.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** LIFE.tick reviews completed RUN jobs, verifies creative receipts and calls independent objective inspection. Original ledger says code_present_unverified.

**Audit state:** source-wired; tests deferred; tests not run; no acceptance conferred.

### CA-104

- [ ] **CA-104 [GAP]** Trigger grounded `evaluate_artifact()` for completed outputs, recording technical checks, personal judgment, objective results, evidence, and preference changes.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Actual independent evaluation and experience recording exist; subjective personal judgment and preference propagation need source-scoped review.

**Audit state:** source-wired partially; tests not run; no acceptance conferred.

### CA-105

- [ ] **CA-105 [GAP]** Independently decide to critique, revise, produce another artifact, advance a milestone, pause, abandon, or complete a project. Require justified limits on rework and cost.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** LIFE critique→bounded revision→completed/paused decisions exist; full optional abandon/produce-next milestone matrix remains open.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-106

- [ ] **CA-106 [GAP]** Automatically reconcile LIFE state with canonical GOALS and RUN receipts after each decision, including failures, rejection, and uncertain results.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Terminal original RUN event, GOALS blocked/pause/expired status handling and exact project revision admission are source-wired. Full race matrix untested.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-107

- [ ] **CA-107 [GAP]** Turn completed projects, failures, and meaningful lessons into future eligible experiences and interests, closing the cycle without inventing observations.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Original experiences recorded after reviewed project outcomes; future interest candidate admission from failure/learning not fully traced.

**Audit state:** source candidate present; tests not run; no acceptance conferred.

### CA-108

- [ ] **CA-108 [VERIFY]** Preserve the valid choice of inactivity; no artificial work creation, no endless project spawning, and no forced messaging to Sparks.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** select_activity has genuine inactivity and quiet; silence and anti-loop 7-day evidence needs tests.

**Audit state:** source-wired, testing deferred; tests not run; no acceptance conferred.

### CA-109

- [ ] **CA-109 [VERIFY]** Verify a project can continue over multiple days and after restart without a user prompt, and can voluntarily end.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Persisted LIFE projects and background ticks exist, but complete restart/absence campaign not executed.

**Audit state:** verification deferred; tests not run; no acceptance conferred.

### CA-110

- [ ] **CA-110 [GAP]** Add a durable project `review_due` / `awaiting_verification` / `next_milestone_due` decision policy derived from existing project/jobs/evaluation records, using idempotent keys rather than an independent new state machine.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** pending_work_review and status-derived decisions exist, original job evidence and CAS protect admission. Universal durable review_due/next-milestone schedule not proven.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-111

- [ ] **CA-111 [GAP]** After a successful RUN receipt, verify exact artifact hash/revision through `CreativeExplorer.verified_preview()`, gather objective-specific checks, then prepare an eligible critique request. Never equate a file's existence with success.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** CreativeExplorer.verified_preview and source receipt/objective checker run before completion or revision. Original ledger code_present_unverified.

**Audit state:** source-wired; tests deferred; tests not run; no acceptance conferred.

### CA-112

- [ ] **CA-112 [GAP]** Trigger `evaluate_artifact()` from the recurring LIFE worker with typed objective results, bounded personal judgment, source receipts and failure/unknown handling; speculative LLM critique alone is not evidence.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Recurring tick persists objective-scoped independent grades and unknown taste; optional model critique cannot supply technical PASS.

**Audit state:** source-wired partially; tests not run; no acceptance conferred.

### CA-113

- [ ] **CA-113 [GAP]** Implement a policy-driven transition table: `CREATE → VERIFY → CRITIQUE → REVISE | COMPLETE | PAUSE | ABANDON`; track milestone status using the already implemented `update_milestone()` and `complete()` methods.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** CREATE/VERIFY/critique/revision/completion and milestone replay are coded; complete transition/event matrix still requires review.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-114

- [ ] **CA-114 [GAP]** Add bounded curiosity/initiative admission: novelty, relevance, expected learning value, goal importance, uncertainty, resource cost and user interruption cost. Score only eligible opportunities; no automatic mutation or new permissions.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** LIFE coordinator has application-owned tick, independent artifact review, source/GOALS/RUN outcomes, partial recovery and bounded optional work. No single method establishes all multi-day or audit acceptance clauses.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-115

- [ ] **CA-115 [VERIFY]** Ensure 3+ consecutive eligible idle ticks do not create duplicate work; after completion, restart or a model failure, the coordinator resumes or chooses quiet without fabrication or an infinite review loop.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`, `src/sofia/life/validation.py`.

**Audit observation/open clause:** Idempotent original RUN work and repeated inactivity projections exist, but complete restart/callback failure matrix unexecuted.

**Audit state:** verification deferred; tests not run; no acceptance conferred.

### CA-201

- [ ] **CA-201 [VERIFY]** Validate Project Forge and native creative adapters on real Windows/Venus, including installed dependencies and actual artifact previews.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-202

- [ ] **CA-202 [VERIFY]** Validate RUN cancellation, deadline handling, resource budgets, bounded queues/workers, failure reporting, interrupted-job recovery, and idempotency.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** DurableWorkStore/Manager handle leases, cancel/deadline and original source receipts; real CPU/memory and interrupted worker scenarios require tests.

**Audit state:** production partial, acceptance deferred; tests not run; no acceptance conferred.

### CA-203

- [ ] **CA-203 [VERIFY]** Run actual OpenCode/DEV candidate build and tests under approved scope; retain operator review before any apply/commit/push/release operation.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-204

- [ ] **CA-204 [VERIFY]** Record verifiable receipts and explicitly represent unknown outcomes; do not manufacture success or retry uncertain remote actions blindly.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-205

- [ ] **CA-205 [VERIFY]** Require configured safe OS-level isolation when needed; a detached worktree alone is not a security sandbox.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-206

- [ ] **CA-206 [VERIFY]** Check Fleet, backup, restart, release, and state recovery when independent LIFE tasks run under CPU/memory pressure.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-207

- [ ] **CA-207 [VERIFY]** Treat retries by operation class: idempotent local reads may retry; uncertain external mutations must await a verified receipt or operator resolution before replay.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-208

- [ ] **CA-208 [VERIFY]** Test user interruption and cancellation mid-critique, mid-artifact, mid-voice delivery and mid-remote diagnostic; preserve foreground priority and never strand an authority grant.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-209

- [ ] **CA-209 [GAP]** Implement capability-specific resource admission for creative/LLM/asset workloads, using live usage and Fleet placement evidence; honor the Windows restricted-worker identity rather than assuming a worktree is a sandbox.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN resource_cost and LIFE daily budgets are nominal admission; capability-specific live host/Fleet CPU/GPU and Windows worker identity not yet established.

**Audit state:** confirmed gap candidate; tests not run; no acceptance conferred.

### CA-210

- [ ] **CA-210 [VERIFY]** Add explicit rollback and repair plans for preference drift, corrupted associative weights, failed world edits, stale project jobs and model/config changes, with an audit trail in canonical storage.

**Related production source:** `src/sofia/run/work.py`, `src/sofia/life/coordinator.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** RUN has bounded queue/workers and canonical terminal receipts, LIFE has one-use creative admission and project review. OS isolation, resource proof, real Venus behavior and multi-host tests require separate paths.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-601

- [ ] **CA-601 [GAP]** Enable multi-stage personally selected creative pursuits, not only starter templates or one-off generated artifacts.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Original text/story drafting, revision and milestones are live; broader multi-stage creative workflows with success-dependent media need more.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-602

- [ ] **CA-602 [EXISTS → GAP]** First verify the documented text/story/SVG/OBJ/animation/WAV/game/simulation native adapters on Venus; only then evaluate additional media applications as individually authorized, verified adapters.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Creative Project Forge and native verified artifact adapters are reused; LIFE authors real text/story with deterministic objective critique. Multi-modal creative skills, world interactions and private portfolio require further source proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-603

- [ ] **CA-603 [EXISTS → GAP]** Reuse `create_project_space()` and `place_artifact()` plus world stores/interaction receipts; connect subsequent verified world interactions to reflection, memory, preferences and future LIFE choices.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Creative Project Forge and native verified artifact adapters are reused; LIFE authors real text/story with deterministic objective critique. Multi-modal creative skills, world interactions and private portfolio require further source proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-604

- [ ] **CA-604 [GAP]** Let Sofía evaluate her own artifacts against explicit technical goals plus bounded aesthetic preferences, revising or stopping when appropriate.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Independent technical objective evaluation exists and personal judgment remains UNKNOWN until grounded; aesthetic preference adaptation not universal.

**Audit state:** source-wired partially; tests not run; no acceptance conferred.

### CA-605

- [ ] **CA-605 [VERIFY]** Test independent activity during long absence without repetitive task loops, wasted model wakeups, disk growth, or notifications.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Creative Project Forge and native verified artifact adapters are reused; LIFE authors real text/story with deterministic objective critique. Multi-modal creative skills, world interactions and private portfolio require further source proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-606

- [ ] **CA-606 [GAP]** Add a private hobby/portfolio index over existing LIFE projects, CreativeStore revisions and world-space links; explain why an item was made and how it changed without invented artistic history.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Project causal trace exists; full private browsable hobby portfolio over projects/revisions/world links not established.

**Audit state:** source candidate, UI missing; tests not run; no acceptance conferred.

### CA-607

- [ ] **CA-607 [GAP]** Add controlled exploration budgets (time, model wakeups, disk bytes, concurrent tasks) for optional experimentation and a hard per-day project-initiation limit.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Daily draft budget, storage size limits and concurrent RUN are bounded; CPU/GPU/wakeup and per-topic exploration budgets not complete.

**Audit state:** source candidate present; tests not run; no acceptance conferred.

### CA-608

- [ ] **CA-608 [GAP]** Make world navigation/interactions visible in activity selection only after actual `WorldEditor` and renderer receipts; a simulated lab activity is not physical action.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Creative Project Forge and native verified artifact adapters are reused; LIFE authors real text/story with deterministic objective critique. Multi-modal creative skills, world interactions and private portfolio require further source proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-609

- [ ] **CA-609 [GAP]** Separate interests she chooses privately, projects she offers collaboratively, and requested user assignments; support explicit project sharing permissions and quiet private activity.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Creative Project Forge and native verified artifact adapters are reused; LIFE authors real text/story with deterministic objective critique. Multi-modal creative skills, world interactions and private portfolio require further source proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-610

- [ ] **CA-610 [VERIFY]** Measure originality/usefulness and revision quality with objective validators plus human review; do not certify aesthetic taste based solely on model self-rating.

**Related production source:** `src/sofia/creative/service.py`, `src/sofia/life/coordinator.py`, `src/sofia/creative/world_bridge.py`.

**Audit observation/open clause:** Creative Project Forge and native verified artifact adapters are reused; LIFE authors real text/story with deterministic objective critique. Multi-modal creative skills, world interactions and private portfolio require further source proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1301

- [ ] **CA-1301 [GAP]** Define a `MotivationSignal` *derived projection* with evidence-linked curiosity, learning progress, unfinished commitment, novelty, utility, estimated work cost, risk, and user-interruption cost. Never store it as an independent source of truth.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** MotivationSignal derived type and comparison routine exist; evidence/safety/interruption cost semantics need exact entrypoint audit.

**Audit state:** source candidate present; tests not run; no acceptance conferred.

### CA-1302

- [ ] **CA-1302 [GAP]** Add an intrinsic-learning-progress heuristic that rewards reducing *verified* uncertainty or improving a skill; prevent novelty-seeking loops and treating model excitement as proof of value.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** MotivationSignal, goal-backed optional selection, resource budgets and choice of inactivity exist. No source-only proof of learning versus random practice or safe virtual-world curricula.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1303

- [ ] **CA-1303 [GAP]** Add `explore | practice | complete | rest | ask | decline` as optional, policy-constrained LIFE decision candidates, with a valid no-activity outcome.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** Quiet, select and optional project choices exist; all explore/practice/ask/decline alternatives with verified intent not confirmed.

**Audit state:** source candidate present; tests not run; no acceptance conferred.

### CA-1304

- [ ] **CA-1304 [GAP]** Add bounded exploratory curricula for one private hobby in the virtual world: start simple, increase difficulty only on observed success, and stop after repeated failures.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** MotivationSignal, goal-backed optional selection, resource budgets and choice of inactivity exist. No source-only proof of learning versus random practice or safe virtual-world curricula.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1305

- [ ] **CA-1305 [VERIFY]** Test 24-hour no-input behavior: no compulsory task spawning, no repetitive pseudo-curiosity, no unwanted outreach, and no unauthorized model wakeups.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** MotivationSignal, goal-backed optional selection, resource budgets and choice of inactivity exist. No source-only proof of learning versus random practice or safe virtual-world curricula.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1306

- [ ] **CA-1306 [GAP]** Support a revisable, evidence-backed `interest exploration budget` per topic, including cooling-off and voluntary disinterest, reusing LIFE interest status and RUN budgets.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** MotivationSignal, goal-backed optional selection, resource budgets and choice of inactivity exist. No source-only proof of learning versus random practice or safe virtual-world curricula.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1307

- [ ] **CA-1307 [VERIFY]** Measure actual knowledge/skill gains versus a random or fixed priority curriculum, not just the number of activities initiated.

**Related production source:** `src/sofia/life/model.py`, `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Audit observation/open clause:** MotivationSignal, goal-backed optional selection, resource budgets and choice of inactivity exist. No source-only proof of learning versus random practice or safe virtual-world curricula.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1601

- [ ] **CA-1601 [GAP]** Add a read-only derived goal dependency/priority view: short-term tasks, long-term projects, prerequisites, resource conflicts, approval blockers and evidence needed for completion.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/goals/service.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** Source contains compare_optional_choices and pending_work_review, canonical GOALS and workload placement. Real long-term dependency projections and outcome-dependent choice need task-specific caller audit.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1602

- [ ] **CA-1602 [GAP]** Add pre-execution comparison of `continue | switch | postpone | ask | abandon` against estimated utility, uncertainty, risk, privacy and interruption costs.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/goals/service.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** compare_optional_choices evaluates bounded hypothetical alternatives; utility and uncertainty/approval gating need full read.

**Audit state:** source candidate present; tests not run; no acceptance conferred.

### CA-1603

- [ ] **CA-1603 [GAP]** Evaluate counterfactual project choices in a local simulation/planning envelope; mark hypothetical outcomes and do not apply them to canonical world truth.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/goals/service.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** Existing alternative comparison is explicitly hypothetical and not canonical world truth; downstream UI/decision visibility needs confirmation.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-1604

- [ ] **CA-1604 [GAP]** Detect blocked progress and emit an honest next-action decision: gather evidence, ask for approval, stop, wait for tool recovery, or choose another eligible goal.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/goals/service.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** pending_work_review surfaces approval waits, missing receipts and technical failures; specific next action execution still review-only.

**Audit state:** source candidate present; tests not run; no acceptance conferred.

### CA-1605

- [ ] **CA-1605 [VERIFY]** Test conflicting priorities: user foreground work vs hobbies, Gaia simulator vs physical hardware, low disk space vs graphics generation, and unfinished user assignment vs private interest.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/goals/service.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** Source contains compare_optional_choices and pending_work_review, canonical GOALS and workload placement. Real long-term dependency projections and outcome-dependent choice need task-specific caller audit.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-1606

- [ ] **CA-1606 [VERIFY]** Prove deadlines, permission denials, operator stop and canonical GOALS receipts outrank any motivation, connectome output or self-assessed personal preference.

**Related production source:** `src/sofia/life/coordinator.py`, `src/sofia/goals/service.py`, `src/sofia/ops/placement.py`.

**Audit observation/open clause:** Operator stop, GOALS transitions, SAFE gateway, post-LLM check and atomic LIFE revision fence are present; multi-source concurrent test deferred.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-2401

- [ ] **CA-2401 P1 [GAP]** Design a **read-only CompanionWorkspace projection** over existing Cognition v2 Turn Kernel focus, NEURO snapshot, verified LIFE/GOALS, eligible MEM and current Presence observations. Do not persist a second semantic authority; acceptance: one bounded projection names source revision/evidence for each field.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** Read-only CompanionWorkspace class/active projection not located in searched production paths; existing LIFE/NEURO/GOALS remain separate.

**Audit state:** confirmed unproven; tests not run; no acceptance conferred.

### CA-2402

- [ ] **CA-2402 P1 [GAP]** Map real `WorkResult` states to LIFE next decisions with explicit *retry-safe `UNCERTAIN` settlement*. Do not let a result classified `completed` settle every brief objective; independently prove objective-specific predicates. Acceptance: distinct test for every work status.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** Original RUN events settle FAILED/BLOCKED/CANCELLED/UNCERTAIN without retry; completed outputs still require actual validator.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-2403

- [ ] **CA-2403 P1 [GAP]** Add an **epistemic reason recorder** at the interface between Cognition v2 proposals and LIFE selection: chosen action, rejected alternatives, missing observation, estimated cost, current goal and applicable policy. Record a concise decision explanation, **not hidden LLM reasoning**.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** LIFE offers causal trace and RUN outcome reconciliation; separate DECISION trace and background composition exist. A combined read-only CompanionWorkspace and COGNITION epistemic reason chain need proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-2404

- [ ] **CA-2404 P1 [GAP]** Add **prospective commitments** as existing GOALS/ACT-scheduled candidates, distinguishing user commitments, project intentions and purely imagined plans; make completed/declined/expired events settle visibly and honestly.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** LIFE offers causal trace and RUN outcome reconciliation; separate DECISION trace and background composition exist. A combined read-only CompanionWorkspace and COGNITION epistemic reason chain need proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-2405

- [ ] **CA-2405 P1 [VERIFY]** Stress simultaneous foreground turn, NEURO refresh, LIFE tick, ACT delivery and DEV worker. Prove no resource inversion, duplicate state owner, write race or starvation; test cancellation and stop while a reviewer is active.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** Multiple foreground/background tasks exist, but real multi-thread exact-host stress tests have not run.

**Audit state:** verification deferred; tests not run; no acceptance conferred.

### CA-2406

- [ ] **CA-2406 P1 [GAP]** Integrate observed failures and verified successes into an **outcome appraisal** projection for EMOTION/PERSONALITY, carefully separating inferred affective labels from physical feelings or fabricated emotional evidence.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** LIFE offers causal trace and RUN outcome reconciliation; separate DECISION trace and background composition exist. A combined read-only CompanionWorkspace and COGNITION epistemic reason chain need proof.

**Audit state:** source-to-entrypoint trace open; tests not run; no acceptance conferred.

### CA-2407

- [ ] **CA-2407 P1 [VERIFY]** Use per-source provenance and time semantics for user statements, sensors, remote Fleet, simulation, project output and AI interpretation; enforce explicit `observed / inferred / hypothesized / simulated / stale / unknown` at every consumer.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** Source epistemic kinds and exact original evidence checks exist. Simulation/model/remote channel matrix not complete.

**Audit state:** source partial traced; tests not run; no acceptance conferred.

### CA-2408

- [ ] **CA-2408 P1 [VERIFY]** Add *operator-readable* life-cycle traces from observation ID → candidate interest → goal → action authorization → result → validated experience → relevant future conversation; test that deleting/revoking a source prevents the whole derived chain from resurfacing.

**Related production source:** `src/sofia/application/decision_trace.py`, `src/sofia/life/coordinator.py`, `src/sofia/application/background_runtime.py`.

**Audit observation/open clause:** project_causal_trace links goal/decision/work/observation and invalid receipts fail closed; revocation/deletion cascade needs proof.

**Audit state:** production partial traced; tests not run; no acceptance conferred.

### CA-3501

- [ ] **CA-3501 P0 [DESIGN/RESEARCH]** Define a **trusted success oracle** per activity class: file digest is existence, validator is technical correctness, user feedback is subjective usefulness, and project milestone is an explicit policy outcome.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Artifact digest existence, technical validator, owner preference and reviewed milestone are separate; trusted oracle for all activity classes not documented end-to-end.

**Audit state:** research gap remains; tests not run; no acceptance conferred.

### CA-3502

- [ ] **CA-3502 P0 [DESIGN/RESEARCH]** Separate generator, reviewer, test oracle, evidence store and approval authority. Identify which existing components already provide independence and prohibit an LLM from self-minting success receipts.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** GoalEvidenceIndex, CreativeExplorer and independent typed verifier reduce LLM self-certification. Actual isolation and separate authority research matrix needed.

**Audit state:** research gap remains; tests not run; no acceptance conferred.

### CA-3503

- [ ] **CA-3503 P1 [DESIGN/RESEARCH]** Write reward-hacking abuse scenarios: editing tests, hiding log errors, changing threshold metadata, substituting another artifact, writing fake JSON receipts, cherry-picking sensor samples and reinterpreting the brief after execution.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Threat and reward-hacking abuse matrix needs held-out scenarios; source byte/receipt guards address only a subset.

**Audit state:** research gap remains; tests not run; no acceptance conferred.

### CA-3504

- [ ] **CA-3504 P1 [DESIGN/RESEARCH]** Plan unseen/held-out checks and test inputs managed outside Hephaestus so the guest cannot alter its own final grade. Measure false positive success as well as successful tasks.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Source independent typed objective checks, verified RUN receipts and catalog original creative-byte revalidation exist. Held-out success-oracle research, reward hacking evaluations and real test isolation remain unverified.

**Audit state:** research/independent proof open; tests not run; no acceptance conferred.

### CA-3505

- [ ] **CA-3505 P1 [DESIGN/RESEARCH]** Design a three-way outcome classification: **technical-valid**, **objective-met**, **personally-valued**, with each value allowed to be yes/no/unknown and independently supported.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** TechnicalOutcome/PERSONAL_JUDGMENT/typed objective status are distinct in LIFE, but full independent three-way oracle cross-activity not accepted.

**Audit state:** research gap remains; tests not run; no acceptance conferred.

### CA-3506

- [ ] **CA-3506 P1 [DESIGN/RESEARCH]** Define what 'independent critique' means when both primary and secondary models share a provider family or context. Compare deterministic validators, separate inputs and blind review before adding any judge role.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Source independent typed objective checks, verified RUN receipts and catalog original creative-byte revalidation exist. Held-out success-oracle research, reward hacking evaluations and real test isolation remain unverified.

**Audit state:** research/independent proof open; tests not run; no acceptance conferred.

### CA-3507

- [ ] **CA-3507 P1 [DESIGN/RESEARCH]** Decide how to make success claims falsifiable in natural conversation: include tested criterion, evidence age, limitations and a succinct failure reason without dumping untrusted logs.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Source independent typed objective checks, verified RUN receipts and catalog original creative-byte revalidation exist. Held-out success-oracle research, reward hacking evaluations and real test isolation remain unverified.

**Audit state:** research/independent proof open; tests not run; no acceptance conferred.

### CA-3508

- [ ] **CA-3508 P1 [DESIGN/RESEARCH]** Map adversarial inputs across Discord, research web pages, Creative SVG/OBJ outputs, Hestia/Docker status, guest test logs and system messages. All such material remains lower-trust data in COGNITION/GOALS.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Source independent typed objective checks, verified RUN receipts and catalog original creative-byte revalidation exist. Held-out success-oracle research, reward hacking evaluations and real test isolation remain unverified.

**Audit state:** research/independent proof open; tests not run; no acceptance conferred.

### CA-3509

- [ ] **CA-3509 P2 [DESIGN/RESEARCH]** Design confidence calibration for real status reports versus hypotheses. Include abstention, contradiction resolution, selective observation and a ceiling on unverified project claims.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Source independent typed objective checks, verified RUN receipts and catalog original creative-byte revalidation exist. Held-out success-oracle research, reward hacking evaluations and real test isolation remain unverified.

**Audit state:** research/independent proof open; tests not run; no acceptance conferred.

### CA-3510

- [ ] **CA-3510 P1 [DESIGN/RESEARCH]** Specify evaluators that remain effective across restarts, changed LLMs, partial Fleet outages and edited project briefs; historical criteria must be versioned and not silently rewritten to match results.

**Related production source:** `src/sofia/life/validation.py`, `src/sofia/goals/evidence.py`, `src/sofia/life/procedures.py`.

**Audit observation/open clause:** Current typed original objectives are persisted; actual changed-model/brief, crash and cross-Fleet evaluator tests are pending.

**Audit state:** research gap remains; tests not run; no acceptance conferred.

## Priority gap and acceptance boundaries

- CA-101/107: real current eligible observations into LIFE interests, future learning and retirements, without treating missing evidence as fake curiosity.
- CA-105/110/113: durable full transition, bounded review/next milestone/abandonment table beyond first text/story plus revised artifacts.
- CA-209/607: exact capability-specific CPU/GPU/time/wakeup/asset budgets and real optional workload host suitability.
- CA-2401/2403/2404: optional read-only CompanionWorkspace, epistemic reason trace and verified prospective commitment obligations.
- CA-3501–3510: independent research/test oracles and adversarial held-out evidence; not acceptable from source-written tests alone.

**No claim all 66 have been individually fully audited or coding-complete.** Additional static path audit and safe production implementation remain. Only user-authorized end-of-campaign test execution can establish acceptance.


## Continued source evidence: GOALS expiry and exact original RUN chronology (2026-10-11)

- **CA-102/106/108/110/114/1604/1606:** expired SELF goals can no longer admit optional creative RUN jobs while the GOALS expiry sweep is delayed. Motivation selection rejects overdue ACTIVE status before model wake, operator dependency projections report a deadline blocker and GOALS→LIFE reconciliation pauses overdue projects without forging a GOALS status change. See code commits `a66cc92d`, `7b77fe7a`; regressions authored only.
- **CA-106/204/2402/2407/2408:** `LifeStore.exact_original_run_outcome` now requires exact original reason as well as event/job/status/time and rejects backdated, timezone-naive or malformed derived observed timestamps without crashing reconciliation. See production commits `2ab07ca1`, `3cfbb41f`; regression code authored, not run.
- **Remaining:** every original CA clause still requires exact-source production tracing; standalone reviewed documents are not accepted tasks. No tests, models, CI or real hosts were exercised by these changes.


## 2026-10-11 production follow-up: RUN source chronology and all-job operator projections

- Original `LifeStore.reconcile_run_outcomes` now delays future original RUN timestamps and refuses malformed source timestamps before inserting the derived LIFE event, preventing a permanently backdated/invalid observation. Partial IDs CA-106/202/204/2402/2407. Production `88aea96c`; deferred regression `2a56be34`.
- Original `SelfDirectedLifeCoordinator.motivation_signals` and `goal_dependency_view` now consider all linked RUN jobs, so an earlier UNCERTAIN/BLOCKED/FAILED/CANCELLED job cannot vanish behind a newer work item. Review keys and operator action references identify the actual unsafe source job. Partial IDs CA-106/110/1301/1303/1602/1604/1606/2402/2408. Production `4ff1522d`; deferred regression `dcb3648e`.
- Read-only source commits are not accepted tasks. Tests/CI/lived host verification remain deferred.

## 2026-10-11 follow-up: original LIFE experience mutation during learning

- **IDs:** CA-101, CA-107, CA-2407. **Original requirements remain partial.**
- **Confirmed source race:** Before this fix, final `LifeStore.record_interest_learning` checked only whether a formerly verified `life_experience` row existed; it never rechecked the row's identity/digest under the canonical write lock.
- **Source correction:** `LifeStore.experience_digest` is now the common original-source fingerprint for the LIFE coordinator and interest writer. A final same-transaction original-row comparison and audience fence prevent altered observations from earning revisions while still recording the old source digest. This is not ordinary unrelated experience ingestion, broad correction propagation or task-wide completion.
- **Source commits:** `4d9eaa4`, `f86ba54`; **regression authored** `17e68da`, unexecuted. No tests/CI/deployment/host effects.

## Follow-up: optional LIFE admissions after original interest source revocation (2026-10-11)

- **Original IDs:** CA-101, CA-107, CA-110, CA-1606, CA-2402 and CA-2407, all still partial task coverage.
- **Confirmed missing read fence:** Active interest strength, status and confidence remained selectable in background LIFE after its original reviewed evidence ref vanished. Existing typed source checks at creation and evaluation did not protect *later* source changes before autonomous selection and RUN.
- **Production correction:** Source-scoped fresh original evidence check now guards motivation, pre-model interest selection, post-model selected-interest revision, direct original LIFE RUN admission and queued native creative effect execution. The gate checks the existing `GoalEvidenceIndex` and canonical principal/audience; it neither mutates GOALS nor models other memory deletion subsystems.
- **Commit:** `4a3b1d9`; new regressions `0937124`, `093bf6c`, not run. No acceptance receipt or host effects.

## Follow-up: source-correct LIFE episode context in ProjectIdeaAgent (2026-10-11)

- **Original CA IDs:** CA-101, CA-107, CA-2407. Partial original implementation only.
- **Gap:** The actual LIFE background ideation call sent recent `life_experience.summary` strings without rechecking original source evidence, chronology, or audience eligibility. This was distinct from the already source-fenced origin interest.
- **Change:** `SelfDirectedLifeCoordinator.consider_new_project` now uses a bounded verified episode subset and post-model source recheck, with the same scoped original `GoalEvidenceIndex` guard; no independent recorder, permission mechanism or replacement planner. Source `aedeb93`; regression `b23f9ce` authored only. Remaining future work includes original-record digest freshness during model latency, correction/deletion invalidation of already-learned historical preferences, and end-to-end tests.
