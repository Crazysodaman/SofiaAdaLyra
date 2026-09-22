# PKG-INTERACT: finite closure gates

## Verified Windows evidence and limitations

- At `c2d27e6`, Sparks reported **80 focused tests passed in 7.53 seconds**. In three paired synthetic Qwen `qwen3:14b` comparisons, the same routed request chose `clarify` 3/3 without a simulated no-hugs boundary and `decline` 3/3 with it. These are exploratory, not a causality or live-quality proof.
- At `d866326`, **95 focused tests passed in 12.04 seconds** for isolated source-checked guards and earlier tests. At `1ab5deb`, **105 passed in 13.13 seconds** including the history-preserving context bridge.
- At `f42d70f`, the first Windows opt-in/atomic suite stopped after 7 passes: a tampered fixture's text changed and a test helper selected it as a newly saved reply. At `3edb400`, the corrected helper selects fixture messages by **stable IDs**, and Sparks reported the targeted test **1 passed in 4.03 seconds** and the full focused suite **128 passed in 89.94 seconds**. This resolves that test false positive; it does not validate real Qwen dialogue or production schema.

## Current opt-in candidate, not production-enabled

- `conversation_offer_context.py` preserves host-reviewed canonical context and prior dialogue for decision and expression; the diagnostic model-written reason never becomes expression evidence.
- `trusted_offer_gate.py` uses existing source attestation and stop state before decision, before expression and before returning text; unverified revisions fail closed.
- `atomic_offer_release.py` matches saved USER message ID/session/text and validates the choice. It checks policy and saves the assistant reply under one SQLite `BEGIN IMMEDIATE` transaction. This serializes *cooperating SQLite writers until commit*, not external actions or policy changes afterwards. It never writes consent or performs contact.
- `live_offer_service.py` and `opt_in_service.py` use actual application context and configured `qwen3:14b`, but only for **exactly** `I ask to hug you` when `SOFIA_INTERACT_STAGED_OFFERS=1`. The default CLI remains unchanged; the opt-in must NOT be globally enabled or pointed at production yet. Other phrases, including `Could I hug you?`, still use the existing conversation service.
- Windows has verified the focused opt-in tests on stubs and disposable SQLite. **No real Qwen run or full regression has yet been reported for this integrated candidate.** The real database may not have the optional source-attestation tables. Its schema must never be silently provisioned as part of a probe.

## Immediate supervised real-model gate

`src/sofia/interaction/disposable_live_offer_probe.py` and [the companion gate document](pkg-interact-disposable-live-offer-gate.md) were committed **after** the 128-test Windows result. They have not been executed or validated on the Windows machine. The probe explicitly requires `--run-disposable` and creates a temporary app state/database and filesystem root, using the actual configuration's Qwen settings without opening the production DB. Within its own process it enables the exact-phrase route, shows raw candidate choice, diagnostic reasons, flags and saved expression, then adds a **synthetic, source-attested** no-hugs statement in that temporary DB and checks that the next offer is blocked with zero additional model calls. A green probe status is not human quality acceptance.

Run only after feature-branch fast-forward, Sofía shutdown and `.venv` activation:

```powershell
python -m sofia.interaction.disposable_live_offer_probe --run-disposable
```

If a traceback occurs, stop and inspect it; never switch to `state/sofia.db`, enable the opt-in globally, or insert synthetic evidence in real sessions. Review the raw natural-language response for invented physical sensation, prior history, stable preferences, completed contact/animation, repetitive generic redirection and choices that do not match the spoken reply. Heuristic flag misses are NOT validation.

## Definition of done, in order

- [x] Exploratory same-model decision contrast and synthetic counterfactual, with raw evidence and stated limitations.
- [x] Isolated source-attested guard, conversation-context bridge, opt-in service and transactional reply tests verified on Windows with disposable SQLite and stub LLMs.
- [ ] **Supervised real application/Qwen gate:** run and human-review the new disposable probe's raw dialogue and guard behavior. Fix real defects, without modifying production state.
- [ ] **Phrasing and clarification:** explicitly review common offers such as `Could I hug you?`, support natural clarification without treating unreviewed words as consent. Keep actual-world sensor queries outside avatar routing.
- [ ] **Regression, security and concurrency:** full suite and selected CORE/SAFE, privacy, authorization, concurrent-writer and restart/replay cases; inspect first failure rather than treating partial pass as success. Review PR #2 diff, optional schema/migration plan and base conflicts before approval.
- [ ] **Explicit acceptance and merge:** Sparks reviews the demonstrated conversational quality and explicitly approves the package and any merge. PR #2 stays draft and `main` unchanged until then.

Discord/PKG-NET, 24/7 operation, actual avatar animation and physical sensors are separate packages. Preserve Sparks's modified `state/sofia.db`, timestamped backup, local `test/test_ollama_generation_contract.py` edit, installed model and its settings, CORE PR #1 and RUN PR #3.
