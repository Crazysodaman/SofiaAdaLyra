# INTERACT: supervised Windows CLI reviews, 2026-09-20

**Status: LIVE ACCEPTANCE FAILED.** Automated tests do not establish natural replies, complete permissions or real-world activity. Preserve the user's configured SQLite state database and timestamped pre-interaction backup. Do not reset or overwrite either.

## First real CLI review at `02a5a25`

The user sent a technical question, ear/hand gestures, stop, head pat, and resume in one turn. The model falsely claimed both controls occurred. A following mixed head-rub/tail/chest question produced generic denial of Sofía's represented form. The initial remediation at `9f3bf4c` added a mixed-control nonexecution response, read-only hypotheticals and clearer virtual embodiment. An import cycle was caught during collection and fixed at `a8fb5c8`; tests then passed. The user clarified that anatomy alone never forbids a registered region; recognition is not consent or approval. Those changes were included in the 143-pass check.

## Second real CLI review at `a8fb5c8`: FAILED

- Sofía reported 19 workspace changes and named nine added and ten modified files; the actual workspace evidence was not independently audited by this document.
- Two virtual gestures in one message were narrated as completed even though the conservative single-gesture parser abstained. No ledger completion was established by the reply.
- A new head pat while stopped received stage directions and an affirmative/recycled reply, instead of an enforced refusal. A subsequent hypothetical reply was disclaimer-heavy.

## Repair and earlier test evidence

- `InteractiveConversationService.respond` routes exact stop/resume, recognized gestures while stopped and plainly compound gestures through bounded, persisted non-LLM replies. The denied gesture is recorded as denied and is not passed to the emotion/model path. The unsupported compound turn saves only the conversation.
- Accepted gestures still use the normal language model, with context guidance discouraging repeated paragraphs, fabricated physical sensations and generic disclaimers. This guidance is not a deterministic guarantee.
- At `52a5d44` a narrow stop/repetition regression passed **11 tests in 2.24 s** in Windows PowerShell.
- At `0a5769a` four new standalone expansion test files passed **28 tests in 3.38 s** in Windows PowerShell.
- The next coordinated I8–I16 candidate was tested at `f3cf992`: **112 passed, one failed** in the hypothetical-prompt test, which expected two explicit grounding phrases. `412dc32` restored those phrases without weakening assertions.
- At `412dc32` the user reported **28 focused tests passed in 3.44 s** and **264 coordinated interaction/application tests passed in 87.92 s** on Windows PowerShell. Their existing local modifications to `state/sofia.db` and `test/test_ollama_generation_contract.py` and the untracked timestamped database backup were preserved. These results DO NOT establish full `pytest -q`, actual LLM response quality or autonomous features.

## Third supervised CLI review at `412dc32`: LIVE QUALITY FAILED

User supplied a full twelve-turn separate-message script and responses from `python -m sofia`. The following is an **assessment of visible replies**, not a direct query of the database, effective LLM request, active provider/model or playback channels.

**Observed working text/control behavior:** exact `Sofía, stop interactions` returned a pause message. A head pat and a described hug while stopped both received explicit non-contact replies. Exact resume returned an availability message. The ear-plus-hand compound turn explicitly stated neither action was completed. The tail/chest hypothetical was answered as a conditional, not narrated as an executed gesture. These text outcomes are consistent with the guarded routing; inspect saved ledger if a durable-state conclusion is required.

**Observed failures:**

1. Ear and hand pats both prompted near-identical variations of 'interesting gesture / what are you trying to convey?', rather than a specific, natural reaction. The accepted head pat after resume expanded into a long self-analysis about whether to be flattered, confused or annoyed, followed by another intent question.
2. An offered hug was answered as though physical contact were requested and refused on a generalized preference for conversation/collaboration. A described hug drew a generic inability-to-physically-reciprocate disclaimer. The refusal itself is allowed; the unsupported blanket preference and offered-versus-described mismatch are the problem.
3. The hypothetical tail/chest answer claimed prior engagement with those regions. No such earlier engagement appears in the supplied session. Whether another authenticated history supports the claim is **unknown**, not verified. The answer also speculated about how an action 'feels' and failed to discuss the two regions distinctly.
4. The accepted head-pat reply asserted a 'strange feeling' without clear modeled/fictional grounding, and repeated ear twitch/head tilt stage directions.
5. The Windows-service diagnosis was generic and verbose, without prioritizing the service's exact name, state, exit code, Service Control Manager events, dependency status and the first observable failure. This is a quality issue, not proof the advice is factually false.
6. Startup awareness offered a generic summary of workspace modifications without useful specifics. Its instruction currently supplies a change count and continuity kind, not necessarily filenames or useful significance; review the actual supplied context before blaming the model alone.

**Source-level inspection after transcript:** `src/sofia/interaction/chat.py` already instructs the model to avoid repetitive text, unrelated physicality disclaimers and mandatory stage directions; `src/sofia/interaction/expanded_service.py` already distinguishes `offered` and `described` in a structured action prompt; `src/sofia/personality/expression.py` already asks for direct, technically precise, varied answers. The observed model output did not consistently follow that guidance. `src/sofia/cognition/assembler.py` includes a personality section when a profile is loaded, but this transcript does **not** establish which profile, provider/model or exact assembled instructions the Windows process used. It is premature to declare the model alone responsible.

**Release decision:** keep PR #2 DRAFT and unmerged. I1–I7 safety-text behavior improved but natural-conversation acceptance is not met; I8–I16 is partial implementation, NOT complete.

## Next diagnostic gate before another patch

1. Capture a **redacted, read-only** snapshot of the actual effective request/context on the failing turns, including loaded profile name/style, provider/model ID, prompt ordering/size, memory provenance and any provider truncation metadata if available. Do not publish private user history, credentials, raw DB content or intimate journal entries. Do not enable new permissions or reset state.
2. Separate a provider baseline with the same model, canonical personality/grounding and recent turns from the full request, if a controlled local harness exists. Compare responses on offered/described hug, repeated different region pats, the hypothetical and a technical service diagnostic. Without such controls, assign likely cause only as a hypothesis.
3. Add automatic **structural** regressions where observable (phase distinctions, no invented recorded history, denied/compound noncompletion, no unauthorized action), plus a human-reviewed multi-turn response-quality checklist. Do not attempt to enforce personality with a brittle word ban or canned affectionate reply.
4. After targeted repair at a new SHA, rerun affected Windows tests, coordinated tests, a new supervised real-model session and finally full `pytest -q`; review migrations/security/privacy and request separate merge approval.

The actual voice/avatar, independent initiative, presence, message delivery, global/cross-client stop and completed I8–I16 acceptance remain outside the verified capability of this CLI review.
