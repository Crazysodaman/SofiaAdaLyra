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

## Additional zero-history control

The executable source-selection study now includes the explicitly requested
**no-retrieval baseline** alongside the previous topical and recency-only
ablations. Its selector returns no evidence, so it earns credit only on
correctly abstained unsupported questions. Known-source questions are scored
as misses, not as silently hallucinated correct answers. The new tests assert
source-ID errors per case and forbid interpreting this deterministic retrieval
control as model answer-quality evaluation.

This remains a preparatory **synthetic single-session** experiment. Licensed
benchmark-adapted samples, authorized multi-session retrieval, answer and
downstream-task quality measurements, independent source review, and
reproducible full acceptances remain outstanding. CA-1205 is **not Gate 4**.

## Authorized multi-session source-selection evaluator

The production retrieval selector can now be checked against an explicit
multi-session, audience-scoped synthetic fixture:

    python -m sofia.verify.v18_memory_dataset --fixture test/fixtures/v18-memory-multisession-v1.json --output scored.json

Each fixture declares session, principal, audience, source timestamps and
required/forbidden source IDs. Wrong-scope and future messages are excluded
before invoking production retrieval. The runner measures strict source
coverage against recency-only and no-retrieval controls and emits only source
identifiers, a SHA-256 fixture digest and deterministic counts. It never emits
raw conversation text in the scored artifact. Synthetic-only admission is
intentional; this is not a live private-memory ingestion interface.

This is **three self-authored smoke examples**, not an official LongMemEval or
LoCoMo dataset, nor an LLM answer-quality or downstream success evaluation.
Licenses are self-declared, not independently authenticated. CA-1205 still
requires adapted licensed benchmark data, more cases, long-term memory
integration, quality scoring, review and authorized host trials.
