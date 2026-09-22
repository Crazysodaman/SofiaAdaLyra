# PKG-OPS | fleet operations, diagnostics, performance, and orchestration

**Planning date:** 2026-09-22. **Status:** documentation contract only; no OPS agent, autonomous enrollment service, remote telemetry transport, hardening executor, or deployment is implemented by this document.

## Outcome

Give Sofía a source-grounded, permission-scoped IT operations layer across her approved fleet: Windows PCs/servers, Linux hosts/VMs, Raspberry Pi-class systems, and later other explicitly supported machines. OPS measures, diagnoses, trends, enrolls, maintains, drains, decommissions, and orchestrates eligible Sofía workloads across the fleet. It does not replace NET, SAFE, RUN, DEV, ACT, or VERIFY.

## Ownership

- **OPS:** normalized host inventory, performance/health telemetry, diagnostics, history/anomaly comparison, trusted discovery/enrollment/decommissioning, bounded typed maintenance, workload registry, placement, drain, migration/failover evidence.
- **NET:** authenticated transport and route/channel enforcement between Sofía and remote agents.
- **SAFE:** trust roots, secrets, least privilege, hardening policy, revocation/quarantine, incident response and independent stop.
- **RUN:** Sofía's own service lifecycle, scheduling, resource budgets, leadership/singleton semantics and supervisor behavior; uses OPS placement/failover evidence rather than inventing a second scheduler.
- **ACT:** proactive user notification and approved outreach.
- **VERIFY:** revision-pinned benchmarks, negative tests and real cross-machine acceptance.
- **DEV:** Sofía source/code changes and OpenCode execution, not generic host administration.

## Normalized telemetry contract

A host reports only metrics it can actually observe. Unsupported values remain unknown rather than becoming zero.

### CPU

- total and per-core utilization when available
- load/run-queue equivalents
- frequency/clock state
- temperature and throttling where supported
- Sofía/Ollama/process CPU use

### RAM

- total, available, committed, cache and swap/pagefile
- per-process RSS/working set/private memory when available
- long-run growth/leak indicators
- memory pressure

### GPU

- vendor/device
- utilization
- VRAM used/total and peak
- clock, temperature, power and throttling where supported
- process/model attribution where the platform exposes it

No GPU field is synthesized for hosts without a supported GPU/driver telemetry source.

### Storage

- capacity/free space
- read/write throughput
- latency/queue/IOPS when available
- filesystem health/error signals
- SMART/NVMe health only where a trusted OS/device interface exposes it
- database/log/cache growth

### Network

- interface status/speed
- throughput/errors/drops
- active/listening connections under approved inspection scope
- latency/packet-loss probes only to approved targets
- DNS/route state
- per-service connectivity where observable

### Host/runtime

- uptime/boot evidence
- service/process state and restart history
- OS/version/patch and pending-reboot evidence
- container/VM state where an adapter exists
- temperatures/power/throttling on Raspberry Pi and similar hardware
- Ollama/model residency, context, token rate, generation latency and memory use when integrated

## Raspberry Pi support

Linux/ARM agents must support Raspberry Pi-class telemetry without pretending desktop capabilities exist. Where available, capture SoC temperature, CPU frequency, throttling/undervoltage flags, RAM/swap, storage health/capacity, network, uptime and relevant service/process state. GPU/VRAM semantics must follow the real platform rather than copying NVIDIA assumptions.

## Performance history and anomaly comparison

OPS should persist bounded, timestamped observations sufficient to answer both:

- "What is this machine doing now?"
- "Is this unusual for this machine?"

History must identify host, source/agent version and freshness. Trend/anomaly logic compares to evidenced baselines and reports uncertainty instead of emitting a magic health score.

Examples:
- CPU normally 10–20%, now sustained above 75% for 40 minutes.
- Ollama VRAM increased after a model/context change.
- Raspberry Pi reports throttling/undervoltage during load.
- a service restart rate changed after an update.

