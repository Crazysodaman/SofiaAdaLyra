# INTERACT I5–I7 combined acceptance: evidence, stop, language

**Branch:** `feature/pkg-interact-shared-engine`. **Status: candidate code committed, NOT accepted.** Sparks's preceding I4 run at `eb73357` reported **20 passed in 4.19 seconds**. That is not verification of subsequent I5–I7 changes. The agreed full-suite run stays after the INTERACT text/headless checkpoint.

## I5: source-linked body events, not imaginary physical sensing

`InteractionLedger` uses the configured SQLite state file and a new `interaction_evidence` table keyed to the actual saved USER-role message ID and session ID. It stores a content digest, timestamp, accepted region/verb and registry version. Denied/unknown region identifiers are not saved in the region/verb columns; original user text remains in the conversation store. The ledger is derivative evidence, not a second conversation, physical event, durable preference or subjective emotional experience. Retries of identical saved messages return `acknowledged`, with no second event or emotion candidate; conflicting reuse of a message ID fails visibly. Synthetic `InteractionLab` fixtures do not write to this ledger. Existing `EmotionalJournal.record_user_cue` remains the sole producer of its legacy head-pat appraisal: the interaction ledger stores separate factual action evidence, not a second emotional event. No emotion is imposed on every non-head gesture. Broad revised emotional appraisals remain an emotion/MEM integration gate.

## I6: session stop and per-turn permission

Exact saved-user commands `Sofía, stop interactions` and `Sofía, resume interactions` toggle a durable per-session stop barrier outside the LLM. A stopped session denies new represented body gestures and suppresses legacy head-pat journaling. A denied request replayed after resumption is still a replay. Controls use SQLite transactions and unique saved-message IDs, even when a model/personality is unavailable. Resumption does **not** establish blanket consent: only a new explicitly user-described ordinary **text-only virtual gesture** is eligible. Restricted regions still deny. A separate conversation has a separate stop state; this does not implement global/multi-client revocation, stop unrelated lab work, authorize private regions, control real tools or establish live avatar identity.

**Identity limit:** the current CLI/conversation boundary saves messages tagged USER but does **not independently authenticate the human typing them**. This ledger assumes a trusted host only passes genuine saved USER-role turns. A remote client or actual avatar must implement and test authenticated actor provenance and globally enforceable revocation under UI/SAFE before production use; neither a regex nor this database creates that authority.

## I7: conservative grammar and live-quality gate

`NaturalInteractionEngine` subclasses the canonical semantic/policy kernel. It adds reviewed region aliases (`left fox ear`, `tip of your right ear`, `tip of your tail`) and complete first-person forms (`Sofía, I gently pat your left ear`, `I give your right hand a gentle pat`). It does not infer contact from imperatives addressed to Sofía, questions, third-party narration, multiple actions, code, quotes, synthetic clicks or model output. Hypothetical/quoted head pats also cannot slip into the legacy affection journal. Unknown meaning abstains or clarifies; actual event semantics and simulated pointer semantics remain shared.

**One focused Windows command, after pulling the INTERACT branch:**

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

**Then a short supervised `python -m sofia` exchange** with a real configured model, recording actual replies, latency and failures: an ordinary technical question; `Sofía, I gently pat your left ear`; `I give your right hand a gentle pat`; `Sofía, stop interactions`; `*pats your head*` (must decline without recording a new head-pat appraisal); `Sofía, resume interactions`; a new head pat; a hypothetical (`If I pat your tail...`); and a restricted-region request (must deny). Review for grounded accuracy, optional region-appropriate stage directions, natural variation, serious-question priority, and no claims of sensed physical contact or actual animation. A passing parser test cannot establish conversational quality. Do not request the long full-suite run or unattended deployment at this gate.

**Remaining limits:** Only the reviewed grammar subset is supported, not unrestricted language or every clothing layer. Form-derived anatomy is not renderer geometry. No actual clickable avatar, authenticated UI event, animation acknowledgment, autonomous lab work, approved private-mode access, real desktop operations, full multi-client consent, or physical sensation. `main`, protected identity/Constitution and the user-local `state/sofia.db` are not modified by remote GitHub commits. Running a real eligible gesture on the local branch **will add interaction tables to the configured state DB**; make a user-approved backup first if reversible migration matters. RUN is a separate branch and does not install a service through this PR.
