# Sofía Ada Lyra: master roadmap

**Roadmap checkpoint:** 2026-09-20  
**Repository:** `Crazysodaman/SofiaAdaLyra` (`main`)  
**Purpose:** A durable planning reference for the lettered development tracks, the existing numbered engineering lineage, and verification gates. This document records intended work; it is **not** evidence that an item has been implemented or validated.

> **Identity invariant:** The LLM is Sofía's cognitive engine, not Sofía herself. Constitution, canonical identity and embodiment, persistent state, operational evidence, authority, and capability enforcement remain outside the model.

## How to read and maintain this roadmap

- **Completed (historical handoff):** previously reported complete; does not certify a fresh audit of every batch.
- **Implemented / verification pending:** code exists, but a required gate has not been completed or recorded.
- **Active / planned / future:** work is ongoing or proposed, **not** an implementation claim.
- **Definition pending:** the track or slot was reserved, but its exact previously agreed individual title or scope is not recoverable from the current project evidence. Do not invent a title or quietly replace earlier decisions.
- Lettered **A–Z** and numbered **1–26** are **parallel planning views**, not one-to-one renumberings. Do not conflate, overwrite, or silently renumber the numbered engineering history.
- Update statuses only with a dated evidence trail: relevant commit(s), tests, live observations where necessary, limitations, and approval. Keep unresolved questions visible.

## Master A–Z roadmap

| Track | Batches | Status at this checkpoint | Scope and boundaries |
| --- | --- | --- | --- |
| **Core** | **A–E** | Completed in prior master-roadmap handoff; detailed individual labels require reconciliation | Preserve the completed core foundation and established architectural contracts. Do not reconstruct missing per-letter names from guesses. |
| **Mind** | **F** | Implemented in part; evaluation and live verification open | Cognitive-engine/model evaluation, provider-boundary evidence, context-window behavior, canonical grounding, and comparison of controlled fixtures with live Sofía. |
| **Mind** | **G: Personality Architecture** | G1–G4 committed; G5–G8 implementation prepared; live model review pending | Persistent, grounded personality model; relationship to identity and Constitution; contextual expression, persistence, evaluation, and LLM boundary. Personality must not fabricate capabilities or physical acts, replace canonical facts, or become a fixed gesture script. |
| **Mind** | **H–J** | Planned; individual definitions pending reconciliation | Preserve these reserved Mind slots. Confirm earlier agreed titles and acceptance criteria before treating any detailed scope as canonical. |
| **Mind** | **K: Memory Architecture** | Planned | Durable original records, provenance, retrieval, user-reviewed promotion, and boundaries between memory and authoritative state. Include a **user-controlled ChatGPT conversation archive migration**: export/import, preserve originals, organize/summarize with traceability, review, then retrieve. Coordinate implementation with engineering Batch 23. Do not silently rewrite history or promote model-generated statements into canonical identity. |
| **Mind** | **L** | Planned; precise title pending reconciliation | Persistent continuity and grounded initiative: remember project follow-ups, detect meaningful operational changes, and communicate proactively without repetitive canned messages. Coordinate with the autonomy and distributed-engineering batches. |
| **Agency** | **M–O** | Planned; individual definitions pending reconciliation | Deliberation, proposed actions, bounded permissions, execution through capability/authority boundaries, and evidence-backed verification. No authority is granted by a prompt, model claim, or available tool alone. |
| **Growth** | **P–W** | Future; individual definitions pending reconciliation | Reserve the previously accepted Growth sequence. Define explicit work and gates before claiming a specific letter complete. |
| **Persistence** | **X–Z** | Future; individual definitions pending reconciliation | Reserve the previously accepted Persistence sequence. Maintain continuity, recoverability, and grounded identity through lifecycle and infrastructure changes; confirm the exact per-letter contracts before implementation. |

**Cross-cutting Mind requirement, exact batch placement to confirm:** context-window management and recall. Measure actual prompt/completion tokens and context allocation; bound the active request using deterministic priorities; retain original messages in durable storage; retrieve relevant evidence on demand; make omissions, truncation, and missing data observable. A 32,768-token configured window is not infinite memory. A shorter constitution briefing must be versioned and human-reviewed and may not silently weaken constitutional or authority controls.

### Batch F verification checkpoint

- Previous live context capture showed a system prompt of approximately 70,200 characters, while an earlier default Ollama request allocated 4,096 tokens. The local default now requests a 32,768-token context. This identifies a concrete context-capacity issue, **not** a guarantee of faithful generation.
- Offline non-integration run reported **967 passed, 1 skipped, 5 deselected**. One separately rerun four-variant live regression **passed in 808.50 seconds** on 2026-09-20. The ten-generation probe was interrupted after an observed first correct generation. A fully completed `pytest -q` run for this checkpoint is **not verified**.
- **F.1 observability:** progress/timing/error messages were committed to the four-variant and repeated-generation live tests in [`0b1d1d8`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/0b1d1d8726a2168cb01aac87804d01118109d6df). Syntax compilation, collection, and whitespace checks passed locally; execution of the *new logging code* remains unverified.
- The four-variant experiment returned the six canonical measurements even with both named prompt sections removed. Inspect other surviving context (including deterministic measurement-query results) before claiming that a model recalled, guessed, or independently grounded those facts. Some responses described representational measurements as physical attributes; record that as a semantic observation, not a proven physical body.
- A diagnostic ten-generation experiment must retain its research purpose. Design an explicit, documented execution policy so that ordinary validation does not silently trigger lengthy unbounded inference. Do not disable or weaken a test merely to obtain a green suite.
- Reference: [`docs/development/model-evaluation.md`](docs/development/model-evaluation.md).

