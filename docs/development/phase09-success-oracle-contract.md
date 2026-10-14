# CA-3501: Trusted success oracle by activity class

**Decision scope:** This is a reviewed Phase 09 design contract, not a second
truth authority and not an assertion that a real Venus deployment was tested.

## Four independent questions

| Question | Canonical owner/source | Independent admissible proof | What is NOT proof |
| --- | --- | --- | --- |
| Did an artifact exist? | CreativeStore and CreativeExplorer.verified_preview | Scoped actual revision, SHA-256 of reopened bytes, exact artifact ID, revision, audience and author | Filename, generated success text, original work item marked completed |
| Did it satisfy technical objectives? | LIFE original brief + `sofia.life.validation.inspect_objective_artifact` + canonical RUN | Exact original typed objective, executable bounded validator, source-byte verification, linked successful RUN receipt with same SHA-256, byte count and revision | Tool returned `true`, approximate title match, a source-file digest alone, unsupported subjective objectives |
| Was it useful or liked? | LIFE ArtifactEvaluation, owner correction, PREFERENCE registry | A separately reviewable judgment with scoped source reference, explicit bounded `PersonalJudgment`, history/corrections and timestamp; UNKNOWN is valid | Model praise or technical pass being converted to affection or usefulness |
| Did the project reach its milestone? | LIFE/GOALS policies and canonical milestone transitions | All original objective results eligible, original execution + source evidence still valid, matching project/goal scope, replay-safe milestone update and policy transition | A completed work job, one correct artifact, a synthetic progress report, an expired grant |

## State semantics

1. `exists`: only the byte-level presence fact, with exact revision and scoped provenance.
2. `technically_valid`: all supported original criteria independently checked. Unsupported criterion is `UNKNOWN`, not `PASS`. The technical validator never applies SAFE permissions.
3. `personally_useful`: independent personal judgment. Technical correctness neither implies nor requires LIKE; `UNKNOWN` is the default, not negative.
4. `milestone_complete`: LIFE policy advances an explicit original milestone after checking original RUN and GOALS evidence. The milestone does not mint technical evidence or self-authorize the next effect.

Allowed direction: original bytes and original RUN evidence → objective report → durable evaluation → policy-governed milestone/project state. Not allowed: model text/score → fake receipt → memory success → new work authorization. All observations preserve principal, audience, original time, evidence ID and revocation state.

## Failure/adversarial gates

- Replaced or enlarged artifact bytes must invalidate existence/technical proof even when the pathname remains unchanged.
- A forged completed RUN result with mismatched SHA-256 or byte count must not authorize review.
- Syntactically valid Python can pass a *syntax* criterion but cannot be claimed to be correct, harmless or useful.
- User-declined or uncheckable subjective objectives remain UNKNOWN; no automatic celebration, preference write or new revision spending.
- Running out of draft budget does not prevent verification of already completed work, but never permits an unauthorized second job.
- Worker interruption between evaluated result and milestone must replay only the original checked milestone, idempotently.

Implementation references:
`src/sofia/creative/service.py`,
`src/sofia/life/validation.py`,
`src/sofia/life/coordinator.py`,
`src/sofia/life/store.py`,
`src/sofia/goals/evidence.py`.
Functional regressions:
`test/test_life_autonomous_followthrough.py`,
`test/test_life_verified_milestone_production.py`,
`test/test_life_project_forge.py`,
`test/test_life_objective_parser_bounded.py`.

Review gate: design distinguishes all four owner domains and clearly identifies accepted, failed and unknown evidence. Production Gate 4 acceptance for any dependent CODE task must still be evidenced by its own exact-revision tests. This document grants no elevated privilege and creates no new schema.
