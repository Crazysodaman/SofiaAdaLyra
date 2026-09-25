# Sofía Ada Lyra | Six reliability gates and replicated-state contract

**Planning revision:** 2026-09-22. **Status:** documentation/acceptance contract only. No database replica, new service, automatic failover, operator console, or production write is implemented by this document.

**Owners:** RUN owns lifecycle, leases and supervision; OPS owns fleet placement and upkeep; SAFE owns trust, operator controls, stop and recovery; MEM owns memory/state semantics; ACT owns outbox; INTEGRATE owns tool registry; VERIFY owns tests/evidence. NET supplies trusted transport; SOCIAL enforces privacy. No new package required. Keep Discord → OPS/RUN 24/7 → general web/search release order.

## R1. Independent control-plane recovery

Inventory **all** authoritative and durable stores, including identity/Constitution files and integrity metadata, memories, original conversations, reflections/thoughts, unsent/delivered outbox, operator approvals, device identities/grants/revocations, job and action ledgers, workload placement/leases, config, docs index and audit evidence. Record physical path, schema/version, writer, consistency group, backup method, retention, recovery dependencies and restore order. Some data is irreplaceable; derived indexes/telemetry may be rebuildable. Do not assume one `sofia.db` contains all state.

Provide a separately controlled recovery route that works if Sofía, Discord, the main host and the normal UI are down. Human operator can independently halt executors, inspect status, restore on another eligible host, verify canonical identity/Constitution, privacy scopes, outbox state and revocations, then approve resumption. Recovery credentials must not depend exclusively on the failed control plane. A backup of the database must not resurrect revoked grants or stale authority. Treat unclear/compromised state as quarantined until independently verified.

Separate physical failure domains: two VMs on Artemis or two databases on a shared NAS are not necessarily independent. Define a measured recovery time objective (RTO) after a real supervised restore; never promise instant recovery.

## R2. Single durable work ledger

Every scheduled job, model action, tool call, alert, Discord send, maintenance operation and migration gets a unique immutable request ID, target, principal/audience, input digest, exact grant, evidence, deadline, tool/version, and idempotency key if supported. Durable states include `proposed`, `authorized`, `reserved`, `dispatched`, `verified`, `denied`, `failed`, `cancelled`, `outcome_unknown`, `compensated`.

Persist intent and authorization **before** any external effect; persist executor receipt and independent verification **after**. Restart reconciliation queries actual target state. Missing receipt does not prove nonexecution. Automatically retry only when the operation and the remote API both demonstrably support safe idempotency/replay. Otherwise retain `outcome_unknown` and notify the operator. Reconcile stateful outbox and job reservation atomically or through a documented recovery protocol; never claim a message sent or thought made while offline.

## R3. Operator-owned controls

Sparks has independently enforced pause/resume, emergency halt, host/workload pin, no-reboot/no-update, maintenance windows, budget/priority and pending-approval controls. An out-of-band emergency stop must work if the LLM/Discord/UI is unavailable, and must revoke executor authority rather than merely sending a prompt. Report exact impact, fresh evidence, permitted action, rollback and receipts. Protect audit entries without logging secrets.

**Only Sparks can explicitly approve final machine removal/decommissioning**, for one cryptographically identified device and exact proposal revision. Standing permissions, Sofía's own text, an expired grant or another host's approval cannot satisfy it. If identity, dependencies, backup or workload state materially changes, require a new approval. Sofía may autonomously quarantine, block privileged access, stop scheduling, drain, and prepare a removal packet, but quarantine is not deletion. Separately protect irreversible data actions, security weakening, expanded credential authority and physical motion.

## R4. Resource fairness/backpressure

Every host/workload declares CPU, RAM, GPU/VRAM, storage, network, power, telemetry and LLM/context budgets, with soft/hard ceilings, reservations and priority. Preserve headroom for emergency failover. Foreground chat/Discord and Sparks' gaming/interactive use outrank optional background thoughts, indexing, benchmarks, tool-building, documentation and batch jobs. Bound simultaneous model loads, GPU contention and disk/network saturation. Throttle, defer, or move only eligible workloads to trusted compatible hosts with permitted privacy/data locality. Unknown readings are not spare capacity. Prevent oscillating moves with cooldown/hysteresis. Measure latency, CPU/GPU/RAM and answer quality before/after tuning.

## R5. Failure lab and rollout gates

Start with isolated no-side-effect fakes, then supervised real hosts/test data under separately granted bounded change authority. Inject: primary host crash, standby loss, network partition, witness loss, stale replica, full/corrupt disk, bad backup, certificate expiry/rotation, compromised agent identity, broken update, interrupted migration, duplicate delivery, unreachable operator and rollback failure. Validate canonical identity, exact authority, no double executor, honest unknown outcomes, privacy isolation, consistent recovered state, real receipts and recovery duration. A mock, old test or documentation is not live acceptance. Require revision-pinned soak/recovery results, canary rollout and a restore rehearsal before deployment.

## R6. Capability truth and effective authority

Maintain one evidence-backed registry of local and remote tools: ID/version, provider, OS/architecture, operation/schema, side effects/risk, exact host/account/principal/audience scope, trust/grant, backend health, tested revision, last observation/receipt, expiry and state: `planned`, `implemented`, `offline-tested`, `live-accepted`, `disabled`, `revoked`, `unknown`. An effective usable tool requires registration **AND** reachable healthy backend **AND** fresh evidence **AND** valid scoped authority **AND** current SAFE/operator policy. A model assertion or peer advertisement cannot confer authority. Demote on stale evidence, incompatible version, revocation or outage; explain why invocation is unavailable.

