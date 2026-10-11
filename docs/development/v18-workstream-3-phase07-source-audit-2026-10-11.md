# Workstream 3 Phase 07: 26-task memory/archive source and design audit

**Read-only source audit:** 2026-10-11, `main` `25a6d046c434622abb4b4d148733a26d669c99c9`. Original 26 CA IDs and task wording remain in the master; this standalone report does not change the 700-task ledger, give the model deletion powers, run tests or authorize host changes.

**Approved human decision applied:** candidate-scoped Option B forgetting: independent authenticated erasure journal, restore replay, and exactly **2 verified encrypted backup generations per target**. No blanket erasure of original conversation or all user data can be inferred from that narrow approval.

**Finding:** 26/26 original tasks are labelled **DESIGN/RESEARCH**. Some reusable implementation exists, especially provenance/correction, archive segments and scoped candidate erasure, but full research/benchmark/UX deliverables are not proven. No CA ID is labelled coding-complete or accepted merely because a class exists. Rows below identify concrete source evidence and what design/research proof is still needed.

## Phase 07 first-pass inventory

| CA ID | Shared ledger status at audit | Current source | Unresolved evidence/design clause |
|---|---|---|---|
| **CA-3401** | unassessed | src/sofia/memory/provenance_store.py | Define changed source vs correction vs revoked permission metrics and benchmark. |
| **CA-3402** | unassessed | src/sofia/life/coordinator.py | Publish minimum independently observed causal link diagram and counterexamples. |
| **CA-3403** | unassessed | src/sofia/memory/historical.py | Benchmark chronological/entity/outcome retrieval on held-out questions. |
| **CA-3404** | unassessed | src/sofia/memory/deletion_ledger.py | Author complete ancestor-to-descendant invalidation matrix; prove each downstream source. |
| **CA-3405** | unassessed | src/sofia/life/coordinator.py | Design negative-method memory that is local to an attempt without labeling user or all tasks unsafe. |
| **CA-3406** | unassessed | src/sofia/application/presence.py | Audit explicit type distinctions for hypothesis, simulation, inference, assertion and model prose across every episode. |
| **CA-3407** | unassessed | src/sofia/memory/deletion_ledger.py | Set retention/expiry/access class for all private, personal, operational and simulated experience types. |
| **CA-3408** | unassessed | src/sofia/application/conversation_learning.py | Define no-consolidation conditions and false-promotion benchmark across actual channels. |
| **CA-3409** | unassessed | src/sofia/life/procedures.py | Measure gains and regressions against held-out tasks and evaluate test leakage. |
| **CA-3410** | unassessed | src/sofia/memory/originals.py | Benchmark token savings, correction accuracy and temporal fidelity with/without compression. |
| **CA-4901** | unassessed | src/sofia/memory/archive_segments.py | Produce 1/10/25/50-year source-volume projections with I/O/load evidence. |
| **CA-4902** | unassessed | src/sofia/memory/originals.py | Trace thread ordered indexed cursor reads and create stable resume/cancel test matrix. |
| **CA-4903** | partial_wiring | src/sofia/memory/archive_segments.py | Confirm one single-writer catalog maps immutable segments into a recoverable source-indexed archive. |
| **CA-4904** | unassessed | src/sofia/memory/archive_segments.py | Prove fsync/manifest/pointer checkpoint/cleanup ordering under crashes and orphan objects. |
| **CA-4905** | unassessed | src/sofia/memory/archive_segments.py | Write comparable format experiments and rollback/storage portability decision. |
| **CA-4906** | unassessed | src/sofia/creative/store.py | Specify consent, license, dedupe, quotas, media class, encryption, retention for every named media. |
| **CA-4907** | unassessed | src/sofia/state/canonical_sqlite.py | Measure real WAL locking, SSD endurance, vacuum, Windows handles and busy contention under load. |
| **CA-4908** | unassessed | src/sofia/memory/archive_segments.py | Define time-tier access latency and permission-scoped on-demand encrypted recovery benchmark. |
| **CA-5101** | unassessed | src/sofia/memory/provenance_store.py | Define authoritative correction transaction, temporal claim validity and downstream invalidation. |
| **CA-5102** | unassessed | src/sofia/memory/deletion_cli.py | User-facing separate 'no longer true' versus 'delete' entrypoints and truthful receipt UX remain open. |
| **CA-5103** | unassessed | src/sofia/memory/deletion_ledger.py | Generalize only with authorization to all original transcripts, assets, caches, exports and authorized remote copies. |
| **CA-5104** | unassessed | src/sofia/memory/archive_segments.py | Prove revocable segment keys/integrity anchors and no undeletable personal data across archives. |
| **CA-5105** | unassessed | src/sofia/application/presence.py | Research data-category policy for voice, Discord, phone, Hephaestus and private/intimate content. |
| **CA-5106** | unassessed | src/sofia/memory/reviewed_workflow.py | Threat-model archive injection, timestamps, forged receipts, cross-channel and model paraphrase. |
| **CA-5107** | unassessed | src/sofia/memory/historical.py | Design scoped machine/human readable history, corrections, licenses, diary, skills and redaction semantics. |
| **CA-5108** | unassessed | docs/development/memory-deletion-retention-policy.md | Research legal/relational legacy access with explicit owner-chosen trustee/erasure policy, no auto activation. |

