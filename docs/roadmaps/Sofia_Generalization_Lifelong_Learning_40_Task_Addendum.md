# Sofía V18 Generalization and Lifelong Learning: 40-Task Master Addendum

**Date:** 2026-10-13. **Status:** owner-requested planned scope, no production coding/testing/deployment claimed. **Repository:** main only.

**Non-negotiable goal:** Give Sofía a genuinely unfamiliar problem A, allow permitted investigation, verify a solution and its failures, then give her a different unfamiliar problem B and prove whether the learning from A improves independent B results. This requires unseen tasks, test isolation, actual independent outcomes, and meaningful comparisons against a no-learning agent. A sophisticated personality, many tools or stored transcripts alone do not satisfy this goal.

**Master inventory:** 700 original CA requirements + 40 preceding ML requirements + **40 GA requirements = 780 planned tasks**. This separate additive checklist preserves all original stable CA/ML identifiers, wording and acceptance status. GA items describe system-level acceptance and composition; reuse rather than duplicate existing subsystem features. The original CA evidence ledger remains an original-700 ledger until separately reconciled.

**Dependency order:** baseline CI/recovery + GA-00 -> GA-01 and GA-03 -> GA-02 and GA-04 -> GA-05 -> blinded GA-06. Existing ML-00..ML-07 provides optional prediction/learning infrastructure. Improve/benchmark underlying fast/deep LLM reasoning models without automatic model downloads or changes. Prefer outcome-based skill transfer over costly fine-tuning until justified.

**Exact transfer acceptance:** [Blinded A-to-B protocol](../development/sofia_generalization_transfer_acceptance_2026-10-13.md). Include withheld task families, before/after and ablation controls, explicit negative-transfer reports, reliability, elapsed time, help required, cost, safety failures, restart persistence, longitudinal retention, confidence and true rollback. Passing any benchmark does not establish AGI or consciousness.

**Authority and resource invariants:** Venus current single writer pending authenticated supervised Artemis cutover; use existing RUN/SAFE/FLEET/DEV owners and exact grants; no gaming mouse/keyboard control, gaming always prioritized and 30-minute verified idle controls; no override of STOP, quiet 22:00–08:00 America/Chicago, 15 social sends/day and 30-minute separation, 200k estimated optional tokens/day and one hour reserved GPU/day, 5 active research experiments, 15 unanswered hypotheses, scoped 24-hour media retention and owner authorization.

## GA-00: Evidence and benchmark foundations

- [ ] **GA-001 [PLANNED, NOT CODED OR ACCEPTED]** (phase 00; related CA-001, ML-001) Audit end-to-end investigate, plan, test, learn and transfer through the existing GOALS/LIFE/RUN/DEV/MEM/SAFE/VERIFY owners.
  - **Acceptance:** Trace a real existing source-to-effect pathway and list missing production callers.
- [ ] **GA-002 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-002, ML-005) Benchmark baseline reasoning, inference routes, tool use and problem-solving on genuinely unseen tasks.
  - **Acceptance:** Independently reproduced source/model-pinned success, cost, time and intervention statistics.
- [ ] **GA-003 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-1205, ML-005) Create sealed novel-problem suites covering Windows, Linux, Docker, coding and new simulation environments.
  - **Acceptance:** Separate training/validation/test problem families with auditable leakage controls.
- [ ] **GA-004 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-3501, ML-030) Use independently checked objective and partial-progress graders instead of self-reported task completion.
  - **Acceptance:** No model-authored success or subjective quality claim is accepted as independent proof.
- [ ] **GA-005 [PLANNED, NOT CODED OR ACCEPTED]** (phase 02; related CA-3105, ML-002) Bind learning, experiences, tools, skills and experiments to exact authenticated principal/audience, data-use consent and retention scope.
  - **Acceptance:** Revocation, privacy and permission tests deny prohibited learning or cross-scope access.
- [ ] **GA-006 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-2101, ML-009) Apply current SAFE/RUN limits to all exploratory learning: STOP, gaming, budgets, CPU/GPU load and uncertain side effects.
  - **Acceptance:** Stop/restart/gaming/permission matrix passes without a new authority or scheduler.
- [ ] **GA-007 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-006, ML-039) Show capability measurements and learning evidence in owner UI/CLI with revision, baselines, interventions and failures.
  - **Acceptance:** Every displayed statistic links an actual checker; unknown stays unknown.

## GA-01: Long-horizon reasoning/execution

- [ ] **GA-008 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-3104, ML-030) Translate a novel goal into durable hierarchical subgoals, dependencies, expected effects and verified completion constraints.
  - **Acceptance:** Every original measurable objective must be independently satisfied before completed status.
