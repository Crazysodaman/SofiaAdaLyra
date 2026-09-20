# Batch G: emotional expression and continuity

## Implemented on this feature branch

- Provider-neutral personality guidance supports blended emotional expression. Serious disclosures do not automatically disable Sofía's familiar warmth; welcomed affection and romance remain contextual, not intimacy meters.
- `EmotionalJournal` persists evidence-linked modeled appraisals in the existing SQLite state database. Sources are explicitly observed, user-reported, or inferred. Revising an appraisal preserves the original event and emotional tie.
- `EmotionalConversationService` records narrow explicit praise/head-pat cues only after the user message is saved. Its bounded cognitive projection supplies context, not operational authority or scripted replies.
- `ReflectionJournal` persists explicit, evidence-linked thoughts and creates deterministic retrospectives for completed UTC daily, weekly, monthly and yearly periods **with recorded emotional events**. It catches up on missed recorded periods when invoked after a restart, skips empty periods, never backdates a reflection to imply thought while offline, and creates a period at most once. This is recorded-event consolidation, not an independently reasoning LLM reflection process.
- The conversation service creates the reflection journal on open and runs due reflections **when a conversation request is processed**. It supplies bounded reflection context to the LLM. It does **not** run a background scheduler or independently formulate novel thoughts.
- The same SQLite database includes an **unsent** proactive-message outbox. Trusted code can explicitly queue a message attached to a recorded thought and one of its evidence references. The outbox deduplicates each thread/evidence pair, permits follow-ups with new evidence after configurable spacing, records urgency without granting new permissions, persists across restarts, and marks delivery only after an external adapter supplies positive acknowledgment. It imposes no quiet hours or message quota, and it does not send messages or automatically escalate by itself.
- The typed `observation_bridge` records real workspace snapshot deltas after a baseline exists, using a deterministic evidence ID, aggregate change counts, and a linked reflection. Application startup connects its actual `runtime.workspace_changes` to this bridge. Missing baselines do not become invented changes. Neither intent nor cause is inferred from a changed or removed file.
- Trusted test-run producers can explicitly call `record_verified_test_run` with a run ID, result counts, timestamp, and actual evidence reference. This API does **not** inspect a terminal or automatically ingest pytest output; caller provenance must be established by a real test runner. `record_user_reappraisal` is an explicit typed API for append-only appraisal revision, not an automatic free-text correction detector.
- `ClarificationJournal` stores a user's explanation separately from the event and its emotional appraisal. The application exposes `clarify_event(event_id=..., message_id=...)`, which requires a real persisted **user** message in the active session and an explicitly selected existing event. Repeated calls are idempotent; conflicting records are rejected. Its bounded projection includes the user note, original emotions, current emotions, and any latest recorded revision reason. A clarification alone does not reclassify emotions or verify the user's interpretation. **No event-selection UI or natural-language correction matcher is wired up yet.**
- `ThoughtAgent` can be invoked by trusted application code through `reflect_on_event(event_id=...)`. It requests one structured, evidence-linked LLM reflection, validates the result, stores it or abstains, and can queue an **unsent** message. This is not an autonomous loop. Its structured-output checks do not establish the semantic truth of generated text.
- `test/test_thought_agent_live_ollama.py` is an **opt-in real-model probe** that tests the Ollama provider and thought agent with a synthetic fixture in a temporary SQLite database. It prints raw model output for human review. It neither alters Sofía's persistent state nor sends messages. A passing result tests response structure and persistence, **not** full application behavior or semantic grounding.
- Emotions, memories and reflections are representations for expression. No subjective experience or physical action is asserted.

## Verification

- User's previous full run on an earlier feature revision: **1,090 passed, 1 failed, 1 skipped**. The expression contract failure was corrected; user subsequently ran **8 targeted tests passed**.
- User pulled the emotional journal integration and ran **19 targeted tests passed in 6.56 seconds**.
- User pulled the reflection journal and outbox integration and ran **26 targeted tests passed in 7.03 seconds** on revision `7e5a4c8`.
- User pulled the observation bridge and self-noise exclusion and ran **35 targeted tests passed in 17.30 seconds** on revision `f494a2b`.
- User pulled the clarification journal and ran **18 targeted tests passed in 7.16 seconds** on revision `a69534e`.
- User pulled the thought agent and ran **39 targeted tests passed in 9.89 seconds** on revision `bc103ce`.
- The opt-in live-model probe has been committed but has **not** been run on the user's Ollama installation. Neither the current head's full suite nor Artemis live validation has been completed.

## Still pending within Batch G and Engineering 22

- Complete typed ingestion from other actually observed runtime, tool and system outcomes; verified test-run producer wiring; a safe conversational event-selection and clarification interface; long-horizon mood synthesis and nuanced timing/decay.
- Validate real Ollama reflection output and its qualitative grounding before enabling unattended generation. The CLI and thought agent share a runtime; concurrent generation and shutdown need an explicit serialized lifecycle contract and tests before starting a background worker.
- Autonomous event triggers, cross-event novelty and priority, deferred/retried follow-ups, an authorized notification/delivery adapter, and real end-to-end observation-to-message acceptance. Being offline does not itself produce thought records.
- Live affectionate and serious-conversation model probes, full repository testing, and Engineering 22's authenticated Artemis transport and live validation. Neither Batch G nor Engineering 22 is complete or merged.
