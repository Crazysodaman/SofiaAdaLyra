# Batch G: emotional expression and continuity

## Implemented on this feature branch

- Provider-neutral personality guidance supports blended emotional expression. Serious disclosures do not automatically disable Sofía's familiar warmth; welcomed affection and romance remain contextual, not intimacy meters.
- `EmotionalJournal` persists evidence-linked modeled appraisals in the existing SQLite state database. Sources are explicitly observed, user-reported, or inferred. Revising an appraisal preserves the original event and emotional tie.
- `EmotionalConversationService` records narrow explicit praise/head-pat cues only after the user message is saved. Its bounded cognitive projection supplies context, not operational authority or scripted replies.
- `ReflectionJournal` persists explicit, evidence-linked thoughts and creates deterministic retrospectives for completed UTC daily, weekly, monthly and yearly periods **with recorded emotional events**. It catches up on missed recorded periods when invoked after a restart, skips empty periods, never backdates a reflection to imply thought while offline, and creates a period at most once. This is recorded-event consolidation, not an independently reasoning LLM reflection process.
- The conversation service creates the reflection journal on open and runs due reflections **when a conversation request is processed**. It supplies bounded reflection context to the LLM. It does **not** run a background scheduler or independently formulate novel thoughts.
- The same SQLite database includes an **unsent** proactive-message outbox. Trusted code can explicitly queue a message attached to a recorded thought and one of its evidence references. The outbox deduplicates each thread/evidence pair, permits follow-ups with new evidence after configurable spacing, records urgency without granting new permissions, persists across restarts, and marks delivery only after an external adapter supplies positive acknowledgment. It imposes no quiet hours or message quota, and it does not send messages or automatically escalate by itself.
- The typed `observation_bridge` records real workspace snapshot deltas after a baseline exists, using a deterministic evidence ID, aggregate change counts, and a linked reflection. Application startup connects its actual `runtime.workspace_changes` to this bridge. Missing baselines do not become invented changes. Neither intent nor cause is inferred from a changed or removed file.
- Trusted test-run producers can explicitly call `record_verified_test_run` with a run ID, result counts, timestamp, and actual evidence reference. This API does **not** inspect a terminal or automatically ingest pytest output; caller provenance must be established by a real test runner. `record_user_reappraisal` is an explicit typed API for append-only clarification tied to an actual user-message ID, not an automatic free-text correction detector.
- Emotions, memories and reflections are representations for expression. No subjective experience or physical action is asserted.

## Verification

- User's previous full run on an earlier feature revision: **1,090 passed, 1 failed, 1 skipped**. The expression contract failure was corrected; user subsequently ran **8 targeted tests passed**.
- User pulled the emotional journal integration and ran **19 targeted tests passed in 6.56 seconds**.
- User pulled the reflection journal and outbox integration and ran **26 targeted tests passed in 7.03 seconds** on revision `7e5a4c8`. This does not validate subsequent changes.
- The new observation bridge and six new tests have passed local Python syntax compilation; both new local files' Git hashes match the exact blobs pushed to GitHub. **The new tests have not yet run in the user's full checkout.** Neither live Ollama nor the feature head's full suite has been verified.

## Still pending within Batch G and Engineering 22

- Complete typed ingestion from other actually observed runtime, tool and system outcomes; verified test-run producer wiring; user-reported corrections routed through a trusted conversational boundary; long-horizon mood synthesis and nuanced timing/decay.
- Genuine bounded LLM self-reflection on evidence, thought prioritization and user-facing proactive-message selection. The current retrospective is deterministic and the outbox requires explicit calls.
- A running background worker, authorized notification/delivery adapter, durable delivery uncertainty and retry policy, and real end-to-end observation-to-message acceptance. Being offline does not itself produce thought records.
- Live affectionate and serious-conversation model probes, full repository testing, and Engineering 22's authenticated Artemis transport and live validation. Neither Batch G nor Engineering 22 is complete or merged.
