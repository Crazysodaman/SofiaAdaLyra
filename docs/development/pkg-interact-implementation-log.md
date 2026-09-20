# PKG-INTERACT: implementation log and acceptance gates

## Lab meaning and one-world rule

**Sparks's lab is a persistent virtual location Sofía can enter and work in, not a simulator.** The [world-location contract](pkg-interact-world-location-contract.md) supersedes earlier ambiguous wording. `LabWorld` stores actual software-state rooms, actors, objects, inventory and transitions; `InteractionLab` is only an isolated synthetic **test harness**, never evidence of work in her location. Text and future authenticated avatar clients must refer to the same body regions, world object IDs and operation results. None of this is a physical room or real equipment control.

## I1: shared body-interaction semantics

Canonical `Embodiment` drives the versioned `InteractionEngine`, including explicit fox anatomy, form-derived human regions and mapped restricted regions. `from_text` and synthetic `from_lab_pointer` yield a common semantic event/decision for supported inputs. Distinct source/provenance and event IDs are retained. `InteractiveConversationService` extends the existing emotional conversation service; accepted gestures can receive optional, natural textual expression with no renderer. The intentionally narrow explicit grammar abstains on discussion, hypotheticals, quotes and multi-actions. Private regions deny by default; no adult-mode grant, real click classification or sensed contact exists. Existing head-pat journal behavior remains; comprehensive durable body-interaction journaling is not implemented.

**Verified by Sparks on Windows at `7175835`:** `test_interaction_shared_engine.py`, `test_interaction_chat_projection.py`, `test_application.py`, `test_affection_cue_phrasings.py`: **59 passed in 51.61 seconds**. Focused, not full-suite or live model evidence.

## I2: synthetic interaction test harness

`InteractionLab` runs bounded, chronological text and synthetic resolved-pointer fixtures through the same interaction kernel, with fresh replay, a local stop barrier and redacted decision-only exports. It cannot access production world state, user memories, model, network, UI or physical equipment. It is distinct from Sofía's real virtual lab location.

## I3: persistent virtual lab and text actions

`LabWorld` has durable on-disk room/actor/object state and atomic audited, replay-safe actions: enter, leave, pick up, put down, begin/finish virtual equipment work. An authored starter room has actor Sofía, a screwdriver and an oscilloscope. New action attempts require new unique request IDs; replaying a denied request returns the original denial even after the world changes. A separately saved and explicitly addressed user command may issue a world operation via `world_text.py` and project its verified result into the existing conversation. Narration such as `Sofía is working on some lab equipment` is not an action; work being marked finished is not a verified repair. The lab's sibling SQLite DB is Git-ignored, with narrowly scoped startup-noise filtering that preserves unrelated file changes.

**Verified by Sparks on Windows at `84695a6`:** `test_interaction_lab.py`, `test_interaction_world_location.py`, `test_interaction_world_text.py`, `test_interaction_world_internal_noise.py`, `test_interaction_chat_projection.py`, `test_application.py`: **44 passed in 53.05 seconds**. An earlier failing test reused a denied pickup request ID; the corrected test asserts old-denial replay and success only for a genuinely new request. The replay guard itself was not weakened. This is focused test evidence, not live CLI or full acceptance. The user's locally modified `state/sofia.db` has not been reset by Git operations.

## I4: read-only virtual-location observations (committed, tests pending)

`world_observation.py` recognizes a small explicit set of saved user queries, including `Sofía, where are you?`, `Sofía, what are you holding?`, `Sofía, what's in the lab?` and `Sofía, what are you working on?`. A status question does **not** provision a missing lab, issue `WorldAction` or manufacture equipment. It projects actual persisted room, held tools and equipment states into the existing chat request and honestly reports an absent lab. Equipment state `work_in_progress` is **not** proof of continuous activity while Sofía is offline or between messages. Observation lists are bounded with truncation signals. `test_interaction_world_observation.py` covers absent state, across-restart facts, nonquery abstention, chat projection and lack of action side effects. **New I4 tests have not run on Sparks's Windows checkout.** The world constructor may still run its normal existing-schema initialization on an existing file; this slice claims no world operations or provisioning from queries, not a general-purpose immutable SQLite connection.

## Open acceptance gates

- Run I4 tests with representative I2/I3 and application regressions. A short supervised **live** CLI/Ollama exchange should verify actual language for entering, holding, working, asking status and a denied/missing-lab case; judge expressive naturalness separately from structural tests.
- Implement sourced, privacy-aware body-event records using the current `EmotionalJournal` without double head-pat logging, followed by independently enforced session/client stop, permission and replay protection. Expand accurate grammar and review each canonical region/clothing layer without misclassifying narration as touch.
- Sofía-initiated work must pass a separately reviewed trusted-action gate. A model sentence or persisted work-in-progress marker does not prove actual continuous action, repaired equipment or authority.
- Actual avatar renderer, authenticated pointer/object hit tests, pose/mirror/occlusion and animation acknowledgments remain **not run**. A real client must use the same body and world engine, not create a second personality or screwdriver. External-screen operations and physical BODY actions have separate independent authority gates.
- No full pytest during these small slices. Sparks requested the coordinated full-suite checkpoint **after INTERACT**; MEM follows package acceptance. `main` remains unchanged and PR #2 stays draft until evidence supports release.
