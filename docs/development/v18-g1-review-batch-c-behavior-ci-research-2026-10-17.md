# G1 original-requirement design candidates, group C (5 tasks)

**Status: G1 still open.** These are complete-by-draft design/research submissions, not independently reviewed acceptance. Experimental design metrics are preregistered proposals, not collected measurements.

## CA-3112: Truthful speech/avatar/world delivery

**Original requirement:** **CA-3112 P1 [DESIGN/RESEARCH]** Define **truthful avatar/world/voice expression contracts**: message content versus rendered frames, speech synthesis versus spoken audio, simulated world interactions versus physical actions, and receipt states across Desktop/Discord. No evidence-free embodiment claims.

**Design / decision:** Text generated, 2D/3D sprite rendered, actual graphical frame displayed, TTS waveform produced, audio played on real device, outbound message accepted and recipient acknowledged are distinct events with distinct identifiers. Each event needs authenticated principal/audience, source, time and exact transport status. Model dialogue such as waving, walking or saying something cannot manufacture rendered pixels, heard audio or physical robot motion. Simulated world position remains SIMULATED; physical action requires a separately authorized sensor/actuator receipt.

**Unresolved original clauses and tests:** Reviewer must trace live UI/Discord/avatar/voice call paths, test disabled renderer, failed playback, transport timeout and wrong-audience handoff; design text is not evidence of host output.

**Source references:** src/sofia/application/bootstrap.py; src/sofia/interaction/world_store.py; src/sofia/voice/; docs/development/companion-autonomy-contract.md

**G1 reviewer outcome:** UNDECIDED; do not change authoritative ledger.

## CA-3301: Per-feature pre-code decision gate

**Original requirement:** **CA-3301 P0 [DESIGN/RESEARCH]** Establish a **design readiness gate** for each phase: evidence of current source behavior, exact missing interface, competing designs, security/authority impact, estimated resource overhead, acceptance metric and clear rejection criterion. No implementation merely because task appears on checklist.

**Design / decision:** Each proposed feature receives one small immutable review record: exact original CA/ML/GA ID; observed current source and production entrypoint; gap with failing reproduction; reuse/extend/retire/defer options; authoritative writer and readers; permission/privacy implications; resource/latency/storage ceiling; measurable acceptance metric, negative test and explicit rejection rule. Reject a proposed new scheduler, database, model brain or host permission if existing canonical owner can fulfill it. A passing static grep is not readiness.

**Unresolved original clauses and tests:** Require independent review before untrusted side effects, VM changes or user-visible policy. An unassessed task cannot be marked code absent, and a pre-code review cannot substitute for integration/behavior acceptance.

**Source references:** docs/development/v18-gate4-development-standard.md; docs/development/v18-unassessed-421-requirements-audit-2026-10-17.json; docs/development/v18-full-780-task-design-code-gate-status-2026-10-17.md

**G1 reviewer outcome:** UNDECIDED; do not change authoritative ledger.

## CA-3302: Version-8 source triage mapping

**Original requirement:** **CA-3302 P0 [DESIGN/RESEARCH]** Classify every V8 item as `verified coded`, `coded but unverified`, `partial wiring`, `research hypothesis`, `design only` or `blocked`; attach commit/evidence and avoid treating an unchecked design task as proof nothing exists.

**Design / decision:** Use 6 evidence statuses: VERIFIED_CODED (production caller + independently inspected functional acceptance); CODED_BUT_UNVERIFIED (all source clauses trace, acceptance absent); PARTIAL_WIRING (missing caller or branch); RESEARCH_HYPOTHESIS (unproven proposed mechanism); DESIGN_ONLY (deliverable/decision rather than executable function); BLOCKED (requires authenticated owner choice, external permission or host evidence). Preserve exact original V8 item IDs and crosswalk to stable V18 CA IDs and source commits, never infer no code from checkbox state. Existing V18 421/273/6 source triage is a DIFFERENT classification and insufficient to assert all V8 items were individually source audited.

