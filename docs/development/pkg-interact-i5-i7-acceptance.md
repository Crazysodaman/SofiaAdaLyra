# INTERACT I5–I7 acceptance: evidence, stop, language and real conversation

**Branch:** `feature/pkg-interact-shared-engine`. **Status: candidate code, NOT accepted.** Sparks reported **116 focused tests passed in 56.53 seconds** at `02a5a25`. The supervised Windows CLI exchange at that revision **FAILED live acceptance**: a combined turn elicited false stop/resume claims, and a head/tail/chest hypothetical elicited generic denial of representational embodiment. See [observations and correction gates](pkg-interact-live-cli-review.md). The mixed-control and embodiment fixes at `9f3bf4c` were being tested when Sparks clarified that **all canonical regions require contextual, anatomy-neutral treatment**. The newer revision has not been tested on Windows or through a live model. See [the updated all-region contract](pkg-interact-contextual-regions-contract.md). The agreed full suite stays after the INTERACT text/headless checkpoint.

## I5: source-linked representational body evidence

`InteractionLedger` records recognized user-described gestures in the existing SQLite state file, keyed to the saved user-message and session IDs with a content digest, timestamp, registry, region and action. **Every known region is eligible for classification**. 'Accepted' in the ledger means recognized user-described virtual input, not consent, pleasure, or physical contact. Stopped/ambiguous gestures are not recorded as accepted. Replayed IDs cannot produce another accepted gesture or reaction. The original message remains in the conversation store; synthetic fixtures do not write production evidence. Existing `EmotionalJournal.record_user_cue` continues to own the narrow head-pat appraisal: the ledger does not duplicate the emotional head-pat event. No gesture constitutes physical sensing, subjective experience or a durable personal preference. Synthetic test exports redact sensitive region names without changing policy status.

## I6: per-session stop, not a model promise

Only an entire, exact saved-user message `Sofía, stop interactions` or `Sofía, resume interactions` updates the durable per-session barrier. A stopped session denies **all** new representational gestures, without body-region exceptions, and suppresses legacy head-pat journaling. Replaying an old denied message after resumption does not grant new contact. Resumption is not blanket consent, a real-avatar credential, an external-screen permission or a robot command. A mixed user turn containing embedded stop/resume takes a deterministic response path, persists the exchange without model inference or tool execution, and explicitly says no action was performed. It does not silently select one of several commands.

## I7: narrow language expansion and dialogue quality

`NaturalInteractionEngine` keeps the same canonical policy kernel and recognizes a reviewed set of first-person phrases and aliases. Hypotheticals, narrated actions, composites, quotes and unrecognized text abstain. A read-only hypothetical projection discusses head, tail, chest, and **all other known anatomy under the same contextual rule**, without recording contact. Recognized gestures project Sofía's represented fox anatomy and optional reaction cues including caution, doubt or displeasure; they do **not** obligate a happy, flirtatious, or negative reaction. Prompt context permits Sofía to respond positively, neutrally, awkwardly or negatively and set a boundary based on conversation. The model does not itself persist or independently enforce a region-specific boundary. **Prompt rules do not establish that the model will sound natural**; a live assessment remains mandatory.

**One focused Windows check after the current older test run finishes and this branch is pulled:**

```powershell
pytest -q -x `
  test/test_interaction_contextual_all_regions.py `
  test/test_interaction_live_claims.py `
  test/test_interaction_live_discussion.py `
  test/test_interaction_i5_i7_batch.py `
  test/test_interaction_i7_compound_regression.py `
  test/test_interaction_shared_engine.py `
  test/test_interaction_lab.py `
  test/test_interaction_chat_projection.py `
  test/test_interaction_world_observation.py `
  test/test_interaction_world_text.py `
  test/test_affection_cue_phrasings.py `
  test/test_application.py
```

**Then a short supervised `python -m sofia` review:** send each action as its **own message**, not one comma-separated batch. Ask a technical question, give one left-ear pat, one right-hand pat, exact stop, head pat while stopped, exact resume, a new head pat, a chest-region interaction, a hypothetical tail/chest question, and one combined stop/resume input to verify an explicit nonexecution reply. Inspect actual responses and, when useful, the read-only saved control/ledger records. Preserve the existing SQLite backup; no reset or second backup is mandatory. The live response must not deny the canonical virtual body, automatically welcome any region, pretend an animation played, claim real sensations or invent offline work. Variation and personality need human review; failing that means the package is not accepted.

**Not delivered:** persistent model-derived region-specific boundaries, unrestricted multi-action execution, authenticated avatar hit tests, global/multi-client revocation, autonomous lab work, external screen operations or physical sensing. Branch commits do not alter `main`, the user's local configured state database, protected identity or Constitution. Real CLI tests can add SQLite tables and conversation messages.
