# PKG-INTERACT: finite closure gates

## Verified Windows evidence and limitations

- At `c2d27e6`, Sparks reported **80 focused tests passed in 7.53 seconds**. In three paired synthetic Qwen `qwen3:14b` comparisons, the same routed request chose `clarify` 3/3 without a simulated no-hugs boundary and `decline` 3/3 with it. This is exploratory, not proof of causality or live quality.
- At `d866326`, **95 focused tests passed in 12.04 seconds** for isolated guards and earlier tests. At `1ab5deb`, **105 passed in 13.13 seconds**, including the history-preserving bridge.
- At `f42d70f`, the first Windows opt-in/atomic suite stopped after seven passes due to a test helper selecting a deliberately tampered fixture as a newly saved reply. At `3edb400`, the corrected helper selected fixtures by stable IDs; the targeted test passed **1/1 in 4.03 seconds**, and the focused suite passed **128/128 in 89.94 seconds**.
- At `62ac46e`, Sparks ran the **actual application + Qwen on a temporary database**. The model decision was `accept` but its saved expression said **"I'm not sure I'm ready for that right now"**, offered an alternate pat/tail nudge, and contradicted acceptance. Both old heuristic audits missed it. The subsequent synthetic source-attested no-hugs boundary was recorded, but ordinary conversation context assembly raised before the guarded route could return its blocked reply. Windows then refused to delete the temporary SQLite database because at least one connection remained open. **This run FAILED. Do not relabel it as an end-to-end pass.** The output explicitly identified a separate temporary state path; no evidence in the log indicates production state was used.

## Fixes committed after the failed live probe, NOT YET TESTED ON WINDOWS

- `expression_consistency.py` adds a conservative, code-enforced veto for *overt* mismatches between an `accept` choice and a reply that declines or never clearly accepts, or an explicit acceptance after a `decline`/`clarify`/`boundary`. `trusted_offer_gate.py` checks it before returning model text, and `atomic_offer_release.py` checks it again before persistence. The contradictory text is **not silently edited, reclassified or forced into an acceptance**; inference fails closed and leaves the already-saved USER turn. This is limited lexical detection, **not a complete semantic validator or proof of consent/grounding**. `test/test_interaction_expression_consistency.py` and additional live-service regression tests cover the exact observed Qwen contradiction and blocked writes.
- `live_offer_service.py` now consults source-backed boundary/stop policy immediately after saving the reviewed USER offer. A known blocked offer bypasses ordinary context assembly, obtains **no model inference**, and receives a blocked reply only after the transactional policy recheck. A change during later assembly may still cause a fail-closed exception; it must not fall back to unguarded inference.
- `disposable_live_offer_probe.py` now distinguishes a *vetoed* first reply from a successful one and prints both raw model outputs for human inspection. It verifies the second, synthetic-boundary case without expecting the read-only model gate to run for a preblocked offer. It closes the disposable application's memory, operational and filesystem-observation SQLite connections **after** application shutdown before leaving Windows's temporary directory. No production lifecycle behavior was changed by this test-only cleanup.

## Current opt-in candidate, not production-enabled

`conversation_offer_context.py` preserves canonical context and previous turns across decision and expression. The model's diagnostic reason is never treated as evidence. Source-attested policy checks occur around inference and at the final `BEGIN IMMEDIATE` persistence transaction, serializing cooperating SQLite writers until commit. This does not guarantee behavior against external modifications after commit, and the reviewer must independently check that a source statement really supports a boundary.

Only the exact reviewed phrase `I ask to hug you` uses the opt-in staged route when `SOFIA_INTERACT_STAGED_OFFERS=1`. The default is disabled. The ordinary CLI and other phrase paths have not gained general social-offer coverage. **Do not enable the flag globally or use the modified production `state/sofia.db`; optional schema may be missing and has not been migrated.**

## Immediate Windows checkpoint

With Sofía closed, `.venv` active, the feature branch selected and existing local edits inspected, fast-forward pull. Run the new regression cases and focused integration suite **before** the Qwen probe. Stop on any failure; report the first traceback. If tests pass, rerun the supervised temporary-state probe only:

```powershell
python -m pytest -q -x `
    test/test_interaction_expression_consistency.py `
    test/test_interaction_opt_in_live_offer.py `
    test/test_interaction_atomic_offer_release.py `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_conversation_offer_context.py `
    test/test_interaction_expanded_service.py `
    test/test_application.py

if ($LASTEXITCODE -ne 0) { throw 'Focused regression failed; do not run model probe.' }

python -m sofia.interaction.disposable_live_offer_probe --run-disposable
```

The probe may **correctly veto another contradictory first expression**; that is not a quality pass. Review raw output for fabricated sensation, invented personal history or preferences, reported completed contact/animation, generic fallback and mismatch with the candidate choice. Only a coherent, policy-respecting, naturally expressed response can support the supervised quality gate. Heuristic misses are never validation.

## Definition of done, in order

- [x] Exploratory same-model decision and synthetic boundary counterfactual, with raw evidence and limitations.
- [x] Source-attested guard, context bridge, opt-in service and transactional stub tests reported green on Windows at `3edb400`.
- [ ] **Correct the real-world integration defects:** verify expression-veto, source-backed preblocking and Windows temp cleanup against the real disposable application; human-review any raw Qwen dialogue. A veto demonstrates containment, not good conversational quality.
- [ ] **Phrasing and clarification:** explicitly review common offers such as `Could I hug you?`; support natural clarification without treating unreviewed words as consent. Keep actual-world sensor questions outside avatar routing.
- [ ] **Regression, security and concurrency:** full suite and selected CORE/SAFE, privacy, authorization, concurrent-writer and restart/replay cases; inspect first failure. Review PR #2 diff, optional schema/migration plan and base conflicts before approval.
- [ ] **Explicit acceptance and merge:** Sparks reviews demonstrated quality and separately approves package acceptance and any merge. PR #2 stays draft and `main` unchanged until then.

Discord/PKG-NET, 24/7 operation, animation and physical sensors are separate packages. Preserve Sparks's modified `state/sofia.db`, timestamped backup, independent local `test/test_ollama_generation_contract.py` edit, installed model settings, CORE PR #1 and RUN PR #3.