Retention/downsampling belongs to explicit configuration so telemetry does not grow without bound.

## Autonomous discovery and zero-touch enrollment

Sofía may proactively discover and enroll new hosts **without asking Sparks for each machine** when a standing policy explicitly permits it.

### Discovery scope

Discovery is bounded to approved:
- local subnets/VLANs,
- known management planes,
- preconfigured bootstrap registries,
- or signed agent advertisements.

No unrestricted internet discovery or arbitrary scanning is implied.

### Candidate state

A newly observed device starts as **candidate/untrusted**. IP address, hostname, MAC address, OS banner, model output or DNS name does not establish trusted identity.

### Trust proof

Before enrollment, a candidate must pass an independently verified trust mechanism such as:
- pre-provisioned device/agent certificate,
- trusted public key,
- one-time enrollment token,
- signed inventory/management record,
- hardware-backed identity where later supported,
- or another SAFE-approved challenge/attestation mechanism.

Use fresh nonces/challenges and replay protection. Key conflicts, cloned identity, stale tokens or unexpected trust chains fail closed.

### Automatic read-only enrollment

When all of the following are true:

1. the device is inside the approved discovery scope,
2. trust proof succeeds,
3. the standing enrollment policy permits that host class/network,
4. required agent/version/security checks pass,

Sofía may automatically:
- create a durable fleet/device identity,
- assign the least-privilege read-only monitoring profile,
- record provenance and trust evidence,
- begin inventory/health/performance collection,
- establish bounded historical sampling,
- and notify Sparks of the enrollment.

No per-device confirmation is required under that standing policy.

### Agent bootstrap/install

If a new machine does not already run a trusted OPS agent, automatic installation is allowed only through a separately approved bootstrap mechanism with explicit installation authority, for example a trusted management service or pre-authorized remote-administration path.

Sofía may not:
- guess passwords,
- scrape/reuse unrelated credentials,
- exploit vulnerabilities,
- expand from monitoring to arbitrary shell access,
- or infer install authority merely because a device is reachable.

The installed package must be signed/hash-verified and tied to an approved version/source.

### Quarantine and rejection

Do not enroll when:
- trust proof fails,
- device identity conflicts with another host,
- replay is detected,
- network/host class is outside policy,
- required hardening/version checks fail,
- or evidence is contradictory.

Keep the device quarantined/candidate-only, perform no privileged operation, and report the reason.

## Proactive notification

Successful enrollment is a meaningful event. ACT should notify Sparks automatically on an approved channel without waiting to be asked.

The notice should summarize:
- canonical device/fleet name,
- when and where it was discovered at an appropriate privacy level,
- how trust was verified,
- assigned enrollment/profile state,
- OS/platform and useful hardware/capability summary,
- initial health/performance concerns,
- and anything unavailable/unknown.

Use durable event IDs and dedupe so reconnects/reboots do not repeatedly announce the same machine.

Unexpected or failed-trust devices may also produce a security-relevant notification, subject to rate limits so network churn does not create alert spam.

## Typed maintenance operations

Read-only telemetry is the first release. Later OPS may expose narrowly typed operations such as:
- restart an approved service,
- stop an approved runaway process,
- rotate an approved log,
- run a defined diagnostic,
- restart Sofía/Ollama under RUN policy,
- apply an approved package/agent update,
- or execute a documented recovery operation.

These remain Think/Diagnose → Propose → Authorize → Execute → Verify. Avoid a generic arbitrary-shell capability.

## Autonomous fleet lifecycle

Enrolled machines have explicit lifecycle state:

- `candidate`
- `enrolled`
- `healthy`
- `degraded`
- `maintenance`
- `draining`
- `quarantined`
- `offline`
- `decommissioned`

State changes require evidence and durable audit records. A transient disconnect does not delete a machine.

### Standing upkeep policy

