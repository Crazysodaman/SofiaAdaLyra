# Sofía 2.0: Hardware-neutral Fleet, resource compatibility, idle benchmarking and inference boundary

**Owner decision:** Approved design contract, 2026-10-24 (America/Chicago).
**Status:** Requirements and implementation/acceptance plan only. Not a claim of coded functionality, host enrollment, successful benchmark, module activation, CI, or production commissioning.
**Owners:** PLAT-05 (module contract), PLAT-06 (model/compute), PLAT-07 (Fleet/resource placement), PLAT-08 (evidence/readiness), SF-03/05/07/11/13/14/16 (resource/device brokers, compatibility, module profiles, forecasting and maintenance), Core cognition for model-independent request/response semantics.
**Relation:** Supplements PLATFORM_AND_MODULE_CATALOG_V1.md and ARCHITECTURE.md; supersedes the *future topology's host-name-specific design assumption*, not its current Venus single-writer safety boundary or any active configuration. This does not authorize Phase 03 migration.

## 1. Decisions and invariants

1. Machines, VMs, GPUs, CPUs and attached devices are enrolled **resources**, not named architectural dependencies. Venus and Artemis are display names/current deployment examples only, not validation constants. A VM may run on Hyper-V, another hypervisor or a supported physical host.
2. Each enrolled compute node has immutable authenticated Fleet identity; editable display name, site and tags never serve as an authority proof. Inventory may be collected on untrusted/discovered nodes, but placement/dispatch requires verified enrollment, current trust and explicit policy.
3. Platform uses one shared, versioned **Resource Capability Contract V1** for *observed supply* and *signed module demand*: same IDs, primitive types, units, schemas, capability vocabularies and constraints. Hardware exposes facts and capacity; modules express predicates over them. No parallel competing hardware schema or second scheduler.
4. Maintain three distinct provenance classes: **manufacturer-stated specifications** (with attributable source, model/part, revision and verification), **host-observed inventory/telemetry** (with authenticated source and freshness), and **benchmarked measurements** (with exact workload and reproducible evidence). Unverified manufacturer claims must not be promoted to verified data.
5. Benchmarks are **automatically eligible at the earliest verified idle opportunity** after enrollment or a meaningful invalidation, subject to a pre-authorized, narrow benchmark policy. Idle is a measured fact, not merely low CPU utilization.
6. A benchmark, manifest, model response, forecast or host self-report cannot enroll or trust a node, broaden privileges, install software, alter firmware/settings, pull a model, promote state ownership, or bypass SAFE/STOP/RUN.
7. One canonical Sofía writer and state lineage at a time. Runtime placement is separate from inference placement. The current writer stays on Venus until independently authorized, verified Phase 03 cutover; the intended Sofía VM is presently on Artemis only because of available virtualization hardware. No general Fleet placement operation can silently relocate Core authority.
8. GPU worker selection may consider multiple approved machines, including an RTX 3060 or any future computer, **without hard-coded host names**. Switching workers is not synonymous with changing model weights or permissions. Exact model identity/digest and authorized provider policy must remain fixed. Automatic rerouting/retry of uncertain external effects is separately gated, never inferred from inventory.
9. Missing/stale/conflicting evidence is UNKNOWN and fails closed for requirements that cannot be proven; capacity forecasts do not replace current resource reservations. A module being compatible, available, installed, healthy or certified is not permission to run it.

## 2. Shared contract and near-1:1 hardware-to-module mapping

**Canonical value format:** A capability key names a property; a supply record contains typed value, unit, scope, provenance, observed_at and expires_at; a requirement is a typed predicate against that same key. Do not redefine equivalent keys in special-case modules. Use stable enumeration vocabularies and integer bytes for capacity; SI Hz/bps for frequency and bandwidth, milliseconds for latency, Celsius for temperature. Convert display units at the UI boundary only.

