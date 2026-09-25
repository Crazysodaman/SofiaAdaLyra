# PKG-RUN | watchdog, standby startup and verified runtime failover

**Planning revision:** 2026-09-22. **Status:** design and acceptance contract only; no deployed supervisor, watchdog, elected leader, synchronous replica, or automatic failover is certified here. Complements [the reliability contract](pkg-reliability-control-plane-contract.md) and [implementation sequence](pkg-reliability-implementation-plan.md).

## Separate failure detectors from authority and execution

- **Local supervisor**: an operating-system service manager or external supervisor on each host watches Sofía's local process, restarts it with bounded backoff after a process crash and enforces startup/shutdown/resource limits. A local restart is not permission to become primary.
- **Independent fleet watchdog**: healthy independent monitoring/control-plane components observe node health, lease state, data freshness and service dependencies. A missed heartbeat alone is not proof that a remote process is dead; partitions and stalled storage require fail-closed handling. A witness/consensus voter participates in safe leader selection and is not itself a data replica or sufficient executor.
- **Standby supervisor**: already running on an eligible independently hosted machine, ready to start/promote a replacement runtime only after data and leadership checks. Optional Wake-on-LAN/IPMI/Redfish can provision a powered-off target through an separately authorized adapter, but availability and power-on capability must be observed; do not promise an instant or universal remote boot.

## Recovery sequence

1. Observe failure with time-stamped evidence and a bounded false-positive/timeout policy. Determine whether the problem is process, host, network, database, service dependency or monitoring partition.
2. For a local process crash, restart as the already authorized role; reconcile pending work, check readiness, and do not accidentally grant a new primary lease.
3. For host failure, independently establish the previous primary has been fenced or cannot successfully use its old epoch/credentials; acquire an exclusive fresh lease through the approved consensus/fencing mechanism. If exclusivity cannot be established, **do not promote**.
4. Confirm candidate host enrollment, exact grants, capacity, OS/model compatibility, privacy/data locality, external-service readiness and a data-bearing replica containing every required acknowledged commit. Under strict two-copy policy, do not resume authoritative writes when one required data copy is unavailable, even if a witness votes.
5. Supervisor starts the standby's compatible runtime as the sole leader; verify identity and Constitution integrity, privacy scopes, revocations, work ledger, outbox, model/provider health, probes and client routes before advertising readiness.
6. Reconcile in-flight jobs and external sends by immutable IDs, receipts and target-state checks. Never automatically replay an `outcome_unknown` non-idempotent action.
7. Reconnect Discord/clients through their narrow existing permissions, report observed downtime and any uncertain/unconfirmed work without claiming seamless continuity.
8. When a failed host returns, require authenticated rejoin, state resynchronization, stale-epoch fencing and a fresh role assignment; no automatic second leader. A returning host is not decommissioned merely because it was offline.

## Dependency and placement constraints

- The monitor, witness, standby executor, authoritative replicas, independent backups and out-of-band operator stop must not all depend on one Artemis host, its attached NAS, one power source, or one shared switch if single-failure survival is claimed. Document actual failure domains; separate VMs alone do not establish independence.
- A replica protects committed data; a standby runtime/host runs Sofía; a witness chooses leadership; a backup restores damage or loss. These are distinct roles, not interchangeable machines or copies.
- A standby with no suitable compatible LLM may preserve canonical identity and basic text/service continuity while reporting degraded inference; do not invent full GPU-equivalent performance.
- If no safe standby, quorum, correct data or trusted recovery path exists, stop state-changing work, keep externally observable failure status where possible and require independent operator recovery.
- Cross-store consistency must cover memory, original conversations, identity and Constitution, grants/revocations, work ledger, thought journal, and outbox. Do not claim a single replicated SQLite file protects all Sofía state.

## Fault and acceptance matrix

- Kill Sofía's process while host lives: local supervisor restarts once with bounded backoff, retains identity, no duplicate send/action.
- Power down primary host: independent observer triggers safe replacement only with fresh exclusive leadership, compatible host and data. Measure actual time to ready.
- Partition primary from watchdog while primary can still reach another subsystem: at most one executor/leader can write or send, or all unsafe writes pause; no heartbeat-only split brain.
- Lose synchronous data standby: strict authoritative writes pause, safe reads/degraded mode may continue; no silent downgrade.
- Lose witness/quorum: no unsafe promotion; follow the proved leader/durability protocol.
- Bring old host back: stale epoch rejected, state resynchronized, host remains enrolled unless Sparks explicitly approves final removal.
- Crash between external effect and receipt: ledger retains `outcome_unknown`, no blind retry.
- Crash during model response: reconnect recovers confirmed conversation state; an uncommitted response may need regeneration and must be labeled as unconfirmed.
- Primary/standby share a hidden dependency: topology check rejects the claimed independent-failure guarantee.
- Out-of-band operator stop works even if Sofía, Discord and main UI are down.

**Live acceptance requires supervised real-host tests, revision-pinned evidence, measured RTO/RPO and resource/latency overhead. A design, simulation, or local process restart is not production high availability.**