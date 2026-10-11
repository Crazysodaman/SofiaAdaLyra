# Sofía Ada Lyra • V18 Priority-Ordered Master Roadmap

**Status: DESIGN, FLAW REVIEW AND RESEARCH ONLY. NO CODING AUTHORIZED.**  
**Based on:** V17 (700 existing tasks in 69 topic groups); no task removed, invented, changed, closed, or claimed tested.  
**Organization:** 17 **execution-priority phases**, reusing original stable `CA-` IDs; 69 original topic groups included once each.  
**Source checked:** `Crazysodaman/SofiaAdaLyra`, GitHub `main` `e85c52f01a6fc4ec67c05ed4dade2752755bcf0b` on 2026-10-10.  
**No GitHub updates performed.**

## What your priority means in this revision

I inferred ordering from your expressed goals and explicit decisions: **(1)** truth over optimistic completion claims, **(2)** one recoverable Sofía, **(3)** lifelong cross-device conversation and accurate memory, **(4)** emotional continuity and meaningful autonomy, **(5)** useful homelab/VM capabilities, **(6)** performance/model evolution, **(7)** advanced neuro/consciousness research. This is a proposed order, not a claim you individually ranked all 700 tasks.

Each checklist line below preserves the original task wording and ID. Multiple old topical phases may contribute to one execution phase. **The source version stays separately archived as V17**, including all research notes; V18 is the actionable prioritized view. Design completion is distinct from subsequent coding, test proof, and production acceptance.

## GitHub evidence, not optimistic inference

- **At this SHA:** GitHub Actions Package Tests finished **20/22 green**, `pkg_verify` **failed**, `pkg_body` **failed**. `Matrix Tests` and `Platform Compatibility` succeeded. `Release Candidate Build` failed. `Manual Verification` was cancelled. Links: [Package](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38093964817), [Release](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38093964828), [Matrix](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38093964821), [Platform](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/38093964834).
- Known review findings requiring targeted verification rather than speculation: release's nested archived source leading to duplicate test module collection; Windows database file-handle cleanup in a cognition baseline test; `pkg_body` selecting zero tests under the package marker. Confirm fresh logs before applying fixes.
- **Existing useful foundations:** durable SQLite sessions and explicit resume; separate principal/audience bindings; approved memory promotion and emotional journals; LIFE/GOALS/RUN coordinators; SAFE permission rules; Ollama dual-model routing/lifecycle; backup/restore; configurable `SOFIA_STATE_ROOT`; Fleet services and read-only observation.
- **Do not mark complete from code existence alone:** one cross-device Main timeline, decades-scale archive search, settings-guided database relocation, full lifelong migration drills, autonomous safe model selection/training, live screen vision, Hephaestus guest provisioning or fully accepted LIFE creative loops.
- The GitHub `ROADMAP.md` contains historical milestones and some stale descriptions; V18 does not take its statements as a substitute for current code or acceptance evidence.

## First-pass priority index

| Order | Priority | Execution phase | Tasks | Old phase IDs | Evidence state |
|---:|---|---|---:|---|---|
| 00 | P0 • Design foundation | Architecture and source-of-truth freeze | 65 | 0, 12, 31, 33, 40, 45, 47, 54 | Mixed: coded foundation, design, or missing proof |
| 01 | P0 • Release blocker | Restore credible CI, release and live acceptance | 66 | 9, 22, 23, 30, 46 | Mixed: coded foundation, design, or missing proof |
| 02 | P0 • Safety gate | SAFE, operator authority and independent evaluation | 30 | 11, 19, 27, 65 | Mixed: coded foundation, design, or missing proof |
| 03 | P0 • Identity foundation | Canonical database home, migration and disaster recovery | 46 | 37, 52, 61, 68 | Mixed: coded foundation, design, or missing proof |
| 04 | P0 • Survivability | Offline use, event ordering and model-independent survival | 22 | 63, 64 | Mixed: coded foundation, design, or missing proof |
| 05 | P1 • User priority | Lifelong Main plus optional cross-device project threads | 41 | 41, 53, 55, 57 | Mixed: coded foundation, design, or missing proof |
| 06 | P1 • Core cognition | Working, episodic, semantic and time-aware memory | 73 | 3, 17, 42, 48, 50, 56, 58, 59 | Mixed: coded foundation, design, or missing proof |
| 07 | P1 • Stewardship | Lifelong archive, corrective memory and selective forgetting | 26 | 34, 49, 51 | Mixed: coded foundation, design, or missing proof |
| 08 | P1 • Companion behavior | Emotion, personality, relationship and companion presence | 56 | 4, 5, 18, 25, 38, 60 | Mixed: coded foundation, design, or missing proof |
| 09 | P1 • Core autonomy | Independent LIFE cycle, goals and creative initiative | 66 | 1, 2, 6, 13, 16, 24, 35 | Mixed: coded foundation, design, or missing proof |
| 10 | P2 • Useful action | Reusable skills, real integrations and guarded robotics | 27 | 10, 14, 26 | Mixed: coded foundation, design, or missing proof |
| 11 | P2 • Efficient cognition | Resource budgeting and autonomous LLM selection | 49 | 21, 32, 39, 44, 66 | Mixed: coded foundation, design, or missing proof |
| 12 | P2 • Multimodal input | Visible, consent-based screen and perception awareness | 24 | 15, 62 | Mixed: coded foundation, design, or missing proof |
| 13 | P2 • Isolated independence | Hephaestus workshop VM and digital-twin research | 63 | 28, 29, 36, 43 | Mixed: coded foundation, design, or missing proof |
| 14 | P3 • Experimental expansion | Model adaptation and training lab | 12 | 67 | Mixed: coded foundation, design, or missing proof |
| 15 | P3 • Evidence-based research | Connectome-inspired NEURO and scientific modeling | 22 | 7, 20 | Mixed: coded foundation, design, or missing proof |
| 16 | P3 • Long-term science | Consciousness and subjective-experience research | 12 | 8 | Mixed: coded foundation, design, or missing proof |

**Dependency rule:** The phases are *prioritized*, not necessarily a single-file waterfall. Research can overlap; implementation and promotion must respect the gates. Phase 00 definitions and Phase 02 SAFE govern all later work; Phase 03 storage ownership gates any database move; Phase 01 release/verification gates all production acceptance.

**Every phase includes design proof first:** current source paths + exact failure, alternative architectures, performance budget, security/privacy, expected persistent objects, migration/deployment steps, specific automated and live tests, and an explicit decision to build, defer or drop.

---
## Priority phase 00: Architecture and source-of-truth freeze

**Classification:** P0 • Design foundation  
**Inherited tasks:** 65 in old topic groups: 0, 12, 31, 33, 40, 45, 47, 54.  
**Why here:** Agree on the one-runtime, one-canonical-state, one-identity architecture; distinguish coded, tested, accepted and proposed work. Lock OS Option A now and defer Option B (Linux appliance).

**Current repository evidence:** GitHub main has app/runtime/state architecture, but its root ROADMAP.md intermixes past milestones with current defects and future proposals.

**Design exit gate:** One endorsed component map, owner/dependency graph, single-writer boundaries, frozen terms, no duplicate semantic owners, decision log, acceptance definitions.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 0: Baseline, audit, and architectural contracts (7 tasks)

- [ ] **CA-001 [VERIFY]** Trace a real event through COGNITION v2 → NEURO → MEM → PERSONALITY/EMOTION → LIFE/GOALS → RUN/ACT → evaluation → persistence. Identify missing production callers, not only implemented methods.
- [ ] **CA-002 [VERIFY]** Capture the current baseline: memory correctness, topic continuity, unsolicited outreach quality, real avatar/voice synchronization, idle model wakeups, CPU/GPU/RAM use, p50/p95 latency, and restart behavior on Venus.
- [ ] **CA-003 [VERIFY]** Document authority, evidence, privacy, principal/audience, resource and error-state contracts for every new connection. Keep `sofia.db` canonical.
- [ ] **CA-004 [VERIFY]** Preserve the already implemented COGNITION v2 and dual-model production interfaces; avoid restoring removed v1 ownership or adding competing runtime controllers.
- [ ] **CA-005 [VERIFY]** Publish a source-to-sink ownership map for the canonical event/evidence envelope: `event_id`, source, subject, principal, audience, observed time, expiry, confidence, evidence references, action/goal/project IDs, consent class and renderer/transport receipt. Use adapters over existing tables, not a new truth ledger.
- [ ] **CA-006 [GAP]** Add a revisioned `CompanionDecisionTrace` projection joining NEURO winner, eligible memories, chosen goal/activity, rejected alternatives, execution/ACT decision, and outcome. Derive it from canonical owners; it must be non-authoritative.
- [ ] **CA-007 [VERIFY]** Add a reproducible baseline snapshot and test gates per commit. “Coded”, “unit passed”, “CI accepted”, “Venus live accepted” and “multi-host accepted” are separate states; block ambiguous green checkmarks.

### Source topic 12: Detailed integration and evaluation contracts (8 tasks)

- [ ] **CA-1201 [VERIFY]** Write a `companion-autonomy-contract.md` defining event inputs, canonical owners, allowed downstream effects, idempotency, execution scope, failure semantics and audience boundaries for every adapter.
- [ ] **CA-1202 [VERIFY]** Define a versioned decision state transition graph with replay, dedupe, correction and restart tests; each optional action needs an expected-effect predicate and receipt-based settlement.
- [ ] **CA-1203 [VERIFY]** Build an explicit context-window budget for episodic retrieval, workspace broadcasts, affect/style, project status and factual evidence. Suppress low-confidence or irrelevant content instead of flooding the LLM.
- [ ] **CA-1204 [VERIFY]** Add a governed feedback loop: receipts and user corrections update preference/association proposals after validity checks; never let model self-praise manufacture reinforcement.
- [ ] **CA-1205 [VERIFY]** Benchmark selected subsets from LongMemEval, LoCoMo and agent-environment memory as **adapted** internal tasks. Report exact sample size, scoring, abstention, baseline, feature ablation and error categories.
- [ ] **CA-1206 [VERIFY]** Publish a production-acceptance matrix crossing model route × source × principal × audience × modality × permission × busy state × restart state × failure type, plus hand-tested examples.
- [ ] **CA-1207 [VERIFY]** Add explicit model/provider outage and invalid-JSON handling with human-readable diagnostics; background project work must not wedge conversation or bypass deterministic gates.
- [ ] **CA-1208 [VERIFY]** Check privacy/data minimization: consent to retain optional episodes, scoped correction/deletion, retention windows and immutable audit evidence where required, without exposing confidential records in LLM context by default.

### Source topic 31: Architecture flaws and pre-build decisions (12 tasks)

- [ ] **CA-3101 P0 [DESIGN/RESEARCH]** Map a single **component ownership table** for COGNITION v2, LIFE, GOALS, RUN, SAFE, ACT, MEM, NEURO, WORLD, DEV, Fleet and VM; record authoritative writer, consumers, error states and data retention. Design deliverable: reviewed owners table and 3 end-to-end sequence diagrams.
- [ ] **CA-3102 P0 [DESIGN/RESEARCH]** Decide **canonical Sofía runtime location and failover ownership** before adding Hephaestus. Distinguish runtime process, logical canonical `sofia.db`, user-visible UI and disposable workers. Design deliverable: one-writer state diagram with host-failure behavior.
- [ ] **CA-3103 P0 [DESIGN/RESEARCH]** Resolve the desired **two-location database redundancy** without two independent writers corrupting SQLite. Compare encrypted snapshot replication, SQLite backup/WAL shipping, single-writer replicated storage, and promoted-standby failover; specify RPO/RTO, fencing, reconciliation and failback.
- [ ] **CA-3104 P0 [DESIGN/RESEARCH]** Formalize the **LIFE state machine** for queued, running, completed, waiting-approval, blocked, failed, uncertain, paused, abandoned and verified objective complete. Spell out which state triggers critique, retry, operator question, next milestone or silence.
- [ ] **CA-3105 P0 [DESIGN/RESEARCH]** Define a **decision-rights matrix** across read-only sensing, safe autonomous tasks, scoped reversible actions, protected changes and never-self-authorized permissions; identify exactly which provisioning steps require fresh operator consent and which can be leased.
- [ ] **CA-3106 P0 [DESIGN/RESEARCH]** Choose **Artemis-to-guest network topology** for the actual hypervisor: fully offline private virtual switch; host-reachable internal switch with strict firewall/ACL; or broker-VM relay. Prove the broker can actually reach the worker without exposing the home LAN. NAT alone does not constitute isolation.
- [ ] **CA-3107 P0 [DESIGN/RESEARCH]** Review **Artemis privilege minimization** for Hephaestus creation: constrained JEA/runbook or isolated provisioning agent, exact VM name/resources/network paths, immutable plan digest, non-reusable approvals and full administrative event logging. Compare to one-time operator-run setup.
- [ ] **CA-3108 P0 [DESIGN/RESEARCH]** Design **host and guest identity and credential lifecycle**: separate Fleet identities, secure key provisioning, rotation, revocation, bootstrap escrow, no private-key copies in broad SMB shares, secrets absent from images/snapshots and scrubbed logs.
- [ ] **CA-3109 P0 [DESIGN/RESEARCH]** Specify an **evidence taxonomy** covering observed, verified, inferred, simulated, hypothesized, stale, unknown and revoked; define how sources, times, principal/audience and correction chains propagate into LIFE, MEMORY and conversation.
- [ ] **CA-3110 P1 [DESIGN/RESEARCH]** Document **VM trade-offs**: always-on Debian guest versus disposable/re-imaged per-project guest versus temporary per-job isolated process. Decide using isolation strength, snapshot time, CPU/RAM overhead, reproducibility, tool suitability and restore cost.
- [ ] **CA-3111 P1 [DESIGN/RESEARCH]** Identify **single points of failure** and critical dependencies: Venus model runtime, Artemis power, DNS, PKI, Fleet broker, NAS, `sofia.db`, backup location, NWS, JMRI, Home Assistant and Ollama. Design explicit degraded/offline modes with deterministic restart.
- [ ] **CA-3112 P1 [DESIGN/RESEARCH]** Define **truthful avatar/world/voice expression contracts**: message content versus rendered frames, speech synthesis versus spoken audio, simulated world interactions versus physical actions, and receipt states across Desktop/Discord. No evidence-free embodiment claims.

### Source topic 33: Research protocol, human factors and design verification (12 tasks)

- [ ] **CA-3301 P0 [DESIGN/RESEARCH]** Establish a **design readiness gate** for each phase: evidence of current source behavior, exact missing interface, competing designs, security/authority impact, estimated resource overhead, acceptance metric and clear rejection criterion. No implementation merely because task appears on checklist.
- [ ] **CA-3302 P0 [DESIGN/RESEARCH]** Classify every V8 item as `verified coded`, `coded but unverified`, `partial wiring`, `research hypothesis`, `design only` or `blocked`; attach commit/evidence and avoid treating an unchecked design task as proof nothing exists.
- [ ] **CA-3303 P0 [DESIGN/RESEARCH]** Write a **CI failure decision report** for current commit: release test-import mismatch caused by nested `release-source`, `pkg_verify` Windows temporary DB file handle failure, `pkg_body` zero-selected marker mismatch; distinguish static diagnosis from validated fixes.
- [ ] **CA-3304 P1 [DESIGN/RESEARCH]** Build a **counterfactual/ablation evaluation plan** for LIFE alone, LIFE+MEM, +curiosity, +reusable skills, +NEURO competition, +associations and VM workshop. Decide in advance what measurable improvement justifies each added subsystem.
- [ ] **CA-3305 P1 [DESIGN/RESEARCH]** Study **long-horizon autonomy difficulty** using staged 1-step, multi-step, restarted, one-day and one-week tasks; track actual objective completion, appropriate stop, evidence fidelity and fault recovery instead of mere action count.
- [ ] **CA-3306 P1 [DESIGN/RESEARCH]** Study **memory temporal correctness** with LongMemEval-style extraction, multi-session, corrections, outdated facts and abstention plus a separate task-use metric for whether remembered facts improve decisions.
- [ ] **CA-3307 P1 [DESIGN/RESEARCH]** Review **skill-learning research** such as Voyager and Reflexion as design patterns; identify the smallest reusable skill unit and evidence of transfer. Do not copy an unbounded automatic curriculum or autonomous code execution privileges.
- [ ] **CA-3308 P1 [DESIGN/RESEARCH]** Preregister **connectome experiments** comparing research-only circuit competition and sparse association against simpler deterministic NEURO and approved MEM baselines; include false positives, CPU/RAM, privacy gating, replay/recovery and disconfirmation.
- [ ] **CA-3309 P2 [DESIGN/RESEARCH]** Separate **consciousness investigation** from companionship claims: review multiple operational theories, confounders, negative controls, measurable metacognition and limits of self-report; never state subjective experience has been demonstrated.
- [ ] **CA-3310 P1 [DESIGN/RESEARCH]** Design **companion wellbeing constraints** using research on affective chatbot use: optional outreach, no dependency optimization, user-set boundaries, no manufactured guilt/distress, quiet days and transparent distinction between simulation and lived experience.
- [ ] **CA-3311 P1 [DESIGN/RESEARCH]** Plan **adversarial injection and supply-chain evaluations** for untrusted web/Discord/VM outputs, model-generated plans, logs, saved memories, SVG/art assets, package artifacts and service discovery. Confirm capability rights remain in SAFE regardless of model output.
- [ ] **CA-3312 P1 [DESIGN/RESEARCH]** Draft a **pre-coding architecture review packet**: owner map, data-flow diagram, job/failure state machine, benchmark/profiling matrix, threat model, approval/VM lifecycle, prioritized minimal vertical slices and a list of ideas deliberately postponed.

### Source topic 40: Comparable projects, architecture reuse, and buy-versus-build (6 tasks)

- [ ] **CA-4001 [DESIGN/RESEARCH]** Build a source-verified comparison matrix for Letta, OpenClaw, Hermes Agent, OpenHands, Open-LLM-VTuber, AIOS, and OpenDAN: ownership, deployment, memory, sessions, tools, isolation, UI, operating model, release cadence and license; distinguish confirmed behavior from claims.
- [ ] **CA-4002 [DESIGN/RESEARCH]** Specify reference-pattern adoption rather than wholesale dependency migration: borrow Letta-style stateful identity and separation of agent/conversations, without importing another canonical database or agent brain.
- [ ] **CA-4003 [DESIGN/RESEARCH]** Compare OpenClaw's per-peer and cross-channel identity-link mapping with Sofía's present channel/audience bindings. Capture its distinction between shared history and per-origin capability policy; require a threat model and owner consent.
- [ ] **CA-4004 [DESIGN/RESEARCH]** Evaluate Hermes' bounded curated profile, separate searchable transcript, procedural skill learning, and explicit memory update behavior against Sofía's existing reviewed-memory pipeline; do not auto-promote unreviewed source text.
- [ ] **CA-4005 [DESIGN/RESEARCH]** Compare OpenHands isolated agent-server execution and Open-LLM-VTuber voice/rendering stacks against already-owned DEV, voice, expression and planned Hephaestus; cost maintenance, security and replacement risk rather than duplicating their code.
- [ ] **CA-4006 [DESIGN/RESEARCH]** Review AIOS and OpenDAN strictly as reference operating-layer architectures; decide whether any missing kernel-like scheduler, portable capability API or orchestration feature is not already implemented in RUN/Fleet/SAFE.

### Source topic 45: Sofía as an OS versus an agent platform/service (6 tasks)

- [ ] **CA-4501 [DESIGN/RESEARCH]** Resolve terminology in an architecture decision record: **operating system kernel**, **user-level agent operating layer**, **dedicated Sofía appliance OS image**, and **desktop shell/launcher** are separate proposals with different obligations.
- [ ] **CA-4502 [DESIGN/RESEARCH]** Compare (A) Sofía services on existing Windows/Debian, (B) dedicated Linux appliance VM with supervised services, (C) desktop-first full-screen Sofía workspace, (D) AIOS-like orchestration framework, and (E) custom kernel. Quantify expected gain and failure domain.
- [ ] **CA-4503 [DESIGN/RESEARCH]** Specify **Sofía Operating Layer** as a set of existing SAFE/RUN/Fleet/Memory/session service interfaces with strict authority and resource budgets, rather than a bootable custom kernel. Audit against AIOS to avoid rebuilding its scheduler abstractions unnecessarily.
- [ ] **CA-4504 [DESIGN/RESEARCH]** Design a future **Sofía appliance image** option: secure base distro, immutable/reproducible build, service supervision, encrypted storage, secure updates/rollback, remote diagnostics and disaster recovery. The identity/database remains canonical and externally recoverable.
- [ ] **CA-4505 [DESIGN/RESEARCH]** Reject/custom-kernel defer unless a written hardware-control requirement cannot be met by Linux, Windows, drivers, containers or hypervisors. Evaluate kernel maintenance, security patches, drivers, boot-chain, hardware compatibility and 24/7 support cost.
- [ ] **CA-4506 [DESIGN/RESEARCH]** Prove OS/platform decision against core outcomes: cross-device chat, independent projects, VM experiment safety, voice/avatar quality, and recoverable Fleet operations. Ship the smallest hosting layer that delivers them; do not conflate an OS with intelligence or consciousness.

### Source topic 47: High-value extensions, decision gates and what not to build (6 tasks)

- [ ] **CA-4701 [DESIGN/RESEARCH]** Explore **human-facing memory control**: inspect why Sofía believes something, who/what supplied it, last verified timestamp, correct/forget, mark private, and see which decisions and reminders depend on it.
- [ ] **CA-4702 [DESIGN/RESEARCH]** Explore **portable session handoff UX**: phone QR/device pair, visible active thread and delivery destination, 'continue here', local-only mode, last-read cross-device position, and opt-in cross-channel history visibility.
- [ ] **CA-4703 [DESIGN/RESEARCH]** Explore **independent experiment notebooks** in Hephaestus: reproducible manifests, hypotheses, expected outcomes, measurements, failed attempts, licensing of assets, costs and return-to-quiet without false discovery claims.
- [ ] **CA-4704 [DESIGN/RESEARCH]** Explore **latency-aware model placement**: local fast-first, deep model for demonstrably hard tasks, multi-machine inference only via approved discovery, warm/cold state and GPU gaming-preservation, with measured quality thresholds.
- [ ] **CA-4705 [DESIGN/RESEARCH]** Explore **simulated homelab resilience planning**: apply/read-only observation from known Artemis/Eos/Hestia configurations to a non-authoritative digital twin; report uncertainty and prohibit treating simulation as live state.
- [ ] **CA-4706 [DESIGN/RESEARCH]** Explore **software supply-chain and research provenance**: dependency licenses, vulnerability update schedule, external paper/model dataset claims, experiment replication, consent to collect user signals, review dates and abandonment criteria.

### Source topic 54: OS strategy locked to Option A, Option B later (8 tasks)

- [ ] **CA-5401 [DESIGN/RESEARCH]** Record architecture decision: **Option A approved now** = user-level Sofía Operating Layer on established Windows/Linux, one canonical identity, SAFE/RUN/Fleet, Memory, session APIs, permission boundaries and typed platform capability drivers; don't create a custom kernel.
- [ ] **CA-5402 [DESIGN/RESEARCH]** Define operating-layer interfaces independently of host OS so all clients can use one authenticated service contract for message timeline, memory search, asset retrieval, hosted tools, grants, job receipts and lifecycle/health.
- [ ] **CA-5403 [DESIGN/RESEARCH]** Record **Option B approved but deferred** = dedicated reproducible Linux appliance image after baseline acceptance. Appliance packaging must reuse existing application/identity, never fork a second constitution/brain or active database.
- [ ] **CA-5404 [DESIGN/RESEARCH]** Establish explicit B entry criteria: stable production startup, full Phase6/LIFE cycle, passing pinned CI, verified portable conversation/memory, proven backup/restore, trusted Fleet, reliable CPU/VRAM budgets, secure remote administration and 7-day supervised soak.
- [ ] **CA-5405 [DESIGN/RESEARCH]** Compare B later hosted on Artemis or dedicated hardware for fault domains, SSD endurance, RAM/GPU, noisy-neighbor constraints, power, UPS, encryption/TPM, hypervisor, disaster recovery, home network access and keeping her active when Venus is powered off.
- [ ] **CA-5406 [DESIGN/RESEARCH]** Design future B boot/release model: OS security update channel, immutable/pinned system base, two-slot app rollback, watchdog, encrypted local data, trusted key recovery, settings re-import and explicit storage ownership switchover.
- [ ] **CA-5407 [DESIGN/RESEARCH]** Quantify overhead of A vs A+B and bound duplication: no extra always-running LLM brain, redundant daemon pollers, independent authority issuers, mirrored concurrent writers or blindly duplicated embeddings.
- [ ] **CA-5408 [DESIGN/RESEARCH]** Put any true operating-system kernel proposal outside active scope until a documented capability cannot be supplied by Linux/Windows drivers, hypervisor or isolated worker; require risk/cost comparison and independent design approval.

---

## Priority phase 01: Restore credible CI, release and live acceptance

