# CA-2205: canonical RUN expires never-started jobs despite busy cognition

Before this correction, `TaskExecutionManager.tick` called `poll` then
returned immediately if foreground work was busy or resource pressure high.
The only queued deadline check was buried inside the executor admission
loop, itself bounded by available worker slots and eligible handlers.
Consequently a queued job could remain apparently pending past its deadline
forever if the user was busy, pressure stayed high, or capacity was zero.

The canonical `DurableWorkStore.expire_unstarted` now scans bounded
**queued-only** deadline-expired work and transitions it to FAILED with a
real RUN event and original reason `deadline_expired_before_start`.
`TaskExecutionManager.tick` always executes this reconciliation before
the busy/resource-pressure return. The LIFE source-event reconciler already
observes resulting RUN failure events through its existing journal.

An operation in RUNNING, BLOCKED or WAITING_APPROVAL may have begun an
external effect or require an owner's review. This correction **does not**
relabel those statuses as harmless failure or replay them. It also does not
propose goals, start LLM inference, grant permissions, or create an alternate
job scheduler. Explicit proof of an unstarted state is required.

Source regression cases cover expiration while busy, idempotent source
events, and avoidance of false clean failures for running/pending approval.
They were authored but NOT executed. CA-2205 remains partial until full
restart/deadline and actual Windows acceptance proves the behavior.
