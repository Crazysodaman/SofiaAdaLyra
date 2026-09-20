# Batch G: emotional expression and continuity

## Implemented on this feature branch

- Provider-neutral personality guidance supports blended emotional expression. Serious disclosures do not automatically disable Sofía's familiar warmth; welcomed affection and romance remain contextual, not intimacy meters.
- `EmotionalJournal` persists evidence-linked modeled appraisals in the existing SQLite state database. Sources are explicitly observed, user-reported, or inferred. Revising an appraisal preserves the original event and emotional tie.
- `EmotionalConversationService` records narrow explicit praise/head-pat cues only after the user message is saved. Its bounded cognitive projection supplies context, not operational authority or scripted replies.
- `ReflectionJournal` persists explicit, evidence-linked thoughts and creates deterministic retrospectives for completed UTC daily, weekly, monthly and yearly periods **with recorded emotional events**. It catches up on missed recorded periods when invoked after a restart, skips empty periods, never backdates a reflection to imply thought while offline, and creates a period at most once. This is recorded-event consolidation, not an independently reasoning LLM reflection process.
- The conversation service creates the reflection journal on open and runs due reflections **when a conversation request is processed**. It supplies bounded reflection context to the LLM. It does **not** run a background scheduler or independently formulate novel thoughts.
- The same SQLite database includes an **unsent** proactive-message outbox. Trusted code can explicitly queue a message attached to a recorded thought and one of its evidence references. The outbox deduplicates each thread/evidence pair, permits follow-ups with new evidence after configurable spacing, records urgency without granting new permissions, persists across restarts, and marks delivery only after an external adapter supplies positive acknowledgment. It imposes no quiet hours or message quota, and it does not send messages or automatically escalate by itself.
- Emotions, memories and reflections are representations for expression. No subjective experience or physical action is asserted.

## Verification

- User's previous full run on an earlier feature revision: **1,090 passed, 1 failed, 1 skipped**. The expression contract failure was corrected; user subsequently ran **8 targeted tests passed**.
- User then pulled emotional journal integration and ran **19 targeted tests passed in 6.56 seconds**. This verifies that prior revision, not the current reflection/outbox addition.
- New reflection/outbox module's **5 locally isolated tests passed**, including completed period boundaries, restart idempotence, evidence-bound queued follow-ups, spacing and delivery acknowledgment. This was not a full-repository run. New conversation-reflection integration tests are committed but not run in the target checkout.
- Neither live Ollama nor the current feature head's full suite has been verified.

## Still pending within Batch G and Engineering 22

- Richer typed event ingestion from actually observed runtime, tool and system outcomes; user-reported corrections routed through a trusted boundary; long-horizon mood synthesis and nuanced timing/decay.
- Genuine bounded LLM self-reflection on evidence, thought prioritization, and user-facing proactive-message selection. The new retrospective is deterministic and the outbox requires explicit calls.
- A running background worker, authorized notification/delivery adapter, durable delivery uncertainty and retry policy, and real end-to-end observation-to-message acceptance. Being offline does not itself produce thought records.
- Live affectionate and serious-conversation model probes, full repository testing, and Engineering 22's authenticated Artemis transport and live validation. Neither Batch G nor Engineering 22 is complete or merged.