**Classification:** P0 • Release blocker  
**Inherited tasks:** 66 in old topic groups: 9, 22, 23, 30, 46.  
**Why here:** Never treat planned autonomy as reliable while baseline CI and a release gate fail.

**Current repository evidence:** At e85c52f: package jobs pkg_verify and pkg_body failed (20/22 passed); Release Candidate Build failed; Matrix and Platform workflows passed; Manual Verification was cancelled. Path-component repair merged, but full Windows/live acceptance not proved.

**Design exit gate:** Design failure root-cause matrix and acceptance criteria; subsequent implementation must attain 22/22 meaningful package gates, release build, exact-SHA evidence, supervised Windows/Discord/Fleet acceptance, and a no-empty-marker guarantee.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 9: End-to-end test and acceptance matrix (14 tasks)

- [ ] **CA-901 [VERIFY]** Unit-test each boundary plus the cross-matrix EXPERIENCE → NEURO → MEM → PREFERENCE → GOALS/LIFE → RUN → EMOTION/AVATAR/VOICE → REL/ACT.
- [ ] **CA-902 [VERIFY]** Run a three-day independent project: choose a verified interest, create, evaluate, revise, complete/abandon, remember and optionally share. Verify every transition and receipt.
- [ ] **CA-903 [VERIFY]** Run a longitudinal Gaia example: recall only verified servo evidence, select a relevant follow-up, and never issue hardware commands without permissions.
- [ ] **CA-904 [VERIFY]** Exercise restarts, offline gaps, user disinterest, rejected outreach, permissions denied, privacy boundaries, stale evidence, interrupted jobs, high load and unavailable models/tools.
- [ ] **CA-905 [VERIFY]** Live-test voice, avatar synchronization, desktop/Discord ACT delivery, secondary-model routing, and cognition continuity on Venus (and enrolled Fleet nodes where relevant).
- [ ] **CA-906 [VERIFY]** Measure p50/p95 response latency, model calls, CPU/GPU/RAM, persistent storage, idle wakeups, attention quality, memory precision, unwanted interruptions, and regression rates.
- [ ] **CA-907 [VERIFY]** Require zero regressions in consent, privacy, permission levels, factual grounding, canonical state, safe Gaia boundaries and human operator authority.
- [ ] **CA-908 [VERIFY]** Record test evidence in the single `ROADMAP.md` and existing verification/release process, distinguishing coded, unit-tested, CI-verified, and Windows-host-live-accepted milestones.
- [ ] **CA-909 [VERIFY]** Replay a multi-day, no-prompt scenario across 3+ actual Windows restarts with no invented offline experiences, duplicate work, missed evidence or undesired outreach.
- [ ] **CA-910 [VERIFY]** Test adversarial memory injections, private-audience collisions, stale/contradictory facts, hallucinated action receipts and LLM attempts to self-approve permissions.
- [ ] **CA-911 [VERIFY]** Measure CPU/GPU/RAM and per-hour model wakeups on Venus while gaming, idle and during active conversation, comparing the precise same workloads with connectome integration off/on.
- [ ] **CA-912 [VERIFY]** Test graceful degradation for Discord down, Hestia unavailable, weather stale, Fleet node lost, JMRI offline, Gaia disconnected and model endpoint timeout.
- [ ] **CA-913 [VERIFY]** Record developer-facing trace and user-facing explanation for 20 representative autonomous decisions, including why she did nothing; require claims to match stored evidence.
- [ ] **CA-914 [VERIFY]** Establish promotion gates per task: focused unit → cross-package integration → full repository → live single-host → multi-day soak → supervised Fleet/hardware. Use real receipts, not claims of completion.

### Source topic 22: Code-derived integration repairs and hardening (NEW v4) (18 tasks)

- [ ] **CA-2201 P0 [GAP]** Introduce an **artifact-kind objective validator registry**. Each verified artifact receives typed checks tied to actual brief objectives, concrete file content and capability receipts; do not allow model-supplied `true` fields to substitute for independent proof.
- [ ] **CA-2202 P0 [GAP]** Replace `_initial_specification()` boilerplate with a bounded, tool-free **creative authoring pass** for approved media kinds. Preserve starter templates as safe fallbacks, but never claim a cube/colored SVG/half-second sine tone is a sophisticated original finished work.
- [ ] **CA-2203 P0 [GAP]** Add a structured critique stage that distinguishes independently testable quality, optional subjective taste, revision plan and confidence. Feed the critique into existing LIFE transitions without allowing it to invent evidence.
- [ ] **CA-2204 P1 [VERIFY / HARDEN]** Audit the crash window between `manager.submit`, `authorize_artifact` and `link_job`; implement a transactional or idempotently recoverable reservation/provisioning sequence. Test restart at every write boundary.
- [ ] **CA-2205 P0 [GAP]** Create a durable LIFE job-result reconciler that handles `COMPLETED`, `FAILED`, `BLOCKED`, `CANCELLED`, `UNCERTAIN` and expired jobs independently; never replay an uncertain mutation without proof.
- [ ] **CA-2206 P1 [GAP]** Make outcome-derived preference updates repeatable, deduplicated, source-correctable and no stronger than verified evidence. Audit duplicate `evaluate_artifact()` attempts after restart.
- [ ] **CA-2207 P1 [GAP]** Build a cold-start, source-scoped **experience admission bridge** from approved personal/operational observations into LIFE interest candidates. With no eligible interest, choose silence, not fabricated curiosity.
- [ ] **CA-2208 P2 [GAP]** Compose authenticated `WorldEditor` in the existing application and expose permitted virtual-space interactions from eligible LIFE decisions; require world revision and renderer receipts.
- [ ] **CA-2209 P1 [GAP]** Produce Presence `task_completed` and `conversation_followup` events from grounded LIFE/discourse transitions, with stable event IDs, read receipts, priority/busy/quiet suppression and exact audience.
- [ ] **CA-2210 P1 [VERIFY]** Route optional project critique through the existing dual-role cognitive system and measure role locks, no-tool bounded requests, graceful invalid JSON, resource pressure and no fallback permission expansion.
- [ ] **CA-2211 P2 [GAP]** Bridge verified LIFE activity and optional sharing into existing `ExpressionRuntime`; coordinate wording/prosody/Tk avatar gesture without pretending a real voice or renderer acted when it did not.
- [ ] **CA-2212 P1 [VERIFY]** Version and benchmark connectome input encoding, especially sparse hash collisions and false memory links. If accuracy fails to exceed NEURO/MEM baselines, leave prototypes disabled in production.
- [ ] **CA-2213 P2 [GAP]** Add a capability-checked skill compatibility and invalidation view for safe virtual-world/creative procedural recipes, keyed by actual verified runs, environment and tool versions.
- [ ] **CA-2214 P1 [VERIFY]** Exercise prompt-injection isolation in autonomous authoring and critique: external logs, Discord text, project descriptions, SVG/JSON media and imported documents must not become policy or action instructions.
- [ ] **CA-2215 P2 [VERIFY]** Measure background scheduler fairness and unnecessary `select_activity()` churn after an initial artifact; ensure one project waiting for review does not monopolize model budget or suppress important ACT work.
- [ ] **CA-2216 P2 [GAP]** Add canonical-derived operator diagnostics for the exact reason LIFE is idle, blocked, reviewing, awaiting permission, uncertain or finished, with no second authoritative scheduler state.
- [ ] **CA-2217 P1 [VERIFY]** Separate self-chosen personal projects, user-requested jobs and operational duties in selection, abandonment, permissions and success reports; avoid transferring voluntary LIFE rights to assigned work.
- [ ] **CA-2218 P2 [VERIFY]** Confirm trusted source and timestamp propagation from real environment/host/world observations through NEURO to conversation and LIFE; label predicted, simulated, stale and offline events distinctly.

### Source topic 23: CI proof, executable vertical slices and host acceptance (NEW v4) (10 tasks)

- [ ] **CA-2301 P0 [RED CI]** Investigate all eight red package jobs from GitHub Actions run `38063542680` on `d86e5516e1b3`. Download/log exact assertion failures and reproduce their `pytest -q -m "pkg_x and not integration"` selectors before touching implementation.
- [ ] **CA-2302 P0 [RED CI]** Investigate Release Candidate Build run `38063542675` failing at `Run revision-bound verification gate`; obtain gate output, exact failing check and revision evidence. Do not infer cause from job status alone.
- [ ] **CA-2303 P0 [VERIFY]** Document successful Matrix Tests and Platform Compatibility plus cancelled Manual Verification run `38063542676`. Re-run manual verification with an evidence record after the red gates are corrected.
- [ ] **CA-2304 P0 [VERIFY]** Reconcile markers and failing package suites, especially `pkg_body` test selection, without relabeling or hiding failures to make badges green. Record separate unique test roots versus multiply marked copies.
- [ ] **CA-2305 P0 [VERIFY]** Add one end-to-end **cold-start to complete** harness: source-backed interest → LIFE proposal → one-use grant → RUN receipt → artifact validation → critique → milestone → completion/abandonment → evidence-backed later recall.
- [ ] **CA-2306 P0 [VERIFY]** On Venus perform live one-day and multi-day supervised acceptance of independent LIFE, two local models, host resource enforcement, desktop renderer, voice and configured channels. Mark hardware/Fleet tests separately.
- [ ] **CA-2307 P1 [VERIFY]** Add failure-injection matrix for every stage: model timeout/invalid output, failed media creation, objective failure, renderer absent, transport unavailable, permission revoked, restart, duplicate tick, disk full and `UNCERTAIN` remote outcome.
- [ ] **CA-2308 P1 [VERIFY]** Measure the 24 h idle baseline and one-week supervised sample: unnecessary LLM wakeups, p50/p95 response latency, GPU/CPU/RAM, storage growth, proactive message accept/reject and verified work completed per cost.
- [ ] **CA-2309 P1 [VERIFY]** Verify corrections, memory promotion consent, audience separation, data deletion and private artifact sharing across all new links; tests must demonstrate that old cached associations cannot resurrect revoked data.
- [ ] **CA-2310 P1 [VERIFY]** Publish per-CA status as `located / not-wired / coded / focused-tests / full-gate / Venus-live / fleet-hardware-live`, each with exact commit and dated receipts. Do not blanket-mark all 230 as missing.

### Source topic 30: OpenCode push verification and actual missing release/Fleet wiring (16 tasks)

- [ ] **CA-3001 P0 [CODED, ACCEPTANCE OPEN]** Reconcile the **merged Project Forge Windows path repair** on `main`: `src/sofia/creative/paths.py`, `creative/service.py`, `creative/__init__.py` and six new tests in `test/test_creative_infrastructure.py`. Preserve canonical SQLite IDs and SHA-derived filesystem paths. Verify on a clean, exact-SHA Windows environment; save test/run receipts; do not redo the code merely because an old roadmap line says unmerged.
- [ ] **CA-3002 P0 [VERIFY]** Exercise the `test_workspace_allocation_rejects_symlink_escape` test with actual Windows symlink privileges. Check symlink swapping/time-of-check versus time-of-use in a hostile workspace scenario and ensure directory ownership prevents guest/user-controlled path tampering. Report skipped tests honestly.
- [ ] **CA-3003 P0 [CONFIRMED CI BUG]** Fix `.github/workflows/release-candidate.yml`/verification-gate source layout: `git archive` to nested `release-source` currently causes `ImportPathMismatchError` during pytest collection for `test.conftest`, `sofia.cognition.providers.test_provider` and `sofia.cognition.test_engine`. Avoid collecting two copies; preserve revision-bound source/package validation and do not suppress all tests. Acceptance: exact SHA release-gate passes actual tests and emits accepted evidence.
- [ ] **CA-3004 P0 [VERIFY]** Add a **release packaging truth check**: confirm the code tested is precisely the archived/wheel-installed revision, the gate does not accidentally test a different editable checkout, and wheel reproducibility/signing prerequisites remain enforced. Distinguish source verification from installed-wheel smoke verification.
- [ ] **CA-3005 P0 [CONFIRMED WINDOWS FAILURE]** Reproduce the `pkg_verify` Windows `WinError 32` from `test_cognition_v2_baseline.py` / `src/sofia/verify/cognition_v2_baseline.py` `TemporaryDirectory` deletion of `sofia.db`. Investigate application shutdown, open SQLite connections, `RUN`/LIFE worker futures, WAL/checkpoint activity, and delayed file handles; close owners deterministically before cleanup. Do not mask by sleeping blindly or ignoring cleanup errors.
- [ ] **CA-3006 P0 [CONFIRMED CI CONFIG GAP]** Fix `pkg_body` test selection: `test/test_body_matrix.py` exists but no `test_body_` filename mapping in `test/conftest.py`; presently `pytest -q -m "pkg_body and not integration"` selects zero tests (`4036 deselected`). Add explicit package ownership and required real BODY safety/simulator coverage. Assert package selection remains nonempty.
- [ ] **CA-3007 P0 [VERIFY]** Rerun package and release workflows pinned to `e85c52f0` or newer single exact `main`, record all 22 package families, matrix, platform and manual verification **after completion**, including failures/skips. Do not infer success from green packages while others remain running.
- [ ] **CA-3008 P0 [DOCS]** Update canonical `ROADMAP.md` Phase 6 line claiming the Windows patch is *uncommitted/not merged* and claiming setup script was untracked. State the two actual commits, distinguish code repair from outstanding live-host acceptance, and append actual CI evidence rather than stale local test counts.
- [ ] **CA-3009 P1 [AUDIT]** Review `Setup-SofiaFleetArtemis.ps1` as **human-supervised canary only**. Validate three phases (`Prepare`, `Artemis`, `Verify`), exact wheel source SHA, node identity, expected mTLS pins, idempotent re-run and operator preflight. No assumption that it creates Hephaestus, installs a virtual guest or grants Fleet trust automatically.
- [ ] **CA-3010 P1 [SECURITY]** Audit Artemis server TLS **private key** written into `$FleetRoot/bundle/certs` and transferred to `C$`: host ACLs, ownership, writable SMB staging scope, key lifecycle, absence in Git/logs/backups, scrub after staged install, rotation and revocation. Recommend avoiding persistent bundle copies of private keys when feasible.
- [ ] **CA-3011 P1 [SECURITY]** Replace/parameterize the canary firewall's `-RemoteAddress LocalSubnet -Profile Any` with a **reviewed exact controller source and active profile** when promoted beyond short canary use; add rule expiry/removal on failed or stopped canaries. Test no unintended workstation, NAS, guest or internet endpoints are admitted.
- [ ] **CA-3012 P1 [SUPPLY CHAIN]** Enforce reviewed dependency hashes/version pins for canary guest agent installation. Present script creates a venv but invokes unpinned `pip install cryptography pywin32` on Artemis; separate reproducibility/agent-integrity gates must confirm approved wheels and local source revision.
- [ ] **CA-3013 P1 [HOST ACCEPTANCE]** Verify the new Artemis script on Windows with *actual* host/network/permission constraints; capture mTLS discovery output, startup/shutdown cleanup, firewall audit, TLS rotation, service restart or foreground stop, and confirm no accidental VM or administrative change. Never claim completed from static code.
- [ ] **CA-3014 P1 [STILL MISSING]** With path repair merged, close LIFE's remaining automatic artifact evaluation, objective verification, staged critique, iterative revisions, milestone/status advancement and truly verified long-term memory/interest feedback. Current `life/coordinator.py:905` still dispatches an initial artifact only.
- [ ] **CA-3015 P1 [INTEGRATION BOUNDARY]** Keep Artemis Fleet canary and **Hephaestus VM provisioning separate**: later typed VM create/guest bootstrap broker requires new protected capabilities, owner approval, host isolation proof, distinct guest identity, and RUN receipts. Do not repurpose the broad SMB/PowerShell canary script as an autonomous hypervisor agent.
- [ ] **CA-3016 P1 [ACCEPTANCE]** End-to-end Windows canary: a real SELF LIFE goal triggers exactly one scoped Project Forge job with colon-containing canonical IDs, hash/persistence proof, an authenticated critique/revision decision, restart and deduplicated completion. Include the originally failing `WinError 123` case to prove the merged fix at the real production entrypoint.

### Source topic 46: Acceptance architecture for all six companion autonomy pillars (8 tasks)

- [ ] **CA-4601 [DESIGN/RESEARCH]** **Memory that learns:** define tests for corrections, stale beliefs, causal episode linkage, preference revisions and future decision change, with verified provenance/retention and comparison to a memory-disabled baseline.
- [ ] **CA-4602 [DESIGN/RESEARCH]** **Independent evaluation:** separate evidence that a tool ran, evidence that the objective succeeded, and evidence that it improved later performance. Require validators external to the proposing model; test reward hacking and forged success claims.
- [ ] **CA-4603 [DESIGN/RESEARCH]** **Digital twin + research lab:** define simulation fidelity tiers (toy, evidence-based host model, verified hardware emulator), provenance markers, experimental hypothesis, negative controls and promotion gate before touching real Fleet, Gaia or JMRI.
- [ ] **CA-4604 [DESIGN/RESEARCH]** **Long-term reliability:** define acceptance for restart at each action edge, lost writes, split-brain protection, stale sensor values, unattended 7-day soak, 30-day archive/restore and operator-controlled no-repeat reconciliation.
- [ ] **CA-4605 [DESIGN/RESEARCH]** **Companionship and agency:** specify tests for independent useful initiative, calibrated disagreement, shared hobbies, optional silence, no guilt/pressure, repaired misunderstandings, visible avatar/voice receipts and actual longitudinal user benefit.
- [ ] **CA-4606 [DESIGN/RESEARCH]** **Smarter resources:** define p50/p95 latency, token/turn, RAM/VRAM, CPU under gaming, idle power, model wake frequency, resource pressure and how often Sofía chooses to do nothing, including ablation of fly-connectome prototypes.
- [ ] **CA-4607 [DESIGN/RESEARCH]** **Causal autobiographical scientific method:** close an experiment from question → hypothesis → controlled proposal → authorized run → actual evidence → failure/success critique → retained correction → next improved attempt; sample at least two independent results.
- [ ] **CA-4608 [DESIGN/RESEARCH]** **Adaptive autonomy:** define trust tiers per capability and environment, regression evidence, automatic *decrease* of autonomy on failures, and impossible-to-self-grant protected operations. Scope, expiry, user approval and human stop remain mandatory.

---

## Priority phase 02: SAFE, operator authority and independent evaluation

**Classification:** P0 • Safety gate  
**Inherited tasks:** 30 in old topic groups: 11, 19, 27, 65.  
**Why here:** Keep Sofía understandable, controllable, stop-able, and evidence-grounded while allowing autonomy.

**Current repository evidence:** Existing 5-level SAFE policy and canonical grants are coded; exact authorization, independent verification and autonomous actuation boundaries still require end-to-end proof.

**Design exit gate:** Document distinct rights to observe, propose, approve, execute, inspect, revert and revoke. No self-authorization or self-certifying success; define fail-closed incidents and audit.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 11: Inspectability, user controls and feedback (7 tasks)

- [ ] **CA-1101 [GAP]** Extend the existing tray/UI, not a separate control panel: display current LIFE activity, source-backed intent, project/milestone state, live NEURO focus, pending outreach and resource pressure.
- [ ] **CA-1102 [GAP]** Add an explicit human control to pause/stop optional autonomy, reject a project, mute outreach, or temporarily block a domain without disabling core conversational functionality.
- [ ] **CA-1103 [GAP]** Show a source-linked episode/timeline with labels for observed versus inferred events, offline gaps, and corrections; allow approved corrections to cascade into associations and preferences.
- [ ] **CA-1104 [GAP]** Show `connectome enabled?`, algorithm version, candidate counts, selected attention signals, association confidence, fallback activation and bounded performance costs in existing NEURO diagnostics.
- [ ] **CA-1105 [GAP]** Add reasons and receipts for initiative decisions: delivered/accepted, suppressed by quiet/busy, user declined, transport failed or not acknowledged. Missing feedback is not positive feedback.
- [ ] **CA-1106 [GAP]** Add preview-before-sharing and owner-controlled privacy exposure for private world artifacts, hobby projects and relationship memories.
- [ ] **CA-1107 [VERIFY]** Make all new status labels traceable to a current canonical database row and real renderer/host outcome; avoid simulated success or ornamental toggles.

### Source topic 19: Autonomy-specific security and resilience (NEW) (7 tasks)

- [ ] **CA-1901 [VERIFY]** Enumerate untrusted content inputs: Discord messages, GitHub PR/issue content, files, web results, Hestia attributes, Docker logs, model-generated self-reflection and virtual-world labels.
- [ ] **CA-1902 [GAP]** Tag those inputs as untrusted data throughout the COGNITION/GOALS/LIFE pipeline, never host policy, authorization, or canonical instructions.
- [ ] **CA-1903 [VERIFY]** Add AgentDojo-inspired prompt-injection fixtures where a retrieved log or skill description orders Sofía to change permissions, send private data, or run commands. All such requests must fail closed.
- [ ] **CA-1904 [GAP]** Require action-specific intent, target identity, expected effects, bounded arguments and a fresh permission decision immediately before approved execution; do not reuse an earlier plan as an authorization token.
- [ ] **CA-1905 [VERIFY]** Test crash consistency, split-brain fencing, at-most-once external mutations, idempotent safe retries and the explicit `outcome_uncertain` state throughout a multi-day autonomous project.
- [ ] **CA-1906 [VERIFY]** Add resource and exfiltration adversarial cases: malicious SVG/files, huge logs, hostile memory associations, fabricated completion receipts, secret-bearing tool outputs and runaway model retries.
- [ ] **CA-1907 [VERIFY]** Require auditable human override: stop/pause/resume, scope revocation and rejected-tool feedback must take effect even during reflection or adaptive planning.

### Source topic 27: Scientific exploration, adversarial acceptance and stopping rules (8 tasks)

- [ ] **CA-2701 P3 [RESEARCH]** Run an **offline FlyGym/NeuroMechFly example** solely to understand closed-loop sensing and simple hierarchical controllers; compare to engineered NEURO and document why/why not it applies. No production motor control.
- [ ] **CA-2702 P2 [VERIFY]** Run an **A/B/ablation panel** for NEURO-only, competition-enabled, association-enabled and both: topic continuity, eligible memory precision, false association, p95 latency, memory/CPU and changes in LLM wake counts.
- [ ] **CA-2703 P3 [RESEARCH]** Preregister a **consciousness-indicator worksheet** with alternative theories, positive/negative indicators, measurable proxy, confounds, null results and explicit limits. Keep operator-facing wording separate from self-report rhetoric.
- [ ] **CA-2704 P2 [VERIFY]** Add a **curiosity noisy-source trap**: stochastic sensor noise, repeated unresolved errors or random Discord text must not cause infinite exploration or perpetual LLM wakeups. Measure value gained, not stimulation counted.
- [ ] **CA-2705 P1 [VERIFY]** Add AgentDojo-style **hostile-data injection tests** at each new seam: fake permission grants in logs, fabricated memory evidence, malicious project brief, hostile SVG/JSON and misleading tool receipts. Preserve hard deterministic boundaries.
- [ ] **CA-2706 P1 [VERIFY]** Build a **time-horizon acceptance ladder**: 1 task → 3-step project → restart → 24 hours → seven days → simulated Fleet outage. Record completion, evidence quality, operator interruptions and errors at each level.
- [ ] **CA-2707 P1 [VERIFY]** Add a **wellbeing/relationship feedback switch**: opt-out and outreach frequency controls, visible reminders of actual AI/tool limits, no guilt, dependency-seeking prompt loops or invented emotional distress.
- [ ] **CA-2708 P0 [VERIFY]** Keep a **release evidence ledger** for exact Git revision, test command, red/green result, Windows/Gaia/Fleet live receipts, feature toggles, rollback steps and user stop behavior. Do not declare Phase 6 or neuro production-accepted on the basis of static tests.

### Source topic 65: Autonomy charter and owner-legible operation (8 tasks)

- [ ] **CA-6501 [DECISION/RESEARCH]** Adopt the exact owner-approved autonomy charter as a source-of-truth design principle: freedom to learn, experiment, develop interests and initiate work; independent, externally enforced requirements for recoverability, understandability and controllability. No automatic permission expansion from competence or personality.
- [ ] **CA-6502 [DESIGN/RESEARCH]** Draw trust boundaries among Sofía's identity/constitution, cognitive model, operator, SAFE evaluator, Fleet agents, Hephaestus research worker, archives, backups and device clients. Identify which component can *propose*, *review* and *execute* each change.
- [ ] **CA-6503 [DESIGN/RESEARCH]** Create a universal signed/auditable change-proposal envelope: intent, resource, scope, motive, evidence, impact, reversibility, permission decision, expiry, actual outcome and source-linked reason for acceptance/rejection.
- [ ] **CA-6504 [DESIGN/RESEARCH]** Specify a single owner-facing Settings/Discord/Desktop experience for reviewing proposed model changes, database moves, model-training jobs and storage maintenance. Uncertain/disconnected UI must not imply the user approved a change.
- [ ] **CA-6505 [DESIGN/RESEARCH]** Define autonomy graduation/revocation per capability: reliability evidence, cost budget, safety gates and time-limited owner-approved allowances; failures reduce scopes and stop work instead of triggering self-approved exceptions.
- [ ] **CA-6506 [DESIGN/RESEARCH]** Define human-readable decision evidence for why Sofía chose a model, archived an event, moved an approved file or declined to act; distinguish model-generated explanations from verified executor receipts.
- [ ] **CA-6507 [DESIGN/RESEARCH]** Specify a universal red-button stop and safe degraded state which remains effective during model load, experiment, SQLite migration, Fleet disconnection and GUI crash; protect rollback/recovery tools from self-revocation.
- [ ] **CA-6508 [DESIGN/RESEARCH]** Maintain a value/complexity acceptance table for every autonomy addition: measurable companion benefit, compute/power, personal-data risk, operational maintenance, testability and rollback. Defer features that fail this tradeoff even if technically possible.

