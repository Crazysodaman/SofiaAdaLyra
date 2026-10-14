# V18 interim objective: all original 700 CA tasks through Gate 4

Approved owner direction, 2026-10-13. This changes the **development reporting target**, not requirements or final production acceptance.

Gate 1 means every original requirement is satisfied. A design/research-only task needs a completed, independently reviewed deliverable, not a code module. Source review alone does not suffice.

Gate 2 means proper integration into actual runtime and canonical component owners, or for design-only tasks a finalized approved decision incorporated in relevant specifications. No placeholder or competing writer.

Gate 3 means reviewed source-to-effect, security, privacy, user consent, test scope, failure/recovery paths, performance and cost. Fix discovered defects before passing.

Gate 4 means task-specific tests pass at a pinned revision, including relevant unit, integration, regression, failure, Windows/Linux and installed-wheel verification. Original tasks demanding a real-world performance trial or a three-day test still demand that trial as part of their original acceptance, even though general production Gate 5 is deferred.

Gates 5–6, general live deployment and final production sign-off, are deferred until separately authorized.

The single status authority remains docs/development/v18-task-evidence.json. Optional ordered gate4_proofs fields on its existing task entries store Gate 1–4 reviewer, commit and SHA-256 content-bound evidence. Gate 4 also requires a CI run reference, exact SHA and specific tests. The read-only checker verifies shape and local evidence; external GitHub run authenticity and relevance require independent review. No plain boolean or arbitrary CI badge can award Gate 4.

Generate JSON with all 700 tasks and Markdown phase progress:

    python -m sofia.verify.v18_gate4 --repo . --output gate4-progress.json --markdown-output gate4-progress.md

Baseline source status: 433 unassessed; 261 partially wired; 6 code-present-unverified. These are triage categories rather than independently accepted gate completions. Prior 30+50 source audits reviewed requirements, not 80 finished tasks. First eliminate CI blockers, then close code-present and partial-wiring gaps and reconcile the unassessed tasks. No live host, single-writer transfer, or production acceptance changes are authorized.
