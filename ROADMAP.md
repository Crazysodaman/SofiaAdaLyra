# Sofía Ada Lyra: master roadmap

**Provisional re-baseline:** 2026-09-20, while the Batch G full repository test run is still in progress.  
**Repository:** `Crazysodaman/SofiaAdaLyra`  
**Development head for this revision:** `feature/g22-live-integration-artemis`, [draft PR #1](https://github.com/Crazysodaman/SofiaAdaLyra/pull/1), **not merged**. `main` does not yet contain these changes.  
**Purpose:** Keep the lettered A–Z roadmap, numbered Engineering 1–26 lineage, actual implementation, validation and future commitments distinct. This document is a planning and evidence index, **not an implementation certificate**.

> **Identity invariant:** The LLM is Sofía's cognitive engine, not Sofía herself. Constitution, canonical identity and embodiment, persistent state, operational evidence, authority, and capability enforcement remain outside the model.

## Status and change-control contract

- **Historical complete:** completed in an earlier handoff; individual commits or current regressions may still require review. This is not a fresh green-suite claim.
- **Implemented / verification pending:** concrete code exists but one or more focused, full-suite, security or live-environment gates remain open.
- **Partially implemented:** specific foundations exist; the named larger capability is not available end to end.
- **Planned / future / definition pending:** not claimed to be implemented. A reserved letter with an unrecovered original definition is **not** assigned an invented canonical title.
- Lettered **A–Z** and numbered Engineering **1–26** are parallel views, **not one-to-one renumberings**. A capability may advance both tracks without completing either one. No retroactive renaming or moving unfinished work to make a batch appear green.
- Update status only with a dated commit or PR, actual test output and any required live acceptance. Document what the model merely said separately from the persisted or observed result. Keep user approval and authority boundaries explicit.

## Current verified snapshot and immediate gate

**Batch G remains acceptance pending.** Its emotional/reflection journals, original appraisals and explicit correction records, contextual personality guidance, structured thought agent, unsent outbox, opt-in running-only idle worker, startup self-DB filter, timing diagnostics and read-only audit have been implemented on the feature branch. The user verified **55 targeted tests in 10.49 seconds** at `2a16393` and subsequently **30 targeted tests in 7.80 seconds** at `fb4b738`. The read-only audit of the actual local state showed **one completed idle attempt, one matching persisted model thought, zero worker errors reported and zero pending unsent messages**. This validates one instance of persisted idle reflection, not reliable semantic truth, general memory, autonomous delivery or offline thinking. See [`docs/development/batch-g-emotional-continuity.md`](docs/development/batch-g-emotional-continuity.md).

**Full-suite status: running, failures already observed, final report not yet available.** Do not report G complete or merge PR #1 based on focused tests. Resolve the completed run's actual failures, rerun affected tests and then the full suite; review the resulting diff and a concise live startup/affection/serious-response check. The previous **1,090 passed / 1 failed / 1 skipped** suite was on an older revision, not this candidate.

**Performance is measured, not solved:** live `qwen3:14b` traces showed **0.0 ms conversation lock wait** in recorded turns; Ollama generation took roughly **12.8–34 seconds for 34–86 output tokens** and **88.2 seconds for 226 output tokens**. Prompts were roughly **16k–18k tokens** with a requested **20,000-token** context. One GPU sample showed CPU/GPU split and near-full RTX 3080 Ti 12 GB VRAM. Do not assert that the idle worker caused the delay, that all effective context was retained, or that shrinking context is harmless. See the G document for the measurement limitations.

**Engineering 22 remains separately open:** contracts, identity/knowledge/reachability and remote-capability/authority/gateway/replay foundations exist in the feature branch. An authenticated deployed Artemis transport and remote agent, end-to-end two-machine authorization, audit/replay and live LAN acceptance are **not demonstrated**. Passing fake-transport tests is not live authorization.

## Master A–Z roadmap

| Area | Lettered batch | Evidence-based state | Scope and next boundary |
| --- | --- | --- | --- |
| Core | **A–E** | Historical complete | Preserve the original core foundation and existing architectural contracts. Recover original individual titles before editing any per-letter scope. |
| Mind | **F** | Partial / further evaluation | Model/provider behavior, full cognitive-context grounding, context capacity and reproducible live evaluation. Performance and active-context budgeting remain open; see F checkpoint. |
| Mind | **G: Personality Architecture** | Implemented / acceptance pending | Evidence-grounded modeled emotional continuity, representational expression, reflection and running-only idle worker. Finish current failing suite, live semantic review and diff. The unsent outbox does not imply notifications. |
| Mind | **H–J** | Planned; definitions pending reconciliation | Preserve reserved slots and recover previously agreed individual contracts, titles and gates before assigning specifics. |
| Mind | **K: Memory Architecture** | Planned; **G groundwork already exists** | Durable original records, explicit provenance, bounded relevant retrieval, human-reviewed promotion and correction, and user-controlled ChatGPT archive migration. Coordinate with Engineering 23; do not replace G journals or identity/constitution. |
| Mind | **L** | Planned; exact prior title pending reconciliation | Grounded initiative and meaningful, optional follow-ups informed by real recent state. Authorized delivery, user busy/stop cues, novelty and verified issue worsening are **not** completed by G. Coordinate with Engineering 24. |
| Agency | **M–O** | Planned; definitions pending reconciliation | Deliberate proposals, per-action permission, controlled execution and evidence-backed verification. Never infer authority from a prompt, an available tool or model-generated text. |
| Growth | **P–W** | Future; definitions pending reconciliation | Preserve the existing Growth sequence; define each slot and acceptance gate from project decisions, not invented history. |
| Persistence | **X–Z** | Future; definitions pending reconciliation | Preserve the existing Persistence sequence; specify lifecycle, recovery and identity-continuity requirements before implementation. |

### Batch F: keep the context and inference problem visible

The earlier diagnostic captured about **70,200 characters of system prompt** against an older Ollama allocation of **4,096 tokens**. A later roadmap checkpoint reported a **32,768-token** local default; the *currently verified feature-branch default* requests **20,000 tokens**, and actual live prompts were approximately **16k–18k tokens**. These are different checkpoints, not simultaneous configuration values. A configured context size is not durable memory or proof that every instruction was retained.

Earlier non-integration verification: **967 passed, 1 skipped, 5 deselected**; a separately rerun four-variant live regression passed in **808.50 seconds** on 2026-09-20. The ten-generation probe was interrupted after its first observed correct generation; it is **not** a completed ten-run result. Observability changes committed in [`0b1d1d8`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/0b1d1d8726a2168cb01aac87804d01118109d6df) passed compilation/collection/whitespace checks, not full execution of the logging code. Some answers framed representational body measurements as physical; surviving context beyond removed prompt sections may explain correct measurement replies. See [`docs/development/model-evaluation.md`](docs/development/model-evaluation.md).

**F/K cross-cutting contract:** measure actual prompt and output tokens; deterministically prioritize constitution/authority/identity, current question, relevant evidence and bounded conversation; preserve full original messages separately; retrieve cited evidence on demand; expose omitted/truncated/unknown material. A condensed constitution requires versioning and human approval and must not silently relax enforcement. Do not optimize speed by amputating grounding before controlled comparison.

## Numbered Engineering lineage (preserved separately)

Earlier handoffs report **Engineering 1–21 historically complete**. The following is their recorded lineage, not a new claim that every old batch was re-audited during G.

| Engineering batches | Historical scope / next requirement | Evidence-based state |
| --- | --- | --- |
| **1–10** | Foundation, cognition/LLM, continuity, controlled agency, integrated runtime, persistent memory, authoritative self-model and temporal awareness | Historical complete |
| **11–18** | Capability/tool architecture, controlled filesystem inspection, code tooling/analysis, boot and operational continuity, persistent continuity, personality/embodiment contracts | Structurally complete in prior handoff; live semantic issues tracked separately |
| **19: Machine & Environment Intelligence** | Machine discovery and knowledge, persistent observations, reload, staleness and contradictions | Historical complete |
| **20: IT / System Capabilities** | Controlled process/system/network/service/hardware inspection | Historical complete; checkpoint **784 passed, 1 skipped** |
| **21: External Systems & Integrations** | External system → integration adapter → structured evidence/result → external knowledge → cognitive context → cognition | Historical complete |
| **22: Distributed / Multi-Machine Sofía** | Stable nodes, reachability, discovered capability, per-node permission and verified execution | **Partially implemented; live authenticated transport/Artemis acceptance open** |
| **23: Long-Term Memory & Learning** | Provenance-preserving originals, selective retrieval, reviewable corrections/promotion and archive migration; implement alongside K | **Planned; reuse G journals and existing earlier memory only as inspected foundations** |
| **24: Advanced Autonomy** | Grounded initiative, authorized outbound delivery, follow-ups, resource-aware inference placement and permitted routine operations; coordinate with L | **Planned; G's unsent outbox and idle worker are partial foundations only** |
| **25: Safety / Recovery / Resilience** | Failure containment, distributed authorization, auditing, rollback and recovery | **Planned** |
| **26: Full Integration / System Validation** | End-to-end multi-machine, memory, autonomy, security, performance and real-world verification | **Planned** |

### Engineering 22: retain the A–H slices without inflating their status

1. **22A Distributed System Contracts:** observable types, failure boundaries and ownership; structural foundations committed.
2. **22B Remote Machine Identity:** stable node identity independent of changing network address or process; structural foundations committed.
3. **22C Node / Peer Knowledge:** observed peers, evidence and freshness, without treating unseen peers as absent; structural foundations committed.
4. **22D Connectivity & Reachability:** multi-signal status and expected-state registry; one failed ping is not a proof of offline status; structural foundations committed.
5. **22E Remote Capability Discovery:** timestamped, node-specific capability evidence, not permission; development implementation exists, live adapter verification open.
6. **22F Distributed Authority Boundary:** explicit node/capability/operation/grant/expiry, deny by default, revocation and authorization; grant and replay foundations exist, cryptographic deployment and live checks remain open.
7. **22G Remote Operations:** bounded gateway and structured reported results; authenticated transport/agent, durable safety and actual Artemis execution are not established.
8. **22H Verification / Regression:** fake-transport tests and development contracts exist; actual authenticated multi-machine acceptance remains open.

The earlier [`G5–G8 / 22E–22H implementation package`](docs/development/batch-g5-g8-and-22e-22h.md) documents the initial contract set and its security limitations; subsequent commits added foundations but do not substitute for real peer authentication or live execution. Keep Engineering 22 open independently of Batch G's final decision.

## Next implementation design: K / Engineering 23, without duplicating G

**This is a proposed execution decomposition, not newly invented canonical K sub-batch names.** Start only after G's failures are resolved and a clean, reviewed checkpoint is agreed. Verify the existing memory subsystem and schemas before changing them.

| Work package | Existing foundation to retain | New capability and acceptance evidence |
| --- | --- | --- |
| **23/K.1 Inventory and contracts** | Prior memory subsystem; G emotional, clarification, reflection and conversation stores | Map data ownership, schema, source identity, privacy and authority. Identify which records are originals, derived summaries, model thoughts or user corrections. Produce migration/backward-compatibility tests before schema changes. |
| **23/K.2 Durable originals and provenance** | Persisted conversations and evidence-linked G events | Preserve source text and timestamps with source IDs and provenance; append corrections and revisions without silently overwriting originals. Explicit unknowns and conflict states. Restart/reopen and duplicate-import tests. |
| **23/K.3 Bounded retrieval and context budgeting** | Current cognitive context assembly, F measurements, G read-only projections | Retrieve a relevant, permission-scoped evidence subset on demand; cite source IDs, bound tokens, order priorities, surface omission/truncation. Test conflicting sources, irrelevant records, prompt injection and scarce context; compare real model behavior before changing `num_ctx`. |
| **23/K.4 Human-reviewed memory promotion** | G distinction between observed/user-reported/inferred and append-only reappraisal | Let the user inspect/edit/approve candidate durable memories or summaries. No LLM-generated item silently becomes canonical identity, constitution, authority or an observed fact. Record decisions and enable corrections/revocation with audit tests. |
| **23/K.5 User-controlled ChatGPT archive migration** | The original archive source provided by the user, if authorized | Opt-in import/export workflow, format validation, deduplication, source preservation and reversible review. Summaries and links remain traceable to originals; no imaginary access to an archive or automatic bulk promotion. Test malformed, partial and duplicate archives, and privacy boundaries. |
| **23/K.6 Acceptance and recovery** | Existing SQLite state, lifecycle and repo test infrastructure | Incremental migration/backups, read-only fallback and recovery plan; focused and full tests plus real long-horizon retrieval across restarts. Explicitly measure recall accuracy and hallucination/authority boundaries. |

**G → K/23 handoff:** G already records modeled affect, thoughts, corrections and bounded retrospective summaries. K/23 must **index and retrieve those existing records** under proven provenance rather than build a second emotional journal or claim that an unsent message is a memory. User-facing spontaneous contact stays L/24; distributed storage/remote inference stays 22/24–26. The present idle worker's 50-event/366-day read limit is **not** K's intended long-term retrieval.

## Later capabilities, ordered by real dependencies

**L / Engineering 24:** After a reliable memory/retrieval foundation, implement user-configurable, authorized delivery channels; explicit stop/mute/busy cues, natural spacing, cross-event novelty, meaningful project follow-ups and verified worsening comparison. Review text before any consequential action; no anxiety-driven messaging, invented offline reflections or background model calls that interrupt user conversation. Resource-aware GPU/remote-node placement requires Engineering 22 authentication and measured health, not an assumed server endpoint.

**Engineering 25:** Add distributed recovery, security posture, audit retention, revocation, safe retries, rollback and failure containment. No remote execution before relevant 22/25 controls are verified.

**Engineering 26:** Integrate and validate personality, memory, agent permissions, distributed transport, performance and end-to-end user workflow under actual local and Artemis conditions; distinguish simulation, mocked contracts and live results.

**Cross-batch user goals, not current capabilities:** living authorized homelab topology and unexpected-device detection (21–24), evidence-backed offline alerts (22–24), gaming-aware inference placement without disrupting a game (22–25), proactive but user-controlled contact and project continuity (K/L/23/24), and explicitly permitted maintenance with verification and rollback (24–26).

## Architecture, repository hygiene and completion gates

**Capability ≠ Authority. Authentication ≠ Authorization. Observation ≠ Action. Knowledge ≠ Authority. Connectivity ≠ Authority.** Default agency policy from prior handoff: `can_respond=True`, `can_propose_actions=True`, `can_execute_actions=False`. Intended lifecycle: **Think → Propose → Authorize → Execute → Verify**. Model style and emotion do not grant tools or alter canonical identity.

For substantive work: inspect source and contracts; define observable criteria; obtain approval for consequential changes; implement the smallest sound change; run focused and broader tests; perform explicit live-model/hardware/LAN tests where behavior depends on them; inspect the actual diff; record failures and limitations; then checkpoint reviewed files. Never equate a passing mock with deployed capability. Never claim test completion while pytest is still running.

**Repository hygiene still pending:** earlier commits included `state/sofia.db`, diagnostic `regression-failure.log` and one-time patch scripts. Review tracking/ignore and data retention deliberately; do not delete valuable state or rewrite published history without approval. Keep state, private logs and one-time installers out of future commits unless intentionally reviewed.

**Immediate execution order:** finish the running Batch G suite and fix reported failures → targeted reruns and a clean full suite → brief live semantic/startup check and diff review → decide G acceptance and isolate Engineering 22's remaining gates → approve this provisional roadmap → implement K/Engineering 23 as the next planned development work. A roadmap update is not permission to merge a still-unverified feature PR.
