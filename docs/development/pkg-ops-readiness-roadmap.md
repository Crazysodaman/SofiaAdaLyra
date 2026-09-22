# PKG-OPS | systems operations, diagnostics, performance, and fleet enrollment

**Planning date:** 2026-09-22. **Status:** documentation contract only; no OPS agent, autonomous enrollment service, remote telemetry transport, hardening executor, or deployment is implemented by this document.

## Outcome

Give Sofía a source-grounded, permission-scoped IT operations layer across her approved fleet: Windows PCs/servers, Linux hosts/VMs, Raspberry Pi-class systems, and later other explicitly supported machines. OPS measures, diagnoses, trends, and proposes or performs narrowly typed maintenance operations. It does not replace NET, SAFE, RUN, DEV, or VERIFY.

## Ownership

- **OPS:** normalized host inventory, performance/health telemetry, diagnostics, history/anomaly comparison, trusted discovery/enrollment, bounded typed maintenance actions.
- **NET:** authenticated transport and route/channel enforcement between Sofía and remote agents.
- **SAFE:** trust roots, secrets, least privilege, hardening policy, revocation/quarantine, incident response and independent stop.
- **RUN:** Sofía's own service lifecycle, scheduling, resource budgets and supervisor behavior.
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

Do not claim OPS fleet support until real acceptance includes:

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
12. no arbitrary shell or privilege expansion from read-only enrollment.

A mocked transport or caller-supplied "authenticated=true" flag is not live enrollment proof.
