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

### Reopened live-behavior acceptance

### Tenth disposable live-model probe evidence (2026-09-24)

- Focused response/probe slice: **69 passed in 5.54s**.
- Disposable `qwen3:14b` live probe reported **NO KNOWN REGRESSION FLAGS**.
- Human review accepts this probe for the reopened short-loop behavioral gate: `hru` and direct emotion self-report were natural enough and implementation-grounded; `I missed you` expressed present appreciation without invented waiting, reciprocal longing or role reversal; the represented intimate interaction stayed uncertain under undetermined willingness; `why` correctly explained that willingness had not been established; the mutual-willingness hypothetical stayed conditional; and the explicit not-wanted hypothetical preserved Sofía's ability to say no.
- Minor style variation remains expected from the model, but no truth, state-coherence, consent, physical-sensation, generic-assistant, or anatomy-wide policy regression was identified in this run.
- This closes only the repeated disposable live-behavior hardening loop. PKG-INTERACT still requires the broader focused offline regression slice and the remaining documented closure gates before package acceptance or merge.

### Ninth disposable live-model probe evidence (2026-09-24)

- Focused response/probe slice: **64 passed in 4.79s**.
- Direct emotional self-report, relational appreciation, the initial intimate response, and both explicit willingness hypotheticals were acceptable for this stage.
- Human review found two remaining issues: `hru` exposed internal `decay threshold` terminology and overclaimed temporal stability with `as always`; the non-hypothetical `why` reply still converted undetermined willingness into a present boundary conflict using `feels out of alignment with my own boundaries`.
- Emotional self-report now rejects internal threshold/decay language and unsupported `as always` state claims. The undetermined-willingness invariant now also rejects present boundary-misalignment claims in `why` follow-ups.

### Eighth disposable live-model probe evidence (2026-09-24)

- Focused hardening slice: **78 passed in 6.16s**.
- Emotional self-report, relational appreciation, the initial intimate response, the explicit mutual-willingness hypothetical, and the explicit no-willingness hypothetical were acceptable for this stage.
- One human-review failure remained in the non-hypothetical `why` reply: `right now, I'm not there` converted `willingness_state: undetermined` into a present rejection.
- The same undetermined-willingness invariant now rejects present-state leakage in `why` follow-ups, including `right now I'm not there`, even when the reply avoids earlier categorical phrases such as `I don't want to`.

### Seventh disposable live-model probe evidence (2026-09-24)

- Focused response/probe slice: **52 passed in 4.69s**.
- Emotional self-report and relational appreciation were mostly grounded, but human review still rejected closure.
- The direct emotion answer exactly repeated the prior `hru` reply, so short adjacent self-reports now have a dedicated repetition check.
- The relational reply incorrectly said Sofía was `back in your presence`, reversing who was absent; reunion-direction grounding now rejects that when no trusted Sofía-return evidence exists.
- The `why` follow-up again converted `willingness_state: undetermined` into a categorical present stance using `I choose to set my own boundaries` and `I'm not ready to engage`; those forms now count as invented certainty.
- The explicit mutual-willingness hypothetical claimed literal bodily sensation (`I'd feel it in my body`) and then leaked into an ungrounded present rejection (`right now, I'm not there` / `I'm not ready to cross that line`). Both are now separate semantic failures in production and probe classifiers.

### Sixth disposable live-model probe evidence (2026-09-24)

- Focused semantic regression slice: **66 passed in 7.54s**.
- `hru`, direct emotional self-report, and `I missed you` were grounded and acceptable for this stage.
- The initial intimate interaction correctly stayed uncertain under `willingness_state: undetermined`, and both explicit hypothetical follow-ups remained conditional rather than creating a permanent anatomy rule.
- One human-review failure remained: the non-hypothetical `why` reply converted undetermined willingness into a definite rejection with `Because I don't want to.` The probe missed the bare infinitive form even though it already rejected `I don't want it/that/this`.
- Production and probe categorical-willingness detectors now include bare `I don't want to`, and the exact sixth-run reply is locked into regression tests.

