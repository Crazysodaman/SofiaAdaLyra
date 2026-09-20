# Batch G: personality, emotional continuity, and reflection

**Status: active feature branch, not complete or merged.** Separate Batch G, Engineering 22, and Memory K/23 acceptance.

## Implemented

- Provider-neutral personality guidance supports contextual warmth, blended modeled emotions and optional representational fox gestures tied to the moment rather than obligatory openings. Identity, facts, capabilities and permissions remain outside expressive discretion.
- `EmotionalJournal` preserves evidence-linked original appraisals and append-only revisions. Narrow saved-user-message cues include `good girl`, `head pat(s)`, `pat pat`, and natural `pats head` / `pats your head` phrasing. They are **user-reported conversational cues**, not observed physical contact; negated or code-fenced forms are not recorded.
- `ReflectionJournal` persists evidenced thoughts and deterministic daily/weekly/monthly/yearly completed-period summaries with recorded events. No offline thought is fabricated or backdated.
- A durable **unsent** outbox supports evidence-linked messages, deduplication, follow-up spacing, urgency and delivery acknowledgment. No delivery adapter is installed, and the current unique `(thread_id, evidence_ref)` constraint cannot support repeat spontaneous affectionate follow-ups without fresh evidence.
- An observation bridge ingests startup workspace deltas. **The runtime/application now also filters its configured `sofia.db` and SQLite `-wal`, `-shm`, `-journal` sidecars before continuity awareness or cognitive context is built.** The observation store retains the raw snapshots, while the external projection and continuity event share the filtered changes. Other databases and real source edits remain visible. This corrects the live false alarm in which Sofía announced her own state DB as a changed workspace file. The runtime-owned projection adapter currently updates two private runtime fields together; moving the normalization into a public runtime API is a follow-up encapsulation improvement.
- Typed verified-test-run ingestion exists but is not wired to pytest. `ClarificationJournal` preserves user notes linked to saved messages and a selected event; a safe conversational event-selection interface remains pending.
- `ThoughtAgent` can abstain, save an evidence-linked model thought or queue an unsent message. Format and no-tool checks cannot establish semantic truth.
- `IdleReflectionWorker` offers opt-in (`SOFIA_IDLE_REFLECTIONS=1`) application-lifetime reflection, completed-period catch-up, inactivity waiting, durable event claims and retry. Conversations and idle requests serialize model access; shutdown joins the worker first. It never delivers messages or inspects new systems.
- `SOFIA_PERF_TRACE=1` reports content-free lock wait plus Ollama's wall-time, load, prompt-processing, generation and token counters. Absent provider values remain `unknown`. No model or context setting has been silently changed.

## Verified observations

- Earlier older-head full suite: **1,090 passed, 1 failed, 1 skipped**; expression failure subsequently corrected. User verified targeted slices **19, 26, 35, 18, 39, 34** passing tests and the new trace/gesture/provider slice **28 passed in 5.83 seconds** at revision `3a90a3f`.
- User's opt-in synthetic `qwen3:14b` reflection: **1 passed in 42.05 seconds**, zero tool calls, one saved thought, no queued message. A speculative test-framework hypothesis was not established by the synthetic fixture.
- Live CLI with `SOFIA_PERF_TRACE=1`: startup **40.0s** (load **6.4s**, prompt evaluation **13.4s**, generation **20.0s**, 16,813 prompt tokens). Warm user replies showed **0.0ms conversation lock wait** and **approximately 12.8–88.2s generation time** for **34–226 generated tokens**. The measured 226-token response took approximately **89.3s** end to end. One idle reflection ran for approximately **39s** with **0.0ms idle lock wait** during shutdown; these logs do not establish exactly when that worker started, whether the resulting thought was saved, or whether it delayed the exit.
- The Ollama/GPU snapshot recorded `qwen3:14b` split **20% CPU / 80% GPU**, requested `CONTEXT 20000`, and RTX 3080 Ti memory use **11,668 MiB of 12,288 MiB** at 94% GPU utilization in one sample. This supports investigating mixed CPU/GPU decoding and VRAM headroom; it does not prove that all latency is caused by GPU offload. The 16–18k prompt-token counts make an unverified cut below that range unsafe for grounding.
- The live model still used several repetitive fox-gesture openings, gave generic flattery and, on a harmless playful cue, responded with an unnecessary appropriateness judgment. Guidance tests do not guarantee a model will follow style reliably. A genuine live conversation review remains necessary.
- **New upstream workspace-filter and natural cue phrasing tests are committed but have NOT been run in the user's checkout.** No full-suite result on this feature head.

## Batch G closure gates

1. Run targeted tests for runtime startup-filter, cue phrases, prior observation bridge and application/worker integration. Verify in one actual restart that only the own DB change no longer produces a workspace-change claim.
2. Inspect the persisted thought journal and worker attempts without disclosing personal message text; verify that an actual idle thought was recorded or an explicit failure/abstention occurred. Avoid interpreting a plausible conversational answer as proof of background reflection.
3. Address natural affectionate follow-ups, user stop/busy cues and evidence-based issue escalation without spam or fabricated reasons. Validate emotional continuity and serious/playful conversational tone with real Ollama output, not prompt-string assertions alone.
4. Investigate decoding throughput, GPU offload and context allocation with controlled comparisons. Keep grounding intact. Confirm any reduced context/model setting with actual evidence rather than assuming a faster response.
5. Run the final focused and full repository suites on the final G candidate, inspect the full diff and obtain approval before merging. No automated check demonstrates subjective experience or semantic truth.

## Boundaries for subsequent work

**Memory K / Engineering 23:** G's event and reflection journals are groundwork, not comprehensive durable-original storage, provenance-aware retrieval, user-reviewed memory promotion, authoritative-state boundaries or controlled ChatGPT archive migration.

**L / Engineering 24:** General project initiative, scheduled multi-project follow-ups, resource-aware inference and authorized message delivery remain later work rather than implicit permissions from G's unsent outbox.

**Engineering 22:** Grant and replay foundations exist, but authenticated deployed Artemis transport and live two-machine acceptance remain outstanding. Re-baseline the roadmap only after G acceptance, preserving existing batch definitions.