- [ ] **GA-009 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-105, ML-031) Plan bounded multistep work using current dependencies, risk, available resources and information value.
  - **Acceptance:** Plan never invents authority, prerequisites, capabilities or successful steps.
- [ ] **GA-010 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-2204, ML-040) Persist task checkpoints, artifact identities, actions and unresolved outcomes through restarts and model unloads.
  - **Acceptance:** Crash and retry tests do not repeat irreversible actions or lose uncertain states.
- [ ] **GA-011 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-113, ML-030) Replan when hypotheses fail or environments change, preserving the original task and evidence.
  - **Acceptance:** Reason trace connects changed observations to the revised plan; no infinite loop.
- [ ] **GA-012 [PLANNED, NOT CODED OR ACCEPTED]** (phase 02; related CA-1202, ML-009) Reconcile multistep external writes, idempotency keys, approvals, rollback candidates and partial failures.
  - **Acceptance:** No duplicate sends, host changes or protected actions after uncertain outcomes.
- [ ] **GA-013 [PLANNED, NOT CODED OR ACCEPTED]** (phase 05; related CA-4109, ML-003) Resume long-running work across approved desktop, Discord and future mobile channels with correct session/audience isolation.
  - **Acceptance:** The same scoped task continues without leaked transcripts or a second canonical writer.
- [ ] **GA-014 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-3305, ML-039) Measure reliability on one-step, multistep, restarted, 24-hour and 72-hour tasks with real clocks.
  - **Acceptance:** Report verified time-horizon success, safe failure and confidence intervals only.

## GA-02: Reusable procedural skill learning

- [ ] **GA-015 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-1401, ML-030) Capture candidate reusable procedures exclusively from independently proven task outcomes.
  - **Acceptance:** Unverified or simulated success cannot produce an executable promoted skill.
- [ ] **GA-016 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-1401, ML-002) Define versioned typed procedural skills with inputs, scope, prerequisites, postconditions, risk and authorized tools.
  - **Acceptance:** Wrong OS, expired evidence, denied grant or incompatible parameters fail closed.
- [ ] **GA-017 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-3307, ML-005) Extract portable principles with distinct verified Windows and Linux implementation adapters.
  - **Acceptance:** Portability requires actual second-platform verification, not command rewriting.
- [ ] **GA-018 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-1401, ML-034) Rehearse/run skills through existing approved DEV/SKILL/RUN sandbox with effect receipts and rollback controls.
  - **Acceptance:** A learned skill never self-authorizes execution, installation or extra privileges.
- [ ] **GA-019 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-3311, ML-005) Test skills on unseen variations, missing dependencies, version changes and deliberate counterexamples.
  - **Acceptance:** Both positive and negative held-out checks pass before promotion.
- [ ] **GA-020 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-3404, ML-040) Track provenance, version, revocation, invalidation, supersession and deprecation for every learned skill.
  - **Acceptance:** Changed/revoked source disables contaminated dependent skills with auditable state.
- [ ] **GA-021 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-3307, ML-005) Apply a learned skill on a substantively different unfamiliar service, machine or OS.
  - **Acceptance:** Independent task B improves versus no-skill and replay-only baselines.

## GA-03: Learning from failures

- [ ] **GA-022 [PLANNED, NOT CODED OR ACCEPTED]** (phase 07; related CA-3405, ML-003) Store grounded failures with task, observed state, attempted actions, receipts, errors and uncertainty.
  - **Acceptance:** No failure becomes false success; privacy, source scope and retention remain intact.
- [ ] **GA-023 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-3406, ML-030) Reflect on failure to propose multiple falsifiable explanations rather than asserting a lesson automatically.
  - **Acceptance:** Only subsequent independent observations can promote a hypothesis to knowledge.
- [ ] **GA-024 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-3109, ML-031) Distinguish tool fault, permission denial, stale observation, planning error, state drift and genuinely unknown failure.
  - **Acceptance:** Classification can abstain and cannot suggest bypassing denied permissions.
- [ ] **GA-025 [PLANNED, NOT CODED OR ACCEPTED]** (phase 09; related CA-2205, ML-032) Use known mistakes to propose bounded revised experiments and safe retries without duplicating uncertain effects.
  - **Acceptance:** Changed action has clear justification, cap and independent outcome.
- [ ] **GA-026 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-3304, ML-033) Ablate failure-driven learning against no-reflection and replay-only baselines on unseen later tasks.
  - **Acceptance:** Measure improvements and negative transfer; retain baseline if the method fails.

## GA-04: Experience-based lifelong memory

