# CA-1203: bounded cognition source-data channel

Date 2026-10-14. `CognitiveContextAssembler` now caps the model-visible
USER-role JSON quotation of eligible MEM, historical import and filesystem
inspection records using explicit route-dependent approximate source byte
budgets (fast 8 KiB, standard/default 16 KiB, deep/open 32 KiB, verify
48 KiB). A source item is either fully admitted or fully omitted. No
fabricated excerpt, partial factual quote or privilege is produced.

Budget pressure preserves upstream eligibility order: reviewed memory,
historical conversation then filesystem results. A typed
`source_budget_omission` record reports omitted counts without copying
the omitted source content or claiming that it was verified. Original
canonical records and permissions remain unchanged. Regression tests
exercise huge hostile imported history, source ordering, precise budget
limits, and preservation of actual current user turns.

Byte ceilings are guardrails, **not exact LLM token usage guarantees**.
The full Phase 00 CA-1203 requirement still needs dynamic allocation
across emotion/style, workspace, project, factual evidence, user turns
and model-output reserve, with quality/provenance/p95 measurements,
real-model validation and independent Gate 4 review.
