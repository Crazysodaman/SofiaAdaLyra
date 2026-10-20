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

## Evidence limits and remaining acceptance

These are source code and authored test evidence. **No local pytest or GitHub Actions result has been observed in this session.** The CI workflow exists but its success is NOT asserted. No independent live Venus/Ollama answer-quality trial has been executed.

Needed before Level 4:
1. Pass focused regressions against the exact updated commit, including the negative privacy/domain cases.
2. Run a live Venus conversation with the configured primary and secondary Ollama routes: "what are you wearing?" → "why?" → "I mean why you choose your outfit?". Check relevance, natural language, truthful selection reason/unknown, and absence of user-directed contempt.
3. Check ordinary "why?" after a technical answer and unrelated metaphors for false positives.
4. Record actual outputs/commit/time and audit privacy, authority, memory and wardrobe state.

Do **not** promote CA-506, CA-3802, CA-5704, CA-5710 or related Phase 08 tasks to Level 4 based only on this source work.
