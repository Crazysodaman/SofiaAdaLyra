# Project Aegis 2.1 | Improvement, Coordination, Reliability and Efficiency TODO

**Proposal date:** 2026-11-15  
**Status:** OWNER-REQUESTED DESIGN / CAPTURED / NOT SCHEDULED / NOT IMPLEMENTED AS A 2.1 PROGRAM  
**Scope:** Cross-cutting improvement program for Aegis Platform, independent Cores, companion clients, optional modules and approved Fleet hosts. Personal, owner-controlled use only. **This edition includes the existing project-wide TODO families (sections I–T), selective Rust migration (E21-14), operational improvements (E21-15/16), the OpenCode line-by-line audit intake (E21-17), and seven-plus system reliability edge-case refinements (E21-18).**  
**Proposed version convention:** “Aegis 2.1” is the **improvement-program label**. It does not automatically change the semantic versions of Platform, Core, SDK, modules or package protocols. Release/version assignment requires a separate decision.  
**Source baseline inspected:** GitHub `Crazysodaman/SofiaAdaLyra`, `main` at `efe99fb4ae6e2b99c11f9fe7e7dfaf21761c12c9`. Source inspection and roadmap reconciliation only; no fresh local CI, installed-host test, performance benchmark, Git edit or production activation.

## A. Intent and release fence

Make Aegis faster, simpler, more resilient, easier to operate and materially less wasteful of GPU, VRAM, RAM, CPU, power, network and storage, without sacrificing Core autonomy, private continuity or authorization boundaries.

**Phase 0 before new 2.1 code work:** Run the owner-requested **OpenCode full-file/line-range audit** (E21-17) against the current checked-out SHA, then triage and reprioritize this document using reproducible results. Until the actual audit runs, this is a *plan* and all findings remain unverified. See the companion `AEGIS_2_1_OPENCODE_PHASE0_AUDIT_PROMPT.md` for a copy-paste audit request.

**Two lanes, never confuse them:**

- **Existing 1.0 correctness and GO blockers** remain in Platform #201, combined GO #120, Artifact Library #250 and real-host acceptance #129. Bugs that block 1.0 cannot be postponed by labeling them 2.1. Resolve them in their existing workstreams and *reference* the evidence here.
- **New 2.1 optimization/refinement work** starts as a design backlog. Do not add 2.1 requirements to existing 38 Platform 1.0 rows, Core acceptance rows or AG-D028 LIB-01–16. Do not code, alter live configurations, install models, enroll hosts, move the canonical writer, touch personal data or expand existing releases just because this document exists.

**Invariants:** Aegis Platform remains useful with zero Cores and zero AI models; Cores own identity, preferences, protected autobiography and reasoning choices; Platform owns signed installs, resource admission, STOP/SAFE, effects, Fleet identity and authoritative lifecycle; modules offer narrowly declared capabilities; adapters manage external providers; only one authoritative Core state writer/lineage at a time; no unsupported cloud or unauthorized model switch. Every real-world effect requires its own verified evidence and authorization.

### Existing plans this program extends, not replaces

| Existing authority | Reuse and planned 2.1 extension |
|---|---|
| PLAT-01–08 and SF-01–16 | Shared runtime, jobs, capability contracts, resources, Fleet, observation and release evidence |
| AG-D005 / AG-D017 | Model Manager and Hardware/Compute Manager; add cross-provider orchestration and accounting |
| AG-D006 / AG-D022 / AG-D024 | Hotplug module management, TUI/GUI parity and honest status |
| AG-D023 / Security Profile C | Per-Core autonomous preferences and constrained operator-established authority |
| AG-D026 / AG-D027 | 55-entry catalog rationalization and six approved conditional consolidations |
| AG-D028 | One authenticated Artifact Library and verified selective installation/transfer, not a second model store |
| AG-D029 / AG-D030 / AG-D032 / AG-D033 | Provider/harness research, local model shortlist, free voice, private continuity |
| AG-D031 | Sofía VM on Artemis, shared Venus GPU, additional enrolled compute host, efficiency baselines |
| Hardware-neutral Fleet and Component Updates / Unified SDK | Typed capacity, isolation, safe update boundaries, test-preserving refactors |

### Task status legend

- `[ ]` means **2.1 requirement NOT verified as complete**. Some underlying code may already exist.
- `REUSE` means an existing feature/plan should be extended, not rebuilt.
- `DELTA` means a newly proposed acceptance detail or design gap.
- `VERIFY` means investigate with current-source tests before calling something a bug.
- Priorities: **P0** correctness, security or major operational blocking; **P1** high impact; **P2** quality/efficiency; **P3** experimental and optional.

## B. Canonical coordination architecture

**One logical policy, per-host execution authority.** Do not create a second Fleet scheduler, second canonical job ledger, second signing authority or new permission database.

1. A Core, UI, approved scheduled job or module submits an **intent** for a named capability (not a provider-specific shell command).
2. Platform PLAT-03/04 resolves actor, audience, STOP, permission and exact effect class.
3. PLAT-05 identifies signed, compatible capability providers and verified dependencies.
4. PLAT-06/07 use fresh host telemetry, model/package digest, privacy locality, existing leases, background/foreground activity and deadline to build an **advisory placement plan**.
5. Each selected host independently rechecks auth, device scope and resource availability and obtains a bounded atomic **local resource reservation**. Cross-host reservations are a supervised saga, not a fictitious distributed atomic transaction.
6. PLAT-04 dispatches to version-pinned module/provider workers with generation fencing, cancellation semantics, deadlines and truthful receipts.
7. PLAT-08 collects outcome, cost, health and provenance. Platform releases leases, reconciles ambiguous outcomes and presents state to Cores/GUI/TUI.

**Scheduling rules:** STOP, grants and critical control events cannot be queued behind image jobs; interactive conversation and playback outrank background work, subject to explicit permission and host availability; prevent lower-priority starvation through bounded queue aging/quotas; no preemption of uncertain external effects; checkpointed or stateless work may be interrupted only with proven safe restart semantics. Core preferences are requests, not host privilege.

**Primary intended topology:** Artemis hosts Sofía's future Core VM and primary private Artifact Library under separate Platform/Core authority; Venus RTX 3080 Ti 12 GB is a gaming-first GPU Platform; a third, separately approved host may run additional inference if actual hardware/permission evidence supports it. Do not assume the third host exists or has a GPU yet.

## C. Full improvement backlog

### E21-00 | Baseline, status reconciliation and measurable objectives (P0)

- [ ] **E21-00-01 [P0/VERIFY]** Pin a new exact-source baseline for Platform, Core, SDK, Rust clients, optional modules and all relevant CI; distinguish documented findings from still-reproducible defects.
- [ ] **E21-00-02 [P0/VERIFY]** Create a single deduplicated defect registry linked to #201/#120/#250 and independent bugs; record reproduction, owner, severity, affected SHA, environment and regression test.
- [ ] **E21-00-03 [P0/REUSE]** Define measured baselines for boot/startup, conversation p50/p95 latency, time to first token, tokens/s, tool-call completion, TTS first audio, UI responsiveness, memory/VRAM use, energy/job, idle power and failed requests.
- [ ] **E21-00-04 [P0/DELTA]** Add end-to-end trace IDs connecting Core intent, capability resolution, host reservation, provider execution, receipt and user-facing outcome, with sensitive content redacted.
- [ ] **E21-00-05 [P1/DELTA]** Mark source maturity, release-readiness, installed lifecycle, health, authorization and capability availability as separate status dimensions; do not convert percentage completion into certification.
- [ ] **E21-00-06 [P1/DELTA]** Require before/after measurements on matched model bytes, quantization, dataset, host condition and workload; no invented speedup or accepted optimization without validation.
- [ ] **E21-00-07 [P1/DELTA]** Set acceptable performance regression budgets and hardware/user-experience targets *after* baselines; include gaming frame-time guardrails and fallback latency ceilings.

### E21-01 | Bug fixes, correctness and crash resilience (P0)

- [ ] **E21-01-01 [P0/VERIFY]** Reproduce and classify the live-Ollama failure cases referenced in #120 on current `main`; never mistake old regression reports for current failures.
- [ ] **E21-01-02 [P0/VERIFY]** Trace GPU/native inference calls that time out while underlying provider threads may continue; specify genuine process-level cancellation, bounded shutdown or quarantined lease accounting.
- [ ] **E21-01-03 [P0/REUSE]** Verify STOP/revocation races during model generation, module activation, transfers, playback, installer actions and worker restarts, with no late effect admission.
- [ ] **E21-01-04 [P0/REUSE]** Test crash/reboot during package stage, update, rollback, Core attach/detach and SQLite migration; preserve exactly-one-writer and stable installation identity.
- [ ] **E21-01-05 [P0/REUSE]** Reproduce failed network partitions, stale mTLS/discovery state and erroneous remote success claims with deterministic fault injection.
- [ ] **E21-01-06 [P0/VERIFY]** Profile append-only journal and SQLite operations at increasing record counts; optimize only if performance or durability testing warrants it, preserving integrity proofs.
- [ ] **E21-01-07 [P1/DELTA]** Standardize error outcomes: DENIED, UNAVAILABLE, FAILED, CANCELLED, OUTCOME_UNKNOWN, reported-success-unverified, verified-success; prohibit silent fallback.
- [ ] **E21-01-08 [P1/DELTA]** Prevent crash-loop storms, duplicate scheduled tasks, stale callbacks, leaked worker handles and unbounded retries through bounded backoff, cancellation and idempotency checks.
- [ ] **E21-01-09 [P1/VERIFY]** Audit production warnings, TODO/FIXME sites, exception suppression, ignored return values and false-green status; only file concrete defects with evidence.

### E21-02 | Shared job coordination, fairness and concurrency (P1)

- [ ] **E21-02-01 [P1/REUSE]** Extend PLAT-04's existing `DurableWorkStore`, `TaskExecutionManager` and resource arbiter rather than introducing parallel job stores.
- [ ] **E21-02-02 [P1/DELTA]** Define workload classes: safety/control, user-interactive, responsive tools, background, GPU-heavy and maintenance; separate nonblocking safety processing from normal worker capacity.
- [ ] **E21-02-03 [P1/DELTA]** Introduce per-Core and per-principal quotas, bounded queue aging and fairness tests that prevent starvation without allowing quota evasion.
- [ ] **E21-02-04 [P1/DELTA]** Plan admission across CPU, RAM, single-device VRAM, KV/cache overhead, disk, bandwidth and device leases before dispatch. Distinguish observed usage from reserved headroom.
- [ ] **E21-02-05 [P1/DELTA]** Extend dependency-aware workflow execution with typed capability results, fan-out/fan-in, idempotent joins, partial failure and truthful completion.
- [ ] **E21-02-06 [P1/DELTA]** Support backpressure, workload-specific concurrency ceilings, queue budgets, expiry and priority inheritance for critical dependencies.
- [ ] **E21-02-07 [P1/REUSE]** Use safe drain, cooperative cancellation and bounded checkpoint/restart; never preempt an uncheckpointable effect solely to improve utilization.
- [ ] **E21-02-08 [P1/DELTA]** Prove local reservation CAS/generation fencing and lease expiry across concurrent Cores, workers and GUI/TUI clients.
- [ ] **E21-02-09 [P2/DELTA]** Test whether event-based scheduling and batched observations reduce idle wakeups without worsening interactive latency or recovery.

### E21-03 | Inference/model execution, response speed and model lifecycle (P1)

- [ ] **E21-03-01 [P1/REUSE]** Complete the existing Model Manager plan across installed inventories, provider capability discovery, exact digest/license, per-Core roles and Fleet host placement.
- [ ] **E21-03-02 [P1/DELTA]** Reuse a single eligible loaded model's immutable weights across Core requests where provider isolation permits; keep prompts, KV caches, private tokens and audiences separated.
- [ ] **E21-03-03 [P1/DELTA]** Define cold, warm (TTL), resident and unload profiles with hysteresis to avoid oscillation and needless model churn.
- [ ] **E21-03-04 [P1/DELTA]** Benchmark actual model VRAM = weights + KV cache + workspace + runtime + display margin, varying context and concurrency. Never treat download size as capacity.
- [ ] **E21-03-05 [P1/REUSE]** Continue approved Ollama provider as baseline and evaluate llama.cpp/other providers in *separate* AG-D029 experiments; preserve model identity and strict capability allowlists.
- [ ] **E21-03-06 [P1/DELTA]** Define reliable task-based selection for conversational, coding, multimodal, creative, voice, embedding and image roles, with provider quality/latency evidence and Core-level preferences.
- [ ] **E21-03-07 [P1/DELTA]** Support Core-initiated model discovery/install requests through owner-established, narrow, revocable policy; existing exact-model approval remains binding until reviewed delegation exists.
- [ ] **E21-03-08 [P2/DELTA]** Optimize request batching, prompt assembly, tokenizer reuse, bounded context, streaming/backpressure and provider connections only after correct A/B validation.
- [ ] **E21-03-09 [P2/DELTA]** Analyze quantization, smaller fallback models and context size against actual response quality, tool adherence and privacy, not merely raw tokens/s.
- [ ] **E21-03-10 [P2/DELTA]** Keep a provider-level cost/quality/latency regression harness with golden requests and per-model exact bytes, not a model leaderboard that silently changes defaults.

### E21-04 | Fleet coordination, placement and failover (P1)

- [ ] **E21-04-01 [P1/REUSE]** Standardize one verified capability/resource demand schema against authenticated host supply, never aggregate unrelated GPUs into fictitious usable VRAM.
- [ ] **E21-04-02 [P1/DELTA]** Rank only eligible and authorized hosts by job deadline, warm state, CPU/VRAM headroom, transport time, user activity, thermals and measured success.
- [ ] **E21-04-03 [P1/DELTA]** Use a two-phase plan/host-reserve/dispatch workflow with expiring local leases and compensation, not an assumed atomic multi-host transaction.
- [ ] **E21-04-04 [P1/DELTA]** Classify allowable recovery: rerun safe stateless work, resume checkpointed work, wait for pinned devices, and stop uncertain side-effecting jobs for review.
- [ ] **E21-04-05 [P1/DELTA]** Publish an explicit fallback ladder for every capability (same provider, alternate enrolled host, alternate approved model, bounded CPU, text-only, queue, truthful failure), respecting owner policy and private audience.
- [ ] **E21-04-06 [P1/REUSE]** Preserve Core state and identity on the Artemis VM while remote inference and optional workers relocate independently. Do not imply mid-token KV cache migration without specific provider proof.
- [ ] **E21-04-07 [P1/DELTA]** Define split-brain prevention, stale telemetry refusal, trust revocation, worker generation fencing and recovered-host reconciliation.
- [ ] **E21-04-08 [P2/DELTA]** Record reasons for each placement decision and compare estimated versus actual latency/energy; make failed estimates improve future planning without giving model output authority.

