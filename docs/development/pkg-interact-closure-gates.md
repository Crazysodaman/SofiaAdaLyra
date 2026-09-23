# PKG-INTERACT: finite closure gates

## Verified Windows evidence

- Earlier exploratory Qwen counterfactual at `c2d27e6`: three `clarify` choices without a synthetic boundary and three `decline` choices with one. Not a causality proof. Isolated focused tests were **80 passed** at `c2d27e6`, **95 passed** at `d866326`, and **105 passed** at `1ab5deb`.
- At `3edb400`, Sparks reported **128 focused tests passed** after correcting a tampered-fixture test helper. At `62ac46e`, the first disposable real-Qwen probe **failed**: choice `accept` versus refusal in the saved text, preblocked context-builder exception, and Windows temporary SQLite cleanup failure.
- At `c7ad0ab`, the focused suite stopped at **1 failed, 36 passed** due to a stale accept-stub response. A separately run disposable probe blocked the synthetic boundary and cleaned up, but Qwen's `clarify` yielded a generic redirect. At `be612c4`, the suite stopped at **1 failed, 38 passed** due to a stale clarify-stub response. Its separately run Qwen sample asked a relevant hug question; the advisory completed-contact detector falsely flagged `hug you're`.
- **Latest verified checkpoint at `f126521`:** Sparks reported the targeted atomic-release test **1 passed**, then the focused suite **67 passed in 80.95 seconds**. The disposable real-application Qwen probe completed with `clarify` and an on-topic question about a virtual embrace versus the offer's meaning; heuristic flags were empty. The synthetic source-attested no-hugs boundary blocked the next identical offer without more Qwen calls. Windows temporary database cleanup succeeded. This confirms the specific supervised run, not broad model reliability.

## New feature code AFTER `f126521`, NOT YET VERIFIED ON WINDOWS

- `reviewed_hug_question.py` recognizes only exact reviewed questions (`Could/Can/May I hug you?` and `Could/Can/May I give you a hug?`, case-insensitive). This is intentionally separate from `action_grammar.py`: a question is ambiguous about avatar versus real contact, not a performed action or consent. Hypothetical, compound, sensor and other unreviewed text remain on the original service.
- `question_clarification_service.py` persists the exact saved user question and a limited disambiguation reply **without LLM calls**, applying source-attested boundary/stop checks before the final transaction. `atomic_offer_release.py` validates that question releases can contain only the fixed clarification, never an injected accept/decline. The original `I ask to hug you` staged real-Qwen route is unchanged and remains disabled by default.
- Stub/disposable tests cover normal default-off behavior, the narrow question classifier, explicit abstentions, saved turns, policy stops and verified boundaries, injected invalid question choices, and one deterministic two-connection SQLite stop-before-reply writer ordering. The supervised disposable real-application probe now adds unblocked and synthetic-boundary-blocked questions with **zero additional Qwen calls**. New code is **not** production-enabled or Windows-tested.
- All interaction schema initialization remains confined to disposable tests. Do NOT run or migrate the modified production `state/sofia.db`, insert synthetic preference records into real sessions, or enable `SOFIA_INTERACT_STAGED_OFFERS` globally. Preserve the backup, local Ollama test edit, provider settings, `main`, CORE PR #1 and RUN PR #3.

## Immediate Windows checkpoint (in order)

With normal Sofía closed, `.venv` active, `feature/pkg-interact-shared-engine` selected, existing local changes inspected and fast-forward pull complete:

```powershell
python -m pytest -q -x `
    test/test_interaction_reviewed_hug_question.py `
    test/test_interaction_atomic_offer_writer_order.py `
    test/test_interaction_opt_in_live_offer.py `
    test/test_interaction_atomic_offer_release.py `
    test/test_interaction_completed_offer_audit.py `
    test/test_interaction_clarify_quality_regression.py `
    test/test_interaction_expression_consistency.py `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_conversation_offer_context.py `
    test/test_interaction_expanded_service.py `
    test/test_application.py
if ($LASTEXITCODE -ne 0) { throw 'Focused regression failed. Do not run Qwen.' }

python -m sofia.interaction.disposable_live_offer_probe --run-disposable
if ($LASTEXITCODE -ne 0) { throw 'Disposable probe failed. Stop.' }
```

Stop on the first failure. Do not count a separate probe as a cure for a red regression suite. A probe may veto a bad candidate: that shows containment, **not** good conversational quality. Read the raw Qwen text and inspect saved-message assertions. No external action, animation or real sensing should occur.

## Definition of done

- [x] Exploratory counterfactual, source-attested boundary model and atomic opt-in service on stubbed/disposable state.
- [x] One verified focused **67-pass** Windows checkpoint and supervised real-Qwen declarative-offer run with a natural clarification and effective synthetic boundary.
- [ ] **Verify new narrow question route and writer-order regression:** focused tests and four-turn disposable real-application probe; human-review first Qwen answer. Do not treat a deterministic clarification as general conversational coverage.
- [ ] **Broad regressions and security:** full `python -m pytest -q` plus selected CORE/SAFE/privacy/authorization, alternate writer order, restart/replay, source attestation and optional-schema/migration checks. Inspect and reconcile PR #2 against `main`, including base conflicts, before acceptance.
- [ ] **Explicit approval:** Sparks accepts PKG-INTERACT and separately authorizes any merge. PR #2 stays draft/unmerged; `main` unchanged until then.

Discord/PKG-NET, 24/7 operation, real avatar animation and physical sensors are separate packages. This package covers bounded represented-world text interaction and its guards, not general animation or physical embodiment.
