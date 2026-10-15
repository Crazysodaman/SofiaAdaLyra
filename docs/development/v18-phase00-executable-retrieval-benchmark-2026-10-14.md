# CA-1205: executable internal long-term recall benchmark, preparatory stage

This first executable stage tests 36 **synthetic** non-sensitive single-session
recall tasks, 12 each for three **inspired** families. They are not the
published LongMemEval (500 questions), LoCoMo (10 annotated conversations),
or a standardized agent-environment dataset. The script imports the actual
production `_retrieve_specific_conversation` selector, supplies original
`ConversationMessage` evidence, and compares it with two simple
recency-only selector ablations.

Run `python -m sofia.verify.v18_memory_benchmark --output /tmp/memory-benchmark.json`.
It emits exact sample count, source-ID oracle, strict required source coverage,
outdated-source conflicts, unsupported-question abstention, error categories,
per-family scores, per-example outcomes and full reproduction metadata.
This is a source-selection evaluation, **not answer correctness, user trust,
model comprehension or real memory persistence**.

External research taxonomy: LongMemEval, Wu et al. (ICLR 2025),
https://github.com/xiaowu0162/LongMemEval; LoCoMo, Maharana et al.
(ACL 2024), https://github.com/snap-research/locomo. No upstream
dataset contents are copied or claimed scored.

CA-1205 remains **open**, since scoring adapted actual official samples,
multi-session authorized retrieval, corrected facts, read-time evaluation
with each real route, cross-host cold restarts, latency/abstention/quality
trials and independent review require more than this internal unit
benchmark. No Gate 4 evidence is added by this stage.
