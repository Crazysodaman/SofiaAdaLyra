# V18 interim objective: all 780 planned tasks through Gate 4

Approved owner direction, 2026-10-13. This changes the **development reporting target**, not requirements or final production acceptance.

Gate 1 means every original requirement is satisfied. A design/research-only task needs a completed, independently reviewed deliverable, not a code module. Source review alone does not suffice.

Gate 2 means proper integration into actual runtime and canonical component owners, or for design-only tasks a finalized approved decision incorporated in relevant specifications. No placeholder or competing writer.

Gate 3 means reviewed source-to-effect, security, privacy, user consent, test scope, failure/recovery paths, performance and cost. Fix discovered defects before passing.

Gate 4 means task-specific tests pass at a pinned revision, including relevant unit, integration, regression, failure, Windows/Linux and installed-wheel verification. Original tasks demanding a real-world performance trial or a three-day test still demand that trial as part of their original acceptance, even though general production Gate 5 is deferred.

Gates 5–6, general live deployment and final production sign-off, are deferred until separately authorized.

The single status authority remains docs/development/v18-task-evidence.json. Optional ordered gate4_proofs fields on its existing task entries store Gate 1–4 reviewer, commit and SHA-256 content-bound evidence. Gate 4 also requires a CI run reference, exact SHA and specific tests. The read-only checker verifies shape and local evidence; external GitHub run authenticity and relevance require independent review. No plain boolean or arbitrary CI badge can award Gate 4.

Generate JSON for 700 original CA tasks plus the 80 separately governed ML/GA tasks, with Markdown phase progress:

    python -m sofia.verify.v18_gate4 --repo . --output gate4-progress.json --markdown-output gate4-progress.md

Baseline source status: 433 unassessed; 261 partially wired; 6 code-present-unverified. These are triage categories rather than independently accepted gate completions. Prior 30+50 source audits reviewed requirements, not 80 finished tasks. First eliminate CI blockers, then close code-present and partial-wiring gaps and reconcile the unassessed tasks. No live host, single-writer transfer, or production acceptance changes are authorized.

Supplemental Gate 4 proofs for ML-001..040 and GA-001..040 are stored as evidence overlays in docs/development/v18-supplemental-gate4-proofs.json. The original CA ledger is not duplicated or rekeyed. The dashboard reports the 700 and 80 separately and the complete 780-item target together.

## Evidence-only status policy

The owner has withdrawn historical four-proof packets as completion counts.
Keep receipts intact for audit trails, but Gate 4 is **only independently
verified original-task acceptance**, not source path existence, ledger metadata
or green CI badges. The dashboard now reports `overall_gate4_verified` and
`overall_gate4_remaining` only. Historical recorded proof totals do not
appear as completion counts, nor satisfy dependency or release gates.

The present read-only verifier **cannot independently authenticate a human
reviewer or actual host acceptance**. Consequently no existing task is
automatically awarded Gate 4 from these artifacts. Before future award,
implement a separately authenticated independent reviewer/evidence process
that checks every original requirement, actual production behavior, pinned
CI selectors, and task-specific real host/soak requirements. Until then,
zero means *not certified by this evidence mechanism*, not *no code exists*.
