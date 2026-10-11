# Phase 01: independent artifact objective checks (partial implementation)

**Coding-only checkpoint, untested.** The registry lives in `src/sofia/life/validation.py`; `SelfDirectedLifeCoordinator.inspect_artifact_objectives(project_id, artifact_id=...)` is a **read-only** entrypoint that reuses the existing authorized `CreativeExplorer.verified_preview` and project/audience-linked revision.

## What can pass without a model judging itself

- `revision.content_sha256` must match the actual file, with size equal to `revision.byte_size` and at most 64 MiB for this inspection.
- An explicitly specified `text_contains:<literal>` on TEXT/STORY/CODE checks the real UTF-8 bytes for the literal.
- An explicitly specified `min_bytes:<positive-integer>` checks real file size.
- Natural-language creative goals such as “make a compelling story” return `UNKNOWN`. Wrong type, oversized material, missing or changing content cannot silently pass.
- `eligible_for_independent_completion` requires at least one checked objective and **all** pass. This is **not** a success receipt or automatic goal transition.
- There is no LLM evaluator in this registry and no way for a model to install additional validator functions at runtime.

## Missing before genuinely autonomous completed-project claims

1. The objectives and specific machine-checkable criteria must be reviewed by an independently authorized actor before execution. A self-authored `min_bytes:1` criterion does not prove that an original complex brief was accomplished.
2. Record evaluator identity, schema/version, experiment hypothesis, exact source receipts and objective-level evidence. Link them to LIFE, GOALS and truthful MEMORY promotions through a checked event ID.
3. Make creative authored output and revision plans tool-free and bounded, with appropriate resource budgets. Do not use the default placeholder SVG/sine/cube as proof of artistic quality.
4. Add replay-safe, permission-scoped completion and critique transitions. The present adapter only reports structural checks and never calls `complete()` automatically.
5. Validate inputs and behavior at the user's later testing stage. No test or live acceptance was executed in this coding pass.

**Safety:** This deliberately opts for `UNKNOWN` over false confidence. Programmatic evidence of bytes/structure never becomes permission, consent, taste, emotional truth or proof of meeting subjective objectives.
