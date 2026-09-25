# Reliability implementation sequence | RUN / OPS / SAFE / MEM / ACT / INTEGRATE / VERIFY

**Status:** design-only implementation plan, 2026-09-22. See [the detailed contract](pkg-reliability-control-plane-contract.md). No workstream below is marked implemented or live accepted by writing this plan.

## Stage A | Evidence and a recoverable baseline (before HA)

- Enumerate all SQLite/flat-file/in-memory state and runtime DB/log files, protected identity/Constitution, revocation/grant/outbox dependencies; flag mixed state across separate SQLite connections.
- Produce a state-owner/schema/failure-domain map and restore-order runbook with explicit consistency gaps.
- Add safe SQLite online-backup or quiesced snapshot adapter and versioned encrypted off-host backups; verify independent restore, hash/integrity, privacy, identity and revocations. No live file mirroring.
- Pin repository revision, platform and backup provenance. Establish actual measured restore time and recoverable point before setting RTO/RPO targets.

**Gate A:** supervised restoration of a test copy on a different machine with no production mutation and a recorded recovery report.

## Stage B | Durable action/outbox ledger and operator stop

- Unify request identity, target, authority, inputs, execution reservation, receipt and uncertain-outcome handling across action, distributed gateway, scheduler, outreach and OPS. Reuse and extend existing ledgers; do not create incompatible parallel schedulers.
- Make executor-side allow/deny, revocation, durable dedupe and fencing independent of LLM text.
- Expose out-of-band pause/stop, no-reboot, host pin, workload pin, maintenance window and approval queue. Approval records bind Sparks to exact device identity and proposal revision, with expiry/revalidation.
- Test crash at each state transition and assert no blind replay, double send or self-approved removal.

**Gate B:** fail-stop and resume from a clean process with `outcome_unknown` reconciliation; operator stop works without Sofía chat/Discord.

## Stage C | Capacity fairness and capability truth

- Version a live capability registry; only grant effective use after backend health, fresh evidence and active exact-scope authorization. Implement negative tests for stale/revoked/unknown tools.
- Record CPU, RAM, GPU/VRAM, storage, network, thermal/power and latency with honest unsupported fields, reserve failover headroom, add per-class queue/admission budgets, cooldown and foreground/gaming priority.
- Benchmark idle, short/long conversation, background jobs and gaming contention with revision/host/model-pinned results and accuracy/quality checks.

**Gate C:** measured background backoff without foreground degradation, plus verified planned/implemented/live registry distinctions.

## Stage D | Replication prototype, independent quorum and restore

- Compare existing SQLite+verified backups against an isolated primary+synchronous-data-standby prototype (for example PostgreSQL), including migration complexity, cross-store atomicity, write latency, storage use and measured recoverability.
- If strict two-copy acknowledged durability is adopted, configure confirmed durable flush on both data-bearing nodes; do not substitute an unflushed remote write. Use independently hosted witness or equivalent proven election/fencing, and test stale-primary rejection.
- Explicitly decide partition and standby-outage policy: default strict mode blocks authoritative writes when required data replica is unavailable. Witness is a vote, **not** a backup or second data copy.
- Retain a third access-isolated encrypted backup with tested restore and point-in-time recovery if supported. Check recovery keys and protected authority state.
- No production dual-writing between different engines; migrate through staged parity checks, separately approved activation, and a reversible cutover plan.

**Gate D:** documented single-host-failure RPO for acknowledged transactions under the tested model, measured RTO and latency; partition/witness failure test with only one active writer; independent restore drill.

## Stage E | Supervised fleet failover, long soak, promotion

- Place movable worker first, then stateful worker, then test primary runtime relocation only with lease/fencing, version/privacy checks, in-flight action reconciliation and client reconnect.
- Run full-disk, corrupt backup, failed cert rotation, partition, delayed replica, duplicate action, host loss, unavailable operator, rollback-failure and UPS-loss tests.
- Require revision-pinned integrated suite, safe refusal, live receipts, rollback, capacity/thermal overhead and multi-day RUN soak before claiming production HA/24-7.
- Preserve existing Discord before OPS/RUN/web release gates; web/search remains later and separately authorized.

**Gate E:** supervised real-hardware acceptance; no assertion of deployed HA just because design/unit tests exist.

## Proposed code/test ownership targets (verify filenames before edits)

- `src/sofia/memory/store.py` and other SQLite stores: state inventory, backup/migration abstraction, integrity and restore.
- `src/sofia/distributed/durable.py` and `src/sofia/action/*`: durable grants, intent/outcome reconciliation and idempotency.
- `src/sofia/application/idle_reflection.py` and `src/sofia/personality/reflection.py`: consistent attempt/outbox ledger and honest continuity.
- `src/sofia/runtime/*`: leader epoch, recovery mode, pause/resume and safe startup.
- `src/sofia/capability/*` and `src/sofia/cognition/tools.py`: effective capability truth registry and executor checks.
- New OPS adapters and NET transport: metrics/placement/replication observation; **do not** add generic arbitrary shell.
- VERIFY tests: `test_recovery_state_inventory`, `test_durable_ledger_crash_matrix`, `test_operator_stop_and_decommission_approval`, `test_resource_fairness`, `test_capability_truth`, `test_replication_partition_fencing`, `test_backup_restore_isolated`, `test_failover_end_to_end` (proposed names, not existing tests).

**Safety invariant:** Sofía can prepare, drain and quarantine a machine, but only Sparks explicitly approves final removal for the exact device/proposal. Do not delete tracked runtime data or run host-modifying drills as a documentation side effect.