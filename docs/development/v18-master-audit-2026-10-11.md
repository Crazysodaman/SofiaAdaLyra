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

## Continued source reconciliation at bb116083, 2026-10-11

This audit revision preserves the original 700 CA requirements and replaces
the prior 5/17/678 reviewed subcounts with **6 code-present/unverified,
23 partially wired, 671 not individually assessed, 0 accepted**. This is
NOT a claim that only six tasks contain code; it means six full code paths
have individually traced source ownership, while 671 still need inspection.

- **Phase 01:** CA-3003 repair now includes exact installed-wheel checkout
  root, verified Git HEAD provenance and CI `GITHUB_WORKSPACE` binding.
  CA-3004 remains partial pending actual package/source parity evidence.
  CA-2304 has real collection proof code and workflow bindings but requires
  an executed exact-head 22-package CI run.
- **Phase 01 / 09:** CA-2204 now has transactional RUN enqueue, LIFE one-use
  authorization and project link on the same SQLite connection. On any
  provisioning exception the RUN job, event and grant roll back together.
  Concurrent pending work plus blocked/uncertain prior outcomes are denied;
  source regression contracts are authored but not run. Broader CA-2205
  all-status recovery/reconciliation remains partial.
- **Phase 02 / 05:** CA-1904 is partially wired at the mobile private-chat
  boundary: the durable host SAFE grant is rechecked immediately before
  private dispatch, matching Main private-history authorization. CA-4107,
  CA-5304, CA-5503 and CA-4110 get only partial evidence from authenticated
  mobile audience isolation and serialized gateway turns. The current
  shared-bearer pairing model still lacks independent per-device credentials,
  and cross-transport offline causal ordering/idempotency remain unimplemented
  at a provable production level.
- **Android:** Network calls execute on `Dispatchers.IO`; Compose observable
  state updates run on the ViewModel UI coroutine. Ambiguous sends restore the
  draft and do not automatically retransmit.

The CI, Windows, Android-build and Fleet tests remain deliberately deferred,
so no CA ID was moved to `accepted`. Any subsequent phase-completion report
must cite the exact Git commit, source code, executing test/live receipt and
all remaining CA requirements before describing the whole phase as done.

## Source audit continuation: 2026-10-11, through main 1805a8a

The exact 700-task evidence ledger was reconciled against the three newest
production commits: `9c8e8b1` (request-id mobile at-most-once receipts),
`caf2949` (session audience binding and first-writer-wins mappings), and
`1805a8a` (protected seed no-clobber publication).

**Source states:** 6 code-present/unverified; 34 partially wired;
660 not yet individually audited; **0 accepted**. These are evidence
classifications, not implementation percentages. Current code paths now
support partial findings for stable CA identifiers covering mobile
request/event identity, cross-device delivery, audience immutability,
reconnect conflict handling, graceful degraded delivery and protection
of the canonical state files against concurrent startup overwrites.

**Boundaries remaining:**
- The current global mobile bearer token is shared between phones. The
  client-claimed `device_id` is not an independently enrolled credential.
  Device impersonation/revocation therefore remains an unresolved Phase 05
  threat-model and implementation task. Rollout needs an operator-approved
  pairing/migration policy.
- A durable mobile `request_id` establishes at-most-once dispatch, not
  exactly-once conversation acceptance plus external effects. Interrupted
  turns are explicitly uncertain and must not be auto-executed.
- Protected file seeding is now atomic create-if-absent, but cross-host
  state relocation still requires an independently privileged actual
  fencing/cutover controller; the existing staging primitives must not
  be promoted by model text.
- No Android build, GitHub CI run, Windows production proof or Fleet host
  test was executed. Per earlier instruction testing remains postponed.

## Source audit continuation through a7de797, October 11, 2026

The release gate at parent `93614b6` could run pytest with `src/`
added to the source import path. A wheel package check under that policy
could test the checkout rather than the artifact that would ship. Commit
`a7de797` corrects that in installed-wheel-only mode: isolated venv
origin check, pytest source-path override, conftest runtime assertion and
GitHub release workflow binding, without changing normal editable tests.
This adds source evidence to CA-3004 and CA-2302. Both remain **partial**
until independently confirmed CI evidence and installed-wheel smoke checks.

After the update the ledger classifies **6**
source-coded/unverified, **35** partially wired,
**659** not individually reviewed, **0** accepted. These
are conservative source-audit states, not progress through production
acceptance or a percentage of remaining implementation.


## Owner-approved pairing decision and audited production code through e3b92c2

The owner intentionally **did not select Venus or Artemis** as the future
canonical SQLite writer. Production code must not infer one from current host
configuration, the Fleet canary, or a copied database. No live cutover was
performed.

The owner **approved individual mobile device credentials and accepted
re-pairing**. Commit `f06224c` replaces the shared bearer token with
per-device `sm1_` credentials. One current SHA-256 verifier per enrolled device
is stored in the existing canonical `sofia.db` with rotation and revocation
audit events. The local operator-only CLI issues each secret once; remote
clients cannot enroll. Every server request verifies the bearer, resolves
its recorded device, and rejects a mismatched JSON device ID. Android uses
existing Keystore-backed settings and shows its device ID for enrollment.
The ACT channel reports readiness only with at least one active enrollment.

Commit `e961de6` repairs a pre-existing startup failure: desktop worker's
mobile HTTP proxy lacked required `main_history`. It now forwards via the
canonical application thread. Commit `e3b92c2` closes a notification leak
where only the lock-screen preview was redacted yet full notification
`content` traveled to Android; both fields now follow the host-approved
external delivery policy. The Android client clears previous unopened
notifications when switching privacy or pairing contexts. The stable
operator command is `python -m sofia.mobile`.

The 700 original CA IDs remain unchanged. Individually inspected source
states now count **6 coded but unverified, 39 partially wired, 655 not
individually audited, 0 accepted**. Phase 02/05 pairing is source-coded
but complete multi-surface identity linking, offline synchronization and
actual Android/Windows evidence remain open. No full phase was declared
finished, no tests executed, and no live machine was touched.