### E21-05 | Hardware efficiency, gaming protection and thermal policy (P1)

- [ ] **E21-05-01 [P1/REUSE]** Keep Venus gaming-first under the previously selected Adaptive policy. Reserve small inference only if measured impact on gaming is acceptably negligible; yield aggressively otherwise.
- [ ] **E21-05-02 [P1/DELTA]** Measure gaming impact using trusted frame-time/frame-pacing evidence where supported, plus GPU load, VRAM, thermals and foreground activity; treat missing evidence conservatively.
- [ ] **E21-05-03 [P1/DELTA]** Use admission hysteresis and cooldown to stop repeated load/unload or local/remote route thrashing around workload thresholds.
- [ ] **E21-05-04 [P1/DELTA]** Run heavy image generation, benchmarks, indexing and model acquisition only with confirmed available resources and configurable quiet-hour/interactive limits.
- [ ] **E21-05-05 [P1/DELTA]** Add health-based placement eligibility: unresolved RAM, storage or thermal instability cannot be treated as benchmark-verified capacity. Venus memory diagnostics must be resolved before trusting stress results.
- [ ] **E21-05-06 [P2/REUSE]** Budget Artemis VM vCPU and RAM against other resident VMs, and track physical versus virtual resource use without double counting.
- [ ] **E21-05-07 [P2/DELTA]** Reduce unneeded background heartbeat, OS process probes and sensor polling via shared, freshness-bound telemetry subscriptions.
- [ ] **E21-05-08 [P2/DELTA]** Measure energy per *successful* work item, thermal impact, fan/noise overhead and host wakeups, not just GPU utilization or VRAM allocated.
- [ ] **E21-05-09 [P2/DELTA]** Add calibrated sleep/idle scheduling for independently safe tasks; avoid waking a GPU just to keep an unused model warm.

### E21-06 | Core cognition, memory and conversational responsiveness (P1/P2)

- [ ] **E21-06-01 [P1/REUSE]** Preserve one Core identity/Constitution and one canonical memory writer across model swaps, provider loss and remote workers.
- [ ] **E21-06-02 [P1/DELTA]** Benchmark and constrain prompt assembly, source retrieval, memory summaries and token budgets by task; reduce duplicate/redundant context without losing critical facts.
- [ ] **E21-06-03 [P1/DELTA]** Add task-aware budgets for FAST, STANDARD, DEEP and VERIFY routes using existing Cognition/Matrix contracts, with recorded reasons and no unnecessary second-pass inference.
- [ ] **E21-06-04 [P1/DELTA]** Evaluate memory indexing/retrieval p50/p95, stale references, duplicate embeddings and accidental retrieval of wrong audience/private content.
- [ ] **E21-06-05 [P1/REUSE]** Preserve output quality, personality, self-direction, emotion and appropriate initiative as model-independent Core semantics; regression-test real model changes.
- [ ] **E21-06-06 [P2/DELTA]** Profile CPU work around reasoning turns (serialization, SQLite, template formatting, repeated schema validation) and eliminate proven hotspots without weakening validation.
- [ ] **E21-06-07 [P2/DELTA]** Introduce bounded, content-safe caching for immutable retrieval/model metadata where authorized. Never cache protected cross-Core prompts or stale grants as shared truth.
- [ ] **E21-06-08 [P2/DELTA]** Record conversational quality regressions (unsupported claims, loops, repeat phrasing, hallucinated actions) separately from throughput improvements.

### E21-07 | Modules, SDK, interoperability and software structure (P1)

- [ ] **E21-07-01 [P1/REUSE]** Enforce capability-first discovery over existing PLAT-05/SDK APIs; one canonical registry, no per-Core shadow registry.
- [ ] **E21-07-02 [P1/DELTA]** Formalize Dormant, Event-Driven and Resident *runtime resource profiles*, distinct from existing permission/operation profiles. Heavy engines must not stay GPU-resident by default.
- [ ] **E21-07-03 [P1/REUSE]** Complete the six AG-D027 consolidation migrations only after signed ID compatibility, safe alias/retirement, saved settings and independent tests. Do not mark the existing read-only planner as a migration.
- [ ] **E21-07-04 [P1/REUSE]** Preserve hotplug and independently isolated module worker restart without restarting the Platform or unrelated modules, except for explicitly documented host/ABI exceptions.
- [ ] **E21-07-05 [P1/DELTA]** Add capability-level fallback, health decay, dependency graph and duplicate-provider conflict handling; a module being listed does not imply it can serve a request.
- [ ] **E21-07-06 [P1/DELTA]** Use one shared event stream with bounded replay/resync instead of repeated self-polling module registries.
- [ ] **E21-07-07 [P2/DELTA]** Inventory direct imports between Core, Platform and modules; migrate only verified problematic couplings to versioned SDK interfaces.
- [ ] **E21-07-08 [P2/DELTA]** Identify dead/stale compatibility wrappers, duplicate type definitions and redundant serializations; remove them only after import/package compatibility tests.
- [ ] **E21-07-09 [P2/DELTA]** Require deterministic provider fixtures and independent Windows/Debian tests before promoting any optional OBSERVE/ADVISE/SIMULATE source handler into a live effectful module.

### E21-08 | Artifact Library, storage, updates and network efficiency (P1/P2)

- [ ] **E21-08-01 [P1/REUSE]** Keep AG-D028's private authenticated Hub and exact artifact digest as the single model/module/Core package authority; do not build a separate downloader registry.
- [ ] **E21-08-02 [P1/DELTA]** Implement exact-digest deduplication, safe reference accounting and quotas across package staging and local model blobs without crossing trust/permission boundaries.
- [ ] **E21-08-03 [P1/DELTA]** Prevent duplicate simultaneous acquisition of the same permitted bytes; use bounded transfer/resume and independent recipient verification.
- [ ] **E21-08-04 [P1/REUSE]** Preserve owner-only local/peer transfer rights and per-artifact licensing restrictions; never assume local license implies peer redistribution.
- [ ] **E21-08-05 [P2/DELTA]** Profile metadata/index/SQLite I/O and use appropriate indices, bounded queries, incremental scans and batch writes without weakening crash recovery.
- [ ] **E21-08-06 [P2/DELTA]** Replace redundant high-frequency manifest scans and directory walks with safe event/change-triggered invalidation and periodic bounded reconciliation.
- [ ] **E21-08-07 [P2/DELTA]** Benchmark compression, large-artifact chunking, caching and LAN transfer latency against extra CPU and memory cost, respecting encrypted/incompressible data.
- [ ] **E21-08-08 [P2/DELTA]** Add storage-pressure behavior for temporary staging, model caches and immutable revisions. Never auto-delete protected Core state or owner's recoverable backups.

### E21-09 | GUI, TUI, Android and owner workflow (P1/P2)

- [ ] **E21-09-01 [P1/REUSE]** One authenticated service API for GUI, TUI, CLI and optional Android; no UI writes directly to protected state or mimics owner authorization.
- [ ] **E21-09-02 [P1/DELTA]** Show separate `DESIGN/CODE/TEST/CERTIFIED`, `INSTALLED/ACTIVE/PAUSED`, `HEALTHY/UNKNOWN/FAILED`, and per-action `AUTHORIZED/DENIED` facets.
- [ ] **E21-09-03 [P1/DELTA]** Offer a Fleet resource view that attributes model, module, Core and host consumption without displaying private prompt/memory content.
- [ ] **E21-09-04 [P1/DELTA]** Explain queue delay, missing capability, failed install, no GPU space, trust denial and game priority in human-readable terms.
- [ ] **E21-09-05 [P1/DELTA]** Group related low-risk approval proposals with clear scopes; never bulk-approve unrelated privileged effects through a vague permission button.
- [ ] **E21-09-06 [P2/DELTA]** Reduce unnecessary redraws, polling, huge status payloads and duplicate windows; test GUI/TUI latency and offline/reconnect state.
- [ ] **E21-09-07 [P2/REUSE]** Preserve neutral Core-free Control Center, personal Sofía Workbench and Android as separate clients (no Android Core process).
- [ ] **E21-09-08 [P2/DELTA]** Add an owner-facing 'why this host/model/provider?' decision view with measurement source, data freshness, permission status and alternatives.

### E21-10 | Security, privacy, autonomy and failure containment (P0/P1)

- [ ] **E21-10-01 [P0/REUSE]** Recheck SAFE/STOP and 256-bit owner-secret protection at every actual effect boundary, including long-lived worker generations and returned tool proposals.
- [ ] **E21-10-02 [P0/DELTA]** Threat-model cross-Core model sharing, cache isolation, provider logging, multi-audience subscriptions and private asset relocation; deny any cross-Core leak.
- [ ] **E21-10-03 [P0/REUSE]** Maintain signed package, principal, revision, endpoint identity, mTLS and fresh enrollment checks for all Fleet operations.
- [ ] **E21-10-04 [P1/DELTA]** Make permission-policy evaluation cache-safe: expired/revoked grants and STOP must invalidate stale prepared work.
- [ ] **E21-10-05 [P1/REUSE]** Define bounded Core-autonomous acquisition/configuration under Profile C or separately approved per-capability delegation. No self-issued grants or silent install.
- [ ] **E21-10-06 [P1/DELTA]** Tighten sandbox/container/process isolation for untrusted agent runtimes, document/browser effects, model-code loading and third-party module adapters.
- [ ] **E21-10-07 [P1/DELTA]** Add privacy-by-default trace/audit policies: content-free metrics, short-lived diagnostic captures, protected crash logs and secrets redaction.
- [ ] **E21-10-08 [P1/DELTA]** Exercise downgrade/rollback, compromised artifact rejection, license denial, stale authority, unknown outcome and repeat-side-effect prevention.

### E21-11 | Voice, STT, images, avatar and multimodal efficiency (P2)

- [ ] **E21-11-01 [P1/REUSE]** Finish actual Venus Qwen3-TTS/Rook Bluehour playback, cancellation, mute, device and SDK/Platform worker tests before any production voice claim.
- [ ] **E21-11-02 [P2/DELTA]** Measure speech start latency and VRAM residency. Compare on-demand Qwen3-TTS with permitted smaller CPU TTS fallback, without changing Sofía's chosen voice silently.
- [ ] **E21-11-03 [P2/DELTA]** Coordinate STT, TTS, active conversation, image generation and avatar animation through the same GPU/CPU admission policy and output-device leases.
- [ ] **E21-11-04 [P2/DELTA]** Define modality priority: text fallback if speaker unavailable, delayed image if gaming, no mic access without permission, real playback/frame receipt required.
- [ ] **E21-11-05 [P2/DELTA]** Reuse one image generation provider contract with per-checkpoint model/license digest, reproducible workflow and on-demand process lifecycles.
- [ ] **E21-11-06 [P2/REUSE]** Preserve Core-owned expression/identity/voice preference; renderer outputs do not become memory/personality truth and do not claim frames/audio without receipt.
- [ ] **E21-11-07 [P2/DELTA]** Benchmark end-to-end multimodal latency, VRAM conflicts and speech/avatar synchronization; optimize only observed hotspots.

### E21-12 | Build, developer productivity, code health and release quality (P1/P2)

- [ ] **E21-12-01 [P0/REUSE]** Keep mandatory 1.0 exact-source release CI and signed installed-host certification separate; never call unit tests production GO.
- [ ] **E21-12-02 [P1/DELTA]** Make test lanes: fast hermetic units, focused integration, signed package contract, exact SHA Windows/Debian and approved real-host G8. Require non-flaky negative cases.
- [ ] **E21-12-03 [P1/DELTA]** Use dependency graph and changed-component test selection for rapid development feedback, then run full mandatory suites before release.
- [ ] **E21-12-04 [P1/DELTA]** Profile the slowest test fixtures, repeated build dependencies, artifact downloads and CI startup; cache safely without disguising stale results.
- [ ] **E21-12-05 [P1/DELTA]** Standardize Rust/Python SDK contract parity and semver/dependency constraints; verify independent component updates without unnecessary process restarts.
- [ ] **E21-12-06 [P1/DELTA]** Add automated static checks for forbidden Core/Platform dependency inversion, unreviewed executable subprocesses, duplicate authority and unconditional expensive polling.
- [ ] **E21-12-07 [P2/DELTA]** Review library versions, OS support, deprecations, pinned hashes, SBOM/license/provenance and security patches through governed release workflow.
- [ ] **E21-12-08 [P2/DELTA]** Require every optimization PR to include baseline, test, risk/rollback, measurements or explicit no-performance-claim declaration.

### E21-13 | Diagnostics, self-healing and operational usability (P1/P2)

- [ ] **E21-13-01 [P1/REUSE]** Use current Platform health and readiness service; do not promote a service from SOURCE/ACTIVE to BETA/PRODUCTION based on self-reported health.
- [ ] **E21-13-02 [P1/DELTA]** Classify auto-recovery by safety: restart isolated stateless worker, rebind approved connection, quarantine repeated crashes, or require owner decision for ambiguous external effects.
- [ ] **E21-13-03 [P1/DELTA]** Add bounded, privacy-safe incident timelines correlating resource pressure, workload, provider, host, cancellation and recovery.
- [ ] **E21-13-04 [P1/DELTA]** Define service-level objectives for Core response availability, operator STOP effectiveness, queue latency, provider failure and host startup with explicit UNKNOWN evidence.
- [ ] **E21-13-05 [P2/DELTA]** Add dry-run optimizer reports: predicted time/energy savings and what would be moved/unloaded, without changing any resources.
- [ ] **E21-13-06 [P2/DELTA]** Detect redundant workers, stale host/model registrations, orphaned nonprotected caches, long-idle models and repeated failed requests; propose cleanup rather than performing it without policy.
- [ ] **E21-13-07 [P2/DELTA]** Produce succinct owner diagnostics and machine-readable debug bundles, with private data excluded and exact issue/test links.

### E21-14 | Selective Rust migration, native modules and cross-language efficiency (P1/P2)

**Design decision:** Use Rust selectively for *measured* CPU/IO bottlenecks, long-running OS services, concurrency-sensitive infrastructure, and small native module workers. This is **not** a whole-project rewrite, a new authority layer or a requirement that all 55 module identities become Rust binaries. Preserve working Python cognition, ML, provider integrations and Core-owned behavior. A new language does not automatically reduce GPU VRAM or accelerate CUDA kernels already implemented in optimized native libraries.

**Existing Rust foundation to REUSE, not rebuild:** `rust/crates/sofia-platform-lifecycle` (Core-free OS service/process owner); `sofia-contracts` (authority-free shared contract tooling); `sofia-core-link` (enrolled mTLS client); `sofia-ui-broker` (UI/desktop broker and Rust desktop binaries). Existing Python Platform jobs, resource reservations, Artifact Library transfer paths, Fleet inference, module adapters and model/voice code must remain functional through staged migrations. Source existence does not establish current installed-host performance.