Sparks may grant OPS a standing maintenance policy so routine fleet care does not require a prompt for every action. Policy is scoped by host/group, action class, risk, maintenance window and rollback requirements.

Eligible autonomous upkeep can include:

- keep the signed OPS agent current;
- update approved Sofía-managed packages/services;
- restart failed approved services;
- rotate or prune approved logs/caches under retention limits;
- perform approved database/index/checkpoint/vacuum work where backup/recovery requirements are met;
- run health checks and documented repair procedures;
- schedule approved OS/package patch work;
- reboot only when specifically permitted by policy and workload drain/availability checks succeed;
- remove stale approved package versions after verified replacement;
- drain and return hosts for maintenance.

The policy must not silently broaden itself. Unsupported or higher-risk operations become proposals.

### Removal/decommissioning

Sofía may automatically remove a host from active fleet service when standing decommission policy explicitly covers the reason, for example:

- approved replacement;
- device retirement;
- revoked or compromised device identity;
- confirmed permanent removal;
- repeated unrecoverable failure meeting configured policy.

Before final decommission:

1. stop new workload placement;
2. drain/move eligible workloads;
3. verify no protected active lease remains;
4. revoke device/agent credentials;
5. remove active routing/service-discovery membership;
6. archive required telemetry/audit/history according to retention policy;
7. preserve necessary backups/recovery artifacts;
8. verify the machine can no longer act as an authorized fleet member.

Unreachable or missing hosts first become offline/degraded. Absence alone is not proof of retirement.

## Workload orchestration

OPS owns placement/movement mechanics for **managed workload units**, not arbitrary OS processes.

### Workload contract

A movable workload declares:

- workload ID/version;
- component/package owner;
- supported OS/architecture/runtime;
- CPU/RAM/GPU/VRAM/storage/network requirements;
- optional versus required GPU acceleration;
- state type: stateless, externally persisted, replicated, checkpointable, singleton;
- input/output data location and privacy/audience constraints;
- required secrets/capabilities;
- startup/shutdown/checkpoint/restore operations;
- health/readiness probes;
- acceptable interruption/downtime;
- affinity/anti-affinity;
- host allow/deny rules;
- leader/singleton semantics;
- rollback procedure.

A normal process is not automatically movable.

### Initial eligible workload classes

Potential early candidates:

- Ollama/model inference workers;
- embedding/index workers;
- background reflection jobs;
- telemetry collectors/aggregators;
- approved batch analysis;
- Discord helper/adapter workers where durable message semantics allow it;
- avatar rendering workers;
- later web/search workers after the web gate.

The canonical identity/memory/authority stores remain protected services with stronger state and leadership requirements.

### Placement policy

The scheduler considers real host evidence:

- current and recent CPU load;
- RAM pressure;
- GPU support/utilization/VRAM;
- temperature/throttling/power state;
- disk capacity/latency/health;
- network latency/reachability;
- host foreground workload, including gaming or interactive use;
- maintenance/drain/quarantine status;
- OS/architecture/runtime compatibility;
- data locality/privacy/audience policy;
- resource reservation/headroom;
- reliability/restart history;
- expected response latency;
- power/resource budget.

Placement must reserve resources rather than merely observe a momentary free value.

### Migration/failover sequence

Preferred movement sequence:

1. mark source workload draining;
2. stop new work on source;
3. checkpoint/flush/replicate state if required;
4. validate target eligibility and reserve resources;
5. transfer or reacquire only authorized state/secrets;
6. start target instance;
7. pass readiness/health/identity/version checks;
8. acquire the current workload lease/epoch;
9. redirect new work;
10. confirm source no longer owns active authority;
11. retire source instance;
12. verify final state and release old reservation.

If any verification fails, rollback or remain safely degraded. Do not declare migration complete because a target process merely started.

### Failover and split-brain prevention

For singleton/authority-bearing components use durable leases, epochs, fencing tokens or equivalent so network partitions cannot produce two active authorities.