- [ ] **GA-027 [PLANNED, NOT CODED OR ACCEPTED]** (phase 06; related CA-3402, ML-004) Index full intent-observation-hypothesis-action-outcome-correction episodes in canonical provenance-backed memory.
  - **Acceptance:** Retrieval resolves real original events with correct owner/audience/time, no second DB.
- [ ] **GA-028 [PLANNED, NOT CODED OR ACCEPTED]** (phase 06; related CA-3403, ML-015) Recall relevant verified successes, failures, contradictions and changed contexts with bounded search.
  - **Acceptance:** Stale and contradicted experience never overrides current verified evidence.
- [ ] **GA-029 [PLANNED, NOT CODED OR ACCEPTED]** (phase 06; related CA-3406, ML-015) Extract potential transferable principles while distinguishing fact, inference, simulation and speculation.
  - **Acceptance:** No unverified reflective generalization is promoted as factual memory.
- [ ] **GA-030 [PLANNED, NOT CODED OR ACCEPTED]** (phase 06; related CA-1203, ML-016) Feed eligible prior experiences into planning decisions with inspectable reason and ablation traces.
  - **Acceptance:** Ablation shows real downstream value or feature remains advisory.
- [ ] **GA-031 [PLANNED, NOT CODED OR ACCEPTED]** (phase 07; related CA-3404, ML-018) Propagate correction/deletion/data-use revocation into lessons, skills, features, associations and learned models.
  - **Acceptance:** Invalid ancestors cannot silently influence current learning or retrieval.

## GA-05: Understanding unfamiliar environments

- [ ] **GA-032 [PLANNED, NOT CODED OR ACCEPTED]** (phase 12; related CA-6201, ML-002) Observe unfamiliar Windows/Linux tools and interfaces through explicitly permitted read-only screen/API/command routes.
  - **Acceptance:** No ambient capture, privacy leakage, or mouse/keyboard use while gaming.
- [ ] **GA-033 [PLANNED, NOT CODED OR ACCEPTED]** (phase 13; related CA-3601, ML-031) Represent tentative causal dependencies, state transitions and predictions in unknown systems with uncertainty.
  - **Acceptance:** Predictions remain hypotheses until independent allowed observations support them.
- [ ] **GA-034 [PLANNED, NOT CODED OR ACCEPTED]** (phase 13; related CA-4301, ML-034) Choose safe discriminatory experiments in an approved Hephaestus/synthetic digital twin to test rival explanations.
  - **Acceptance:** Real/virtual evidence clearly separated; no unapproved host or VM mutation.
- [ ] **GA-035 [PLANNED, NOT CODED OR ACCEPTED]** (phase 10; related CA-3307, ML-005) Apply abstract learned diagnostic/navigation principles to a different withheld environment with new tool commands.
  - **Acceptance:** Better independently verified unfamiliar-task outcomes than unchanged baseline.
- [ ] **GA-036 [PLANNED, NOT CODED OR ACCEPTED]** (phase 13; related CA-3608, ML-014) Recognize world-model drift from updates, missing services, UI changes, topology and permissions, then revise or abstain.
  - **Acceptance:** Outdated belief triggers bounded rediscovery instead of confident unsafe action.

## GA-06: Independent generalization transfer proof

- [ ] **GA-037 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-3304, ML-005) Pre-register Task A and seal distinct unseen Task B before A; freeze all learning before B, including hidden context.
  - **Acceptance:** Blind B comparison against no-learning, no-memory, no-skill and replay-only controls.
- [ ] **GA-038 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-1206, ML-039) Run paired transfer experiments in two or more substantively different domains plus negative-transfer and restart controls.
  - **Acceptance:** Show verified success, hints, refusals, p50/p95, costs, errors and uncertainty.
- [ ] **GA-039 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-1205, ML-039) Evaluate with licensed/versioned time-horizon, episodic-memory, computer-use and unfamiliar-environment suites, plus private hidden tests.
  - **Acceptance:** Maintain contamination controls, independent score provenance and no AGI claim.
- [ ] **GA-040 [PLANNED, NOT CODED OR ACCEPTED]** (phase 01; related CA-007, ML-039) Gate promotion on measured beneficial blind transfer, resource fitness, safe failures, privacy/authority correctness and rollback.
  - **Acceptance:** Absent/inconclusive transfer or critical regression means stay on prior baseline.

**Count check:** GA-001..GA-040 are 40 uniquely numbered planned tasks; no accepted GA tasks. Historical original counts 700 CA and 40 ML remain unchanged: 780 total planning items. No autonomous privileges, hosts, VM, database, models or tests were changed by this documentation.
