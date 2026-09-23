# PKG-INTERACT: finite closure gates

## Reopened after live conversational acceptance probe (2026-09-23)

The earlier structural closure is **suspended**. A real `python -m sofia` conversation exposed behavioral failures that the prior focused/unit coverage did not certify:

- `hru` fell through to a generic greeting plus `How can I assist you today?` instead of answering the social/emotional question.
- `are you happy` replaced Sofía's modeled emotional state with generic AI-emotion boilerplate.
- `gropes breast` did not match the interaction grammar, so the turn bypassed INTERACT and reached an ungrounded blanket refusal.
- Short follow-ups such as `why` and `what if it was wanted` were not explicitly grounded to the preceding represented interaction and could fall back to generic moral/safety prose.
- Generic service closers such as `How can I assist/support you?` repeatedly leaked through otherwise conversational replies.
- `I missed you` could be generated without a real absence/reunion appraisal and could imply ongoing thoughts while no recorded process established them.

The branch now includes live-behavior hardening for those findings: relationship-scoped current emotional state with decay, grounded reunion appraisal, explicit `I missed you` relational evidence, direct emotional self-report guidance, provider-side retry/trim for known generic fallbacks, consent/boundary follow-up grounding, emotion/gesture coherence guidance, and `grope/gropes/groping` normalization to the existing canonical `touch` interaction semantic. Historical head-pat auto-affection remains suppressed on the hardened live service.

**Closure may not be restored from code inspection alone.** The new focused tests must pass on Windows and the real configured Ollama model must pass a supervised conversational probe without the failures above. The unrelated local `18000` versus `32768` Ollama contract edit remains preserved and must not be overwritten merely to obtain a green suite.


## Verified Windows evidence

- At `f126521`, Sparks reported **67 focused tests passed** and a supervised real-Qwen disposable probe with a relevant clarification and synthetic boundary enforcement.
- At `01f52ae`, Sparks reported **97 focused tests passed in 81.60 seconds**. The actual application and installed `qwen3:14b` ran against an independent temporary SQLite database: a declarative hug offer produced a `clarify` choice and avatar-scene question; the narrow `Could I hug you?` route returned an avatar-versus-real-world clarification without inference; synthetic, source-attested no-hugs policy blocked both forms. Four turns used **two provider calls total**, and Windows temporary cleanup succeeded. The first Qwen question was slightly circular, and these cases do not prove broad conversational quality or consent.
- On the SAME `01f52ae` checkout, `python -m pytest -q -x` stopped at **1 failed, 1337 passed in 2416.25 seconds** on the pre-existing locally modified `test/test_ollama_generation_contract.py::test_ollama_generation_configuration_is_translated`: local input `context_size=18000`, local expectation `num_ctx=32768`. The provider intentionally passes configured `context_size` through to Ollama. The committed test constructs/expects 32768. **Do not overwrite the user's local edit or change provider settings to mask this mismatch.**
- Sparks then ran the qualified continuation with only that exact local assertion deselected: **1665 passed, 2 skipped, 1 deselected in 2397.64 seconds**. This establishes that every other collected test in that checkout passed. It is a qualified green regression result, not an unqualified full-suite pass until the local 18000-vs-32768 expectation is reconciled.
- GitHub reports draft PR #2 `mergeable=true` after the root-roadmap overlap was resolved. From the common ancestor, `main` has **55 newer commits** and the feature has its INTERACT history. A path-level comparison found **only one file changed on both sides: `ROADMAP.md`**. No INTERACT runtime or test path overlaps those 55 newer base commits. The feature copy of `ROADMAP.md` was an obsolete 13-package document while `main` contains the current 19-package roadmap, so the feature branch now mirrors `main` for that root roadmap. No rebase, merge or force push has been performed.

## Next gates (in order)

1. **Resolve the one local Ollama contract mismatch without discarding local work:** all other collected tests passed in the qualified run. Preserve the entire modified file and its second test; reconcile whether the intended contract input/expectation is `18000` or `32768` before editing. Do not change the provider merely to satisfy the stale expectation.
2. **Audit additional concurrency and policy integrity:** existing qualified-suite coverage already exercises restart persistence (`test_interaction_temporal.py`), replay/idempotence and session stops, source-attestation tamper detection, unverified revocation, scoped boundaries, external authentication, filesystem authority and unauthorized-tool hiding. A second deterministic SQLite writer-order regression covers the opposite serialization order (reply lock first, later stop waits). At `db40d58`, Sparks reported **2/2 writer-order tests passed in 17.21 seconds**, followed by the complete closure-audit selection **60/60 passed in 10.56 seconds**.
3. **Review PR scope and base integration:** the only path-level overlap with the 55 newer `main` commits was the root `ROADMAP.md`, now synchronized byte-for-byte to `main`. GitHub subsequently recomputed PR #2 as **mergeable=true**. The PR remains draft and unmerged. Optional interaction tables are intentionally not auto-created by normal startup/read paths; any future production provisioning remains a separate reviewed migration before enabling staged offers.
4. **Human acceptance and separate merge approval:** the technical closure gates are now satisfied except for the known unrelated local Ollama test expectation mismatch (`18000` input versus `32768` expected), which remains preserved and unmodified. Sparks reviews the demonstrated dialogue and known limitation (staged offers remain off until a separately reviewed schema migration), explicitly accepts PKG-INTERACT, and separately authorizes any merge. PR #2 stays draft and `main` unchanged until then.

## Safety and scope

The exact declarative offer and narrow reviewed-question routes are **opt-in off by default**. Synthetic boundary evidence is test-only. Never use the disposable probe on production `state/sofia.db`, enable `SOFIA_INTERACT_STAGED_OFFERS` globally, migrate production schema without review, infer real consent or contact, or alter the installed model settings. Preserve the modified database, timestamped backup, independent Ollama test edit, CORE PR #1 and RUN PR #3. Discord/PKG-NET, reliable 24/7 runtime, actual avatar animation and physical sensors remain separate packages.