A replacement instance cannot become authoritative without proving:

- current configuration/version;
- required durable state;
- current lease/epoch;
- host authorization;
- readiness.

When source state cannot be confirmed, report uncertainty/loss rather than fabricating seamless continuity.

### Moving Sofía's runtime

Sofía is not bound to a specific machine. The canonical identity remains the same while execution components move.

RUN + OPS may move/fail over the primary runtime itself only when:

- target host is trusted and eligible;
- protected identity/Constitution/memory state is available and integrity-verified;
- singleton leadership is transferred/fenced safely;
- active conversation/outbox state is reconciled;
- clients can reconnect to the new active runtime;
- the change is recorded and announced to Sparks.

If the old host dies abruptly, the standby may take over using the latest verified durable state. Any possibly lost/unconfirmed turn, thought, or action must be reported honestly.

## Proactive fleet management notifications

ACT should surface **meaningful** fleet events, not telemetry spam:

- new host enrolled;
- host quarantined/revoked;
- maintenance started/completed with notable outcome;
- workload moved because of load, heat, failure, gaming contention or maintenance;
- primary runtime failover;
- decommission completed;
- update/repair failed and needs intervention.

Routine successful samples and repetitive stable-state messages stay silent.


## Host hardening observations

OPS supplies evidence to SAFE for:
- firewall state,
- unexpected listening ports/services,
- patch level,
- Defender/AV/security service state where available,
- secrets/config file permission posture,
- startup/scheduled-task drift,
- dependency/package drift,
- service-account privilege,
- agent version/signature,
- unusual process/network behavior,
- backup/recovery readiness.

Observation does not itself authorize remediation.

## Performance optimization loop

Use matched measurements before and after tuning:
1. baseline,
2. identify bottleneck,
3. change one controlled variable,
4. repeat the same workload,
5. compare latency, CPU, GPU/VRAM, RAM, disk/network and correctness/personality,
6. retain only changes whose resource/latency benefit does not regress grounding, reliability or safety.

Key workloads:
- idle,
- warm short chat,
- long technical turn,
- memory-heavy retrieval,
- background reflection,
- Discord traffic,
- model load/unload,
- gaming/contention scenario,
- multi-hour/day soak.

## Acceptance

Do not claim OPS fleet/orchestration support until real acceptance includes:

1. local host telemetry with honest unsupported fields,
2. remote Windows telemetry,
3. remote Linux telemetry,
4. Raspberry Pi-class telemetry including thermal/throttling where available,
5. durable history and restart continuity,
6. detect + challenge + authenticate + auto-enroll a new authorized host without a per-host prompt,
7. proactive one-time notification to Sparks,
8. spoofed/replayed/wrong-network/duplicate/revoked host denial,
9. quarantine/revoke stopping privileged collection/actions,
10. resource profiling under idle/chat/background load,
11. at least one measured optimization with before/after evidence,
12. no arbitrary shell or privilege expansion from read-only enrollment;
13. standing-policy maintenance completes one approved upkeep cycle with before/after verification;
14. planned drain moves all eligible workloads before maintenance;
15. automatic placement chooses a compatible lower-pressure host using measured resources;
16. move a stateless workload and verify target before source retirement;
17. move/checkpoint a stateful workload without duplicate or stale authority;
18. fail an active worker and recover it on an eligible host;
19. prove singleton split-brain prevention during a simulated/real partition condition;
20. refuse incompatible, overcommitted, quarantined and privacy-prohibited targets;
21. evacuate eligible workloads from a quarantined host;
22. decommission a retired host only after credential, workload, routing and retention verification;
23. move/fail over the primary Sofía runtime in a supervised test while preserving canonical identity and reporting any uncertain state;
24. proactive notifications are useful, deduplicated and do not spam routine telemetry.

A mocked transport or caller-supplied "authenticated=true" flag is not live enrollment or orchestration proof.