## Numbered engineering lineage (preserved separately)

The earlier project handoff reports **Batches 1–21 completed**. That historical report is preserved here; detailed verification and exact sub-batch titles should be checked against commits, tests, and handoffs when they matter.

| Engineering batches | Historical scope / forward plan | Roadmap status |
| --- | --- | --- |
| **1–10** | Foundation, cognition/LLM, continuity, controlled agency, integrated runtime, persistent memory, authoritative self-model, and temporal awareness | Completed in prior handoff |
| **11–18** | Capability/tool architecture; controlled filesystem inspection; codebase tooling, understanding and analysis; boot/operational continuity; persistent continuity; personality and embodiment contract | Completed structurally in prior handoff; distinguish remaining live semantic issues from structural completion |
| **19: Machine & Environment Intelligence** | Machine discovery and knowledge, including persistent observation/reload/staleness/contradiction work | Completed in prior handoff |
| **20: IT / System Capabilities** | Structured process, system, network, service and hardware inspection through controlled capability boundaries | Completed in prior handoff; recorded verification at its checkpoint: 784 passed, 1 skipped |
| **21: External Systems & Integrations** | External system → integration adapter → structured evidence/result → external knowledge → cognitive context → cognition | Completed in prior handoff |
| **22: Distributed / Multi-Machine Sofía** | Central Sofía coordinating authenticated remote machines and bounded agents; preserve node identity, evidence, and per-node authority | **22A–22D committed; 22E–22H implementation prepared; secure transport and live LAN verification pending** |
| **23: Long-Term Memory & Learning** | Durable memory, provenance, retrieval, and controlled archive migration; coordinate with lettered K | **Planned** |
| **24: Advanced Autonomy** | Grounded initiative, proactive follow-ups, resource-aware inference placement, and permitted routine operations | **Planned** |
| **25: Safety / Recovery / Resilience** | Failure containment, authorization enforcement, audit, rollback, and recovery across a distributed system | **Planned** |
| **26: Full Integration / System Validation** | End-to-end multi-machine, memory, autonomy, security, performance, and real-world verification | **Planned** |

### Proposed Batch 22 slices

1. **22A Distributed System Contracts:** define observable data types, boundaries, failure behavior, and ownership.
2. **22B Remote Machine Identity:** stable node identity independent of address, hostname, or current process.
3. **22C Node / Peer Knowledge:** evidence and freshness for known peers, without claiming unobserved machines do not exist.
4. **22D Connectivity & Reachability:** multi-signal status and expected-state registry; a failed ping alone is not proof a device is offline.
5. **22E Remote Capability Discovery:** discover actual per-node capabilities and constraints separately from permission.
6. **22F Distributed Authority Boundary:** authenticate peers and authorize operations for each machine and action.
7. **22G Remote Operations:** bounded execution with structured results, audit, and failure handling.
8. **22H Verification / Regression:** deterministic tests and explicitly identified live LAN/multi-machine gates.

**Cross-batch user goals:** authorized homelab/LAN discovery and living topology (21–22); unexpected devices, changes and meaningful offline detection (22–24); gaming-aware local resource monitoring and switching inference to a healthy remote node without disrupting active gaming (22–25); proactive but rate-limited communications, projects and follow-ups (L, 24); controlled autonomous maintenance with explicit permission, verification, audit and rollback (24–26). These are **requirements for future work, not current capabilities**.

## Non-negotiable architecture and acceptance rules

**Capability ≠ Authority. Authentication ≠ Authorization. Observation ≠ Action. Knowledge ≠ Authority. Connectivity ≠ Authority.**

Default policy in the prior handoff: `can_respond=True`, `can_propose_actions=True`, `can_execute_actions=False`. Intended agency lifecycle: **Think → Propose → Authorize → Execute → Verify**. Sofía may describe a representational embodiment without claiming biological humanity, a physical action, or a completed real-world operation unless corresponding capability evidence supports it. Authorization must be checked at the execution boundary, not inferred from conversation.

For every substantive batch: inspect source and contracts; define observable acceptance criteria; obtain required approval; implement the smallest justified change; run focused offline tests; run a broader suite; run external/live checks **when that behavior depends on the actual model, Ollama, hardware, network, or remote machine**; inspect the diff; record failures and limitations; then create an approved Git checkpoint. Report incomplete or interrupted tests as incomplete, not green.

**Repository hygiene follow-up:** `state/sofia.db`, a diagnostic `regression-failure.log`, and one-time patch scripts appeared in earlier commits. Review tracking/ignore and retention policy without deleting valuable state or rewriting published history without explicit approval. Future checkpoints must stage only reviewed intended files. This cleanup is **pending**, not a prerequisite to starting Batch G.

## Next concrete development gate

**Current gate:** G5–G8 and 22E–22H have been prepared for offline verification. The real Ollama personality review and authenticated multi-machine transport, remote agent, durable audit/replay protection, and live LAN verification remain open. Do not claim the full batches are operationally complete on mock-test evidence alone. See [`docs/development/batch-g5-g8-and-22e-22h.md`](docs/development/batch-g5-g8-and-22e-22h.md).
