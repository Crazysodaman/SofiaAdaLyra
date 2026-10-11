# Sofía V18: 700-task source audit and remaining-work truth
**Date:** 2026-10-11  **Base GitHub main:** `1925361e1362520c11980987167a410a6635deb0`  **Method:** read-only static source/tree and original task-by-task metadata; no tests, CI, deployment or live-host exercise.
**Authority:** original unchanged 700-ID, 17-phase V18 master. Evidence ledger is not an implementation oracle.

## Strict production-wiring interpretation (owner requirement)

**Coding-complete means fully wired into the real production path, with only tests/CI/live evidence left.** A partial implementation, dormant module, unused adapter, test fixture, research contract or uncalled helper is **NOT coded-complete**, regardless of code volume. The [enforced production-wiring standard](v18-production-wiring-gate-2026-10-11.md) now requires an explicit application/CI entrypoint, actual composition, calling path, implementation, side-effect/output path and exact reviewed revision before any `code_present_unverified` label is allowed.

**The six code-present tasks** have source-traced candidate production paths but are not tested or deployed. **All 63 partial tasks are coding-incomplete under this stricter definition.** Their existence is not counted as finished implementation. The 631 unassessed tasks are genuinely unknown and must not be called placeholders simply because they have not been traced.

**Progress reporting must not infer an overall coding-done percentage from the 6/63/631 counts.** The 6 are fully-wired source candidates, not accepted; the remaining 694 are a mixture of unfinished, unknown and research/verification requirements, not a validated list of 694 missing features.

## What the numbers MEAN

- **700 / 700** original stable IDs and phases reconciled to the GitHub ledger. This is **inventory coverage**, not full semantic implementation inspection.
- **6** tasks have individually traced source coded in the ledger, **unverified**.
- **63** tasks have individually traced *some* production code, but task scope remains partial or acceptance proof missing.
- **631** tasks have **insufficient task-specific source tracing**. They are NOT automatically missing code. A repository inventory cannot turn them into "uncoded."
- **0 / 700** tasks production-accepted under the ledger's exact-SHA test and relevant live-host gate.
- **69 / 700 = 9.9%** now have an **individual source-status classification**. This is an **audit progress** percentage only, never a percent of remaining coding.
- **No defensible exact "% coding left" yet**: incomplete tasks may require only test evidence, extensive implementation, research, or a human decision. Treating all unchecked original boxes as missing code is wrong.

## Original roadmap is not 700 equivalent coding tickets

The original task-label distribution is **397** labeled design/research, **112** labeled verify, **110** labeled gap and **81** mixed/other labels, covering all 700. Labels describe their original intent and do not prove a task is implemented or unimplemented. Phase 13 uses many specialist labels (INFRA, NETWORK, WIRING, etc.); they are counted as mixed, not automatically complete.

**Priority coding-triage subset:** Of the **110** original tasks explicitly labeled `[GAP]`, **3** have traced code-present/unverified, **12** have partial source evidence, and **95** still need task-specific code inspection. Those 95 are *not* established as absent implementations. This is a practical review queue, not a count of required new modules.


## Source-backed status by execution-priority phase

| Phase | Area | Original tasks | Code-present (not verified) | Partial | Still needs task-specific inspection |
|---|---|---:|---:|---:|---:|
| 00 | Architecture/owners | 65 | 0 | 5 | 60 |
| 01 | CI/release/acceptance | 66 | 4 | 8 | 54 |
| 02 | SAFE/operator | 30 | 0 | 1 | 29 |
| 03 | State/recovery | 46 | 0 | 6 | 40 |
| 04 | Offline/survival | 22 | 0 | 7 | 15 |
| 05 | Lifelong Main | 41 | 0 | 16 | 25 |
| 06 | MEM | 73 | 0 | 2 | 71 |
| 07 | Archive/forgetting | 26 | 0 | 1 | 25 |
| 08 | Emotion/presence | 56 | 0 | 0 | 56 |
| 09 | LIFE/GOALS/creative | 66 | 2 | 8 | 56 |
| 10 | Skills/integrations | 27 | 0 | 3 | 24 |
| 11 | Models/resources | 49 | 0 | 1 | 48 |
| 12 | Vision | 24 | 0 | 1 | 23 |
| 13 | Hephaestus/VM | 63 | 0 | 0 | 63 |
| 14 | Model adaptation | 12 | 0 | 1 | 11 |
| 15 | NEURO/connectome | 22 | 0 | 1 | 21 |
| 16 | Consciousness research | 12 | 0 | 2 | 10 |
| **Total** | | **700** | **6** | **63** | **631** |

## Reconciled work since previous evidence checkpoint