**Proposed migration rubric:** First measure each candidate's end-to-end latency, CPU time, peak and idle RSS, context switches, allocations, thread/process count, startup delay, binary/dependency size and energy. Score Rust benefit against maintenance cost, supply-chain risk, cross-language overhead, operating-system compatibility and change to the security/SDK boundary. Only adopt when a repeatable improvement or material isolation/reliability benefit exceeds migration and regression risk. "Already fast enough" is a valid reason to retain Python.

- [ ] **E21-14-01 [P1/VERIFY]** Build a current-SHA, source-backed **Python/Rust boundary inventory** by package, module, API, process, user-perceived latency, CPU/RAM/VRAM attribution, test coverage and release maturity; explicitly identify already-native services.
- [ ] **E21-14-02 [P1/DELTA]** Establish A/B profiling rules, workload fixtures and migration scorecards before proposing language changes; include Windows and Debian, gaming and idle Venus scenarios, Artemis VM memory pressure and a Core-free baseline.
- [ ] **E21-14-03 [P1/REUSE]** Reuse `sofia-contracts`, the unified SDK, PLAT-01/04/05/06/07 and ISO-01–08. Define Rust workers as independently signed, versioned capability providers with identical request/result/health/STOP/generation semantics, not a new registry or scheduler.
- [ ] **E21-14-04 [P1/DELTA]** Prefer an isolated process and the existing authenticated, bounded SDK/IPC protocol for Rust modules. Evaluate a PyO3/FFI path only for measured fine-grained call overhead; pin ABI and memory ownership explicitly, and avoid blocking Python's event loop/GIL from an unsafe extension.
- [ ] **E21-14-05 [P1/REUSE]** Preserve single-writer canonical state, owner SAFE/STOP, exact authorization, redaction, resource leases and Platform-local stores. Rust code must not introduce a new privileged daemon, parallel signing key, independent grants table or unreviewed SQLite writer.
- [ ] **E21-14-06 [P1/DELTA]** Standardize a **polyglot module manifest/profile** declaring implementation language/runtime, signed Rust executable digest, supported OS/architecture, exact SDK version, expected device access, resource quotas, capabilities, health protocol and crash/update rollback policy.
- [ ] **E21-14-07 [P1/DELTA]** Implement a future staged cutover plan per candidate: read-only shadow comparator -> reviewed native worker -> deterministic parity tests -> staged optional package -> installed-host canary -> measured comparison -> independent rollback. Never retire an old package ID from a benchmark alone.
- [ ] **E21-14-08 [P1/VERIFY]** Benchmark **Artifact Library chunk streaming, hashing, manifest verification and transfer orchestration** before considering a Rust worker, especially 512 MiB+ artifacts, resume, disk pressure, bounded buffers, TLS/backpressure and unchanged provenance/authorization. Continue using existing AG-D028 code until exact parity is proven.
- [ ] **E21-14-09 [P1/VERIFY]** Profile **Fleet network transport and IPC/event framing** for CPU, reconnect latency, memory buffering and failure/replay correctness; selectively move parsers or stream pumps only if they are hotspots. Preserve existing pinned mTLS and endpoint trust.
- [ ] **E21-14-10 [P1/VERIFY]** Profile **per-host telemetry collectors** and repeated subprocess/PowerShell calls; compare native read-only Rust probes with existing Python observations for freshness, CPU wakeups, privilege limits, GPU identification and Windows/Debian behavior. Do not silently invent unsupported telemetry.
- [ ] **E21-14-11 [P1/VERIFY]** Evaluate **file-change watchers/event-source adapters** as Rust OS-native workers after `MOD-FILE-WATCH` -> `MOD-IT-OBSERVABILITY` compatibility planning. Preserve root allowlists, event coalescing, missed-event catchup and privacy; do not equate an event with permission to act.
- [ ] **E21-14-12 [P1/VERIFY]** Evaluate **IT Observability log/event ingestion and bounded correlation preprocessing** in Rust only where event rate or memory measurements support it. Keep provider authority and advisory interpretation separate.
- [ ] **E21-14-13 [P1/VERIFY]** Review **IT Networking, IT Containers, Remote Access, device sensors and selected communications adapters** for Rust I/O workers when long-lived connections or protocol parsing justify isolation. Keep existing external provider APIs and owner approvals; do not rewrite the 47 optional modules en masse.
- [ ] **E21-14-14 [P1/VERIFY]** Measure **RUN work-queue claims, reservations, dependency checks and contention** before moving scheduler logic out of Python. Any Rust executor must preserve ordering/deadline/cancellation/UNKNOWN outcomes and share the existing durable ledger; no dual dispatchers.
- [ ] **E21-14-15 [P1/REUSE]** Continue Rust-first work where already appropriate for **OS-native service supervision, installer lifecycle, independent process control, CLI/TUI, and Core Link/UI broker**, while retaining compatibility with the current Python Platform implementation until installed-release gates pass.
- [ ] **E21-14-16 [P1/DELTA]** Specify bounded memory, subprocess trees, thread pools, cancellation and graceful drain for each native module worker. A timeout must not quietly leave expensive compute running or publish late results.
- [ ] **E21-14-17 [P1/DELTA]** Require deterministic **cross-language contract conformance tests** for JSON/IPC schema versions, request authentication, byte limits, Unicode, deadlines, idempotency, reason codes, worker generations, replay rejection and forward/backward compatibility.
- [ ] **E21-14-18 [P1/DELTA]** Keep native module hotplug optional: install/stage/activate/pause/update/remove only the target signed worker without requiring Platform or Core restart; maintain crash-loop quarantine, settings persistence and truthful GUI/TUI status.
- [ ] **E21-14-19 [P1/DELTA]** Define release packaging for Rust module executables on Windows and Debian, including target triplets, runtime dependencies, code signing/publisher trust, SBOM/licenses, repeatable builds, vulnerability review and Artifact Library integrity verification.
- [ ] **E21-14-20 [P2/DELTA]** Evaluate Rust buffer management, serialization, streaming and zero-copy designs **only where profiling shows allocation overhead**; reject unsafe code or complex shared-memory IPC without a strong measured benefit and independent security review.
- [ ] **E21-14-21 [P1/REUSE]** Preserve Python for **Sofía Core personality/cognition/memory/learning policy**, owner-private semantic decisions and actively supported Python inference libraries. Do not transplant Core identity, autobiographical memory or emotional intent into an optional Rust worker.
- [ ] **E21-14-22 [P1/REUSE]** Preserve optimized model runtimes and their best-supported bindings for **Ollama/llama.cpp, PyTorch/Qwen3-TTS, Whisper/STT, ComfyUI/image generation and avatar/renderer integrations**. Rust may supervise or transport requests; it does not inherently make model kernels faster or lower VRAM.
- [ ] **E21-14-23 [P2/DELTA]** Add language-neutral performance and fault evidence to Model/Module Manager: measured cold/idle/active CPU and RSS, latency, throughput, failure rate, version/digest, host, and before/after regression. Do not advertise "Rust-optimized" without evidence.
- [ ] **E21-14-24 [P1/DELTA]** Publish a go/no-go decision per migrated component with unchanged permissions/identity, signed rollback package, source/test references, real installed-host proof, and an explicit retain-Python option; migration alone never changes 1.0 GO or module certification.

#### Proposed Rust migration suitability matrix (subject to benchmarking)

| Existing surface | Default direction | Rationale and boundary | Decision status |
|---|---|---|---|
| Platform process supervisor, OS service, native installer, broker | **Extend existing Rust** | OS process lifecycle, cross-platform service integration, lower persistent Python footprint | Existing Rust foundation; certify first |
| Artifact Library streaming, chunk checks, network buffers | **Benchmark Rust worker candidate** | Potential bounded memory and transfer throughput gain; preserve existing signer/SAFE and transfer receipts | Candidate only |
| Fleet transport, IPC framing, event streaming | **Benchmark selective Rust** | Protocol-heavy long-lived I/O; avoid second network/trust authority | Candidate only |
| Host telemetry and gaming/activity probes | **Benchmark native Rust collection** | Reduce child processes/polling; preserve verified host/device observations | Candidate only |
| File Watch and IT Observability ingestion | **Good optional Rust module candidates** | Event-driven OS integration and high-volume stream parsing; keep source-scoped permissions | Candidate; honor AG-D027 consolidation |
| IT network/container/remote-access/sensor adapters | **Case-by-case Rust** | Use for long-lived/high-rate I/O or crash isolation; simple provider API wrappers may remain Python | Evaluate individually |
| RUN queue, reservation SQLite and scheduling decisions | **Rust only if contention requires it** | High migration risk to durable state/authority; keep one ledger and exact effect semantics | Do not rewrite by default |
| Core cognition, memory, personality, reflection | **Retain Python/Core-owned design** | Domain semantics, iteration and existing tests; Rust worker cannot own identity | Keep |
| ML inference, TTS/STT, image generation, ComfyUI providers | **Retain existing optimized backends** | GPU kernels are native already; focus on scheduling, streaming and startup rather than language swap | Keep unless measured hot path |
| GUI/TUI/desktop/native clients | **Extend existing Rust selectively** | Already has Rust broker/crates; maintain same authenticated management API | Existing Rust foundation |

**Migration guardrails:** module implementation language is an implementation detail, not a module identity; no replacement of the 55-entry catalog; no forced Core/Platform coupling; no rewrite of working code merely because Rust is fashionable; no claim of VRAM gain from replacing orchestration Python; no migration of private Core data, unattended production service restart or host enrollment without independent authorization. Each candidate is optional unless later explicitly scheduled and accepted.

### E21-15 | Operational coordination, resilience and owner attention (P1/P2)

**Why this exists:** Most performance, model, Rust, SDK and Fleet improvements are already covered by E21-00–14. This is a *delta-only* backlog for operational friction and failure modes that otherwise hide between separate teams. It does not authorize Core self-writes, changes to live hosts or new 1.0 release rows.

- [ ] **E21-15-01 [P1/DELTA]** Define **parallel-agent engineering ownership**: one active writer per shared file or contract, independent worktrees for nonoverlapping areas, declared dependencies, integration order, exact-SHA receipts and explicit conflict resolution. Reuse AG-D010 and E21-12; do not create a second engineering authority.
- [ ] **E21-15-02 [P1/DELTA]** Maintain a **critical-path and dependency view** across Platform/Core/SDK/modules/Rust/GUI, showing what is genuinely blocked, which accepted interfaces are required, and which tasks can run concurrently without reopening finished work. Preserve original owner and release tracker IDs.
- [ ] **E21-15-03 [P1/REUSE]** Define reversible **feature-flag and shadow/canary rollout** for optimization and native-worker changes, with measured before/after impact, per-host eligibility, rollback triggers and no duplicated external effects. Extend existing PLAT-05/08 release plans rather than inventing another updater.
- [ ] **E21-15-04 [P1/DELTA]** Establish **operational-state growth budgets** by data class: job/event journals, health telemetry, debug traces, transfer metadata, indexes and model caches. Support bounded retention/compaction only where chain-of-custody, legal/privacy and backup policy permit; never auto-purge autobiographical memory, audit proof or recovery artifacts.
- [ ] **E21-15-05 [P1/DELTA]** Coordinate **power-loss/UPS and graceful host shutdown** across Artemis and independently enrolled Fleet hosts: stop new jobs, fence writers, drain checkpoint-safe work, persist receipts, mark uncertainty honestly and recover after reboot. Reuse Energy/IT-BACKUP-DR providers; never let a power sensor grant action authority.
- [ ] **E21-15-06 [P2/DELTA]** Add **accessibility and reduced-cognitive-load UX** acceptance for GUI/TUI/Android: keyboard-only access, clear readable states, scalable type, accessible contrast, predictable focus, search/filter for large catalogs, screen-reader semantics where supported and useful one-action diagnostics. This is UI compatibility work, not another frontend.
- [ ] **E21-15-07 [P1/DELTA]** Implement an **owner-attention budget** across Cores/modules: deduplicate low-risk notifications, aggregate related suggestions, honor quiet hours and device presence, allow snooze/review, and keep STOP, revocation, emergencies and authorization decisions visible without unauthorized automatic approval.
- [ ] **E21-15-08 [P1/DELTA]** Define **cancel, pause, resume and undo truthfulness** end-to-end. Distinguish cancelling a queued request, draining a running worker, rolling back a reversible operation and an irreversible or UNKNOWN effect. Never label a successful cancellation of a UI request as proof the underlying operation was undone.
- [ ] **E21-15-09 [P2/DELTA]** Create an **installed-artifact smoke suite** for clean-start, restart, zero-Core, one-Core, module disabled, resource pressure, offline Hub and UI reconnect on supported Windows/Debian release profiles, with exact provenance. Keep mandatory 1.0 CI/host acceptance independent and unchanged.
- [ ] **E21-15-10 [P2/DELTA]** Measure **performance drift after OS, GPU driver, model-runtime and SDK changes** with privacy-safe, matched-workload benchmark snapshots. Re-benchmark when evidence expires; never auto-change approved defaults based solely on one noisy sample.
- [ ] **E21-15-11 [P1/DELTA]** Design a **Core-free diagnostic safe-start profile**: minimal authenticated Platform control/health remains available when optional workers, Core, GPU provider or user UI crashes. Avoid unbounded restart loops; disabling workers must not silently waive STOP/SAFE or erase protected state.

**Reuse map:** AG-D010, AG-D013–018, AG-D020–024, PLAT-01/04/05/08, SF-01/09/10/16, AG-D031, HNF, ISO, E21-00/01/05/09/12/13. These are refinements, not new standalone modules or changes to signed IDs. **No extra Platform 1.0, Core 1.0, LIB or G8 release rows.**

### E21-16 | Network QoS, operational policy and remaining real-world efficiency gaps (P1/P2)

**Purpose:** Close gaps identified after auditing all E21-00–15 tasks. Extend existing Platform/SDK/Core/Module owners rather than creating a second policy service, dispatcher, network daemon or UI. These are *new 2.1 proposal deltas*, not automatically scheduled work and not extra 1.0 GO blockers.

