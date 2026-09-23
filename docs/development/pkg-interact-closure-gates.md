# PKG-INTERACT: finite closure gates

## Verified Windows evidence and limitations

- At `c2d27e6`, Sparks reported **80 focused tests passed** and three synthetic Qwen counterfactual pairs: `clarify` without an injected no-hugs boundary and `decline` with one, 3/3 each. This does not establish causality or live dialogue quality.
- At `d866326`, **95 focused tests passed**. At `1ab5deb`, **105 passed**, including the history-preserving bridge. At `3edb400`, the corrected tamper test passed and the focused opt-in/atomic suite passed **128/128**.
- At `62ac46e`, the first real-application/Qwen probe on temporary SQLite **failed**: an `accept` decision yielded a refusing saved reply, the ordinary request builder raised on the synthetic boundary, and Windows temporary cleanup encountered a still-open connection.
- At `c7ad0ab`, the next Windows suite stopped at **1 failed, 36 passed**: a stub chose `accept` but returned non-accepting prose. Separately, the disposable probe passed boundary blocking and cleanup, but real Qwen chose `clarify` and issued a generic decline/redirect. These were **not** combined checkpoint passes.
- At `be612c4`, Sparks fast-forwarded, preserving the three existing local changes. The focused suite stopped at **1 failed, 38 passed**: the atomic-release fixture chose `clarify` but its placeholder `A natural model reply.` did not ask about the offer and was correctly vetoed. The user ran the disposable Qwen probe separately: the choice was `clarify`; the saved reply naturally asked what kind of hug the user meant; a synthetic source-attested no-hugs boundary blocked a second offer with no extra model calls; Windows temporary cleanup succeeded. **Disposable plumbing passed, while the focused regression suite did not.** The completed-contact advisory audit flagged the phrase `hug you're`, a false positive, not evidence that a hug occurred.

## Latest feature-branch fixes AFTER `be612c4`, NOT YET WINDOWS VERIFIED

- `test/test_interaction_atomic_offer_release.py` replaces the stale placeholder with a real, offer-related clarification. Its persistence, boundary, stop and rollback assertions continue to test the same transactional behavior. This is a fixture correction, NOT a bypass of the clarification veto.
- `decision_expression.py` narrows the diagnostic completed-hug pattern so the fragment `hug you're` / `hug you’re` no longer looks like `hug you`. Added `test/test_interaction_completed_offer_audit.py` with the exact observed Qwen reply, contraction variants and positive tests for explicit narrated contact. The remaining diagnostic rules are advisory and can still be wrong.
- Earlier fixes remain: the guarded route checks source-backed policy before ordinary request assembly, immediately after expression inference, and under the final `BEGIN IMMEDIATE` reply transaction. An overt choice/expression contradiction or a `clarify` that declines or redirects is withheld, not rewritten into a yes. The disposable-only probe closes the app-owned SQLite connections on Windows. Only exact `I ask to hug you` is opt-in with `SOFIA_INTERACT_STAGED_OFFERS=1`; normal CLI remains off.
- No production data, provider settings, actual contact, animation or permissions are changed by the feature-branch fixes. Do not assume missing optional tables can safely be provisioned in the modified production database.

## Next supervised Windows checkpoint

With normal Sofía closed, `.venv` active, the feature branch checked, and pre-existing local changes preserved, fast-forward pull. First run the formerly failing atomic test, then the full focused suite. **Run the disposable model probe only if tests pass.**

```powershell
python -m pytest -q -x test/test_interaction_atomic_offer_release.py::test_clear_policy_persists_exact_candidate_and_updates_session
if ($LASTEXITCODE -ne 0) { throw 'Atomic fixture regression failed. Stop.' }

python -m pytest -q -x `
    test/test_interaction_completed_offer_audit.py `
    test/test_interaction_clarify_quality_regression.py `
    test/test_interaction_expression_consistency.py `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_opt_in_live_offer.py `
    test/test_interaction_atomic_offer_release.py `
    test/test_interaction_conversation_offer_context.py `
    test/test_interaction_expanded_service.py `
    test/test_application.py
if ($LASTEXITCODE -ne 0) { throw 'Focused regression failed. Do not run Qwen.' }

python -m sofia.interaction.disposable_live_offer_probe --run-disposable
if ($LASTEXITCODE -ne 0) { throw 'Disposable probe failed. Stop.' }
```

A green automated probe is not a substitute for human reading of the raw response. A veto demonstrates containment, not conversational quality. Stop at the first failure; do not treat a later separate probe as curing a red suite. Never use `state/sofia.db`, enable the opt-in globally or insert synthetic preferences into production.

## Definition of done

- [x] Exploratory counterfactual and synthetic source-attested guarded route.
- [x] Stub-based opt-in and atomic reply tests reported green at `3edb400`; later additions still need their own verification.
- [ ] **Verify latest regression fixes and grounded real-Qwen expression.** Pass focused tests and isolated live probe; inspect natural, choice-consistent, non-fabricated text. A veto alone is not enough.
- [ ] **Natural phrasing and clarification:** review alternative hug offers such as `Could I hug you?`; route only trusted grammar and abstain on ambiguity; keep real-world sensor questions distinct.
- [ ] **Broad regressions and safety:** full suite, concurrent SQLite writer order, restart/replay, source attestation, privacy/tool authorization, CORE/SAFE, optional schema/migration and PR conflict review.
- [ ] **Explicit approval:** Sparks accepts PKG-INTERACT and separately approves any merge. PR #2 stays draft, unmerged, and `main` unchanged.

Discord, 24/7 operation, real avatar animation and physical sensors are separate packages. Preserve the modified production database, timestamped backup, independent local Ollama test edit, other PRs and installed model settings.
