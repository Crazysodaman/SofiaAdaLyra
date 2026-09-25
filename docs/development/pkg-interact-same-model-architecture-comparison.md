# PKG-INTERACT: same-model avatar decision-route comparison (diagnostic only)

## Why this experiment exists

Sparks's Windows evidence at `15db95b`: 44 focused tests passed in 5.36 s, but the state-free `--case offer --samples 3` probe produced three `decline` decisions whose reasons all explicitly cited lack of physical presence. Declining is valid; invoking real-world physical impossibility as the reason for an *avatar-world offer* is a domain error. The expression audit also missed an explicit physical-impossibility statement. `ollama list` then showed **only `qwen3:14b` installed** (ID `bdbd181c33f2`, 9.3 GB), so a genuine second-model comparison cannot be performed without a new installation. Do not imply one was run.

## Controlled decision-contract comparison

`python -m sofia.interaction.architecture_compare --pairs 3` uses the existing installed Qwen and the exact synthetic `I ask to hug you` offer. The trusted action grammar classifies it once, the canonical assembler builds the original bounded request, and the same provider object/configuration is used for both paths. No SQLite, application startup, saved history, tool invocation or avatar execution occurs. This is **choice-only**: expression is deliberately excluded to isolate the previously observed decision-stage fault.

- **A (existing-choice):** the existing `choice_request` with the canonical self-state, same reviewed action and exact user text.
- **B (routed-avatar-social-choice):** deterministic, grammar-reviewed avatar-social routing; same canonical self-state, same reviewed action, same user text, same JSON choice/reason schema, allowed choices and tool-free scope. Only the decision-task message changes to require a social choice *within the represented scene*, reserving real-world capability checks for a different route. This is a routing/decision-contract **candidate**, not an independent model, and cannot establish that architecture rather than wording caused any observed difference.

Both paths still allow `accept`, `decline`, `clarify` or `boundary`, never auto-consent, force affection, complete contact, claim physical sensations or trigger animation. The test alternates request order each pair (A/B, B/A, A/B) to reduce simple order confounding. Ollama generation parameters are not overridden, but stochastic samples are **not seeded or paired**, so this is a qualitative diagnostic rather than a controlled statistical study. The original decision reason is printed for human inspection; narrow flags are *regex observations*, never a quality score or approval.

## Gates and next action

1. On `feature/pkg-interact-shared-engine` with Sofía closed, inspect `git status --short`, fast-forward only (`git pull --ff-only origin feature/pkg-interact-shared-engine`) and preserve independent local changes to `state/sofia.db`, its timestamped backup and `test/test_ollama_generation_contract.py`.
2. Run `python -m pytest -q -x test/test_interaction_architecture_compare.py test/test_interaction_decision_expression.py test/test_interaction_decision_reason_audit.py`; stop on failure. These use stubbed providers, not a live-model quality gate.
3. If green, run `python -m sofia.interaction.architecture_compare --pairs 3` once. Inspect *every* A/B choice, reason and flag. A decline with a contextual boundary is valid; a physical-impossibility premise in either path remains a diagnostic failure for that sample. Malformed JSON or tool-call output must not be silently converted to an acceptable choice.
4. If B consistently avoids physical-world reasons while A does not, gather additional reviewed fixtures, controlled sample sizes and regression/grounding checks before considering any integration. If both paths fail, investigate a different installed-compatible model **after verifying availability** or a deeper choice architecture; do not blindly retry the earlier failed Ministral download or stack general production prompt prose.

**No live adapter or merge.** Keep PR #2 draft and `main`, CORE/Artemis PR #1, RUN PR #3, production database, model settings and real-world execution unchanged. User approval is required before integration/merge. Tests and live inference have not yet been run on Sparks's Windows machine for this candidate.