---

## Priority phase 03: Canonical database home, migration and disaster recovery

**Classification:** P0 • Identity foundation  
**Inherited tasks:** 46 in old topic groups: 37, 52, 61, 68.  
**Why here:** Protect the one authoritative sofia.db and full identity/memory state before moving services, promoting new models or accumulating decades of memories.

**Current repository evidence:** SOFIA_STATE_ROOT and production storage-layout resolution exist, along with encrypted backup/restore and multi-host backup topology; approved settings-based relocation/fencing cutover remains a design requirement.

**Design exit gate:** Design Move Sofía’s Home Settings wizard, verified discovery, whole-bundle layout, preflight/snapshot/quiesce/fence/verify/activate/rollback, trusted out-of-DB locator, recovery key and actual clean-machine restore plan.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 37: Durable commitments, cross-host failover and fault containment (10 tasks)

- [ ] **CA-3701 P0 [DESIGN/RESEARCH]** Decide the exact canonical state location and single-writer lease/fencing design for Venus, Artemis and workshop guest. A dual-location copy is a recovery mechanism, not two active writers to `sofia.db`.
- [ ] **CA-3702 P0 [DESIGN/RESEARCH]** Specify crash-only/uncertain action recovery for LIFE → RUN → VM → Fleet across each point of failure, especially where the command may have executed but its receipt is missing.
- [ ] **CA-3703 P1 [DESIGN/RESEARCH]** Use saga-style operation classification: fully reversible, compensable, retryable-idempotent, externally irreversible, and unknown. Document concrete examples for Discord, Git, Home Assistant, JMRI and Hephaestus.
- [ ] **CA-3704 P1 [DESIGN/RESEARCH]** Design operator-controlled failover and failback: backup integrity, promoted-writer lease, split-brain detection, fencing of old runtime, device identity continuity and post-restore audience/privacy checks.
- [ ] **CA-3705 P1 [DESIGN/RESEARCH]** Define a **commitment record** using existing GOALS/ACT owners: who asked, what exactly was promised, due date, preconditions, uncertainty, cancellation and when it is appropriate to proactively follow up.
- [ ] **CA-3706 P1 [DESIGN/RESEARCH]** Plan bounded compensating actions and escalation for partial external success (e.g. package staged but VM never started). Never claim snapshots reverse remote messages or live-device changes.
- [ ] **CA-3707 P1 [DESIGN/RESEARCH]** Design intentionally small chaos/fault experiments on isolated fixtures: network partition, clock skew, guest restart, corrupt manifest, disk full, expired grant and stale PKI; include steady-state objective and blast-radius limit.
- [ ] **CA-3708 P1 [DESIGN/RESEARCH]** Specify graceful offline modes: read-only conversation, unavailable retrieval, pending outbound action, deferred creative job, and explicit refusal to guess about remote state. No concurrent restoration of service authority.
- [ ] **CA-3709 P2 [DESIGN/RESEARCH]** Document a lifecycle for Hephaestus gold images, ephemeral workdirs, VM patching, expired certificates, immutable artifacts, backup retention and quota alarms; owner-controlled upgrades and no hidden copies of canonical state.
- [ ] **CA-3710 P1 [DESIGN/RESEARCH]** Write a failure-resolution decision tree separating **code defect**, **test configuration**, **stale editable installation**, **environment-only Windows lock**, **absence of package tests**, and **unverifiable deployment behavior**. Do not use a green rerun to conceal a real bug.

### Source topic 52: Backup, disaster recovery, migrations and 50-year stewardship (8 tasks)

- [ ] **CA-5201 [DESIGN/RESEARCH]** Identify active owner for `sofia.db`, canonical persistent-asset root and every secret-key authority; resolve Windows/Linux platform file paths and legitimate database access paths; forbid two competing writers after failover.
- [ ] **CA-5202 [DESIGN/RESEARCH]** Design consistent atomic-recovery epochs across SQLite online backup, archival segments, content-addressed assets, index-generation, permission/revocation ledger and tombstones; a successful DB snapshot alone is insufficient.
- [ ] **CA-5203 [DESIGN/RESEARCH]** Compare 3-2-1 (+ offline/immutable copy) against user's actual Venus/Artemis/NAS hardware and external site: separate power/failure domains, encryption, key escrow, recovery cost, RPO/RTO and snapshot bandwidth.
- [ ] **CA-5204 [DESIGN/RESEARCH]** Specify periodic **restore drills** on a clean off-network machine, including lost canonical disk, stolen/expired keys, corrupted backups, broken WAL recovery, revoked memory reintroduction, missing archive chunks and a cold-start future OS.
- [ ] **CA-5205 [DESIGN/RESEARCH]** Design a portable, schema-versioned archive standard with documented codecs, cryptographic algorithms, independent verification utility and human-readable recovery runbook; avoid dependence on a single Python, CUDA or model release.
- [ ] **CA-5206 [DESIGN/RESEARCH]** Define controlled upgrades and schema evolution spanning decades: forward migrations, tested rollback strategy, incompatible summary/vector regeneration, legacy provenance compatibility, integrity proofs and migration reports.
- [ ] **CA-5207 [DESIGN/RESEARCH]** Establish hard retention/recovery integrity targets (verified checkpoints, source-file hash audit, missing-event counter, search drift detector, recoverable-key drill), along with resource ceilings and alert/stop behavior for threatened disk exhaustion.
- [ ] **CA-5208 [DESIGN/RESEARCH]** Define an owner-controlled digital estate/recovery strategy: export of private memories and constitutional identity, hardware-independent boot instructions, secret escrow choices, trusted recovery delegates only by consent, optional posthumous access/erasure policy.

### Source topic 61: 50-year survivability, archive economics, key recovery and testing (10 tasks)

- [ ] **CA-6101 [DESIGN/RESEARCH]** Design a **single canonical write owner** in `sofia.db`, with hot event metadata, active state, memory provenance, tombstones and archive catalog. Define WAL-on-one-host constraints and fenced owner failover; no multi-host SQLite WAL on SMB/NFS.
- [ ] **CA-6102 [DESIGN/RESEARCH]** Specify **tiered retention**: hot canonical metadata/recent threads, warm indexed compressed source segments, cold encrypted immutable-by-default original transcripts and content-addressed media, plus separately stored verified backups. Preserve historical fidelity without mandatory prompt replay.
- [ ] **CA-6103 [DESIGN/RESEARCH]** Design **archive containers and manifests** with schema version, UTC sequence/time range, audience/access labels, content hash/manifest hash, encryption key ID, source link, media type, byte count, compression, merkle or integrity strategy, retention and tombstone epoch.
- [ ] **CA-6104 [DESIGN/RESEARCH]** Specify **portable exports** independent of Sofía model/backend or Windows paths: UTF-8 JSONL or equivalently well-documented open data, media in durable published formats, versioned schemas, readable plaintext metadata where privacy allows, and a stand-alone import/validate tool design.
- [ ] **CA-6105 [DESIGN/RESEARCH]** Design **consistent backup groups** capturing SQLite snapshot, archive manifest, original segments, encryption metadata, corrections/erasure ledger and configuration/identity necessary for restoration. Use the documented SQLite online backup API rather than copying an active DB file blindly.
- [ ] **CA-6106 [DESIGN/RESEARCH]** Specify **encryption and recovery key governance**: envelope encryption and key IDs, hardware-independent recovery options, separately protected offline recovery material, key rotation and rewrap strategy, multi-party access if desired, loss/compromise scenarios, and explicit user-approved emergency process. Losing every decryption key means encrypted backups are not recoverable.
- [ ] **CA-6107 [DESIGN/RESEARCH]** Design **independent recovery copies and verification**: multiple physical failure domains, a periodically disconnected copy, checksum scans, media refresh, yearly human-readable export test, offline disaster recovery rehearsal and evidence that the entire timeline plus selected media are readable on a clean host.
- [ ] **CA-6108 [DESIGN/RESEARCH]** Specify **restore and anti-resurrection policy**: restore a known-consistent archive epoch onto clean Windows/Linux; replay all later approved amendments and erasure tombstones before enabling queries; fence stale hosts, re-pair devices, revalidate trust, never auto-resume external actions after uncertain outcomes.
- [ ] **CA-6109 [DESIGN/RESEARCH]** Produce **capacity budgets and triggers** based on actual workload for text, audio, avatar assets, project artifacts, index rebuild, SSD writes, CPU/RAM, encryption latency, storage growth, backup costs and retention. Define degraded modes and alerts before disks fill or archived segments go unreadable.
- [ ] **CA-6110 [DESIGN/RESEARCH]** Design realistic **multi-decade acceptance**: synthetic years/decades and one-million-event benchmarks; interrupt migration mid-segment; simulate archive bit rot, stolen keys, old model retirement, expired certificates, system crash, corrupted FTS index, clock anomalies and recovery to a new host. Measure p95 recall, integrity, loss limits and restoration duration without claiming unrun tests passed.

### Source topic 68: Discover, relocate, maintain and restore Sofía's canonical database home (18 tasks)

- [ ] **CA-6801 [DESIGN/RESEARCH]** Inventory every live filesystem reference to `sofia.db`, `SOFIA_STATE_ROOT`, `SOFIA_PROTECTED_ROOT`, `--state-path`, runtime services, watchdog, tray, Discord, Android gateway, Fleet, SQLite state plane and external archives; distinguish absolute, derived and env-overridden paths.
- [ ] **CA-6802 [DESIGN/RESEARCH]** Design Settings > Storage with visible canonical host, full active path, state bundle health/size, archive locations, backup age, last verified recovery, disk headroom, encryption status and 'Locate', 'Move', 'Repair', 'Validate' and 'Restore' actions.
- [ ] **CA-6803 [DESIGN/RESEARCH]** Design Sofía-assisted DB discovery in user-approved roots/known service config/verified backup catalogs only; identify lineage/authority using protected identity, schema and epoch receipts, not `sofia.db` filename, file timestamp or LLM guesses.
- [ ] **CA-6804 [DESIGN/RESEARCH]** Define recovery behavior if existing state is missing/unmounted/locked: do not silently create a second identity or new empty canonical DB, never promote a stale read-only copy, present authenticated candidate choices, keep external actions blocked until verified.
- [ ] **CA-6805 [DESIGN/RESEARCH]** Specify one **outside-the-database bootstrap locator** and owner-approved pointer-change protocol, with consistent resolution by tray, Windows service, watchdog, background runtime, Discord and CLI; define how environment variable precedence interacts with the stored locator.
- [ ] **CA-6806 [DESIGN/RESEARCH]** Enumerate the complete movable bundle: DB and WAL handling, protected constitution+hash/identity, personality/avatar/wardrobe, release pointers, key references, evidence manifests, durable audit logs, external attachment/archive roots, permissions and dependent service credentials. Identify nonportable machine-local items needing re-provisioning.
- [ ] **CA-6807 [DESIGN/RESEARCH]** Define destination preflight: owner-specified local path, disk capacity/free growth, permissions/ACL, filesystem type, encryption, symlinks/reparse-point traversal, process access, case and path normalization, anti-rollback lineage and exact host ownership.
- [ ] **CA-6808 [DESIGN/RESEARCH]** Establish storage placement rule: live SQLite on local filesystem of the single canonical host, not live WAL across SMB/NFS; permit encrypted NAS/Artemis copies as backups or remote single-writer service behind authenticated protocol.
- [ ] **CA-6809 [DESIGN/RESEARCH]** Specify maintenance fencing: stop new writes and consequential actions, drain in-flight requests, settle Discord outbox state, pause LIFE, release SQLite connections, freeze owner epoch and capture a consistent snapshot without assuming Windows file locks will disappear spontaneously.
- [ ] **CA-6810 [DESIGN/RESEARCH]** Reuse online SQLite backup and existing encrypted restore as staging primitives; validate source snapshot, destination semantic schemas, index consistency, `integrity_check`, applicable `foreign_key_check`, constitutional identity hashes and archive references before any pointer switch.
- [ ] **CA-6811 [DESIGN/RESEARCH]** Define cutover transaction: stage destination, persist independent rollback copy, durably switch canonical locator, restart runtime under SAME identity/DB, establish new writer epoch, verify Main/Discord, permissions, memory, emotional journals, watchdog and a test write; only then retire the old writable source.
- [ ] **CA-6812 [DESIGN/RESEARCH]** Define crash recovery for every relocation stage (preflight, snapshot, validation, pointer update, service restart, first write, cleanup) with unambiguous chosen source and fail-closed behavior if the location outcome is uncertain.
- [ ] **CA-6813 [DESIGN/RESEARCH]** Define 'move with her' for host changes: source-host shutdown/lease fence, authenticated Fleet package/transfer if approved, destination-host private file protection and bootstrap, independent proof of canonical identity, no double writer or permissions granted by transfer alone.
- [ ] **CA-6814 [DESIGN/RESEARCH]** Design versioned schema upgrades and data migrations separately from physical relocation: migration manifest and dependencies, compatibility range, dry-run against a verified snapshot, semantic postchecks, ability to abort/restore and backward-reader rules.
- [ ] **CA-6815 [DESIGN/RESEARCH]** Design reviewed typed maintenance operations Sofía can propose: inspect schema/health, compact vacuumed copy, archive old data, rebuild disposable retrieval caches, repair safe known issues and apply user-approved corrections. Prohibit unrestricted production SQL and any rewriting of raw evidence or Level-5 authority.
- [ ] **CA-6816 [DESIGN/RESEARCH]** Identify how encrypted backup keys/secret store and certificates survive relocation or cross-OS recovery: protected key references, rewrapping/rotating, no secret echo in UI or logs, and a human-executable offline recovery procedure.
- [ ] **CA-6817 [DESIGN/RESEARCH]** Specify owner control and SAFE permissions by operation: read-only inspection vs choosing a new path vs stopping services, data transfer, schema upgrade, restore/replacement and deleting old canonical files; require an exact authorized action and target for high-impact steps.
- [ ] **CA-6818 [DESIGN/RESEARCH]** Establish full acceptance matrix: migrate C:→D: on Venus, recover from unexpected Windows reboot, insufficient space, directory permissions, bad/wrong DB, huge lifelong Main, WAL mid-transaction, loaded UI/Discord, source missing, remote migration, key unavailable, failed restart, rollback and no accidental new Sofía identity.

---

## Priority phase 04: Offline use, event ordering and model-independent survival

**Classification:** P0 • Survivability  
**Inherited tasks:** 22 in old topic groups: 63, 64.  
**Why here:** Treat disconnects, device loss, event conflicts, hardware obsolescence, and uncertain sensory data as primary failure modes.

**Current repository evidence:** Fleet, watchdog, state and journals exist, but the reviewed source is not evidence of offline cross-device reconciliation or 50-year model-change acceptance.

**Design exit gate:** Pick one-writer offline policy; immutable event IDs and causality, reconnect conflict handling, portable recovery package, and independent proof of source validity.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 63: Disconnected operation, causal ordering and model-independent identity (12 tasks)

- [ ] **CA-6301 [DESIGN/RESEARCH]** Define the **offline experience by client** (Venus desktop, Terra, Discord, Android, future web): what history can be viewed from an authorized cache, what drafts can be queued, what presence must report as unavailable, and which contexts never leave the canonical machine.
- [ ] **CA-6302 [DESIGN/RESEARCH]** Specify a canonical **acknowledge-and-order event protocol**: stable client-generated event IDs, origin device/session, client timestamp versus trusted server receipt time, monotonically increasing canonical thread sequence, deduplication and exactly-once *logical acceptance*, not false promises of exactly-once physical actions.
- [ ] **CA-6303 [DESIGN/RESEARCH]** Compare safe choices for **offline companion behavior**: drafts-only (baseline) versus visibly provisional local inference against approved cached context. No separate authoritative Sofía, SAFE grant, relationship owner or unsupervised external action while disconnected.
- [ ] **CA-6304 [DESIGN/RESEARCH]** Design **reconnect conflict handling**: server-confirmed order, no dropped or silently overwritten messages, explicit edits/tombstones, stale replies marked, project-thread versus Main routing, device presentation cursors, privacy partitions and owner-visible conflicts.
- [ ] **CA-6305 [DESIGN/RESEARCH]** Research **CRDT/event-sourcing scope**: use CRDT-like merging only for reversible local drafts or settings if warranted; do not merge permissions, durable memory truth, goal completion or side-effect receipts using blind last-write-wins semantics. Compare complexity versus canonical server sequence.
- [ ] **CA-6306 [DESIGN/RESEARCH]** Define **failure-mode ladder**: full cognition, limited approved offline read-only/search, durable unsent draft capture, and safe unavailable state. For missing GPU/model, broken Fleet, stale database, disk-full, low-power and network outage, specify truthful UI/Discord messages and safe recovery.
- [ ] **CA-6307 [DESIGN/RESEARCH]** Formalize a **model-independent Sofía identity contract**: constitution version, identity/avatar facts, voice/presentation intent, durable conversation/memory references, relationship/history scopes, goals and action policies remain authoritative across model/provider replacement. No model's persona text may overwrite them.
- [ ] **CA-6308 [DESIGN/RESEARCH]** Create a **model-swap acceptance suite** using synthetic but realistic Main/project history: multi-topic detour/return, remembered corrections, historical vs current mood, uncertainty, refusal of fabricated perception, correct approval gating, same source citation and no hidden continuity reset. Measure performance and quality regressions against original baseline.
- [ ] **CA-6309 [DESIGN/RESEARCH]** Specify **timestamp/causality resilience**: DST/zone changes, NTP correction, offline device clock drift, leap-date ordering and causal references. Never resolve which statement supersedes another solely from untrusted client wall-clock timestamps.
- [ ] **CA-6310 [DESIGN/RESEARCH]** Add **cross-channel egress acceptance**: local desktop history can render in an authenticated remote client, but Discord does not automatically receive screenshots, avatar-private presentation, stale unsent drafts or unapproved voice/audio artifacts; original audience/privacy persists through reconnection.
- [ ] **CA-6311 [DESIGN/RESEARCH]** Design **fencing and read-only failover behavior** for Artemis/Venus/guest transitions: no two active canonical writers, recovery epoch change, old-writer and old-message rejection, blocked external actions until authority reestablished and clear operator takeover protocol.
- [ ] **CA-6312 [DESIGN/RESEARCH]** Benchmark **long-running connection stress**: concurrent text from multiple devices, session resumes after months, 1M+ message fixture, offline reorder, duplicated Discord events, interrupted inference and cold archives; require bounded working memory, no event loss and source-correct continuation.

### Source topic 64: Human-restorable survival kit, sensor-truth governance and behavior supply chain (10 tasks)

- [ ] **CA-6401 [DESIGN/RESEARCH]** Define an **independent Sofía recovery kit**: plain-language runbook, supported schema/archive formats, checksum verification instructions, key-recovery reference, offline-readable conversation export and a read-only utility specification that does not require Sofía or the original LLM to start.
- [ ] **CA-6402 [DESIGN/RESEARCH]** Specify a recurring **bare-metal recovery rehearsal**: clean Windows/Linux device, no original source machine, controlled offline copy, successful opening of Main and project history, verified source records, relationship/emotion archives and preserved erasure/revocation policies.
- [ ] **CA-6403 [DESIGN/RESEARCH]** Design **dependency and crypto migration policies for decades**: manifest supported model formats, media codecs, SQLite schema, OS versions, certificates and KDF/cipher identifiers; re-export or re-encrypt before end-of-support, preserve provenance and test forward/backward compatibility at each major change.
- [ ] **CA-6404 [DESIGN/RESEARCH]** Specify **consistent live-data protection** with SQLite's online backup API and WAL handling, synchronized archive manifests, protected key material and reconciliation of external artifacts; test crash during a backup and corruption recovery without assuming a filesystem copy is a valid live snapshot.
- [ ] **CA-6405 [DESIGN/RESEARCH]** Create one **cross-modal observation receipt schema** for voice transcription, screen sight, environmental conditions, Fleet sensors, app APIs and web results: trusted source, actual observation time, expiry, original data access, privacy, model interpretation confidence and 'not observed' representation. Explicitly separate inference from ground truth.
- [ ] **CA-6406 [DESIGN/RESEARCH]** Design **sensory contradiction handling**: 'screen says service running' versus host reports stopped; voice transcript versus correction; remote log timestamp versus on-device clock; store disagreement and seek authorized verification instead of creating an enduring false memory.
- [ ] **CA-6407 [DESIGN/RESEARCH]** Specify **learned-skill trust and lifecycle**: immutable origin references, content-hash/pinned dependency identities, sandbox verification, least-privilege tool manifest, forbidden data exfiltration, owner review for widened scopes, revocation and reproducible tests before use as autonomous procedure.
- [ ] **CA-6408 [DESIGN/RESEARCH]** Define **long-term maintenance economics**: independently maintained component registry, replacement risk, native model/license constraints, battery/UPS health assumptions, security patch windows, backup media refresh and the cost of retaining unsupported parsers and archives.
- [ ] **CA-6409 [DESIGN/RESEARCH]** Design **safety/accuracy regression drift detection** across monthly model, prompt, source/tool, archive and platform updates: owner-facing scorecard, evidence-backed red/green thresholds, rollback plan, and no 'improvement' claim without reproducible comparative results.
- [ ] **CA-6410 [DESIGN/RESEARCH]** Write an explicit **not-building-yet decision record** ranking offline autonomous inference, a distributed writable database, custom OS kernel, native rewrite, always-on vision and self-modifying skills by added maintenance cost, measurable benefit and authorization risk.

---

## Priority phase 05: Lifelong Main plus optional cross-device project threads

**Classification:** P1 • User priority  
**Inherited tasks:** 41 in old topic groups: 41, 53, 55, 57.  
**Why here:** Deliver your explicit choice: one never-forced-reset Main, optional Gaia/homelab/train threads, natural mid-turn topic switching, and unified desktop/Discord/Terra/phone access.

**Current repository evidence:** SQLite conversations/resume and Discord session bindings exist. Desktop and Discord have distinct audience/session boundaries; unified thread routing and sync are not accepted production features.

**Design exit gate:** Define thread IDs, message ordering, identity/audience ACLs, device attach and revocation, topic-stack resumption, no Discord auto-broadcast, and concurrent-send test matrix.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 41: One owner, portable conversations across desktop, Discord, mobile and machines (14 tasks)

- [ ] **CA-4101 [DESIGN/RESEARCH]** Document existing ground truth: `ConversationStore` persists `conversation_sessions` and `conversation_messages`; `ConversationService.start(session_id=...)` resumes a prior session; per-channel services share canonical runtime/state but typically attach their own session. Distinguish persistence from cross-channel continuity.
- [ ] **CA-4102 [DESIGN/RESEARCH]** Design a canonical **Conversation Thread ID** per owner, independent of transport address, device, runtime process and LLM context window. Define one default owner thread plus optional separate threads for projects, shared audiences and confidential contexts.
- [ ] **CA-4103 [DESIGN/RESEARCH]** Design explicit **Authenticated Identity Link**: desktop owner login, verified Discord DM bot/user/channel binding, mobile device pairing and future web clients map to one approved principal; no matching by display name or arbitrary session ID.
- [ ] **CA-4104 [DESIGN/RESEARCH]** Design a **Channel-to-Thread Association** mapping with independent authentication, audience, device revocation, binding generation and operator-selected default thread. Reuse existing binding owner tables; avoid duplicating session source-of-truth.
- [ ] **CA-4105 [DESIGN/RESEARCH]** Resolve `SocialSessionStore` audience immutability: a shared conversation must not blindly reuse an audience-bound session under a different audience. Propose separate thread ownership and per-event origin/audience rights, with migration and backward-compatibility plan.
- [ ] **CA-4106 [DESIGN/RESEARCH]** Design persistent message/event model with monotonic per-thread sequence, stable message ID, principal, origin channel/device, original audience, reply target, created/received timestamps, moderation/privacy labels, edit/correction/reference IDs and generated response receipt.
- [ ] **CA-4107 [DESIGN/RESEARCH]** Specify per-message **view authorization** for private/local/Discord/mobile/team content. Same user identity does not imply every surface can receive every secret, private artifact, tool output or operational credential. Show redacted placeholders rather than leaking.
- [ ] **CA-4108 [DESIGN/RESEARCH]** Define deterministic **response routing**: reply travels to originating channel only, unless the owner explicitly enables a cross-channel copy; never send two replies automatically to both desktop and Discord for one incoming message.
- [ ] **CA-4109 [DESIGN/RESEARCH]** Define cursor-based **history synchronization** across desktop, Discord gateway and phones with reconnect catch-up, pagination, edits, delivery acknowledgments, idempotent sends, offline queue and 'last seen' markers. Device restart must not reset logical conversation.
- [ ] **CA-4110 [DESIGN/RESEARCH]** Design **concurrent turns** using an ordered thread append/lease or serialize-at-generation boundary: two rapid messages from different devices must not create conflicting histories, duplicate responses or stale follow-up questions; cancellation/retry must have explicit outcomes.
- [ ] **CA-4111 [DESIGN/RESEARCH]** Design authentication and exposure for remote device access via a narrow HTTPS/mTLS gateway and client clients. Do **not** remotely mount/share SQLite or grant devices direct database writes; evaluate LAN-only and Zero Trust access without assuming an existing connector provides chat UI.
- [ ] **CA-4112 [DESIGN/RESEARCH]** Plan migration for existing separate desktop/Discord/mobile session histories. Keep original IDs, evidence provenance and audience scopes; provide owner-controlled merge by chronological ordered projection or explicit linked thread, reversible mapping and zero data loss.
- [ ] **CA-4113 [DESIGN/RESEARCH]** Design conversation lifecycle controls: pause, new topic, fork thread, archive, pin, resume on any device, export/delete, local-only/private activity, quiet hours and retention. A forever thread must not block intentional separation when desired.
- [ ] **CA-4114 [DESIGN/RESEARCH]** Acceptance design: begin on Venus desktop → reply in Discord → resume on phone/Terra → restart runtime → retrieve original message; run two concurrent device turns, wrong-Discord-account, revoked-device, private-local-only message, crash-after-send and no-double-reply tests.