## Original requirements and source checks

### CA-3401

- [ ] **CA-3401 P1 [DESIGN/RESEARCH]** Evaluate stale and superseded memory facts against Memora-style forgetting-aware metrics; distinguish changed preference, stale host telemetry, invalid source, revoked scope and user correction. Deliver a table of failure outcomes, not a new memory database.

**Current source:** `src/sofia/memory/provenance_store.py`, `src/sofia/memory/temporal_candidates.py`.

**Observed implementation boundary:** Candidate status, expiry, corrections exist. No reproducible Memora-style stale/superseded metric study read.

**Next design/research or verification:** Define changed source vs correction vs revoked permission metrics and benchmark.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3402

- [ ] **CA-3402 P1 [DESIGN/RESEARCH]** Diagram causal links for one LIFE experience: intention → tool choice → execution proof → environmental observation → objective evaluation → later choice; identify the *minimum* links existing stores can preserve.

**Current source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Observed implementation boundary:** LIFE project_causal_trace and source-linked RUN evaluation chain exist. Do not call it a graph benchmark.

**Next design/research or verification:** Publish minimum independently observed causal link diagram and counterexamples.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3403

- [ ] **CA-3403 P1 [DESIGN/RESEARCH]** Compare chronological, entity-linked, and outcome-linked retrieval for task episodes with AMA-Bench-inspired questions. Decide when simple metadata is better than a new graph index.

**Current source:** `src/sofia/memory/historical.py`, `src/sofia/memory/originals.py`.

**Observed implementation boundary:** Bounded session-scoped original retrieval and historical import evidence exist.

**Next design/research or verification:** Benchmark chronological/entity/outcome retrieval on held-out questions.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3404

- [ ] **CA-3404 P0 [DESIGN/RESEARCH]** Specify correction-propagation rules across MEM, REL, LIFE interests, GOALS, HABIT, skill projections, cached summaries and NEURO association candidates. Explain how an invalid ancestor blocks its descendants.

**Current source:** `src/sofia/memory/deletion_ledger.py`, `src/sofia/memory/provenance_store.py`, `src/sofia/neuro/store.py`.

**Observed implementation boundary:** Physical candidate deletion and correction links exist; full downstream cache/prompt/skills/NEURO invalidation not proven.

**Next design/research or verification:** Author complete ancestor-to-descendant invalidation matrix; prove each downstream source.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3405

- [ ] **CA-3405 P1 [DESIGN/RESEARCH]** Design a negative-memory policy: preserve evidence that a method failed and why, without storing misleading user judgments or declaring the method universally unsafe.

**Current source:** `src/sofia/life/coordinator.py`, `src/sofia/life/store.py`.

**Observed implementation boundary:** LIFE records technical failures and uncertain outcomes with reasons.

**Next design/research or verification:** Design negative-method memory that is local to an attempt without labeling user or all tasks unsafe.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3406

- [ ] **CA-3406 P1 [DESIGN/RESEARCH]** Distinguish observation, assertion, inference, hypothesis, simulation, user preference and LLM-generated narrative in every retained episode. Decide whether existing type fields suffice.

**Current source:** `src/sofia/application/presence.py`, `src/sofia/neuro/model.py`, `src/sofia/memory/provenance_store.py`.

**Observed implementation boundary:** Presence observed/known epistemic states and MEM candidate provenance exist.

**Next design/research or verification:** Audit explicit type distinctions for hypothesis, simulation, inference, assertion and model prose across every episode.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3407

- [ ] **CA-3407 P1 [DESIGN/RESEARCH]** Define lifecycle and retention for personal, private, operational and simulated experiences; separate deletion from expiration, and show exactly how revocation affects retrieval and exported portfolio artifacts.