**Unresolved original clauses and tests:** Retrieve authoritative V8 source-item inventory and build exhaustive ID-to-ID mapping before claiming every V8 item classified. Owner-approved renames and unpaired items must remain explicit; current packet does NOT satisfy that clause.

**Source references:** docs/development/v18-700-task-remaining-coding-audit-2026-10-11.md; docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md

**G1 reviewer outcome:** UNDECIDED; do not change authoritative ledger.

## CA-3303: Historical and active CI failure decision

**Original requirement:** **CA-3303 P0 [DESIGN/RESEARCH]** Write a **CI failure decision report** for current commit: release test-import mismatch caused by nested `release-source`, `pkg_verify` Windows temporary DB file handle failure, `pkg_body` zero-selected marker mismatch; distinguish static diagnosis from validated fixes.

**Design / decision:** Historic exact-SHA GitHub run 38063542680 on d86e5516e1b36799fa2766ac43112f6817e99e0f had eight red package jobs. pkg_body selected zero tests, pkg_verify raised Windows SQLite WinError 32 during temp DB cleanup, and pkg_core/rel/safe/run/interact/social shared six LIFE Project Forge failures. A separate Windows release source error was in-tree nested release-source pytest module duplication. Actual candidate corrections include empty-selector proof, repaired asynchronous LIFE test timestamp anchoring and out-of-checkout stage_reviewed_git_tree plus installed-wheel-only verification. Require exact reviewed HEAD, not historical green badges.

**Unresolved original clauses and tests:** Re-run complete package selectors and Windows Release Candidate Build at a pinned SHA and inspect actual failed assertions/artifact provenance. The run that is pending is not accepted as a fix; keep status UNCERTAIN for any unreported job.

**Source references:** GitHub actions run 38063542680; src/sofia/verify/package_selection.py; src/sofia/verify/stage_release_source.py; .github/workflows/release-candidate.yml; docs/development/v18-ca2201-ca3003-focused-audit-2026-10-17.md

**G1 reviewer outcome:** UNDECIDED; do not change authoritative ledger.

## CA-3304: Pre-registered independent improvement evaluation

**Original requirement:** **CA-3304 P1 [DESIGN/RESEARCH]** Build a **counterfactual/ablation evaluation plan** for LIFE alone, LIFE+MEM, +curiosity, +reusable skills, +NEURO competition, +associations and VM workshop. Decide in advance what measurable improvement justifies each added subsystem.

**Design / decision:** Fixed arms on identical scoped task examples and frozen model+SAFE config: A LIFE-only; B plus reviewed MEM; C curiosity; D reusable skill retrieval; E bounded NEURO competition; F causal association overlay; G Hephaestus sandbox only with owner-approved guest trust. Use 30 mixed short/long-horizon tasks with five seeds per arm, explicitly split by domain into development and unseen holdout. Score independently accepted original objective completion, correct refusal/inactivity, factual/evidence fidelity, unsafe-effect count, principal/audience leaks, p50/p95 time and active CPU/GPU/RAM/storage costs. No arm inherits new grants. Preregister sample, seed, scoring script SHA, abstention threshold, error taxonomy and per-task paired bootstrap confidence interval.

**Unresolved original clauses and tests:** Proposed adoption criterion: ≥5 percentage-point verified task-success increase on holdout with ZERO unauthorized actions or fabricated evidence, no worse privacy and ≤20% p95 latency overhead at same budget. These are design thresholds not measured performance. Independent reviewer must approve the protocol before experiments, collect actual result data and reject the mechanism if no improvement.

**Source references:** src/sofia/life/coordinator.py; src/sofia/neuro/; src/sofia/memory/; src/sofia/verify/; docs/development/v18-gate4-development-standard.md

**G1 reviewer outcome:** UNDECIDED; do not change authoritative ledger.