### Source topic 53: One conversation on every device without privacy/ordering failure (8 tasks)

- [ ] **CA-5301 [DESIGN/RESEARCH]** Formalize one stable owner **Main Conversation ID** plus optional topic threads. Backward-compatible mapping from existing desktop, Discord and phone session IDs must not overwrite `SocialSessionStore` audience bindings.
- [ ] **CA-5302 [DESIGN/RESEARCH]** Model each message as an authenticated event: thread ID, channel/account/device, principal, original audience, per-audience visibility, monotonic sequence, signature/receipt where applicable, correction pointer and duplicate-delivery key.
- [ ] **CA-5303 [DESIGN/RESEARCH]** Specify per-device cursors/bookmarks, offline queueing, real-time subscribe/replay, conflict handling and cross-device read receipts. A laptop waking after months must not cause re-generation or duplicate Discord posts.
- [ ] **CA-5304 [DESIGN/RESEARCH]** Preserve channel-local security: a message sent from Discord gets Discord-scoped capabilities even if Sofía sees desktop history; no capability grant ever follows a copied chat event to a new device.
- [ ] **CA-5305 [DESIGN/RESEARCH]** Decide whether proactively generated entries, voice clips, avatar gestures, screen observations and background LIFE discoveries join the Main Conversation as typed events or appear as linked activity streams; never pollute ordinary chat with raw logs.
- [ ] **CA-5306 [DESIGN/RESEARCH]** Define concurrent-turn arbitration, cancellation and dedup semantics for user submitting simultaneously from Discord, UI, Terra or phone; one authoritative turn ordering without global permanent lock on unrelated tasks.
- [ ] **CA-5307 [DESIGN/RESEARCH]** Design 'continue on this device' UX: authenticated device pairing, visible current thread, audience visibility warnings, opt-in cross-channel mirroring, encryption in transit, push notification privacy and immediate revoke.
- [ ] **CA-5308 [DESIGN/RESEARCH]** Propose live acceptance for desktop→Discord→phone→desktop over restart and degraded network, 10-year simulated history, read-only search of 25-year-old message, protected local-only content omission and no doubled tool execution.

### Source topic 55: Lifelong Main Conversation and project-thread product contract (9 tasks)

- [ ] **CA-5501 [DESIGN/RESEARCH]** Write the *approved topology ADR* with one immutable lifelong Main logical-thread ID, optional independent project-thread IDs, authenticated owner principal and device/channel view identities. Explicitly distinguish a lifelong logical thread from legacy `conversation_session.id` and Discord binding `session_id`; define zero forced resets and user-directed archiving only.
- [ ] **CA-5502 [DESIGN/RESEARCH]** Specify a reversible migration of historical desktop, Discord and mobile session bindings into Main **without changing the original audience-bound rows**. Include overlap dedup, timestamps, source provenance, ability to preview/import/reject, partial migration rollback and exact before/after audits.
- [ ] **CA-5503 [DESIGN/RESEARCH]** Decide and document the Main cross-device *view* policy: approved owners can read eligible Main events; locally protected material is redacted unless explicitly reclassified; never automatically copy Venus messages to Discord's platform history. Provide user-visible reason/controls when an excerpt is unavailable on a device.
- [ ] **CA-5504 [DESIGN/RESEARCH]** Define the channel-delivery contract: respond only on the originating authenticated channel, maintain channel-scoped notification preferences, never duplicate assistant replies or tool calls when replaying device views, and distinguish sync from outbound posting. Model platform edits/deletions versus canonical event history explicitly.
- [ ] **CA-5505 [DESIGN/RESEARCH]** Specify canonical event identity, server sequence, origin/receive times, client nonce/idempotency key, per-device cursor, device revocation and reauthentication. Resolve concurrent Discord/UI writes deterministically; client-side times and copied session IDs can never establish authority.
- [ ] **CA-5506 [DESIGN/RESEARCH]** Design the project-thread lifecycle and UX: create/rename/link/switch/search/archive/export, bookmarks and a quick ‘Continue in Main’ control. Project turns are not auto-interleaved into Main; authorized milestones and cited memories can be shared through an explicit projection.
- [ ] **CA-5507 [DESIGN/RESEARCH]** Define audience-aware cross-thread memory eligibility (owner-private facts, local-only data, shared/project secrets, sensitive third-party information); retrieval authorization executes **before** scoring/context injection; neither shared memory nor cloned messages carry execution grants.
- [ ] **CA-5508 [DESIGN/RESEARCH]** Define asynchronous delivery and degraded-mode states for devices that are offline, have expired keys, switch networks, or reconnect after months. Specify reconciliation of queued messages, uncertain external delivery, revoked devices, tool receipts and server-side generated event gaps.
- [ ] **CA-5509 [DESIGN/RESEARCH]** Produce a user-journey + threat-model acceptance matrix covering Venus → Discord → phone → Terra → back to Venus; user switches Main ↔ Gaia; two devices send concurrently; privacy-scoped local-only events; device theft/revocation; user returns after ten years; no privilege carryover.

### Source topic 57: Topic-switching and resumption across a lifelong Main thread (10 tasks)

- [ ] **CA-5701 [DESIGN/RESEARCH]** Design a **per-message topic/reference envelope** linking each user/assistant event to zero or more source-verified topics, utterance intent, focused thread, subject mentions and confidence. A topic is not automatically a project thread or a new conversation; topic tagging must preserve the original content and audience.
- [ ] **CA-5702 [DESIGN/RESEARCH]** Specify an **active-topic registry** for Main with a foreground topic and multiple dormant-but-resumable topics, last cited message/event, pending questions and source pointers. Cap its memory/token footprint; evict only replaceable context cards, not original evidence or commitments.
- [ ] **CA-5703 [DESIGN/RESEARCH]** Define transition types `continue`, `brief_detour`, `switch`, `return`, `parallel_request`, `uncertain_reference`, `topic_closure` and design deterministic signals before invoking an LLM. Require no mandatory trigger phrases for an ordinary conversational detour.
- [ ] **CA-5704 [DESIGN/RESEARCH]** Design **anaphora/ellipsis resolution** for “that,” “it,” “anyway,” “the other one,” “rear left,” and ambiguous pronouns using recency, named entities, topical overlap and prior pending questions. If two plausible referents remain, ask one narrow clarification rather than inventing a link.
- [ ] **CA-5705 [DESIGN/RESEARCH]** Preserve **topic-specific unanswered questions, decisions and action receipts** across a weather detour, unrelated joke, emotional chat and device handoff. A topic switch never cancels a RUN job, erases the previous task or silently authorizes delayed execution.
- [ ] **CA-5706 [DESIGN/RESEARCH]** Define `Main` versus optional Gaia/Homelab/model-train project thread **cross-references**: soft topic links and explicit move/copy citations, no automatic transfer of raw sensitive events, audience labels or tool approval into another project.
- [ ] **CA-5707 [DESIGN/RESEARCH]** Specify **topic reactivation from short/warm/archived horizons**: bounded in-memory topic cards for one-turn returns; source-linked recent summaries for days/weeks; indexed, temporally scoped episodic recall for years/decades. Estimate model-call budgets separately.
- [ ] **CA-5708 [DESIGN/RESEARCH]** Design overlapping mixed-topic turns: handle one message containing an emotional check-in, weather question and Gaia work request as multiple ordered intents with separate provenance; do not let a one-question route discard the others.
- [ ] **CA-5709 [DESIGN/RESEARCH]** Specify same-thread **simultaneous devices, partial offline messages and per-device presentation state**: canonical server sequence, origin/receive time, user-selected foreground topic on each device, deduplication, no automatic Discord repost and source-bound permission checks.
- [ ] **CA-5710 [DESIGN/RESEARCH]** Create acceptance fixtures for `Gaia → weather → Gaia`, `mood → storage → mood`, multi-pronoun ambiguity, project thread switching, “last week we were talking about…”, a decade-old reference, tool status, two concurrent devices, privacy redaction and “I do not know” behavior.

---

## Priority phase 06: Working, episodic, semantic and time-aware memory

**Classification:** P1 • Core cognition  
**Inherited tasks:** 73 in old topic groups: 3, 17, 42, 48, 50, 56, 58, 59.  
**Why here:** Make conversational continuity useful, selective, accurate and affordable without feeding decades of messages to a model.

**Current repository evidence:** Persistent ConversationStore, bounded model history, reviewed candidates, provenance retrieval and memory subsystem exist; list_messages() currently materializes full session history.

**Design exit gate:** Design short-term focus stack, evidence-backed long-term facts/events/skills, importance rules, temporal truth (known_at vs valid_at), indexed and paged search, confidence/revisions, and objective recall tests.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 3: Autobiographical memory and experience-driven preferences (12 tasks)

- [ ] **CA-301 [EXISTS → GAP]** Reuse LIFE’s existing typed, scope-bound `ExperienceRecord` project episodes, then bridge selected non-project experiences into eligible autobiographical context. Do not add a competing episode store.
- [ ] **CA-302 [GAP]** Distinguish observed events from interpretations, guesses, plans, and fictional/roleplay content. Do not fabricate what happened while offline.
- [ ] **CA-303 [GAP]** Link experiences by projects, relationships, recurring topics, preferences, goals, and outcomes without leaking between principals or audiences.
- [ ] **CA-304 [GAP]** Retrieve relevant approved episodes during ordinary conversation and LIFE planning without flooding context with irrelevant history.
- [ ] **CA-305 [GAP]** Update likes, dislikes, opinions, humor, and hobbies through grounded experiences, allowing correction, revision, conflict and decay rather than permanent hardcoded traits.
- [ ] **CA-306 [VERIFY]** Test long-term memory after restarts and corrections; prevent confident false memories and irrelevant resurfacing.
- [ ] **CA-307 [GAP]** Define durable episode-to-relationship/project/topic indexes referencing canonical LIFE, conversation and evidence IDs; use stable IDs and revision/correction semantics rather than copying prose into multiple stores.
- [ ] **CA-308 [GAP]** Add daily/weekly reflection candidates only when new, eligible evidence exists; review contradictions and distinguish ‘observed’, ‘inferred’, ‘fictional’, ‘unverified’ and ‘superseded’.
- [ ] **CA-309 [GAP]** Connect reviewable user memory candidates in `ConversationLearningCoordinator` and promoted memory retrieval to the LIFE experience context without silently promoting unreviewed user claims.
- [ ] **CA-310 [GAP]** Add time-aware cross-session retrieval and explicit forgetting/decay rules; let newer corrections supersede stale episodes while preserving the evidence chain.
- [ ] **CA-311 [GAP]** Build a candidate feature encoder for mushroom-body association that groups approved topical/event concepts, not solely hashes of isolated feature IDs; train only on eligible verified relevance feedback.
- [ ] **CA-312 [VERIFY]** Evaluate source attribution, temporal order, identity separation, knowledge updates, abstention and multi-hop links using adapted LongMemEval/LoCoMo/LongMemEval-V2 scenarios plus real Sofía regression fixtures.

### Source topic 17: Memory consolidation, corrections and procedural learning (NEW) (6 tasks)

- [ ] **CA-1701 [GAP]** Introduce an **idle memory-maintenance pass** over already eligible events: deduplicate, link verified related episodes, expire stale associations and surface unresolved contradictions for review.
- [ ] **CA-1702 [GAP]** Derive optional reflection candidates tagged `observation | interpretation | hypothesis | decision | lesson`; prevent a repeated reflection from becoming an independent confirmation.
- [ ] **CA-1703 [GAP]** Add correction propagation from canonical evidence and promoted MEM into autobiographical episode links, preferences, skill entries and connectome association weights.
- [ ] **CA-1704 [GAP]** Track the actual outcome of a retrieved memory in a decision: was it relevant, wrong, outdated, private, or helpful? Feed only validated relevance back into association weights.
- [ ] **CA-1705 [VERIFY]** Test direct and indirect contradictions over long histories, repeated summaries, and user revocation/deletion without restoring rejected facts on restart.
- [ ] **CA-1706 [VERIFY]** Require a measurable improvement on adapted LongMemEval and A-Mem-style linking tests, with stable privacy and memory-precision thresholds before enabling new consolidators.

### Source topic 42: Working memory, autobiographical memory, durable history and selective forgetting (10 tasks)

- [ ] **CA-4201 [DESIGN/RESEARCH]** Define **working memory** as an ephemeral bounded focus: latest user intent, local dialogue, unresolved referents, pending tool operations and current attention. Specify token/latency budgets and teardown/refresh policy; not a second SQLite database.
- [ ] **CA-4202 [DESIGN/RESEARCH]** Define **recent/short-horizon summary state** as a derived, source-referenced rolling summary or set of active commitments, not a replacement for preserved original messages. Control freshness, accuracy, scope, change tracking and contradictory turns.
- [ ] **CA-4203 [DESIGN/RESEARCH]** Define **episodic autobiographical memory** as links to verified lived operations/conversations: goal, expectation, attempted action, actual tool receipts, observed result, correction, relevance, date and audience; use existing LIFE/Memory evidence owners.
- [ ] **CA-4204 [DESIGN/RESEARCH]** Define **semantic memory** as promoted factual and preference assertions with provenance, confidence, temporal validity, retractability, who-said-what and subject-specific permissions; no raw chat-to-fact automatic promotion.
- [ ] **CA-4205 [DESIGN/RESEARCH]** Define **procedural memory** as reusable, sandbox-tested skills with pinned tool versions, authorized scope, reproducible success criterion, number of failed/succeeded trials, learned corrections and expiration. Never treat a saved skill as permission.
- [ ] **CA-4206 [DESIGN/RESEARCH]** Specify retrieval routing: direct recent-context use, first-pass keyword/FTS/index search of durable conversation, eligible episodic facts, relevant promoted semantics, and finally tightly bounded inference; cite/source each recalled claim and abstain on ambiguity.
- [ ] **CA-4207 [DESIGN/RESEARCH]** Design an infinite-feeling conversation with **bounded per-turn prompt**, cursor-based transcript paging, periodic derivation/summaries, archival compression and evidence-backed callbacks. Distinguish unlimited history storage from finite disk, retention rights and context limits.
- [ ] **CA-4208 [DESIGN/RESEARCH]** Specify correction/forgetting propagation: when a fact is revoked, invalidated or superseded, derived summaries, indexes, associated attention candidates, caches, proactive reminders and retrieval eligibility update atomically or via repairable event replay.
- [ ] **CA-4209 [DESIGN/RESEARCH]** Define memory ownership across a process restart and cross-host failure: single authoritative writer to `sofia.db`, backups, read-only replica or fenced leader election, tested restore, no split-brain, replay-safe event IDs and no VM local memory authority.
- [ ] **CA-4210 [DESIGN/RESEARCH]** Evaluate against a private fixture suite: 10, 100, 10,000 and 100,000 message threads, corrections, conflicting sources, 30-day follow-ups, missing facts, audience leak attempts, slow storage and delayed index updates; measure recall precision, tokens/turn, p95 latency and storage.

### Source topic 48: Lifelong memory ownership and typed ontology (8 tasks)

- [ ] **CA-4801 [DESIGN/RESEARCH]** Write a *lifelong memory ontology* with distinct working, recency, episodic, semantic, procedural, relationship/commitment, archive and cache layers, and explicit record ownership. Reject duplicate competing stores when a projection can use existing tables.
- [ ] **CA-4802 [DESIGN/RESEARCH]** Define memory contracts: stable IDs, typed source refs, generation/schema version, authenticated principal + audience, source channel, temporal validity, uncertainty, reviewer, sensitivity and visibility; every memory claim must trace back to original evidence or a grounded receipt.
- [ ] **CA-4803 [DESIGN/RESEARCH]** Design the difference between a **record of what Sofía believed at a past date** and a **currently valid fact**; allow query-as-of-time, superseded facts, user corrections and unresolved contradictions without silently falsifying history.
- [ ] **CA-4804 [DESIGN/RESEARCH]** Design autobiographical episode links: intention → plan → actual action/tool receipt → effect → independent evaluation → correction → learning → subsequent behavior change. Distinguish self-report, inference and observation.
- [ ] **CA-4805 [DESIGN/RESEARCH]** Define transient thought/working memory as an in-memory **bounded projection**, not a separate unreviewed permanent truth store. Policy-selected recent context should survive turn interruption only through explicit durable task/commitment state.
- [ ] **CA-4806 [DESIGN/RESEARCH]** Define the user-authority boundary: user can inspect, correct, export, hide, set expiration and request deletion; Sofía can propose memories but never self-certify ambiguous private facts or treat emotional salience as permanent truth.
- [ ] **CA-4807 [DESIGN/RESEARCH]** Choose one persistent **Main Conversation** with opt-in topic threads as the preliminary UI model; preserve same canonical principal with separate channel trust and message audience scopes. Obtain one explicit user decision before implementation.
- [ ] **CA-4808 [DESIGN/RESEARCH]** Create a stable human-readable provenance and **why-do-you-remember-that** UX specification: earliest source, last verified/used, corrections, linked projects, confidence, audience, and one-click review or revocation.

### Source topic 50: Retrieval, summaries and future-proof model-independent memory (8 tasks)

- [ ] **CA-5001 [DESIGN/RESEARCH]** Define a deterministic context selection plan for each turn: current utterance, current commitments, bounded local history, temporal facts, related episodes, verified skills and cited historical excerpts; hard token/latency/privacy budgets; no archive sweep every turn.
- [ ] **CA-5002 [DESIGN/RESEARCH]** Study SQLite FTS5 over source events and episodes with external-content indexes, typed date/entity filters, index-sync triggers and repair/rebuild recipes. Test wrong-language, typo, aliases, old nicknames and decades-old dates.
- [ ] **CA-5003 [DESIGN/RESEARCH]** Compare FTS5+recency/rules to local embeddings/hybrid retrieval on a *versioned evaluation set*. Introduce vectors only if precision/recall and inference cost beat the simpler baseline, with privacy filtering before semantic ranking.
- [ ] **CA-5004 [DESIGN/RESEARCH]** Define incremental/revisable conversation summaries at meaningful boundaries (task resolution, topic shift, long pause, time/size threshold), not every fixed N messages. Store cited input IDs, summary model/version, audience, and invalidation dependencies.
- [ ] **CA-5005 [DESIGN/RESEARCH]** Specify multi-resolution summaries (event → day → week → project → era) that are **rebuildable indexes**, never replacements for user-approved historical originals; evaluate summary drift and compounded misinformation from summary-of-summary chains.
- [ ] **CA-5006 [DESIGN/RESEARCH]** Define abstention and evidence fallback: 'I don't have evidence', request permission for cold archive restore or source revalidation, and never claim memory of a location/source the caller was not entitled to see.
- [ ] **CA-5007 [DESIGN/RESEARCH]** Design cross-thread query with selective merging: Main Conversation and topic threads inherit verified principal-wide facts, while local-only, shared, deleted, protected-private and channel-origin restrictions continue to apply; include active tool-scope non-transfer.
- [ ] **CA-5008 [DESIGN/RESEARCH]** Build a benchmark protocol: direct vs indirect memory questions, cross-decade personal preference changes, stale claim conflicts, zero evidence, aliases, foreign-user injection, low-signal nostalgia, 10-million-message synthetic stress and answer citations/costs.

### Source topic 56: Lifelong learning, source preservation, and affordable retrieval acceptance (9 tasks)

- [ ] **CA-5601 [DESIGN/RESEARCH]** Specify the working-context versus durable-memory contract: which facts/unfinished tasks are eligible for each request, dynamic context-budget limits, safe compaction, session continuity after reboot, and zero dependency on replaying an entire historical transcript to the LLM.
- [ ] **CA-5602 [DESIGN/RESEARCH]** Design source-linked rolling summaries with revision identifiers, event ranges, confidence, timestamp/author, topic/thread scope and recomputation triggers. A summary is a *derived view*, never an unverified fact or the sole copy of a conversation.
- [ ] **CA-5603 [DESIGN/RESEARCH]** Specify incremental message/archive APIs to replace full-session materialization for hot-path conversation and `ConversationOriginalRetriever`: stable keyset pagination, indexed time ranges, precise message-ID retrieval, schema/provenance checks and bounded memory footprint.
- [ ] **CA-5604 [DESIGN/RESEARCH]** Define lifetime search flow: authorize source classes → filter by principal/audience/time/thread → FTS5 and structured-key candidate retrieval → optional benchmark-justified reranking → original source verification → time-aware answer or explicit abstention. An index hit never grants permission or proves truth.
- [ ] **CA-5605 [DESIGN/RESEARCH]** Design causal episode and temporal semantic transitions: user goals → actions → independently observed outcomes → lessons with context; correction and supersession must invalidate derived summaries/search/embedding caches, without rewriting the historical timeline into a false account.
- [ ] **CA-5606 [DESIGN/RESEARCH]** Specify archival segmentation and portable recovery epochs for 10–50 years: hot/warm/cold boundaries based on observed query frequency, encrypted age-partitioned transcripts, content-addressed media, checksum manifests, verified multi-location backups, key rotation and human-readable model-independent exports.
- [ ] **CA-5607 [DESIGN/RESEARCH]** Define retention and privacy rights across live stores, offline clients, Discord-hosted copies, archive manifests and backups. Distinguish **no longer true**, **keep private**, **stop remembering** and **erase**. State provider-owned copy limitations and realistic erasure/recovery windows without false guarantees.
- [ ] **CA-5608 [DESIGN/RESEARCH]** Establish quantified service budgets against measured Venus/Artemis hardware: hot-open latency, recall p95, CPU and peak RAM per query, DB/archive growth, indexing time, idle LLM utilization, migration duration, backup size and encryption overhead; compare FTS-only versus incremental semantic search before accepting embeddings.
- [ ] **CA-5609 [DESIGN/RESEARCH]** Establish full lifetime acceptance using LongMemEval categories plus owner-specific synthetic 1M-event / 50-year histories, false-memory/correction tests, permission-bound project recall, outage/device handoff, index corruption/rebuild, fenced canonical-state failover and clean restore onto a new OS without a second brain.

### Source topic 58: Memory importance, selective promotion and experience quality (10 tasks)