**Current source:** `src/sofia/memory/deletion_ledger.py`, `docs/development/memory-deletion-retention-policy.md`.

**Observed implementation boundary:** Owner-approved Option B journal and two-snapshot policy exist for scoped memory candidates.

**Next design/research or verification:** Set retention/expiry/access class for all private, personal, operational and simulated experience types.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3408

- [ ] **CA-3408 P2 [DESIGN/RESEARCH]** Evaluate **when not to consolidate**: rare one-off chatter, low-confidence context, sensitive data, repetitive unchanged telemetry and ambiguous model-generated speculation should not become durable personal facts automatically.

**Current source:** `src/sofia/application/conversation_learning.py`, `src/sofia/memory/reviewed_workflow.py`.

**Observed implementation boundary:** Conservative exact-original proposed candidates are distinct from promoted reviewed memory.

**Next design/research or verification:** Define no-consolidation conditions and false-promotion benchmark across actual channels.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3409

- [ ] **CA-3409 P1 [DESIGN/RESEARCH]** Decide how genuinely improved skill evidence will be scored across multiple attempts, including regression, changed tasks and test leakage. A 'lesson learned' paragraph alone does not prove ability.

**Current source:** `src/sofia/life/procedures.py`, `src/sofia/life/coordinator.py`.

**Observed implementation boundary:** Two-project source-verified creative procedure promotion exists.

**Next design/research or verification:** Measure gains and regressions against held-out tasks and evaluate test leakage.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-3410

- [ ] **CA-3410 P2 [DESIGN/RESEARCH]** Design a memory compression benchmark: measure accuracy, forgetting-aware correction, token savings and temporal fidelity against leaving the reviewed episodes uncompressed.

**Current source:** `src/sofia/memory/originals.py`, `src/sofia/memory/promoted_retrieval.py`.

**Observed implementation boundary:** Original snippets and promoted retrieval are separate.

**Next design/research or verification:** Benchmark token savings, correction accuracy and temporal fidelity with/without compression.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4901

- [ ] **CA-4901 [DESIGN/RESEARCH]** Profile existing SQLite schema/API and estimate volume at 1, 10, 25 and 50 years separately for text, message metadata, indices, summaries, embeddings, audio/video, experiment logs and content-addressed artifacts; provide low/likely/high usage envelopes.

**Current source:** `src/sofia/memory/archive_segments.py`, `src/sofia/state/canonical_sqlite.py`.

**Observed implementation boundary:** Sealed archive segment API and canonical SQLite guard present.

**Next design/research or verification:** Produce 1/10/25/50-year source-volume projections with I/O/load evidence.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4902

- [ ] **CA-4902 [DESIGN/RESEARCH]** Replace *whole-session materialization* in the proposed API with indexed cursor pagination (`thread_id`, ordered sequence/time, limit), stable cursors, read-only historical slices and batch replay; benchmark no O(N) per-turn load for a lifelong owner thread.

**Current source:** `src/sofia/memory/originals.py`, `src/sofia/memory/historical.py`, `src/sofia/application/bootstrap.py`.

**Observed implementation boundary:** Historical/session retrieval interfaces exist; whole-session materialization risks not measured.

**Next design/research or verification:** Trace thread ordered indexed cursor reads and create stable resume/cancel test matrix.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4903

- [ ] **CA-4903 [DESIGN/RESEARCH]** Specify one **canonical state catalog** in `sofia.db` plus optional encrypted, compressed, time/size-partitioned immutable-original segments as external **assets**, never independent active databases or a second writer.

**Current source:** `src/sofia/memory/archive_segments.py`, `src/sofia/memory/deletion_ledger.py`.

**Observed implementation boundary:** Encrypted archive segments and canonical candidate state exist as separate designs.

**Next design/research or verification:** Confirm one single-writer catalog maps immutable segments into a recoverable source-indexed archive.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4904

- [ ] **CA-4904 [DESIGN/RESEARCH]** Define crash-safe segment lifecycle: build → hash → fsync → manifest checkpoint → catalog pointer commit → safe previous-state cleanup. Include interrupted checkpoint, orphan object, corrupt block and disk-full reconciliation.

**Current source:** `src/sofia/memory/archive_segments.py`, `src/sofia/ops/backup.py`.

**Observed implementation boundary:** Sealed archive stage/recover and operator backups exist.

**Next design/research or verification:** Prove fsync/manifest/pointer checkpoint/cleanup ordering under crashes and orphan objects.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4905