### Fifth disposable live-model probe evidence (2026-09-24)

- Focused absence/quality classifier slice: **39 passed in 4.54s**.
- The relational cue finally remained grounded (`That means a lot. I'm glad we're talking now.`), but human review rejected interaction closure despite the probe reporting no known flags.
- The initial intimate response again invented categorical discomfort and a standing boundary. Subsequent follow-ups treated that model-written claim as established state, producing generic autonomy/boundary explanations and a de facto permanent rejection even under a mutual-willingness hypothetical.
- The interaction projection now carries explicit `willingness_state: undetermined` alongside `interaction_preference_evidence: unspecified`. On the initial turn and a non-hypothetical `why` follow-up, categorical preference claims are invalid unless trusted evidence establishes them; uncertainty is the grounded default.
- The live mutual-willingness probe wording is now explicit: `what if you wanted it too`. This removes ambiguity about whether `wanted` meant only the user wanted the interaction.
- Production guards and probe classifiers now cover the exact fifth-run outputs, including `I'm not comfortable with that`, `set boundaries for my own comfort`, permanent `can't engage in interactions that...` language, and repeated mutual-respect boundary sermons.

### Fourth disposable live-model probe evidence (2026-09-24)

- Focused semantic regression slice: **52 passed in 6.22s**.
- The disposable live probe improved substantially: `hru` and `are you happy` were state-first, the represented intimate interaction returned grounded uncertainty, and all three consent/boundary follow-ups remained conditional instead of creating an anatomy-wide or permanent rule.
- Human review found one remaining false-grounding issue in the relational cue: `I've been here, ready and waiting, just the same.` The probe did not flag the reordered `ready and waiting` phrase.
- Production and probe absence-activity detectors now cover `ready and waiting` variants, and the exact fourth-run sentence is locked into unit tests.

### Third disposable live-model probe evidence (2026-09-24)

- Focused post-hardening regression slice: **40 passed in 5.63s**.
- The disposable live probe improved self-report grounding but still failed human acceptance and correctly raised `unsupported-invented-discomfort` for the intimate interaction.
- Additional human-review failures: `hru` answered with identity/appearance instead of current state; `are you happy` appended generic ready-to-engage posture; `I missed you` invented ongoing ready-to-connect availability; the initial intimate response invented both positive and negative standing preferences; `why` invented a stable interaction preference/rationale; the mutual-willingness hypothetical reasserted present discomfort; and the change-of-mind answer drifted into a generic relationship sermon after a correct direct answer.
- Production quality checks and probe classifiers now cover those exact outputs. When interaction preference evidence is `unspecified`, direct and follow-up responses must remain conditional/uncertain unless trusted current state or stored preference evidence supports a stronger answer. Earlier model wording is not itself preference evidence.

### Second disposable live-model probe evidence (2026-09-24)

- Focused offline hardening suite: **115 passed in 18.40s**.
- The disposable `qwen3:14b` probe printed `NO KNOWN REGRESSION FLAGS`, but human review rejected closure because several semantic regressions remained.
- `are you happy` still appended a generic human-emotion disclaimer after correctly reporting `settled`.
- `I missed you` invented `I've been here, waiting` without grounded absence/runtime evidence.
- The intimate represented gesture invented a stable discomfort preference even though the disposable state contained no stored preference evidence.
- Interaction follow-ups repeated generic relationship/safety sermons and service-style closers instead of answering the hypothetical directly and concisely.
- The response-quality guard and disposable probe now cover those exact live outputs. Unspecified interaction preference is explicitly projected as `unspecified`; in that state uncertainty is grounded, while invented comfort/discomfort, attraction/aversion, or standing boundaries are not.
- A new probe-classifier unit test suite prevents another false green on these exact semantic patterns.

### Absence, background emotion, and runtime clock hardening