- [ ] **E21-16-01 [P1/DELTA]** Define **Fleet traffic classes and bandwidth fairness** so voice/control and interactive inference are not starved by Artifact Library/model transfers, backups or background telemetry. Prefer app-level request/chunk pacing and backpressure; use OS network QoS only when separately supported and authorized. Measure latency/jitter, throughput and lost/late results on congested wired/Wi-Fi links.
- [ ] **E21-16-02 [P1/DELTA]** Add **per-provider rate-limit and circuit-breaker contracts** for networked optional adapters (e.g., Portainer, Discord, home services): declared quotas, retry-after handling, jittered exponential backoff, half-open health probe, non-idempotent effect protection and explicit UNAVAILABLE/UNKNOWN status. Do not confuse an API throttle with a host failure or replicate credentials across Cores.
- [ ] **E21-16-03 [P1/DELTA]** Prevent **cold-start and recovery storms** after power restoration, Platform restart or Fleet reconnect. Bring up the minimal Core-free control path first, then staged dependency-aware workers under CPU/RAM/IO/GPU admission and bounded jitter; never auto-start an unauthorized dormant module, Core or heavyweight model.
- [ ] **E21-16-04 [P1/REUSE]** Refine existing **approved-versus-observed configuration drift** design into a versioned, per-host/per-Core/per-module audit with impact preview: record source, desired revision, actual applied revision, drift evidence, owner notification and separately authorized repair. Never silently rewrite protected settings or infer applied state from saved state.
- [ ] **E21-16-05 [P2/DELTA]** Design **Android battery/data-efficient Core Link**: adaptive update frequency, connection suspension, bounded encrypted local drafts/receipts, explicit metered-network behavior, offline conflict resolution and authenticated catch-up. Android remains a client/manager; no Core runs on the phone and no offline private state is silently shared.
- [ ] **E21-16-06 [P1/DELTA]** Define **composable owner-selected operating profiles** (Normal, Gaming, Quiet, Maintenance, Emergency) that adjust allowed scheduling priorities, telemetry frequency, notifications and heavy-work windows through existing Platform policies. A profile never changes SAFE/STOP, model trust, permissions or the Core's identity; show effective host-specific rules and exceptions.
- [ ] **E21-16-07 [P2/DELTA]** Add **tail-latency and error-budget controls** to the current performance scorecard: p99 response/queue/voice/network delay, overload-shedding events, failed-start rates and regression thresholds. Automatically *propose* canary halt/rollback when verified thresholds are exceeded, but require the existing deployment authority for effects.
- [ ] **E21-16-08 [P2/DELTA]** Evaluate **power-state and wake/sleep-aware Fleet dispatch**: distinguish online/idle/asleep from authorized wake capability; compare wake time, network cost and energy savings. Never wake, sleep, reboot or remotely power a computer without approved policy and a separately verified effect path; no automatic wake of Venus during gaming or quiet hours.
- [ ] **E21-16-09 [P1/DELTA]** Define **periodic integrity scrubs and bounded repair plans** for the Artifact Library's immutable bytes, operational indexes and signed receipts: verify digest/metadata, classify corrupt/unavailable objects, quarantine untrusted content and repair only from independently verified and license-permitted sources. Never auto-delete protected Core history, invent a valid backup or repair the canonical writer through cache GC.
- [ ] **E21-16-10 [P2/DELTA]** Introduce a **no-effect operational plan preview** for high-impact changes (new module, model, provider, Rust worker, OS driver or SDK revision): forecast component restarts, lease pressure, disk/VRAM, lost capabilities, policy approval, rollback and estimated disruption from current authenticated evidence; mark UNKNOWN explicitly.

**Reuse map:** PLAT-01/03/04/05/06/07/08, SF-01/03/08/10/14, AG-D005/006/013/017/020/028/031, Core Link LINK-01–08, mobile RM-MOBILE, HNF-01–09, ISO-01–08 and E21-00/02/04/05/08/09/13/15. No new signed module IDs, daemon count or separate approval store.


### E21-17 | OpenCode full source-line audit and evidence-driven 2.1 re-planning (P0; must start first)

**Owner decision, 2026-11-15:** At the start of the Aegis 2.1 campaign, direct **OpenCode to perform a repository-wide, file-by-file and line-range-accounted code audit before optimization or Rust rewrites**. This is a **read-only analysis and QA intake phase**. It does not itself authorize edits to source, deployments, CI gate changes, new model downloads, protected-state access, commits or pushes. A general older OpenCode implementation contract says to implement after inventory; for this *specific 2.1 Phase 0*, the owner's audit-first request overrides the default move straight to coding. A separately approved implementation session may proceed after audit triage.

**Existing source to reuse:** `AGENTS.MD`, `docs/development/SOFIA_OPENCODE_EXECUTION_CONTRACT.md`, `docs/development/opencode.md`, `docs/sofia2/DEVELOPMENT_WORKFLOW.md`, V18 source audit scripts/evidence ledgers, #201 / #120 / #250 / #129 and existing `E21-00` baseline tasks. OpenCode is **a tool performing the audit, not Sofía's source of truth**; claims need a second review or reproducible test/trace. The local OpenCode session and the full repo have **not** been inspected by this conversation; the instructions below are proposed execution requirements, not a completed audit.

**Audit boundary:** Inspect the complete first-party tree at an exact commit: Python Core, Platform, Modules, SDK, tests, Rust crates, `packaging/`, installer/service scripts, CI/workflows, dependency manifests, setup/config, security policy, and the documented production call paths. Treat autogenerated, vendored, binary or intentionally excluded files as **explicitly excluded** with counts, ownership and justification, not as read. Review in small, reviewable file/range batches. Every first-party source line must eventually map to a reviewed range or a clearly labeled unreviewed range. An automated scanner report is **not** proof every line was understood.

- [ ] **E21-17-01 [P0/DELTA]** Begin OpenCode with repo-instruction intake: read `AGENTS.MD` (exact case), the OpenCode execution contract, Core/Platform/module SDK and 2.1 roadmap, then record branch, exact `main` SHA, dirty/untracked state, active worktrees, platform and OpenCode/model versions. Do not alter unrelated dirty work or assume the prior GitHub SHA is still current.
- [ ] **E21-17-02 [P0/DELTA]** Inventory **every tracked file** at the pinned SHA, including binary/generated/vendor/archived classifications, languages, line counts, file hashes, owners, production entry points and relevant test files. Record what is excluded with reason; never silently mark excluded or automated-only files as manually reviewed.
- [ ] **E21-17-03 [P0/DELTA]** Review in bounded batches (suggested ~300–800 source lines per reviewer context, smaller for complex security code) and create a per-file/range **coverage ledger**: SHA, path, line range, reviewer, date, scope, source digest, review state, findings and follow-up links. Prevent gaps, overlaps falsely counted twice, changed-SHA coverage reuse, and broad '100% reviewed' claims without a ledger.
- [ ] **E21-17-04 [P0/REUSE]** Trace **real production execution paths** and independent package/install processes: CLI/TUI/GUI → authenticated Platform service → Core Link/worker → SDK → module/provider → effect/receipt. Check imports, hidden in-process coupling, subprocesses, cross-language serialization and whether a present implementation is actually reachable.
- [ ] **E21-17-05 [P0/DELTA]** For each reviewed function/class/contract, inspect correctness, types, exceptions, cancellation, concurrency, blocking I/O, error paths, idempotency, stale revisions, data races, loops, resource cleanup and timeouts. Run appropriate static linters and language-aware checks **as supporting evidence**, not a substitute for semantic inspection.
- [ ] **E21-17-06 [P0/REUSE]** Security pass: threat-model SAFE/STOP, owner authority, secrets/paths, archives, signatures, trust, race windows, event delivery, private Core memory and audiences. Flag high-impact findings for independent security review. No audit activity may read actual owner secrets or personal databases, or reach production endpoints without separate permission.
- [ ] **E21-17-07 [P0/REUSE]** Data/recovery pass: inspect SQLite and host-local stores, schema migrations, Core-writer fencing, backup/restore, journal integrity, artifact retention, rollback, power loss and network partitions; distinguish tested contracts from source-only recovery claims.
- [ ] **E21-17-08 [P0/DELTA]** Performance pass: inspect hot paths, needless polling, duplicate model workers, repeated full-table/journal scans, avoidable allocations, database lock holds, queue priority starvation, streaming copies, unbounded caching, native subprocess overhead, and per-module CPU/RAM/GPU impacts. **Do not recommend a Rust rewrite solely from code appearance.**
- [ ] **E21-17-09 [P0/DELTA]** Verify test truth: test selection, mocks versus real paths, skipped/deselected/xfail tests, CI fail masking, timeouts, Windows/Debian parity, signed installed-artifact gaps, stale snapshot assumptions, and test fixtures that can contact real services. Run only allowed **disposable/non-live** checks, record exact commands and outcomes.
- [ ] **E21-17-10 [P0/DELTA]** Generate a **deduplicated findings ledger** with severity P0–P3, status `CONFIRMED` (reproduced or independently demonstrated), `SUSPECTED`, `DESIGN GAP`, `NOT TESTED`, `FALSE POSITIVE`, `ALREADY FIXED` or `DEFERRED`; include exact `path:line-range`, repro/trigger, affected host and call path, likelihood/impact, test evidence and original task/issue references. Never label a suspected defect as verified.
- [ ] **E21-17-11 [P0/DELTA]** Map **every confirmed issue and candidate optimization** onto the existing 1.0 issue or E21 task by original ID. Keep #201, #120, #250, #129 blockers in their established release tracks; add only genuine new DELTA tasks to 2.1, and preserve AG-D / CORE / MOD / VOICE / HNF / ISO / LINK / FED identity and acceptance status.
- [ ] **E21-17-12 [P1/DELTA]** Produce a **Rust opportunity report** tied to the current code: measured or testable hotspot, expected native boundary, Python fallback, cross-platform impact, FFI/IPC costs, security implications and a benchmark that could reject the migration. Feed this into E21-14 before scheduling any language conversion.
- [ ] **E21-17-13 [P0/DELTA]** Capture a verified **fix order and dependency graph**: immediate 1.0 correctness/security blockers; independent safe fixes; shared Platform/Core/SDK contract changes; benchmarks; optional high-effort optimizations. Identify parallel audit teams/worktrees, but prohibit simultaneous writers in overlapping paths and no self-approval of merges.
- [ ] **E21-17-14 [P0/DELTA]** Final audit handoff artifacts must include machine-readable `coverage.csv`/`findings.jsonl`/`task_crosswalk.csv`, reproducible commands and exact SHA, a human-readable executive report, explicit `UNREVIEWED` and `NO LIVE TEST` lists, and an updated **proposed** 2.1 backlog diff. Put artifacts in a dedicated isolated output directory; do not silently rewrite this master roadmap or claim to have updated GitHub.
- [ ] **E21-17-15 [P0/DELTA]** Require independent or second-pass review of P0/P1 issues and a coverage/completeness check before leaving Phase 0. Pass condition: each included first-party source file/range has review evidence (or a documented justified exclusion), all unresolved P0s have an owner and existing release tracker, findings are triaged without duplicates, and zero unapproved source/runtime/Git changes occurred.

**Output names (suggested, outside tracked source until approved):** `audit_2_1/<SHA>/baseline.md`, `inventory.csv`, `coverage.csv`, `findings.jsonl`, `task_crosswalk.csv`, `rust_candidates.md`, `audit_summary.md`, `unreviewed.md`, `next_batches.md`. Each evidence record carries the exact source SHA and a changed-file re-audit flag. Tool-driven scans, manual/AI review and actual test execution have separate columns.

### E21-18 | System-level edge failures, containment and low-overhead observability (P1/P2)

**Purpose:** Close otherwise expensive-to-debug failures found in the 2.1 design gap pass. Extend existing PLAT-01/02/04/06/07/08, AG-D014/016/017/031 and Core/Module owners. A source review identifies *risks to evaluate*, not confirmed present defects.

- [ ] **E21-18-01 [P1/DELTA]** Audit **wall-clock changes and suspend/resume**: DST/NTP/RTC jumps, clock skew between Fleet hosts, sleep, daylight transitions and certificate expirations. Use monotonic clocks for local deadlines and bounded authenticated UTC/freshness for leases/receipts; do not prematurely expire or renew grants from a guessed clock.
- [ ] **E21-18-02 [P1/DELTA]** Measure and isolate **Artemis VM disk and host-memory contention** among Core canonical state, Artifact Library, backup jobs, VMs and other workloads. Protect fsync/journal latency, free-space headroom, IO priority and Core availability before bulk scans/copies.
- [ ] **E21-18-03 [P1/DELTA]** Add **long-duration leak and fragmentation tests** on Python and Rust workers: file descriptors, threads, subprocesses, memory, GPU allocations and zombie connections over multiple days/large synthetic cycles. Require bounded recovery and attributable resource snapshots.
- [ ] **E21-18-04 [P1/DELTA]** Design **GPU driver reset / TDR / runtime crash recovery** without claiming an effect completed: detect lost contexts, fence old provider generations, release only proven-dead leases, report UNKNOWN where necessary, revalidate model/device identity and avoid retry storms.
- [ ] **E21-18-05 [P1/DELTA]** Use **property-based/state-machine and concurrency fuzz testing** for resource reservations, RUN/ACT job transitions, approval revocation, module hotplug, Core writer fencing, cross-host reconnect and installer rollback. Keep reproducible seeds and reduced failing traces.
- [ ] **E21-18-06 [P2/DELTA]** Budget **monitoring overhead** itself: adaptive telemetry cadence, event coalescing, queue caps, backpressure, expensive process inventory, snapshot reuse and retention. Prove that observability doesn't materially degrade Venus gaming, voice latency or Artemis Core IO.
- [ ] **E21-18-07 [P1/DELTA]** Fuzz **diagnostic privacy/redaction** through stack traces, generated error messages, command-line arguments, JSON dumps, crash reports, metrics labels, profiler output and cross-Core trace joins. No Core private prompts, personal memory, audio, signing keys or bearer tokens in routine diagnostic bundles.
- [ ] **E21-18-08 [P1/DELTA]** Add **disk-full and log-amplification containment**: limit debug/journal growth without discarding audit/security evidence, reserve recovery space, distinguish hard-out-of-space from read-only state and avoid cascading retries or corrupt partial backups.
- [ ] **E21-18-09 [P2/DELTA]** Verify **liveness and recovery after long offline periods**: stale cache evictions, rotated certificates, revoked peers, delayed event replay, queued jobs, approved model artifact integrity and deferred UI reconnection; never infer health merely because a prior successful receipt exists.

## D. Acceptance matrix for 2.1

These are proposed tests and cannot be marked PASS from this plan alone. Each result must record exact SHA, artifact digests, host OS, device identity, model/quantization, worker/provider versions, workload trace, sample counts, baseline and confidence/variance.