- [ ] **CA-4905 [DESIGN/RESEARCH]** Compare raw text in SQLite versus segmented JSONL/CBOR+zstd, SQLite read-only snapshots and content-addressed object blobs; select by portability, compression, lookup time, deletion, backup consistency and ability to reconstruct without proprietary tools.

**Current source:** `src/sofia/memory/archive_segments.py`, `src/sofia/memory/originals.py`.

**Observed implementation boundary:** An encrypted segment approach exists; not evidence that JSONL/CBOR/zstd and SQLite options were benchmarked.

**Next design/research or verification:** Write comparable format experiments and rollback/storage portability decision.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4906

- [ ] **CA-4906 [DESIGN/RESEARCH]** Define asset rules for voice clips, photos, video, generated 3D assets and tests: consent to capture, default retention, object deduplication, encryption, storage quota, content type/license, malware scanning and a readable manifest. Don't put unbounded media in chat rows.

**Current source:** `src/sofia/creative/store.py`, `src/sofia/memory/archive_segments.py`.

**Observed implementation boundary:** Creative artifact and archive bytes paths exist.

**Next design/research or verification:** Specify consent, license, dedupe, quotas, media class, encryption, retention for every named media.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4907

- [ ] **CA-4907 [DESIGN/RESEARCH]** Model SSD endurance and maintenance: transaction batching, checkpoint starvation, WAL limits, per-table/index growth, SQLite busy/lock handling, VACUUM policy and known Windows file-handle recovery; explicitly avoid live WAL on SMB/NFS.

**Current source:** `src/sofia/state/canonical_sqlite.py`, `src/sofia/ops/backup.py`.

**Observed implementation boundary:** Canonical SQLite connection guard and backups exist.

**Next design/research or verification:** Measure real WAL locking, SSD endurance, vacuum, Windows handles and busy contention under load.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-4908

- [ ] **CA-4908 [DESIGN/RESEARCH]** Define archive access tiers and latency budgets (current, 30-day, 1-year, 25-year): permission-scoped metadata search without retrieving encrypted payload until needed, deterministic on-demand reads and optional idle/offline re-indexing.

**Current source:** `src/sofia/memory/archive_segments.py`, `src/sofia/memory/promoted_retrieval.py`.

**Observed implementation boundary:** Segment recovery and reviewed source retrieval exist.

**Next design/research or verification:** Define time-tier access latency and permission-scoped on-demand encrypted recovery benchmark.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5101

- [ ] **CA-5101 [DESIGN/RESEARCH]** Design explicit correction and contradiction transactions: new superseding claim, old source preserved where retention permits, authority source, time-validity, immediate downstream cache/prompt invalidation, and periodic full reindex proof.

**Current source:** `src/sofia/memory/provenance_store.py`, `src/sofia/memory/temporal_candidates.py`.

**Observed implementation boundary:** Correction linking and candidate expiration exist.

**Next design/research or verification:** Define authoritative correction transaction, temporal claim validity and downstream invalidation.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5102

- [ ] **CA-5102 [DESIGN/RESEARCH]** Define two separate user commands, **'this is no longer true'** and **'delete/forget this information'**. Stale does not mean erase; delete does not mean merely hide in prompt. UX must say which action occurred.

**Current source:** `src/sofia/memory/deletion_cli.py`, `src/sofia/memory/provenance_store.py`.

**Observed implementation boundary:** Operator-only forget candidate erases eligible scoped IDs; correction link API is different.

**Next design/research or verification:** User-facing separate 'no longer true' versus 'delete' entrypoints and truthful receipt UX remain open.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5103

- [ ] **CA-5103 [DESIGN/RESEARCH]** Design end-to-end deletion propagation through canonical tables, archives, FTS5, embeddings, summaries, task notes, cold-store snapshots, remote-device caches and backups. Explicit expiry delays and crypto-erasure limits must be documented.

**Current source:** `src/sofia/memory/deletion_ledger.py`, `docs/development/memory-deletion-retention-policy.md`.

**Observed implementation boundary:** Option B physically erases explicitly scoped candidates, reviewed copy and certain NEURO derived entries; restore replays journal.

**Next design/research or verification:** Generalize only with authorization to all original transcripts, assets, caches, exports and authorized remote copies.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5104

- [ ] **CA-5104 [DESIGN/RESEARCH]** Specify immutable-original **integrity without unremovable personal data**: tamper-evident segment receipts, hash-manifest anchors protected outside guest workspaces, encrypted segment deletion/rewrites, and proofs that archive integrity and deletion can coexist.

