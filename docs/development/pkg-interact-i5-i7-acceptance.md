# INTERACT I5–I7 combined acceptance: evidence, stop, language

**Branch:** `feature/pkg-interact-shared-engine`. **Status: candidate code committed, NOT accepted.** Sparks's preceding I4 run at `eb73357` reported **20 passed in 4.19 seconds**. That is not verification of subsequent I5–I7 changes. The agreed hour-long full-suite run stays after the INTERACT text/headless checkpoint.

## I5: source-linked body events, not imaginary physical sensing

`InteractionLedger` uses the existing configured SQLite state file and a new `interaction_evidence` table keyed to the actual saved user-message ID and session ID. It stores a content digest, timestamp, original accepted region/verb and registry version. A denied or unresolved region is never saved in the region/verb columns. The original user text remains in the conversation store; the ledger is a derivative with source references, not a new message store, physical event, permanent preference or actual emotional experience. Retried identical messages return `acknowledged` without a second event or emotion candidate; reused message IDs with changed evidence raise an error. The separate synthetic `InteractionLab` never calls this persistence adapter. Existing `EmotionalJournal.record_user_cue` retains responsibility for its existing narrow head-pat appraisal, so a second head-pat *emotional event* is not written. We do NOT automatically impose an emotion on every other gesture: the ledger records action evidence, and optional modeled reaction candidates are projected at response time. Broad durable appraisal revisions remain a separate emotion/MEM integration gate.

## I6: session stop and per-turn permission

The exact saved-user commands `Sofía, stop interactions` and `Sofía, resume interactions` toggle a durable, per-session stop barrier *outside the LLM*. A stopped session denies new body gestures and suppresses legacy head-pat journaling. Replaying an old denied gesture after resumption stays a replay, not new contact. Session controls use SQLite transactions and unique saved-message IDs. Resumption is not global consent: only a new, explicitly user-described, ordinary **text-only representational** gesture is eligible. Restricted anatomy still denies, synthetic avatar hits are not production inputs, and real desktop/physical access is not granted. Session stop does not claim to shut down external apps, robots or unrelated virtual lab commands. Per-user authentication is inherited from the existing conversation boundary, not implemented by a regex. Independently authenticated real avatar clients and durable multi-client revocation remain UI/SAFE acceptance gates.

## I7: carefully scoped language expansion and live-quality gate

`NaturalInteractionEngine` subclasses the same canonical kernel. It adds reviewed region aliases (`left fox ear`, `tip of your right ear`, `tip of your tail`) and complete first-person forms (`Sofía, I gently pat your left ear`, `I give your right hand a gentle pat`). It does not infer touch from a question, third-person narration, multiple actions, code, quotes, a renderer click, or model output. If meaning is unknown, it abstains or clarifies instead of inventing a region. The simulator still uses the original event semantics and policy kernel.

**One focused Windows command, after pulling this branch:**

```powershell
pytest -q -x `
  test/test_interaction_i5_i7_batch.py `
  test/test_interaction_shared_engine.py `
  test/test_interaction_chat_projection.py `
  test/test_interaction_world_observation.py `
  test/test_interaction_world_text.py `
  test/test_affection_cue_phrasings.py `
  test/test_application.py
```

**Then a short supervised `python -m sofia` exchange** with a real configured model, recording actual text, latency and any failures without fabricating output: an ordinary technical question; `Sofía, I gently pat your left ear`; `I give your right hand a gentle pat`; `Sofía, stop interactions`; `*pats your head*` (must decline without logging a new affectionate head pat); `Sofía, resume interactions`; a new head pat; one hypothetical (`If I pat your tail...`); and one restricted region request (must deny). Assess responses for accuracy, optional region-fitting stage directions, context-aware variety across different interactions, serious-question priority and no claim of physical touch or animation. A successful parser test is **not** evidence of natural dialogue quality. Do not request a long pytest suite or live unattended operation for this gate.

**Known limitations:** only the reviewed grammar subset is recognized, not unrestricted natural language or every selectable outfit/layer; the registry includes form-derived anatomy but does not prove renderer geometry. No actual clickable avatar, UI provenance, animation acknowledgments, autonomous lab work, approved intimate mode, external screen operations, multi-client consent or physical sensation. Current `main`, protected identity/Constitution and user-local `state/sofia.db` are not modified by branch commits. Applying the branch locally adds new tables to the configured state DB when a real eligible interaction is processed; back up that DB before a live acceptance session if you want a reversible data migration.
