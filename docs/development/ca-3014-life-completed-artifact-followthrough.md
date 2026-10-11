# CA-3014: finished RUN artifact verification independent of creation selection

`SelfDirectedLifeCoordinator.tick` previously invoked automatic
`_settle_personal_project` only when `select_activity` picked a project
for *new optional work*. That selector correctly denies new spending
after daily CPU/wall/storage budget is consumed, but it also blocked
source-based verification of work that RUN had already completed.
An artifact could remain forever unreviewed after a successful job
because it had exhausted its own creation budget.

The canonical LIFE tick now first inspects existing **ACTIVE, personally
owned** projects with proven COMPLETED RUN jobs and linked artifact receipt.
When foreground user work, high resource pressure and explicit quiet time
allow, it settles at most ONE eligible project's original job per tick,
using the existing `_settle_personal_project` objective verification path.
It may validate/complete real artifact bytes and issue grounded evidence
even when the previous creation spent the daily budget. It does **not**
draft a new revision outside budget; draft generation is set to `None`
unless normal budget conditions are satisfied.

To prevent one inconclusive project monopolizing every background wake,
only source artifacts with no prior independent review, independently valid
and automatically completable evidence, or a bounded eligible revision
are considered. Missing/unlinked receipts, unknown criteria and
personal subjective decisions remain in the existing operator review
queue. Daily-draft admission receipts prevent a failed revision from being
attempted on every scheduler tick. All original RUN grants, source IDs,
preferences and reviewed-completion checks remain authoritative.

Regression cases are authored for actual completed Project Forge work
with exhausted storage budget and optional quiet-time deferral.
They were not run. Real Windows/host acceptance and the broader multi-day
LIFE feedback contract remain open; CA-3014 is not accepted.