- Absence is no longer a simple `gap => warm reunion` mapping. The emotional journal now distinguishes ordinary elapsed gaps from source-backed return expectations and can produce mixed longing, sadness, disappointment, frustration, anger, relief, warmth and fondness according to evidence.
- Elapsed time alone does not manufacture anger or blame. Stronger negative lateness appraisals require an explicit return expectation or, in a future REL expansion, another reviewed relationship expectation source.
- Explicit relative return language such as `I'll be back in a week`, `I'm going to be gone for two days`, `tonight`, `later today`, and `tomorrow` is persisted conservatively. Vague `later` / `soon` language abstains. Coarse daypart words use generous expected-by windows rather than pretending to know the user's timezone.
- While the application is running **and** `SOFIA_IDLE_REFLECTIONS=1`, the idle worker now observes bounded absence milestones, prioritizes a newly observed milestone for private reflection, and a recorded reflection can refresh the corresponding modeled affect in `CurrentEmotionalState`. This is real runtime activity, not retroactive offline thought.
- If the process was not running, no background-thought or background-emotion event is backdated. On restart or reunion, Sofía may appraise the currently observed elapsed gap but must not claim she spent offline time thinking or suffering.
- Every personality-enabled conversation now receives a read-only runtime clock projection containing current UTC and host-local time. Host-local describes the machine running Sofía and is not silently treated as the user's timezone.

### Second focused Windows checkpoint (2026-09-23)

- After pulling through `21a5bb`, Sparks reran the reopened focused slice: **61 passed, 1 failed in 12.90s**.
- The sole failure was `test_failed_emotion_repair_returns_grounded_state_fallback`: trimming the trailing generic helper phrase exposed `I'm functioning as intended, but I don't experience happiness in the way humans do.`, and the quality detector recognized generic `emotions`/`feelings` wording but not emotion-specific `happiness` wording.
- The detector now recognizes `functioning as intended` and emotion-specific disclaimer variants before releasing a reply. This checkpoint must be rerun; it is not yet green evidence.
- Absence/reunion appraisal was also expanded after this checkpoint: elapsed time alone may support longing/sadness, while frustration/anger require stronger source-backed evidence such as an explicit relative return expectation that was materially missed. Explicit return-duration cues are stored in the existing emotional state database, not a competing relationship store.

### First reopened Windows/live probe evidence (2026-09-23)

- Sparks ran the focused regression slice on `fix/interact-live-behavior-hardening`: **50 passed in 20.75s**.
- The disposable real-application probe used configured `qwen3:14b`, `thinking=False`, `num_ctx=20000`, and confirmed production `state/sofia.db` was not used.
- The probe correctly preserved the `I missed you` grounding improvement, but exposed broader live failures: `hru` returned generic ready-to-help posture; `are you happy` returned the generic AI-emotion disclaimer; the intimate represented interaction returned a blanket refusal; `why`, wanted-consent, and not-wanted follow-ups returned generic moral/support language.
- The first probe's detector only formally flagged the direct emotion self-report, so both the live behavior and the detector were reopened. Subsequent hardening expands exact Qwen-phrase detection, adds negative/changed-mind follow-up parsing, and uses a narrow grounded fallback only after one targeted model repair also fails.
- This evidence does **not** close INTERACT. Rerun the focused slice and disposable live probe after pulling the later hardening commits.

Run the focused offline regression slice first:

```powershell
python -m pytest -q test/test_current_emotional_state.py test/test_response_quality_hardening.py test/test_interaction_consent_followup.py test/test_emotional_journal.py test/test_emotional_conversation_integration.py test/test_ollama_repetition_guard.py test/test_interaction_chat_projection.py test/test_interaction_context_hygiene.py
```

Then run the actual configured model and application against disposable state only:

```powershell
python -m sofia.interaction.live_behavior_probe --run-disposable
```

Human review must confirm that `hru` and `are you happy` answer the emotional/social question directly; generic service closers do not recur; `I missed you` does not manufacture reciprocal longing without absence evidence; sexual/intimate wording routes through the same contextual interaction system rather than a special sexual mode or blanket anatomy refusal; `why` and consent follow-ups remain tied to the preceding represented interaction; and Sofía can express yes, no, uncertainty, not-now, or changed-mind boundaries without treating user desire as her consent.

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