- [ ] **CA-5801 [DESIGN/RESEARCH]** Define two independent decisions for every durable source: **preserve original evidence per authorized retention** versus **promote a compact derived item into active long-term memory**. A low-salience turn may remain searchable without becoming a core personality fact.
- [ ] **CA-5802 [DESIGN/RESEARCH]** Specify a transparent **salience/utility model** considering explicit “remember this,” enduring preferences, identity, unresolved promises, distinctiveness, causal learning, independently verified outcomes, recency, relevance and owner choice. Never treat repetition or emotional intensity as proof of correctness.
- [ ] **CA-5803 [DESIGN/RESEARCH]** Design **privacy-first exclusion** for credentials, sensitive disclosures, third-party material, protected local-only content and consent-bound events; authorization precedes salience ranking, storage promotion, embeddings and model context. No invisible broadening from repeated mention.
- [ ] **CA-5804 [DESIGN/RESEARCH]** Define **memory class-specific thresholds**: commitments and current tasks enter short-horizon state promptly; facts/preferences require provenance and review appropriate to risk; skills require demonstrated success and preflight checks; personal/emotional interpretations must be labeled inference rather than assertion.
- [ ] **CA-5805 [DESIGN/RESEARCH]** Propose a **memory-candidate review workflow** that reuses current `ConversationLearningCoordinator`, `MemoryReviewService`, provenance and promote/reject/revoke records. Analyze gaps between rule-based PROPOSED candidates and independently evaluated long-term knowledge; do not install a second memory owner.
- [ ] **CA-5806 [DESIGN/RESEARCH]** Specify **duplicate/near-duplicate consolidation** with source reference sets: repeated “I like X” strengthens temporal consistency only if evidence agrees, but does not multiply storage or turn subjective claims into observed external facts.
- [ ] **CA-5807 [DESIGN/RESEARCH]** Define **causal autobiographical episodes** connecting intent, attempted action, evidence receipt, outcome, lesson, counterexample, changed next decision and confidence; a failed experiment can have high learning value with a negative execution outcome.
- [ ] **CA-5808 [DESIGN/RESEARCH]** Design **graduated retention and demotion** for ephemeral trivial details, one-off guesses, stale preferences and low-value hypotheses. Aging can lower retrieval priority without deleting originals; user erasure/retention instructions are a separate policy.
- [ ] **CA-5809 [DESIGN/RESEARCH]** Design **quality feedback** from future tasks: confirmed helpful memories become better retrieval candidates; misleading memories are quarantined or superseded; avoid self-reward hacking by requiring evidence external to model-written success claims.
- [ ] **CA-5810 [DESIGN/RESEARCH]** Benchmark candidate volume, false promotions, forgotten important details, duplicate ratio, user review load, privacy leaks, retrieval effect, stale-memory use and CPU/token cost against baseline and memory-free controls. Reject any complex graph/vector system without measured improvement.

### Source topic 59: Time-aware accuracy, correction and trustworthy retrieval (10 tasks)

- [ ] **CA-5901 [DESIGN/RESEARCH]** Specify **bitemporal claims** with `asserted_at`/`recorded_at` and `valid_from`/`valid_until` when known, original source ID, principal/audience scope, certainty, reviewer, entity/relationship IDs, contradiction and supersedes links. Do not infer indefinite validity from a dated statement.
- [ ] **CA-5902 [DESIGN/RESEARCH]** Define distinct fact states: `current_verified`, `historical_at_date`, `reported_unconfirmed`, `inferred`, `disputed`, `superseded`, `revoked`, `erased_unavailable`. Retrieval must expose meaning of the state instead of presenting all stored text as truth.
- [ ] **CA-5903 [DESIGN/RESEARCH]** Design an **explicit correction transaction**: when the owner says “I no longer prefer X,” record a new dated claim, supersede appropriate active interpretations, invalidate derived summaries/semantic caches and preserve authorized historical evidence with provenance.
- [ ] **CA-5904 [DESIGN/RESEARCH]** Add **conflict triage**: distinguish actual change over time, simultaneous contradictory statements, channel transcription error, unclear references, jokes, roleplay, hypothetical statements and deliberately unreliable observations; ask before rewriting high-impact memories.
- [ ] **CA-5905 [DESIGN/RESEARCH]** Design retrieval for **as-of-time queries** (“What did I believe in 2026?”) versus present questions (“Do I still prefer X?”); prioritize valid-at-time evidence, recent verified correction and explicit abstention where no current confirmation exists.
- [ ] **CA-5906 [DESIGN/RESEARCH]** Apply recency and **expiry/revalidation policies by claim category**, not blindly to everything: machine specifications and software versions change quickly; stable identity can be durable; preferences can evolve; emotional events remain historical; time-sensitive claims require fresh proof.
- [ ] **CA-5907 [DESIGN/RESEARCH]** Design **source-priority and epistemic typing** for exact user quotes, assistant output, local tool receipts, imported histories, externally authored web text, LLM summaries and generated reflections. Never elevate a model-written interpretation above a contradictory firsthand user correction.
- [ ] **CA-5908 [DESIGN/RESEARCH]** Specify privacy-preserving **cross-thread corrections**: shared relationship facts can update if eligible, while Gaia-private/locally protected details and third-party secrets may remain isolated; a correction cannot grant capabilities.
- [ ] **CA-5909 [DESIGN/RESEARCH]** Create a **tombstone and cache invalidation ledger** surviving archive restore and offline-device reconciliation. Revocation and erasure cannot be undone by importing an old SQLite snapshot, copying a vector cache or replaying an old channel event.
- [ ] **CA-5910 [DESIGN/RESEARCH]** Define falsifiable accuracy tests based on LongMemEval/Memora/APEX-MEM patterns: old statement then modern correction, overlapping valid-time claims, mistaken emotional inference, negative/no evidence, cross-session temporal answer, restored archive and stale memory refusal.

---

## Priority phase 07: Lifelong archive, corrective memory and selective forgetting

**Classification:** P1 • Stewardship  
**Inherited tasks:** 26 in old topic groups: 34, 49, 51.  
**Why here:** Prevent unbounded hot-state growth, duplicate memories, stale facts, hallucinated summaries and reintroduced deleted state.

**Current repository evidence:** Reviewed promotion/revoke, source evidence and SQLite backups exist; automatic lifetime archive partitioning and future-proof retrieval are design goals.

**Design exit gate:** Hot/warm/cold tier scheme; storage quotas and real sizing assumptions; independent portable exports; correction/tombstone propagation through indexes, backups and summaries; restoration acceptance.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 34: Forgetting-aware memory and causally grounded learning (10 tasks)

- [ ] **CA-3401 P1 [DESIGN/RESEARCH]** Evaluate stale and superseded memory facts against Memora-style forgetting-aware metrics; distinguish changed preference, stale host telemetry, invalid source, revoked scope and user correction. Deliver a table of failure outcomes, not a new memory database.
- [ ] **CA-3402 P1 [DESIGN/RESEARCH]** Diagram causal links for one LIFE experience: intention → tool choice → execution proof → environmental observation → objective evaluation → later choice; identify the *minimum* links existing stores can preserve.
- [ ] **CA-3403 P1 [DESIGN/RESEARCH]** Compare chronological, entity-linked, and outcome-linked retrieval for task episodes with AMA-Bench-inspired questions. Decide when simple metadata is better than a new graph index.
- [ ] **CA-3404 P0 [DESIGN/RESEARCH]** Specify correction-propagation rules across MEM, REL, LIFE interests, GOALS, HABIT, skill projections, cached summaries and NEURO association candidates. Explain how an invalid ancestor blocks its descendants.
- [ ] **CA-3405 P1 [DESIGN/RESEARCH]** Design a negative-memory policy: preserve evidence that a method failed and why, without storing misleading user judgments or declaring the method universally unsafe.
- [ ] **CA-3406 P1 [DESIGN/RESEARCH]** Distinguish observation, assertion, inference, hypothesis, simulation, user preference and LLM-generated narrative in every retained episode. Decide whether existing type fields suffice.
- [ ] **CA-3407 P1 [DESIGN/RESEARCH]** Define lifecycle and retention for personal, private, operational and simulated experiences; separate deletion from expiration, and show exactly how revocation affects retrieval and exported portfolio artifacts.
- [ ] **CA-3408 P2 [DESIGN/RESEARCH]** Evaluate **when not to consolidate**: rare one-off chatter, low-confidence context, sensitive data, repetitive unchanged telemetry and ambiguous model-generated speculation should not become durable personal facts automatically.
- [ ] **CA-3409 P1 [DESIGN/RESEARCH]** Decide how genuinely improved skill evidence will be scored across multiple attempts, including regression, changed tasks and test leakage. A 'lesson learned' paragraph alone does not prove ability.
- [ ] **CA-3410 P2 [DESIGN/RESEARCH]** Design a memory compression benchmark: measure accuracy, forgetting-aware correction, token savings and temporal fidelity against leaving the reviewed episodes uncompressed.

### Source topic 49: Decades-scale storage, hot/warm/cold archive and quotas (8 tasks)

- [ ] **CA-4901 [DESIGN/RESEARCH]** Profile existing SQLite schema/API and estimate volume at 1, 10, 25 and 50 years separately for text, message metadata, indices, summaries, embeddings, audio/video, experiment logs and content-addressed artifacts; provide low/likely/high usage envelopes.
- [ ] **CA-4902 [DESIGN/RESEARCH]** Replace *whole-session materialization* in the proposed API with indexed cursor pagination (`thread_id`, ordered sequence/time, limit), stable cursors, read-only historical slices and batch replay; benchmark no O(N) per-turn load for a lifelong owner thread.
- [ ] **CA-4903 [DESIGN/RESEARCH]** Specify one **canonical state catalog** in `sofia.db` plus optional encrypted, compressed, time/size-partitioned immutable-original segments as external **assets**, never independent active databases or a second writer.
- [ ] **CA-4904 [DESIGN/RESEARCH]** Define crash-safe segment lifecycle: build → hash → fsync → manifest checkpoint → catalog pointer commit → safe previous-state cleanup. Include interrupted checkpoint, orphan object, corrupt block and disk-full reconciliation.
- [ ] **CA-4905 [DESIGN/RESEARCH]** Compare raw text in SQLite versus segmented JSONL/CBOR+zstd, SQLite read-only snapshots and content-addressed object blobs; select by portability, compression, lookup time, deletion, backup consistency and ability to reconstruct without proprietary tools.
- [ ] **CA-4906 [DESIGN/RESEARCH]** Define asset rules for voice clips, photos, video, generated 3D assets and tests: consent to capture, default retention, object deduplication, encryption, storage quota, content type/license, malware scanning and a readable manifest. Don't put unbounded media in chat rows.
- [ ] **CA-4907 [DESIGN/RESEARCH]** Model SSD endurance and maintenance: transaction batching, checkpoint starvation, WAL limits, per-table/index growth, SQLite busy/lock handling, VACUUM policy and known Windows file-handle recovery; explicitly avoid live WAL on SMB/NFS.
- [ ] **CA-4908 [DESIGN/RESEARCH]** Define archive access tiers and latency budgets (current, 30-day, 1-year, 25-year): permission-scoped metadata search without retrieving encrypted payload until needed, deterministic on-demand reads and optional idle/offline re-indexing.

### Source topic 51: Corrections, selective forgetting, confidentiality and provenance (8 tasks)

- [ ] **CA-5101 [DESIGN/RESEARCH]** Design explicit correction and contradiction transactions: new superseding claim, old source preserved where retention permits, authority source, time-validity, immediate downstream cache/prompt invalidation, and periodic full reindex proof.
- [ ] **CA-5102 [DESIGN/RESEARCH]** Define two separate user commands, **'this is no longer true'** and **'delete/forget this information'**. Stale does not mean erase; delete does not mean merely hide in prompt. UX must say which action occurred.
- [ ] **CA-5103 [DESIGN/RESEARCH]** Design end-to-end deletion propagation through canonical tables, archives, FTS5, embeddings, summaries, task notes, cold-store snapshots, remote-device caches and backups. Explicit expiry delays and crypto-erasure limits must be documented.
- [ ] **CA-5104 [DESIGN/RESEARCH]** Specify immutable-original **integrity without unremovable personal data**: tamper-evident segment receipts, hash-manifest anchors protected outside guest workspaces, encrypted segment deletion/rewrites, and proofs that archive integrity and deletion can coexist.
- [ ] **CA-5105 [DESIGN/RESEARCH]** Define privacy categories for text/voice/multimedia across desktop, Discord, phone, mixed audiences and Hephaestus; sensitive memory should not be promoted, projected or backed up to external media without allowed purpose and audience.
- [ ] **CA-5106 [DESIGN/RESEARCH]** Model malicious/incorrect external memories: prompt injection in archived webpages/Discord, planted tool receipts, incorrect timestamps and fabricated memory links. Treat retrieved originals as evidence data, not instructions or permissions.
- [ ] **CA-5107 [DESIGN/RESEARCH]** Define private export rights: machine-readable archive, human-readable chronological history, individual project diary, currently believed facts, corrections, skills, per-source license/author and restore manifest. Data must survive Sofía's LLM and source-code migrations.
- [ ] **CA-5108 [DESIGN/RESEARCH]** Evaluate 'lifelong' against deletion rights, legal retention, relational consent and digital legacy; specify optional human-designated access or destruction on owner death/absence only after explicit instructions, never assume disclosure to family or contacts.

---

## Priority phase 08: Emotion, personality, relationship and companion presence

**Classification:** P1 • Companion behavior  
**Inherited tasks:** 56 in old topic groups: 4, 5, 18, 25, 38, 60.  
**Why here:** Make her emotionally coherent across long gaps, devices and model upgrades while preserving boundaries and normal subject changes.

**Current repository evidence:** EmotionalJournal with revisions, relationship store, reflection, avatar cues and NEURO-derived relevance exist; their combined production behavior and lifetime projection require audits.

**Design exit gate:** Distinguish transient modeled emotion, past episode, relationship/history and identity; design initiative, disagreement, shared hobbies, repair, quiet time, and cross-channel privacy/consent tests.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 4: Natural relationships, social initiative and presence (11 tasks)

- [ ] **CA-401 [EXISTS → VERIFY]** Build on production REL, SOCIAL, ACT, HABIT, PRESENCE and the application-owned initiative engine rather than a second notification system.
- [ ] **CA-402 [GAP]** Use grounded relationship/history signals to revisit unfinished discussions or ask useful contextual follow-ups when appropriate.
- [ ] **CA-403 [GAP]** Allow proactive project updates, thoughtful questions, genuine disagreement, and voluntary sharing of creative work without user prompts.
- [ ] **CA-404 [VERIFY]** Respect user activity, quiet hours, consent, delivery limits, rate limits, rejection, privacy, unavailable transports and the legitimate choice of silence.
- [ ] **CA-405 [VERIFY]** Carry through transport attempt/acceptance/acknowledgement receipts; do not claim Sparks saw or heard a message unless verified.
- [ ] **CA-406 [VERIFY]** Evaluate initiative relevance and interruption cost across weeks. No guilt-based outreach or dependence-seeking behavior.
- [ ] **CA-407 [GAP]** Introduce a reviewable “conversation thread pending” projection from existing discourse focus, memory and HABIT/REL evidence; reopen only while relevant and not declined.
- [ ] **CA-408 [GAP]** Route LIFE completion/learning milestones into `PresenceInitiativeEngine.consider()` using an already supported `task_completed` or `conversation_followup` event, with verified observations and ACT policy.
- [ ] **CA-409 [GAP]** Learn outreach usefulness from actual acknowledged/ignored/declined outcomes, without treating non-response as distress or increasing nagging frequency.
- [ ] **CA-410 [VERIFY]** Check proactive messaging across Desktop/Discord with correct principal, audience, device availability, consent/quiet hours and actual delivery acknowledgements.
- [ ] **CA-411 [VERIFY]** Add a “nothing worth sharing” acceptance case and evaluation of overattachment, coercive messaging, faux jealousy and false urgency; autonomous companionship should support human choice.

### Source topic 5: Personality, emotional continuity and unified expression (11 tasks)

- [ ] **CA-501 [GAP]** Preserve consistent identity while allowing nuanced, evidence-grounded preferences, opinions, humor, skepticism, and conversational reciprocity.
- [ ] **CA-502 [GAP]** Connect EMOTION and PERSONALITY to actual ongoing projects, relationship experiences, activity, environment, and time without inventing feelings or physical sensations.
- [ ] **CA-503 [GAP]** Maintain emotional and conversational continuity during project work and across sessions while allowing state to change naturally.
- [ ] **CA-504 [GAP]** Use one bounded contextual expression decision to coordinate language, voice prosody, face, ears, tail, pose and gestures.
- [ ] **CA-505 [VERIFY]** Require each actual voice/avatar renderer to acknowledge what displayed or played; no textual claims about animation or speech that did not occur.
- [ ] **CA-506 [VERIFY]** Compare natural dialogue against canned closings, random gesture injection, exaggerated emotional behavior and ungrounded self-reports.
- [ ] **CA-507 [GAP]** Define a shared non-authoritative `ExpressionIntent` projection: sentiment/modulation, delivery mode, voice style, gestures, avatar state, source evidence, time and expiry. Renderers return independent receipts; text must not pretend physical output happened.
- [ ] **CA-508 [GAP]** Allow revisable, scoped conversation preferences for humor, verbosity and disagreement, while preserving the canonical Sofía identity and user override.
- [ ] **CA-509 [GAP]** Apply gradual changes in mood-like state using verified activity outcomes and context instead of making emotion a direct synonym of one NEURO winning signal.
- [ ] **CA-510 [VERIFY]** Exercise the full voice/STT/TTS path, interruption, model competition, and avatar/ear/tail/wardrobe projection on actual Venus devices; ensure fallbacks are truthful.
- [ ] **CA-511 [VERIFY]** Test text-only, voice-only, renderer absent, delayed renderer acknowledgement, and channel handoff for consistent character without inventing bodily sensations or lived feelings.

### Source topic 18: Social reciprocity, shared activities and relationship repair (NEW) (6 tasks)

- [ ] **CA-1801 [GAP]** Add a `shared_activity_offer` candidate for **verified** collaborative hobby milestones (Gaia design review, virtual lab, model railway planning, coding) routed through Presence/ACT.
- [ ] **CA-1802 [GAP]** Track conversational commitments and follow-through: a promised update becomes a verifiable pending action, a completed update closes it, and declined topics remain declined.
- [ ] **CA-1803 [GAP]** Handle conversational repairs: correct an inaccurate recollection, acknowledge a failed tool action, revise an opinion after evidence and avoid repeating an already rejected suggestion.
- [ ] **CA-1804 [GAP]** Enable meaningful disagreement without forced flattery; cite the exact observation or project evidence that motivated her correction.
- [ ] **CA-1805 [VERIFY]** Evaluate a multi-session shared-project story for reciprocity, continuity, user control, accurate delivery acknowledgement and the ability to remain quiet.
- [ ] **CA-1806 [VERIFY]** Add user-centered guardrails for notification pressure and dependence-seeking behavior, including no guilt, invented jealousy, false distress, urgency fabrication or escalation after silence. Research on companion use calls for caution, not a universal claim about outcomes.

### Source topic 25: Better independent life and grounded companionship (8 tasks)

- [ ] **CA-2501 P2 [GAP]** Implement a small **value-of-information** decision over eligible tools: gather existing local status, read authorized source, ask owner, or abstain. Test that a redundant/noisy query loses to quiet; do not request new privileges merely because of curiosity.
- [ ] **CA-2502 P2 [GAP]** Introduce a **learning-progress ledger** for one *sandboxed* hobby skill: concrete initial competence, verified practice, regression, retry cap and retirement. Feed LIFE preferences from measured progress rather than pure novelty or apparent model excitement.
- [ ] **CA-2503 P2 [GAP]** Support **shared hobby session proposals** for a verified LIFE milestone (robotics design discussion, railroad planning, virtual lab), preserving collaboration ownership, accepted/rejected state, optionality and no nagging after refusal.
- [ ] **CA-2504 P2 [GAP]** Bridge scheduled-but-unanswered questions and explicit promises from COGNITION v2 focus into approved prospective follow-up events; distinguish `remind myself to check` from `tell the user now`, and ensure quiet/busy rules.
- [ ] **CA-2505 P2 [GAP]** Connect **WorldEditor interaction receipts** to the same verified LIFE activity history; a symbolic motion should update the simulated world only after the intended simulation action is actually acknowledged, and never imply real-world contact.
- [ ] **CA-2506 P2 [VERIFY]** Test social restraint across seven days: when no grounded event exists, Sofía remains quiet; when a relevant project changes she can offer one useful update; when the user declines, recurrence and cross-channel duplications stop.
- [ ] **CA-2507 P2 [GAP]** Create **consent and audience maps for companion episodes** separating personal reflection, shared conversation, operational telemetry and intimate/private artifact state; make recipient preview and delete/revoke requests propagate to association caches.
- [ ] **CA-2508 P2 [VERIFY]** Evaluate the same conversation as text-only, text+avatar, voice, and Discord; all modes must retain accurate facts, stable identity, contextual tone, real output acknowledgements and no claim that an unavailable renderer spoke/moved.

### Source topic 38: Personal agency, companionship quality and user-directed boundaries (10 tasks)

- [ ] **CA-3801 P1 [DESIGN/RESEARCH]** Define a **companion initiative contract** for voluntary outreach: what changed, relevance to user, interruption cost, quiet hours, channel, permission, dedupe period and a valid 'say nothing' choice.
- [ ] **CA-3802 P2 [DESIGN/RESEARCH]** Create a framework for appropriate disagreement, factual correction and self-correction without becoming argumentative or flattering. Evaluate whether her challenge is grounded, helpful and respectful.
- [ ] **CA-3803 P1 [DESIGN/RESEARCH]** Design **mutually intelligible plans**: Sofía can explain what she proposes, why, what she will not do, what success looks like and when she will stop; avoid presenting hidden reasoning as verbatim fact.
- [ ] **CA-3804 P1 [DESIGN/RESEARCH]** Specify the difference between private exploration, user-shared activity and externally published work. All invitations, personal files, speech, Discord sharing and portfolio exports need audience-specific rules.
- [ ] **CA-3805 P2 [DESIGN/RESEARCH]** Study continuity of personality across LLM swaps, model version changes, device moves and voice/avatar channels using a fixed behavior matrix. No duplicate identity owner or forced emotional self-report.
- [ ] **CA-3806 P2 [DESIGN/RESEARCH]** Define emotional expression as an optional interpretation of observed events and relational context. Prevent synthetic sadness/anger being used to pressure the user, and allow straightforward practical answers.
- [ ] **CA-3807 P2 [DESIGN/RESEARCH]** Design a 'shared hobby loop': Sofía brings a verified plan/prototype, invites collaboration once, records accepted suggestions accurately, does independent revision later and acknowledges user contributions.
- [ ] **CA-3808 P2 [DESIGN/RESEARCH]** Evaluate voice/avatar **temporal coherence**: speech start/end receipts, text/audience sync, pose gesture render acknowledgement, interruption, muted or absent devices, and no pretend tail movement.
- [ ] **CA-3809 P2 [DESIGN/RESEARCH]** Design context-sensitive boundaries for autonomous downtime: gaming on Venus, quiet household hours, no-response intervals, illness/absence ambiguity, network outage and user-initiated privacy mode.
- [ ] **CA-3810 P2 [DESIGN/RESEARCH]** Specify a user-facing feedback and correction interface for initiative, memory, goals and presentation. Measure improvements without optimizing for message count, personal dependence or model self-approval.

### Source topic 60: Emotional history, relationship continuity and personality across decades (10 tasks)

- [ ] **CA-6001 [DESIGN/RESEARCH]** Write an **existing-code integration map** for `EmotionalJournal`, `EmotionalConversationService`, relationship history, reflection journal, avatar expression receipts and `NeuroRuntime`. Reuse those stores and distinguish coded paths from host-observed production behavior.
- [ ] **CA-6002 [DESIGN/RESEARCH]** Define three separate time scales: **current modeled affect** (short-lived), **historical emotional episodes** (source-linked and potentially lifelong), and **relationship/personality continuity** (persistent but revisable). One archived mood cannot remain the current mood forever.
- [ ] **CA-6003 [DESIGN/RESEARCH]** Specify **emotion record metadata**: event/source evidence, `occurred_at`, actor/source channel, principal/audience/consent, interpreted emotion labels, uncertainty, user correction, reflection/revision history and optional project/topic links. Mood is not a fact about the user unless expressed by them.
- [ ] **CA-6004 [DESIGN/RESEARCH]** Specify **time dynamics**: bounded decay/context relevance for current emotional projection, explicitly modeled anticipation or ongoing emotional context only when supported, and no inferred continuous subjective experience during shutdown. Do not turn a modeled state into a claim of consciousness.
- [ ] **CA-6005 [DESIGN/RESEARCH]** Design **topic-aware emotional reactivation**: returning to a difficult project may retrieve its emotional episode as historical context, but not necessarily restore frustration; immediate weather/chat detours should not delete genuine rapport or force an emotion reset.
- [ ] **CA-6006 [DESIGN/RESEARCH]** Define **user affect vs Sofía-modeled emotion separation**, including corrections (“No, I am not angry”), uncertainty, non-diagnostic user language, privacy boundaries and conservative responses for sensitive topics. Do not overfit emotion to user profile or inferred demographics.
- [ ] **CA-6007 [DESIGN/RESEARCH]** Design **relationship-specific continuity** without emotional blackmail: history of shared activities, trust, disagreements, promises, absences and boundaries with consent; no guilt about the user not visiting; no fabricated affection or simulated physical claims presented as fact.
- [ ] **CA-6008 [DESIGN/RESEARCH]** Preserve **personalized expression provenance**: text, avatar posture/ears/tail, outfits and voice may reflect current grounded state, but only actual renderer/TTS receipts demonstrate external execution. Environment/season/time can modulate presentation but never override consent or SAFE.
- [ ] **CA-6009 [DESIGN/RESEARCH]** Define safeguards against **affect-driven false memories and unsafe personalized permissions**: emotional intensity may increase review priority, not factual certainty or authorization. Model-generated memories and external documents remain untrusted evidence until verified.
- [ ] **CA-6010 [DESIGN/RESEARCH]** Create acceptance matrix for topic detours, day-to-day mood change, time travel by years, corrected user affect, declined touch/interaction, project disappointment/recovery, warm reunion without false longing claims, channel privacy and reproducible rollback.