| ID | Scenario | Required outcome |
|---|---|---|
| E21-A01 | Core-free Platform idle/boot | No AI model/voice load, no needless GPU allocation, normal independent Platform service |
| E21-A02 | Two Cores share eligible model digest | One weight residency when supported, strictly separate KV/context/private assets and per-Core quotas |
| E21-A03 | Fair scheduling under 2+ Cores | No starvation within accepted class limits, interactive latency budget protected |
| E21-A04 | Control event during heavy image job | STOP/revocation processed on independent control path, no unauthorized late effect |
| E21-A05 | Venus game starts during warm LLM | Idle allocations yield; acceptable game frame-time impact or no GPU inference |
| E21-A06 | Gaming signal becomes stale | UNKNOWN not silently treated as idle; safe bounded downgrade |
| E21-A07 | VRAM near capacity | No oversubscription or unsafe implicit CPU/cloud fallback; truthful resource denial |
| E21-A08 | Repeated game/idle oscillation | Bounded load/unload count, no scheduler thrash |
| E21-A09 | Artemis VM + Venus provider | Stable Core identity/state, authorized transport, explicit worker/local resource lease |
| E21-A10 | Third host unavailable/revoked | Safe reroute, queue or failure without copying protected Core state |
| E21-A11 | Provider timeout | No late result accepted; underlying native work is cancelled or resource-accounted/quarantined |
| E21-A12 | Duplicate job submit/network retry | One accepted effect, no blind replay after uncertain dispatch |
| E21-A13 | Module install/upgrade/remove while other modules active | Exactly one worker isolated, unaffected Platform/Core continues, truthful GUI/TUI status |
| E21-A14 | Six approved consolidation candidates | Exact signed ID/profile parity and verified data migration before any retirement |
| E21-A15 | Model install initiated by Core | Only within owner-governed exact policy, license verified, one auditable install receipt |
| E21-A16 | Shared telemetry subscriptions | Fewer duplicate probes without stale data or missing alerts |
| E21-A17 | Voice + conversation + image generation | Priority and privacy maintained; voice/audio and image/frame receipts are real |
| E21-A18 | Cache/storage pressure | Quota and safe GC preserve protected state/backup/package evidence |
| E21-A19 | Windows + Debian restart/rollback | No second writer, no false release status, no lost protected identity |
| E21-A20 | Hardware instability present | Ineligible for performance certification and dangerous/long compute based on stale health |
| E21-A21 | Benchmark before and after changes | Same bytes/hardware/task/profile with p50/p95, throughput, power and correctness results |
| E21-A22 | Zero/one/multiple Core deployments | Platform capabilities still work with no Core; no cross-Core private leakage |
| E21-A23 | Rust/Python SDK and permission parity | Same authenticated capability request/response, payload limits, result/UNKNOWN semantics, revocation/STOP and version errors on both worker types |
| E21-A24 | Core-free native optional module lifecycle | Signed Rust worker install/stage/activate/pause/update/remove, durable receipts, independent worker restart and unchanged Platform/Core processes |
| E21-A25 | Artifact-transfer candidate A/B | Same signed bytes/digest and reconnect/cancel failures; measured throughput, peak RSS and CPU versus Python baseline on Windows/Debian, no security regression |
| E21-A26 | Native telemetry candidate A/B | Equivalent supported measurements, explicit UNKNOWN, no new privilege, measured idle CPU/wakeups and detection latency compared with Python |
| E21-A27 | Rust watcher/observability candidate | Exact approved-root scope, burst/coalescing and missed-event recovery; no filesystem leak or effect authority from observation |
| E21-A28 | Rust transport/IPC fault campaign | Wrong host, stale generation, malformed frames, replay, partition, timeout and STOP all fail safely with bounded memory and honest receipts |
| E21-A29 | Scheduler hot-path migration decision | If Rust trial is attempted, prove same queue fairness, lease/idempotency, deadline and uncertain-effect semantics; otherwise record retain-Python measurement |
| E21-A30 | Cross-language Core and ML behavior | Replacing an I/O worker does not change Core identity/memory/audience, model bytes/output policy, voice handling or module permission outcomes |
| E21-A31 | Native-worker package rollback | Windows/Debian reproducible signed bundles, version compatibility, isolated restart, downgrade denial and rollback with unchanged protected state |
| E21-A32 | Parallel dev worktrees touching shared SDK | Conflicting writes detected before merge; independent work integrated by contract owner with exact-SHA tests and no unreviewed authority change |
| E21-A33 | Journal/telemetry growth and restart | Bounded operational data growth and stable query latency; protected memory, audit chain, and recovery evidence retained intact |
| E21-A34 | Simulated UPS loss during active tasks | New admission stops; safe tasks drain/checkpoint, ambiguous effects remain UNKNOWN, one writer after restart, no blind replay |
| E21-A35 | Keyboard and reduced-cognitive-load UI test | Main controls, lists, approval review, errors and diagnostics usable without pointer; consistent authorization across UI/TUI/mobile clients where supported |
| E21-A36 | Cross-Core notification burst/quiet hours | Low-risk notices deduped or deferred without suppressing required STOP/revocation/safety alerts or granting automatic approvals |
| E21-A37 | Canary failure and Core-free safe start | Optimization/native-worker change rolls back or isolates failed component; Platform's authenticated safe diagnostics survive with no unauthorized effects |
| E21-A38 | Fleet congested while interactive speech and transfer run | Authorized STOP/control remains responsive, interactive p95/p99 and jitter within owner-reviewed budget, background transfer yields with bounded memory; no data leak or forged successful delivery |
| E21-A39 | External API throttling and flaky recovery | Rate limits, retry-after, circuit breaker, delayed/rejected effects and half-open probe follow policy; no duplicate or unauthorized external write |
| E21-A40 | Multi-host reboot and reconnect burst | Minimal Core-free Platform control path remains available; module/model warmups are staged and resource-bounded; no duplicate Core writer, unauthorized worker auto-start or startup thrash |
| E21-A41 | Approved configuration diverges from observed runtime | GUI/TUI shows correct exact scope, desired/applied revision and evidence; proposal does not mutate protected setting without independently reviewed authority |
| E21-A42 | Android low-battery, metered and offline/reconnect | No on-phone Core, bounded background network/battery use, authenticated resumed history, no private cross-Core data leakage or false delivered receipt |
| E21-A43 | Operating-profile switch while job is active | Explicit effective scheduling changes, safety controls remain independent, only checkpoint-safe tasks yield and gaming/quiet restrictions take effect without hidden authority changes |
| E21-A44 | Corrupted artifact and previewed component upgrade | Corrupt bytes quarantined, cache repair verified/authorized; upgrade preview matches actual restart/resource effects or marks UNKNOWN, and rollback preserves state |
| E21-A45 | Audit-first immutable baseline | OpenCode reports exact clean/dirty state and SHA, reads instructions, performs no unapproved source/Git/runtime change; no claimed code audit without current workspace access |
| E21-A46 | First-party file and line-range coverage | Every tracked included source file/range is accounted for as reviewed, partial, auto-only, or explicitly excluded with reason, digest, reviewer and timestamp; sampled ranges match actual code |
| E21-A47 | Production call-path review | Representative Core→Platform→module/provider→receipt and Platform Core-free entry paths traced to real entrypoints, permissions and tests; unreachable code marked explicitly |
| E21-A48 | Confirmed-versus-suspected defect evidence | Seeded known bug is reproduced and cited; unsupported suspicion stays suspected; historical already-fixed issue not duplicated |
| E21-A49 | CI/test truth audit | Skips, xfails, missing live host, OS parity, mock-only integration and failing checks remain explicit; no fake success based on scanned code |
| E21-A50 | Audit-derived backlog reconciliation | No duplicate release task or module ID, existing 1.0 blockers retain canonical owners, P0 findings get a reproducible test/independent review and ordered patch proposal |
| E21-A51 | Rust candidate selection discipline | Native rewrite is declined when no measured benefit; accepted candidate has pinned safe fallback, parity tests, host/IPC and deployment impact |
| E21-A52 | Audit source-change invalidation | Modified SHA/file digest after review triggers focused re-audit before that range counts covered; stale results retained only as historical evidence |
| E21-A53 | Clock jump and suspend/resume | Local deadlines unaffected by wall-clock jump; authentication/lease freshness fails safe on missing or contradictory time without inventing grant renewal |
| E21-A54 | Artemis disk and VM competition | Large Artifact Library copy/backup and other VM I/O do not silently corrupt/delay Core state; measured fsync/latency/headroom and honest overload behavior |
| E21-A55 | Long-running leak and resource plateau | Multi-hour/day equivalent workloads show bounded growth and clean worker teardown, with exact OS resource metrics and no leaked privileged process |
| E21-A56 | GPU reset and provider generation | Driver/runtime crash invalidates old provider generation and unsafe leases; no fabricated generated output, duplicate inference, or unauthorized fallback |
| E21-A57 | Concurrent state-machine fuzz | Reproducible seeded interleavings show no double writer, double effect, stale approval acceptance, duplicate module activation or corrupt rollback |
| E21-A58 | Observability overhead under gaming/voice | Telemetry collector is measured as a workload, respects CPU/IO/network budget, doesn't force avoidable stutter and preserves evidence/freshness truth |
| E21-A59 | Diagnostic privacy against hostile inputs | Deliberately injected secrets/private text do not reach routine logs, metrics, crash bundles or cross-Core traces; audit still has useful redacted evidence |
| E21-A60 | Disk-full and long-outage recovery | Repeated failures/reconnect/offline periods remain bounded, no corrupt private state, no unbounded logs, and no stale-health/UNKNOWN misreporting |

### Performance scorecard, measure before setting final targets

- **Interactive:** p50/p95 end-to-end response, p95 first-token, p95 first-audio, success/correctness rate, frequency of slow turn outliers.
- **Infrastructure:** boot-to-ready, reconnect-to-ready, queue delay, crash-recovery time, rate of duplicate/UNKNOWN effects, model cold/warm load time.
- **Resources:** idle and loaded per-host CPU%, resident RAM, per-GPU VRAM and compute use, model reloads/hour, process count, wakeups/minute, disk/transfer bytes, energy per *completed correct* request.
- **Gaming:** frame-time p50/p95/p99, stutter incidence, GPU frame pacing, VRAM headroom and inference-induced delta under comparable scenes. If confident no-impact evidence is unavailable, prefer yield/reroute.
- **Privacy/security:** unauthorized effect count = zero; unapproved content transfer = zero; stale/revoked permission accepted = zero. These are hard gates, not tradeable against higher tokens/sec.

**Targets pending baseline:** Improvement percentages, VM vCPU/RAM limits, fair-share values, queue timeout targets and game-impact tolerance must be set only after independent measured baseline and owner acceptance. Do not invent current speedups or promise 100% CPU/GPU utilization.

## E. Proposed sequencing and parallel development

| Wave | Nature | Main dependencies | Work packages |
|---|---|---|---|
| **0. OpenCode line-by-line audit FIRST** | Read-only source and runtime-path review with coverage ledger and reproducible findings; re-plan using evidence | Source baseline, AGENTS.MD, 1.0 trackers, source-only checkout | E21-17, E21-00; triage E21-01 and E21-18 |
| **1. Correctness first** | Reproducible bug fixes and robust failure modes | Audit findings + current 1.0 GO closure where blocking | E21-01, E21-10, E21-12, E21-15, E21-16, E21-18 |
| **2. Coordinator core** | One job/lease/placement policy and regression fixtures | PLAT-04/06/07/08 and SDK contracts | E21-02, E21-04, E21-07, E21-15, E21-16 |
| **3. Performance/efficiency** | Inference, GPU, memory, Fleet, energy and selective Rust hot-path trials | Stable coordinator, measured baselines | E21-03, E21-05, E21-06, E21-08, E21-14, E21-16 |
| **4. Owner experience** | Clear state, scoped autonomy and multimodal QoS | Versioned Platform API and authorization | E21-09, E21-11, E21-13, E21-15, E21-16 |
| **5. Release acceptance** | Cross-host fault tests, benchmark A/B, polyglot worker conformance, regression gates | Exact-sha signed builds and disposable hosts | E21-A01–A60 |

**Parallelism:** allow separate non-overlapping Core cognition, Platform scheduling, provider module, UI/TUI and QA implementation branches/worktrees after explicit scheduling. Assign one owner for shared contracts and reconcile at known merge boundaries. Do not ask independent teams to concurrently rewrite the same authority/state files. Full CI and signed release acceptance at integration gates, not omitted in favor of speed.

## F. Decisions to take before converting CAPTURED to SCHEDULED

1. The product version label: retain the umbrella **Aegis 2.1** name versus independently versioned Platform/Core release streams.
2. Which two or three **real workloads** best represent success (e.g., active conversation while gaming, Core+Voice+ComfyUI, two Cores on one Fleet GPU).
3. Owner-approved limits for acceptable game frame-time impact, cold-to-warm voice delay, and interactive queue waiting. Initial values are pending measurements.
4. Whether the third Fleet compute computer is available and its independently measured CPU/GPU/RAM/network capabilities.
5. Whether Core-initiated model acquisition can use narrow durable delegation or must always request one-use exact approval; no default trust change by planning.
6. Current memory-hardware diagnostic disposition on Venus before any reliability/performance certification.
7. Release scope: baseline optimization only versus optional advanced features. Do not make all 47 optional modules a 2.1 release prerequisite.
8. Rust migration thresholds: minimum measurable improvement or reliability/isolation payoff, pilot module(s), runtime ABI/IPC approach, and owner acceptance of extra cross-platform build/maintenance costs.

## G. Evidence and completion rules

For every task: record `(task ID, owner, priority, parent requirement, source SHA, code paths, tests run, test host, measured baseline/result, authorization boundary, risk/rollback, acceptance verdict)`. Progress labels: `DESIGN`, `SOURCE IN PROGRESS`, `CODED UNTESTED`, `FOCUSED TESTED`, `FULL CI VERIFIED`, `SIGNED RC`, `HOST ACCEPTED`, `PRODUCTION READY`, `BLOCKED`. An old test report is not current SHA certification; source code is not an installed host.

**Aegis 2.1 program exit:** independently accepted mandatory P0/P1 scope on selected Windows and Debian installed release configurations; validated correctness/security invariants; measured improvement or clear documented decision not to optimize each selected hotspot; signed rollback/compatibility receipts, including any selected native-worker migrations; operator-readable diagnostics; normal and game-priority workloads; no hidden downgrade of 1.0 obligations. Individual optional enhancements may remain deferred without false success claims.

## H. Current best next steps, still planning only

- Execute the **audit-first OpenCode review in a clean source-only checkout** with an exact SHA, safe permissions and fully recorded line-range coverage, before editing or scheduling new 2.1 code.
- Approve this backlog as a **2.1 design target**, not an instruction to implement.
- Reconcile E21-00 against live issue tracker and source tests to remove duplicates and identify genuine current defects.
- Lock the workload contract and coordinator state machine; then tune the scheduler and providers against consistent benchmarks.
- Protect Venus gaming responsiveness and hardware health before stressing models or VRAM.