| Shared capability family | Host/device inventory or live supply | Module signed requirement / runtime gate |
| --- | --- | --- |
| identity/trust | Fleet node ID, certificate/key identity, enrollment state, trust, grants | eligible enrolled nodes; required trust class and audience/data locality |
| os/runtime | OS family/version/kernel/architecture, ABI and runtime/API versions | OS/arch/ABI range, installed service and runtime version constraints |
| cpu | architecture, model, cores/threads, instruction sets, measured allocatable shares, utilization | allowed architectures/instructions, min cores/shares, latency/performance need |
| memory | physical/guest total, currently allocatable bytes, lease/reservation state | min/desired/peak allocatable bytes and reservation period |
| gpu | per-device stable ID, PCI identity, vendor/model, accelerator API, driver/runtime, VRAM total/free/allocatable, utilization, compute support | optional/required GPU, supported backend/driver ranges, per-device free VRAM, compute features and isolation |
| storage | per-volume ID, media class, free/allocatable bytes, IOPS/throughput, durability, path scope | space, persistence, throughput/latency, safe scratch location, retention |
| network | network identity, policy-approved routes, measured latency/bandwidth, isolation, endpoint trust | bandwidth/latency/MTU where relevant, permitted destination, mTLS endpoint capability |
| peripherals | typed per-device IDs, driver/protocol/version, attachment host, exclusive-use/lease state, fresh health | device class/protocol/count, required specific attachment and exclusive lease |
| software/models | approved binaries/services/versions, model IDs/digests actually installed, API support | exact provider/ABI version, model identity/digest, tool protocol/capability |
| virtualization | physical vs VM, parent relationship, hypervisor capabilities, vCPU/vRAM limits, passthrough | guest compatibility, hardware passthrough, isolation, required host affinity |
| physical location | site/room and local device topology if verified | locality, latency and pinned control-device restrictions |
| live activity/health | busy/gaming/idle state, foreground device use, load, temperature, throttling, heartbeat and freshness | admit only when current health/headroom and activity policy permit |
| recovery/placement | snapshot/checkpoint capability, restart semantics, leases and mobility | PORTABLE_STATELESS / CHECKPOINT_RESTART / HOST_PINNED / CANONICAL_PINNED, recovery budget |

All hardware capabilities and module needs share namespaces such as:
- cpu.arch (enum), cpu.cores.allocatable (count), cpu.features (set)
- memory.allocatable_bytes (int)
- gpu[device_id].backend (set), gpu[device_id].vram.allocatable_bytes (int), gpu[device_id].driver_version (version)
- storage[volume_id].allocatable_bytes (int), storage[volume_id].sequential_write_bytes_per_second (measured int)
- network[endpoint_id].round_trip_ms (measured number), network[endpoint_id].bandwidth_bps (measured int)
- runtime[service_id].version (version), model[model_id].digest (hash)
- device[device_id].protocol (enum), device[device_id].lease_state (enum)
- host.trust_state (enum), host.activity_state (enum)

Bracketed selectors above are illustrative canonical-schema notation, not already-implemented literal key names. Final identifiers must be versioned and validated consistently. **Do not aggregate multiple GPUs' free VRAM into one device's allocatable VRAM** or double-count the guest's capacity and its underlying hypervisor host's capacity.

Requirement predicate types: equals, in-set, range/minimum/maximum, semver/ABI range, contains-feature, matches-per-device, one-of alternative, all-of conjunction, same-host/device-affinity, mandatory measured evidence and bounded freshness. Unknown is not zero or false: it is an explicit non-admissible third state.

## 3. Four related durable records

