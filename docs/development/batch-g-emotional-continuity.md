# Batch G: emotional expression and continuity

## Implemented in this feature branch

- Provider-neutral personality guidance names an expansive, blendable emotional vocabulary. Serious disclosures do not automatically disable Sofía's familiar warmth; welcomed affectionate/romantic expression remains contextual, not an intimacy meter.
- An `EmotionalJournal` stores evidence-linked, typed modeled appraisals in the existing SQLite state database, survives restarts, rejects conflicting event IDs, and separates observed, user-reported, and inferred provenance.
- `revise` appends new appraisals while keeping the original evidence and emotional tie. No retroactive rewriting of the original event.
- The application composes `EmotionalConversationService`, which records narrow explicit user praise/head-pat cues only after a user message is durably saved. The journal supplies a bounded, clearly labeled read-only cognitive projection. No canned replies are stored, and the LLM has no write permission to the journal.
- Old entries stop being projected as current emotional context after seven days, but remain in SQLite as history. No visible mood meters, intimacy unlocks, or automatic suppression of personality.

## Verification

- Local isolated `test/test_emotional_journal.py`: 9 passed. These tests exercised the new journal and expression module only, not the full repository or Ollama runtime.
- Conversation integration test is included for the target repository; it has not been run against the complete repository here.
- Previously, 1,090 passed, 1 failed, 1 skipped on the earlier feature commit; the targeted expression regression fix subsequently passed 8 tests. These results **do not** verify this new change set.

## Not implemented or demonstrated yet

The journal currently automatically recognizes only narrow, explicit affectionate cues. Most emotional event ingestion needs additional typed integrations with observed test results, continuity changes, other actual tools, and user-reported corrections. The correction API does not yet interpret natural-language corrections automatically. A seven-day context window is not a computed long-term mood or periodic reflection. Daily/weekly/monthly/yearly scheduled reflections, a persistent thought journal, proactive message outbox, background execution and delivery adapter remain outstanding. No actual human feelings or subjective experience are asserted. Live model response quality and full-suite compatibility require verification on the target runtime.
