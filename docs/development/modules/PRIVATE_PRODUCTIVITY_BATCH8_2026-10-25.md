# Sofía 2.0: optional module Batch 8, development evidence

**Modules:** `MOD-FINANCE`, `MOD-CALENDAR`, `MOD-COMMUNICATIONS`, `MOD-PRODUCTIVITY`.
**Version:** `0.1.0` each. **Status:** ALPHA (source + focused tests only). **SDK contract:** `1.0` shape, pending production installation.

## Capability contracts and boundaries

| Module | Capability | Profile | Data class | Exact scope |
| --- | --- | --- | --- | --- |
| MOD-FINANCE | `finance.review_budget_aggregates.v1` | ADVISORY | private / sensitive finance | Integer-cents monthly category aggregates, total spending, cashflow, budget variance; no bank identifiers, transaction details, transfers or payment methods |
| MOD-CALENDAR | `calendar.review_schedule_conflicts.v1` | ADVISORY | private calendar | Opaque event IDs, busy status, offset-aware start/end and half-open schedule-overlap detection; no attendee/title/location or provider mutation |
| MOD-COMMUNICATIONS | `communications.review_delivery_receipts.v1` | OBSERVE | private communications | Opaque message IDs and recipient reference consumed but not returned, source-supplied queued/sent/delivered/failed/bounced/cancelled states; never claim read proof, delivery authentication, messages sent, or receipt consent |
| MOD-PRODUCTIVITY | `productivity.review_task_dependencies.v1` | ADVISORY | personal tasks | Opaque task IDs, priorities, dependency cycles, ready/waiting/overdue classifications; no reminders, agenda changes or Core goal mutations |

All capabilities are deterministic Python handlers with strict field sets, limited list lengths, timezone-aware freshness, no effects, and no direct network/filesystem/DB/subprocess calls. Payload source references **are not authentication**. Neither copying these files nor importing the modules registers an executable authority grant.

## Provisional operating and resource profiles

The modules export `PROFILE` and `RESOURCES` constants for review. They are **not signed platform-enforced profiles**. CPU: 50/50/50/75 millicores respectively. RAM: 32/48/32/48 MiB respectively. GPU: 0. Portable stateless placement proposed. Exact budgets are provisional, not benchmarked or verified at live host steady-state.

Maintenance plan: read-only dependency checks and capability shape checks at install, bounded probe payload and freshness validation, zero retry side effects, quarantine on repeated validation exceptions or faulty handler, owner-reviewed semantic version pin, rollback to previous signed digest, no raw personal-data logs, revoke modules' narrowly scoped source permissions on uninstall. Owner and Platform must decide retention periods and approved source-to-module mapping separately for **finance**, **calendar**, **communications** and **tasks**. A consent grant for one does not authorize another.

## Local verification

Command: `PYTHONPATH=src python -m pytest -q test/test_module_batch8.py`.
Result: **80 passed**, offline Python. Exact local SDK/Platform constructor shapes reproduced as test-only stand-ins. Tests include malformed data, booleans masquerading as integers, duplicate identities, cycle detection, future/stale evidence masking, receipt chronology, half-open event overlaps, privacy field rejection, and `CapabilityRequest` handler dispatch.

## Release blockers

1. Production SDK/Platform registration via trusted, signed module package manifest and exact reviewed factory.
2. Live admission of authenticated origin/recipient and per-domain privacy permissions. Source refs are merely hints.
3. Process isolation and crash/timeout recovery; restart-safe invalidation and audited effect receipts.
4. Signed module and maintenance profiles, digest pinning, installation/upgrade/rollback and resource telemetry.
5. Full repository integration/CI, fault injection, access revocation, privacy review, and owner-approved real-host trials.
6. Real provider adapters: no Firefly, calendar, mail/chat, or task source is connected by this batch.

**Do not advance to BETA, RELEASE CANDIDATE, or PRODUCTION READY without independent evidence for these gates.**
