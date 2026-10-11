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


## Production source repair wave through e34fbdb, October 11, 2026

The user authorized continued production coding on `main`, deferred all test
execution until the coding campaign's final gate, and explicitly withheld
authorization for live host changes. The user has approved **individual
device-enrollment credentials with re-pairing**, but has **not selected the
canonical SQLite writer machine**.

Actual source commits (all pushed directly to main, [skip ci]):
- `ed72d3a`: recertify phone token at desktop owner-thread dispatch and
  before HTTP reply; revoked requests in queue no longer execute.
- `1eaf142`: Android Keystore-encrypted durable single-outstanding-turn
  journal preserves stable text/nonce across process death; no auto resend.
- `315ef68`: LIFE journal observes original RUN event IDs for completed,
  failed, blocked, cancelled, uncertain and awaiting approval, idempotently.
- `ba9c6d9`: deny unauthorized mobile notification title and original ACT
  source ID exposure; stable opaque handles remain acknowledged by host.
- `cfb6440`: sensor/gateway/credential/notification SQLite connections
  require existing canonical mode=rw DB; no new state-home creation.
- `358ae1d`: mobile sensor SQLite read/write/initialization connections
  now deterministically close, reducing Windows handle leak risk.
- `e34fbdb`: mobile ENVIRONMENT projection only admits current active
  paired-device sensor rows; revocation blocks new writes and current recall.

Source path audit against the complete latest GitHub tree found **zero missing
code paths among references in the 700-task ledger**. Conservative states:
**6 coded/unverified, 44 partially wired, 650 not individually assessed,
0 production-accepted.** The status counts measure audit coverage, not
total coding completeness. The original V18 master task wording/IDs remain
unchanged. Remaining Phase 03 fenced cutover, Phase 05 full cross-channel
causal consistency, independent host/phone pairing exercise, CI, Windows,
Android and Fleet acceptance remain explicitly open.

## Partial-first coding wave through 2fe9c12

All original 44 partially wired V18 IDs were crosswalked to the byte-exact
master task statements and previously recorded source paths, without
relabeling any as accepted. Eight have **new source-coded repairs** this
wave: CA-2216 LIFE diagnostics (`845694f`), CA-2304 unique test
denominators (`7b1c1d8`), CA-4104 generation-bound mobile audiences
(`493a4f6`), CA-6302 source-timestamped mobile admission order
(`1be739c`), CA-6807 local filesystem destination preflight (`248dcb9`),
CA-2205 queued deadline settlement even when busy (`da78b53`), and
CA-6304/CA-6306 truthful typed Android reconnect conflict handling
(`2fe9c12`). Each has production source and unexecuted regression files;
complete acceptance remains open. Source includes no hidden shadow
transport, no second scheduler, and no automatic DB relocation.

The 44-item coding queue is
`docs/development/v18-partial-first-coding-2026-10-10.md` and the original
source-evidence ledger is `docs/development/v18-task-evidence.json`.
Existing package BODY ownership is already coded; its historical red
CI test report still needs actual rerun and evidence. Source state totals
remain **6 code-present/unverified, 44 partial, 650 individually unaudited,
0 production accepted**. More code is still needed on the remaining
partial items; this is not a declaration that all 44 were completed.

## Further partial-first source fixes through a34e1eb

Seven more original partially wired tasks received committed production source
changes after the initial eight-task phase: CA-5603 (`720d416`),
CA-4105 (`2f064ae`), CA-5502 (`5688a35`), CA-6608
(`8f72fb4`), CA-3005 (`7390eb3`), CA-6303 (`c387d67`)
and CA-3014 (`a34e1eb`). Evidence paths and SHAs are attached
to their exact CA records in `v18-task-evidence.json`.

**15 of 44 original partial IDs now have new source-coded repair evidence;
29 have no new code in this campaign.** These are not finished-task
percentages and none has passed the deferred CI/Windows/Android/Fleet
acceptance campaign. Overall source classifications remain
6 code-present/unverified, 44 partial, 650 unassessed, zero accepted.
The single-writer host remains undecided and no live host was changed.

## Partial-first source coding after original 15-task checkpoint

Further production source changes:
- `80bd5cb` **CA-1904**: one-use SAFE execution fingerprint and
  owner attribution validation in the shared approval verifier; actual
  independent human authentication still outstanding.
- `dc2e0b8` **CA-6405**: typed cross-modal provenance/expiration/privacy
  receipt stored atomically by the existing Presence owner.
- `a52d2be` **CA-5307**: authenticated mobile current session/audience
  shown on Android with explicit no-cross-channel-mirroring warning.
- `2c3b27b` **CA-6804**: SAFE approval connections reject creation of a
  fresh state database after missing/unmounted canonical state.

The original V18 700-ID ledger therefore records **19** partially wired
tasks with new source-coded repairs, **25** with no new repair this
campaign, **44 still partial**, **6 coded/unverified**, **650 individually
unaudited**, and **0 production accepted**. The exact GitHub source
reference audit found zero missing code paths. All newly authored
tests remain unexecuted and no host has been touched.

## Phase 03 source-safety continuation on main, 2026-10-11

The 700 original CA checklist lines remain unchanged. This review located an
additional **production defect**, not a new authority system: SQLite stores
that checked for `sofia.db` only in their constructors could still recreate
a missing canonical database on their subsequent default-create connections.

Source commits: `d4576b9` LIFE, `31f29e7` lifelong Main, `a30e27f`
GOALS evidence, `b77bac1` Presence observations/outreach; authored
regression cases `9639985` corrected at `c45289a`. Source report:
`docs/development/phase03-canonical-state-no-resurrection-2026-10-11.md`.
They now require an existing non-symlink canonical file and use SQLite
URI `mode=rw` (GOALS index remains read-only) at these selected paths.
All these source changes are **not tested or production accepted**.

**CA-6804, CA-5201, CA-6101 remain partial**: this reduces accidental
resurrection only at inspected boundaries; audit the other SQLite writers,
bootstrap, epoch/identity validation, owned-writer fencing and complete
restore before claiming a safe canonical-state migration. In particular,
`ConversationStore.open()` still permits first-install seeding and needs a
separate post-start state-loss review, not an unreviewed global change.
Neither Venus nor Artemis has been chosen as the write host. No service,
database, mobile device, model or Fleet node has been modified live.

The ledger's **6 coded-unverified / 44 partially wired / 650 unassessed /
0 accepted** counts are retained as conservative audited statuses. Newly
committed safety code does not silently close an entire multi-criterion
CA task or provide the missing exact-SHA CI and host acceptance receipts.
