# G7-A evidence-boundary pin batch — 2026-11-02

Development policy: **main only**. Test-only batch plus one dated documentation addendum. No production code changed; no runtime, canonical state, or service behavior touched.

## Input evidence

The 2026-10-31 Codex takeover audit (`codex-takeover-2026-10-31.md`) predated the G7-A evidence-graph batch (commits `1d23040b`, `34e23f5e`, `c6961900`, `a7a697d1`) and the Fleet outcome-verification batch (`4b704b61`). A re-audit of current source showed several of its reported defects are repaired in code while their acceptance evidence remains open. This batch closes the smallest textual gaps in the V2 evidence, Fleet observation, and GOALS learning boundary contracts so future audits pin against executable negs.

## What was implemented

All changes are tests or a dated correction note. Retested failure scenarios only; no gates weakened.

1. **Item 74 (symbolic/evidence truth pins) — `test/test_cognition_v2_evidence.py`:**
   - `test_knowledge_retrieval_evidence_cannot_satisfy_machine_need`: a validated `knowledge.retrieval` atom satisfies only its exact knowledge need; a same-subject `machine.cpu.model` need resolves `NOT_SAMPLED` with no atoms; per-item hardware premises are absent from the ledger.
   - `test_model_forges_cannot_carry_retrieval_truth_across_keys`: replaying retrieval evidence under a machine key raises `capability evidence does not match requested key`; rebranding retrieval bytes as a hardware result raises `capability evidence source does not match result`; nothing ingested. This pins that validated acquisition is the only host-truth path and document retrieval can never be laundered into machine proof.

2. **Item 75 (perception→Core trusted bridge pins) — `test/test_cognition_v2_fleet_observation.py`:**
   - `test_observation_fact_without_source_ref_is_unconstructable`: a `CapabilityFact` without a source reference cannot exist (missing-source failure).
   - `test_supply_rejects_facts_from_other_hosts`: an inventory spanning hosts is rejected before bridge ingestion (forged host identity failure).
   - `test_fleet_observations_are_scoped_to_the_receiving_audience`: two audiences at the same Fleet node produce distinct, non-conflicting scoped atoms; each audience's resolution sees exactly its own atoms and goal-evidence records preserve the `private:<audience>` projection scope.

3. **Item 76 (learning→future decision boundary pin) — `test/test_goal_production_wiring.py`:**
   - `test_g7a_verified_learning_influence_never_writes_owner_preferences`: with the preference registry composed before the learning run, a genuinely successful influence pass (2 `ga_planning_influence` rows; planner decision changed) writes **zero** `personality_preference_revision` rows and leaves every communication-style preference unset. Learning influence is bounded to planning advice; owner preference revision remains owner-gated.

4. **Documentation correction — `codex-takeover-2026-10-31.md` addendum (2026-11-02):** records that `attest_effect` now has production callers (commit `4b704b61` and related) and that the V2 `EvidenceGraph` truth-gate consumer exists, without closing any acceptance item.

## Exact-SHA verification

SHA: `fc8ca985ed02dcc00c2d12bc00188831e57cbe6e` (base of this change, Windows disposable development state).

Focused first run before repairs reproduced 3 fixture failures (wrong payload key copy, wrong audience prefix expectation, table created lazily); after corrections:

```
python -m pytest -q test/test_cognition_v2_evidence.py test/test_cognition_v2_fleet_observation.py test/test_goal_production_wiring.py
90 passed in 72.11s
```

Broader affected suites:

```
python -m pytest -q test/test_cognition_v2_fleet_machine.py test/test_knowledge_v2.py \
  test/test_cognition_v2_cutover.py test/test_generalization_advanced.py \
  test/test_generalization_workflow.py test/test_life_project_forge.py \
  test/test_presence_cross_modal_provenance.py test/test_v18_presence_conflicts.py \
  test/test_goals_v1.py test/test_remote_mtls_transport_acceptance.py
173 passed in 292.06s
```

## Status and limitations

- These tests pin **existing** production contracts; they were not pre-existing failures. Source-code presence plus green local runs is not matching-SHA CI, not installed-wheel evidence, and not owner acceptance.
- G7-A #74/#75/#76 code roles are evidenced by these commits: the canonical graph has exactly one production consumer (`FleetMachineAnswerCoordinator`), Fleet observations are consent/enrollment-gated and audience-scoped, and verified outcome learning alters the actual GOALS decision with ablation trace and revocation while never mutating owner preferences.
- **Still open for items 75/76/78:** Presence observations remain a separate evidence plane from the V2 ledger (bridge-or-boundary decision pending owner review); no full-application single-restart continuity acceptance test exists; no app-composed multi-step GOALS dependency/blocked-branch acceptance test exists.
- Matching-SHA Windows/Debian RC CI, live Venus acceptance, revocation/restart evidence on the installed artifact (G7-A #80, #87–#89) and the remaining GO LIVE gates stay open. NO-GO remains the standing GO LIVE state.