1. **HardwareInventory:** verified Fleet identity and node/parent relations, manufacturer-stated specs, machine-observed components, per-device IDs, supported runtime/backend versions, source refs, observations, integrity and change revisions.
2. **HardwareTelemetry:** bounded, periodic authenticated observations: current available/allocatable CPU, RAM, VRAM, storage, network, utilization, thermals, power state, health, activity and leases; per-metric timestamp, source, TTL, units and UNKNOWN. Store bounded history via existing canonical state and telemetry owners.
3. **ModuleResourceRequirements:** signed module/version/digest and each allowed operation profile's exact hard constraints, soft preferences, resource maxima, data classification, device constraints and placement mode. Immutable signed constraints can only be narrowed by authorized policy overrides.
4. **PlacementAssessmentAndReceipt:** exact node/resource IDs, manifest/profile/model digest, inventory and telemetry revision refs, benchmark refs, failed/unknown reasons, resource reservation, SAFE/STOP decision, actor/audience, dispatch/effect receipt, expiry and measured outcome.

Do not create a shadow database, second authority, independent resource scheduler or second placement engine. Preserve historical records and re-evaluate active leases against current authoritative data.

## 4. Automatic benchmark lifecycle

**Trigger and cadence**
- On enrollment, supported-hardware inventory discovery, or first eligible observation, enqueue one durable *pending* baseline benchmark job for applicable resource classes as soon as an idle window is available.
- Invalidate/schedule bounded retests after relevant hardware replacement, software/runtime or driver update, changed GPU/CPU allocation, model digest change, unexplained performance degradation, test-harness revision or benchmark data expiry.
- Keep deduplicated per-resource/per-workload jobs; persistent state survives reboot and interruption. Use cooldown/backoff, caps on concurrent tests per host and per resource, and avoid endless retry storms.
- Break work into small resumable stages with a time budget and resource quota; prefer completing useful short stages at the earliest safe idle time, rather than indefinitely requiring a long continuous idle period.
- Default no automatic destructive, disk-wearing, power-intensive, device-effectful or network-saturating stress tests. Such tests require separate explicit policy/approval, if supported at all.

**Idle gate, all required with fresh authenticated evidence**
- Machine online, worker healthy, enrolled, correct trust/policy; benchmark workload explicitly permitted for that host.
- No foreground gaming, owner activity, streaming/recording or other priority workload. Stale activity telemetry is UNKNOWN, not idle.
- No conflicting GPU/CPU/IO leases, physical device duties or user-initiated tasks; respect approved quiet/resource limits.
- Sufficient memory, disk scratch space, thermal and power headroom, and a bounded uninterrupted stage budget.
- Operator STOP, local policy override, new foreground activity, increased contention or thermal risk interrupts and yields promptly. The benchmark never overrides foreground use; safe cancellation and cleanup produce truthful receipts.

**Benchmark classes**
- CPU: single/multicore workloads and relevant instruction-feature performance with bounded utilization.
- RAM: bandwidth and latency using bounded memory.
- GPU: compatible compute-backend tests, per-GPU measured throughput/latency and VRAM pressure (not unbounded stress).
- Storage: safe bounded scratch-only sequential/random read/write; never production DB or critical filesystem paths; capped wear and cleanup verification.
- Network: only approved endpoints, bounded bandwidth/latency, never unapproved public speed tests.
- LLM: approved, **already installed** exact model/digest and runtime; prompt-processing throughput, generated tokens/sec, time to first token, cold/warm readiness, RAM/VRAM consumption and failure rates; synthetic non-private prompts with provenance, no auto model pull.
- Module-specific: benchmark relevant workloads only when supplied as reviewed non-effectful tests in a compatible module profile; never pulse physical actuators or issue network/device commands without separate authorization.

**Benchmark record**
benchmark_id; test_suite/revision/digest; workload/profile; exact host, VM, resource and device IDs; vendor/system specs snapshot ref; OS/kernel/driver/runtime; model identifier/digest if used; configuration/context size; test start/end; preflight activity/thermal/lease telemetry refs; samples/results with unit, variance and confidence; cancellation/failure reason; baseline; measured resource use; provenance, verifier and source SHA; freshness/expiry; visibility/data classification. Keep multiple runs and revisions so drift and regressions can be explained. A single opaque combined "speed score" must not authorize placement.