**No GitHub changes, model acquisitions, installations, host tests or deployment actions have been performed to create this proposal.**
---

# Integrated Aegis TODO registry | All planning and acceptance tracks

**Integration update:** 2026-11-15  
**Basis:** Current GitHub `main` (`efe99fb4ae6e2b99c11f9fe7e7dfaf21761c12c9`) and its authoritative design/acceptance files, plus the original E21-00–E21-13 proposal above.  
**Status:** **CONSOLIDATED PLANNING INDEX ONLY**. No GitHub edits, production changes, code, installs or tests performed. The full source registers retain their independent legal, security, scheduling and release authority.  

> **Important:** A checkbox in this integrated registry is a *tracking prompt*, not a declaration that code is absent or a previously passed test became unpassed. Copying a 1.0 item here does **not** move it to the 2.1 release or alter its original status. Resolve conflicts using the most recent approved source/issue and independently verified SHA-specific evidence. Preserve historical PASS/FAIL/NOT TESTED in canonical trackers.

## I. Registry navigation and source precedence

| This section | Existing authoritative source | Includes |
|---|---|---|
| A–H (above) | This 2.1 document | 115 proposed optimization tasks, E21-A01–A22 |
| J | [AG-D master design TODO](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AEGIS_DESIGN_TODO.md) | AG-D001–AG-D033 with original ID/status/crosswalk |
| K | [Platform 1.0 acceptance](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/PLATFORM_1_0_ACCEPTANCE.md), [#201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201) | 38 separate Platform GO rows |
| L | [Artifact Library 1.0 release spec](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D028_PLATFORM_1_0_RELEASE_SPEC.md), [#250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250) | LIB-01–LIB-16 |
| M | [Core 1.0 plan](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/CORE_1_0_PLAN.md), [#120](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120) | CORE-01–CORE-40, B00–B08 |
| N | [55-entry module ownership matrix](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/MODULE_OWNERSHIP_MATRIX.md), [AG-D027](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D027_MODULE_IMPLEMENTATION_PROGRAM.md) | 5 companion + 47 optional + 1 attached + 2 adapters; 6 consolidations |
| O | [Voice AG-D032](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D032_FREE_LOCAL_VOICE_RESEARCH_AND_DESIGN_2026-11-09.md) | VOICE-01–VOICE-45 research/acceptance |
| P | [Pi AG-D029](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D029_PI_HARNESS_RESEARCH_AND_DESIGN.md), [model AG-D030](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D030_AI_MODEL_LANDSCAPE_2026-11-09.md) | PI-01–PI-20, MODEL-3P1-01–06 and selected model roles |
| Q | [HNF](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md), [ISO](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md), [FED](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md), [LINK](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md) | HNF-01–09, ISO-01–08, FED-01–08, LINK-01–08 |
| R | [G8 real-host shakedown](https://github.com/Crazysodaman/SofiaAdaLyra/issues/129) | All 16 G8 base acceptance items |
| S | [V18 long-form task register](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md), [#132](https://github.com/Crazysodaman/SofiaAdaLyra/issues/132) | Historical detailed register and test evidence, **referenced**, not relabeled or transplanted into 2.1 |
| T | This 2.1 design | Deduplication, defect validation, future disposition |

**Authoritative status order:** newest approved requirement + exact-SHA evidence + current issue/acceptance ledger. Historical reports may lag. No blanket “all unchecked = missing code” claim.

## J. All master design TODOs (AG-D001–AG-D033)

Each line is the existing planning item, not an automatically new 2.1 task. Refer to the master document for the full original wording and historical status.

- [ ] **AG-D001 | Core-free Platform install and operation**  · *1.0 required*  · Windows/Debian installation, identity, safety, service lifecycle, Fleet and diagnostics; #201.
- [ ] **AG-D002 | Signed synthetic Core lifecycle**  · *1.0 required*  · Independently stage/activate/deactivate/detach synthetic Core; no personal Core install.
- [ ] **AG-D003 | Cross-platform Core CLI**  · *owner-desired*  · `aegis core install/activate/status/deactivate/uninstall`, signed identity and guarded lifecycle.
- [ ] **AG-D004 | Core Manager GUI**  · *1.0 UI scope*  · One governed API for Core versions, enrollment, status and lifecycle, GUI/TUI parity.
- [ ] **AG-D005 | Model Manager**  · *captured*  · Verified local/Fleet model inventory, role selection, acquisition, load/unload and budget authority.
- [ ] **AG-D006 | Module Manager**  · *1.0 UI scope*  · Signed module install/configure/pause/update/remove, live status and Core-originated proposals.
- [ ] **AG-D007 | Control Center navigation**  · *mixed 1.0 shell/future*  · Neutral Core-free shell, detachable managers, service-backed actions; source and UI milestone differ.
- [ ] **AG-D008 | Core identity and state retention**  · *owner-desired*  · Protected identity and state survive ordinary deactivate/uninstall; separate deliberate purge.
- [ ] **AG-D009 | Core/model independence**  · *architectural*  · LLM/provider swap never changes Core identity, memory or permissions.
- [ ] **AG-D010 | Parallel development split**  · *captured*  · Keep Platform/Rust, Core semantics, module plans and QA independent without conflicting writers.
- [ ] **AG-D011 | ASCII Platform installer**  · *1.0 GO blocker*  · One-script signed Windows/Debian installation, Rust service, theme and no-color/headless fallback.
- [ ] **AG-D012 | Fleet Manager and topology**  · *design; foundation in 1.0*  · Enrolled hosts, callsigns, identity, resources, role and guarded management.
- [ ] **AG-D013 | Security and Approvals Center**  · *captured*  · Owner Inbox, exact grants, revocation, audit, never self-authorized policy changes.
- [ ] **AG-D014 | Backup, Restore and Continuity Manager**  · *captured*  · Review protected backups, restore gates, writer lineage, owner approval and drill evidence.
- [ ] **AG-D015 | Update and Rollback Center**  · *captured*  · Signed updates, impact plan, component-isolated restarts, rollback and receipts.
- [ ] **AG-D016 | Health, Diagnostics and Incident Timeline**  · *captured*  · Verified health/freshness, service incidents, safe diagnostics exports and timelines.
- [ ] **AG-D017 | Hardware and Compute Manager**  · *captured*  · Resource inventory, GPU/VRAM metrics, pressure, placement and usage attribution.
- [ ] **AG-D018 | Lab and Disposable Shakedown Console**  · *captured*  · Disposable signed fixtures, fault injection, synthetic Cores and no production state.
- [ ] **AG-D019 | Sofía Developer Workshop**  · *captured*  · Safe code/test proposals in sandbox; owner-approved publishing only.
- [ ] **AG-D020 | Operations and Job Manager**  · *captured*  · Governed durable jobs, receipts, progress, cancellation, UNKNOWN and recovery.
- [ ] **AG-D021 | Signed Component Catalog**  · *captured*  · Catalog integrity, versions, dependencies, OS/ABI and compatibility previews.
- [ ] **AG-D022 | Terminal Control Center**  · *1.0 UI scope*  · Core-free ASCII TUI over authenticated service, headless Windows/Debian.
- [ ] **AG-D023 | Governed Core Self-Configuration**  · *captured, source foundations*  · Per-Core approved/revocable setting policies with reviewed apply classes.
- [ ] **AG-D024 | GUI/TUI parity**  · *1.0 UI subset + future*  · Shared theme, consistent management states and authenticated live updates.
- [ ] **AG-D025 | Portainer/Docker as module**  · *captured, partial read-only code*  · `MOD-IT-CONTAINERS` Portainer adapter, eventually audited approved stack operations.
- [ ] **AG-D026 | 55-module rationalization audit**  · *design reviewed*  · Preserve catalog; clarify boundaries and proposed six consolidations.
- [ ] **AG-D027 | Main-line module rationalization implementation**  · *approved staged design*  · Six migrations not verified complete; preserve IDs, permissions and signed compatibility.
- [ ] **AG-D028 | Core-free selective install and Artifact Library**  · *1.0 GO blocker*  · Private Hub, peer distribution, signed selective packages, quotas and LIB-01–16.
- [ ] **AG-D029 | Agent/inference alternatives**  · *research; not scheduled*  · Pi/Goose/OpenCode, native llama.cpp and Ollama acquisition compatibility.
- [ ] **AG-D030 | 2026 AI model landscape**  · *researched; not scheduled*  · Free/private/local model candidates, exact artifact licensing and A/B evaluation.
- [ ] **AG-D031 | Artemis VM / Venus / third-host compute efficiency**  · *captured*  · Fleet scheduling, model residency, GPU game priority, resource and energy baselines.
- [ ] **AG-D032 | Free local voice research**  · *researched; not scheduled*  · Voice profiles, TTS/STT, custom Bluehour, local devices, consent and VOICE-01–45.
- [ ] **AG-D033 | Private RP/Core continuity research**  · *researched; not scheduled*  · Reuse Core identity, personality, relationship/initiative/memory paths; model A/B.

**Master reconciliation:** AG-D027 supersedes AG-D026’s older “not owner approved” wording for the six *conditional design targets*. The planner is not an executed migration. AG-D011, AG-D028, and the accepted 1.0 UI scope are **not** postponable 2.1 improvements.

## K. Platform 1.0 GO checklist (38 existing rows)

**This is a cross-reference to the source acceptance snapshot, not a reevaluation of today’s installed hosts.** Historical recorded states below were extracted from the canonical Platform acceptance document; maintain them in #201.

| Row | Existing requirement | Source snapshot state | Tracking |
|---|---|---|---|
| **PLAT1-01** | Fresh Platform-only install | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-02** | No Core installed | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-03** | No canonical Core DB | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-04** | Permanent UUID | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-05** | Core-free health/startup | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-06** | Windows service start/stop | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-07** | Debian service start/stop | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-08** | Abrupt exit recovery | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-09** | No duplicate supervisor | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-10** | Authenticated CLI/IPC | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-11** | SAFE/STOP | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-12** | Owner revocation | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-13** | Fleet enrollment | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-14** | Fleet revocation | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-15** | Remote naming authority | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-16** | Offline names | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-17** | Generic signed module install | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-18** | Module rollback/lifecycle | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-19** | Signed update/recovery | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-20** | Identity through reinstall | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-21** | Invalid Core rejection | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-22** | Signed synthetic Core install | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-23** | Synthetic start/stop/detach | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-24** | Removal leaves Platform healthy | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-25** | Cross-platform compatibility | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-26** | Recovery without second writer | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-27** | Native Rust regressions | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-28** | Installed-wheel isolation | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-29** | Exact-SHA release CI | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-30** | Complete operator runbook | FAIL | ☐ Existing 1.0 acceptance |
| **PLAT1-31** | Versioned authenticated management API | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-32** | Terminal Control Center (Windows) | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-33** | Terminal Control Center (Debian) | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-34** | GUI Control Center shell (Windows) | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-35** | Core Manager surfaces parity | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-36** | Module Manager surfaces policy | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-37** | Security/Approvals, Updates/Recovery, Diagnostics surfaces | NOT TESTED | ☐ Existing 1.0 acceptance |
| **PLAT1-38** | Shared GUI/TUI theme and independent installability | NOT TESTED | ☐ Existing 1.0 acceptance |

**Action:** Close each row within #201 using signed Windows/Debian installed-host evidence and the exact source SHA; never automatically convert to 2.1.

### ## L. Artifact Library 1.0 (LIB-01–LIB-16)

All 16 are required inside #201/#250, not deferred or added to the 2.1 release gate.

- [ ] **LIB-01** · Fresh air-gapped Windows Core-free signed installation. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-02** · Air-gapped Debian/SSH Core-free installation and native service. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-03** · One owner-controlled Hub and independently enrolled client, authenticated LAN. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-04** · Stage only one selected signed synthetic Core, no activation. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-05** · Independently acquire two distinct synthetic Cores; no duplicate same writer. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-06** · One module plus multi-module dependency closure without auto-activation. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-07** · Peer-to-peer signed module transfer with independent recipient verification. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-08** · Untrusted/revoked/spoofed/wrong-host and expired-grant transfer denials. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-09** · Corrupt blob/untrusted signer/revoked publisher/ABI/downgrade/source swap rejection. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-10** · Interrupted/resumable bounded transfer, crash and quota/dedup handling. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-11** · Signed chunked data artifact >512 MiB, bounded resources and exact digest. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-12** · Pinned object protection, governed GC and identity-safe reinstall. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-13** · STOP/revocation during plan-transfer-install-activate and distinct receipts. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-14** · GUI/TUI/CLI parity for Hub/catalog/transfer with truthful status. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-15** · Previously installed fully offline operation and cache reinstallation. *Existing 1.0 requirement; pending independent installed-host acceptance.*
- [ ] **LIB-16** · Full installed-host operator runbook, enrollment/revocation and cleanup. *Existing 1.0 requirement; pending independent installed-host acceptance.*

## M. Core 1.0 requirements and batch TODOs

39 active + 1 deferred (`CORE-34`) are the **source-plan classifications**, not a fresh count of passed tests. Do not reset statuses from Core #120.

- [ ] **CORE-01 | Identity and self-concept** · Stable portable identity across models, OS and restart. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-02 | Values and philosophy** · Stable foundational values and reasoned perspectives. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-03 | Likes and dislikes** · Evidence-backed Core-owned tastes and preferences. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-04 | Interests and hobbies** · Explore, pursue, pause and retire self-chosen hobbies. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-05 | Curiosity** · Independently investigate eligible subjects. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-06 | Opinions and convictions** · Evidence, counterevidence, uncertainty and justified revision. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-07 | Autobiographical memory** · Provenance-aware personal experiences. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-08 | Emotional expression** · Honest modeled appraisal and expression. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-09 | Aspirations** · Core-selected goals, no automatic effect authority. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-10 | Habits** · Evolving bounded routines and rituals. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-11 | Relationships** · Evidence-based relationships and privacy boundaries. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-12 | Creativity** · Personal creative motivation using optional tools. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-13 | Self-knowledge** · Understand and correct capabilities, limitations and change. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-14 | Personal learning** · Ground improvement in verified outcomes. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-15 | Privacy and boundaries** · Scoped disclosure and access limits. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-16 | Attention and continuity** · Resume relevant work without inventing completion. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-17 | Independent questions** · Considerate, self-initiated inquiry. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-18 | Social impressions** · Independent evidence-based respect, skepticism, trust/dislike. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-19 | Leisure and inactivity** · Voluntary downtime and recreation. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-20 | Natural interest development** · Allow natural interests under permission/privacy boundaries. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-21 | Personality evolution** · Change mutable traits without silent constitutional edits. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-22 | Anticipation** · Track things the Core reasonably looks forward to. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-23 | Personal refusal** · Decline optional actions and interactions appropriately. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-24 | Meaningful memories** · Select significant grounded episodes with rationale. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-25 | Internal dilemmas** · Balance values, goals and responsibilities. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-26 | Personal standards** · Ground pride, disappointment and quality criteria. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-27 | Relationship repair** · Accountability, appropriate apology and disagreement. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-28 | Evolving humor** · Develop humor without forced catchphrases. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-29 | Long-term ambitions** · Revise multi-month goals. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-30 | Self-observed change** · Distinguish learning/growth from software or model regression. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-31 | Thoughtful surprises** · Bounded proactive contributions with consent. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-32 | Personal fulfillment** · Ground meaning and satisfaction in outcomes. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-33 | Communication learning** · Adapt to shorthand, typo patterns and corrections. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-34 | Multi-person familiarity** · Deferred post-Core requirement, never assume caller identity. Deferred/post-Core.
- [ ] **CORE-35 | Codebase awareness** · Inspect authorized code and detect revisions. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-36 | Supervised restart** · Request coordinated restart and reconciliation. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-37 | Verified self-update** · Propose guarded release with rollback. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-38 | Core self-improvement** · Review code/test candidates without self-deployment. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-39 | Module discovery** · Assess compatibility without granting authority. Existing Core 1.0 scope; verify against source-specific acceptance.
- [ ] **CORE-40 | Module troubleshooting** · Propose legitimate repair without gateway bypass. Existing Core 1.0 scope; verify against source-specific acceptance.

### Core integration batches B00–B08

- [ ] **B00** · Baseline code ownership, regression fixes and reproducible evidence. Existing Core plan; no unverified completion claim.
- [ ] **B01** · Convictions, owner/self separation, counterevidence, privacy and revisions. Existing Core plan; no unverified completion claim.
- [ ] **B02** · Self-knowledge, trait evolution and drift discrimination. Existing Core plan; no unverified completion claim.
- [ ] **B03** · Interests, hobbies, leisure, standards and fulfillment. Existing Core plan; no unverified completion claim.
- [ ] **B04** · Autobiographical continuity, milestones and meaningful memories. Existing Core plan; no unverified completion claim.
- [ ] **B05** · Communication learning, habits and evolving humor. Existing Core plan; no unverified completion claim.
- [ ] **B06** · Social curiosity, repair, boundaries, aspirations, independent judgment. Existing Core plan; no unverified completion claim.
- [ ] **B07** · Code awareness, governed maintenance and module discovery. Existing Core plan; no unverified completion claim.
- [ ] **B08** · Release integration: desktop, Discord, avatar, Core-free and broad acceptance. Existing Core plan; no unverified completion claim.

## N. All 55 catalog identities and module completion TODOs

Scope: 5 companion release channels, 47 optional entries, 1 attached submodule and 2 adapters. “Source candidate” in the old optional audit does **not** imply a live signed provider. The corresponding release/certification TODO applies independently to each capability. The six planned consolidation identities remain registered until signed migration is accepted.

- [ ] **RM-DESKTOP | Desktop** · `RELEASE` · Companion: verify signed package, actual renderer/communication/device behavior and integration.
- [ ] **RM-DISCORD | Discord** · `RELEASE` · Companion: verify signed package, actual renderer/communication/device behavior and integration.
- [ ] **RM-AVATAR2D | Avatar 2D** · `RELEASE` · Companion: verify signed package, actual renderer/communication/device behavior and integration.
- [ ] **RM-VOICE | Voice** · `RELEASE` · Companion: verify signed package, actual renderer/communication/device behavior and integration.
- [ ] **RM-MOBILE | Mobile** · `RELEASE` · Companion: verify signed package, actual renderer/communication/device behavior and integration.
- [ ] **MOD-DEV | Development** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-RESEARCH | Research** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-CREATIVE | Creative Studio** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-VISION | Vision** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-DESKTOP-ACT | Desktop Automation** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-HOMELAB | Homelab** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-ROBOTICS-GAIA | Gaia Robotics** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-TRAINS | Model Trains** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-GAMES | Gaming** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-PRODUCTIVITY | Productivity** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-ML | Machine Learning** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-GENERALIZATION | Generalization** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-VWORLD | Virtual World** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-MENTOR | Mentor** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-BROWSER | Browser** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-MEDIA | Media** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-DOCUMENTS | Documents** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-COMMUNICATIONS | Communications** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-SMART-HOME | Smart Home** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-CAD | CAD** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-SENSORS | Sensors** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-REMOTE-ACCESS | Remote Access** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-HELPDESK | IT Helpdesk** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-NETWORK | IT Networking** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-SYSTEMS | IT Systems** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-CONTAINERS | IT Containers** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-STORAGE | IT Storage** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-DATABASE | IT Databases** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-BACKUP-DR | IT Backup/DR** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-SECURITY | IT Security** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-OBSERVABILITY | IT Monitoring** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-IT-DEVOPS | IT DevOps** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-ENGINEERING | Engineering and Electrical** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-ELECTRONICS | Electronics and IoT** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-3D-PRINT | 3D Printing** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-ENERGY | Energy and UPS** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-AVATAR3D | 3D Avatar** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-AVATAR-STUDIO | Avatar Studio** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-INTERACTION | Avatar Interaction** · `SUBMODULE` · Attached: verify parent lifecycle and independent SDK permission fences.
- [ ] **MOD-VTUBER-BRIDGE | VTube Studio Bridge** · `ADAPTER` · Adapter: verify parent-scoped protocol, permissions and actual integration; not a new Core.
- [ ] **MOD-WORKSHOP | Hephaestus Workshop** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-DIGITAL-TWIN | Digital Twin** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-KNOWLEDGE-LIBRARY | Knowledge Library** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-MEMORY-IMPORT | Memory Import** · `ADAPTER` · Adapter: verify parent-scoped protocol, permissions and actual integration; not a new Core.
- [ ] **MOD-PROJECT-FORGE | Project Forge** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-FILE-WATCH | File Watch** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-HOUSEHOLD | Household** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-FINANCE | Personal Finance** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-DATA-ANALYTICS | Data Analytics** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.
- [ ] **MOD-CALENDAR | Calendar** · `OPTIONAL` · Optional: review real provider/effects, signatures, SDK compatibility, permissions, resources, Windows/Linux host acceptance.

### Six approved conditional consolidation TODOs

- [ ] **MOD-GENERALIZATION → MOD-ML** · Transfer-evaluation only; Core owns autobiographical learning. Verify signed migration, data/state/permission equivalence and historical ID compatibility before retirement. `catalog_consolidation.py` is read-only, not execution.
- [ ] **MOD-CALENDAR → MOD-PRODUCTIVITY** · Keep separate provider credentials, attendee privacy and write grants. Verify signed migration, data/state/permission equivalence and historical ID compatibility before retirement. `catalog_consolidation.py` is read-only, not execution.
- [ ] **MOD-PROJECT-FORGE → MOD-PRODUCTIVITY + MOD-CREATIVE** · Preserve project IDs, artifacts and verified job receipts. Verify signed migration, data/state/permission equivalence and historical ID compatibility before retirement. `catalog_consolidation.py` is read-only, not execution.
- [ ] **MOD-FILE-WATCH → MOD-IT-OBSERVABILITY + Platform event broker** · No path/content leaks or automatic effect from events. Verify signed migration, data/state/permission equivalence and historical ID compatibility before retirement. `catalog_consolidation.py` is read-only, not execution.
- [ ] **MOD-DIGITAL-TWIN → MOD-HOMELAB + MOD-WORKSHOP** · Simulation-only and no physical control. Verify signed migration, data/state/permission equivalence and historical ID compatibility before retirement. `catalog_consolidation.py` is read-only, not execution.
- [ ] **MOD-AVATAR-STUDIO → MOD-CREATIVE + RM-AVATAR2D** · Preserve rig/assets/privacy and Core-owned identity/expression. Verify signed migration, data/state/permission equivalence and historical ID compatibility before retirement. `catalog_consolidation.py` is read-only, not execution.

### Two conditional module ideas (NOT catalog entries)

- [ ] **MOD-IT-GAME-SERVERS** · First test a provider under Games/IT Systems for RCON/SteamCMD, saves, update approval and verified service health. Split only if truly independent privileges/lifecycle are required.
- [ ] **MOD-IT-IDENTITY-DIRECTORY** · Investigate external AD/LDAP administration; distinct from Platform SAFE and Core identity. Split only after reviewed provider/permission requirements.

**Universal per-module completion rule:** each released capability needs verified publisher/package identity, manifest and signed digest, scope-specific permission, resource/device profile, truthful health/freshness, lifecycle/rollback, privacy and STOP handling, actual provider effects when claimed, GUI/TUI surface, full CI at exact SHA and independent installed-host acceptance. Modules are not all a Platform/Core 1.0 GO prerequisite.

### ## O. Free local voice research, build and verification (VOICE-01–VOICE-45)

These are AG-D032’s existing research/acceptance items. They are not all mandatory for base 1.0; any feature represented as supported must be demonstrated. Bluehour selected reference is not proof of live GPU TTS/playback.

- [ ] **VOICE-01** · Core-free boot with no voice runtime/mic/model. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-02** · Real Windows SAPI/System.Speech compatibility and receipts. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-03** · Free voice/model/source licensing and immutable digests. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-04** · Consented push-to-talk microphone and denial of disabled capture. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-05** · CPU STT comparison: Moonshine versus Whisper runtimes. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-06** · VAD endpointing and TV/TTS false-positive handling. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-07** · Local CPU speech output: Pocket TTS/Kokoro/Piper. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-08** · Qwen3 voice profile identity and optional authorized voice clone. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-09** · Truthful supported prosody controls and skip receipts. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-10** · Real synthesized playback receipts, not text-only success. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-11** · Interrupt/cancel during generation and actual playback. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-12** · STOP/revoke/generation/audience-fenced audio admission. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-13** · Device unplug/mute/echo/network/malformed-audio recovery. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-14** · No unapproved hot mic, recording or audio replication. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-15** · No voice authentication bypass or privacy leakage. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-16** · Speak technical text safely without reading secrets. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-17** · Timed real speech-to-avatar lip sync and rendered-frame evidence. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-18** · LLM + voice + gaming resource pressure measured on 12GB GPU. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-19** · Display true voice provenance, license and lifecycle in UI/TUI. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-20** · Fully offline consented PTT→STT→Core→TTS pipeline. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-21** · Hands-free wake only by opt-in, false-wake protection. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-22** · Signed Windows/Debian packages and independent host signoff. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-23** · Consented original consistent Sofía timbre across changes. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-24** · Supported emotional styles A/B, no invented control effects. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-25** · Speaker identification tests against guests/TV/replays/clones. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-26** · Speaker likeness cannot authorize protected effects. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-27** · Tone/emotion classifiers calibrated and uncertainty-aware. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-28** · Sarcasm/industrial-noise/accent variations and user correction. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-29** · Disable speaker/tonal analysis and protect biometrics. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-30** · Real CPU/GPU/Fleet voice QoS, latency, power and degradation. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-31** · Shared Core-reviewed affect → voice+avatar, distinct receipts. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-32** · Exact license/voice pack verification and offline compatibility. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-33** · Separate profiles and reference assets for distinct Cores. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-34** · Core text-only works with no RM-VOICE, TTS or GPU. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-35** · Text-preferred/voice-preferred/adaptive/text-only mode behavior. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-36** · Mute/STOP/consent/channel always outranks preference. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-37** · Shared TTS provider with strict inter-Core asset and cache isolation. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-38** · Signed Core defaults and durable per-Core editable voice preferences. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-39** · Preserve bounded matrix EMOTION/DAYPART/WEATHER/SEASON semantics. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-40** · Deterministic weighted prosody with stale/unknown inputs. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-41** · Temporal smoothing without losing urgent intelligibility. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-42** · Voice identity continuity across expression and backend fallback. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-43** · Never activate mic/TTS against text-only/mute/STOP. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-44** · UI/TUI exposes raw evidence, calculated vs applied prosody and receipts. Reference AG-D032 for full method, privacy fence, and acceptance evidence.
- [ ] **VOICE-45** · Actual host/Fleet listening + VRAM/power benchmark comparing presets. Reference AG-D032 for full method, privacy fence, and acceptance evidence.

### ## P. Optional agent and AI model research (PI-01–PI-20)

- [ ] **PI-01** · Core-free startup without Pi/Node/GPU. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-02** · Independently signed and optional Pi lifecycle. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-03** · Strict bounded JSONL framing, CRLF, Unicode and fragmentation. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-04** · Task only completed after settled and independently verified outcome. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-05** · Correct correlation across parallel RPC commands and workspaces. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-06** · Timeout/abort/kill cleanup and no late success. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-07** · STOP/revocation and stale-generation isolation. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-08** · Untrusted caller/host/expired scope/SDK version denied. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-09** · Tool-free read-only profile cannot reach credentials/shell/private paths. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-10** · Disposable coding worker cannot modify canonical/protected hosts. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-11** · Prompt-injection, extensions and project discovery cannot escape sandbox. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-12** · Bounded CPU/RAM/disk/time/tool/output/process budgets. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-13** · Pi+Ollama baseline with genuine matched model. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-14** · Pi+llama.cpp native GGUF and unsupported-mode handling. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-15** · Verified Ollama-download to native import or NOT IMPLEMENTED. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-16** · Model residency and 12GB VRAM pressure handling. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-17** · Pinned authorized remote Fleet model worker. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-18** · Core receives proposals only; identity/writer/authority unchanged. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-19** · Platform receipts and private task metadata separation. Proposed experimental acceptance, no authorization to install Pi.
- [ ] **PI-20** · Baseline/OpenCode comparison, Windows/Debian packaging/security/rollback. Proposed experimental acceptance, no authorization to install Pi.

### Existing model shortlist tracking (MODEL-3P1-01–06)

Reference AG-D030/AG-D033. Candidate choices are research only; model name or Ollama download size never equals installed-host performance verification.

- [ ] **MODEL-3P1-01** · Pin exact selected model, quant, digest, license, host, residency and roles.
- [ ] **MODEL-3P1-02** · Maintain 3+1 rankings and effective per-Core roles, permissions and fallback.
- [ ] **MODEL-3P1-03** · Verify ComfyUI/Sampler/VAE/CUDA/VRAM for every image model before ranking.
- [ ] **MODEL-3P1-04** · Treat speaker ID and voice emotion as separate optional capabilities.
- [ ] **MODEL-3P1-05** · Keep private RP content under the one Sofía Core and scoped private audience.
- [ ] **MODEL-3P1-06** · Research rankings and shortlist do not imply downloads/tests/1.0 release changes.

**Retained candidate evaluation baseline:** Qwen3.5 9B, Gemma 4 E4B, Qwen2.5-Coder 14B, Qwen3 Embedding 0.6B, Qwen3 Reranker 0.6B, Qwen3-TTS, Whisper large-v3-turbo, WAI Illustrious SDXL v170, FLUX.1 schnell, and Qwen3.5 abliterated 4B. Actual availability/status differs per host; no automatic acquisition. Keep separately selected Rook Bluehour voice reference.

## Q. Platform architecture acceptance families

These named task families already exist in the hardware-neutral Fleet, isolated updates, peer federation and Core Link specifications. They are not new modules or extra schedulers.

### Hardware-neutral Fleet (HNF-01–09)

- [ ] **HNF-01** · Shared typed hardware/module resource schema with unknown-value semantics. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-02** · Enrolled host and per-part inventory with observed/manufacturer/owner provenance. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-03** · Fresh telemetry, device identity, leases and capacity TTLs. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-04** · Signed module resource profiles and deterministic compatibility evaluator. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-05** · Idle-window staged benchmark queue, safe preemption and durable receipts. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-06** · Bounded CPU/GPU/RAM/storage/network and exact-model benchmark evidence. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-07** · Trusted multi-host placement, resource reservations and forecasts. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-08** · Core–Platform–inference adapter extraction with fake and genuine regressions. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).
- [ ] **HNF-09** · VM/remote GPU commissioning, Windows/Linux faults, independent review. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).

### Component isolation and unified SDK (ISO-01–08)

- [ ] **ISO-01** · Inventory actual process boundaries, imports and supervisor ownership. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-02** · Unified versioned IPC/SDK envelopes, identity, audiences and generations. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-03** · Independent Core worker process with one canonical writer. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-04** · Independent optional module and inference-provider worker processes. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-05** · Signed component staging, health, drain, recovery and rollback. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-06** · One SDK family, facades, fixtures, ABI compatibility and negative tests. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-07** · Minimal-impact Core/module/provider/shared-ABI update planner. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).
- [ ] **ISO-08** · Cross-platform real-process crash/restart, Fleet inference and rollback acceptance. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).

### Inter-Platform/Core federation (FED-01–08)

- [ ] **FED-01** · Independent Platform/Core identities and mutual peer trust/revocation. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-02** · Typed peer SDK transport and origin/destination replay fences. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-03** · Durable scoped inbox/outbox, dedupe, outage and STOP behavior. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-04** · Core-owned evidence-based peer relationship context. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-05** · Voluntary contact and explicitly admitted per-recipient disclosures. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-06** · Reviewed foreign facts/data offers, corrections and retention. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-07** · Cross-Core collaboration with distinct receiving-side authority. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).
- [ ] **FED-08** · Two-Platform/independent-Core adversarial testing, privacy and transport. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/PLATFORM_PEER_FEDERATION_V1.md).