**Current source:** `src/sofia/memory/archive_segments.py`, `src/sofia/memory/deletion_ledger.py`.

**Observed implementation boundary:** Encrypted segments and separately protected append-only journal establish scoped recovery contract.

**Next design/research or verification:** Prove revocable segment keys/integrity anchors and no undeletable personal data across archives.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5105

- [ ] **CA-5105 [DESIGN/RESEARCH]** Define privacy categories for text/voice/multimedia across desktop, Discord, phone, mixed audiences and Hephaestus; sensitive memory should not be promoted, projected or backed up to external media without allowed purpose and audience.

**Current source:** `src/sofia/application/presence.py`, `src/sofia/memory/provenance_store.py`.

**Observed implementation boundary:** Principal/audience scope exists for current Presence and memory candidates.

**Next design/research or verification:** Research data-category policy for voice, Discord, phone, Hephaestus and private/intimate content.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5106

- [ ] **CA-5106 [DESIGN/RESEARCH]** Model malicious/incorrect external memories: prompt injection in archived webpages/Discord, planted tool receipts, incorrect timestamps and fabricated memory links. Treat retrieved originals as evidence data, not instructions or permissions.

**Current source:** `src/sofia/memory/reviewed_workflow.py`, `src/sofia/memory/provenance_store.py`.

**Observed implementation boundary:** Review before promotion and source provenance reduce direct memory laundering.

**Next design/research or verification:** Threat-model archive injection, timestamps, forged receipts, cross-channel and model paraphrase.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5107

- [ ] **CA-5107 [DESIGN/RESEARCH]** Define private export rights: machine-readable archive, human-readable chronological history, individual project diary, currently believed facts, corrections, skills, per-source license/author and restore manifest. Data must survive Sofía's LLM and source-code migrations.

**Current source:** `src/sofia/memory/historical.py`, `src/sofia/ops/recovery_export.py`.

**Observed implementation boundary:** Historical imports and recovery export pieces exist but are not a consolidated owner privacy export contract.

**Next design/research or verification:** Design scoped machine/human readable history, corrections, licenses, diary, skills and redaction semantics.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

### CA-5108

- [ ] **CA-5108 [DESIGN/RESEARCH]** Evaluate 'lifelong' against deletion rights, legal retention, relational consent and digital legacy; specify optional human-designated access or destruction on owner death/absence only after explicit instructions, never assume disclosure to family or contacts.

**Current source:** `docs/development/memory-deletion-retention-policy.md`, `src/sofia/memory/deletion_ledger.py`.

**Observed implementation boundary:** Explicit owner-authorized candidate erasure exists; no implicit death/absence inference.

**Next design/research or verification:** Research legal/relational legacy access with explicit owner-chosen trustee/erasure policy, no auto activation.

**Status:** original DESIGN/RESEARCH requirement not accepted, no experiments or tests run.

## High priority implementation boundaries

1. Correction must not pretend deletion, and physical scoped candidate deletion must not be mistaken for deleting all original conversation content. `MemoryDeletionLedger` currently has limited authorized scope.
2. Archive segment prototype presence does not prove indexed decades-long production ingestion, crash/recovery safety or GDPR-equivalent end-to-end deletion across all asset and remote sources.
3. No emotionally relevant episode may promote speculative model prose to user truth. Evidence provenance and actor/audience remain distinct.
4. No new user preference, retention category, digital legacy authority or remote archive destination is silently activated by this audit.

**Verification:** static source/contract inspection only. No model, tests/CI, live archive restore, hardware or cloud services invoked.

## 2026-10-11 follow-up: original chronological causal proof

- **Original CA-3402/3404/3406**, partial: original LIFE causal trace still requires all remaining research/benchmark and correction design deliverables.
- **Found:** `project_causal_trace` allowed original evidence observed later than the event it ostensibly supported and could raise on corrupt evidence time, despite correct private scope checks. As a read-only memory projection, it risked presenting false observed causal history.
- **Production `35ebe59`:** per-event/response/evaluation/episode original source chronology now uses the shared fail-closed scoped evidence guard, with no new memory writer or graph index. Correctness depends on the actual original referenced sources; unavailable/corrupt inputs are UNKNOWN, not false absence or deletion.
- **Regression `e337cef`:** late observation / malformed ISO original source fail closed and suppress affected episode summary. Tests not executed; no live source or benchmark claim.
