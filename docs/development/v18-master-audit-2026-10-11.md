# V18 master checklist: GitHub source reconciliation (2026-10-11)

**Authoritative task source:** `docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md`  
**Original file SHA-256:** `08c773e5d8080c2d5606e0a31459e11f78339cbfee069b00ce912b63c59128dc`  
**Original Git blob SHA-1:** `9ea103b551b1e22ce7230202fdcc762eac63f050`  
**Reviewed Git `main` SHA:** `ddab92447ce38a6f3c0bd8f173c7d8a7e7fd51cb`  
**Review method:** source/paths and historical Git commits, no tests or real-host exercises.

The uploaded V18 master is preserved **byte-for-byte**. It is the task inventory:
700 unique `CA-` IDs, grouped into 69 original topics and 17 execution-priority
phases. Its opening `DESIGN ... NO CODING AUTHORIZED` notice describes the
historical design-only snapshot at `e85c52f0`, and remains unedited for
provenance; the user's more recent explicit instructions authorize coding.
Do not silently change the original CA wording, reorder IDs, remove design
tasks, or convert original checkbox state into an implementation claim.

## Exact original inventory

| Phase | Area | Tasks |
| --- | --- | ---: |
| 00 | Architecture and source-of-truth freeze | 65 |
| 01 | CI/release/live acceptance | 66 |
| 02 | SAFE/operator authority | 30 |
| 03 | Canonical state migration/recovery | 46 |
| 04 | Offline use/survival | 22 |
| 05 | Lifelong Main | 41 |
| 06 | Memory systems | 73 |
| 07 | Archive/forgetting | 26 |
| 08 | Emotion/personality/presence | 56 |
| 09 | LIFE/creativity/goals | 66 |
| 10 | Tools/skills/robotics | 27 |
| 11 | Resource/model selection | 49 |
| 12 | Screen vision | 24 |
| 13 | Hephaestus/digital twin | 63 |
| 14 | Model training | 12 |
| 15 | NEURO/connectome | 22 |
| 16 | Consciousness research | 12 |
| **Total** | **69 original groups** | **700** |

## What this first source-level pass actually established

`docs/development/v18-task-evidence.json` now has **exactly one
non-authoritative evidence entry per original CA ID**; it never changes the
source checklist. The classifications at reviewed SHA:

| State | Tasks | Interpretation |
| --- | ---: | --- |
| `code_present_unverified` | 5 | Source implementation identified; full user task and acceptance remain unproved |
| `partial_wiring` | 17 | Production source observed, but one or more task requirements are missing |
| `unassessed` | 678 | **Not individually audited yet**, not evidence that code is absent |
| `accepted` | 0 | No exact test+live receipt has been recorded for the current reviewed revision |

Known coded but not accepted: CA-2201 (deterministic objective validation),
CA-3001 (Project Forge Windows path mapping), CA-3003 (external clean release
source), CA-103 (recurring LIFE finished-job inspection), and CA-111
(real linked artifact/checker path). For each, see exact source_paths and
commit in the JSON ledger. They remain **unverified**, not "done".

Known partial: CA-3005 (Windows SQLite cleanup not proven globally),
CA-3006 (BODY tests now mapped, but CI nonempty gate proof missing),
CA-104/CA-112 (host technical judgment without complete subjectively
reviewed critique), CA-105/106/110/113/2205/3014 (LIFE policy, all-state
settlement, milestones, feedback), CA-2204 (non-transactional work submission
edges), CA-101 (experience-admission), CA-4109/5502/6302 (cross-device Main,
migration/offline ordering), CA-5603 (remaining O(N) historical reads),
CA-6608 (model promotion only prepared). These are not blanket statements
about the 678 unassessed tasks.

## Production CI integrity contract

The existing `sofia.verify.gate` now runs
`python -m sofia.verify.v18_roadmap`. This pure, read-only gate checks
the byte-exact original source, all IDs with correct topic/phase/line,
source path existence for coded claims, non-duplicated entries, revision
format and evidence-only acceptance requirements. It returns failure on
missing, duplicated or silently accepted tasks. This is a **traceability
check**, not an autonomously trusted grading oracle or substitute for CI.

The two historical V18 release defects CA-3003 and CA-3006 were already
source-repaired at current `main`: checkout-external release archive, and
the explicit BODY filename mapping. Their **CI rerun and host acceptance
remain open**. Do not repeat prior repair code merely because the original
V18 document describes an older SHA.

## Next highest-risk work in dependency order

1. Phase 01: exact-SHA CI package/release proof, Windows lock diagnosis,
   nonempty marker tests, source versus installed-wheel provenance.
2. Phase 02/03: protected-authority boundaries, durable fail-closed state
   relocation, source-owner fencing, full state bundle backup and recovery.
3. Phase 04/05: offline canonical message acceptance and full authenticated
   Main routing, not just the existing Android read-only history projection.
4. Phase 06/07: indexed bounded historical retrieval and correction/erasure
   propagation across cold archives, clients and replicas.
5. Phase 09: transactional LIFE work reservation and receipts, independent
   critique/revision policy, milestones, and experience-to-interest loop.
6. Later phases: exact-grant model role switching/rollback, consented visual
   capture, approved Hephaestus guest, experimental adaptation and
   falsifiable NEURO/consciousness research.

### Acceptance policy

`code_present_unverified` never means complete or production approved.
Only dated, exact-commit source, focused/full tests and appropriate live-host
evidence can change a task to `accepted`. No CI, Venus, Artemis, Gaia or
Fleet test was executed in this audit. User's earlier **code first, tests
at the end** instruction is still observed.