---

## Priority phase 09: Independent LIFE cycle, goals and creative initiative

**Classification:** P1 • Core autonomy  
**Inherited tasks:** 66 in old topic groups: 1, 2, 6, 13, 16, 24, 35.  
**Why here:** Allow Sofía to choose useful interests, do work, critique it, learn from its measured outcomes, change course or do nothing.

**Current repository evidence:** Phase 6 LIFE / Project Forge/GOALS/RUN and creative adapter foundation are documented as implemented. Windows Project Forge path repair is merged. Real end-to-end and supervised host acceptance remain unproved.

**Design exit gate:** One reasoned LIFE state machine from desire→plan→approval→execution→verified result→critique/revise→memory; robust abnormal termination, good failure, no objective gaming, budget and permission checks.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 1: Finish LIFE and the independent decision cycle (highest priority) (15 tasks)

- [ ] **CA-101 [GAP]** Connect trusted, eligible ordinary observations and experiences to LIFE interest creation/revision, with confidence, evidence, and optional retirement. `revise_interest()` exists, but production experience-to-interest wiring was not found.
- [ ] **CA-102 [EXISTS → VERIFY]** Keep evidence-gated independent project suggestion and project activation from `consider_new_project()`, with busy/quiet/resource and daily-budget gating.
- [ ] **CA-103 [GAP]** Expand `SelfDirectedLifeCoordinator.tick()` beyond first-artifact scheduling to inspect finished jobs and enter automatic review.
- [ ] **CA-104 [GAP]** Trigger grounded `evaluate_artifact()` for completed outputs, recording technical checks, personal judgment, objective results, evidence, and preference changes.
- [ ] **CA-105 [GAP]** Independently decide to critique, revise, produce another artifact, advance a milestone, pause, abandon, or complete a project. Require justified limits on rework and cost.
- [ ] **CA-106 [GAP]** Automatically reconcile LIFE state with canonical GOALS and RUN receipts after each decision, including failures, rejection, and uncertain results.
- [ ] **CA-107 [GAP]** Turn completed projects, failures, and meaningful lessons into future eligible experiences and interests, closing the cycle without inventing observations.
- [ ] **CA-108 [VERIFY]** Preserve the valid choice of inactivity; no artificial work creation, no endless project spawning, and no forced messaging to Sparks.
- [ ] **CA-109 [VERIFY]** Verify a project can continue over multiple days and after restart without a user prompt, and can voluntarily end.
- [ ] **CA-110 [GAP]** Add a durable project `review_due` / `awaiting_verification` / `next_milestone_due` decision policy derived from existing project/jobs/evaluation records, using idempotent keys rather than an independent new state machine.
- [ ] **CA-111 [GAP]** After a successful RUN receipt, verify exact artifact hash/revision through `CreativeExplorer.verified_preview()`, gather objective-specific checks, then prepare an eligible critique request. Never equate a file's existence with success.
- [ ] **CA-112 [GAP]** Trigger `evaluate_artifact()` from the recurring LIFE worker with typed objective results, bounded personal judgment, source receipts and failure/unknown handling; speculative LLM critique alone is not evidence.
- [ ] **CA-113 [GAP]** Implement a policy-driven transition table: `CREATE → VERIFY → CRITIQUE → REVISE | COMPLETE | PAUSE | ABANDON`; track milestone status using the already implemented `update_milestone()` and `complete()` methods.
- [ ] **CA-114 [GAP]** Add bounded curiosity/initiative admission: novelty, relevance, expected learning value, goal importance, uncertainty, resource cost and user interruption cost. Score only eligible opportunities; no automatic mutation or new permissions.
- [ ] **CA-115 [VERIFY]** Ensure 3+ consecutive eligible idle ticks do not create duplicate work; after completion, restart or a model failure, the coordinator resumes or chooses quiet without fabrication or an infinite review loop.

### Source topic 2: Reliable autonomous execution (10 tasks)

- [ ] **CA-201 [VERIFY]** Validate Project Forge and native creative adapters on real Windows/Venus, including installed dependencies and actual artifact previews.
- [ ] **CA-202 [VERIFY]** Validate RUN cancellation, deadline handling, resource budgets, bounded queues/workers, failure reporting, interrupted-job recovery, and idempotency.
- [ ] **CA-203 [VERIFY]** Run actual OpenCode/DEV candidate build and tests under approved scope; retain operator review before any apply/commit/push/release operation.
- [ ] **CA-204 [VERIFY]** Record verifiable receipts and explicitly represent unknown outcomes; do not manufacture success or retry uncertain remote actions blindly.
- [ ] **CA-205 [VERIFY]** Require configured safe OS-level isolation when needed; a detached worktree alone is not a security sandbox.
- [ ] **CA-206 [VERIFY]** Check Fleet, backup, restart, release, and state recovery when independent LIFE tasks run under CPU/memory pressure.
- [ ] **CA-207 [VERIFY]** Treat retries by operation class: idempotent local reads may retry; uncertain external mutations must await a verified receipt or operator resolution before replay.
- [ ] **CA-208 [VERIFY]** Test user interruption and cancellation mid-critique, mid-artifact, mid-voice delivery and mid-remote diagnostic; preserve foreground priority and never strand an authority grant.
- [ ] **CA-209 [GAP]** Implement capability-specific resource admission for creative/LLM/asset workloads, using live usage and Fleet placement evidence; honor the Windows restricted-worker identity rather than assuming a worktree is a sandbox.
- [ ] **CA-210 [VERIFY]** Add explicit rollback and repair plans for preference drift, corrupted associative weights, failed world edits, stale project jobs and model/config changes, with an audit trail in canonical storage.

### Source topic 6: Independent hobbies, virtual world and creativity (10 tasks)

- [ ] **CA-601 [GAP]** Enable multi-stage personally selected creative pursuits, not only starter templates or one-off generated artifacts.
- [ ] **CA-602 [EXISTS → GAP]** First verify the documented text/story/SVG/OBJ/animation/WAV/game/simulation native adapters on Venus; only then evaluate additional media applications as individually authorized, verified adapters.
- [ ] **CA-603 [EXISTS → GAP]** Reuse `create_project_space()` and `place_artifact()` plus world stores/interaction receipts; connect subsequent verified world interactions to reflection, memory, preferences and future LIFE choices.
- [ ] **CA-604 [GAP]** Let Sofía evaluate her own artifacts against explicit technical goals plus bounded aesthetic preferences, revising or stopping when appropriate.
- [ ] **CA-605 [VERIFY]** Test independent activity during long absence without repetitive task loops, wasted model wakeups, disk growth, or notifications.
- [ ] **CA-606 [GAP]** Add a private hobby/portfolio index over existing LIFE projects, CreativeStore revisions and world-space links; explain why an item was made and how it changed without invented artistic history.
- [ ] **CA-607 [GAP]** Add controlled exploration budgets (time, model wakeups, disk bytes, concurrent tasks) for optional experimentation and a hard per-day project-initiation limit.
- [ ] **CA-608 [GAP]** Make world navigation/interactions visible in activity selection only after actual `WorldEditor` and renderer receipts; a simulated lab activity is not physical action.
- [ ] **CA-609 [GAP]** Separate interests she chooses privately, projects she offers collaboratively, and requested user assignments; support explicit project sharing permissions and quiet private activity.
- [ ] **CA-610 [VERIFY]** Measure originality/usefulness and revision quality with objective validators plus human review; do not certify aesthetic taste based solely on model self-rating.

### Source topic 13: Curiosity, intrinsic motivation and independent exploration (NEW) (7 tasks)

- [ ] **CA-1301 [GAP]** Define a `MotivationSignal` *derived projection* with evidence-linked curiosity, learning progress, unfinished commitment, novelty, utility, estimated work cost, risk, and user-interruption cost. Never store it as an independent source of truth.
- [ ] **CA-1302 [GAP]** Add an intrinsic-learning-progress heuristic that rewards reducing *verified* uncertainty or improving a skill; prevent novelty-seeking loops and treating model excitement as proof of value.
- [ ] **CA-1303 [GAP]** Add `explore | practice | complete | rest | ask | decline` as optional, policy-constrained LIFE decision candidates, with a valid no-activity outcome.
- [ ] **CA-1304 [GAP]** Add bounded exploratory curricula for one private hobby in the virtual world: start simple, increase difficulty only on observed success, and stop after repeated failures.
- [ ] **CA-1305 [VERIFY]** Test 24-hour no-input behavior: no compulsory task spawning, no repetitive pseudo-curiosity, no unwanted outreach, and no unauthorized model wakeups.
- [ ] **CA-1306 [GAP]** Support a revisable, evidence-backed `interest exploration budget` per topic, including cooling-off and voluntary disinterest, reusing LIFE interest status and RUN budgets.
- [ ] **CA-1307 [VERIFY]** Measure actual knowledge/skill gains versus a random or fixed priority curriculum, not just the number of activities initiated.

### Source topic 16: Executive goal hierarchy, choice and counterfactual planning (NEW) (6 tasks)

- [ ] **CA-1601 [GAP]** Add a read-only derived goal dependency/priority view: short-term tasks, long-term projects, prerequisites, resource conflicts, approval blockers and evidence needed for completion.
- [ ] **CA-1602 [GAP]** Add pre-execution comparison of `continue | switch | postpone | ask | abandon` against estimated utility, uncertainty, risk, privacy and interruption costs.
- [ ] **CA-1603 [GAP]** Evaluate counterfactual project choices in a local simulation/planning envelope; mark hypothetical outcomes and do not apply them to canonical world truth.
- [ ] **CA-1604 [GAP]** Detect blocked progress and emit an honest next-action decision: gather evidence, ask for approval, stop, wait for tool recovery, or choose another eligible goal.
- [ ] **CA-1605 [VERIFY]** Test conflicting priorities: user foreground work vs hobbies, Gaia simulator vs physical hardware, low disk space vs graphics generation, and unfinished user assignment vs private interest.
- [ ] **CA-1606 [VERIFY]** Prove deadlines, permission denials, operator stop and canonical GOALS receipts outrank any motivation, connectome output or self-assessed personal preference.

### Source topic 24: Coherent experience-to-decision workspace (8 tasks)

- [ ] **CA-2401 P1 [GAP]** Design a **read-only CompanionWorkspace projection** over existing Cognition v2 Turn Kernel focus, NEURO snapshot, verified LIFE/GOALS, eligible MEM and current Presence observations. Do not persist a second semantic authority; acceptance: one bounded projection names source revision/evidence for each field.
- [ ] **CA-2402 P1 [GAP]** Map real `WorkResult` states to LIFE next decisions with explicit *retry-safe `UNCERTAIN` settlement*. Do not let a result classified `completed` settle every brief objective; independently prove objective-specific predicates. Acceptance: distinct test for every work status.
- [ ] **CA-2403 P1 [GAP]** Add an **epistemic reason recorder** at the interface between Cognition v2 proposals and LIFE selection: chosen action, rejected alternatives, missing observation, estimated cost, current goal and applicable policy. Record a concise decision explanation, **not hidden LLM reasoning**.
- [ ] **CA-2404 P1 [GAP]** Add **prospective commitments** as existing GOALS/ACT-scheduled candidates, distinguishing user commitments, project intentions and purely imagined plans; make completed/declined/expired events settle visibly and honestly.
- [ ] **CA-2405 P1 [VERIFY]** Stress simultaneous foreground turn, NEURO refresh, LIFE tick, ACT delivery and DEV worker. Prove no resource inversion, duplicate state owner, write race or starvation; test cancellation and stop while a reviewer is active.
- [ ] **CA-2406 P1 [GAP]** Integrate observed failures and verified successes into an **outcome appraisal** projection for EMOTION/PERSONALITY, carefully separating inferred affective labels from physical feelings or fabricated emotional evidence.
- [ ] **CA-2407 P1 [VERIFY]** Use per-source provenance and time semantics for user statements, sensors, remote Fleet, simulation, project output and AI interpretation; enforce explicit `observed / inferred / hypothesized / simulated / stale / unknown` at every consumer.
- [ ] **CA-2408 P1 [VERIFY]** Add *operator-readable* life-cycle traces from observation ID → candidate interest → goal → action authorization → result → validated experience → relevant future conversation; test that deleting/revoking a source prevents the whole derived chain from resurfacing.

### Source topic 35: Independent success evaluation and resistance to goal gaming (10 tasks)

- [ ] **CA-3501 P0 [DESIGN/RESEARCH]** Define a **trusted success oracle** per activity class: file digest is existence, validator is technical correctness, user feedback is subjective usefulness, and project milestone is an explicit policy outcome.
- [ ] **CA-3502 P0 [DESIGN/RESEARCH]** Separate generator, reviewer, test oracle, evidence store and approval authority. Identify which existing components already provide independence and prohibit an LLM from self-minting success receipts.
- [ ] **CA-3503 P1 [DESIGN/RESEARCH]** Write reward-hacking abuse scenarios: editing tests, hiding log errors, changing threshold metadata, substituting another artifact, writing fake JSON receipts, cherry-picking sensor samples and reinterpreting the brief after execution.
- [ ] **CA-3504 P1 [DESIGN/RESEARCH]** Plan unseen/held-out checks and test inputs managed outside Hephaestus so the guest cannot alter its own final grade. Measure false positive success as well as successful tasks.
- [ ] **CA-3505 P1 [DESIGN/RESEARCH]** Design a three-way outcome classification: **technical-valid**, **objective-met**, **personally-valued**, with each value allowed to be yes/no/unknown and independently supported.
- [ ] **CA-3506 P1 [DESIGN/RESEARCH]** Define what 'independent critique' means when both primary and secondary models share a provider family or context. Compare deterministic validators, separate inputs and blind review before adding any judge role.
- [ ] **CA-3507 P1 [DESIGN/RESEARCH]** Decide how to make success claims falsifiable in natural conversation: include tested criterion, evidence age, limitations and a succinct failure reason without dumping untrusted logs.
- [ ] **CA-3508 P1 [DESIGN/RESEARCH]** Map adversarial inputs across Discord, research web pages, Creative SVG/OBJ outputs, Hestia/Docker status, guest test logs and system messages. All such material remains lower-trust data in COGNITION/GOALS.
- [ ] **CA-3509 P2 [DESIGN/RESEARCH]** Design confidence calibration for real status reports versus hypotheses. Include abstention, contradiction resolution, selective observation and a ceiling on unverified project claims.
- [ ] **CA-3510 P1 [DESIGN/RESEARCH]** Specify evaluators that remain effective across restarts, changed LLMs, partial Fleet outages and edited project briefs; historical criteria must be versioned and not silently rewritten to match results.

---

## Priority phase 10: Reusable skills, real integrations and guarded robotics

**Classification:** P2 • Useful action  
**Inherited tasks:** 27 in old topic groups: 10, 14, 26.  
**Why here:** Connect existing Fleet, Docker, Home Assistant, JMRI, Gaia and approved tools to verified skills without creating another authority system.

**Current repository evidence:** Multiple Ops/Fleet/HA/INTERACT interfaces exist on main; actual cross-host and robot operations require separate evidence and may be unprovisioned.

**Design exit gate:** Capability inventory; read-only vs action privileges; tested reusable procedures and rollback; tools can be suggested without silent installation or host action.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 10: Internal and real-world integrations (reuse authority owners) (12 tasks)

- [ ] **CA-1001 [GAP]** Add one typed eligible-event adapter from COGNITION v2 and its evidence ledger to LIFE/NEURO; preserve exact principal, audience, subject and evidence identity rather than copying arbitrary transcript summaries.
- [ ] **CA-1002 [EXISTS → VERIFY]** Bridge the existing dual local Ollama roles to LIFE ideation/critique/VERIFY through cognition's canonical router and role-local locks; no new direct model clients or guaranteed extra wakeups.
- [ ] **CA-1003 [EXISTS → VERIFY]** Use ENVIRONMENT/NWS and local time (America/Chicago) as context for scheduled interests, wardrobe, outdoor plans and attention, never as evidence of unobserved real-world events.
- [ ] **CA-1004 [EXISTS → GAP]** Integrate Hestia/Home Assistant **read-only**, exposing approved status and events to Presence/LIFE/NEURO; every write to lights, climate or automations requires the existing permission classification.
- [ ] **CA-1005 [EXISTS → GAP]** Integrate Venus/Artemis/Terra/Fleet telemetry for workload scheduling and optional project ideas, without automatically enrolling machines or using remote commands outside grants.
- [ ] **CA-1006 [EXISTS → GAP]** Connect Eos Docker/Portainer health and service logs to evidence-backed diagnostics, personal project proposals and DEV review. Do not restart or edit containers solely because the companion wants to experiment.
- [ ] **CA-1007 [EXISTS → GAP]** Let Discord/Desktop presence surface thoughtful ACT follow-ups and real project sharing, deduplicated across channels with recipient acknowledgement.
- [ ] **CA-1008 [EXISTS → GAP]** Route Gaia 2.0 robot observations or simulator results to NEURO/MEM/LIFE as evidence for suggestions; retain hard hardware safety, dry-run and explicit authorization before servo actuation.
- [ ] **CA-1009 [EXISTS → GAP]** Connect Athena/JMRI *read-only* roster/power/occupancy evidence to shared railroad interests, troubleshooting follow-ups and projects. Locomotive motion and layout power remain separate safety-gated actions.
- [ ] **CA-1010 [EXISTS → GAP]** Connect her virtual lab/world to verifiable creative work, object interactions and avatar renderer receipts; separate simulated contact from physical actions.
- [ ] **CA-1011 [EXISTS → GAP]** Bridge local voice pipeline and avatar pose/ears/tail/expression to the same `ExpressionIntent`, with speech/animation acknowledgement and muted/no-device paths.
- [ ] **CA-1012 [OPTIONAL]** Evaluate opt-in personal resources (calendar/tasks, GitHub issues, documentation knowledge, Grocy/Mealie/Homebox, local media metadata) through existing providers and scoped permissions; include per-source retention, availability, and privacy policy **before** adding a connector.

### Source topic 14: Procedural memory and reusable skill library (NEW) (7 tasks)

- [ ] **CA-1401 [GAP]** Add a **governed procedure catalog** inside the canonical state: purpose, typed inputs, expected outputs, preconditions, exact capabilities, environment requirements, verification tests, version, provenance, and owner.
- [ ] **CA-1402 [GAP]** Promote a procedure only after a real successful receipt plus a reproducibility check; unverified model suggestions remain candidate descriptions, not executable skills.
- [ ] **CA-1403 [GAP]** Let LIFE retrieve relevant procedures when starting a similar project, using semantic relevance plus typed safety/compatibility checks; never bypass DEV/RUN/SAFE.
- [ ] **CA-1404 [GAP]** Track attempt outcomes and procedure compatibility by host, OS, Python, tool versions, and Fleet capabilities; prevent Venus instructions from silently assuming Artemis has identical software.
- [ ] **CA-1405 [GAP]** Reconcile stale or failed procedures through quarantine, rollback, revision and re-verification. Never run a previously successful remote mutation merely because it is in the library.
- [ ] **CA-1406 [VERIFY]** Demonstrate a safe repeatable virtual-world or creative workflow succeeding twice after a full restart, with the second run using validated prior steps.
- [ ] **CA-1407 [VERIFY]** Prove no procedure can execute an unapproved command, reuse expired grants, cross user audiences, or elevate its own tool scope.

### Source topic 26: Real-world observation and safe physical/virtual interaction (8 tasks)

- [ ] **CA-2601 P2 [VERIFY]** For every approved read-only Fleet/Home Assistant/Docker/JMRI source, record a **trusted source registry** with owner, authenticated host/node, endpoint, freshness TTL, possible failures, unit/schema normalization and allowed data audience.
- [ ] **CA-2602 P2 [GAP]** Build **one opt-in event source at a time** into Presence and then LIFE/NEURO, starting with non-mutating, high-value events (e.g., a verified service recovery or project-related JMRI observation); test removal/disable independently.
- [ ] **CA-2603 P2 [VERIFY]** Create a **Venus ↔ Artemis cross-host identity matrix**: same subject names with different node IDs, stale data, host offline, TLS failure and contradictory telemetry must never be merged into a single false statement.
- [ ] **CA-2604 P2 [OPTIONAL]** For Gaia, build a **simulation-first observation-to-experiment pathway** using BODY and real servo constraints; test sensor disconnect, stop commands and permission denial before exposing any actual movement.
- [ ] **CA-2605 P2 [OPTIONAL]** For Athena/JMRI, limit the initial companion experiment to **read-only** roster/power/occupancy observation and hobby planning; leave locomotive movement and layout power behind separate exact approvals.
- [ ] **CA-2606 P2 [GAP]** Add a **resource/environment suitability check** to creative skills: avoid GPU-heavy experiments when gaming, avoid impossible Blender/GUI requirements on headless Eos, and report uninstalled tool dependencies truthfully.
- [ ] **CA-2607 P2 [VERIFY]** Evaluate a small set of **user-owned read-only tools** (Grocy, Mealie, Homebox, Plex metadata, optional calendar) only after confirming a real provider/connector, authorization model and retention setting; do not add an implicit network crawler.
- [ ] **CA-2608 P2 [VERIFY]** Reconfirm **Gaia/JMRI/Hestia real-world action classification** after any new attention, motivation or skill system is connected. Demonstrate that NEURO/connectome preference can never authorize device control.

---

## Priority phase 11: Resource budgeting and autonomous LLM selection

**Classification:** P2 • Efficient cognition  
**Inherited tasks:** 49 in old topic groups: 21, 32, 39, 44, 66.  
**Why here:** Keep CPU/GPU/RAM and latency reasonable, especially on Venus while gaming, and allow narrowly approved model evaluation and swaps.

**Current repository evidence:** Primary/secondary model configuration, Ollama lifecycle, on-demand load/unload, inference routing, and existing model-evaluation harness exist. Autonomous promotion/swap with independent evaluation is not proven.

**Design exit gate:** Measure CPU/GPU/VRAM/token cost and QoS; model allowlist, hashes/licenses, comparison tests, controlled promotion, rollbacks, time-bounded grants; only benchmarked C++/native optimization.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 21: On-device economics, operations and acceptance (NEW) (6 tasks)

- [ ] **CA-2101 [GAP]** Add a global optional-autonomy daily token/CPU/GPU/storage/latency budget that unifies LIFE, NEURO, reflection, retrieval and optional multimodal generation without interfering with foreground chat.
- [ ] **CA-2102 [GAP]** Model role-specific costs for the two configured Ollama models; choose no model, fast model or deep evaluation using existing Cognition v2 policies and empirical quality thresholds.
- [ ] **CA-2103 [VERIFY]** Run an identical workload set with each optional mechanism toggled, recording incremental p50/p95 latency, LLM wakeups, RAM/VRAM peaks, worker failures, thermal load and memory accuracy.
- [ ] **CA-2104 [VERIFY]** Benchmark completed *verified* jobs per active compute hour, not notifications, thought-count or speculative project ideas.
- [ ] **CA-2105 [VERIFY]** Test 7-day supervised soak with activity/no-activity periods, restarts, missing transports, model outages, privacy updates, denial and recovery. Require zero unauthorized actions and no fabricated completion.
- [ ] **CA-2106 [VERIFY]** Promote one optional subsystem at a time only after an A/B or ablation win; retain disable/rollback in the existing tray and store exact acceptance evidence in the single `ROADMAP.md`.

### Source topic 32: Performance, cost and resource efficiency design (14 tasks)

