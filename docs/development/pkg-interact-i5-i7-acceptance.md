# INTERACT I5–I7 acceptance: evidence, stop, language and real conversation

**Branch:** `feature/pkg-interact-shared-engine`. **Status: candidate code, NOT accepted.** Sparks reported **3 import-order tests passed in 9.10 seconds and 143 focused interaction/application tests passed in 63.75 seconds** at `a8fb5c8`. Two subsequent supervised CLI reviews have not established live acceptance; the second review, at `a8fb5c8`, showed a false completed compound gesture and an almost verbatim affectionate response to a head pat **after an exact stop**. See [the live evidence](pkg-interact-live-cli-review.md). Guarded-response changes made afterward have NOT been verified on Windows or with a live model. The full suite stays after headless text acceptance.

## I5: source-linked representational body evidence

`InteractionLedger` links classified user-described gestures to a saved user-message ID, session, content digest, timestamp, registry, region and gesture in persistent SQLite. All registered regions can be recognized: `accepted` means recognized virtual input, NOT consent, approval, positive emotion or physical sensing. Stop/ambiguous gestures are not recorded as accepted; a replay never becomes another fresh gesture. Synthetic test fixtures cannot write production evidence. Sensitive anatomy is redacted from synthetic trace exports for privacy, not automatically denied. Previously recorded emotional history remains intact.

## I6: stop and honest action reports

An exact, separately issued `Sofía, stop interactions` or `Sofía, resume interactions` updates the session-wide durable barrier. A stopped gesture is denied for **every** body region and does not become a fresh affectionate journal entry. In the new candidate, exact stop/resume and recognized gestures while stopped have deterministic persisted replies derived from ledger outcomes **before model inference**, rather than asking the model to narrate an authoritative control or denied pat. Compound messages containing controls also receive explicit nonexecution replies. Replaying an old denied ID after resume never makes it fresh. The CLI route does not authenticate an avatar or offer multi-client/global revocation.

## I7: narrow grammar, contextual response and repetition

`NaturalInteractionEngine` recognizes reviewed single-action forms and aliases; it abstains from hypothetical, quoted or unsupported compound inputs. A new response guard also prevents plainly compound first-person action sentences from being fed to the model as if both gestures happened: it saves the original turn but records neither gesture and asks for separately issued actions. No blanket anatomy ban exists; a recognized action never obligates Sofía to like it. The forearm-versus-ear cue collision is fixed. Read-only hypotheticals are prompted to answer each named gesture specifically without generic AI disclaimers. Accepted-gesture prompts discourage reusing previous assistant wording and the same closing question. **That repetition guidance is not a general output-similarity guarantee; another supervised live model test is required.** A model-stated specific boundary is not independently persisted or enforced yet; the exact session-wide stop is.

## Next focused Windows run, after clean CLI exit and fast-forward pull

```powershell
pytest -q -x `
  test/test_interaction_live_stop_repetition.py `
  test/test_interaction_import_order.py `
  test/test_interaction_live_claims.py `
  test/test_interaction_live_discussion.py `
  test/test_interaction_contextual_all_regions.py `
  test/test_interaction_region_cue_collision.py `
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

**Supervised CLI review after tests pass:** Use a fresh `python -m sofia` process and send the following as distinct turns: one ear pat, one hand pat, an exact stop, one head pat while stopped, exact resume, a new head pat, a hypothetical question about tail/chest, one combined ear-plus-hand gesture, and a mixed stop/resume message. The stopped head pat must not trigger a narrated gesture or recycle the preceding affectionate paragraph. The compound gesture must explicitly report neither was recorded. The **new** post-resume head pat should receive distinct, conversationally appropriate wording, with no invented physical sensation or avatar animation. Naturalness is a human-reviewed gate. If the result fails, inspect exact outputs and update the relevant layer, not the whole package blindly.

Preserve the configured state database and existing backup; no reset is part of this check. Only after live acceptance run the agreed full suite, then review the draft PR and any merge separately. No real avatar pointer, screen rights, autonomous lab work or physical sensing are claimed.
