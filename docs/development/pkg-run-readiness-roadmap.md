# PKG-RUN | branch readiness roadmap

**2026-09-21 | draft PR #3 | baseline head `e48019a72f3600bef9e08bda90eb0c42dc35c486`.** Companion `pkg-run-always-on-contract.md`; this branch contains a 14-package variant of root `ROADMAP.md` while PR #4 proposes 16. Reconcile both master rosters before merge; this branch must not silently remove SOCIAL/AVATAR or replace the original 13 identifiers.

## Existing code and actual evidence

R1 disabled-by-default `OpportunityPolicy` and SQLite atomic `PeriodicThoughtGate` with cooldown, daily cap, UTC quiet hours, busy/evidence checks and explicit `PeriodicThoughtRunner.tick`. A host callback-confirmed recorded event ID is required before marking `reflected`; attempts alone are not thoughts. Tests exist in branch but **RUN R1 Windows/actual GitHub checkout/live tests have NOT been reported**. No daemon, service, 24/7 uptime, auto-start or actual unattended reflection is established.

## Work and acceptance gates

1. Inspect and pin existing opt-in runtime idle worker, ACT unsent outbox, MEM journal, authorization/stop, CORE restart continuity and host startup. Reuse **one** optional reflection opportunity loop; never accidentally create a second scheduler or attribute processing to a stopped process.
2. Verify R1 focused tests on actual branch and Windows using a disposable SQLite copy: concurrency atomicity, cooldown/day rollover, UTC/local quiet-hours, busy/resource caps, stop/revoke, duplicate event/restart and callback failure. Keep any periodic activity opt-in and no guaranteed reply or fabricated constant thinking.
3. Design an **external host supervisor** with independently observed process health, boot start, controlled restart/backoff, clean/unexpected stop classification, readiness endpoint and persisted truthful timestamps/sequence; define Windows host/service account, storage, updates and monitoring before installing. Self-report from the model cannot establish uptime.
4. Run supervised staged deployment tests: service install on agreed host, startup/reboot, Ollama not ready, network outage, forced kill, disk full, corrupt state, upgrade/rollback, duplicate outbox, clock changes, STOP and supervisor failure. Confirm foreground interaction and gaming/compute resource budget remain acceptable.
5. Record an agreed real 24/7 observation window, actual start/end, observed gaps/alerts, restart recovery, supervision and backup restoration. Only **after independently accepted** Discord D0–D4 and RUN soak may NET general web/search be designed/enabled under a *separate grant*. Avatar artwork is not a RUN prerequisite.

## User decisions at RUN gate

Actual deployment host (Artemis VM versus another node), supervisor/service technology, service account and secrets storage, observation period and outage alert route, preferred real local quiet hours, opt-in reflection frequency and resource budget, whether any unsolicited contact is allowed (default no). These are not inferred from test fixture IDs or prior local installs.

**Exit:** R1 candidate only; no Windows/full-suite/live supervisor/soak or genuine 24/7 acceptance. No service installed, merge/deploy or general internet authority.
