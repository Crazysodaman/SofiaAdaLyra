# Phase 01 / 09: durable source-linked LIFE observation of RUN outcomes

The current `DurableWorkStore` owns the authoritative work state and an
append-only `autonomous_work_event` table. `LifeStore` knows which original
RUN jobs belong to each personal project. The existing LIFE review projection
does not persist whether a blocked, failed, cancelled, approval-waiting, or
uncertain RUN transition was ever observed, so restarts can repeatedly show
the same transition without a stable processing receipt.

The production LIFE store now maintains a *derived observation journal*
`life_run_outcome_observation` keyed by the **original RUN event_id**.
Inside a single SQLite transaction, it reads only explicitly linked RUN
jobs, inspects their real persisted source events and inserts each relevant
RUN transition exactly once. This includes COMPLETED, FAILED, BLOCKED,
CANCELLED, UNCERTAIN and WAITING_APPROVAL. Both latest RUN state and its
original source events remain owned by RUN; LIFE observations are
append-only, auditable evidence, not competing work state.

`SelfDirectedLifeCoordinator.tick` reconciles persisted events **before**
optional work selection (even while busy or over resource budget) and again
after RUN dispatch. It reports the number of newly observed source events.
Open job arbitration now counts approval-waiting and uncertain jobs rather
than selecting another job in their place. Nothing here automatically
retries an uncertain effect, grants scope, changes the project status,
or treats a finished RUN job as independently validated creative work.
The existing objective checker and SAFE authorization remain in place.

Regression source cases cover durable idempotency, multi-status transitions,
busy/pressure operation and no side-effect replay. No tests were run,
and no live host, state relocation, pairing or operator grant was changed.
More extensive multi-day project and external-effect recovery are still
separate V18 acceptance work.
