# Phase 09: atomic LIFE/RUN creative admission

Source basis: actual `SelfDirectedLifeCoordinator.schedule_artifact`,
`LifeStore` and `DurableWorkStore.enqueue` in current `main`.

## Audited defect

An eligible creative work request previously wrote a RUN QUEUED job, then
independently inserted a LIFE one-use authorization, then independently linked
the RUN job back to the LIFE project. A process crash or write failure could
leave a runnable queue item with no matching permission or a project with no
linked job, leading to stale review state and potential duplicate attempts.

## Full production repair of this path

`DurableWorkStore.enqueue` now accepts a narrowly internal transactional
owner callback, executed after RUN job/event insertion but *before the one
SQLite commit*. The callback is only useful for owners sharing the exact
canonical `sofia.db`; it cannot mint or widen a SAFE operator grant.
`LifeStore.provision_artifact_job` validates ACTIVE project status, an
existing canonical goal, one unsettled RUN job maximum, exact request
identity/hash consistency, and owning project identity before inserting a
one-use LIFE creative authorization and the linked job in that same
transaction. A callback failure rolls back RUN/job/event/LIFE authorization
together. A pre-existing fingerprint may not be rebound to changed payload or
request. Once an actual RUN job settles, a new revision can be submitted.

The execution worker continues to require the independent existing SAFE/
CapabilityGateway checks at the moment of execution, consumes the one-use
request, and requires a real file receipt. This transaction does not increase
autonomy privilege, bypass grants, or touch external hosts.

## Deferred evidence

Unexecuted regression cases cover atomic success, forced failure after the
RUN insert with zero orphan rows, concurrent pending admission refusal, and
a verified second revision after the first job completes. The user's
test-last instruction remains in force. The rest of Phase 09 is **not**
declared finished; evidence-to-interest, multi-step milestone refinement,
detailed critique and host/live acceptance are still outstanding.