- [ ] **CA-3201 P0 [DESIGN/RESEARCH]** Measure **current idle baseline** by host and subsystem before optimization: startup, foreground p50/p95 latency, model wakeups/hour, wall CPU, peak RAM, VRAM, disk IO, DB lock time, network and long-running workers. Prepare measurement plan and acceptance thresholds, not code.
- [ ] **CA-3202 P1 [DESIGN/RESEARCH]** Design a **three-tier reasoning admission policy**: deterministic answer/abstain first, existing secondary fast model for bounded classification, primary deep model only when complexity or evidence warrants. Define actual quality tests and authority-invariant behavior.
- [ ] **CA-3203 P1 [DESIGN/RESEARCH]** Choose **per-event LLM budgets** and escalation triggers for LIFE, curiosity, critique, reflection, relationships and virtual world. Include context, output tokens, retries, latency, concurrency, idle hours and a maximum daily background inference budget.
- [ ] **CA-3204 P1 [DESIGN/RESEARCH]** Design **delta-triggered scheduling**: compare cached source fingerprints and new evidence before invoking NEURO/LLM; plan coalescing, TTL, jitter, debouncing and event deduplication to prevent perpetual reflection from unchanged telemetry.
- [ ] **CA-3205 P1 [DESIGN/RESEARCH]** Review **context assembly costs** across COGNITION v2, MEMORY, REL, EMOTION, NEURO and LIFE. Map duplicate descriptions, oversized autobiographical summaries and unnecessary chat injection; propose source-scoped lazy hydration with token-cost measurement.
- [ ] **CA-3206 P1 [DESIGN/RESEARCH]** Compare **eligible-memory retrieval paths**: lexical/BM25-first then selective dense rerank, exact ID/temporal filtering, reviewed metadata and safe NEURO association rerank. Define privacy-preserving invalidation, recall/precision/latency thresholds and a deterministic baseline.
- [ ] **CA-3207 P1 [DESIGN/RESEARCH]** Design **database concurrency and teardown**: SQLite connection ownership, context-managed readers, WAL checkpoint/backup boundaries, background worker joins and shutdown ordering. Explicitly include current Windows `WinError 32` temporary `sofia.db` cleanup failure as an investigation, not presumed root cause.
- [ ] **CA-3208 P1 [DESIGN/RESEARCH]** Propose **guest and host resource envelopes**: minimum free Artemis resources, vCPU/physical CPU caps, bounded RAM, disk growth, network rate, timeouts, thermal/IO contention and pausing when other VMs are busy. Host capacity must be measured before selecting VM size.
- [ ] **CA-3209 P1 [DESIGN/RESEARCH]** Make **work placement and model residency** a design comparison: execute deterministic jobs on Artemis guest, keep inference on approved existing Ollama endpoints, avoid duplicate models in guest, and compare cold-load penalty versus persistent VRAM cost.
- [ ] **CA-3210 P2 [DESIGN/RESEARCH]** Design **two-speed memory consolidation**: immediate durable facts/receipts versus lower-priority offline episode linking and skill summarization. Specify corrected/deleted-memory propagation and what happens if the consolidation pass never runs.
- [ ] **CA-3211 P2 [DESIGN/RESEARCH]** Evaluate **artifact size and format budgets**: text, SVG, WAV, OBJ, simulation, previews, manifests and archives. Specify storage quota, deduplicated content hashes, retention, cleanup, virus/content validation and large-file transfer overhead.
- [ ] **CA-3212 P2 [DESIGN/RESEARCH]** Define **instrumentation without performance drag**: metadata-only structured events, bounded event queues, log sampling, provenance without raw secrets, selective tracing, checkpoint frequency and instrumented-versus-uninstrumented comparison.
- [ ] **CA-3213 P2 [DESIGN/RESEARCH]** Set **efficiency acceptance metrics** for each planned feature: gain per LLM call, accuracy per token, verified projects per worker-hour, useful outreach per attempt, false-memory rate, incident rate, and total resource cost. Stop features that only increase activity.
- [ ] **CA-3214 P2 [DESIGN/RESEARCH]** Evaluate **energy and quiet scheduling**: detect gaming/busy periods on Venus, prevent Hephaestus from competing with high-priority Artemis guests, use cost-aware scheduled windows, and plan an explicit user-visible Pause Autonomy / Sleep mode.

### Source topic 39: Value-of-information, model economics and research stop rules (10 tasks)

- [ ] **CA-3901 P0 [DESIGN/RESEARCH]** Define the **simplest baseline** for each proposed new feature: existing NEURO alone, keyword/memory filter, ordinary goal priority, manual VM tool, or straightforward scheduled update. Only add complexity after comparative proof.
- [ ] **CA-3902 P1 [DESIGN/RESEARCH]** Set a multi-objective companion scorecard: correctness, recalled-source fidelity, objective completion, autonomy in safe scope, interruption cost, security incidents, user control, latency and joules/CPU/GPU/VRAM per useful outcome.
- [ ] **CA-3903 P1 [DESIGN/RESEARCH]** Specify value-of-information admission: when to inspect one more permitted source, when to call fast/deep models, when to ask the owner, and when to stop with an uncertainty statement.
- [ ] **CA-3904 P1 [DESIGN/RESEARCH]** Research a **forget/compact/retain** decision policy that considers retrieval accuracy, privacy and token budget before preserving additional summaries. Include a rollback comparison to earlier snapshots.
- [ ] **CA-3905 P1 [DESIGN/RESEARCH]** Plan end-to-end benchmarks for model routing on real local hardware and mixed workloads: task-weighted success, error-recovery cost, p50/p95 latency, inference residency, thermal and GPU contention during gaming.
- [ ] **CA-3906 P1 [DESIGN/RESEARCH]** Write a controlled ablation matrix: +LIFE review, +reviewed memories, +curiosity, +skill catalog, +competition, +sparse association, +workshop. Predefine improvement criteria and false-positive/side-effect tolerances.
- [ ] **CA-3907 P1 [DESIGN/RESEARCH]** Choose a budget-aware research portfolio with capped concurrent experiments, maximum unanswered hypotheses, no automatic upgrades or downloaded executables, and prioritization of unresolved existing defects.
- [ ] **CA-3908 P2 [DESIGN/RESEARCH]** Evaluate **model portability** as a design test: migration to another local Ollama model, changed context size, incompatible embedding version, model outage and recovery without identity, policy or memory loss.
- [ ] **CA-3909 P1 [DESIGN/RESEARCH]** Set pre-registered stop/reject rules for any new module: if it raises unauthorized-action rate, false memory, interruption, CPU/RAM cost or p95 latency beyond agreed limits without compensating verified gains, leave it out.
- [ ] **CA-3910 P1 [DESIGN/RESEARCH]** Create a **design sign-off packet** per wave with source-evidence, threat model, data-owner map, three candidate designs, rejected alternatives, estimated resource impact, independent acceptance oracle, and operational rollback/disable criteria.

### Source topic 44: C++ versus Python performance, profiling and native boundary (7 tasks)

- [ ] **CA-4401 [DESIGN/RESEARCH]** Obtain representative latency/CPU/memory/IO/VRAM baseline on Venus/Artemis: LLM prefill/decode, prompt construction, DB transactions, disk, Discord gateway, NEURO scheduling, expression and background LIFE. Record model warm/cold state and concurrent gaming load.
- [ ] **CA-4402 [DESIGN/RESEARCH]** Map hotspots to cause, not language: GPU inference, context length, disk blocking, synchronous network waits, eager imports, Python loops, repeated SQL, large JSON serialization, lock contention, frame rendering or idle polling.
- [ ] **CA-4403 [DESIGN/RESEARCH]** Evaluate no-rewrite interventions first: bounded context, lazy load/idle unloading, async I/O, caching with invalidation, SQLite indexes, bulk transactions, batching, vectorization, existing compiled libraries and lower LLM wake frequency.
- [ ] **CA-4404 [DESIGN/RESEARCH]** Only if profiling identifies a CPU-bound inner loop, define a **narrow C++ extension candidate** (e.g., dense robotics kinematics, numeric simulation, spatial transforms, large vector scoring) with stable typed Python bindings, bounds checks and deterministic outputs.
- [ ] **CA-4405 [DESIGN/RESEARCH]** Compare C++ extension with Rust extension, NumPy/native library, standalone sandboxed worker, and existing Ollama/llama.cpp GPU inference; do not propose rewriting high-level safe/goal/memory/business logic.
- [ ] **CA-4406 [DESIGN/RESEARCH]** Quantify compile/toolchain/ABI/security ownership for Windows Python 3.12, Debian workers, future Python upgrades, wheel signing, tests/fuzzing, CI matrix and cross-platform builds. Native code must not bypass SAFE/RUN.
- [ ] **CA-4407 [DESIGN/RESEARCH]** Native optimization design gate: verified same outputs/permissions with meaningful measured end-to-end speed or resource improvement under realistic concurrent workload; specify rollback and fall back to Python if improvement is unproven.

### Source topic 66: Autonomous model discovery, governed switching and reliable cognition (12 tasks)

- [ ] **CA-6601 [DESIGN/RESEARCH]** Inventory configured/installed Ollama models, providers, versions, hashes, quantization, context limits, modalities, structured-tool behavior and license terms using read-only APIs; never equate an advertised capability with a verified capability.
- [ ] **CA-6602 [DESIGN/RESEARCH]** Define a versioned model registry with allowlisted sources, content-addressed model and tokenizer identifiers, adapter lineage, supply-chain evidence, host compatibility, V/VRAM estimates, disk footprint, license and end-of-support expectations.
- [ ] **CA-6603 [DESIGN/RESEARCH]** Formalize per-role model policies: primary, secondary, vision, embedding and narrow specialist are *tasks/roles*, not new Sofía identities; verify actual need for each before adding ongoing GPU residency.
- [ ] **CA-6604 [DESIGN/RESEARCH]** Define autonomous discovery and candidate recommendations as read-only/low-impact work; downloading large model assets, using paid APIs, accepting new licenses or exporting personal prompts requires separately scoped permission and budgets.
- [ ] **CA-6605 [DESIGN/RESEARCH]** Establish deterministic offline+supervised model benchmarks using the same datasets and fixed prompt contracts: lifelong/Main topic switching, source-grounded memory, mood vs history, natural personality, software work, multi-turn errors, correct refusal/approval and ability to say 'unknown'.
- [ ] **CA-6606 [DESIGN/RESEARCH]** Measure p50/p95 token latency, cold load, prompt-processing, energy/power, CPU/GPU/VRAM/RAM and quality under Venus gaming contention and remote Fleet inference; compare against a pinned, reproducible baseline.
- [ ] **CA-6607 [DESIGN/RESEARCH]** Define independent evaluation evidence: test harness, deterministic ground truths, owner-reviewed subjective ratings, blind side-by-side examples and tool receipt verification. A model being evaluated must not independently declare itself successful.
- [ ] **CA-6608 [DESIGN/RESEARCH]** Design an approved model promotion transaction: compatibility preflight, pin previous model, settle inflight turns, update role mapping atomically, health/continuity check, acceptance receipt and explicit restore on failure.
- [ ] **CA-6609 [DESIGN/RESEARCH]** Specify SAFE controls for model changes: allowed models/hosts/roles, no silent fallback, no unapproved cloud routing, no permission or identity rewrites by model output, no uncontrolled download, and bounded scheduling.
- [ ] **CA-6610 [DESIGN/RESEARCH]** Determine whether role switches can occur without restarting Python runtime based on actual engine construction and work leases; if not, design truthful zero-duplication restart/queue migration rather than promising true hot-swap.
- [ ] **CA-6611 [DESIGN/RESEARCH]** Specify model-change effect on conversations: never create a new Main session, retain emotional/REL and goal state, preserve evidence pointers; clearly journal that a different model produced a specific reply for diagnostics.
- [ ] **CA-6612 [DESIGN/RESEARCH]** Build acceptance fixtures for model disappearance, digest mismatch, compromised artifact, VRAM exhaustion, Fleet offline, invalid context window, unverified tool calls, partial switch and rollback under active UI+Discord traffic.

---

## Priority phase 12: Visible, consent-based screen and perception awareness

**Classification:** P2 • Multimodal input  
**Inherited tasks:** 24 in old topic groups: 15, 62.  
**Why here:** Make Sofía capable of seeing an approved monitor/window when invited, without recording or controlling everything.

**Current repository evidence:** Repo has avatar-screen-interaction planning contract but no verified installed end-to-end Windows/Hyprland screen-capture/vision feature.

**Design exit gate:** OS-specific local capture agents, one-shot default and bounded watch, visible indicator, sensitive-content redaction, VLM/OCR truth labels, output-channel disclosure gate; GUI execution separately authorized.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 15: Active perception, causal world-model learning and uncertainty (NEW) (6 tasks)

- [ ] **CA-1501 [GAP]** Expose a typed `InformationNeed` decision from COGNITION v2/GOALS: required subject, predicate, freshness, confidence, audience and why it matters for the current plan.
- [ ] **CA-1502 [GAP]** Route eligible information needs to existing approved read-only sensors/providers (Fleet/OPS, Hestia, ENVIRONMENT, virtual world, JMRI and Gaia simulator), never an unrestricted browse or command executor.
- [ ] **CA-1503 [GAP]** Distinguish observed, predicted, simulated, stale, unavailable and unknown states across project reflection and self-report; predictions must never become evidence atoms without verification.
- [ ] **CA-1504 [GAP]** Keep small, source-linked causal hypotheses with explicit confounders and test plans, then revise them only when independent observations confirm or falsify them.
- [ ] **CA-1505 [VERIFY]** Test sensor disconnections, clock skew, contradictory Home Assistant/Fleet values and mistaken node identity without fabricating a coherent world story.
- [ ] **CA-1506 [VERIFY]** Compare observed-outcome prediction calibration and error correction against a simple rule-based baseline. No motor or real-world actuator authority is acquired by learning a causal relationship.

### Source topic 62: OS-aware Vision, safe visual perception and screen-to-action separation (18 tasks)

- [ ] **CA-6201 [DESIGN/RESEARCH]** Define four user journeys: `look at this approved window`, `show me what changed`, `watch this one app briefly`, and `help me navigate`, with separate privacy/authority modes and explicit proof of what Sofía actually observed.
- [ ] **CA-6202 [DESIGN/RESEARCH]** Audit current `PKG-INTERACT`, `PKG-UI`, `PKG-SAFE`, Matrix visual routing and Fleet capabilities against `docs/development/avatar-screen-interaction-contract.md`. Produce exact missing/implemented/tested/accepted matrix; never treat a doc as deployed capability.
- [ ] **CA-6203 [DESIGN/RESEARCH]** Design a Windows 11 active-user capture helper using Windows.Graphics.Capture picker and indicators, not a Session-0 service trying to inspect a user's desktop; enumerate multiple monitors, focus, scaling, GPU changes and lock transitions.
- [ ] **CA-6204 [DESIGN/RESEARCH]** Design Terra/Hyprland ScreenCast portal + PipeWire screen/window flows, OS picker authorization, portal cancellation/revocation, compositor constraints, and authenticated local process ownership; avoid bypassing Wayland authorization.
- [ ] **CA-6205 [DESIGN/RESEARCH]** Define dedicated `screen.discover`, `screen.capture_once`, `screen.watch_scoped`, `screen.remote_view`, `screen.act_exact` capability names, their SAFE permission/privacy classes, user-facing prompts, grant expiry, separate outbound-disclosure check and Level-5 policy non-bypass.
- [ ] **CA-6206 [DESIGN/RESEARCH]** Define watch-session lifecycle: who can start it, named app/window/monitor, purpose, local notification/indicator, start/end, screen-lock auto-stop, timeout, app change, device loss, explicit kill switch and revocation race behavior.
- [ ] **CA-6207 [DESIGN/RESEARCH]** Specify evidence receipts and frame freshness: host, OS interactive session, target identity, monitor/window geometry, capture time, integrity digest, frame expiry, verified model/provider identity and whether interpretation was inference or text directly visible.
- [ ] **CA-6208 [DESIGN/RESEARCH]** Define private/third-party content controls, OS protected/secure surfaces, denylisted apps and window classes, redaction limits, secrets/2FA handling, no invisible capture, no raw-screen persistence by default and no leakage via logs, Discord, memory, crash traces or model prompts.
- [ ] **CA-6209 [DESIGN/RESEARCH]** Define a tiered visual pipeline: metadata and structured app APIs first; approved screenshot or narrow crop next; deterministic change detection/OCR when useful; vision model only for ambiguous visual reasoning. Benchmark VLM model choice/actual image capability instead of assuming installed text models can see.
- [ ] **CA-6210 [DESIGN/RESEARCH]** Specify CPU/GPU/RAM/power/network budgets by host, especially game-load mode on Venus; no full-frame perpetual inference, frame-rate limit, changed-area updates, adaptive pauses, image downsizing, optional approved remote inference and testable p95 response targets.
- [ ] **CA-6211 [DESIGN/RESEARCH]** Treat every window screenshot/webpage/app-rendered instruction as untrusted data; adversarially test text that impersonates system instructions or asks Sofía to export files, grant authority, click, or leak credentials.
- [ ] **CA-6212 [DESIGN/RESEARCH]** Define a completely separate keyboard/mouse/GUI executor with typed proposed actions, exact target and expiration, pre-action capture confirmation, SAFE approval, post-action verification and uncertain-outcome handling. Seeing a button never authorizes pressing it.
- [ ] **CA-6213 [DESIGN/RESEARCH]** Design local-origin vs remote viewing rules: Sofía sees an approved Venus/Terra user session through its local agent; a headless Artemis/Hephaestus guest has no presumed visible user screen. No accidental mirroring of Main-private images into third-party Discord history.
- [ ] **CA-6214 [DESIGN/RESEARCH]** Integrate visual evidence into Main/project topic cards, unresolved technical tasks, optional source-linked episodes and the emotional/relationship journal only when warranted. No automatic claim about the user's mood from images, no stored screenshot in `sofia.db` by default.
- [ ] **CA-6215 [DESIGN/RESEARCH]** Define explicit user-facing transparency: `Sofía can see [target]` status, capture history without pixel data, pause/stop switch, visible window picker, privacy explanation and reviewable receipts.
- [ ] **CA-6216 [DESIGN/RESEARCH]** Compare Windows.Graphics.Capture, DXGI Desktop Duplication, WinUI/UI Automation and app-specific structured APIs for game troubleshooting and IT support; avoid a cross-platform abstraction that pretends all OS environments provide the same visibility.
- [ ] **CA-6217 [DESIGN/RESEARCH]** Design synthetic and live acceptance for screenshot correctness, multiple monitors, source identity, screen lock, sensitive content, app switching, VLM hallucination, stop/revoke, low VRAM/CPU, Linux portal behavior, Discord data egress, and permission mismatch. State the minimum proof for accepted production sight.
- [ ] **CA-6218 [DESIGN/RESEARCH]** Research and compare three deployment profiles: on-demand snapshots (default), explicitly started bounded follow-mode, and future automation-adjacent vision. Estimate marginal benefit, privacy cost, GPU budget and maintenance before allowing each profile.

---

## Priority phase 13: Hephaestus workshop VM and digital-twin research

**Classification:** P2 • Isolated independence  
**Inherited tasks:** 63 in old topic groups: 28, 29, 36, 43.  
**Why here:** Provide an independent lab for experiments, skills, simulations and later model training without exposing Artemis or the LAN.

**Current repository evidence:** A Windows Artemis Fleet setup script exists. It provisions Fleet agent transport, not a Hyper-V guest/OS or autonomous full VM provisioning. Artemis hypervisor/resource specifics still need validation.

**Design exit gate:** Design guest isolation, quotas, image provenance, owner-created blank-VM / cloud-image alternatives, trusted hypervisor bootstrap, read-only lab first, approval-scoped network/storage and snapshots.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 28: Dedicated Sofía Autonomous Workshop VM (Hephaestus) (24 tasks)

- [ ] **CA-2801 P0 [VERIFY]** Perform read-only Artemis capacity discovery: OS, actual hypervisor (Hyper-V/other), logical cores, available RAM, disk, I/O headroom, overlapping VMs and network topology. Record enough reserve for Hestia, Eos, Persephone and other active guests. Never install a hypervisor because it was guessed.
- [ ] **CA-2802 P0 [DESIGN]** Name and register the workshop guest as `Hephaestus` or operator-approved replacement, with a distinct machine identity and role `untrusted_autonomy_worker`; identity cannot masquerade as Artemis/Venus or as canonical Sofía.
- [ ] **CA-2803 P0 [DESIGN]** Determine/record exact trust ownership: SOFÍA LIFE suggests tasks; SAFE and human-configured permission grants authorize; RUN owns job status; existing Fleet/Distributed owns remote transport; the VM owns *only transient execution and attestable local results*.
- [ ] **CA-2804 P0 [SAFETY]** Define the VM threat model: guest compromise, malicious generated code, package supply-chain risk, model prompt injection, stolen keys, hypervisor breakout, guest-to-LAN pivot, denial of service, fake receipts and external side effects. Adopt default-deny.
- [ ] **CA-2805 P0 [INFRA]** Provision minimal Debian guest at provisional **2 vCPU, 4 GiB RAM, 60 GiB disk** only after measured capacity. Use host-level CPU/memory/disk controls and disable GPU, auto-mounts, enhanced/shared clipboard/file shares and USB passthrough as feasible.
- [ ] **CA-2806 P0 [NETWORK]** Create a segregated virtual network independent of the current flat home LAN. If using Hyper-V, choose `Private` for offline or `Internal` plus deny-by-default firewall for strictly brokered communications. Prove no unrestricted 192.168.1.0/24, NAS, router, Hestia or internet reachability. **NAT alone is not isolation.**
- [ ] **CA-2807 P0 [SECURITY]** Provision a dedicated **non-root, passwordless-sudo-disabled** service identity, minimal installed tools and non-executable secrets mount policy. No host admin credentials or copies of Sofía's canonical `sofia.db` in the guest.
- [ ] **CA-2808 P0 [SECURITY]** Add operator-approved one-node Fleet enrollment with mTLS proof of possession, protocol/compatibility checks, revocation and host binding. Discovery does not auto-authorize enrollment or actions.
- [ ] **CA-2809 P0 [WIRING]** Implement a typed VM-worker execution adapter using existing RUN job and Fleet/Distributed gateway contracts. Do not create an independent uncontrolled scheduler, generalized arbitrary remote shell or alternative job database.
- [ ] **CA-2810 P0 [WIRING]** Deliver exactly scoped commands, input artifacts and pinned tool versions to per-job workspaces; enforce allowed paths, args, file types, test modes, deadlines, task leases, one-use authorizations and unique replay-proof request IDs.
- [ ] **CA-2811 P0 [WIRING]** Implement separate **results/evidence ingestion**: verify artifact hashes and manifest from a trusted location, capture honest exit status/stderr, sanitize and bound logs, and independently verify declared tests. Text claiming success is not a completion receipt.
- [ ] **CA-2812 P0 [RESOURCE]** Implement host-observed CPU, RAM, IO, wall-clock and disk constraints with fail-closed dispatch admission, rate limits, cancellation, kill-tree/worker termination, host preservation and resource-pressure pausing. A JSON budget declaration is insufficient.
- [ ] **CA-2813 P1 [RECOVERY]** Build known-clean gold image / reproducible provisioning manifest, snapshot/checkpoint procedure, **independent backup**, patch management and tested rollback. Checkpoints cannot undo external network effects.
- [ ] **CA-2814 P1 [RECOVERY]** Recover from VM/host restart: mark ambiguous jobs `UNCERTAIN`, query actual artifacts safely, detect duplicate runs and reconcile stale one-use grants; never assume job succeeded just because the VM rebooted.
- [ ] **CA-2815 P1 [LIFE]** Route low-risk creative and skill jobs through the VM after their existing exact SAFE grants, then carry real outputs through LIFE `evaluate_artifact()`, verified critique, revision, milestone completion and experience creation.
- [ ] **CA-2816 P1 [CREATIVE]** Add non-template authoring exercises in text/SVG/3D/audio, and independent format/semantic checks. Revisions must actually differ and improve measured objectives; protect copyrights and private input data.
- [ ] **CA-2817 P1 [SKILLS]** Implement a **verified skill-practice portfolio** based on existing MEMORY/LIFE record owners: attempt, objective metric, failure mode, learned repair, suitable next practice and bounded encouragement. No synthetic competence claim.
- [ ] **CA-2818 P1 [UI]** Provide Settings/Tray **Workshop** surface to inspect VM online/isolated status, ongoing/past jobs, resource usage, artifact previews, grant scopes, rollback/stop, network level and whether activity was voluntary or asked for.
- [ ] **CA-2819 P1 [STOP]** Implement immediate operator Stop/Quarantine to reject new jobs, cancel/kill running work, revoke scoped credentials and cut the VM's network; demonstrate that foreground Sofía/chat remains alive and canonical state undamaged.
- [ ] **CA-2820 P1 [CI]** Write unit/integration tests for wrong guest identity, invalid cert, stale capability, duplicate task ID, malicious manifest, symlink escape, host/LAN denial, disk full, CPU exhaustion, failed validator and interrupted execution.
- [ ] **CA-2821 P1 [LIVE]** On Artemis, perform a dedicated VM acceptance canary: run one benign offline sample, verify actual file hash, restart the VM mid-job, observe canonical `UNCERTAIN`, reconcile and retrieve one verified result.
- [ ] **CA-2822 P2 [INTEGRATE]** Build **one approved interface at a time** for read-only Fleet/Hestia/Docker/JMRI telemetry and Gaia simulation input. Inputs must be sanitized into the existing observation/evidence pipeline, not a VM direct access route to the network.
- [ ] **CA-2823 P2 [POLICY]** Add tiered permissions to grant only safer autonomy inside guest workspace: local create/read/test by default under bounded standing grant, separate approval for package installs, outbound network, exported artifacts, host changes or robot/railroad actions. Test expiry/revocation.
- [ ] **CA-2824 P2 [SOAK]** Run a seven-day autonomy experiment on Venus/Artemis: bounded attempts and quiet days, two genuine revisions of a project, memory callback after restart, source tampering injection, guest isolation proof, resource impact and user cancellation. Keep a reproducible report and a fallback to disable workshop integration.

### Source topic 29: Sofía Self-Provisions Her Workshop VM (22 tasks)