**Acceptance tests**
- Initial host discovered → benchmark pending → verified idle → run and persist results; busy/gaming/stale observation blocks; preemption cleans up; reboot resumes safe stages.
- Resource contention, insufficient VRAM, unsupported driver, CPU-only host, virtual guest, multiple GPUs, overheating and expired reservation refuse or defer correctly.
- Synthetic exact-model inference benchmarks are bounded and require no new installation. Missing model remains missing; no silent model substitution.
- No benchmark touches production state, unapproved network endpoints or physical control devices. No credentials/private prompts in benchmark artifacts.
- Performance results drive **advisory ranking** but never bypass trust, current capacity, health, privacy, safe device leases, approval or STOP.

## 5. Placement algorithm and hardware independence

1. Enumerate current, authenticated Fleet nodes from the authoritative host inventory; keep descriptive names only for UI. Never target strings "Venus" or "Artemis" in core policy code.
2. Evaluate exact module resource requirements against the shared capability schema. Distinguish static incompatibility, unmet live capacity, unknown state, denied trust and missing authorization.
3. Choose only approved package/profile/runtime/model digests and supported device classes, applying all hard predicates per actual CPU/GPU/device/VM resource, not an averaged host score.
4. Apply current reservation and lease checks, data locality and principal/audience restrictions. Some resources are host-pinned, some modules are portable and Core canonical state is never ordinary mobile workload.
5. Rank remaining eligible hosts using verified benchmark evidence, current available headroom, predicted demand, real latency, thermal/power policy and switching cost. Unknown benchmark data can be queued for testing; it is not fabricated. Hard constraints always beat ranking.
6. Record an explainable placement plan and admission receipt, acquire appropriate resource/device leases, route through existing SAFE/RUN, recheck at dispatch, and reconcile external outcomes without unsafe replay.
7. If no eligible worker is available, preserve the job/pending state or return honest unavailable. No unapproved new host enrollment, model swap, host cutover, silent worker failover or shadow Core.
8. For same exact model/digest across more than one worker, selection and failover are separate owner-configured policies; no automatic switch unless explicitly authorized, independently authenticated and execution/retry-safe.
9. Guest and physical hypervisor host resource parentage must be respected to prevent double bookings across VM and parent.

## 6. LLM/provider separation: do NOW as a staged, test-preserving boundary cleanup

**Decision:** Extract provider-specific implementation from Core in an isolated Codex-owned coding batch, after preserving current working entrypoints and a before-change regression baseline. Do not do a big-bang rewrite or remove real-model testing. This change is a prerequisite to claiming a clean Core/Platform/module ownership boundary; it is NOT itself proof that Core 1.0 or Platform is release-certified.

**Keep in Core:**
- provider-neutral CognitiveEngine and LLMProvider *interface/contract* (or a minimal neutral request/response protocol shared with the interface) and source-grounded reasoning policies;
- turn kernel, model-independent context, Memory/Identity/Personality, response validation, tool authorization handoff and model result interpretation;
- controlled deterministic fake/rule provider and tests; no direct Ollama process/API, model-host naming or provider-specific transport requirements.

**Move to Inference Module / Platform:**
- provider-specific Ollama client, tool-call marshalling and generation options, model load/unload/probe implementations into an approved inference provider adapter/module;
- configuration, factory construction and worker routing into Platform composition and PLAT-06/07; mTLS Fleet transport and resource admission remain Platform;
- use a stable versioned inference request/response+error contract, preserving tool-candidate-as-data and existing SAFE/gateway execution boundary; provider cannot authenticate owner or perform tool actions;
- retain backwards-compatible import shims for existing call sites if necessary, with clear deprecation path and tests, then remove once callers migrated;
- no duplicate cognition engine, shadow state or second model authority.

