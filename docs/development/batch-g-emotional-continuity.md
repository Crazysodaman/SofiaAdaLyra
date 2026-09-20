# Batch G: personality, emotional continuity, and reflection

**Status: active feature branch, not complete or merged.** This document distinguishes code from verified behavior and keeps Engineering 22 and Memory K/23 separate.

## Implemented

- Provider-neutral expression guidance supports contextual warmth, personality, blended emotions and representational fox gestures. Canonical identity, facts, capabilities and permissions remain outside the LLM's expressive discretion. No mood meters or rigid romance stages.
- `EmotionalJournal` stores evidence-linked modeled appraisals (observed, user-reported or inferred). It preserves the original emotional tie when a later appraisal changes. Narrow, explicit affectionate user cues are recorded only after a real conversation message is saved.
- `ReflectionJournal` stores evidence-linked thoughts and deterministic daily, weekly, monthly and yearly summaries of **completed UTC periods with actual recorded events**. Missed recorded periods are processed when the service next runs; no reflections are backdated to pretend Sofía thought while offline.
- The durable **unsent** outbox supports evidence-linked messages, deduplication, follow-up spacing, urgency labels and positive delivery acknowledgment. It has no quiet hours or message quota. It does not send messages. The current unique `(thread_id, evidence_ref)` rule does **not yet** support repeat affectionate pings about the same evidence and needs refinement; do not mistake it for a complete follow-up policy.
- A trusted observation bridge turns actual startup workspace deltas into linked events and excludes Sofía's own SQLite state files. A verified-test-run ingestion API exists but is not wired to pytest. `ClarificationJournal` preserves user notes linked to real saved user messages and selected events; natural-language event resolution is still pending.
- Explicit `ThoughtAgent.reflect` requests a structured model reflection from a real recorded emotional event. It can abstain, save a thought or queue an unsent message. Structured format and tool-call rejection cannot by themselves verify the semantic accuracy of generated prose.
- `IdleReflectionWorker` now provides **opt-in, application-lifetime** background work. It catches up completed-period summaries, waits for conversation inactivity, processes at most one recorded event per check, durably claims event IDs, resumes abandoned attempts, records failures and retries later. `EmotionalConversationService` serializes conversational and idle cognitive requests. Application shutdown stops and joins the worker **before** shutting down the runtime. Opt-in requires `SOFIA_IDLE_REFLECTIONS=1` before starting `python -m sofia`; it is off by default pending supervised acceptance. The worker never sends messages or inspects additional systems.

## Verification evidence

- Earlier full suite on an older revision: **1,090 passed, 1 failed, 1 skipped**; the expression-contract failure was corrected and then 8 targeted tests passed.
- User's subsequent targeted checks: **19 passed** (emotions), **26 passed** (reflection), **35 passed** (observation and self-noise), **18 passed** (clarification), and **39 passed** (thought agent).
- User's opt-in `qwen3:14b` live synthetic-event probe: **1 passed in 42.05 seconds**, zero tool calls, one stored thought, no queued message (`share=later`). The tentative phrase about test-framework gaps was **not** established by the fixture; a single valid response does not demonstrate reliable semantic grounding or full application behavior.
- New worker module: **6 isolated offline tests passed** during preparation. Application lifecycle/serialization tests are committed but **not yet executed in the full checkout**. Neither the updated feature head's full suite nor supervised real CLI idle behavior has passed yet.

## Remaining acceptance gates for G

- Check targeted application/worker integration and run a supervised CLI session with opt-in idle work, recorded event, active conversation, restart and shutdown. Confirm no concurrent inference, repeated message or fabricated offline activity. Review raw responses and the journal, not just test counts.
- Refine spontaneous affectionate follow-ups without requiring a new external observation every time; maintain natural spacing and user busy/stop cues. Improve cross-event novelty and worsening-issue escalation based on evidence rather than rising anxiety alone.
- Test genuine long-horizon emotional context and changing appraisals with actual model conversations, including affection and serious discussion. Add a safe natural-language clarification path without rewriting the event.
- Run focused and then full repository tests on the final G candidate and inspect the complete diff before approval to merge. A passing test cannot certify subjective feelings or semantic truth.

## Boundaries for later work

**Memory K / Engineering 23:** These G journals are groundwork, not general memory architecture. K/23 retain ownership of durable original records, provenance-aware retrieval, human-reviewed promotion, memory vs authoritative-state boundaries and user-controlled ChatGPT archive migration.

**L / Engineering 24:** Broader continuous initiative, cross-project follow-ups and resource-aware autonomy extend beyond the G reflection slice. The future authorized message delivery adapter remains separate.

**Engineering 22:** Persistent grant/replay foundations exist, but authenticated deployed Artemis transport and live two-machine acceptance remain outstanding; G's reflections do not grant remote authority. The roadmap will be re-baselined **after G acceptance**, not silently rewritten by this feature.