## Two data locations: replication and backup design

### Nonnegotiable semantics

**One authoritative database writer** at a time. Never dual-write to two independent SQLite databases or mirror live SQLite files. SQLite WAL does not support processes on separate hosts accessing the same database across a network filesystem. Use SQLite's supported online backup/checkpoint APIs or a quiesced consistent snapshot for the present SQLite estate, not a naive copy of a busy database file.

Goal: retain acknowledged authoritative transactions under a **defined and tested single-data-host-failure model**, not promise that no possible failure can lose any information. Independent physical/power/storage/network failure domains matter. Primary + synchronous data-bearing standby in separate failure domains is a candidate for strict acknowledged durability; PostgreSQL with synchronous replication is one option to evaluate, **not an implementation decision**. A strict commit must wait for local and required remote durable flush, not just network delivery or an unflushed `remote_write` acknowledgment. Benchmark synchronous latency/throughput and measure replica lag.

Separate **data durability** from **leader election**. A third independent voting witness/consensus participant or equivalently proven lease/fencing mechanism is needed for safe automatic promotion in a partition; leader epochs/fencing must reject the returning stale primary. A witness holding no database data does **not** replace the second data copy. With only one data-bearing node available, a strict two-copy policy pauses authoritative writes even if the primary and witness can communicate. Loss of quorum blocks unsafe promotion. Check a candidate standby has all acknowledged commits before granting writes. Unacknowledged/in-flight transactions and external side effects may still be uncertain and require reconciliation.

Synchronous replication is **not a backup**: an accidental deletion, corrupted input, ransomware or bad schema change can propagate. Maintain independent encrypted versioned backups on a third failure domain, access-isolated/immutable or offline where possible, with verified restore keys, retention, checksums, off-host copies, periodic full restore and point-in-time recovery where supported. Never keep the sole decryption key only inside the failed runtime.

### Migration phases

1. Inventory every SQLite database, WAL/journal, flat file and in-memory state; map which stores cannot share a transaction and which artifacts are protected or tracked in Git. Preserve originals and never delete production state during cleanup.
2. Take consistent supported backups and verify independent restore of every store, preserving cross-store conversation/memory/outbox/grant consistency and privacy. Establish an operator recovery runbook and backup monitoring.
3. Implement durable operation IDs/reconciliation and a storage abstraction; measure present latency/IO/size and establish current recovery point/time.
4. In a lab compare keeping SQLite with proven periodic backup (no synchronous-zero-loss/automatic-HA claim) against a replication-capable backend candidate. Design schema migration, data parity checks, rollback, WAL retention and read routing. Avoid uncontrolled production dual writes.
5. If a backend migration is warranted, require explicit activation approval, tested migration, synchronous standby, safe witness/leader fencing, independent third backup, restart/rejoin and failover acceptance. Preserve canonical identity, privacy and revocations.
6. Verify whether the observed single-host failover reaches **RPO 0 for acknowledged transactions within the tested model** and report measured RTO. Never equate that conditional result with absolute zero-loss or universal continuous availability.

### Failure outcomes

| Condition | Required response |
| --- | --- |
| Primary fails; standby has every acknowledged commit and leadership/fencing verified | Promote and reconnect; reconcile in-flight work, report actual downtime. |
| Synchronous standby unavailable but primary/witness healthy | Safe reads may continue; pause strict authoritative writes, do not silently downgrade. |
| Witness/quorum unavailable | No unsafe promotion; active leader may write only if the selected protocol independently proves exclusive authority and required durability. |
| Split brain, stale standby, or unknown committed position | Block competing writers, fence/quarantine, verify state before resumption. |
| Both replicas corrupt/lost or harmful deletion replicated | Restore an independently verified backup; disclose its actual recovery point. |

## Acceptance checklist

- [ ] R-01 complete durable-state inventory and consistency/restore map.
- [ ] R-02 independently usable stop and supervised recovery while Sofía/Discord/primary host are down.
- [ ] R-03 durable work ledger: crash between execution and receipt produces `outcome_unknown`, never blind replay.
- [ ] R-04 operator pin/no-reboot/emergency controls enforced at trusted executor.
- [ ] R-05 foreground gaming/interaction forces measured background throttling without quality regression.
- [ ] R-06 registry refuses stale, untested, revoked or offline tools and distinguishes planned from live.
- [ ] R-07 acknowledged commit retained through measured single-data-host failure using actually configured synchronous durability.
- [ ] R-08 witness/partition/stale-primary tests prove single active writer and no split brain.
- [ ] R-09 standby loss blocks strict writes unless Sparks separately authorizes a changed durability policy.
- [ ] R-10 encrypted independent backup restores on another host with identity/privacy/revocations intact.
- [ ] R-11 full disk, bad cert, corrupt backup, interrupted migration and duplicate send fail safely.
- [ ] R-12 machine decommission denied without Sparks' exact fresh approval.
- [ ] R-13 record real measured RPO/RTO, latency cost and rollback at pinned revision before any HA deployment claim.

## Technical references for design, not installed components

- SQLite WAL: https://www.sqlite.org/wal.html and Online Backup API: https://www.sqlite.org/backup.html
- PostgreSQL synchronous durability: https://www.postgresql.org/docs/current/runtime-config-wal.html and https://www.postgresql.org/docs/current/warm-standby.html
- etcd quorum and membership: https://etcd.io/docs/v3.5/faq/

**This contract alone does not run tests, deploy hosts, create replicas or change runtime data.**