**Migration test gates, in order:**
1. Capture BEFORE source revision and provider-neutral cognition, Ollama contract, routing, memory/context, authorization, tool-call and response-quality baselines.
2. Introduce interface and new adapter behind the existing factory, with one production code path; old and new adapter produce equivalent canonical requests/results/errors in deterministic golden fixtures. Never duplicate executable tool dispatch.
3. Keep Core unit tests running with a deterministic fake; keep Ollama provider tests with a stubbed client; do not count either as a live inference test.
4. Perform permitted actual local Ollama integration on an installed model, preserving exact provider/model identity and tool semantics. Test normal response, tool candidate, malformed result, cancellation, provider outage and response provenance.
5. Perform **actual approved remote** inference with the runtime on a disposable-state Linux VM and enrolled GPU worker(s), through pinned mTLS, with explicit host/resource admission. Test successful round-trip and offline/denied/partitioned workers. No local or alternate-model fallback unless independently authorized.
6. Compare end-to-end conversation, Memory/Personality, source/audience privacy, reasoning and operational cost before and after; run full affected regression set and B08 package/Windows/Linux acceptance separately.
7. Only after all required gates pass, remove old direct Core provider wiring, update ownership docs, and seek independent review. If gates fail, keep the proven path active and mark boundary work incomplete.

**Inference service class:** foundational but replaceable compute module. Required for generative conversation but not required for allowed non-LLM observation, bookkeeping or Platform recovery. Model weights live on an eligible approved worker; Sofía's identity never lives in those weights alone.

## 7. Pre-commissioning implementation slices and expected evidence

**HNF-01** shared typed capability schema, units, selectors, predicates and consistent unknown semantics.
**HNF-02** enrolled node/device inventory with observed vs manufacturer provenance and VM/parent mapping.
**HNF-03** live telemetry normalized to same schema; TTLs, leases and device identities.
**HNF-04** signed per-profile module hardware requirements and deterministic compatibility evaluator.
**HNF-05** background idle-window benchmark queue, safe preemption/cancellation and durable stage receipts.
**HNF-06** bounded CPU/GPU/RAM/storage/network and exact-model inference benchmark harnesses and evidence.
**HNF-07** multi-host capability-based worker placement + forecasts with authorization, reservation and model-pinning constraints.
**HNF-08** Core↔Platform↔Inference provider boundary extraction, backward compatibility, fake and real-model regressions.
**HNF-09** disposable VM and remote GPU-worker commissioning, fault campaigns, Windows/Linux packaging and independent review.

Each implementation slice must record production callers, typed data schema, migration/compatibility plan, policy, actual tests/commands/revision, failures and readiness level. Do not mark a slice RELEASE CANDIDATE/PRODUCTION READY from this document or mocks alone. Existing PLAT-05/06/07/08 and SF-13/14/16 owners remain authoritative; HNF IDs are acceptance slices, **not** a new parallel service or replacement for V18 task IDs.

## 8. Non-goals and boundary-preserving rollout

- No production Artemis/other-host writer promotion, package activation, re-enrollment, external physical effect, private benchmark data export or GPU model installation from adoption of this document.
- Do not change the currently running Venus single-writer topology by mere configuration edits. Live VM commissioning begins with a distinct disposable test DB and explicitly approved network/certificate configuration.
- Do not require a hypervisor-specific provider, a fixed PC name, a single GPU brand or only two physical machines.
- Preserve existing Core B08 schedule and correct working code. Make boundary extraction an integrated **test-preserving B08/Platform seam** task rather than a pretext to delay all Core acceptance.
- Source code, evidence ledger, Git history and actual host results must agree before claiming implementation.

**Owner acceptance test, in plain English:** "Enroll any eligible computer; record vendor-reported specifications and current measured headroom; queue benchmarks promptly when it is verified idle; select or refuse exact module profiles using the same typed resource keys; run the same approved LLM through any explicitly permitted worker while Sofía's canonical identity remains in one place; explain every decision without inventing test results."
