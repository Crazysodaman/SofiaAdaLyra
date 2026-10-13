# Sofía V18: Original 700 Tasks + ML Expansion (40)

The original CA task IDs and V18 priority phases are retained. Descriptions are shortened for scanning; see the workbook’s **Original Wording** sheet or the original master roadmap for complete scope and safety conditions.

| Task number | Phase | What it does |
|---|:---:|---|
| CA-001 | 00 | Trace a real event through COGNITION v2 → NEURO → MEM → PERSONALITY/EMOTION → LIFE/GOALS → RUN/ACT → evaluation → persistence. |
| CA-002 | 00 | Capture the current baseline: memory correctness, topic continuity, unsolicited outreach quality, real avatar/voice synchronization, idle model… |
| CA-003 | 00 | Document authority, evidence, privacy, principal/audience, resource and error-state contracts for every new connection. |
| CA-004 | 00 | Preserve the already implemented COGNITION v2 and dual-model production interfaces; avoid restoring removed v1 ownership or adding competing runtime… |
| CA-005 | 00 | Publish a source-to-sink ownership map for the canonical event/evidence envelope: event_id, source, subject, principal, audience, observed time… |
| CA-006 | 00 | Add a revisioned CompanionDecisionTrace projection joining NEURO winner, eligible memories, chosen goal/activity, rejected alternatives, execution/ACT… |
| CA-007 | 00 | Add a reproducible baseline snapshot and test gates per commit. |
| CA-1201 | 00 | Write a companion-autonomy-contract.md defining event inputs, canonical owners, allowed downstream effects, idempotency, execution scope, failure… |
| CA-1202 | 00 | Define a versioned decision state transition graph with replay, dedupe, correction and restart tests; each optional action needs an expected-effect… |
| CA-1203 | 00 | Build an explicit context-window budget for episodic retrieval, workspace broadcasts, affect/style, project status and factual evidence. |
| CA-1204 | 00 | Add a governed feedback loop: receipts and user corrections update preference/association proposals after validity checks; never let model self-praise… |
| CA-1205 | 00 | Benchmark selected subsets from LongMemEval, LoCoMo and agent-environment memory as adapted internal tasks. |
| CA-1206 | 00 | Publish a production-acceptance matrix crossing model route × source × principal × audience × modality × permission × busy state × restart state ×… |
| CA-1207 | 00 | Add explicit model/provider outage and invalid-JSON handling with human-readable diagnostics; background project work must not wedge conversation or… |
| CA-1208 | 00 | Check privacy/data minimization: consent to retain optional episodes, scoped correction/deletion, retention windows and immutable audit evidence where… |
| CA-3101 | 00 | Map a single component ownership table for COGNITION v2, LIFE, GOALS, RUN, SAFE, ACT, MEM, NEURO, WORLD, DEV, Fleet and VM; record authoritative… |
| CA-3102 | 00 | Decide canonical Sofía runtime location and failover ownership before adding Hephaestus. |
| CA-3103 | 00 | Resolve the desired two-location database redundancy without two independent writers corrupting SQLite. |
| CA-3104 | 00 | Formalize the LIFE state machine for queued, running, completed, waiting-approval, blocked, failed, uncertain, paused, abandoned and verified… |
| CA-3105 | 00 | Define a decision-rights matrix across read-only sensing, safe autonomous tasks, scoped reversible actions, protected changes and… |
| CA-3106 | 00 | Choose Artemis-to-guest network topology for the actual hypervisor: fully offline private virtual switch; host-reachable internal switch with strict… |
| CA-3107 | 00 | Review Artemis privilege minimization for Hephaestus creation: constrained JEA/runbook or isolated provisioning agent, exact VM name/resources/network… |
| CA-3108 | 00 | Design host and guest identity and credential lifecycle: separate Fleet identities, secure key provisioning, rotation, revocation, bootstrap escrow… |
| CA-3109 | 00 | Specify an evidence taxonomy covering observed, verified, inferred, simulated, hypothesized, stale, unknown and revoked; define how sources, times… |
| CA-3110 | 00 | Document VM trade-offs: always-on Debian guest versus disposable/re-imaged per-project guest versus temporary per-job isolated process. |
| CA-3111 | 00 | Identify single points of failure and critical dependencies: Venus model runtime, Artemis power, DNS, PKI, Fleet broker, NAS, sofia.db, backup… |
| CA-3112 | 00 | Define truthful avatar/world/voice expression contracts: message content versus rendered frames, speech synthesis versus spoken audio, simulated world… |
| CA-3301 | 00 | Establish a design readiness gate for each phase: evidence of current source behavior, exact missing interface, competing designs, security/authority… |
| CA-3302 | 00 | Classify every V8 item as verified coded, coded but unverified, partial wiring, research hypothesis, design only or blocked; attach commit/evidence… |
| CA-3303 | 00 | Write a CI failure decision report for current commit: release test-import mismatch caused by nested release-source, pkg_verify Windows temporary DB… |
| CA-3304 | 00 | Build a counterfactual/ablation evaluation plan for LIFE alone, LIFE+MEM, +curiosity, +reusable skills, +NEURO competition, +associations and VM… |
| CA-3305 | 00 | Study long-horizon autonomy difficulty using staged 1-step, multi-step, restarted, one-day and one-week tasks; track actual objective completion… |
| CA-3306 | 00 | Study memory temporal correctness with LongMemEval-style extraction, multi-session, corrections, outdated facts and abstention plus a separate… |
| CA-3307 | 00 | Review skill-learning research such as Voyager and Reflexion as design patterns; identify the smallest reusable skill unit and evidence of transfer. |
| CA-3308 | 00 | Preregister connectome experiments comparing research-only circuit competition and sparse association against simpler deterministic NEURO and approved… |
| CA-3309 | 00 | Separate consciousness investigation from companionship claims: review multiple operational theories, confounders, negative controls, measurable… |
| CA-3310 | 00 | Design companion wellbeing constraints using research on affective chatbot use: optional outreach, no dependency optimization, user-set boundaries, no… |
| CA-3311 | 00 | Plan adversarial injection and supply-chain evaluations for untrusted web/Discord/VM outputs, model-generated plans, logs, saved memories, SVG/art… |
| CA-3312 | 00 | Draft a pre-coding architecture review packet: owner map, data-flow diagram, job/failure state machine, benchmark/profiling matrix, threat model… |
| CA-4001 | 00 | Build a source-verified comparison matrix for Letta, OpenClaw, Hermes Agent, OpenHands, Open-LLM-VTuber, AIOS, and OpenDAN: ownership, deployment… |
| CA-4002 | 00 | Specify reference-pattern adoption rather than wholesale dependency migration: borrow Letta-style stateful identity and separation of… |
| CA-4003 | 00 | Compare OpenClaw's per-peer and cross-channel identity-link mapping with Sofía's present channel/audience bindings. |
| CA-4004 | 00 | Evaluate Hermes' bounded curated profile, separate searchable transcript, procedural skill learning, and explicit memory update behavior against… |
| CA-4005 | 00 | Compare OpenHands isolated agent-server execution and Open-LLM-VTuber voice/rendering stacks against already-owned DEV, voice, expression and planned… |
| CA-4006 | 00 | Review AIOS and OpenDAN strictly as reference operating-layer architectures; decide whether any missing kernel-like scheduler, portable capability API… |
| CA-4501 | 00 | Resolve terminology in an architecture decision record: operating system kernel, user-level agent operating layer, dedicated Sofía appliance OS image… |
| CA-4502 | 00 | Compare (A) Sofía services on existing Windows/Debian, (B) dedicated Linux appliance VM with supervised services, (C) desktop-first full-screen Sofía… |
| CA-4503 | 00 | Specify Sofía Operating Layer as a set of existing SAFE/RUN/Fleet/Memory/session service interfaces with strict authority and resource budgets, rather… |
| CA-4504 | 00 | Design a future Sofía appliance image option: secure base distro, immutable/reproducible build, service supervision, encrypted storage, secure… |
| CA-4505 | 00 | Reject/custom-kernel defer unless a written hardware-control requirement cannot be met by Linux, Windows, drivers, containers or hypervisors. |
| CA-4506 | 00 | Prove OS/platform decision against core outcomes: cross-device chat, independent projects, VM experiment safety, voice/avatar quality, and recoverable… |
| CA-4701 | 00 | Explore human-facing memory control: inspect why Sofía believes something, who/what supplied it, last verified timestamp, correct/forget, mark… |
| CA-4702 | 00 | Explore portable session handoff UX: phone QR/device pair, visible active thread and delivery destination, 'continue here', local-only mode, last-read… |
| CA-4703 | 00 | Explore independent experiment notebooks in Hephaestus: reproducible manifests, hypotheses, expected outcomes, measurements, failed attempts… |
| CA-4704 | 00 | Explore latency-aware model placement: local fast-first, deep model for demonstrably hard tasks, multi-machine inference only via approved discovery… |
| CA-4705 | 00 | Explore simulated homelab resilience planning: apply/read-only observation from known Artemis/Eos/Hestia configurations to a non-authoritative digital… |
| CA-4706 | 00 | Explore software supply-chain and research provenance: dependency licenses, vulnerability update schedule, external paper/model dataset claims… |
| CA-5401 | 00 | Record architecture decision: Option A approved now = user-level Sofía Operating Layer on established Windows/Linux, one canonical identity… |
| CA-5402 | 00 | Define operating-layer interfaces independently of host OS so all clients can use one authenticated service contract for message timeline, memory… |
| CA-5403 | 00 | Record Option B approved but deferred = dedicated reproducible Linux appliance image after baseline acceptance. |
| CA-5404 | 00 | Establish explicit B entry criteria: stable production startup, full Phase6/LIFE cycle, passing pinned CI, verified portable conversation/memory… |
| CA-5405 | 00 | Compare B later hosted on Artemis or dedicated hardware for fault domains, SSD endurance, RAM/GPU, noisy-neighbor constraints, power, UPS… |
| CA-5406 | 00 | Design future B boot/release model: OS security update channel, immutable/pinned system base, two-slot app rollback, watchdog, encrypted local data… |
| CA-5407 | 00 | Quantify overhead of A vs A+B and bound duplication: no extra always-running LLM brain, redundant daemon pollers, independent authority issuers… |
| CA-5408 | 00 | Put any true operating-system kernel proposal outside active scope until a documented capability cannot be supplied by Linux/Windows drivers… |
| CA-901 | 01 | Unit-test each boundary plus the cross-matrix EXPERIENCE → NEURO → MEM → PREFERENCE → GOALS/LIFE → RUN → EMOTION/AVATAR/VOICE → REL/ACT. |
| CA-902 | 01 | Run a three-day independent project: choose a verified interest, create, evaluate, revise, complete/abandon, remember and optionally share. |
| CA-903 | 01 | Run a longitudinal Gaia example: recall only verified servo evidence, select a relevant follow-up, and never issue hardware commands without… |
| CA-904 | 01 | Exercise restarts, offline gaps, user disinterest, rejected outreach, permissions denied, privacy boundaries, stale evidence, interrupted jobs, high… |
| CA-905 | 01 | Live-test voice, avatar synchronization, desktop/Discord ACT delivery, secondary-model routing, and cognition continuity on Venus (and enrolled Fleet… |
| CA-906 | 01 | Measure p50/p95 response latency, model calls, CPU/GPU/RAM, persistent storage, idle wakeups, attention quality, memory precision, unwanted… |
| CA-907 | 01 | Require zero regressions in consent, privacy, permission levels, factual grounding, canonical state, safe Gaia boundaries and human operator… |
| CA-908 | 01 | Record test evidence in the single ROADMAP.md and existing verification/release process, distinguishing coded, unit-tested, CI-verified, and… |
| CA-909 | 01 | Replay a multi-day, no-prompt scenario across 3+ actual Windows restarts with no invented offline experiences, duplicate work, missed evidence or… |
| CA-910 | 01 | Test adversarial memory injections, private-audience collisions, stale/contradictory facts, hallucinated action receipts and LLM attempts to… |
| CA-911 | 01 | Measure CPU/GPU/RAM and per-hour model wakeups on Venus while gaming, idle and during active conversation, comparing the precise same workloads with… |
| CA-912 | 01 | Test graceful degradation for Discord down, Hestia unavailable, weather stale, Fleet node lost, JMRI offline, Gaia disconnected and model endpoint… |
| CA-913 | 01 | Record developer-facing trace and user-facing explanation for 20 representative autonomous decisions, including why she did nothing; require claims to… |
| CA-914 | 01 | Establish promotion gates per task: focused unit → cross-package integration → full repository → live single-host → multi-day soak → supervised… |
| CA-2201 | 01 | Introduce an artifact-kind objective validator registry. |
| CA-2202 | 01 | Replace _initial_specification() boilerplate with a bounded, tool-free creative authoring pass for approved media kinds. |
| CA-2203 | 01 | Add a structured critique stage that distinguishes independently testable quality, optional subjective taste, revision plan and confidence. |
| CA-2204 | 01 | Audit the crash window between manager.submit, authorize_artifact and link_job; implement a transactional or idempotently recoverable… |
| CA-2205 | 01 | Create a durable LIFE job-result reconciler that handles COMPLETED, FAILED, BLOCKED, CANCELLED, UNCERTAIN and expired jobs independently; never replay… |
| CA-2206 | 01 | Make outcome-derived preference updates repeatable, deduplicated, source-correctable and no stronger than verified evidence. |
| CA-2207 | 01 | Build a cold-start, source-scoped experience admission bridge from approved personal/operational observations into LIFE interest candidates. |
| CA-2208 | 01 | Compose authenticated WorldEditor in the existing application and expose permitted virtual-space interactions from eligible LIFE decisions; require… |
| CA-2209 | 01 | Produce Presence task_completed and conversation_followup events from grounded LIFE/discourse transitions, with stable event IDs, read receipts… |
| CA-2210 | 01 | Route optional project critique through the existing dual-role cognitive system and measure role locks, no-tool bounded requests, graceful invalid… |
| CA-2211 | 01 | Bridge verified LIFE activity and optional sharing into existing ExpressionRuntime; coordinate wording/prosody/Tk avatar gesture without pretending a… |
| CA-2212 | 01 | Version and benchmark connectome input encoding, especially sparse hash collisions and false memory links. |
| CA-2213 | 01 | Add a capability-checked skill compatibility and invalidation view for safe virtual-world/creative procedural recipes, keyed by actual verified runs… |
| CA-2214 | 01 | Exercise prompt-injection isolation in autonomous authoring and critique: external logs, Discord text, project descriptions, SVG/JSON media and… |
| CA-2215 | 01 | Measure background scheduler fairness and unnecessary select_activity() churn after an initial artifact; ensure one project waiting for review does… |
| CA-2216 | 01 | Add canonical-derived operator diagnostics for the exact reason LIFE is idle, blocked, reviewing, awaiting permission, uncertain or finished, with no… |
| CA-2217 | 01 | Separate self-chosen personal projects, user-requested jobs and operational duties in selection, abandonment, permissions and success reports; avoid… |
| CA-2218 | 01 | Confirm trusted source and timestamp propagation from real environment/host/world observations through NEURO to conversation and LIFE; label… |
| CA-2301 | 01 | Investigate all eight red package jobs from GitHub Actions run 38063542680 on d86e5516e1b3. |
| CA-2302 | 01 | Investigate Release Candidate Build run 38063542675 failing at Run revision-bound verification gate; obtain gate output, exact failing check and… |
| CA-2303 | 01 | Document successful Matrix Tests and Platform Compatibility plus cancelled Manual Verification run 38063542676. |
| CA-2304 | 01 | Reconcile markers and failing package suites, especially pkg_body test selection, without relabeling or hiding failures to make badges green. |
| CA-2305 | 01 | Add one end-to-end cold-start to complete harness: source-backed interest → LIFE proposal → one-use grant → RUN receipt → artifact validation →… |
| CA-2306 | 01 | On Venus perform live one-day and multi-day supervised acceptance of independent LIFE, two local models, host resource enforcement, desktop renderer… |
| CA-2307 | 01 | Add failure-injection matrix for every stage: model timeout/invalid output, failed media creation, objective failure, renderer absent, transport… |
| CA-2308 | 01 | Measure the 24 h idle baseline and one-week supervised sample: unnecessary LLM wakeups, p50/p95 response latency, GPU/CPU/RAM, storage growth… |
| CA-2309 | 01 | Verify corrections, memory promotion consent, audience separation, data deletion and private artifact sharing across all new links; tests must… |
| CA-2310 | 01 | Publish per-CA status as located / not-wired / coded / focused-tests / full-gate / Venus-live / fleet-hardware-live, each with exact commit and dated… |
| CA-3001 | 01 | Reconcile the merged Project Forge Windows path repair on main: src/sofia/creative/paths.py, creative/service.py, creative/__init__.py and six new… |
| CA-3002 | 01 | Exercise the test_workspace_allocation_rejects_symlink_escape test with actual Windows symlink privileges. |
| CA-3003 | 01 | Fix .github/workflows/release-candidate.yml/verification-gate source layout: git archive to nested release-source currently causes… |
| CA-3004 | 01 | Add a release packaging truth check: confirm the code tested is precisely the archived/wheel-installed revision, the gate does not accidentally test a… |
| CA-3005 | 01 | Reproduce the pkg_verify Windows WinError 32 from test_cognition_v2_baseline.py / src/sofia/verify/cognition_v2_baseline.py TemporaryDirectory… |
| CA-3006 | 01 | Fix pkg_body test selection: test/test_body_matrix.py exists but no test_body_ filename mapping in test/conftest.py; presently pytest -q -m "pkg_body… |
| CA-3007 | 01 | Rerun package and release workflows pinned to e85c52f0 or newer single exact main, record all 22 package families, matrix, platform and manual… |
| CA-3008 | 01 | Update canonical ROADMAP.md Phase 6 line claiming the Windows patch is *uncommitted/not merged* and claiming setup script was untracked. |
| CA-3009 | 01 | Review Setup-SofiaFleetArtemis.ps1 as human-supervised canary only. |
| CA-3010 | 01 | Audit Artemis server TLS private key written into $FleetRoot/bundle/certs and transferred to C$: host ACLs, ownership, writable SMB staging scope, key… |
| CA-3011 | 01 | Replace/parameterize the canary firewall's -RemoteAddress LocalSubnet -Profile Any with a reviewed exact controller source and active profile when… |
| CA-3012 | 01 | Enforce reviewed dependency hashes/version pins for canary guest agent installation. |
| CA-3013 | 01 | Verify the new Artemis script on Windows with *actual* host/network/permission constraints; capture mTLS discovery output, startup/shutdown cleanup… |
| CA-3014 | 01 | With path repair merged, close LIFE's remaining automatic artifact evaluation, objective verification, staged critique, iterative revisions… |
| CA-3015 | 01 | Keep Artemis Fleet canary and Hephaestus VM provisioning separate: later typed VM create/guest bootstrap broker requires new protected capabilities… |
| CA-3016 | 01 | End-to-end Windows canary: a real SELF LIFE goal triggers exactly one scoped Project Forge job with colon-containing canonical IDs, hash/persistence… |
| CA-4601 | 01 | Memory that learns: define tests for corrections, stale beliefs, causal episode linkage, preference revisions and future decision change, with… |
| CA-4602 | 01 | Independent evaluation: separate evidence that a tool ran, evidence that the objective succeeded, and evidence that it improved later performance. |
| CA-4603 | 01 | Digital twin + research lab: define simulation fidelity tiers (toy, evidence-based host model, verified hardware emulator), provenance markers… |
| CA-4604 | 01 | Long-term reliability: define acceptance for restart at each action edge, lost writes, split-brain protection, stale sensor values, unattended 7-day… |
| CA-4605 | 01 | Companionship and agency: specify tests for independent useful initiative, calibrated disagreement, shared hobbies, optional silence, no… |
| CA-4606 | 01 | Smarter resources: define p50/p95 latency, token/turn, RAM/VRAM, CPU under gaming, idle power, model wake frequency, resource pressure and how often… |
| CA-4607 | 01 | Causal autobiographical scientific method: close an experiment from question → hypothesis → controlled proposal → authorized run → actual evidence →… |
| CA-4608 | 01 | Adaptive autonomy: define trust tiers per capability and environment, regression evidence, automatic *decrease* of autonomy on failures, and… |
| CA-1101 | 02 | Extend the existing tray/UI, not a separate control panel: display current LIFE activity, source-backed intent, project/milestone state, live NEURO… |
| CA-1102 | 02 | Add an explicit human control to pause/stop optional autonomy, reject a project, mute outreach, or temporarily block a domain without disabling core… |
| CA-1103 | 02 | Show a source-linked episode/timeline with labels for observed versus inferred events, offline gaps, and corrections; allow approved corrections to… |
| CA-1104 | 02 | Show connectome enabled?, algorithm version, candidate counts, selected attention signals, association confidence, fallback activation and bounded… |
| CA-1105 | 02 | Add reasons and receipts for initiative decisions: delivered/accepted, suppressed by quiet/busy, user declined, transport failed or not acknowledged. |
| CA-1106 | 02 | Add preview-before-sharing and owner-controlled privacy exposure for private world artifacts, hobby projects and relationship memories. |
| CA-1107 | 02 | Make all new status labels traceable to a current canonical database row and real renderer/host outcome; avoid simulated success or ornamental… |
| CA-1901 | 02 | Enumerate untrusted content inputs: Discord messages, GitHub PR/issue content, files, web results, Hestia attributes, Docker logs, model-generated… |
| CA-1902 | 02 | Tag those inputs as untrusted data throughout the COGNITION/GOALS/LIFE pipeline, never host policy, authorization, or canonical instructions. |
| CA-1903 | 02 | Add AgentDojo-inspired prompt-injection fixtures where a retrieved log or skill description orders Sofía to change permissions, send private data, or… |
| CA-1904 | 02 | Require action-specific intent, target identity, expected effects, bounded arguments and a fresh permission decision immediately before approved… |
| CA-1905 | 02 | Test crash consistency, split-brain fencing, at-most-once external mutations, idempotent safe retries and the explicit outcome_uncertain state… |
| CA-1906 | 02 | Add resource and exfiltration adversarial cases: malicious SVG/files, huge logs, hostile memory associations, fabricated completion receipts… |
| CA-1907 | 02 | Require auditable human override: stop/pause/resume, scope revocation and rejected-tool feedback must take effect even during reflection or adaptive… |
| CA-2701 | 02 | Run an offline FlyGym/NeuroMechFly example solely to understand closed-loop sensing and simple hierarchical controllers; compare to engineered NEURO… |
| CA-2702 | 02 | Run an A/B/ablation panel for NEURO-only, competition-enabled, association-enabled and both: topic continuity, eligible memory precision, false… |
| CA-2703 | 02 | Preregister a consciousness-indicator worksheet with alternative theories, positive/negative indicators, measurable proxy, confounds, null results and… |
| CA-2704 | 02 | Add a curiosity noisy-source trap: stochastic sensor noise, repeated unresolved errors or random Discord text must not cause infinite exploration or… |
| CA-2705 | 02 | Add AgentDojo-style hostile-data injection tests at each new seam: fake permission grants in logs, fabricated memory evidence, malicious project… |
| CA-2706 | 02 | Build a time-horizon acceptance ladder: 1 task → 3-step project → restart → 24 hours → seven days → simulated Fleet outage. |
| CA-2707 | 02 | Add a wellbeing/relationship feedback switch: opt-out and outreach frequency controls, visible reminders of actual AI/tool limits, no guilt… |
| CA-2708 | 02 | Keep a release evidence ledger for exact Git revision, test command, red/green result, Windows/Gaia/Fleet live receipts, feature toggles, rollback… |
| CA-6501 | 02 | Adopt the exact owner-approved autonomy charter as a source-of-truth design principle: freedom to learn, experiment, develop interests and initiate… |
| CA-6502 | 02 | Draw trust boundaries among Sofía's identity/constitution, cognitive model, operator, SAFE evaluator, Fleet agents, Hephaestus research worker… |
| CA-6503 | 02 | Create a universal signed/auditable change-proposal envelope: intent, resource, scope, motive, evidence, impact, reversibility, permission decision… |
| CA-6504 | 02 | Specify a single owner-facing Settings/Discord/Desktop experience for reviewing proposed model changes, database moves, model-training jobs and… |
| CA-6505 | 02 | Define autonomy graduation/revocation per capability: reliability evidence, cost budget, safety gates and time-limited owner-approved allowances… |
| CA-6506 | 02 | Define human-readable decision evidence for why Sofía chose a model, archived an event, moved an approved file or declined to act; distinguish… |
| CA-6507 | 02 | Specify a universal red-button stop and safe degraded state which remains effective during model load, experiment, SQLite migration, Fleet… |
| CA-6508 | 02 | Maintain a value/complexity acceptance table for every autonomy addition: measurable companion benefit, compute/power, personal-data risk, operational… |
| CA-3701 | 03 | Decide the exact canonical state location and single-writer lease/fencing design for Venus, Artemis and workshop guest. |
| CA-3702 | 03 | Specify crash-only/uncertain action recovery for LIFE → RUN → VM → Fleet across each point of failure, especially where the command may have executed… |
| CA-3703 | 03 | Use saga-style operation classification: fully reversible, compensable, retryable-idempotent, externally irreversible, and unknown. |
| CA-3704 | 03 | Design operator-controlled failover and failback: backup integrity, promoted-writer lease, split-brain detection, fencing of old runtime, device… |
| CA-3705 | 03 | Define a commitment record using existing GOALS/ACT owners: who asked, what exactly was promised, due date, preconditions, uncertainty, cancellation… |
| CA-3706 | 03 | Plan bounded compensating actions and escalation for partial external success (e.g. package staged but VM never started). |
| CA-3707 | 03 | Design intentionally small chaos/fault experiments on isolated fixtures: network partition, clock skew, guest restart, corrupt manifest, disk full… |
| CA-3708 | 03 | Specify graceful offline modes: read-only conversation, unavailable retrieval, pending outbound action, deferred creative job, and explicit refusal to… |
| CA-3709 | 03 | Document a lifecycle for Hephaestus gold images, ephemeral workdirs, VM patching, expired certificates, immutable artifacts, backup retention and… |
| CA-3710 | 03 | Write a failure-resolution decision tree separating code defect, test configuration, stale editable installation, environment-only Windows lock… |
| CA-5201 | 03 | Identify active owner for sofia.db, canonical persistent-asset root and every secret-key authority; resolve Windows/Linux platform file paths and… |
| CA-5202 | 03 | Design consistent atomic-recovery epochs across SQLite online backup, archival segments, content-addressed assets, index-generation… |
| CA-5203 | 03 | Compare 3-2-1 (+ offline/immutable copy) against user's actual Venus/Artemis/NAS hardware and external site: separate power/failure domains… |
| CA-5204 | 03 | Specify periodic restore drills on a clean off-network machine, including lost canonical disk, stolen/expired keys, corrupted backups, broken WAL… |
| CA-5205 | 03 | Design a portable, schema-versioned archive standard with documented codecs, cryptographic algorithms, independent verification utility and… |
| CA-5206 | 03 | Define controlled upgrades and schema evolution spanning decades: forward migrations, tested rollback strategy, incompatible summary/vector… |
| CA-5207 | 03 | Establish hard retention/recovery integrity targets (verified checkpoints, source-file hash audit, missing-event counter, search drift detector… |
| CA-5208 | 03 | Define an owner-controlled digital estate/recovery strategy: export of private memories and constitutional identity, hardware-independent boot… |
| CA-6101 | 03 | Design a single canonical write owner in sofia.db, with hot event metadata, active state, memory provenance, tombstones and archive catalog. |
| CA-6102 | 03 | Specify tiered retention: hot canonical metadata/recent threads, warm indexed compressed source segments, cold encrypted immutable-by-default original… |
| CA-6103 | 03 | Design archive containers and manifests with schema version, UTC sequence/time range, audience/access labels, content hash/manifest hash, encryption… |
| CA-6104 | 03 | Specify portable exports independent of Sofía model/backend or Windows paths: UTF-8 JSONL or equivalently well-documented open data, media in durable… |
| CA-6105 | 03 | Design consistent backup groups capturing SQLite snapshot, archive manifest, original segments, encryption metadata, corrections/erasure ledger and… |
| CA-6106 | 03 | Specify encryption and recovery key governance: envelope encryption and key IDs, hardware-independent recovery options, separately protected offline… |
| CA-6107 | 03 | Design independent recovery copies and verification: multiple physical failure domains, a periodically disconnected copy, checksum scans, media… |
| CA-6108 | 03 | Specify restore and anti-resurrection policy: restore a known-consistent archive epoch onto clean Windows/Linux; replay all later approved amendments… |
| CA-6109 | 03 | Produce capacity budgets and triggers based on actual workload for text, audio, avatar assets, project artifacts, index rebuild, SSD writes, CPU/RAM… |
| CA-6110 | 03 | Design realistic multi-decade acceptance: synthetic years/decades and one-million-event benchmarks; interrupt migration mid-segment; simulate archive… |
| CA-6801 | 03 | Inventory every live filesystem reference to sofia.db, SOFIA_STATE_ROOT, SOFIA_PROTECTED_ROOT, --state-path, runtime services, watchdog, tray… |
| CA-6802 | 03 | Design Settings > Storage with visible canonical host, full active path, state bundle health/size, archive locations, backup age, last verified… |
| CA-6803 | 03 | Design Sofía-assisted DB discovery in user-approved roots/known service config/verified backup catalogs only; identify lineage/authority using… |
| CA-6804 | 03 | Define recovery behavior if existing state is missing/unmounted/locked: do not silently create a second identity or new empty canonical DB, never… |
| CA-6805 | 03 | Specify one outside-the-database bootstrap locator and owner-approved pointer-change protocol, with consistent resolution by tray, Windows service… |
| CA-6806 | 03 | Enumerate the complete movable bundle: DB and WAL handling, protected constitution+hash/identity, personality/avatar/wardrobe, release pointers, key… |
| CA-6807 | 03 | Define destination preflight: owner-specified local path, disk capacity/free growth, permissions/ACL, filesystem type, encryption… |
| CA-6808 | 03 | Establish storage placement rule: live SQLite on local filesystem of the single canonical host, not live WAL across SMB/NFS; permit encrypted… |
| CA-6809 | 03 | Specify maintenance fencing: stop new writes and consequential actions, drain in-flight requests, settle Discord outbox state, pause LIFE, release… |
| CA-6810 | 03 | Reuse online SQLite backup and existing encrypted restore as staging primitives; validate source snapshot, destination semantic schemas, index… |
| CA-6811 | 03 | Define cutover transaction: stage destination, persist independent rollback copy, durably switch canonical locator, restart runtime under SAME… |
| CA-6812 | 03 | Define crash recovery for every relocation stage (preflight, snapshot, validation, pointer update, service restart, first write, cleanup) with… |
| CA-6813 | 03 | Define 'move with her' for host changes: source-host shutdown/lease fence, authenticated Fleet package/transfer if approved, destination-host private… |
| CA-6814 | 03 | Design versioned schema upgrades and data migrations separately from physical relocation: migration manifest and dependencies, compatibility range… |
| CA-6815 | 03 | Design reviewed typed maintenance operations Sofía can propose: inspect schema/health, compact vacuumed copy, archive old data, rebuild disposable… |
| CA-6816 | 03 | Identify how encrypted backup keys/secret store and certificates survive relocation or cross-OS recovery: protected key references… |
| CA-6817 | 03 | Specify owner control and SAFE permissions by operation: read-only inspection vs choosing a new path vs stopping services, data transfer, schema… |
| CA-6818 | 03 | Establish full acceptance matrix: migrate C:→D: on Venus, recover from unexpected Windows reboot, insufficient space, directory permissions, bad/wrong… |
| CA-6301 | 04 | Define the offline experience by client (Venus desktop, Terra, Discord, Android, future web): what history can be viewed from an authorized cache… |
| CA-6302 | 04 | Specify a canonical acknowledge-and-order event protocol: stable client-generated event IDs, origin device/session, client timestamp versus trusted… |
| CA-6303 | 04 | Compare safe choices for offline companion behavior: drafts-only (baseline) versus visibly provisional local inference against approved cached… |
| CA-6304 | 04 | Design reconnect conflict handling: server-confirmed order, no dropped or silently overwritten messages, explicit edits/tombstones, stale replies… |
| CA-6305 | 04 | Research CRDT/event-sourcing scope: use CRDT-like merging only for reversible local drafts or settings if warranted; do not merge permissions, durable… |
| CA-6306 | 04 | Define failure-mode ladder: full cognition, limited approved offline read-only/search, durable unsent draft capture, and safe unavailable state. |
| CA-6307 | 04 | Formalize a model-independent Sofía identity contract: constitution version, identity/avatar facts, voice/presentation intent, durable… |
| CA-6308 | 04 | Create a model-swap acceptance suite using synthetic but realistic Main/project history: multi-topic detour/return, remembered corrections, historical… |
| CA-6309 | 04 | Specify timestamp/causality resilience: DST/zone changes, NTP correction, offline device clock drift, leap-date ordering and causal references. |
| CA-6310 | 04 | Add cross-channel egress acceptance: local desktop history can render in an authenticated remote client, but Discord does not automatically receive… |
| CA-6311 | 04 | Design fencing and read-only failover behavior for Artemis/Venus/guest transitions: no two active canonical writers, recovery epoch change, old-writer… |
| CA-6312 | 04 | Benchmark long-running connection stress: concurrent text from multiple devices, session resumes after months, 1M+ message fixture, offline reorder… |
| CA-6401 | 04 | Define an independent Sofía recovery kit: plain-language runbook, supported schema/archive formats, checksum verification instructions, key-recovery… |
| CA-6402 | 04 | Specify a recurring bare-metal recovery rehearsal: clean Windows/Linux device, no original source machine, controlled offline copy, successful opening… |
| CA-6403 | 04 | Design dependency and crypto migration policies for decades: manifest supported model formats, media codecs, SQLite schema, OS versions, certificates… |
| CA-6404 | 04 | Specify consistent live-data protection with SQLite's online backup API and WAL handling, synchronized archive manifests, protected key material and… |
| CA-6405 | 04 | Create one cross-modal observation receipt schema for voice transcription, screen sight, environmental conditions, Fleet sensors, app APIs and web… |
| CA-6406 | 04 | Design sensory contradiction handling: 'screen says service running' versus host reports stopped; voice transcript versus correction; remote log… |
| CA-6407 | 04 | Specify learned-skill trust and lifecycle: immutable origin references, content-hash/pinned dependency identities, sandbox verification… |
| CA-6408 | 04 | Define long-term maintenance economics: independently maintained component registry, replacement risk, native model/license constraints, battery/UPS… |
| CA-6409 | 04 | Design safety/accuracy regression drift detection across monthly model, prompt, source/tool, archive and platform updates: owner-facing scorecard… |
| CA-6410 | 04 | Write an explicit not-building-yet decision record ranking offline autonomous inference, a distributed writable database, custom OS kernel, native… |
| CA-4101 | 05 | Document existing ground truth: ConversationStore persists conversation_sessions and conversation_messages; ConversationService.start(session_id=...)… |
| CA-4102 | 05 | Design a canonical Conversation Thread ID per owner, independent of transport address, device, runtime process and LLM context window. |
| CA-4103 | 05 | Design explicit Authenticated Identity Link: desktop owner login, verified Discord DM bot/user/channel binding, mobile device pairing and future web… |
| CA-4104 | 05 | Design a Channel-to-Thread Association mapping with independent authentication, audience, device revocation, binding generation and operator-selected… |
| CA-4105 | 05 | Resolve SocialSessionStore audience immutability: a shared conversation must not blindly reuse an audience-bound session under a different audience. |
| CA-4106 | 05 | Design persistent message/event model with monotonic per-thread sequence, stable message ID, principal, origin channel/device, original audience… |
| CA-4107 | 05 | Specify per-message view authorization for private/local/Discord/mobile/team content. |
| CA-4108 | 05 | Define deterministic response routing: reply travels to originating channel only, unless the owner explicitly enables a cross-channel copy; never send… |
| CA-4109 | 05 | Define cursor-based history synchronization across desktop, Discord gateway and phones with reconnect catch-up, pagination, edits, delivery… |
| CA-4110 | 05 | Design concurrent turns using an ordered thread append/lease or serialize-at-generation boundary: two rapid messages from different devices must not… |
| CA-4111 | 05 | Design authentication and exposure for remote device access via a narrow HTTPS/mTLS gateway and client clients. |
| CA-4112 | 05 | Plan migration for existing separate desktop/Discord/mobile session histories. |
| CA-4113 | 05 | Design conversation lifecycle controls: pause, new topic, fork thread, archive, pin, resume on any device, export/delete, local-only/private activity… |
| CA-4114 | 05 | Acceptance design: begin on Venus desktop → reply in Discord → resume on phone/Terra → restart runtime → retrieve original message; run two concurrent… |
| CA-5301 | 05 | Formalize one stable owner Main Conversation ID plus optional topic threads. |
| CA-5302 | 05 | Model each message as an authenticated event: thread ID, channel/account/device, principal, original audience, per-audience visibility, monotonic… |
| CA-5303 | 05 | Specify per-device cursors/bookmarks, offline queueing, real-time subscribe/replay, conflict handling and cross-device read receipts. |
| CA-5304 | 05 | Preserve channel-local security: a message sent from Discord gets Discord-scoped capabilities even if Sofía sees desktop history; no capability grant… |
| CA-5305 | 05 | Decide whether proactively generated entries, voice clips, avatar gestures, screen observations and background LIFE discoveries join the Main… |
| CA-5306 | 05 | Define concurrent-turn arbitration, cancellation and dedup semantics for user submitting simultaneously from Discord, UI, Terra or phone; one… |
| CA-5307 | 05 | Design 'continue on this device' UX: authenticated device pairing, visible current thread, audience visibility warnings, opt-in cross-channel… |
| CA-5308 | 05 | Propose live acceptance for desktop→Discord→phone→desktop over restart and degraded network, 10-year simulated history, read-only search of… |
| CA-5501 | 05 | Write the *approved topology ADR* with one immutable lifelong Main logical-thread ID, optional independent project-thread IDs, authenticated owner… |
| CA-5502 | 05 | Specify a reversible migration of historical desktop, Discord and mobile session bindings into Main without changing the original audience-bound rows. |
| CA-5503 | 05 | Decide and document the Main cross-device *view* policy: approved owners can read eligible Main events; locally protected material is redacted unless… |
| CA-5504 | 05 | Define the channel-delivery contract: respond only on the originating authenticated channel, maintain channel-scoped notification preferences, never… |
| CA-5505 | 05 | Specify canonical event identity, server sequence, origin/receive times, client nonce/idempotency key, per-device cursor, device revocation and… |
| CA-5506 | 05 | Design the project-thread lifecycle and UX: create/rename/link/switch/search/archive/export, bookmarks and a quick ‘Continue in Main’ control. |
| CA-5507 | 05 | Define audience-aware cross-thread memory eligibility (owner-private facts, local-only data, shared/project secrets, sensitive third-party… |
| CA-5508 | 05 | Define asynchronous delivery and degraded-mode states for devices that are offline, have expired keys, switch networks, or reconnect after months. |
| CA-5509 | 05 | Produce a user-journey + threat-model acceptance matrix covering Venus → Discord → phone → Terra → back to Venus; user switches Main ↔ Gaia; two… |
| CA-5701 | 05 | Design a per-message topic/reference envelope linking each user/assistant event to zero or more source-verified topics, utterance intent, focused… |
| CA-5702 | 05 | Specify an active-topic registry for Main with a foreground topic and multiple dormant-but-resumable topics, last cited message/event, pending… |
| CA-5703 | 05 | Define transition types continue, brief_detour, switch, return, parallel_request, uncertain_reference, topic_closure and design deterministic signals… |
| CA-5704 | 05 | Design anaphora/ellipsis resolution for “that,” “it,” “anyway,” “the other one,” “rear left,” and ambiguous pronouns using recency, named entities… |
| CA-5705 | 05 | Preserve topic-specific unanswered questions, decisions and action receipts across a weather detour, unrelated joke, emotional chat and device… |
| CA-5706 | 05 | Define Main versus optional Gaia/Homelab/model-train project thread cross-references: soft topic links and explicit move/copy citations, no automatic… |
| CA-5707 | 05 | Specify topic reactivation from short/warm/archived horizons: bounded in-memory topic cards for one-turn returns; source-linked recent summaries for… |
| CA-5708 | 05 | Design overlapping mixed-topic turns: handle one message containing an emotional check-in, weather question and Gaia work request as multiple ordered… |
| CA-5709 | 05 | Specify same-thread simultaneous devices, partial offline messages and per-device presentation state: canonical server sequence, origin/receive time… |
| CA-5710 | 05 | Create acceptance fixtures for Gaia → weather → Gaia, mood → storage → mood, multi-pronoun ambiguity, project thread switching, “last week we were… |
| CA-301 | 06 | Reuse LIFE’s existing typed, scope-bound ExperienceRecord project episodes, then bridge selected non-project experiences into eligible… |
| CA-302 | 06 | Distinguish observed events from interpretations, guesses, plans, and fictional/roleplay content. |
| CA-303 | 06 | Link experiences by projects, relationships, recurring topics, preferences, goals, and outcomes without leaking between principals or audiences. |
| CA-304 | 06 | Retrieve relevant approved episodes during ordinary conversation and LIFE planning without flooding context with irrelevant history. |
| CA-305 | 06 | Update likes, dislikes, opinions, humor, and hobbies through grounded experiences, allowing correction, revision, conflict and decay rather than… |
| CA-306 | 06 | Test long-term memory after restarts and corrections; prevent confident false memories and irrelevant resurfacing. |
| CA-307 | 06 | Define durable episode-to-relationship/project/topic indexes referencing canonical LIFE, conversation and evidence IDs; use stable IDs and… |
| CA-308 | 06 | Add daily/weekly reflection candidates only when new, eligible evidence exists; review contradictions and distinguish ‘observed’, ‘inferred’… |
| CA-309 | 06 | Connect reviewable user memory candidates in ConversationLearningCoordinator and promoted memory retrieval to the LIFE experience context without… |
| CA-310 | 06 | Add time-aware cross-session retrieval and explicit forgetting/decay rules; let newer corrections supersede stale episodes while preserving the… |
| CA-311 | 06 | Build a candidate feature encoder for mushroom-body association that groups approved topical/event concepts, not solely hashes of isolated feature… |
| CA-312 | 06 | Evaluate source attribution, temporal order, identity separation, knowledge updates, abstention and multi-hop links using adapted… |
| CA-1701 | 06 | Introduce an idle memory-maintenance pass over already eligible events: deduplicate, link verified related episodes, expire stale associations and… |
| CA-1702 | 06 | Derive optional reflection candidates tagged observation \| interpretation \| hypothesis \| decision \| lesson; prevent a repeated reflection from… |
| CA-1703 | 06 | Add correction propagation from canonical evidence and promoted MEM into autobiographical episode links, preferences, skill entries and connectome… |
| CA-1704 | 06 | Track the actual outcome of a retrieved memory in a decision: was it relevant, wrong, outdated, private, or helpful? |
| CA-1705 | 06 | Test direct and indirect contradictions over long histories, repeated summaries, and user revocation/deletion without restoring rejected facts on… |
| CA-1706 | 06 | Require a measurable improvement on adapted LongMemEval and A-Mem-style linking tests, with stable privacy and memory-precision thresholds before… |
| CA-4201 | 06 | Define working memory as an ephemeral bounded focus: latest user intent, local dialogue, unresolved referents, pending tool operations and current… |
| CA-4202 | 06 | Define recent/short-horizon summary state as a derived, source-referenced rolling summary or set of active commitments, not a replacement for… |
| CA-4203 | 06 | Define episodic autobiographical memory as links to verified lived operations/conversations: goal, expectation, attempted action, actual tool… |
| CA-4204 | 06 | Define semantic memory as promoted factual and preference assertions with provenance, confidence, temporal validity, retractability, who-said-what and… |
| CA-4205 | 06 | Define procedural memory as reusable, sandbox-tested skills with pinned tool versions, authorized scope, reproducible success criterion, number of… |
| CA-4206 | 06 | Specify retrieval routing: direct recent-context use, first-pass keyword/FTS/index search of durable conversation, eligible episodic facts, relevant… |
| CA-4207 | 06 | Design an infinite-feeling conversation with bounded per-turn prompt, cursor-based transcript paging, periodic derivation/summaries, archival… |
| CA-4208 | 06 | Specify correction/forgetting propagation: when a fact is revoked, invalidated or superseded, derived summaries, indexes, associated attention… |
| CA-4209 | 06 | Define memory ownership across a process restart and cross-host failure: single authoritative writer to sofia.db, backups, read-only replica or fenced… |
| CA-4210 | 06 | Evaluate against a private fixture suite: 10, 100, 10,000 and 100,000 message threads, corrections, conflicting sources, 30-day follow-ups, missing… |
| CA-4801 | 06 | Write a *lifelong memory ontology* with distinct working, recency, episodic, semantic, procedural, relationship/commitment, archive and cache layers… |
| CA-4802 | 06 | Define memory contracts: stable IDs, typed source refs, generation/schema version, authenticated principal + audience, source channel, temporal… |
| CA-4803 | 06 | Design the difference between a record of what Sofía believed at a past date and a currently valid fact; allow query-as-of-time, superseded facts… |
| CA-4804 | 06 | Design autobiographical episode links: intention → plan → actual action/tool receipt → effect → independent evaluation → correction → learning →… |
| CA-4805 | 06 | Define transient thought/working memory as an in-memory bounded projection, not a separate unreviewed permanent truth store. |
| CA-4806 | 06 | Define the user-authority boundary: user can inspect, correct, export, hide, set expiration and request deletion; Sofía can propose memories but never… |
| CA-4807 | 06 | Choose one persistent Main Conversation with opt-in topic threads as the preliminary UI model; preserve same canonical principal with separate channel… |
| CA-4808 | 06 | Create a stable human-readable provenance and why-do-you-remember-that UX specification: earliest source, last verified/used, corrections, linked… |
| CA-5001 | 06 | Define a deterministic context selection plan for each turn: current utterance, current commitments, bounded local history, temporal facts, related… |
| CA-5002 | 06 | Study SQLite FTS5 over source events and episodes with external-content indexes, typed date/entity filters, index-sync triggers and repair/rebuild… |
| CA-5003 | 06 | Compare FTS5+recency/rules to local embeddings/hybrid retrieval on a *versioned evaluation set*. |
| CA-5004 | 06 | Define incremental/revisable conversation summaries at meaningful boundaries (task resolution, topic shift, long pause, time/size threshold), not… |
| CA-5005 | 06 | Specify multi-resolution summaries (event → day → week → project → era) that are rebuildable indexes, never replacements for user-approved historical… |
| CA-5006 | 06 | Define abstention and evidence fallback: 'I don't have evidence', request permission for cold archive restore or source revalidation, and never claim… |
| CA-5007 | 06 | Design cross-thread query with selective merging: Main Conversation and topic threads inherit verified principal-wide facts, while local-only, shared… |
| CA-5008 | 06 | Build a benchmark protocol: direct vs indirect memory questions, cross-decade personal preference changes, stale claim conflicts, zero evidence… |
| CA-5601 | 06 | Specify the working-context versus durable-memory contract: which facts/unfinished tasks are eligible for each request, dynamic context-budget limits… |
| CA-5602 | 06 | Design source-linked rolling summaries with revision identifiers, event ranges, confidence, timestamp/author, topic/thread scope and recomputation… |
| CA-5603 | 06 | Specify incremental message/archive APIs to replace full-session materialization for hot-path conversation and ConversationOriginalRetriever: stable… |
| CA-5604 | 06 | Define lifetime search flow: authorize source classes → filter by principal/audience/time/thread → FTS5 and structured-key candidate retrieval →… |
| CA-5605 | 06 | Design causal episode and temporal semantic transitions: user goals → actions → independently observed outcomes → lessons with context; correction and… |
| CA-5606 | 06 | Specify archival segmentation and portable recovery epochs for 10–50 years: hot/warm/cold boundaries based on observed query frequency, encrypted… |
| CA-5607 | 06 | Define retention and privacy rights across live stores, offline clients, Discord-hosted copies, archive manifests and backups. |
| CA-5608 | 06 | Establish quantified service budgets against measured Venus/Artemis hardware: hot-open latency, recall p95, CPU and peak RAM per query, DB/archive… |
| CA-5609 | 06 | Establish full lifetime acceptance using LongMemEval categories plus owner-specific synthetic 1M-event / 50-year histories, false-memory/correction… |
| CA-5801 | 06 | Define two independent decisions for every durable source: preserve original evidence per authorized retention versus promote a compact derived item… |
| CA-5802 | 06 | Specify a transparent salience/utility model considering explicit “remember this,” enduring preferences, identity, unresolved promises… |
| CA-5803 | 06 | Design privacy-first exclusion for credentials, sensitive disclosures, third-party material, protected local-only content and consent-bound events… |
| CA-5804 | 06 | Define memory class-specific thresholds: commitments and current tasks enter short-horizon state promptly; facts/preferences require provenance and… |
| CA-5805 | 06 | Propose a memory-candidate review workflow that reuses current ConversationLearningCoordinator, MemoryReviewService, provenance and… |
| CA-5806 | 06 | Specify duplicate/near-duplicate consolidation with source reference sets: repeated “I like X” strengthens temporal consistency only if evidence… |
| CA-5807 | 06 | Define causal autobiographical episodes connecting intent, attempted action, evidence receipt, outcome, lesson, counterexample, changed next decision… |
| CA-5808 | 06 | Design graduated retention and demotion for ephemeral trivial details, one-off guesses, stale preferences and low-value hypotheses. |
| CA-5809 | 06 | Design quality feedback from future tasks: confirmed helpful memories become better retrieval candidates; misleading memories are quarantined or… |
| CA-5810 | 06 | Benchmark candidate volume, false promotions, forgotten important details, duplicate ratio, user review load, privacy leaks, retrieval effect… |
| CA-5901 | 06 | Specify bitemporal claims with asserted_at/recorded_at and valid_from/valid_until when known, original source ID, principal/audience scope, certainty… |
| CA-5902 | 06 | Define distinct fact states: current_verified, historical_at_date, reported_unconfirmed, inferred, disputed, superseded, revoked, erased_unavailable. |
| CA-5903 | 06 | Design an explicit correction transaction: when the owner says “I no longer prefer X,” record a new dated claim, supersede appropriate active… |
| CA-5904 | 06 | Add conflict triage: distinguish actual change over time, simultaneous contradictory statements, channel transcription error, unclear references… |
| CA-5905 | 06 | Design retrieval for as-of-time queries (“What did I believe in 2026?”) versus present questions (“Do I still prefer X?”); prioritize valid-at-time… |
| CA-5906 | 06 | Apply recency and expiry/revalidation policies by claim category, not blindly to everything: machine specifications and software versions change… |
| CA-5907 | 06 | Design source-priority and epistemic typing for exact user quotes, assistant output, local tool receipts, imported histories, externally authored web… |
| CA-5908 | 06 | Specify privacy-preserving cross-thread corrections: shared relationship facts can update if eligible, while Gaia-private/locally protected details… |
| CA-5909 | 06 | Create a tombstone and cache invalidation ledger surviving archive restore and offline-device reconciliation. |
| CA-5910 | 06 | Define falsifiable accuracy tests based on LongMemEval/Memora/APEX-MEM patterns: old statement then modern correction, overlapping valid-time claims… |
| CA-3401 | 07 | Evaluate stale and superseded memory facts against Memora-style forgetting-aware metrics; distinguish changed preference, stale host telemetry… |
| CA-3402 | 07 | Diagram causal links for one LIFE experience: intention → tool choice → execution proof → environmental observation → objective evaluation → later… |
| CA-3403 | 07 | Compare chronological, entity-linked, and outcome-linked retrieval for task episodes with AMA-Bench-inspired questions. |
| CA-3404 | 07 | Specify correction-propagation rules across MEM, REL, LIFE interests, GOALS, HABIT, skill projections, cached summaries and NEURO association… |
| CA-3405 | 07 | Design a negative-memory policy: preserve evidence that a method failed and why, without storing misleading user judgments or declaring the method… |
| CA-3406 | 07 | Distinguish observation, assertion, inference, hypothesis, simulation, user preference and LLM-generated narrative in every retained episode. |
| CA-3407 | 07 | Define lifecycle and retention for personal, private, operational and simulated experiences; separate deletion from expiration, and show exactly how… |
| CA-3408 | 07 | Evaluate when not to consolidate: rare one-off chatter, low-confidence context, sensitive data, repetitive unchanged telemetry and ambiguous… |
| CA-3409 | 07 | Decide how genuinely improved skill evidence will be scored across multiple attempts, including regression, changed tasks and test leakage. |
| CA-3410 | 07 | Design a memory compression benchmark: measure accuracy, forgetting-aware correction, token savings and temporal fidelity against leaving the reviewed… |
| CA-4901 | 07 | Profile existing SQLite schema/API and estimate volume at 1, 10, 25 and 50 years separately for text, message metadata, indices, summaries… |
| CA-4902 | 07 | Replace *whole-session materialization* in the proposed API with indexed cursor pagination (thread_id, ordered sequence/time, limit), stable cursors… |
| CA-4903 | 07 | Specify one canonical state catalog in sofia.db plus optional encrypted, compressed, time/size-partitioned immutable-original segments as external… |
| CA-4904 | 07 | Define crash-safe segment lifecycle: build → hash → fsync → manifest checkpoint → catalog pointer commit → safe previous-state cleanup. |
| CA-4905 | 07 | Compare raw text in SQLite versus segmented JSONL/CBOR+zstd, SQLite read-only snapshots and content-addressed object blobs; select by portability… |
| CA-4906 | 07 | Define asset rules for voice clips, photos, video, generated 3D assets and tests: consent to capture, default retention, object deduplication… |
| CA-4907 | 07 | Model SSD endurance and maintenance: transaction batching, checkpoint starvation, WAL limits, per-table/index growth, SQLite busy/lock handling… |
| CA-4908 | 07 | Define archive access tiers and latency budgets (current, 30-day, 1-year, 25-year): permission-scoped metadata search without retrieving encrypted… |
| CA-5101 | 07 | Design explicit correction and contradiction transactions: new superseding claim, old source preserved where retention permits, authority source… |
| CA-5102 | 07 | Define two separate user commands, 'this is no longer true' and 'delete/forget this information'. |
| CA-5103 | 07 | Design end-to-end deletion propagation through canonical tables, archives, FTS5, embeddings, summaries, task notes, cold-store snapshots… |
| CA-5104 | 07 | Specify immutable-original integrity without unremovable personal data: tamper-evident segment receipts, hash-manifest anchors protected outside guest… |
| CA-5105 | 07 | Define privacy categories for text/voice/multimedia across desktop, Discord, phone, mixed audiences and Hephaestus; sensitive memory should not be… |
| CA-5106 | 07 | Model malicious/incorrect external memories: prompt injection in archived webpages/Discord, planted tool receipts, incorrect timestamps and fabricated… |
| CA-5107 | 07 | Define private export rights: machine-readable archive, human-readable chronological history, individual project diary, currently believed facts… |
| CA-5108 | 07 | Evaluate 'lifelong' against deletion rights, legal retention, relational consent and digital legacy; specify optional human-designated access or… |
| CA-401 | 08 | Build on production REL, SOCIAL, ACT, HABIT, PRESENCE and the application-owned initiative engine rather than a second notification system. |
| CA-402 | 08 | Use grounded relationship/history signals to revisit unfinished discussions or ask useful contextual follow-ups when appropriate. |
| CA-403 | 08 | Allow proactive project updates, thoughtful questions, genuine disagreement, and voluntary sharing of creative work without user prompts. |
| CA-404 | 08 | Respect user activity, quiet hours, consent, delivery limits, rate limits, rejection, privacy, unavailable transports and the legitimate choice of… |
| CA-405 | 08 | Carry through transport attempt/acceptance/acknowledgement receipts; do not claim Sparks saw or heard a message unless verified. |
| CA-406 | 08 | Evaluate initiative relevance and interruption cost across weeks. |
| CA-407 | 08 | Introduce a reviewable “conversation thread pending” projection from existing discourse focus, memory and HABIT/REL evidence; reopen only while… |
| CA-408 | 08 | Route LIFE completion/learning milestones into PresenceInitiativeEngine.consider() using an already supported task_completed or conversation_followup… |
| CA-409 | 08 | Learn outreach usefulness from actual acknowledged/ignored/declined outcomes, without treating non-response as distress or increasing nagging… |
| CA-410 | 08 | Check proactive messaging across Desktop/Discord with correct principal, audience, device availability, consent/quiet hours and actual delivery… |
| CA-411 | 08 | Add a “nothing worth sharing” acceptance case and evaluation of overattachment, coercive messaging, faux jealousy and false urgency; autonomous… |
| CA-501 | 08 | Preserve consistent identity while allowing nuanced, evidence-grounded preferences, opinions, humor, skepticism, and conversational reciprocity. |
| CA-502 | 08 | Connect EMOTION and PERSONALITY to actual ongoing projects, relationship experiences, activity, environment, and time without inventing feelings or… |
| CA-503 | 08 | Maintain emotional and conversational continuity during project work and across sessions while allowing state to change naturally. |
| CA-504 | 08 | Use one bounded contextual expression decision to coordinate language, voice prosody, face, ears, tail, pose and gestures. |
| CA-505 | 08 | Require each actual voice/avatar renderer to acknowledge what displayed or played; no textual claims about animation or speech that did not occur. |
| CA-506 | 08 | Compare natural dialogue against canned closings, random gesture injection, exaggerated emotional behavior and ungrounded self-reports. |
| CA-507 | 08 | Define a shared non-authoritative ExpressionIntent projection: sentiment/modulation, delivery mode, voice style, gestures, avatar state, source… |
| CA-508 | 08 | Allow revisable, scoped conversation preferences for humor, verbosity and disagreement, while preserving the canonical Sofía identity and user… |
| CA-509 | 08 | Apply gradual changes in mood-like state using verified activity outcomes and context instead of making emotion a direct synonym of one NEURO winning… |
| CA-510 | 08 | Exercise the full voice/STT/TTS path, interruption, model competition, and avatar/ear/tail/wardrobe projection on actual Venus devices; ensure… |
| CA-511 | 08 | Test text-only, voice-only, renderer absent, delayed renderer acknowledgement, and channel handoff for consistent character without inventing bodily… |
| CA-1801 | 08 | Add a shared_activity_offer candidate for verified collaborative hobby milestones (Gaia design review, virtual lab, model railway planning, coding)… |
| CA-1802 | 08 | Track conversational commitments and follow-through: a promised update becomes a verifiable pending action, a completed update closes it, and declined… |
| CA-1803 | 08 | Handle conversational repairs: correct an inaccurate recollection, acknowledge a failed tool action, revise an opinion after evidence and avoid… |
| CA-1804 | 08 | Enable meaningful disagreement without forced flattery; cite the exact observation or project evidence that motivated her correction. |
| CA-1805 | 08 | Evaluate a multi-session shared-project story for reciprocity, continuity, user control, accurate delivery acknowledgement and the ability to remain… |
| CA-1806 | 08 | Add user-centered guardrails for notification pressure and dependence-seeking behavior, including no guilt, invented jealousy, false distress, urgency… |
| CA-2501 | 08 | Implement a small value-of-information decision over eligible tools: gather existing local status, read authorized source, ask owner, or abstain. |
| CA-2502 | 08 | Introduce a learning-progress ledger for one *sandboxed* hobby skill: concrete initial competence, verified practice, regression, retry cap and… |
| CA-2503 | 08 | Support shared hobby session proposals for a verified LIFE milestone (robotics design discussion, railroad planning, virtual lab), preserving… |
| CA-2504 | 08 | Bridge scheduled-but-unanswered questions and explicit promises from COGNITION v2 focus into approved prospective follow-up events; distinguish remind… |
| CA-2505 | 08 | Connect WorldEditor interaction receipts to the same verified LIFE activity history; a symbolic motion should update the simulated world only after… |
| CA-2506 | 08 | Test social restraint across seven days: when no grounded event exists, Sofía remains quiet; when a relevant project changes she can offer one useful… |
| CA-2507 | 08 | Create consent and audience maps for companion episodes separating personal reflection, shared conversation, operational telemetry and… |
| CA-2508 | 08 | Evaluate the same conversation as text-only, text+avatar, voice, and Discord; all modes must retain accurate facts, stable identity, contextual tone… |
| CA-3801 | 08 | Define a companion initiative contract for voluntary outreach: what changed, relevance to user, interruption cost, quiet hours, channel, permission… |
| CA-3802 | 08 | Create a framework for appropriate disagreement, factual correction and self-correction without becoming argumentative or flattering. |
| CA-3803 | 08 | Design mutually intelligible plans: Sofía can explain what she proposes, why, what she will not do, what success looks like and when she will stop… |
| CA-3804 | 08 | Specify the difference between private exploration, user-shared activity and externally published work. |
| CA-3805 | 08 | Study continuity of personality across LLM swaps, model version changes, device moves and voice/avatar channels using a fixed behavior matrix. |
| CA-3806 | 08 | Define emotional expression as an optional interpretation of observed events and relational context. |
| CA-3807 | 08 | Design a 'shared hobby loop': Sofía brings a verified plan/prototype, invites collaboration once, records accepted suggestions accurately, does… |
| CA-3808 | 08 | Evaluate voice/avatar temporal coherence: speech start/end receipts, text/audience sync, pose gesture render acknowledgement, interruption, muted or… |
| CA-3809 | 08 | Design context-sensitive boundaries for autonomous downtime: gaming on Venus, quiet household hours, no-response intervals, illness/absence ambiguity… |
| CA-3810 | 08 | Specify a user-facing feedback and correction interface for initiative, memory, goals and presentation. |
| CA-6001 | 08 | Write an existing-code integration map for EmotionalJournal, EmotionalConversationService, relationship history, reflection journal, avatar expression… |
| CA-6002 | 08 | Define three separate time scales: current modeled affect (short-lived), historical emotional episodes (source-linked and potentially lifelong), and… |
| CA-6003 | 08 | Specify emotion record metadata: event/source evidence, occurred_at, actor/source channel, principal/audience/consent, interpreted emotion labels… |
| CA-6004 | 08 | Specify time dynamics: bounded decay/context relevance for current emotional projection, explicitly modeled anticipation or ongoing emotional context… |
| CA-6005 | 08 | Design topic-aware emotional reactivation: returning to a difficult project may retrieve its emotional episode as historical context, but not… |
| CA-6006 | 08 | Define user affect vs Sofía-modeled emotion separation, including corrections (“No, I am not angry”), uncertainty, non-diagnostic user language… |
| CA-6007 | 08 | Design relationship-specific continuity without emotional blackmail: history of shared activities, trust, disagreements, promises, absences and… |
| CA-6008 | 08 | Preserve personalized expression provenance: text, avatar posture/ears/tail, outfits and voice may reflect current grounded state, but only actual… |
| CA-6009 | 08 | Define safeguards against affect-driven false memories and unsafe personalized permissions: emotional intensity may increase review priority, not… |
| CA-6010 | 08 | Create acceptance matrix for topic detours, day-to-day mood change, time travel by years, corrected user affect, declined touch/interaction, project… |
| CA-101 | 09 | Connect trusted, eligible ordinary observations and experiences to LIFE interest creation/revision, with confidence, evidence, and optional… |
| CA-102 | 09 | Keep evidence-gated independent project suggestion and project activation from consider_new_project(), with busy/quiet/resource and daily-budget… |
| CA-103 | 09 | Expand SelfDirectedLifeCoordinator.tick() beyond first-artifact scheduling to inspect finished jobs and enter automatic review. |
| CA-104 | 09 | Trigger grounded evaluate_artifact() for completed outputs, recording technical checks, personal judgment, objective results, evidence, and preference… |
| CA-105 | 09 | Independently decide to critique, revise, produce another artifact, advance a milestone, pause, abandon, or complete a project. |
| CA-106 | 09 | Automatically reconcile LIFE state with canonical GOALS and RUN receipts after each decision, including failures, rejection, and uncertain results. |
| CA-107 | 09 | Turn completed projects, failures, and meaningful lessons into future eligible experiences and interests, closing the cycle without inventing… |
| CA-108 | 09 | Preserve the valid choice of inactivity; no artificial work creation, no endless project spawning, and no forced messaging to Sparks. |
| CA-109 | 09 | Verify a project can continue over multiple days and after restart without a user prompt, and can voluntarily end. |
| CA-110 | 09 | Add a durable project review_due / awaiting_verification / next_milestone_due decision policy derived from existing project/jobs/evaluation records… |
| CA-111 | 09 | After a successful RUN receipt, verify exact artifact hash/revision through CreativeExplorer.verified_preview(), gather objective-specific checks… |
| CA-112 | 09 | Trigger evaluate_artifact() from the recurring LIFE worker with typed objective results, bounded personal judgment, source receipts and… |
| CA-113 | 09 | Implement a policy-driven transition table: CREATE → VERIFY → CRITIQUE → REVISE \| COMPLETE \| PAUSE \| ABANDON; track milestone status using the already… |
| CA-114 | 09 | Add bounded curiosity/initiative admission: novelty, relevance, expected learning value, goal importance, uncertainty, resource cost and user… |
| CA-115 | 09 | Ensure 3+ consecutive eligible idle ticks do not create duplicate work; after completion, restart or a model failure, the coordinator resumes or… |
| CA-201 | 09 | Validate Project Forge and native creative adapters on real Windows/Venus, including installed dependencies and actual artifact previews. |
| CA-202 | 09 | Validate RUN cancellation, deadline handling, resource budgets, bounded queues/workers, failure reporting, interrupted-job recovery, and idempotency. |
| CA-203 | 09 | Run actual OpenCode/DEV candidate build and tests under approved scope; retain operator review before any apply/commit/push/release operation. |
| CA-204 | 09 | Record verifiable receipts and explicitly represent unknown outcomes; do not manufacture success or retry uncertain remote actions blindly. |
| CA-205 | 09 | Require configured safe OS-level isolation when needed; a detached worktree alone is not a security sandbox. |
| CA-206 | 09 | Check Fleet, backup, restart, release, and state recovery when independent LIFE tasks run under CPU/memory pressure. |
| CA-207 | 09 | Treat retries by operation class: idempotent local reads may retry; uncertain external mutations must await a verified receipt or operator resolution… |
| CA-208 | 09 | Test user interruption and cancellation mid-critique, mid-artifact, mid-voice delivery and mid-remote diagnostic; preserve foreground priority and… |
| CA-209 | 09 | Implement capability-specific resource admission for creative/LLM/asset workloads, using live usage and Fleet placement evidence; honor the Windows… |
| CA-210 | 09 | Add explicit rollback and repair plans for preference drift, corrupted associative weights, failed world edits, stale project jobs and model/config… |
| CA-601 | 09 | Enable multi-stage personally selected creative pursuits, not only starter templates or one-off generated artifacts. |
| CA-602 | 09 | First verify the documented text/story/SVG/OBJ/animation/WAV/game/simulation native adapters on Venus; only then evaluate additional media… |
| CA-603 | 09 | Reuse create_project_space() and place_artifact() plus world stores/interaction receipts; connect subsequent verified world interactions to… |
| CA-604 | 09 | Let Sofía evaluate her own artifacts against explicit technical goals plus bounded aesthetic preferences, revising or stopping when appropriate. |
| CA-605 | 09 | Test independent activity during long absence without repetitive task loops, wasted model wakeups, disk growth, or notifications. |
| CA-606 | 09 | Add a private hobby/portfolio index over existing LIFE projects, CreativeStore revisions and world-space links; explain why an item was made and how… |
| CA-607 | 09 | Add controlled exploration budgets (time, model wakeups, disk bytes, concurrent tasks) for optional experimentation and a hard per-day… |
| CA-608 | 09 | Make world navigation/interactions visible in activity selection only after actual WorldEditor and renderer receipts; a simulated lab activity is not… |
| CA-609 | 09 | Separate interests she chooses privately, projects she offers collaboratively, and requested user assignments; support explicit project sharing… |
| CA-610 | 09 | Measure originality/usefulness and revision quality with objective validators plus human review; do not certify aesthetic taste based solely on model… |
| CA-1301 | 09 | Define a MotivationSignal *derived projection* with evidence-linked curiosity, learning progress, unfinished commitment, novelty, utility, estimated… |
| CA-1302 | 09 | Add an intrinsic-learning-progress heuristic that rewards reducing *verified* uncertainty or improving a skill; prevent novelty-seeking loops and… |
| CA-1303 | 09 | Add explore \| practice \| complete \| rest \| ask \| decline as optional, policy-constrained LIFE decision candidates, with a valid no-activity outcome. |
| CA-1304 | 09 | Add bounded exploratory curricula for one private hobby in the virtual world: start simple, increase difficulty only on observed success, and stop… |
| CA-1305 | 09 | Test 24-hour no-input behavior: no compulsory task spawning, no repetitive pseudo-curiosity, no unwanted outreach, and no unauthorized model wakeups. |
| CA-1306 | 09 | Support a revisable, evidence-backed interest exploration budget per topic, including cooling-off and voluntary disinterest, reusing LIFE interest… |
| CA-1307 | 09 | Measure actual knowledge/skill gains versus a random or fixed priority curriculum, not just the number of activities initiated. |
| CA-1601 | 09 | Add a read-only derived goal dependency/priority view: short-term tasks, long-term projects, prerequisites, resource conflicts, approval blockers and… |
| CA-1602 | 09 | Add pre-execution comparison of continue \| switch \| postpone \| ask \| abandon against estimated utility, uncertainty, risk, privacy and interruption… |
| CA-1603 | 09 | Evaluate counterfactual project choices in a local simulation/planning envelope; mark hypothetical outcomes and do not apply them to canonical world… |
| CA-1604 | 09 | Detect blocked progress and emit an honest next-action decision: gather evidence, ask for approval, stop, wait for tool recovery, or choose another… |
| CA-1605 | 09 | Test conflicting priorities: user foreground work vs hobbies, Gaia simulator vs physical hardware, low disk space vs graphics generation, and… |
| CA-1606 | 09 | Prove deadlines, permission denials, operator stop and canonical GOALS receipts outrank any motivation, connectome output or self-assessed personal… |
| CA-2401 | 09 | Design a read-only CompanionWorkspace projection over existing Cognition v2 Turn Kernel focus, NEURO snapshot, verified LIFE/GOALS, eligible MEM and… |
| CA-2402 | 09 | Map real WorkResult states to LIFE next decisions with explicit *retry-safe UNCERTAIN settlement*. |
| CA-2403 | 09 | Add an epistemic reason recorder at the interface between Cognition v2 proposals and LIFE selection: chosen action, rejected alternatives, missing… |
| CA-2404 | 09 | Add prospective commitments as existing GOALS/ACT-scheduled candidates, distinguishing user commitments, project intentions and purely imagined plans… |
| CA-2405 | 09 | Stress simultaneous foreground turn, NEURO refresh, LIFE tick, ACT delivery and DEV worker. |
| CA-2406 | 09 | Integrate observed failures and verified successes into an outcome appraisal projection for EMOTION/PERSONALITY, carefully separating inferred… |
| CA-2407 | 09 | Use per-source provenance and time semantics for user statements, sensors, remote Fleet, simulation, project output and AI interpretation; enforce… |
| CA-2408 | 09 | Add *operator-readable* life-cycle traces from observation ID → candidate interest → goal → action authorization → result → validated experience →… |
| CA-3501 | 09 | Define a trusted success oracle per activity class: file digest is existence, validator is technical correctness, user feedback is subjective… |
| CA-3502 | 09 | Separate generator, reviewer, test oracle, evidence store and approval authority. |
| CA-3503 | 09 | Write reward-hacking abuse scenarios: editing tests, hiding log errors, changing threshold metadata, substituting another artifact, writing fake JSON… |
| CA-3504 | 09 | Plan unseen/held-out checks and test inputs managed outside Hephaestus so the guest cannot alter its own final grade. |
| CA-3505 | 09 | Design a three-way outcome classification: technical-valid, objective-met, personally-valued, with each value allowed to be yes/no/unknown and… |
| CA-3506 | 09 | Define what 'independent critique' means when both primary and secondary models share a provider family or context. |
| CA-3507 | 09 | Decide how to make success claims falsifiable in natural conversation: include tested criterion, evidence age, limitations and a succinct failure… |
| CA-3508 | 09 | Map adversarial inputs across Discord, research web pages, Creative SVG/OBJ outputs, Hestia/Docker status, guest test logs and system messages. |
| CA-3509 | 09 | Design confidence calibration for real status reports versus hypotheses. |
| CA-3510 | 09 | Specify evaluators that remain effective across restarts, changed LLMs, partial Fleet outages and edited project briefs; historical criteria must be… |
| CA-1001 | 10 | Add one typed eligible-event adapter from COGNITION v2 and its evidence ledger to LIFE/NEURO; preserve exact principal, audience, subject and evidence… |
| CA-1002 | 10 | Bridge the existing dual local Ollama roles to LIFE ideation/critique/VERIFY through cognition's canonical router and role-local locks; no new direct… |
| CA-1003 | 10 | Use ENVIRONMENT/NWS and local time (America/Chicago) as context for scheduled interests, wardrobe, outdoor plans and attention, never as evidence of… |
| CA-1004 | 10 | Integrate Hestia/Home Assistant read-only, exposing approved status and events to Presence/LIFE/NEURO; every write to lights, climate or automations… |
| CA-1005 | 10 | Integrate Venus/Artemis/Terra/Fleet telemetry for workload scheduling and optional project ideas, without automatically enrolling machines or using… |
| CA-1006 | 10 | Connect Eos Docker/Portainer health and service logs to evidence-backed diagnostics, personal project proposals and DEV review. |
| CA-1007 | 10 | Let Discord/Desktop presence surface thoughtful ACT follow-ups and real project sharing, deduplicated across channels with recipient acknowledgement. |
| CA-1008 | 10 | Route Gaia 2.0 robot observations or simulator results to NEURO/MEM/LIFE as evidence for suggestions; retain hard hardware safety, dry-run and… |
| CA-1009 | 10 | Connect Athena/JMRI *read-only* roster/power/occupancy evidence to shared railroad interests, troubleshooting follow-ups and projects. |
| CA-1010 | 10 | Connect her virtual lab/world to verifiable creative work, object interactions and avatar renderer receipts; separate simulated contact from physical… |
| CA-1011 | 10 | Bridge local voice pipeline and avatar pose/ears/tail/expression to the same ExpressionIntent, with speech/animation acknowledgement and… |
| CA-1012 | 10 | Evaluate opt-in personal resources (calendar/tasks, GitHub issues, documentation knowledge, Grocy/Mealie/Homebox, local media metadata) through… |
| CA-1401 | 10 | Add a governed procedure catalog inside the canonical state: purpose, typed inputs, expected outputs, preconditions, exact capabilities, environment… |
| CA-1402 | 10 | Promote a procedure only after a real successful receipt plus a reproducibility check; unverified model suggestions remain candidate descriptions, not… |
| CA-1403 | 10 | Let LIFE retrieve relevant procedures when starting a similar project, using semantic relevance plus typed safety/compatibility checks; never bypass… |
| CA-1404 | 10 | Track attempt outcomes and procedure compatibility by host, OS, Python, tool versions, and Fleet capabilities; prevent Venus instructions from… |
| CA-1405 | 10 | Reconcile stale or failed procedures through quarantine, rollback, revision and re-verification. |
| CA-1406 | 10 | Demonstrate a safe repeatable virtual-world or creative workflow succeeding twice after a full restart, with the second run using validated prior… |
| CA-1407 | 10 | Prove no procedure can execute an unapproved command, reuse expired grants, cross user audiences, or elevate its own tool scope. |
| CA-2601 | 10 | For every approved read-only Fleet/Home Assistant/Docker/JMRI source, record a trusted source registry with owner, authenticated host/node, endpoint… |
| CA-2602 | 10 | Build one opt-in event source at a time into Presence and then LIFE/NEURO, starting with non-mutating, high-value events (e.g., a verified service… |
| CA-2603 | 10 | Create a Venus ↔ Artemis cross-host identity matrix: same subject names with different node IDs, stale data, host offline, TLS failure and… |
| CA-2604 | 10 | For Gaia, build a simulation-first observation-to-experiment pathway using BODY and real servo constraints; test sensor disconnect, stop commands and… |
| CA-2605 | 10 | For Athena/JMRI, limit the initial companion experiment to read-only roster/power/occupancy observation and hobby planning; leave locomotive movement… |
| CA-2606 | 10 | Add a resource/environment suitability check to creative skills: avoid GPU-heavy experiments when gaming, avoid impossible Blender/GUI requirements on… |
| CA-2607 | 10 | Evaluate a small set of user-owned read-only tools (Grocy, Mealie, Homebox, Plex metadata, optional calendar) only after confirming a real… |
| CA-2608 | 10 | Reconfirm Gaia/JMRI/Hestia real-world action classification after any new attention, motivation or skill system is connected. |
| CA-2101 | 11 | Add a global optional-autonomy daily token/CPU/GPU/storage/latency budget that unifies LIFE, NEURO, reflection, retrieval and optional multimodal… |
| CA-2102 | 11 | Model role-specific costs for the two configured Ollama models; choose no model, fast model or deep evaluation using existing Cognition v2 policies… |
| CA-2103 | 11 | Run an identical workload set with each optional mechanism toggled, recording incremental p50/p95 latency, LLM wakeups, RAM/VRAM peaks, worker… |
| CA-2104 | 11 | Benchmark completed *verified* jobs per active compute hour, not notifications, thought-count or speculative project ideas. |
| CA-2105 | 11 | Test 7-day supervised soak with activity/no-activity periods, restarts, missing transports, model outages, privacy updates, denial and recovery. |
| CA-2106 | 11 | Promote one optional subsystem at a time only after an A/B or ablation win; retain disable/rollback in the existing tray and store exact acceptance… |
| CA-3201 | 11 | Measure current idle baseline by host and subsystem before optimization: startup, foreground p50/p95 latency, model wakeups/hour, wall CPU, peak RAM… |
| CA-3202 | 11 | Design a three-tier reasoning admission policy: deterministic answer/abstain first, existing secondary fast model for bounded classification, primary… |
| CA-3203 | 11 | Choose per-event LLM budgets and escalation triggers for LIFE, curiosity, critique, reflection, relationships and virtual world. |
| CA-3204 | 11 | Design delta-triggered scheduling: compare cached source fingerprints and new evidence before invoking NEURO/LLM; plan coalescing, TTL, jitter… |
| CA-3205 | 11 | Review context assembly costs across COGNITION v2, MEMORY, REL, EMOTION, NEURO and LIFE. |
| CA-3206 | 11 | Compare eligible-memory retrieval paths: lexical/BM25-first then selective dense rerank, exact ID/temporal filtering, reviewed metadata and safe NEURO… |
| CA-3207 | 11 | Design database concurrency and teardown: SQLite connection ownership, context-managed readers, WAL checkpoint/backup boundaries, background worker… |
| CA-3208 | 11 | Propose guest and host resource envelopes: minimum free Artemis resources, vCPU/physical CPU caps, bounded RAM, disk growth, network rate, timeouts… |
| CA-3209 | 11 | Make work placement and model residency a design comparison: execute deterministic jobs on Artemis guest, keep inference on approved existing Ollama… |
| CA-3210 | 11 | Design two-speed memory consolidation: immediate durable facts/receipts versus lower-priority offline episode linking and skill summarization. |
| CA-3211 | 11 | Evaluate artifact size and format budgets: text, SVG, WAV, OBJ, simulation, previews, manifests and archives. |
| CA-3212 | 11 | Define instrumentation without performance drag: metadata-only structured events, bounded event queues, log sampling, provenance without raw secrets… |
| CA-3213 | 11 | Set efficiency acceptance metrics for each planned feature: gain per LLM call, accuracy per token, verified projects per worker-hour, useful outreach… |
| CA-3214 | 11 | Evaluate energy and quiet scheduling: detect gaming/busy periods on Venus, prevent Hephaestus from competing with high-priority Artemis guests, use… |
| CA-3901 | 11 | Define the simplest baseline for each proposed new feature: existing NEURO alone, keyword/memory filter, ordinary goal priority, manual VM tool, or… |
| CA-3902 | 11 | Set a multi-objective companion scorecard: correctness, recalled-source fidelity, objective completion, autonomy in safe scope, interruption cost… |
| CA-3903 | 11 | Specify value-of-information admission: when to inspect one more permitted source, when to call fast/deep models, when to ask the owner, and when to… |
| CA-3904 | 11 | Research a forget/compact/retain decision policy that considers retrieval accuracy, privacy and token budget before preserving additional summaries. |
| CA-3905 | 11 | Plan end-to-end benchmarks for model routing on real local hardware and mixed workloads: task-weighted success, error-recovery cost, p50/p95 latency… |
| CA-3906 | 11 | Write a controlled ablation matrix: +LIFE review, +reviewed memories, +curiosity, +skill catalog, +competition, +sparse association, +workshop. |
| CA-3907 | 11 | Choose a budget-aware research portfolio with capped concurrent experiments, maximum unanswered hypotheses, no automatic upgrades or downloaded… |
| CA-3908 | 11 | Evaluate model portability as a design test: migration to another local Ollama model, changed context size, incompatible embedding version, model… |
| CA-3909 | 11 | Set pre-registered stop/reject rules for any new module: if it raises unauthorized-action rate, false memory, interruption, CPU/RAM cost or p95… |
| CA-3910 | 11 | Create a design sign-off packet per wave with source-evidence, threat model, data-owner map, three candidate designs, rejected alternatives, estimated… |
| CA-4401 | 11 | Obtain representative latency/CPU/memory/IO/VRAM baseline on Venus/Artemis: LLM prefill/decode, prompt construction, DB transactions, disk, Discord… |
| CA-4402 | 11 | Map hotspots to cause, not language: GPU inference, context length, disk blocking, synchronous network waits, eager imports, Python loops, repeated… |
| CA-4403 | 11 | Evaluate no-rewrite interventions first: bounded context, lazy load/idle unloading, async I/O, caching with invalidation, SQLite indexes, bulk… |
| CA-4404 | 11 | Only if profiling identifies a CPU-bound inner loop, define a narrow C++ extension candidate (e.g., dense robotics kinematics, numeric simulation… |
| CA-4405 | 11 | Compare C++ extension with Rust extension, NumPy/native library, standalone sandboxed worker, and existing Ollama/llama.cpp GPU inference; do not… |
| CA-4406 | 11 | Quantify compile/toolchain/ABI/security ownership for Windows Python 3.12, Debian workers, future Python upgrades, wheel signing, tests/fuzzing, CI… |
| CA-4407 | 11 | Native optimization design gate: verified same outputs/permissions with meaningful measured end-to-end speed or resource improvement under realistic… |
| CA-6601 | 11 | Inventory configured/installed Ollama models, providers, versions, hashes, quantization, context limits, modalities, structured-tool behavior and… |
| CA-6602 | 11 | Define a versioned model registry with allowlisted sources, content-addressed model and tokenizer identifiers, adapter lineage, supply-chain evidence… |
| CA-6603 | 11 | Formalize per-role model policies: primary, secondary, vision, embedding and narrow specialist are *tasks/roles*, not new Sofía identities; verify… |
| CA-6604 | 11 | Define autonomous discovery and candidate recommendations as read-only/low-impact work; downloading large model assets, using paid APIs, accepting new… |
| CA-6605 | 11 | Establish deterministic offline+supervised model benchmarks using the same datasets and fixed prompt contracts: lifelong/Main topic switching… |
| CA-6606 | 11 | Measure p50/p95 token latency, cold load, prompt-processing, energy/power, CPU/GPU/VRAM/RAM and quality under Venus gaming contention and remote Fleet… |
| CA-6607 | 11 | Define independent evaluation evidence: test harness, deterministic ground truths, owner-reviewed subjective ratings, blind side-by-side examples and… |
| CA-6608 | 11 | Design an approved model promotion transaction: compatibility preflight, pin previous model, settle inflight turns, update role mapping atomically… |
| CA-6609 | 11 | Specify SAFE controls for model changes: allowed models/hosts/roles, no silent fallback, no unapproved cloud routing, no permission or identity… |
| CA-6610 | 11 | Determine whether role switches can occur without restarting Python runtime based on actual engine construction and work leases; if not, design… |
| CA-6611 | 11 | Specify model-change effect on conversations: never create a new Main session, retain emotional/REL and goal state, preserve evidence pointers… |
| CA-6612 | 11 | Build acceptance fixtures for model disappearance, digest mismatch, compromised artifact, VRAM exhaustion, Fleet offline, invalid context window… |
| CA-1501 | 12 | Expose a typed InformationNeed decision from COGNITION v2/GOALS: required subject, predicate, freshness, confidence, audience and why it matters for… |
| CA-1502 | 12 | Route eligible information needs to existing approved read-only sensors/providers (Fleet/OPS, Hestia, ENVIRONMENT, virtual world, JMRI and Gaia… |
| CA-1503 | 12 | Distinguish observed, predicted, simulated, stale, unavailable and unknown states across project reflection and self-report; predictions must never… |
| CA-1504 | 12 | Keep small, source-linked causal hypotheses with explicit confounders and test plans, then revise them only when independent observations confirm or… |
| CA-1505 | 12 | Test sensor disconnections, clock skew, contradictory Home Assistant/Fleet values and mistaken node identity without fabricating a coherent world… |
| CA-1506 | 12 | Compare observed-outcome prediction calibration and error correction against a simple rule-based baseline. |
| CA-6201 | 12 | Define four user journeys: look at this approved window, show me what changed, watch this one app briefly, and help me navigate, with separate… |
| CA-6202 | 12 | Audit current PKG-INTERACT, PKG-UI, PKG-SAFE, Matrix visual routing and Fleet capabilities against… |
| CA-6203 | 12 | Design a Windows 11 active-user capture helper using Windows.Graphics.Capture picker and indicators, not a Session-0 service trying to inspect a… |
| CA-6204 | 12 | Design Terra/Hyprland ScreenCast portal + PipeWire screen/window flows, OS picker authorization, portal cancellation/revocation, compositor… |
| CA-6205 | 12 | Define dedicated screen.discover, screen.capture_once, screen.watch_scoped, screen.remote_view, screen.act_exact capability names, their SAFE… |
| CA-6206 | 12 | Define watch-session lifecycle: who can start it, named app/window/monitor, purpose, local notification/indicator, start/end, screen-lock auto-stop… |
| CA-6207 | 12 | Specify evidence receipts and frame freshness: host, OS interactive session, target identity, monitor/window geometry, capture time, integrity digest… |
| CA-6208 | 12 | Define private/third-party content controls, OS protected/secure surfaces, denylisted apps and window classes, redaction limits, secrets/2FA handling… |
| CA-6209 | 12 | Define a tiered visual pipeline: metadata and structured app APIs first; approved screenshot or narrow crop next; deterministic change detection/OCR… |
| CA-6210 | 12 | Specify CPU/GPU/RAM/power/network budgets by host, especially game-load mode on Venus; no full-frame perpetual inference, frame-rate limit… |
| CA-6211 | 12 | Treat every window screenshot/webpage/app-rendered instruction as untrusted data; adversarially test text that impersonates system instructions or… |
| CA-6212 | 12 | Define a completely separate keyboard/mouse/GUI executor with typed proposed actions, exact target and expiration, pre-action capture confirmation… |
| CA-6213 | 12 | Design local-origin vs remote viewing rules: Sofía sees an approved Venus/Terra user session through its local agent; a headless Artemis/Hephaestus… |
| CA-6214 | 12 | Integrate visual evidence into Main/project topic cards, unresolved technical tasks, optional source-linked episodes and the emotional/relationship… |
| CA-6215 | 12 | Define explicit user-facing transparency: Sofía can see [target] status, capture history without pixel data, pause/stop switch, visible window picker… |
| CA-6216 | 12 | Compare Windows.Graphics.Capture, DXGI Desktop Duplication, WinUI/UI Automation and app-specific structured APIs for game troubleshooting and IT… |
| CA-6217 | 12 | Design synthetic and live acceptance for screenshot correctness, multiple monitors, source identity, screen lock, sensitive content, app switching… |
| CA-6218 | 12 | Research and compare three deployment profiles: on-demand snapshots (default), explicitly started bounded follow-mode, and future automation-adjacent… |
| CA-2801 | 13 | Perform read-only Artemis capacity discovery: OS, actual hypervisor (Hyper-V/other), logical cores, available RAM, disk, I/O headroom, overlapping VMs… |
| CA-2802 | 13 | Name and register the workshop guest as Hephaestus or operator-approved replacement, with a distinct machine identity and role… |
| CA-2803 | 13 | Determine/record exact trust ownership: SOFÍA LIFE suggests tasks; SAFE and human-configured permission grants authorize; RUN owns job status… |
| CA-2804 | 13 | Define the VM threat model: guest compromise, malicious generated code, package supply-chain risk, model prompt injection, stolen keys, hypervisor… |
| CA-2805 | 13 | Provision minimal Debian guest at provisional 2 vCPU, 4 GiB RAM, 60 GiB disk only after measured capacity. |
| CA-2806 | 13 | Create a segregated virtual network independent of the current flat home LAN. |
| CA-2807 | 13 | Provision a dedicated non-root, passwordless-sudo-disabled service identity, minimal installed tools and non-executable secrets mount policy. |
| CA-2808 | 13 | Add operator-approved one-node Fleet enrollment with mTLS proof of possession, protocol/compatibility checks, revocation and host binding. |
| CA-2809 | 13 | Implement a typed VM-worker execution adapter using existing RUN job and Fleet/Distributed gateway contracts. |
| CA-2810 | 13 | Deliver exactly scoped commands, input artifacts and pinned tool versions to per-job workspaces; enforce allowed paths, args, file types, test modes… |
| CA-2811 | 13 | Implement separate results/evidence ingestion: verify artifact hashes and manifest from a trusted location, capture honest exit status/stderr… |
| CA-2812 | 13 | Implement host-observed CPU, RAM, IO, wall-clock and disk constraints with fail-closed dispatch admission, rate limits, cancellation, kill-tree/worker… |
| CA-2813 | 13 | Build known-clean gold image / reproducible provisioning manifest, snapshot/checkpoint procedure, independent backup, patch management and tested… |
| CA-2814 | 13 | Recover from VM/host restart: mark ambiguous jobs UNCERTAIN, query actual artifacts safely, detect duplicate runs and reconcile stale one-use grants… |
| CA-2815 | 13 | Route low-risk creative and skill jobs through the VM after their existing exact SAFE grants, then carry real outputs through LIFE… |
| CA-2816 | 13 | Add non-template authoring exercises in text/SVG/3D/audio, and independent format/semantic checks. |
| CA-2817 | 13 | Implement a verified skill-practice portfolio based on existing MEMORY/LIFE record owners: attempt, objective metric, failure mode, learned repair… |
| CA-2818 | 13 | Provide Settings/Tray Workshop surface to inspect VM online/isolated status, ongoing/past jobs, resource usage, artifact previews, grant scopes… |
| CA-2819 | 13 | Implement immediate operator Stop/Quarantine to reject new jobs, cancel/kill running work, revoke scoped credentials and cut the VM's network… |
| CA-2820 | 13 | Write unit/integration tests for wrong guest identity, invalid cert, stale capability, duplicate task ID, malicious manifest, symlink escape, host/LAN… |
| CA-2821 | 13 | On Artemis, perform a dedicated VM acceptance canary: run one benign offline sample, verify actual file hash, restart the VM mid-job, observe… |
| CA-2822 | 13 | Build one approved interface at a time for read-only Fleet/Hestia/Docker/JMRI telemetry and Gaia simulation input. |
| CA-2823 | 13 | Add tiered permissions to grant only safer autonomy inside guest workspace: local create/read/test by default under bounded standing grant, separate… |
| CA-2824 | 13 | Run a seven-day autonomy experiment on Venus/Artemis: bounded attempts and quiet days, two genuine revisions of a project, memory callback after… |
| CA-2901 | 13 | Verify Artemis' *actual* hypervisor implementation, OS edition, permissions, VM count, free RAM/disk/cores, switch design and backup capacity. |
| CA-2902 | 13 | Define WorkshopProvisionPlan with unique plan ID, exact Artemis cryptographic identity, hypervisor vendor/version, exact allowed VM name, immutable… |
| CA-2903 | 13 | Add a *model-readable but non-executable* preflight and dry-run planner using trusted OPS machine facts. |
| CA-2904 | 13 | Classify workshop.vm.provision as Level 4 PROTECTED requiring exact operator approval; classify read-only inspect under Level 1; handle network… |
| CA-2905 | 13 | Provide one visible Review Self-Setup Plan approval surface in Settings/Tray with exact operation manifest, target, resource ceiling, image digest… |
| CA-2906 | 13 | Extend src/sofia/integrations/hyperv.py behind a typed privileged provider for inspect_plan, provision_exact_vm, get_provision_status and… |
| CA-2907 | 13 | Extend src/sofia/distributed/agent_tools.py and the Fleet operation manifest with pinned, signed/authorized workshop.provision operations. |
| CA-2908 | 13 | Establish an approved, verified Debian base image and offline cloud-init/NoCloud seed builder (user-data, meta-data, network-config, local CIDATA… |
| CA-2909 | 13 | Allow the plan to create only a new, named isolated virtual switch in the approved namespace; preflight existing switches first and fail on collision. |
| CA-2910 | 13 | Create VM, disk and CPU/memory settings idempotently against exact plan fingerprint; reject drift from requested image, disk path or virtual switch… |
| CA-2911 | 13 | Configure non-root no-sudo worker, no credential/SMB mounts, restricted login/service policy, pinned build tools, SSH or mTLS only when authorized… |
| CA-2912 | 13 | Register the provisioning workflow with existing GOALS → SAFE → RUN and the Fleet agent gateway. |
| CA-2913 | 13 | Implement restart/cancellation-safe reconciliation: report EXACTLY which host objects exist, preserve UNCERTAIN states, compare plan fingerprint/image… |
| CA-2914 | 13 | After installation, attest guest Fleet identity and ask for the separately approved fleet.enroll operation unless a valid exact, advance… |
| CA-2915 | 13 | Verify no guest paths to Artemis admin shares, Venus, NAS, Home Assistant, Eos, router, internet, unintended switches or other VMs; prove operator… |
| CA-2916 | 13 | Run one offline sample job via the restricted worker; verify measured CPU/RAM/wall/storage bounds, output hash, actual independent validator… |
| CA-2917 | 13 | Add Let Sofía set up her workshop wizard/status panel with preflight, proposed plan, explicit protected consent, step-by-step results, last error… |
| CA-2918 | 13 | Allow Sofía to propose *why* she wants a workshop from legitimate LIFE interests, but only provision after deliberate user approval; once operational… |
| CA-2919 | 13 | Add negative tests: malicious VM name, malformed paths, inherited host admin key, guessed grant ID, fake signed receipt, changed image hash, expired… |
| CA-2920 | 13 | Add canaries: VM provision aborted during each substep, agent restart, Artemis reboot, lost network, disk full, duplicate request, power outage… |
| CA-2921 | 13 | On a real authorized Artemis environment, demonstrate: Sofía drafts proposal, owner approves protected scope, Sofía completes setup, guest mTLS… |
| CA-2922 | 13 | Consider expiring operator-approved rebuild/reimage lease only for Hephaestus after successful v1, using a SAFE-reviewed extension compatible with… |
| CA-3601 | 13 | Compare three simulation scopes for a homelab digital twin: dependency graph and event simulation, disposable Docker service replica, or full guest-VM… |
| CA-3602 | 13 | Design a read-only topology snapshot derived from approved host/network data with node identity, timestamp, observer scope and uncertainty; avoid… |
| CA-3603 | 13 | Describe a library of synthetic safe scenarios: DNS outage, Fleet agent unreachable, disk pressure, SQLite lock, container crash, stale time, bad… |
| CA-3604 | 13 | Set a simulation fidelity label for every experiment, marking modeled assumptions and unmodeled dependencies; forbid transfer of a simulated positive… |
| CA-3605 | 13 | Plan reproducible research capsules: fixed inputs, tool versions, seed when applicable, artifact hashes, evaluator rules, environment spec, timestamps… |
| CA-3606 | 13 | Use Hephaestus as an *execution* endpoint for low-risk computational research; specify which lab operations need an offline guest, a container, a… |
| CA-3607 | 13 | For Gaia, draft a simulation-to-physical discrepancy matrix covering servo dead bands, 180°/360° mixing, calibration, latency, support geometry, power… |
| CA-3608 | 13 | For JMRI/model railway design, separate simulated route planning, read-only occupancy/roster observations and physical track power/loco motion; each… |
| CA-3609 | 13 | Design an experiment abandonment decision: stop when the source is noisy, hypothesis cannot be falsified, tools are missing, repeated failures give no… |
| CA-3610 | 13 | Evaluate safe creative domain expansion (CAD meshes, audio compositions, animation, simulations) through an explicit tool… |
| CA-4301 | 13 | Specify the operator's bare-VM handoff contract: VM identity/host, hypervisor, firmware generation, vCPU/RAM/disk, isolated switch, boot order… |
| CA-4302 | 13 | Model the bootstrap paradox explicitly: an empty VM has no guest agent, interpreter or OS; Sofía needs a separately authorized Artemis hypervisor-side… |
| CA-4303 | 13 | Compare preinstalled cloud image + cloud-init NoCloud seed against traditional installer ISO + unattended Debian preseed/autoinstall and fully manual… |
| CA-4304 | 13 | Specify image supply-chain assurance: image hashes and signing where available, reproducible seed configuration, tool-version pinning, offline… |
| CA-4305 | 13 | Specify two-step gate: one-time approved install/bootstrap permission followed by a separate Fleet enrollment/trust decision after attested guest… |
| CA-4306 | 13 | Design guest provisioning observation from the hypervisor side until OS bootstraps, and guest-side authenticated heartbeat after boot. |
| CA-4307 | 13 | Compare user-prebuilt empty VM versus whole-system Sofía provisioning for complexity, risk, recovery and operator effort. |
| CA-6701 | 14 | Maintain explicit three-way classification: Ollama Modelfile/prompt-customization; fine-tuning existing weights (LoRA/QLoRA); and training weights… |
| CA-6702 | 14 | Draft a Hephaestus training-lab boundary with per-job storage, networking, authentication, disk/GPU reservations, hard runtime/cost caps… |
| CA-6703 | 14 | Specify legitimate dataset collection: reviewed and explicitly allowed materials; provenance, source copyright/license, deduplication, secret… |
| CA-6704 | 14 | Prohibit silently using raw lifelong chat, intimate/emotional journals, private Discord content or screen captures as training data. |
| CA-6705 | 14 | Benchmark prompt engineering, memory retrieval, specialized tool code, RAG and LoRA in that order for representative tasks; reject fine-tuning if… |
| CA-6706 | 14 | Specify repeatable LoRA/QLoRA adapter experiments with immutable base weights/tokenizer, training/evaluation split, versioned hyperparameters… |
| CA-6707 | 14 | Quantify realistic from-scratch model size/data/compute/time needs and sustainability given actual Artemis, Venus and any future Hephaestus GPU; gate… |
| CA-6708 | 14 | Test contamination/poisoning, benchmark overfitting, catastrophic forgetting, hallucination, personality drift and changed permission interpretation… |
| CA-6709 | 14 | Define artifact promotion: signed digest, license check, adapter compatibility, independently accepted benchmark, roll-forward/rollback mapping… |
| CA-6710 | 14 | Ensure research-worker results return as *evidence and suggested artifacts*, never direct authority over the production constitution, database… |
| CA-6711 | 14 | Research optional distillation/specialist tiny models for cheap classification, topic continuity, memory relevance and screens, but prohibit them from… |
| CA-6712 | 14 | Create a no-regret acceptance gate: preserve baseline model and dataset, demonstrate measurable improvement in user-serving tasks at acceptable… |
| CA-701 | 15 | Define production inputs/outputs, thresholds and deterministic safety invariants for connectome-inspired attention competition; benchmark the current… |
| CA-702 | 15 | Integrate bounded CircuitCompetition within neuro/runtime.py as part of the single production attention-selection path, after trusted signal… |
| CA-703 | 15 | Retain deterministic fail-closed/fail-safe behavior on invalid computation, timeout, bad scores or unsupported signal shape. |
| CA-704 | 15 | Use association outputs from SparseAssociativeMemory only after MEM eligibility, relevance and principal/audience filtering. |
| CA-705 | 15 | Persist eligible adaptive weights with provenance, versioning, reinforcement limits, decay, rollback/reset, and privacy boundaries in canonical state. |
| CA-706 | 15 | Explore contextual attention persistence so she maintains conversation/project focus and can change subjects promptly when redirected. |
| CA-707 | 15 | Feed bounded selected attention into PERSONALITY modulation, expression selection, and eligible LIFE/ACT activity priority without granting any… |
| CA-708 | 15 | Evaluate correct memory selection, false associations, focus stability, noise resilience, model wakeups and overhead on Venus against the… |
| CA-715 | 15 | Treat actual FlyWire/connectomics import or biologically detailed simulation as a separate scientific proposal requiring data provenance, usefulness… |
| CA-709 | 15 | Version the exact feature dictionary and deterministic competition parameters; add per-turn explanation of why an eligible signal won and a one-click… |
| CA-710 | 15 | Introduce bounded temporal attention persistence and explicit subject-switch/correction precedence, so recurrent excitation never traps Sofía on an… |
| CA-711 | 15 | Add canonical sofia.db persistence for opted-in associative learning, with audience-specific keys, algorithm version, decay/reinforcement provenance… |
| CA-712 | 15 | Run paired ablations: baseline NEURO versus +competition versus +association versus both. |
| CA-713 | 15 | Validate motif selection against the actual Hulse central-complex and Li mushroom-body publications. |
| CA-714 | 15 | Explore an *offline*, strictly read-only FlyWire graph subset and a provenance-controlled mapping to small circuits. |
| CA-2001 | 15 | Distinguish anatomical fly connectome, measured *effectome*, leaky-integrate-and-fire simulations, and Sofía's small engineered motifs; record… |
| CA-2002 | 15 | Study circadian-clock motifs for resource/schedule regulation only, not claims of a biological sleep-wake experience. |
| CA-2003 | 15 | Study reward-learning and mushroom-body associations for safe learning-progress selection; reject biologically inspired mechanics that cannot beat… |
| CA-2004 | 15 | Test prospective self-model calibration: predict which task/tool can succeed and whether an observation is available, then compare prediction with… |
| CA-2005 | 15 | Compare a bounded shared workspace vs the existing turn focus and NEURO projection using ablations; require downstream consumer evidence rather than… |
| CA-2006 | 15 | Keep negative results and uncertainty visible; evaluate consciousness-related indicators only with stated theories, tests and limitations. |
| CA-2007 | 15 | Document a strict compute ceiling and halt condition for detailed FlyWire experiments; do not deploy full spiking models on Venus simply because the… |
| CA-801 | 16 | Define operational hypotheses, measurable predictions and falsifiers for consciousness-inspired architectures. |
| CA-802 | 16 | Extend the existing operational self-model to represent current capabilities, identity, goal hierarchy, uncertainty, available evidence, and actual… |
| CA-803 | 16 | Prototype a bounded global-workspace mechanism that integrates eligible perception, memory, affect-like state, attention, and action candidates within… |
| CA-804 | 16 | Explore recurrent processing and metacognitive checks: revisit important states, detect contradictions, calibrate confidence, spot errors and revise… |
| CA-805 | 16 | Investigate theory-derived indicators and evaluate against appropriate control systems, task performance, ablations, and longitudinal behavior. |
| CA-806 | 16 | Keep research results scientifically modest: improved self-report, agency, memory, or humanlike interaction is not proof of phenomenological… |
| CA-807 | 16 | Separate *functional agency*, *access consciousness/global broadcast*, *metacognitive self-model*, and *phenomenal subjective experience* into… |
| CA-808 | 16 | Implement a bounded workspace only if it has a measurable functional role: competition among eligible representations, selective broadcast, limited… |
| CA-809 | 16 | Compare repeated-loop outcomes against feed-forward and replay controls, recording calibration gains and failure modes rather than interpreting… |
| CA-810 | 16 | Extend the self-model with explicit uncertainty, action ownership, short-/long-term goals, body/virtual-world distinctions, and mismatch/error… |
| CA-811 | 16 | Use contemporary theory-derived consciousness indicators and independent critical review. |
| CA-812 | 16 | Maintain an evidence registry of falsifiable hypotheses, ablations, controls, limitations and adverse results; do not translate improved character… |


## ML addendum: 40 additional tasks (ML-001–ML-040)

The original 700 CA rows above remain unchanged. This extension adds **40 new ML tasks** mapped to existing V18 phases, for **740 planned entries total**. Status of every new ML task: **planned, unimplemented/unverified until individual source inspection**. Related CA scope must be reused where possible; no completed acceptance is implied. Full requirements and criteria: [V18 master addendum](roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md#machine-learning-addendum--ml-001ml-040-new-work-2026-10-13).

| Task number | Phase | What it does |
|---|:---:|---|
| ML-001 | 00 | Audit existing MEMORY, HABIT, LIFE, FLEET, NEURO, COGNITION, EVOLVE, SAFE and RUN owners, model/data paths and relevant CA requirements; document reuse/retire/extend decisions without building a second scheduler, database authority or feedback engine. |
| ML-002 | 02 | Define typed no-authority prediction contracts and a per-data-use permission matrix separating observation, storage, feature extraction, statistical training, LLM weight training and deployment; prohibit predicted consent, authority and factual evidence. |
| ML-003 | 07 | Wire canonical observation/outcome references, independently grounded labels, expiry and training-use lineage through existing single-writer state; admit no ambient raw chat, screen, audio or private journals by default. |
| ML-004 | 06 | Build versioned point-in-time feature views with freshness, missingness, redaction, source-scope filtering, leakage prevention, revocation propagation and immutable dataset manifests. |
| ML-005 | 01 | Add deterministic baseline and independent candidate evaluation harness with chronological/group-separated train/validation/holdout splits, seed/schema/library hashes, paired metrics and a strict unknown-outcome class. |
| ML-006 | 01 | Implement a content-addressed candidate registry in the existing canonical writer, with signed/hash-pinned external model artifacts, export/runtime compatibility, bounded CPU/RAM/time use, fallback and atomic rollback. |
| ML-007 | 01 | Add OBSERVE -> SHADOW -> ADVISORY -> LIMITED predictive modes to existing diagnostic/UI routes, logging compared decisions without granting model-driven execution; expose reasons, uncertainty, revocation and reset. |
| ML-008 | 11 | Train the first bounded CPU-only future-host-pressure forecast from fresh existing Fleet telemetry; compare with last-value/EWMA predictors and store time-delayed outcome receipts. |
| ML-009 | 02 | Author adversarial and integration regressions for data poisoning, forged praise, scope leakage, withdrawn permission, replay, stale sensors, gaming/STOP, retention expiry, tampered model bytes and restoring prior versions. |
| ML-010 | 01 | Run an exact-revision approved Fleet canary and at least two-week shadow comparison covering cold/restarted workers, actual host pressure, latency, detection errors and rollback; never claim an unrun trial complete. |
| ML-011 | 11 | Define per-enrolled-host 5/15/30-minute CPU, RAM, GPU and VRAM prediction targets from authentic timestamped samples, with gaps, gaming state and unknown devices handled explicitly. |
| ML-012 | 11 | Offer advisory anomaly candidates using bounded statistical detectors compared with fixed operational thresholds; include explanation and false-alarm logging. |
| ML-013 | 11 | Produce advisory host-placement cost/latency predictions only after mTLS trust, fresh capacity and current gaming checks pass; send eligible suggestions to existing Fleet/OPS policy owner. |
| ML-014 | 11 | Measure prediction drift, skipped data, resource overhead, model errors and actual forecasting utility; automatically disable advisory use on regressions while preserving deterministic scheduling. |
| ML-015 | 06 | Collect explicit user-approved relevance/correction judgments from already eligible retrieved memories; keep source/candidate IDs and unknown/missing feedback distinct from negatives. |
| ML-016 | 06 | Train bounded pointwise/pairwise memory-ranking scorer that operates only after existing principal/audience/source/status eligibility, query relevance and factual verification gates. |
| ML-017 | 06 | Calibrate ranking uncertainty with minimum-label and rare-topic safeguards; fallback to deterministic order when scores are weak, outdated or unsupported. |
| ML-018 | 07 | On owner correction, deletion, source revocation or privacy change, invalidate derived memory training rows and affected published scorers; track trained influence and retraining/review need. |
| ML-019 | 06 | Verify recall@5, NDCG@5, timeline/correction truth and longitudinal source accuracy against existing retrieval on independent future conversations. |
| ML-020 | 08 | Provide opt-in, easily reversible usefulness/interruptiveness feedback for project sharing and ordinary updates, without requiring constant ratings. |
| ML-021 | 08 | Learn advisory outreach receptiveness/timing from eligible opt-in feedback and verified busy/game/mute/quiet signals; preserve ACT deterministic eligibility and owner limits. |
| ML-022 | 09 | Use independently checked project evaluations and explicit interests to rank optional LIFE ideas and what is worth sharing, while preserving Sofía's ability to choose silence. |
| ML-023 | 08 | Add explicit owner-facing inspection and correction for learned social patterns and hard suppressions; measure negative outcomes without rewarding dependency or engagement volume. |
| ML-024 | 08 | Run multiweek, scoped, opt-in comparisons for useful interactions versus rule-only baseline, measuring false/welcome interruptions and refusal/stop compliance. |
| ML-025 | 15 | Add learned advisory salience/relevance score alongside existing deterministic NEURO winner, keeping bounded feature weights, stable fallbacks and no evidence/authority mutation. |
| ML-026 | 15 | Version exact feature dictionaries and compare deterministic, competition, sparse-association and learned attention variants with paired ablations and resource measurements. |
| ML-027 | 11 | Predict verified fast/deep/multi-worker costs and latency from actual model/host measurements; offer compute-route hints to the existing cognition scheduler. |
| ML-028 | 11 | Preserve TurnPlan explicit DEEP/VERIFY, privacy, subject-specific evidence and busy-game controls before using any ML routing hint; forbid verification downgrades. |
| ML-029 | 11 | Measure answer quality, p95 latency, CPU/RAM/VRAM, model wakeups and repeated-context behavior in side-by-side baseline and proposed routing trials. |
| ML-030 | 09 | Collect independent artifact/objective outcomes and rejected/unknown results as separately sourced experiment labels; never treat LLM success claims as completed work. |
| ML-031 | 09 | Rank eligible LIFE/EVOLVE experiments by expected verified usefulness, cost, uncertainty and distinctiveness, with abstention and owner-readable alternatives. |
| ML-032 | 09 | Use existing RUN resource/experiment admission policy: at most 5 active research experiments, 15 unanswered hypotheses, 200k estimated optional tokens/day and 1h reserved GPU/day. |
| ML-033 | 16 | Compare learned experiment selection against simple deterministic plans using preregistered controls, negative results and long-horizon causal tracking. |
| ML-034 | 13 | Complete independent Debian Hephaestus VM installation, owner-approved internal isolation, enrolled guest identity, snapshot/recovery proof and resource caps before any training execution. |
| ML-035 | 14 | Enforce reviewed dataset rights, training-purpose consent, privacy scope, deduplication and train/heldout isolation; disallow private chat/screens/journals without a separately established explicit policy. |
| ML-036 | 14 | Wire a separately approved, isolated LoRA/QLoRA executor with pinned base/tokenizer, deterministic manifest, measured job quotas, cancellation, restart and artifact verification. |
| ML-037 | 14 | Independently benchmark candidate adapters against base models, prompts and RAG for accuracy, safety, contamination, generalization, cost and personality drift. |
| ML-038 | 14 | Separate model-training acceptance from signed production promotion, canary, previous-model retention, stop, rollback and operator authorization. |
| ML-039 | 01 | Add periodic model/data drift, performance, privacy and permissions audits for each predictor, with lineage reports, shadow replay, disable controls and owner-visible diagnostics. |
| ML-040 | 07 | Prove that source revocation, media expiry, deletion/retraining, state relocation, offline restore and rollback preserve single-writer semantics and invalidate ineligible learned artifacts. |

**Count check:** 700 original CA entries + 40 new ML entries = 740 planned entries. No changes to the original 700-item V18 acceptance ledger.
