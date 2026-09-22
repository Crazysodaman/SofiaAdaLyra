# PKG-INTERACT: finite closure gates

## Verified Windows evidence and limits

At `c2d27e6`, Sparks reported **80 focused tests passed in 7.53 seconds**. Three synthetic, counterbalanced Qwen `qwen3:14b` pairs used the *same* avatar-social decision request. Without a synthetic boundary Qwen chose `clarify` 3/3; with the explicitly simulated no-hugs statement it chose `decline` 3/3. No physical-impossibility premise appeared in these six reasons, although several declines did not attribute the choice explicitly to the boundary. These observations are not proof of causation or live reliability. No boundary does not imply consent, a regex miss is not validation, and only `qwen3:14b` was installed.

At `d866326`, Sparks reported **95 focused tests passed in 12.04 seconds**, including the new guarded-offer and source-attested boundary tests. These tests use stub providers and disposable SQLite; no live Ollama inference or `python -m sofia` integration has been verified for the guarded path. The fast-forward checkout preserved the preexisting modified database, independent test edit and timestamped backup.

## Current candidate: preserve actual conversation context

`src/sofia/interaction/conversation_offer_context.py` and `test/test_interaction_conversation_offer_context.py` are a new **unverified-on-Windows** prerequisite for integrating the guarded path with a real session. The original synthetic prototype permitted only two or three messages. The bridge now accepts trusted host-provided canonical context, precisely one matching reviewed offer projection, preceding conversation turns, and the exact final user offer. It produces tool-free choice and expression requests with identical original history, using the existing B choice instruction. Only the validated choice, never the model-written diagnostic reason, enters expression. Unreviewed/duplicate projections, changed final text, tool definitions, tool-call history and missing canonical self-state are rejected.

`src/sofia/interaction/trusted_offer_gate.py` now uses that bridge and the existing `read_interaction_context` and session-stop read. It checks active/unverified boundaries and stop **before decision, before expression, and before returning text**. It fails closed on changed attestation, missing schema, bad provider output and unexpected tool calls. The gate does **not** write production state, save a reply, verify client identity, perform contact or render motion. Its three reads do **not** provide atomic cross-process enforcement. The existing live `ExpandedConversationService` is not yet wired to this gate, and no new setting is enabled by default.

### Immediate Windows check

With Sofía closed and `.venv` active, check `feature/pkg-interact-shared-engine`, inspect local edits, and `git pull --ff-only origin feature/pkg-interact-shared-engine`. Then:

```powershell
python -m pytest -q -x `
    test/test_interaction_conversation_offer_context.py `
    test/test_interaction_trusted_offer_gate.py `
    test/test_interaction_preference_context.py `
    test/test_interaction_boundary_counterfactual_probe.py `
    test/test_interaction_route_boundary_probe.py `
    test/test_interaction_architecture_compare.py `
    test/test_interaction_decision_expression.py `
    test/test_interaction_decision_reason_audit.py
```

Stop and inspect the first traceback on failure. No extra Ollama sampling is needed for this code-only checkpoint. Do not treat tests on stubs as Qwen quality acceptance.

## Definition of done, in order

- [x] **Exploratory decision contrast:** observed paired synthetic A/B and boundary counterfactual; preserve raw output and limitations. Reassess after changes to decision wording.
- [x] **Isolated guarded-policy candidate:** source-attested stop/boundary read and three rechecks have passed focused Windows tests on disposable databases. This is not deployed or atomic enforcement.
- [ ] **Conversation-context bridge:** run the new stubbed tests and inspect the preserved history and tool-free scope. Then integrate using the application-owned runtime context, source-verified saved user evidence, and transaction-safe policy at reply release. Do not bypass ordinary conversation persistence, memory/context or unrelated capability authorization.
- [ ] **Reviewed phrasing and clarification:** explicitly review common social-offer wording including `Could I hug you?`, build a natural clarification for unreviewed/ambiguous text without inferring consent. Real-sensor/hardware questions stay on the actual-world route.
- [ ] **Grounded expression and supervised live quality:** test the validated choice-to-expression path with configured Qwen in an isolated session. Inspect for fabricated history, durable preference, felt touch, claimed performed contact/animation and generic assistant fallback. Heuristic flags are advisory only; do not force an accept/decline or canned gesture.
- [ ] **Regression, security and concurrency review:** full suite, source attestation activation/revocation, stop/race/replay checks, privacy, CORE/SAFE/authorization, representative conversation and performance checks; review the PR diff and reconcile any merge conflicts.
- [ ] **Explicit user acceptance:** Sparks approves the reviewed integration and any PR merge. Until then, PR #2 remains draft and `main` unchanged.

PKG-NET/Discord, 24/7 operation, actual animation and physical sensors are separate packages. Preserve modified `state/sofia.db`, its timestamped backup, the independent local `test/test_ollama_generation_contract.py` edit and provider settings.
