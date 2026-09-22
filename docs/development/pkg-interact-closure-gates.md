# PKG-INTERACT: finite closure gates

## Verified Windows evidence and limits

- At `c2d27e6`, Sparks reported **80 focused tests passed in 7.53 seconds**. In three synthetic, counterbalanced Qwen `qwen3:14b` pairs using the same routed choice request: without a synthetic boundary, `clarify` 3/3; with a simulated no-hugs statement, `decline` 3/3. No physical-impossibility premise appeared in those six reasons, but several declines did not explicitly cite the boundary. These are exploratory observations, not proof of causality or live reliability.
- At `d866326`, Sparks reported **95 focused tests passed in 12.04 seconds**, including the source-attested, read-only guarded-offer tests using stub providers and disposable SQLite.
- At `1ab5deb`, Sparks reported **105 focused tests passed in 13.13 seconds**, including the conversation-context bridge and existing expanded-service tests. The fast-forward checkout still showed the preexisting modified `state/sofia.db`, independent local Ollama test edit, and timestamped backup. Do not treat any of these tests as real Qwen quality validation.

## Current feature-branch candidate: opt-in staged live route, NOT released

The isolated `conversation_offer_context.py` bridge preserves the original conversation history and canonical self-state in both decision and expression; only the checked choice, never the model-written diagnostic reason, reaches expression. The source-checked `trusted_offer_gate.py` checks the existing boundary records and session stop before decision, after decision and after expression. Existing source attestations link explicit assistant/user statements to reviewed revisions; this is not a natural-language preference detector or proof that every saved statement is semantically correct.

New since Windows head `1ab5deb`, **UNTESTED on Sparks's Windows machine**:

- `atomic_offer_release.py` matches the exact saved USER offer, canonical host IDs and parsed choice. Under SQLite `BEGIN IMMEDIATE`, it rechecks policy and inserts the assistant reply in the same transaction. A concurrent boundary or stop can replace an in-flight candidate with a limited, truthful blocked reply. Missing/tampered evidence fails closed. This serializes cooperating SQLite writers until commit. It does not grant consent, claim performed action, or prevent a new policy change *after* commit.
- `live_offer_service.py` uses the normal application-owned conversation store, same configured `qwen3:14b` cognitive engine and runtime context assembler, and the two tool-free stages. It preserves a saved USER turn even if a guarded inference fails; it never silently retries through the unguarded path. The existing idle/model lock serializes local inference.
- `opt_in_service.py` and `application/bootstrap.py` compose a subclass of the existing live service. **Default is disabled.** Only the exact independently reviewed `I ask to hug you` text uses the new route if `SOFIA_INTERACT_STAGED_OFFERS=1`. Everything else continues through the existing `ExpandedConversationService`. An unreviewed `Could I hug you?` has NOT gained a clarification route. Do not set this environment variable on Sofía's actual production database yet: optional attestation/schema provisioning, real Qwen expression quality, and broader integration still need review.
- `test/test_interaction_atomic_offer_release.py` and `test/test_interaction_opt_in_live_offer.py` use disposable SQLite and stub LLM responses for saved-turn checks, stop, attested/unverified boundaries, revocation, policy changes during inference, rollback, exact-phrase gating, default-off behavior and no leaked diagnostic reasons. These are new tests to RUN, not claimed passes.

### Next Windows code-only gate

With Sofía closed and `.venv` active, verify the `feature/pkg-interact-shared-engine` branch, inspect and preserve existing changes, and use `git pull --ff-only origin feature/pkg-interact-shared-engine`. Then:

```powershell
python -m pytest -q -x `
    test/test_interaction_atomic_offer_release.py `
    test/test_interaction_opt_in_live_offer.py `
    test/test_interaction_conversation_offer_context.py `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_expanded_service.py `
    test/test_interaction_preference_context.py `
    test/test_interaction_boundary_counterfactual_probe.py `
    test/test_interaction_route_boundary_probe.py `
    test/test_interaction_architecture_compare.py `
    test/test_interaction_decision_expression.py `
    test/test_interaction_decision_reason_audit.py `
    test/test_application.py
```

Stop at the first failure. Do not enable the opt-in or run a production CLI interaction for this checkpoint; no Ollama sampling is needed for stub-only verification.

## Definition of done, in order

- [x] Exploratory same-model decision contrast and synthetic boundary counterfactual, with raw evidence and stated limitations.
- [x] Isolated guarded policy checks and conversation-context bridge verified on Windows with disposable, stub-only tests.
- [ ] **Live adapter and transaction gate:** run the new tests, inspect real application bootstrap/context/persistence, verify concurrent writer ordering, safe failure/restart, stop and revocation; ensure no duplicate user or assistant messages. Test opt-in only against a separate, explicitly provisioned disposable runtime database, never the modified production state.
- [ ] **Reviewed phrasing and natural clarification:** expand supported offer forms deliberately, with abstention for genuinely ambiguous input and no fabricated consent. Real physical sensor/hardware questions stay outside avatar-social routing.
- [ ] **Grounded expression and supervised Qwen checks:** exercise complete choice and expression with `qwen3:14b` on an isolated session. Inspect raw replies for fabricated history, body sensation, narrated completed touch or animation, and repetitive generic assistant fallback. Heuristic flags are advisory only; do not force accept/decline or canned reactions.
- [ ] **Regression, privacy, authorization and concurrency review:** run full suite and relevant integration, integrity, CORE/SAFE, source-attestation, stop/race/replay, privacy and performance checks. Review PR #2 diff and reconcile base conflicts before approval.
- [ ] **Explicit user acceptance:** Sparks approves the package and any merge. PR #2 remains draft/unmerged and `main` unchanged until then.

Discord/PKG-NET, 24/7 runtime, actual avatar animation and physical sensors stay in their own packages rather than broadening this closure definition. Preserve Sparks's modified production DB, timestamped backup, independent local `test/test_ollama_generation_contract.py` edit and installed model settings.
