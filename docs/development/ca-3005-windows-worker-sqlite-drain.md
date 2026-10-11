# CA-3005: bounded RUN worker shutdown before Windows SQLite cleanup

The source-audited Windows `pkg_verify` failure involved a temporary
`sofia.db` directory that could not be deleted due to an open handle.
`SofiaApplication.shutdown` already closes ConversationService and UI
draft-store handles, but its LIVE LIFE and AutonomousWorkCoordinator
owners both called `TaskExecutionManager.close(wait=False)`.
`ThreadPoolExecutor.shutdown(wait=False)` signals cancellation but can
return while worker jobs or Future completion callbacks continue issuing
SQLite updates. A host shutdown could therefore close core state and
release the temp directory while another thread still held or reopened
`sofia.db`.

The real shared `TaskExecutionManager` now supports a **bounded drain**
after setting cancellation events and invoking nonblocking executor
shutdown. A Condition notifies only AFTER the canonical RUN completion
callback has completed its database transition and removed its active job.
A waiting close refuses to report success if active callbacks do not
drain within an explicit finite timeout, rather than sleeping blindly or
silently ignoring errors. A closed manager refuses new ticks/submissions.

Both production application owners now call the same drained close with
a 30-second timeout. If work is uncooperative, shutdown raises instead
of claiming the state is safe for Windows backup/deletion. This does not
erase or automatically replay UNCERTAIN RUN mutations.

Regression cases were authored for real ThreadPoolExecutor concurrency,
post-completion SQLite handle operations, timeout failure, and the
canonical production close path. They have NOT been run. Actual Windows
`WinError 32` reproduction, ephemeral DB unlink evidence and CI
acceptance remain pending, so CA-3005 is **not accepted**.