The ledger had last recorded `2c3b27b` despite later production commits. These commits are present at audited head:
- `40751acf`: hardened canonical SQLite ownership; affects CA-5201/6101/6804 and SAFE/RUN cross-cuts. Does **not** establish approved cross-host writer/failover.
- `c3e48096`: repaired canonical-state test fixtures. Test code present, not run.
- `7e506aab`: LIFE experience-to-interest learning, persistent idempotent consume, and new test cases; affects CA-101/104. Its v1 signal is explicitly limited to reviewed LIFE artifact evaluations, not all ordinary observations.
- `1925361e`: authenticated canonical turn admission/settlement and source-facing conversation sequencing; affects CA-4106/4110/5302/5306/5505. No cross-device Android/Discord/desktop live race test was run.
- **Codex jobs 1–4: source commits present. Job 5: no dedicated completion commit at the audited head.** Existing LIFE objective checks/revisions are substantial but the end-to-end lifecycle and milestone/uncertain-action recovery are not source-proved complete.
- Earlier direct-main SAFE, LIFE, GOALS, Main, Presence state-loss hardening commits remain present.
All above jobs remain **unaccepted** because tests were deferred at the owner's request.

## Newly traced **partial** evidence (not claims of task completion)

| Stable ID | Observed source slice and missing boundary |
|---|---|
| CA-006 | Read-only CompanionDecisionTrace projection exists, not proved complete for every causal winner/consumer. |
| CA-1203 | Provider token budgets exist; complete per-context source allocation/quality behavior is not proved. |
| CA-3103 | StatePlane replication witness and encrypted backup exist, but do not replicate every direct SQLite owner or authorize host failover. |
| CA-3109 | Observed/inferred source receipts exist in Presence and cognition; not universal evidence propagation. |
| CA-3302 | V18 provenance verifier and 700-entry ledger exist; many tasks still lack individual source tracing. |
| CA-3501 | Independent typed artifact rules exist; not a trusted success oracle for every activity type. |
| CA-4903 | Encrypted archival segments exist; no verified cross-tier canonical 50-year catalog/lifecycle. |
| CA-5801 | Preserved original/archive and independent promoted-memory owners exist; full retention/consent coverage unproved. |
| CA-6201 | Screen permit/receipt types exist; Windows/Terra capture and four real user journeys not proved. |
| CA-6404 | SQLite online backup and recovery staging exist; consistent live-data all-asset recovery not proved. |
| CA-6307 | Stable identity and authenticated state home exist; full multi-provider identity continuity test is pending. |
| CA-6701 | Adaptation classification policy exists; owner-facing training classification/UX not proved. |
| CA-6801 | Read-only state location/pointer inventory and preflight exist; full host path inventory and operator move not proved. |
| CA-701 | Selected connectome motifs and NEURO runtime exist; production invariant proof/benchmarks still pending. |
| CA-801 | Consciousness-research protocol validation exists; experimental hypotheses/controls and outcomes not validated. |
| CA-802 | Operational self-model exists; goal/evidence continuity completeness unproved. |
| CA-1004 | Read-only Home Assistant integration adapter exists; eligible Presence/LIFE/NEURO wiring not proved. |
| CA-1006 | Portainer container/log adapter exists; protected evidence/diagnostic-to-LIFE/DEV path not proved. |
| CA-1401 | Typed procedural skill candidate/review exists; canonical governed versioned executable catalog not proved. |

## Confirmed scope still requiring coding or explicit production proof

1. **Phase 09 / Codex Job 5:** LIFE's source has independent artifact objective inspection, explicit bounded revisions and a completion path, but the entire `CREATE → VERIFY → CRITIQUE → REVISE | COMPLETE | PAUSE | ABANDON` lifecycle, milestone advancement and GOALS/RUN uncertain outcomes still need a source-complete reconciliation against CA-105/106/110/112/113/3014.
2. **Phase 03:** `src/sofia/ops/state_mobility.py` declares itself *read-only preflight* and its `ready_for_automatic_cutover` property is false. A privileged fenced move, verified promotion/failback and active writer-host decision are **not** present by implication. Owner has deliberately **not** selected Venus or Artemis.
3. **Phase 12:** `src/sofia/vision/consent.py` explicitly says it contains **no background screen capture or mouse/keyboard execution**. Actual OS picker/approved capture and receiver flows require development and host evidence.
4. **Phase 14:** `src/sofia/evolve/training_policy.py` calls itself **research-only manifests; no training or self-deployment**. It is not proof of autonomous LoRA training or model creation.
5. **Phase 15:** selected connectome circuit motifs are documented as research hypotheses and not a fly-brain simulation. Actual scientific ablation and production impact remain unproven.
6. **Phase 16:** a research protocol validator exists; it does not demonstrate consciousness or completed experiments.
7. **Phase 01:** current revision's release-wheel parity, Windows cleanup, package suites, Android build and multi-host tests are deferred. Do not describe source-written tests as passed.

## Concrete next work and how to update progress

- Finish and audit Codex Job 5 before marking further LIFE requirements source-complete.
- Continue per-ID semantic source inspection of the **631** entries, linking actual callers, guards, durability, audience, tests and production paths, and use `partial_wiring` or `code_present_unverified` only when individually evidenced.
- Separate **needs-new-code**, **needs-decision/research**, and **coded-needs-verification** in later passes. Only then calculate a credible coding-done/coding-left fraction.
- After deferred exact-head focused/full CI and relevant Venus/Artemis/Android tests, evaluate production acceptance separately. Never flip `accepted` from source presence.

**Repository scope:** 17 phases, 69 source topics, 700 stable tasks. This audit did **not** silently rewrite the original V18 checklist, select an authoritative host, move `sofia.db`, or execute tests.
