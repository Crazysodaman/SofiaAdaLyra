# CA-2216: canonical-source operator diagnostics for LIFE

The prior LIFE coordinator offered a pending-review list but no exact
read-only explanation covering all of: idle, quiet by choice, blocked,
awaiting permission, uncertain RUN state, reviewing, and finished.
That made an operator infer current status from repeated model text,
rather than original canonical sources.

`SelfDirectedLifeCoordinator.operator_diagnostics(now,limit)` projects
existing `LifeStore` project states, RUN job statuses, LIFE selection/quiet
receipts and idempotent source-linked RUN observations. It reports the
source table, original job ID/status/reason, last original RUN event ID,
current counts and whether completion was actually verified. The projection
is bounded and read-only, cannot schedule work or create a second status
owner, and reports deliberately chosen inactivity separately from absence
of projects. User-assigned and collaborator projects cannot enter this
self-owned local scope.

This closes a concrete source-wiring gap in CA-2216, but the task remains
unaccepted without source-unit and live operator trace proof. It does
not invent cognition or claim user-facing tray integration is present.
Tests authored, not executed as instructed.
