# V18: Owner live conversation follow-up corrections

Date: 2026-10-20 (America/Chicago)
Branch: main
Scope: CA-506, CA-3802, CA-5704, CA-5710; related CA-501, CA-503 and AVATAR self-fact grounding.

## Evidence

The owner supplied a real conversation after the 129-test Windows pass pinned to
`49318c9ac3c1306b613f43d2caaedb8f18f8c4d6`. The owner has **not yet**
provided a new local HEAD or live-model provenance for this observed run.

- "How are you?" produced an unsupported first-person account of how the last
  twelve hours *felt*, and a generic service handoff.
- "What are you wearing?" returned a concrete, current lounge ensemble.
- "why?" supplied comfort/random-inspiration/old-papers explanations without
  a verified wardrobe-selection source.
- "do u have a tail" claimed a small/slender tail rather than the canonical fox
  tail; implied animation/activity without a renderer receipt.

This contradicts the intended provider-agnostic identity, current presentation
and uncertainty contracts. The prior tests were passing **without covering the
live failure classes**. That run must not be retroactively relabeled failed.

## Existing source-of-truth found in the code

1. `AvatarSelfFactResolver.resolve` already knows how to explain an outfit from
   `PresentationProjection.reason`, including `headless_daily_context`,
   `user_clothing_action`, bootstrap, and unknown reasons. This was not reached
   by one-word "why?" responses.
2. `embodiment/avatar.json` defines a fox tail in anatomy and features,
   dark-violet coloring, lighter-violet tip, and fluffy fur. Precise tail
   dimensions are not measured in the canonical data.
3. `response_quality_issue` already rejected several emotion overclaims but
   did not recognize "last twelve hours felt like a long pause".

## Corrections authored on main

- `src/sofia/application/conversation_service.py`: after normal saved-turn
  coordination and before generic V2/model response, resolve a narrow set of
  self-fact questions from the canonical avatar. Bare outfit "why?" must survive
  the existing domain-filtered immediately preceding exchange; an explicit
  outfit-choice query supplies its own referent. Reuse the existing audience
  projection, checked private grants, and wardrobe matrix. No new state store
  or approval is introduced.
- `src/sofia/avatar/self_fact_query.py`: answer direct presence questions
  such as "do u have a tail?" from canonical anatomy/feature declarations and
  current presentation appearance, without invented size, sensation or movement.
- `src/sofia/cognition/repetition_guard.py` and
  `src/sofia/cognition/quality_repair.py`: recognize unsupported elapsed
  subjective experience in a check-in and request a targeted text-only rewrite
  that describes only current evidence.
- Added focused tests in `test/test_avatar_self_fact_query.py`,
  `test/test_conversation_service.py`, and
  `test/test_response_quality_hardening.py`.
- `.github/workflows/v18-conversation-quality-regression.yml` now watches
  and runs the new AVATAR coverage.

## Validation status and open acceptance

**Source changes committed; no post-change pytest or CI pass has been
observed in this chat.** The owner's previous 129 passed applies only to the
older `49318c9` revision.

Focused verification command on a fresh main checkout:

```powershell
git pull --ff-only origin main
git rev-parse HEAD
python -m pytest -q --durations=10 `
  test/test_avatar_self_fact_query.py `
  test/test_response_quality_hardening.py `
  test/test_conversation_service.py `
  -k "tail or outfit or checkin_rejects_invented_subjective_elapsed_waiting or simple_present_checkin"
```

Before task promotion, also run the full cross-package regression and repeat
the same real conversation on Venus with each configured model. Save source
revision, responses, current presentation reason provenance, actual renderer
receipts (or absence), and cross-channel results. Verify unrelated "why?"
questions, missing avatar state, privacy filtering, and truthful uncertainty.
No task in this workstream is newly asserted Level 4 or 5.
