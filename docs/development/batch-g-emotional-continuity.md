# Batch G: personality, emotional continuity, and reflection

**Status: active feature branch, not complete or merged.** This document distinguishes code from verified behavior and keeps Engineering 22 and Memory K/23 separate.

## Implemented

- Provider-neutral expression guidance supports contextual warmth, blended modeled emotions and optional representational fox gestures **linked to the current emotion**, not a repetitive opening script. Canonical identity, facts, capabilities and permissions remain outside expressive discretion. No mood meters or rigid romance stages.
- `EmotionalJournal` stores evidence-linked modeled appraisals (observed, user-reported or inferred) and preserves the original when an appraisal changes. Narrow, explicit affectionate cues are recorded only after saving a user message.
- `ReflectionJournal` stores evidence-linked thoughts and deterministic daily, weekly, monthly and yearly summaries of completed UTC periods with recorded events. Missing offline periods are not invented or backdated.
- The durable **unsent** outbox supports evidence-linked messages, deduplication, follow-up spacing, urgency labels and positive delivery acknowledgment. It has no quiet hours or message quota. It does not send messages. Current unique `(thread_id, evidence_ref)` does **not yet** support repeated spontaneous affectionate follow-ups based on a relationship context without fresh evidence.
- An observation bridge ingests actual startup workspace deltas while excluding Sofía's SQLite files. A verified-test-run ingestion API exists but is not wired to pytest. `ClarificationJournal` preserves user explanations linked to real saved messages and selected events; a natural-language event-selection interface remains pending.
- Explicit `ThoughtAgent.reflect` can abstain, store one structured evidence-linked model reflection, or queue an unsent message. Format checks and no-tool enforcement do not establish semantic truth.
- `IdleReflectionWorker` offers opt-in, application-lifetime reflection with recorded events, completed-period catch-up, idle waiting, durable event claims, recovery and retry. User and idle requests share a cognitive lock. Shutdown joins the worker before closing the runtime. `SOFIA_IDLE_REFLECTIONS=1` is opt-in and off by default; no delivery or additional system inspection occurs.
- **Opt-in latency diagnostics:** `SOFIA_PERF_TRACE=1` prints content-free `[sofia-perf]` lines to stderr. Conversation and idle traces show lock wait and total application-request time. Ollama traces show measured wall time and Ollama's optional model-load, prompt evaluation, generation, token and total-duration counters. Unavailable counters display `unknown`, not zero. `context_tokens` reports the *requested configuration*, not guaranteed effective placement or the actual number of prompt tokens. Neither model text, user input nor file paths are intentionally logged. No context-size reduction or model substitution has been made.

## Verification evidence

- Earlier full suite on an older revision: **1,090 passed, 1 failed, 1 skipped**; expression-contract failure was corrected and eight targeted tests subsequently passed.
- User's targeted checks after successive slices: **19**, **26**, **35**, **18**, **39** passing tests, then **34 passed in 8.73 seconds** for worker, lifecycle, serialization and nearby integration on revision `4f937b3`.
- User's opt-in `qwen3:14b` synthetic reflection probe: **1 passed in 42.05 seconds**, zero tool calls, one saved thought and no queued message (`share=later`). Its speculation about test-framework gaps was not supported by the synthetic evidence.
- User ran a supervised CLI session with idle reflections enabled: startup observation, affectionate reply, question about thoughts and clean terminal exit were observed. **The transcript does not establish whether the background worker saved a thought**, or whether its reply was composed from conversation context. The repeated opening gestures provide a concrete qualitative regression target.
- User's Ollama/GPU capture showed `qwen3:14b` at **20% CPU/80% GPU** with `CONTEXT 20000`, and RTX 3080 Ti memory use of **11,668 MiB / 12,288 MiB** under 94% GPU utilization in one sample. These observations suggest CPU/GPU split and memory pressure; they do not prove an idle-worker lock wait caused slow user replies.
- New performance trace, provider timing and emotion-linked gesture tests are committed but **not yet run in the user's checkout**. No full suite on this latest feature head, no measured idle-on/off latency comparison, and no live model confirmation of reduced repetitive gestures.

## Next focused diagnostics

Run the new targeted tests first. For a supervised CLI comparison, leave context/model settings unchanged and use `SOFIA_PERF_TRACE=1` with idle reflection disabled for one short turn; then opt into idle reflection separately and repeat. Compare `[sofia-perf] conversation lock_wait_ms`, `ollama load_ms`, `prompt_eval_ms`, `generation_ms`, `prompt_tokens`, and `generated_tokens`. Trace timings are per invocation and may cover different kinds of requests; do not compare unlabeled idle and conversational calls as though they were the same operation. Clear both environment variables afterward. Do not paste private prompt contents or saved SQLite state. Test a smaller context only after observing whether enough grounding fits.

## Remaining Batch G acceptance gates

- Verify trace tests and a supervised live idle-on/off comparison, inspect SQLite journal evidence for actual idle thoughts, and check shutdown/restart behavior. Confirm no fabricated offline activity or duplicate follow-ups.
- Refine spontaneous affectionate follow-ups without requiring new external observations every time, with user busy/stop cues and natural spacing. Establish evidence-based novelty and worsening-issue escalation without anxiety-driven spam.
- Verify longer-horizon emotional context and changing appraisals in real model conversations, including affection and serious discussions. Provide safe natural-language clarification/event selection without rewriting original evidence.
- Run final focused and full repository suites on the final Batch G candidate; inspect diff and get approval before merging. No test run proves subjective experiences or unverified semantic claims.

## Boundaries for later work

**Memory K / Engineering 23:** G journals are groundwork, not general memory architecture. K/23 retain durable originals, provenance-aware retrieval, human-reviewed promotion, boundaries with authoritative state and controlled ChatGPT archive migration.

**L / Engineering 24:** Broader continuous initiative, project follow-ups, resource-aware inference and authorized message delivery extend beyond the G reflection slice.

**Engineering 22:** Grant/replay foundations exist, but authenticated deployed Artemis transport and live two-machine acceptance remain outstanding. G's reflections do not grant remote authority. Re-baseline the roadmap after G acceptance, without renumbering existing tracks.