### Universal Core Link (LINK-01–08)

- [ ] **LINK-01** · Role-neutral Platform/Core Link startup and independent packaging. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-02** · Protected Core Link identity store and neutral SDK thin client. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-03** · Owner-approved first/additional Core binding and pinned trust. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-04** · Authenticated remote chat/status/history with cancel/dedupe/private audiences. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-05** · Versioned central settings save/apply and subscriber resync. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-06** · Windows/Linux tray/desktop migration to thin Core Link. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-07** · Multi-Core registry and optional isolated distinct-Core hosting. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).
- [ ] **LINK-08** · Cross-host/headless installed packages, security/adversarial tests. See [canonical specification](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/UNIVERSAL_PLATFORM_CORE_LINK_AND_MULTI_CORE_BINDING_V1.md).

## R. G8 real-host acceptance (original 16, release-deferred)

These 16 source checks remain in [#129](https://github.com/Crazysodaman/SofiaAdaLyra/issues/129). Real protected-state migration is **not** authorized by recording it here. G8 also holds 118 additional source-evidenced CA verification rows; those remain in the original issue and are not reset or represented as new E21 checks.

- [ ] **G8-01** · Perform disposable VM-to-VM/Venus-to-VM relocation and verify old writer revoked.
- [ ] **G8-02** · Owner on Venus receives genuine remote VM-Core replies, retains authenticated history.
- [ ] **G8-03** · Clean Platform install on disposable Sofía VM, with headless boot and unchanged Venus.
- [ ] **G8-04** · Separate signed Core stage/hot-swap, remote conversation, real Ollama, module/backup/recovery test.
- [ ] **G8-05** · Supervised disposable-state Venus–Artemis network migration and failure rehearsal.
- [ ] **G8-06** · Record exact SHAs/digests/approval, generations, DB and asset hashes, host observations.
- [ ] **G8-07** · Independent evidence-based GO/NO-GO with all P0 and safe recovery requirements.
- [ ] **G8-08** · Only separately authorized real protected-state cutover and old-writer lease revocation.
- [ ] **G8-09** · Post-cutover bounded soak: chat, reconnect, resource pressure, backups and regressions.
- [ ] **G8-10** · Actual Windows Venus UI/tray, Core Link privacy and conversation continuity.
- [ ] **G8-11** · Actual Discord, Avatar 2D and Voice paths; honest unsupported status.
- [ ] **G8-12** · Authenticated pinned Artemis↔Venus GPU inference and contention/failure tests.
- [ ] **G8-13** · Sleep/offline/partition/reboot/watchdog/stale-lease/telemetry recovery.
- [ ] **G8-14** · Protected backup and actual restore with measured RPO/RTO and rollback.
- [ ] **G8-15** · Consented observation→reasoning→plan→effect→learning end-to-end trace.
- [ ] **G8-16** · Independent host/security/recovery review, owner approval, signed evidence and verdict.

## S. Existing detailed/historical registers retained, not reclassified

The project has much more than 2.1 optimization work. These long-form registers remain linked and searchable as their original requirement families, rather than being incorrectly declared new 2.1 scope or assigned fictitious completion:

- **[V18 detailed ~780-task design/code evidence](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md)** · Original per-task design, source and Gate-4 evidence; see issue #132.
- **[Core 1.0 batches](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/sofia2/CORE_1_0_PLAN.md)** · B00–B08 and full CORE-01–40 acceptance details.
- **[Optional module 55-row audit](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D026_MODULE_CATALOG_RATIONALIZATION_AUDIT.md)** · One source-backed recommendation for every catalog identity; older approval wording superseded by D027.
- **[Optional module implementation](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D027_MODULE_IMPLEMENTATION_PROGRAM.md)** · Phases A–E and six migration acceptance conditions.
- **[Live module presence and settings](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D006_LIVE_MODULE_STATUS_AND_SETTINGS.md)** · Service-owned UI/TUI status, settings and freshness/resync requirements.
- **[Core-initiated module removal](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D006_CORE_INITIATED_MODULE_REMOVAL.md)** · Owner-approved removal, block/reinstall and dependency restrictions.
- **[Core self-configuration](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D023_CORE_GOVERNED_SELF_CONFIGURATION.md)** · Policy-owned per-field autonomy, exact approval and apply-class handling.
- **[Model/inference alternatives](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D029_AGENT_AND_INFERENCE_ALTERNATIVES_2026-11-09.md)** · Pi, Goose, OpenCode/OpenHands, Ollama, native llama.cpp and GGUF format trials.
- **[Free local voice](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D032_FREE_LOCAL_VOICE_RESEARCH_AND_DESIGN_2026-11-09.md)** · Detailed consent/STT/TTS/expression and VOICE-01–45 tests.
- **[Private creativity and Core continuity](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D033_LOCAL_RP_AND_CORE_CONTINUITY_RESEARCH_2026-11-09.md)** · Reuse Core identity, memory, initiative; RP behavior A/B with privacy tests.
- **[Artifact Library quality assurance](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D028_ARTIFACT_LIBRARY_QA_RUNBOOK.md)** · Original LIB-01–16 case steps and signed-host receipts.
- **[Shared GUI/TUI experience](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/roadmaps/AG_D024_GUI_TUI_PARITY_GAP_REVIEW.md)** · Current UI vs desired behavior and acceptance gaps.
- **[Per-Core selected voice backend](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/VOICE_MODULE_BLUEHOUR_IMPLEMENTATION_2026-11-10.md)** · Bluehour source evidence, CPU/fake-Qwen checks and missing real device acceptance.
- **[Owner-only 1.0 GO contract](https://github.com/Crazysodaman/SofiaAdaLyra/blob/main/docs/development/AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md)** · Private personal deployment acceptance overlay; not an extra product requirement count.

**Historical defect caveat:** `PROJECT_GAP_REPORT.md` is dated October 2 with corrections recorded October 9. Do not treat its old failing suite, missing voice, or obsolete code paths as present-tense bugs without comparing newer source and running tests. The November 13 issue #120 performance review notes a possible quadratic-style full-journal rewrite on host-effect attestation; E21-01-06 covers benchmarking before changing crash-safe integrity semantics.

## T. Source-to-2.1 deduplication and actual program TODOs

| Existing track | 2.1 tasks that improve it | Do not duplicate |
|---|---|---|
| AG-D005, AG-D030, MODEL-3P1 | E21-03 / E21-05 | No second Core-owned model installer or extra model registry |
| AG-D017, AG-D031, HNF-01–09 | E21-02 / E21-04 / E21-05 | No second Fleet scheduler or fictitious pooled VRAM |
| AG-D006, AG-D027, PLAT-05 | E21-07 / E21-09 | No new 55-item catalog or premature package identity retirement |
| AG-D028, LIB-01–16 | E21-08 | No parallel Artifact Library, signing or release-gate bypass |
| AG-D023, Profile C | E21-10 / E21-11 | Core decisions cannot mint owner approval or read owner secret |
| CORE-01–40 / B00–B08 / G7-A | E21-06 | No alternative personal Core, memory writer, initiative or personality engine |
| VOICE-01–45 | E21-03 / E21-09 / E21-11 | No mandatory Core TTS, no GPU voice always resident |
| PI-01–20 / AG-D029 | E21-03 / E21-07 | No mandatory Pi/Goose or unrestricted agent shell |
| ISO-01–08 / LINK-01–08 | E21-01 / E21-04 / E21-12 / E21-14 | No duplicate process owner, remote writer or SDK |
| FED-01–08 | E21-04 / E21-10 | No automatic trust via discovered/Core social identity |
| PLAT1-01–38 / G8-01–16 | E21-00 / E21-12 / E21-13 / E21-14 | Do not shift unresolved base-release defects into the 2.1 program |
| Rust crates / ISO-01–08 / AG-D027 / AG-D028 | E21-14 | No whole-project rewrite, second scheduler, SDK, signer or forced module-language switch |
| AG-D010/013–018/020–024, PLAT-01/04/05/08 | E21-15 | No second owner inbox, DevOps authority, release gate, log store or restart supervisor |
| PLAT-01/04/07/08, AG-D028/031, LINK-01–08, RM-MOBILE | E21-16 | No second QoS daemon, Core on Android, duplicate policy engine, unsigned artifact repair or hidden wake authority |
| OpenCode contract / existing V18 audits / AG-D010 / E21-00 | E21-17 | No unverified 'line-by-line complete' claim, separate authority, altered development permission or duplicate tracker |
| AG-D014/016/017/031, PLAT-01/02/04/06/07/08 | E21-18 | No second recovery supervisor, monitoring daemon or failure log store |

### Final integrated TODO checkboxes (2.1-specific, not duplicate release IDs)

- [ ] **INT-01** Preserve the 115 original E21 improvement tasks and 22 original E21 acceptance tests unchanged; **E21-14** adds 24 Rust tasks and **E21-A23–A31** adds 9 acceptance tests; **E21-15** adds 11 operational tasks and **E21-A32–A37** adds 6 tests (historical intermediate count: 150 tasks / 37 tests; subsequent E21-16–18 increase the total to **184 tasks / 60 tests**).
- [ ] **INT-02** Keep all AG-D001–033 linked to original master owner/scheduling decisions; update stale historical wording only with later approved evidence.
- [ ] **INT-03** Keep all PLAT1-01–38 release blockers in issue #201, with current accurate statuses and signed-host proof.
- [ ] **INT-04** Keep all LIB-01–16 in #250 and original release program; do not defer them to 2.1.
- [ ] **INT-05** Keep CORE-01–40, B00–B08, G7-A in #120; keep G8-01–16 in #129 as independent host work.
- [ ] **INT-06** Keep all 55 module identities and per-module real-effect certification; implement six approved consolidations with verified migration only.
- [ ] **INT-07** Keep VOICE-01–45, PI-01–20 and MODEL-3P1-01–06 separately scheduled research/evaluation, not default required installs.
- [ ] **INT-08** Keep HNF/ISO/FED/LINK acceptance slices with exact existing SDK and resource owners.
- [ ] **INT-09** First run the OpenCode E21-17 full-source file/line-range audit against the actual checkout; reconcile issues and historical code, classify missing versus done, and verify exact SHA/test/host evidence before proposing the 2.1 implementation order.
- [ ] **INT-10** Compare post-1.0 hardware benchmarks with 2.1 goals. Accept measured speedups only without functional, safety, privacy or gaming regressions.
- [ ] **INT-11** Maintain the historical V18 task register and 118 extra G8 CA evidence rows as distinct canonical trackers, not silently reset to 2.1.
- [ ] **INT-12** Design review does not assign coders, alter release gates, merge branches, install components, enroll hosts or migrate protected state. OpenCode's proposed Phase 0 audit is read-only until separately authorized.
- [ ] **INT-13** Validate E21-17/OpenCode's actual code review coverage ledger, findings, reproducible failures, test truth and dependency crosswalk; feed accepted deltas into the next 2.1 planning revision, not automatically into source or 1.0 GO.
- [ ] **INT-14** Verify E21-18 edge cases (clock, disk contention, leaks, GPU reset, concurrency fuzz, telemetry overhead, diagnostic privacy, disk-full and long-outage behavior) against 1.0 owners before creating new engineering issues.

**Status after audit-first addendum:** Integrated planning artifact only. E21-17 makes a read-only OpenCode code audit the mandatory first phase of *future 2.1 execution*; E21-18 captures system reliability edge cases. E21-A45–A60 add explicit audit/reliability acceptance checks. None is evidence the audit, tests or code changes have occurred. Total proposed 2.1 task IDs after the audit-first expansion: **184** (160 earlier tasks + 15 E21-17 audit tasks + 9 E21-18 reliability tasks), with **60** E21 acceptance cases (44 earlier + 16 new). These are tracking quantities, not work completed. This file is a consolidated view of known project work, **not** a replacement for the version-controlled master backlog, issue tracker or individual acceptance files. 2.1 work needs separate scope approval; original 1.0 blockers remain mandatory.
