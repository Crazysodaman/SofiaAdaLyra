# V18 focused cognitive behavior correction: outfit-choice follow-ups

Date: 2026-10-20
Branch: `main`
Scope: CA-5704, CA-5710, CA-506, CA-3802; related CA-501/CA-503/CA-508.

## Reproduced behavior targeted

Owner's observed exchange:
1. User asks what Sofía is wearing; a grounded clothing list is returned.
2. User asks "why?".
3. Sofía treats the referent as missing, insults the user using a vending-machine metaphor, and fails to explain the outfit selection.
4. User clarifies "I mean why you choose your outfit?".

No new memory owner, identity, permissions or wardrobe-selection state is introduced.

## Production changes

- `src/sofia/application/conversation_service.py`: detect outfit-choice "why?" using only the already domain-filtered immediately preceding user/assistant exchange. Supply host-authored clarification to the provider without copying any untrusted dialogue into a system instruction. Support explicit outfit-choice questions even after a deflection or when the history policy limits the prompt to the current turn. Do not invent a selection reason from garment names.
- `src/sofia/cognition/repetition_guard.py`: reject the specific user-directed vending-machine and "more coherent query" insults, without prohibiting unrelated metaphor or useful technical challenge.
- `src/sofia/cognition/quality_repair.py`: on the bounded provider retry, answer the actual outfit-selection question and require grounded motive evidence. If both drafts fail, return a truthful context-limited unknown rather than a generic apology that dodges "why?".

## Authored tests and CI

- `test/test_response_quality_hardening.py`: original insult, one retry, double-hostility fallback, positive grounded uncertainty, explicit later clarification, unrelated why.
- `test/test_conversation_service.py`: source-scoped one-word follow-up detection; negative unrelated-topic cases; production `_build_request` carries relevant context while excluded domains stay excluded; explicit post-deflection clarification.
- `.github/workflows/v18-conversation-quality-regression.yml`: Python 3.12 cross-platform compilation and focused personality/conversation/provider regression on Windows and Ubuntu, pinned to the push commit.

## Owner Windows focused regression (2026-10-20)

The owner reported the following run from a `.venv` PowerShell session on
Venus (Windows) after the source changes:

```powershell
python -m pytest -q `
  test/test_conversation_service.py `
  test/test_response_quality_hardening.py `
  test/test_short_contact_channel_quality.py `
  test/test_cognition_v2_turn_kernel.py
```

**Owner-reported result: 129 passed, 0 failed, in 1469.16 seconds
(approximately 24 minutes 29 seconds).** The owner subsequently supplied:

- **Tested Git HEAD:** `49318c9ac3c1306b613f43d2caaedb8f18f8c4d6`
- **Python:** `3.12.10`
- **Environment:** Windows Venus, activated `.venv` PowerShell session
- **Pytest version:** not recorded in the supplied output

This pins the reported passing regression to an exact local source revision.
It is owner-provided output, not an independently executed test in this
development session. This is **not** a CI receipt and **not** a live Ollama
conversation acceptance trial. Later audit and CI-timeout commits do not
retroactively change the tested SHA.

The first cross-platform quality workflow had `timeout-minutes: 20`, shorter
than the observed Windows subset runtime. Its successor increases the cap
to 45 minutes and adds pytest `--durations=15` diagnostics; this only avoids
a predictable premature timeout and does not diagnose the slowness. Treat the
performance question as open.

## Evidence limits and remaining acceptance

These are source code, authored tests, and the owner-reported local Windows pass above. **No matching-commit GitHub Actions result or live Ollama conversation trial has been observed.** The CI workflow exists but its success is NOT asserted. No independent live Venus/Ollama answer-quality trial has been executed.

Needed before Level 4:
1. Local tested SHA and Python version are recorded above. Capture pytest version if needed and re-run tests if any later production changes affect the behavior; retain a per-task source-to-test mapping.
2. Run a live Venus conversation with the configured primary and secondary Ollama routes: "what are you wearing?" → "why?" → "I mean why you choose your outfit?". Check relevance, natural language, truthful selection reason/unknown, and absence of user-directed contempt.
3. Check ordinary "why?" after a technical answer and unrelated metaphors for false positives.
4. Record actual outputs/commit/time and audit privacy, authority, memory and wardrobe state.

Do **not** promote CA-506, CA-3802, CA-5704, CA-5710 or related Phase 08 tasks to Level 4 based only on this source work.
