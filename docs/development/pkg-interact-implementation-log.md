# PKG-INTERACT: implementation log and acceptance gates

## Slice I1: shared headless semantics (focused tests passed)

The existing canonical `Embodiment` drives `InteractionEngine`. Explicit fox ears and tail are checked against its feature/anatomy data; human body part names are **form-derived coverage**, not proof of rendered geometry. The versioned registry contains left/right parts, ear/tail subregions, and explicitly restricted regions. Unknown forms or new canonical appendages fail visibly instead of disappearing.

One `InteractionEvent` and one `InteractionDecision` serve `from_text` and `from_lab_pointer`. Equal actor/region/gesture/phase produces equal semantic meaning, policy status and candidate modeled reactions for supported fixtures. Source, event ID and evidence refs differ. Pointer inputs are already-resolved *synthetic* gestures; a real mouse click is not magically a pat. Real hit testing, authenticated input, renderer acknowledgments and physical sensation are not supplied.

`InteractiveConversationService` extends `EmotionalConversationService` and adds trusted decision context to the LLM request without altering the original persisted message or introducing a second bot, emotional journal or independent persona. Textual `*...*` cues are optional modeled expression, not confirmed renderer output or subjective feeling. The short, explicitly addressed text grammar abstains on discussion, negation, hypotheticals, quotes, code and composite phrases. Ambiguous regions clarify; private regions deny by default; no adult-mode authorization is implied. Existing narrow head-pat journaling remains; new durable interaction events are **not** implemented or accepted.

**Observed local verification supplied by Sparks:** On Windows, branch `feature/pkg-interact-shared-engine` at its I1 revision `7175835`, the command `pytest -q -x test/test_interaction_shared_engine.py test/test_interaction_chat_projection.py test/test_application.py test/test_affection_cue_phrasings.py` reported **59 passed in 51.61 seconds**. This was a focused run, not the full suite, live Ollama review or renderer verification. The user's locally modified `state/sofia.db` was preserved during branch switching.

## Slice I2: isolated replayable lab (committed, untested)

`src/sofia/interaction/lab.py` adds an in-process `LabScene`/`LabStep`/`InteractionLab` with validated synthetic inputs, distinct IDs, chronological order, a 64-step maximum, deterministic fresh replay, a stop barrier and a redacted decision-only trace export. It invokes the **same** `InteractionEngine` for explicit text and synthetic resolved pointer inputs. Its text fixture calls `from_text` (which identifies the *input modality* as `user_text` internally); the lab neither persists that event nor presents it as an observed real user interaction. No raw synthetic text or private-region identity is exported. Stop state lives only within one scene. This is not durable production revocation or authenticated UI input.

`test/test_interaction_lab.py` covers text/pointer semantic/policy/reaction-option equivalence, discussion abstention, stop and replay isolation, unfinished/cancelled pointer phases, private-region redaction and denial, invalid/duplicate/out-of-order fixtures and step-budget rejection. **This newly added test file has not yet been executed on Sparks's Windows checkout.** Source commits alone are not test evidence.

## Remaining acceptance and nonclaims

- Run the new lab tests with the existing I1 and representative application tests; repair genuine failures without weakening the assertions. Do a short supervised real CLI review across playful, technical and declined interactions. Behavioral naturalness is assessed separately from structural assertions.
- Improve grammar and aliases without treating anatomy discussion as touch. Audit every actual canonical part and selectable clothing layer. Reconcile per-region verbs and modeled expression with revised canonical data.
- Build source-linked durable event capture with the existing `EmotionalJournal`, avoiding double-logging current head pats, lab fixtures and duplicate retries. Implement independently enforced session stop/permissions, consent/revocation and evidence corrections before claiming production replay safety.
- For eventual real avatar: explicitly select a renderer and trusted input channel; implement geometry/hit tests, occlusion, transparency, click-through isolation, gesture-sequence classification and renderer acknowledgments. Call the same semantic engine, not a second personality. Actual UI tests remain `not run` until a client exists.
- Scope external screen operations, intimate-mode handling, voice and hardware separately through their relevant authority gates. The agreed full-suite checkpoint remains **after INTERACT**; no long suite is requested during these small slices. PKG-MEM follows after package acceptance.
