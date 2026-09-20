# Sofía Ada Lyra: master roadmap and delivery plan

**Provisional revision:** 2026-09-20, while the Batch G full suite is still running with failures already observed.  
**Working branch:** `feature/g22-live-integration-artemis`, [draft PR #1](https://github.com/Crazysodaman/SofiaAdaLyra/pull/1), **unmerged**; `main` does not contain these changes. This documentation revision was committed *after* the user's ongoing test run began and is not part of that run.  
**Purpose:** Preserve the original A–Z and Engineering 1–26 lineages while organizing future implementation into larger, dependency-aware delivery packages. This document is a planning and evidence index, not proof of implementation.

> **Identity invariant:** The LLM is Sofía's cognitive engine, not Sofía herself. Constitution, canonical identity, embodiment, state, operational evidence, authority and capability enforcement remain outside the model.

## Execution dashboard

| Lane | Delivery package (not a batch rename) | Existing batches | Status and release gate |
| --- | --- | --- | --- |
| **Now** | G closeout and measured model performance | G; relevant F | G implemented with focused and one real idle-persistence verification; **full suite still running with failures**. Diagnose failures, retest, check live startup/style and review diff. No model/context change without a controlled comparison. |
| **Next primary lane** | Memory, retrieval and context | K + Engineering 23; F context contract | Planned. Reuse prior memory and G journals; deliver traceable originals, bounded retrieval, user-reviewed promotion and optional archive migration. |
| **Independent parallel lane** | Authenticated multi-machine operation | Remaining Engineering 22 | Partially implemented. Authenticated Artemis transport/agent, durable execution safety and live two-machine acceptance are outstanding. Remote execution stays unavailable until proven safe. |
| **After relevant dependencies** | Grounded initiative and delivery | L + Engineering 24; relevant M–O only after definitions are recovered | Planned. Depends on memory and G's verified outbox. Remote placement/actions additionally require authenticated 22 and relevant 25 controls. |
| **Built alongside each subsystem** | Resilience and recovery | Engineering 25 | Planned; introduce safety controls where needed, then validate actual recovery and negative scenarios. |
| **Final integration** | Full-system acceptance | Engineering 26 | Planned. Real local + Artemis, memory, agency, safety and performance scenarios; cannot replace earlier focused tests. |

**Package names are workgroup labels, never new canonical batch titles.** A–Z and Engineering 1–26 remain separate historical planning views, not one-to-one mappings. A capability may advance several tracks without completing any of them. Do not retroactively rename a batch or move unfinished work to claim completion.

## How to execute bigger packages without losing correctness

1. **Inspect and reuse first:** inventory source, schemas, current interfaces, existing tests and unresolved failures. Recover reserved batch definitions from actual history rather than invent them. Record which existing records and contracts must survive migration.
2. **Agree an end-to-end package contract:** define owned behavior, dependencies, explicitly deferred features, permissions, rollback and observable acceptance. A mock transport, prompt instruction or journal table is not a deployed capability.
3. **Implement cohesive slices:** small reviewed commits, focused tests and clear integration interfaces inside a larger package. Independent slices may progress together, but do not build a dependent layer on a known-broken prerequisite. Reduce user interruptions by consolidating pulls and test requests into meaningful package checkpoints, not one per minor commit.
4. **Accept as a package:** focused tests for all changed slices, cross-component and negative/security tests, then broader/full suite. Add explicit bounded live Ollama, hardware and Artemis tests where the claim depends on them. If a test did not run, label it **not run**, never green. Slow ten-generation research probes are not silently part of fast validation.
5. **Release deliberately:** review complete diff, exact files, data migrations, security and recorded limitations; obtain needed user approval before merging. If a PR mixes G and unfinished 22, either verify both or separate the scopes by a separately reviewed, authorized Git operation. Do not merge just for branch housekeeping.

**Evidence ledger per package:** commit/PR and exact scope; focused and full-suite results; live results; observed/inferred/unknown distinctions; unresolved limitations; diff and human approval; merge status. Tests validate a contract, not subjective feelings or unrestricted correctness. Do not start a competing full suite while the user's current one runs. A docs-only revision is not a new test result.

## Current verified snapshot and blockers

**G remains acceptance pending.** The branch implements contextual personality expression, evidence-linked modeled emotional appraisals and append-only corrections, retrospectives, a structured thought agent, durable **unsent** outbox, opt-in running-only idle worker, startup self-DB filtering, performance tracing and read-only journal audit. User-verified focused results: **55 passed in 10.49 seconds** on `2a16393`, then **30 passed in 7.80 seconds** on `fb4b738`. The read-only audit showed **one completed idle-worker attempt with one matching persisted model thought**, no reported error, and zero pending unsent messages. One successful reflection is not proof of long-term memory, reliable semantic accuracy, offline thought or notification delivery. See [`docs/development/batch-g-emotional-continuity.md`](docs/development/batch-g-emotional-continuity.md).

**G full suite:** running, failures already visible, final failure list and count **unknown**. Wait for actual `FAILURES` and summary, diagnose, repair without weakening contracts, run targeted regressions and a clean full suite, check a short live startup/affection/serious interaction and inspect the diff. A previous **1,090 passed / 1 failed / 1 skipped** suite belongs to an older revision, not this head. PR #1 also contains unfinished Engineering 22; G acceptance alone cannot authorize its entire merge.

**F performance:** recorded conversation model-lock wait was **0.0 ms**; Ollama generation took ~**12.8–34 seconds for 34–86 output tokens** and **88.2 seconds for 226 tokens**. Prompts were roughly **16k–18k tokens** with 20,000 context *requested*. A GPU snapshot showed mixed CPU/GPU execution and near-full RTX 3080 Ti 12 GB VRAM. Actual effective grounding and faster configurations remain unverified. Earlier F checkpoint: about 70,200 characters of system prompt vs an older 4,096-token allocation; a different checkpoint reported 32,768 while the currently inspected branch requests 20,000. These were **different configurations**, not concurrent values. Earlier non-integration tests: **967 passed, 1 skipped, 5 deselected**; a separate four-variant live regression passed in **808.50 seconds**. The ten-generation probe was interrupted. See [`docs/development/model-evaluation.md`](docs/development/model-evaluation.md).

**Engineering 22:** stable node contracts, peer identity/knowledge/reachability, discovered capability, authorization/gateway and replay foundations exist, but an authenticated deployed Artemis agent/transport and end-to-end live two-machine authorization, auditing and recovery are **not established**. Do not confuse development mock tests with production-safe remote operations.

## Preserve original A–Z ownership

| Area | Batch | Evidence-based status and original boundary |
| --- | --- | --- |
| Core | **A–E** | Historically complete, not freshly re-audited. Preserve core contracts; recover original individual titles before changing scope. |
| Mind | **F** | Partially verified. Model/provider evaluation, full cognitive-context grounding, context budget and measured inference behavior; cross-cuts G and K/23. |
| Mind | **G: Personality Architecture** | Implemented, **acceptance pending**. Evidence-grounded emotion/reflection and representational style; worker/outbox do not imply messages can be sent. |
| Mind | **H–J** | Planned; original individual titles and criteria pending reconciliation. Do not invent them. |
| Mind | **K: Memory Architecture** | Planned with **G groundwork**. Durable originals, provenance-aware retrieval, user-reviewed promotion, controlled ChatGPT archive migration. Shared delivery with Engineering 23. |
| Mind | **L** | Planned; exact prior title pending reconciliation. Meaningful grounded initiative and optional, user-controlled follow-ups; shared delivery with Engineering 24. |
| Agency | **M–O** | Planned; individual definitions pending reconciliation. Proposal, explicit per-action authority, execution and verification; do not rename these via a package label. |
| Growth | **P–W** | Future, definitions pending reconciliation. Preserve reserved Growth sequence. |
| Persistence | **X–Z** | Future, definitions pending reconciliation. Preserve reserved Persistence sequence. |

## Preserve original Engineering 1–26 lineage

The earlier handoff reports **1–21 historically complete**. Historical status is not a fresh audit or claim of flawless live model behavior.

| Batch | Recorded scope | Evidence-based status |
| --- | --- | --- |
| **1–10** | Foundation, cognition/LLM, continuity, bounded agency, runtime, memory, self-model, temporal awareness | Historically complete; inspect existing memory before K/23. |
| **11–18** | Capabilities, filesystem/code tools, operational and persistent continuity, personality/embodiment contracts | Historically structurally complete; live semantic limits tracked separately. |
| **19: Machine & Environment Intelligence** | Machine knowledge, observations, reload, staleness and contradictions | Historically complete. |
| **20: IT / System Capabilities** | Bounded process/system/network/service/hardware inspection | Historically complete; checkpoint **784 passed, 1 skipped**. |
| **21: External Systems & Integrations** | Adapter → structured evidence → external knowledge → cognitive context → cognition | Historically complete. |
| **22: Distributed / Multi-Machine Sofía** | Node identity, reachability, capabilities, per-node authority and verified operations | **Partially implemented; authenticated Artemis transport and live acceptance open**. |
| **23: Long-Term Memory & Learning** | Durable provenance, selective retrieval, reviewed learning and archive migration | Planned; integrate with K without rebuilding G journals. |
| **24: Advanced Autonomy** | Initiative, authorized delivery, follow-ups, resource-aware inference and permitted actions | Planned; G's worker and unsent outbox are only foundations. |
| **25: Safety / Recovery / Resilience** | Audit, revocation, rollback, recovery and failure isolation | Planned; essential controls belong in earlier implementation too. |
| **26: Full Integration / System Validation** | Actual multi-machine, memory, safety, latency and user-workflow acceptance | Planned. |

**Engineering 22A–H remain as originally scoped:** 22A system contracts; 22B remote machine identity; 22C peer knowledge; 22D connectivity/reachability; 22E capability discovery; 22F distributed authority; 22G bounded remote operations; 22H verification. 22A–D foundations are committed; 22E–H have development code/tests, **not** accepted deployed authentication or live Artemis execution. An advertised capability is not permission; a failed ping is not proof of offline state. See [`docs/development/batch-g5-g8-and-22e-22h.md`](docs/development/batch-g5-g8-and-22e-22h.md).

## Delivery package: K + Engineering 23, memory and context

**Proposed execution slices, not newly numbered K sub-batches.** Entry: resolve G regressions and agree stable interfaces; inspect the prior memory subsystem and conversation data before editing.

| Slice | Reuse | Deliverable and testable acceptance |
| --- | --- | --- |
| **Inventory and ownership** | Existing memory/conversation stores; G emotional, reflection and clarification journals | Map originals, model-derived thoughts, source IDs, timestamps, sensitivity, authority, schemas and backward compatibility. Establish migration tests. |
| **Preserved originals and provenance** | Durable messages and G evidence-linked events | Keep immutable originals, append corrections, distinguish observed/user-reported/inferred and missing/conflicting records. Test restart, duplicate import and rollback. |
| **Selective retrieval and context budget** | F measurements, cognitive context assembly, G bounded projections | Fetch permission-scoped, relevant source-linked evidence; prioritize constitution/authority/identity and the user's question; expose truncation/omission. Test conflicts, prompt injection and scarce context. Compare real model responses *before* altering `num_ctx`. |
| **Human-reviewed promotion** | Explicit G clarification and provenance | Inspect/edit/approve/reject candidate long-term memories and summaries; audit/revoke decisions. No automatic promotion to identity, constitution, permissions or observed facts. |
| **User-controlled ChatGPT archive migration** | An archive the user actually provides or authorizes | Validate formats, preserve originals, dedupe, stage review, make summaries traceable, support reversible imports. Test malformed/partial/duplicate and privacy cases. No assumed archive access. |
| **Acceptance and recovery** | Existing SQLite state/lifecycle/tests | Migration backup and recovery, long-horizon relevant retrieval across restarts, grounded live responses, measured token use, focused + full-suite acceptance. |

**Definition of delivered memory:** a recalled answer can identify the original supporting record and its provenance, retain disagreements/corrections, acknowledge unknowns and survive restarts without rewriting canonical identity. G's 50-event/366-day worker window is *not* long-term retrieval. An unsent outbox message is *not* a promoted memory.

## Delivery package: finish Engineering 22

Build and verify enrolled cryptographic peer identity and authenticated transport; deploy a bounded agent to Artemis; discover fresh node-specific capabilities independently of authorization; enforce durable node+capability+operation+expiry grants, replay resistance, audit and failure handling at the execution boundary. Test invalid peers, stale information, revoked grants, replay, disconnects and uncertain results; then complete an explicitly authorized **real** local-to-Artemis two-machine acceptance. No general remote shell, false `authenticate()` implementation or unauthorized background actions. May proceed alongside K/23 only where interfaces and code ownership are independent. Remote model placement additionally depends on measured health/resources and Engineering 24/25 authorization, not the mere existence of a node.

## Delivery package: L + Engineering 24

Entry: dependable K/23 retrieval and G's verified outbox; authenticated 22 for any remote resource or action. Build user-controlled notification delivery with explicit stop/mute/busy choices, natural spacing and cross-event novelty, grounded project/relationship follow-ups and verified earlier/later observation comparisons before declaring a condition worse. Preserve the rule that emotion labels or loneliness do not justify escalation. Add resource-aware inference placement and permitted routine operations *only* with actual hardware/game-activity evidence and per-action authorization. Verify duplicate prevention, no unwanted contact, foreground responsiveness, delivery acknowledgments, restarts and network failure. **G does not currently send messages.**

## Delivery packages: Engineering 25 and 26

**25 Recovery/resilience:** design security, revocation, audit retention, secrets, safe retries, backups and rollback into each earlier subsystem; later validate cross-system crash/restart, uncertainty and negative-security cases. Do not postpone essential 22 authorization to a final hardening pass.

**26 End-to-end validation:** run real local + Artemis workflows spanning personality, memory, permissions, initiative, failures and performance. Label mocked contracts and deployed evidence separately. Prove continuity without claiming thoughts during downtime.

## Architecture and operational discipline

**Capability ≠ Authority. Authentication ≠ Authorization. Observation ≠ Action. Knowledge ≠ Authority. Connectivity ≠ Authority.** Historical default: `can_respond=True`, `can_propose_actions=True`, `can_execute_actions=False`. Intended path: **Think → Propose → Authorize → Execute → Verify**. Personality does not change grants or factual truth.

**Open repository hygiene:** earlier commits included `state/sofia.db`, diagnostic `regression-failure.log` and one-time patch scripts. Review tracking/ignore, privacy and retention deliberately; do not delete valuable state or rewrite published history without approval. Keep unrelated cleanup out of functional fixes.

**Immediate next step:** leave the currently running full suite undisturbed; get its final failure report before diagnosing. Fix the actual G regressions on this existing branch, retest and review. Review this proposed package plan with Sparks before treating its ordering or package scope as approved; G acceptance and any PR merge are separate decisions.
