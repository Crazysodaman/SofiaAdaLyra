# V18 Phase 03/04 executable contract decisions (2026-10-15)

Author: OpenCode development executor.
Status: **design decisions implemented as side-effect-free executable contracts,
with focused tests.** This does not assert live-host acceptance, production
Gates 5–6, or independent human review.

These tasks were `[DESIGN/RESEARCH]` in the immutable master source. Per the V18
Gate 4 standard, a design task's Gate 1 deliverable is a completed decision and
its Gate 2 requirement is that the decision be incorporated into the relevant
specification. To make Gate 4 meaningful (not a test that merely checks a file
exists), each decision below is expressed as a pure, typed, fail-closed contract
module with behavioral tests, and adopted here as the specification.

The contracts open no database, hold no authority, perform no effect, and
introduce no competing canonical writer. They are decision kernels for the
owning subsystems to call.

## CA-3703 — saga-style operation classification

Decision: every named external operation is classified into exactly one of
`fully_reversible`, `compensable`, `retryable_idempotent`,
`externally_irreversible`, or `unknown`. The classification lives in
`src/sofia/ops/saga.py` (`EffectClass`, `OperationEffect`, `classify_operation`).

Concrete examples (the original requirement's list), as declared in the module:

| Operation | Effect class | Rationale |
| --- | --- | --- |
| `discord.message.send` | externally_irreversible | may already have been read remotely |
| `git.commit.local` | fully_reversible | unpushed local commit can be reset |
| `git.push` | externally_irreversible | published history is visible; only a revert commit is possible |
| `home_assistant.service.call` | unknown | generic service calls may actuate hardware; local request keys do not prove external deduplication |
| `jmri.turnout.set` | unknown | repeating a command can re-energize physical hardware without confirmed receiver-side deduplication |
| `hephaestus.package.stage` | compensable | a staged artifact that was never activated can be removed |

Invariant: an unregistered or insufficiently specified physical operation is
classified `unknown` and **fails closed**; it is never assumed reversible.
A retryable-idempotent operation must have a stable key **and an independently
verified receiver-side deduplication contract**. The generic Home Assistant
state setter is also `unknown` for the same reason. An externally irreversible operation is
forbidden from declaring a "compensation".

## CA-3706 — bounded compensating actions and escalation

Decision: `plan_compensation` in `src/sofia/ops/saga.py` maps a
`PartialOutcome` to a bounded `CompensationPlan`:

- reversible → local rollback, no operator involvement;
- compensable → one bounded compensation step, operator review before rerun;
- retryable-idempotent → automatic retry with the same key only;
- externally irreversible → **no compensation is presented**, operator action
  required (review when the external effect is unobserved);
- unknown → fail closed, operator action required.

Invariant: a compensation never claims to reverse a remote message or a
live-device change. The concrete case in the requirement ("package staged but VM
never started") is `hephaestus.package.stage`, which is compensable and removed
only under the original authenticated mapping.

## CA-3710 — failure-resolution decision tree

Decision: `triage_failure` in `src/sofia/ops/failure_triage.py` classifies an
explicit `FailureSignature` into `code_defect`, `test_configuration`,
`stale_editable_installation`, `environment_windows_lock`,
`absent_package_tests`, or `unverifiable_deployment` (else `unknown`). The tree
is ordered and deterministic:

1. an unobserved deployment claim → `unverifiable_deployment`;
2. zero selected tests / no-selection → `absent_package_tests`;
3. collection or marker mismatch → `test_configuration`;
4. Windows file lock with a busy resource → `environment_windows_lock`;
5. import failure that passes under a pinned install → `stale_editable_installation`;
6. a deterministic functional assertion → `code_defect`;
7. otherwise → `unknown`.

Invariant: `may_retry_cleanly` is `False` for code defects, unverifiable
deployments and unknown signatures, and `conceals_code_defect_if_retried` is
`True` for them — a green rerun may not conceal a real bug. Windows file locks
and stale editable installs are the only retryable environment cases.

## CA-6109 — capacity budgets, degraded modes, and pre-exhaustion triggers

Decision: `src/sofia/ops/capacity.py` defines ordered inclusive thresholds
(`warn_at <= degrade_at <= stop_at`) per resource and returns the worst observed
level with explicit alerts. `DEFAULT_BUDGETS` declares starting ceilings for the
canonical DB, archives, backups, media assets, process RSS, sustained CPU, and
p95 encryption latency, derived from the baseline workload and to be re-derived
from observation.

Invariant: an observed resource with no declared budget is reported `WARN`
(fail closed), never silently ignored. `STOP` is surfaced so the runtime sheds
load before writing more. The module measures nothing itself.

## CA-6406 — sensory contradiction handling

Decision: `compare_observations` in
`src/sofia/knowledge/observation_conflict.py` preserves the disagreement between
two observations of the same subject/predicate as a `Contradiction` record.

- An authoritative `host_receipt`/`trusted_verification` outranks a transient
  screen/voice view, but the disagreement is still recorded;
- two equally/weakly trusted sources require authorized verification;
- a device-clock observation is never used to reorder history.

Invariant: no contradiction creates an enduring false memory, and no untrusted
wall clock resolves which statement supersedes another.

## CA-6409 — safety/accuracy regression drift scorecard

Decision: `compare_metrics` in `src/sofia/verify/drift.py` compares a baseline
and current `Sample` for a typed `MetricSpec` (direction, warn/fail thresholds)
and returns `improved`, `within_tolerance`, `warn`, `regressed`, or
`unverifiable`.

Invariant: an improvement is only claimed with reproducible samples on both
sides; a zero sample size is `unverifiable`, never an improvement. A regression
beyond the fail threshold sets `recommend_rollback`.

## Verification

Focused tests (also selected by `.github/workflows/v18-phase03-04-contracts.yml`):

- `test/test_v18_saga_contracts.py`
- `test/test_v18_failure_triage.py`
- `test/test_v18_capacity_budgets.py`
- `test/test_v18_commitment_projection.py`
- `test/test_v18_observation_conflict.py`
- `test/test_v18_drift_scorecard.py`

## CA-3705 — commitment record projected from the GOALS owner

Decision: `src/sofia/ops/commitment.py` projects an existing
`sofia.goals.model.Goal` into a `CommitmentRecord` (who asked, what was
promised, due date, preconditions, uncertainty, cancellability, and a
deterministic follow-up predicate). No new table or writer is introduced; the
GOALS state plane remains the sole durable owner.

Invariant: a blocked or approval-pending promise is never proactively chased; a
terminal goal is a history record, not an open commitment; system/maintenance
goals are not user commitments.

## CA-6406 clock-synchronization correction

The first pure comparator contained a dead clock-skew branch: it returned
`None` on matching values *before* checking skew, and could label a
different-value conflict as clock skew solely because time had elapsed.
The corrected contract now carries an optional bounded `event_id`.
Only two observations referencing the **same event** with equal values and
a device-clock timestamp discrepancy of at least 60 seconds produce
`clock_skew`. Two unrelated events are never merged. When values conflict,
the result remains a `value_conflict` and preserves both originals.
Typed tests cover the threshold, source-order symmetry, value disagreement,
forged/malformed identifiers and absence of correlation.

**Still open:** independent review and production consumer wiring to
authorized scoped durable contradictory-source evidence, plus a live remote
device clock comparison. Pure comparator regressions alone do not earn Gate 4.

## CA-6109 read-only capacity sampling and missing-reading repair

`assess_capacity` previously could report `normal` when only one healthy
resource was measured and every other declared resource was absent. It now
reports every missing budgeted reading as `WARN` with `used=None`.
A measured zero remains distinct from no observation. This change is
exercised by `test/test_v18_capacity_budgets.py`.

`python -m sofia.ops.capacity_probe --canonical-db <existing-path>
--media-dir <existing-path> --output <report.json>` performs an opt-in
read-only bounded **filesystem metadata** probe. It measures existing
canonical SQLite data/WAL and optionally archive/backup/media trees. It
does not read file contents, create SQLite, follow symlinks, touch the
single-writer role or pretend absent CPU/SSD/latency samples are zero.
It rejects overlapping roots and out-of-bounds scans.

`test/test_v18_capacity_probe.py` exercises nested usage, DB sidecar
accounting, omitted sensors, symlinks, bounds, and missing paths. This is
preparatory production measurement infrastructure, **not** an Artemis/Venus
measurement. Workload-derived growth, CPU/RAM, backups, encryption p95,
retention triggers and owner-approved budget thresholds still must be
collected on actual machines before CA-6109 can earn Gate 4.

## CA-6109 real production callback and advisory local disk pressure

`src/sofia/ops/capacity_runtime.py` now connects the existing bounded
`measure_storage()` sampler to the existing canonical PRESENCE owner via
`record_state`, with a time-limited `runtime:local_storage` observation.
The actual `create_background_coordinator` registers
`local_capacity_observation` every 300 seconds under the existing
RUN budget and OPERATOR STOP gate. No new thread, database, standalone
scheduler, provider call, file deletion, write throttle or notification
authority is introduced.

The observation reports measured canonical SQLite bytes and local free/total
filesystem bytes. It distinguishes missing CPU/backup/encryption/asset sensors
from zero and reports explicit provisional WARN/DEGRADED/STOP thresholds
without taking an unapproved action. These triggers are not calibrated
to actual Venus/Artemis workloads and cannot be treated as release
acceptance. The presence owner persists the diagnostic but it is not
an independently verified host resource/performance receipt.

Cross-platform focused tests cover the production projection, disk-pressure
boundaries, missing/invalid telemetry, no implicit repairs and registration
under the existing background scheduler.

## CA-6406 integrated diagnostic contradiction retention

`PresenceInitiativeEngine.observe` can now accept an **explicit**
`correlation_event_id` for the same event from two distinct attested
source adapters. The original observations still use the canonical PRESENCE
SQLite writer. Each correlated source requires an exact private audience and
a verified original source receipt. Only bounded scalar status values enter
the contradiction comparator, and the *diagnostic* table stores source IDs,
an audience, correlation ID, and `pending` review status, not raw text.
The existing source storage/pruning also bounds these diagnostics. Original
world observations are never overwritten or accepted as long-term memory
based on comparison alone.

The optional same-event correlation is supplied by the caller; it is NOT
independent proof that a screenshot and Fleet event describe the same fact.
No automatic Fleet/voice pairing, permission grant, renderer effect, outreach,
or durable-memory promotion is attempted. Scope, immutable pairing, restart
persistence, duplicate retries and unsupported private text are tested.

The original CA-6406 still requires authenticated source correlation from
authorized live adapters, independent acceptance review, and actual
cross-device verification before Gate 4 can be awarded.