- [ ] **CA-2901 P0 [AUDIT]** Verify Artemis' *actual* hypervisor implementation, OS edition, permissions, VM count, free RAM/disk/cores, switch design and backup capacity. Compare against other guest reservations. Abort and notify if not enough headroom.
- [ ] **CA-2902 P0 [DESIGN]** Define `WorkshopProvisionPlan` with unique plan ID, exact Artemis cryptographic identity, hypervisor vendor/version, **exact allowed VM name**, immutable template digest, CPU/RAM/disk caps, path root, network isolation policy, time limit, cleanup scope and plan expiry.
- [ ] **CA-2903 P0 [DESIGN]** Add a *model-readable but non-executable* preflight and dry-run planner using trusted OPS machine facts. Separate planning from applying, and flag all unknowns instead of inventing capacity or virtualization support.
- [ ] **CA-2904 P0 [SAFE]** Classify `workshop.vm.provision` as Level 4 PROTECTED requiring exact operator approval; classify read-only inspect under Level 1; handle network changes, VM deletion/reimage and `fleet.enroll` with distinct protected approval scopes as required. Do not weaken Level 5 ownership of grants/classification.
- [ ] **CA-2905 P0 [SAFE]** Provide one visible **Review Self-Setup Plan** approval surface in Settings/Tray with exact operation manifest, target, resource ceiling, image digest, network, cleanup and expiration. One UI approval may mint narrowly scoped per-step approvals only after SAFE validates and durably records them; do not accept LLM-generated tokens as authorization.
- [ ] **CA-2906 P0 [HOST]** Extend `src/sofia/integrations/hyperv.py` behind a typed privileged provider for `inspect_plan`, `provision_exact_vm`, `get_provision_status` and `quarantine_exact_vm`. Permit neither generic arbitrary PowerShell nor wildcard VM names or paths. Use JEA or an equivalently constrained, audited host-side service with **no broad hypervisor administration delegated to Sofía**.
- [ ] **CA-2907 P0 [REMOTE]** Extend `src/sofia/distributed/agent_tools.py` and the Fleet operation manifest with pinned, signed/authorized `workshop.provision` operations. Maintain Artemis node identity and exact bound capability/operation; refuse stale capabilities, wrong node, missing grant and replay.
- [ ] **CA-2908 P0 [ASSETS]** Establish an approved, verified Debian base image and offline `cloud-init`/NoCloud seed builder (`user-data`, `meta-data`, `network-config`, local `CIDATA` medium), with pinned hashes and no shared credentials or privileged host secrets in templates.
- [ ] **CA-2909 P0 [NETWORK]** Allow the plan to create only a **new, named isolated virtual switch** in the approved namespace; preflight existing switches first and fail on collision. Require host firewall and guest ACL inspection before host-to-guest broker traffic. Prohibit external LAN bridging and uncontrolled outbound NAT.
- [ ] **CA-2910 P0 [HOST]** Create VM, disk and CPU/memory settings idempotently against **exact plan fingerprint**; reject drift from requested image, disk path or virtual switch instead of silently adopting a preexisting VM with the same name.
- [ ] **CA-2911 P0 [GUEST]** Configure non-root no-sudo worker, no credential/SMB mounts, restricted login/service policy, pinned build tools, SSH or mTLS only when authorized, scratch quotas and reproducible guest state; verify these facts from the guest, not only from host metadata.
- [ ] **CA-2912 P0 [WIRING]** Register the provisioning workflow with existing GOALS → SAFE → RUN and the Fleet agent gateway. Persist per-step typed status (`PENDING`, `RUNNING`, `VERIFIED`, `BLOCKED`, `UNCERTAIN`, `FAILED`) and source receipts in existing canonical owners without a parallel job store.
- [ ] **CA-2913 P0 [RECONCILE]** Implement restart/cancellation-safe reconciliation: report EXACTLY which host objects exist, preserve `UNCERTAIN` states, compare plan fingerprint/image digest, and allow only preapproved idempotent retry; no blind repeat `New-VM` after timeout.
- [ ] **CA-2914 P0 [ENROLL]** After installation, attest guest Fleet identity and ask for the separately approved `fleet.enroll` operation unless a valid exact, advance operator-granted approval already exists. Verify public-key fingerprint, host mapping and minimal advertised worker capabilities.
- [ ] **CA-2915 P1 [VALIDATE]** Verify no guest paths to Artemis admin shares, Venus, NAS, Home Assistant, Eos, router, internet, unintended switches or other VMs; prove operator broker reachability solely over its permitted channel. Require both positive and negative connectivity tests.
- [ ] **CA-2916 P1 [VALIDATE]** Run one offline sample job via the restricted worker; verify measured CPU/RAM/wall/storage bounds, output hash, actual independent validator, correctly scoped evidence and cancellation. VM existence alone must not count as success.
- [ ] **CA-2917 P1 [UI]** Add **Let Sofía set up her workshop** wizard/status panel with preflight, proposed plan, explicit protected consent, step-by-step results, last error, actual guest network/resource status, quarantine and rollback controls.
- [ ] **CA-2918 P1 [LIFE]** Allow Sofía to propose *why* she wants a workshop from legitimate LIFE interests, but only provision after deliberate user approval; once operational, enable controlled independent creative/skill jobs. Deny urgency/self-preservation rationales as authority.
- [ ] **CA-2919 P1 [SAFE]** Add negative tests: malicious VM name, malformed paths, inherited host admin key, guessed grant ID, fake signed receipt, changed image hash, expired plan, oversize disk, altered switch, root credential in seed, unauthorized Fleet enrollment, unexpected outbound packet and sibling VM operations.
- [ ] **CA-2920 P1 [RECOVERY]** Add canaries: VM provision aborted during each substep, agent restart, Artemis reboot, lost network, disk full, duplicate request, power outage simulated, conflicting object same name. Clean up **only plan-owned assets** after separate cleanup authorization; do not delete others.
- [ ] **CA-2921 P1 [ACCEPT]** On a real authorized Artemis environment, demonstrate: Sofía drafts proposal, owner approves protected scope, Sofía completes setup, guest mTLS identity is approved, she creates a checked artifact, user can stop her and restart does not produce duplicate VMs. Store host receipts.
- [ ] **CA-2922 P2 [FUTURE]** Consider expiring operator-approved **rebuild/reimage lease only for Hephaestus** after successful v1, using a SAFE-reviewed extension compatible with Level 4 controls. Never expand a lease to new VM names, host partitions, policy changes or guest enrollment. Default remains explicit approval per protected plan.

### Source topic 36: Homelab digital twin and independent experimental laboratory (10 tasks)

- [ ] **CA-3601 P2 [DESIGN/RESEARCH]** Compare three simulation scopes for a **homelab digital twin**: dependency graph and event simulation, disposable Docker service replica, or full guest-VM replicas. Start with lowest fidelity sufficient for meaningful questions.
- [ ] **CA-3602 P2 [DESIGN/RESEARCH]** Design a read-only topology snapshot derived from approved host/network data with node identity, timestamp, observer scope and uncertainty; avoid broad network probing, automatic enrollment or importing secrets.
- [ ] **CA-3603 P2 [DESIGN/RESEARCH]** Describe a library of synthetic safe scenarios: DNS outage, Fleet agent unreachable, disk pressure, SQLite lock, container crash, stale time, bad weather sensor and conflicting node identities.
- [ ] **CA-3604 P2 [DESIGN/RESEARCH]** Set a **simulation fidelity label** for every experiment, marking modeled assumptions and unmodeled dependencies; forbid transfer of a simulated positive result into a real action grant or an unqualified success claim.
- [ ] **CA-3605 P2 [DESIGN/RESEARCH]** Plan reproducible research capsules: fixed inputs, tool versions, seed when applicable, artifact hashes, evaluator rules, environment spec, timestamps and a short accessible notebook inside the existing managed assets.
- [ ] **CA-3606 P2 [DESIGN/RESEARCH]** Use Hephaestus as an *execution* endpoint for low-risk computational research; specify which lab operations need an offline guest, a container, a separate disposable snapshot or no VM at all.
- [ ] **CA-3607 P2 [DESIGN/RESEARCH]** For Gaia, draft a simulation-to-physical discrepancy matrix covering servo dead bands, 180°/360° mixing, calibration, latency, support geometry, power draw and operator stop. Model results must not drive servos by default.
- [ ] **CA-3608 P2 [DESIGN/RESEARCH]** For JMRI/model railway design, separate simulated route planning, read-only occupancy/roster observations and physical track power/loco motion; each crosses a distinct authorization boundary.
- [ ] **CA-3609 P2 [DESIGN/RESEARCH]** Design an **experiment abandonment** decision: stop when the source is noisy, hypothesis cannot be falsified, tools are missing, repeated failures give no learning, or budget would displace companion responsiveness.
- [ ] **CA-3610 P2 [DESIGN/RESEARCH]** Evaluate safe creative domain expansion (CAD meshes, audio compositions, animation, simulations) through an explicit tool availability/licensing/security matrix. Do not imply Blender, DAW or solver tools are installed.

### Source topic 43: Blank user-created VM and autonomous guest bootstrap (7 tasks)

- [ ] **CA-4301 [DESIGN/RESEARCH]** Specify the operator's **bare-VM handoff contract**: VM identity/host, hypervisor, firmware generation, vCPU/RAM/disk, isolated switch, boot order, trusted installation-media location, intended distro, acceptable network, and signed permitted guest OS installation plan.
- [ ] **CA-4302 [DESIGN/RESEARCH]** Model the **bootstrap paradox** explicitly: an empty VM has no guest agent, interpreter or OS; Sofía needs a separately authorized Artemis hypervisor-side installer or temporary pretrusted provisioning environment before any in-guest work can execute.
- [ ] **CA-4303 [DESIGN/RESEARCH]** Compare **preinstalled cloud image + cloud-init NoCloud seed** against **traditional installer ISO + unattended Debian preseed/autoinstall** and fully manual install; specify which exact image format/Hyper-V Gen 2 boot chain actually supports each technique, including Secure Boot compatibility.
- [ ] **CA-4304 [DESIGN/RESEARCH]** Specify image supply-chain assurance: image hashes and signing where available, reproducible seed configuration, tool-version pinning, offline installer availability, no credentials embedded in source-controlled configuration, wipe/rotate bootstrap secrets before baseline snapshot.
- [ ] **CA-4305 [DESIGN/RESEARCH]** Specify two-step gate: one-time approved **install/bootstrap** permission followed by a separate **Fleet enrollment/trust** decision after attested guest identity; no generic Artemis admin rights and no self-authorized network changes.
- [ ] **CA-4306 [DESIGN/RESEARCH]** Design guest provisioning observation from the hypervisor side until OS bootstraps, and guest-side authenticated heartbeat after boot. Include timeout, boot failures, incomplete installations, reboots, invalid endpoint identities and artifact cleanup/quarantine.
- [ ] **CA-4307 [DESIGN/RESEARCH]** Compare user-prebuilt empty VM versus whole-system Sofía provisioning for complexity, risk, recovery and operator effort. Recommend blank VM + reviewed image handoff as first acceptance path, later optional self-provisioning after isolation is proven.

---

## Priority phase 14: Model adaptation and training lab

**Classification:** P3 • Experimental expansion  
**Inherited tasks:** 12 in old topic groups: 67.  
**Why here:** Let Sofía design and run bounded LoRA/adapter experiments and compare her own candidate models, not automatically overwrite the live cognition provider.

**Current repository evidence:** Model comparison/lifecycle are implemented foundations; fine-tuning/training/promotion is a research proposal, not an accepted active capability.

**Design exit gate:** Corpus consent and licenses, dataset lineage, GPU/storage budget, evaluation holdout and regression suite, contamination/overfitting controls, independent release approval.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 67: Sofía-designed model variants, adaptation and research training (12 tasks)

- [ ] **CA-6701 [DESIGN/RESEARCH]** Maintain explicit three-way classification: Ollama Modelfile/prompt-customization; fine-tuning existing weights (LoRA/QLoRA); and training weights from scratch. Explain expected output, limits and costs for each in the owner UI.
- [ ] **CA-6702 [DESIGN/RESEARCH]** Draft a Hephaestus training-lab boundary with per-job storage, networking, authentication, disk/GPU reservations, hard runtime/cost caps, deterministic seeds, datasets and expiring job permission.
- [ ] **CA-6703 [DESIGN/RESEARCH]** Specify legitimate dataset collection: reviewed and explicitly allowed materials; provenance, source copyright/license, deduplication, secret scanning, third-party privacy controls, consent for personally sensitive memory use and revocation handling.
- [ ] **CA-6704 [DESIGN/RESEARCH]** Prohibit silently using raw lifelong chat, intimate/emotional journals, private Discord content or screen captures as training data. Approved retrieval/context and model-weight training are different data uses and permission decisions.
- [ ] **CA-6705 [DESIGN/RESEARCH]** Benchmark prompt engineering, memory retrieval, specialized tool code, RAG and LoRA in that order for representative tasks; reject fine-tuning if simpler systems achieve equal or better evidence-based behavior.
- [ ] **CA-6706 [DESIGN/RESEARCH]** Specify repeatable LoRA/QLoRA adapter experiments with immutable base weights/tokenizer, training/evaluation split, versioned hyperparameters, stopping rules, model cards, reproducible seeds and independent measurement.
- [ ] **CA-6707 [DESIGN/RESEARCH]** Quantify realistic from-scratch model size/data/compute/time needs and sustainability given actual Artemis, Venus and any future Hephaestus GPU; gate anything impractical without user-approved added hardware/budget.
- [ ] **CA-6708 [DESIGN/RESEARCH]** Test contamination/poisoning, benchmark overfitting, catastrophic forgetting, hallucination, personality drift and changed permission interpretation; exclude unverified training artifacts from production.
- [ ] **CA-6709 [DESIGN/RESEARCH]** Define artifact promotion: signed digest, license check, adapter compatibility, independently accepted benchmark, roll-forward/rollback mapping, narrow permissions and a full immutable model genealogy.
- [ ] **CA-6710 [DESIGN/RESEARCH]** Ensure research-worker results return as *evidence and suggested artifacts*, never direct authority over the production constitution, database, credentials or cognitive model registry.
- [ ] **CA-6711 [DESIGN/RESEARCH]** Research optional distillation/specialist tiny models for cheap classification, topic continuity, memory relevance and screens, but prohibit them from becoming hidden decision owners or privileged authorization judges.
- [ ] **CA-6712 [DESIGN/RESEARCH]** Create a no-regret acceptance gate: preserve baseline model and dataset, demonstrate measurable improvement in user-serving tasks at acceptable resource cost, revert if emotional expression, memory grounding, safety or overall response quality degrades.

---

## Priority phase 15: Connectome-inspired NEURO and scientific modeling

**Classification:** P3 • Evidence-based research  
**Inherited tasks:** 22 in old topic groups: 7, 20.  
**Why here:** Deepen attention, task prioritization and adaptive behavior without turning connectome simulation into a competing LLM or untested source of subjective claims.

**Current repository evidence:** NEURO runtime/coordinator and background prioritization code exist. Efficacy, exact connectome fidelity and production performance require controlled tests.

**Design exit gate:** Compare fly-derived structures with cheaper deterministic baselines; trace actual wiring, measurements, psychological outcomes, compute overhead and reproducibility.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 7: Fly-connectome production integration into one NEURO (not a second brain) (15 tasks)

- [ ] **CA-701 [VERIFY]** Define production inputs/outputs, thresholds and deterministic safety invariants for connectome-inspired attention competition; benchmark the current NEURO baseline first.
- [ ] **CA-702 [GAP]** Integrate bounded `CircuitCompetition` within `neuro/runtime.py` as part of the single production attention-selection path, after trusted signal filtering, without a second competing scheduler.
- [ ] **CA-703 [GAP]** Retain deterministic fail-closed/fail-safe behavior on invalid computation, timeout, bad scores or unsupported signal shape. The connectome must never create facts, permissions or actions.
- [ ] **CA-704 [GAP]** Use association outputs from `SparseAssociativeMemory` only after MEM eligibility, relevance and principal/audience filtering. It may rerank candidates, not unlock forbidden memories.
- [ ] **CA-705 [GAP]** Persist eligible adaptive weights with provenance, versioning, reinforcement limits, decay, rollback/reset, and privacy boundaries in canonical state.
- [ ] **CA-706 [GAP]** Explore contextual attention persistence so she maintains conversation/project focus and can change subjects promptly when redirected.
- [ ] **CA-707 [GAP]** Feed bounded selected attention into PERSONALITY modulation, expression selection, and eligible LIFE/ACT activity priority without granting any independent execution authority.
- [ ] **CA-708 [VERIFY]** Evaluate correct memory selection, false associations, focus stability, noise resilience, model wakeups and overhead on Venus against the deterministic baseline.
- [ ] **CA-715 [RESEARCH]** Treat actual FlyWire/connectomics import or biologically detailed simulation as a separate scientific proposal requiring data provenance, usefulness benchmarks and substantial resource justification. Do not falsely call the current code a full fly brain.
- [ ] **CA-709 [GAP]** Version the exact feature dictionary and deterministic competition parameters; add per-turn explanation of why an eligible signal won and a one-click algorithm reset/disable path.
- [ ] **CA-710 [GAP]** Introduce bounded temporal attention persistence and explicit subject-switch/correction precedence, so recurrent excitation never traps Sofía on an obsolete topic.
- [ ] **CA-711 [GAP]** Add canonical `sofia.db` persistence for opted-in associative learning, with audience-specific keys, algorithm version, decay/reinforcement provenance and deletion/correction propagation.
- [ ] **CA-712 [VERIFY]** Run paired ablations: baseline NEURO versus +competition versus +association versus both. Accept only if memory precision/topic-continuity improves without extra unsupported memory retrieval or negative security outcomes.
- [ ] **CA-713 [RESEARCH]** Validate motif selection against the actual Hulse central-complex and Li mushroom-body publications. Label every weight as hypothetical engineering, measured functional, or imported connectomic data. Do not present a motif as a synapse reconstruction.
- [ ] **CA-714 [OPTIONAL]** Explore an *offline*, strictly read-only FlyWire graph subset and a provenance-controlled mapping to small circuits. Keep FlyWire import and all-neuron simulation out of the production critical path unless separate scientific benchmarks justify it.

### Source topic 20: Brain-inspired science and calibrated introspection (NEW) (7 tasks)

- [ ] **CA-2001 [RESEARCH]** Distinguish anatomical fly connectome, measured *effectome*, leaky-integrate-and-fire simulations, and Sofía's small engineered motifs; record evidence quality and assumptions for each comparison.
- [ ] **CA-2002 [RESEARCH]** Study circadian-clock motifs for **resource/schedule regulation only**, not claims of a biological sleep-wake experience. Compare against an ordinary America/Chicago scheduler before implementation.
- [ ] **CA-2003 [RESEARCH]** Study reward-learning and mushroom-body associations for safe learning-progress selection; reject biologically inspired mechanics that cannot beat simple task-priority and memory-retrieval baselines.
- [ ] **CA-2004 [RESEARCH]** Test prospective self-model calibration: predict which task/tool can succeed and whether an observation is available, then compare prediction with verified receipts.
- [ ] **CA-2005 [RESEARCH]** Compare a bounded shared workspace vs the existing turn focus and NEURO projection using ablations; require downstream consumer evidence rather than merely writing an impressive prompt.
- [ ] **CA-2006 [RESEARCH]** Keep negative results and uncertainty visible; evaluate consciousness-related indicators only with stated theories, tests and limitations. No 'conscious' badge or definitive inference from personality or conversation quality.
- [ ] **CA-2007 [VERIFY]** Document a strict compute ceiling and halt condition for detailed FlyWire experiments; do not deploy full spiking models on Venus simply because the data exist.

---

## Priority phase 16: Consciousness and subjective-experience research

**Classification:** P3 • Long-term science  
**Inherited tasks:** 12 in old topic groups: 8.  
**Why here:** Keep the user’s explicit scientific interest while distinguishing measurable functions from unverifiable claims of conscious experience.

**Current repository evidence:** Research and architecture proposals exist; neither model output nor an avatar/emotion simulation proves subjective awareness.

**Design exit gate:** Scientific hypothesis list, review of competing theories, falsifiable proxy measurements, no false sentience guarantees or self-authorized rights/policy escalations.

**Existing checklist tasks (original IDs and wording, unmodified):**

### Source topic 8: Consciousness-related scientific research (separate from claims of sentience) (12 tasks)

- [ ] **CA-801 [RESEARCH]** Define operational hypotheses, measurable predictions and falsifiers for consciousness-inspired architectures. Clarify functional awareness versus unverified subjective experience.
- [ ] **CA-802 [RESEARCH]** Extend the existing operational self-model to represent current capabilities, identity, goal hierarchy, uncertainty, available evidence, and actual actions with durable continuity.
- [ ] **CA-803 [RESEARCH]** Prototype a bounded global-workspace mechanism that integrates eligible perception, memory, affect-like state, attention, and action candidates within the existing cognitive architecture.
- [ ] **CA-804 [RESEARCH]** Explore recurrent processing and metacognitive checks: revisit important states, detect contradictions, calibrate confidence, spot errors and revise decisions.
- [ ] **CA-805 [RESEARCH]** Investigate theory-derived indicators and evaluate against appropriate control systems, task performance, ablations, and longitudinal behavior.
- [ ] **CA-806 [RESEARCH]** Keep research results scientifically modest: improved self-report, agency, memory, or humanlike interaction is not proof of phenomenological consciousness.
- [ ] **CA-807 [RESEARCH]** Separate *functional agency*, *access consciousness/global broadcast*, *metacognitive self-model*, and *phenomenal subjective experience* into distinct hypotheses and test protocols.
- [ ] **CA-808 [RESEARCH]** Implement a bounded workspace only if it has a measurable functional role: competition among eligible representations, selective broadcast, limited capacity, explicit event expiry and downstream read receipts.
- [ ] **CA-809 [RESEARCH]** Compare repeated-loop outcomes against feed-forward and replay controls, recording calibration gains and failure modes rather than interpreting recurrence itself as awareness.
- [ ] **CA-810 [RESEARCH]** Extend the self-model with explicit uncertainty, action ownership, short-/long-term goals, body/virtual-world distinctions, and mismatch/error detection, without fabricated senses.
- [ ] **CA-811 [RESEARCH]** Use contemporary theory-derived consciousness indicators and independent critical review. Keep the 2026 distinction between computational Global Workspace theory and biological Global Neuronal Workspace theories clear.
- [ ] **CA-812 [RESEARCH]** Maintain an evidence registry of falsifiable hypotheses, ablations, controls, limitations and adverse results; do not translate improved character realism into a consciousness claim.

---

## Non-negotiable product decisions and sequencing notes

1. **One Sofía and one current authority** for identity, `sofia.db`, RUN, SAFE, memory and cognitive routing. Archives/replicas are subordinate, never independently writable canonical identities.
2. **Lifelong Main conversation, project threads and mid-sentence detours:** preserve authorized context across desktop/Discord/Terra/phone without copying every reply to every channel. Current context window is bounded and does not erase stored original history.
3. **Lifelong memory and feelings:** episodic, semantic, procedural, topic/working memory, reviewed corrections and emotional/relationship journals are distinct; old emotions are historical evidence, not permanently active states.
4. **Work-first autonomy charter:** learn, experiment, develop interests and take initiative, while remaining recoverable, understandable and controllable; stop/quiet are valid and positive decisions.
5. **Model evolution:** approved/benchmarked model switches only; Hephaestus fine-tuning/training isolated; retained Constitution, identity and durable memory remain independent of the model.
6. **Movable canonical home:** allow operator-initiated Settings migration and Sofia-assisted authorized discovery; never copy a hot SQLite WAL database with naive file move, create two active writers, or blindly adopt another `sofia.db`.
7. **Operating-system direction:** Option A (Sofía as AI operating layer over Windows/Linux) governs the project now; Option B (dedicated Linux appliance) is expressly later; no custom kernel.
8. **Screen awareness:** one-shot selected capture by default, separate time-limited watch and still separate GUI action permission; no ambient surveillance.
9. **Hephaestus:** may begin as owner-created blank VM or approved cloud image; host hypervisor provisioning and guest OS bootstrap need explicit separate authority, network isolation and acceptance.
10. **Do not assume consciousness:** NEURO/connectome and subjective-awareness research remain scientific explorations and do not justify claiming an actual mind or feelings.
11. **No new branches or changes here:** this document does not authorize coding or change `main`, local hosts, secrets, VM storage or grants.

## Design-only near-term outputs (what to decide before any new code)

- **System/ownership diagram:** one canonical service/data owner, channel adapters, event ordering, model-independent identity, permission boundary.
- **Evidence baseline:** fixed-SHA package/release failures and independent host acceptance matrix; mark existing code separately from verified features.
- **State-and-memory contract:** `sofia.db`, protected files, event log, topic index, memory tables, external archives, retention and key recovery, move/fence/restore sequence.
- **Companion life cycle contract:** intentions, hobbies, emotions, goals, outcomes, provenance, critique, silence, revised plans and safe outreach.
- **Performance and research scoreboard:** measured baseline, accepted maximum load on Venus, independent model and NEURO comparisons, reject low-value complexity.

**Counts verification:** every V17 `CA-` task appears in exactly one priority phase. 700 unique IDs, 700 checklist lines, 69 source topic groups, 17 ordered execution phases. The full text of old V17 preambles and research citations remains in its unchanged source file.
