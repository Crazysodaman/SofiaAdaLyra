# PKG-INTERACT: finite closure gates

## Verified Windows evidence and limitations

- At `c2d27e6`, Sparks reported **80 focused tests passed** and three synthetic Qwen counterfactual pairs: `clarify` without an injected no-hugs boundary and `decline` with one, 3/3 each. This does not establish causality or real dialogue quality.
- At `d866326`, **95 focused tests passed**. At `1ab5deb`, **105 passed**, including the history-preserving bridge. At `3edb400`, the corrected tamper test passed and the focused opt-in/atomic suite passed **128/128**.
- At `62ac46e`, the first real-application/Qwen probe on temporary SQLite **failed**: `accept` decision, refusing saved reply, unblocked ordinary context builder raised after the synthetic boundary, and Windows temporary cleanup encountered an open connection.
- At `c7ad0ab`, the NEXT Windows regression run stopped at **1 failed, 36 passed**. The `test_inflight_new_boundary_withholds_candidate_reply[2-2]` stub chose `accept` but its generic expression never accepted, so the new consistency veto raised before the test's boundary result. Sparks correctly stopped the regression gate. The separate disposable real-Qwen probe was run despite that stop: it **passed its isolation, boundary block, no-extra-model-call and cleanup assertions**, but Qwen selected `clarify` and produced a de facto decline plus generic `How can I assist you instead?` redirect. The expression audit flagged `generic-assistant-redirect`. **Do not report the combined checkpoint or conversational-quality gate as passed.**

## Latest feature fixes AFTER the above Windows run, UNVERIFIED

- `test/test_interaction_trusted_offer_gate.py` now supplies choice-matched stub expressions. Its in-flight boundary test can reach the intended assertion; an additional regression covers a contradictory expression arriving simultaneously with a newly attested boundary.
- `trusted_offer_gate.py` checks source-backed boundary/stop **immediately after expression inference, before the lexical expression veto**. An active verified block wins, and no model draft is released. A clear state still vetoes overtly contradictory replies.
- `expression_consistency.py` rejects a `clarify` expression that explicitly refuses, generically redirects or lacks an offer-related question. `conversation_offer_context.py` provides choice-specific guidance to ask a natural question *about the offer*, without forcing acceptance or writing a canned reply. `test/test_interaction_clarify_quality_regression.py` captures the exact observed Qwen redirect. These are conservative lexical checks, NOT general semantic verification or proof of subjective feeling or consent.
- No production data, installed provider settings, actual contact, animation, or permission is changed by these feature-branch commits. The exact reviewed phrase `I ask to hug you` remains opt-in only. Other phrasings, including `Could I hug you?`, are NOT supported by this staged route yet.

## Next supervised Windows checkpoint

With normal Sofía closed, `.venv` active, checked `feature/pkg-interact-shared-engine`, and unrelated `git status --short` changes preserved, fast-forward pull. First run the targeted regression and focused suite:

```powershell
python -m pytest -q -x `
    test/test_interaction_trusted_offer_gate.py::test_inflight_new_boundary_withholds_candidate_reply `
    test/test_interaction_trusted_offer_gate.py::test_inflight_boundary_overrides_invalid_expression_without_releasing_it `
    test/test_interaction_clarify_quality_regression.py `
    test/test_interaction_expression_consistency.py `
    test/test_interaction_opt_in_live_offer.py `
    test/test_interaction_atomic_offer_release.py `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_conversation_offer_context.py `
    test/test_interaction_expanded_service.py `
    test/test_application.py
if ($LASTEXITCODE -ne 0) { throw 'Regression failed. Do not run Qwen.' }
python -m sofia.interaction.disposable_live_offer_probe --run-disposable
```

Stop at the first failed test and inspect the traceback; do not treat a later separate probe as curing a failing suite. The probe may correctly veto a bad Qwen reply: this demonstrates containment **only**, not satisfactory interaction quality. Review raw decisions/replies and the saved records. Never use the modified production `state/sofia.db`, enable the opt-in globally, or provision real attestation schema as part of a test.

## Definition of done

- [x] Exploratory counterfactual and synthetic source-attested guarded route.
- [x] Stub-based opt-in and atomic reply tests verified at `3edb400`.
- [ ] **Fix and verify the regressions and grounded real-Qwen expression.** Pass the focused suite and isolated live probe; human-review *natural, choice-consistent* output. A veto alone cannot satisfy quality.
- [ ] **Natural phrasing and clarification:** review alternative hug offers; route only trusted grammar; abstain on ambiguity; keep actual-world questions distinct.
- [ ] **Broad regressions and safety:** full test suite, concurrent SQLite writer order, restart/replay, source attestation, privacy/tool authorization, CORE/SAFE and optional schema/migration and PR conflict review.
- [ ] **Explicit approval:** Sparks accepts PKG-INTERACT and separately approves any merge. PR #2 remains draft, unmerged, and `main` unchanged.

Discord, 24/7 operation, actual avatar animation and physical sensors are separate packages. Preserve Sparks's modified production database, timestamped backup, independent local Ollama test edit, other PRs and model settings.
