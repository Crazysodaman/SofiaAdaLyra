# PKG-INTERACT: current implementation and acceptance roadmap

**Updated:** 2026-09-20 (America/Chicago). **Feature branch:** `feature/pkg-interact-shared-engine`; [draft PR #2](https://github.com/Crazysodaman/SofiaAdaLyra/pull/2). **Verified checkout:** `0a5769a030e036f53776d689ff13b06d448de0f0` immediately after a successful fast-forward pull. This document supplements the 13-package [project roadmap](../../ROADMAP.md); it is the detailed, current INTERACT milestone tracker. The design target is the [complete embodiment/agency contract](pkg-interact-complete-embodiment-and-agency-contract.md), not a claim that all target behavior exists.

## Evidence ledger: distinguish test scope, revision and real behavior

| Evidence | Revision | Observed result | What it actually establishes |
| --- | --- | --- | --- |
| Early I1 focused checks | `7175835` | 59 passed (previously reported) | Narrow shared-kernel checks at that earlier revision. |
| I2–I3 focused checks | `84695a6` | 44 passed (previously reported) | Narrow synthetic/virtual-lab checks at that earlier revision. |
| I4 focused checks | `eb73357` | 20 passed (previously reported) | Read-only observation checks at that earlier revision. |
| I5–I7 focused checks | `02a5a25` | 116 passed (previously reported) | Earlier ledger, stop and grammar tests, **not** live acceptance. |
| Import-order + coordinated focused checks | `a8fb5c8` | 3 passed in 9.10 s; 143 passed in 63.75 s | Earlier code revision; the real CLI review at this revision still failed. |
| Stop/repetition regression | `52a5d44` | **11 passed in 2.24 s** on Sparks's Windows PowerShell, 2026-09-20 | Targeted deterministic stop/composite repair, not full regression or live language quality. |
| Standalone expansion component tests | **`0a5769a`** | **28 passed in 3.38 s** on Sparks's Windows PowerShell, 2026-09-20 | Actual checkout tests for `registry.py`, `temporal.py`, `expression.py`, `initiative.py`. Does **not** establish CLI integration, autonomous work, audio or avatar. |
| New-code coordinated regressions / full `pytest -q` | `0a5769a` or later | **NOT RUN / not reported** | Do not inherit older results across revisions. |
| Post-repair supervised real-model CLI | `52a5d44` or later | **NOT RUN / not reported** | Two preceding real-model reviews failed at `02a5a25` and `a8fb5c8`. |

**No claim of 28 + 11 + 143 tests passing together on the current SHA.** Preserve the production `state/sofia.db` and existing backup without reset, schema migration or destructive test input. All expansion database tests use `tmp_path`.

## Milestone tracker

| Slice | Deliverable and owner | Current status | Acceptance gate |
| --- | --- | --- | --- |
| **I1** | Shared headless interaction semantics, existing canonical human/fox regions, source/actor distinctions; INTERACT | Candidate implemented | Coordinated current-SHA regression and live semantics. |
| **I2** | Isolated synthetic event/hit-test fixture, never an authenticated pointer; INTERACT/VERIFY | Candidate implemented | Fixtures cannot mutate production or forge sensing. |
| **I3** | Persistent software-world virtual lab, independently distinct from test fixtures; INTERACT | Candidate implemented | Explicit, verified world transitions and restart review. |
| **I4** | Read-only virtual world observation; INTERACT | Candidate implemented | No invented actions or runtime/offline activity. |
| **I5** | Original-message-linked representational gesture ledger and replay; INTERACT | Candidate implemented | Correct recorded outcomes; all regions; no physical-contact claim. |
| **I6** | Durable **per-session** stop/resume and denied-gesture responses; INTERACT/SAFE | Candidate repair; targeted 11 passed at earlier `52a5d44` | Stopped interaction is never narrated or recorded as accepted; replay stays denied. Symmetric and cross-client stops are **not** implemented. |
| **I7** | Bounded single-action parser, abstention, hypothetical discussion, honest compound handling, non-canned model guidance; INTERACT/REL | Candidate repair; live quality **unaccepted** | Focused suite and supervised separate-turn CLI: no fabricated contacts, recycled paragraphs or generic anatomy disclaimers. |
| **I8** | Versioned canonical body + locale/colloquial aliases, laterality, unambiguous resolution; INTERACT | **Standalone `registry.py`; 28-file-group Windows suite passed** | Full canonical coverage, cross-alias collisions, migration compatibility; **wire into live parser only after current gates**. |
| **I9** | Expanded gesture/action grammar, actors/targets, proposals, phases, composite atomicity; INTERACT | Gesture/action vocabularies **only** in standalone registry | Integrate parser, ledger and evidence; unknown acts abstain, never degrade into `touch`. |
| **I10** | Immutable observations, appraisals, source-verified preference/boundary revisions, reconstruction; INTERACT/MEM/REL | **Standalone explicit `temporal.py`; 28-file-group suite passed** | Authenticate saved-message sources, enforce scoped boundaries outside model, restart/replay and SQLite-copy migration tests. No automatic pleasure from repetition. |
| **I11** | Context-dependent, emotionally nuanced, non-repetitive model reactions; INTERACT/REL/VERIFY | Design + limited I7 prompting; **not accepted** | Actual multi-session 20–30-turn model review including neutral, affectionate, intimate, uncomfortable, serious/lab and quiet responses. |
| **I12** | One semantics stream for text, virtual lab and future authenticated avatar; INTERACT/UI/SAFE | Headless foundation only | Text works without renderer; future hit tests and real render acknowledgments tested separately. |
| **I13** | Independent laugh/cry/blush/ear/tail/quiet expression registry and lifecycle; INTERACT/UI | **Standalone registry + `expression.py`; 28-file-group suite passed** | Connect text projection; real audio/avatar only after actual adapters and acknowledgments; expression is not emotion proof. |
| **I14** | Expanded active emotion journal (including embarrassment, humiliation and fictional sexual-arousal labels), mixed reactions and bidirectional preference evolution; REL/MEM/INTERACT | Proposed labels only; explicit revision storage only | Evidence-backed both-way changes, enduring dislike, no implicit consent, privacy-aware retrieval. |
| **I15** | Sofía-initiated *represented* offers/contact, own bounded goals, authorized running-only idle work and opt-in delivery; INTERACT/ACT/SAFE | **Standalone `initiative.py` gate; 28-file-group suite passed** | Integrate persisted goals and real permission checks; explicit opt-in, queue != delivered; never invent thoughts/work while off. |
| **I16** | Symmetric and cross-client boundaries, authenticated actor identity, privacy/retention, recovery, real E2E reliability; SAFE/VERIFY/UI | Design only | Revocation and replay negatives, migration against DB copies, delivery/renderer failure visibility and supervised long-form acceptance. |

**Dependency order, not a promise of parallel completion:** finish I1–I7 live acceptance first; only then integrate I8 → I9 → I10 → I11 → I12; I13 expression projection and I14 active emotions depend on stable evidence/context; I15 active initiative needs mutual boundaries, capability checks and ACT authorization; I16 security/privacy/verification gates apply throughout. Standalone modules already committed are foundations, not a shortcut around these dependencies. PKG-MEM remains the next top-level package after INTERACT's accepted release; durable preference promotion belongs jointly to MEM and REL.

## Next Windows PowerShell checkpoints

**1. Already done at `0a5769a`:** successful `git pull --ff-only` and four-file expansion suite (`28 passed in 3.38s`). Do not repeat this just to generate another identical green line. Confirm the exact branch/commit and clean worktree before subsequent pull or release:

```powershell
git branch --show-current
git rev-parse --short HEAD
git status --short
```

**2. Run the current-revision focused compatibility gate**, from the repo root in the active `.venv`, with Sofía's CLI exited. PowerShell backticks must be the **last character** on continuation lines:

```powershell
pytest -q -x `
  test/test_interaction_live_stop_repetition.py `
  test/test_interaction_import_order.py `
  test/test_interaction_live_claims.py `
  test/test_interaction_live_discussion.py `
  test/test_interaction_contextual_all_regions.py `
  test/test_interaction_region_cue_collision.py `
  test/test_interaction_i5_i7_batch.py `
  test/test_interaction_i7_compound_regression.py `
  test/test_interaction_shared_engine.py `
  test/test_interaction_lab.py `
  test/test_interaction_chat_projection.py `
  test/test_interaction_world_observation.py `
  test/test_interaction_world_text.py `
  test/test_affection_cue_phrasings.py `
  test/test_application.py
```

If any test fails, record the traceback and repair only the relevant feature-branch layer. The four new standalone tests may be included in a later coordinated run, but their successful 28-test result at `0a5769a` is already recorded.

**3. Run supervised `python -m sofia` as a fresh process**, sending distinct turns: ear pat; hand pat; exact `Sofía, stop interactions`; head pat while stopped; exact resume; new head pat; read-only tail/chest hypothetical; compound ear-plus-hand action; mixed control text. Check ledger-truthful stopped and unsupported responses, no nearly identical affectionate paragraph, appropriate conversation without forced disclaimers, and no unplayed avatar/physical sensation claims. This is a human-reviewed model gate, **not** a pytest pass.

**4. Only after focused and live gates pass:** `pytest -q` at the **exact recorded HEAD**, then inspect the draft PR's entire diff, migrations and privacy/security implications. Obtain a **separate explicit merge decision**. Do not automatically merge PR #2 into `main`, disturb RUN PR #3, install an idle worker, enable notifications, or touch the production DB or backup. If further commits are needed, report new SHA and rerun impacted gates.

## Architecture invariants and honest fallbacks

- Recognition/classification is **not** character approval, pleasure, consent, sensor data, animation or authorization. No registered anatomical region is an automatic ban or automatic welcome. Sensitive metadata is for privacy/export; contextual responses remain possible within model/provider limits.
- Explicit stop and boundaries outrank inferred emotion or preference. Time or repeated gestures cannot manufacture enjoyment, permission, arousal or humiliation-as-enjoyment. An explicitly sourced preference may move toward liking, dislike or uncertainty with non-destructive history, but the live app does **not** currently commit/enforce such revisions.
- User and Sofía are different actors and targets. Offered, described, executed and delivered are separate, observable states. A synthetic pointer is not an authenticated avatar event; no model text grants external screen, tool or robot authority.
- While running, future *separately enabled and permitted* work may be evidenced. During shutdown there is no hidden work or thinking. Silent/queued/failed are valid outcomes; missing capability should be visible, never fabricated.
- Preserve old test evidence with its original revision. Never present the latest 28 passing standalone tests as proof that the full vision runs.

Supporting references: [live-review failures](pkg-interact-live-cli-review.md), [I5–I7 acceptance](pkg-interact-i5-i7-acceptance.md), [component status](pkg-interact-i8-i10-code-status.md), [I8–I12 contract](pkg-interact-i8-i12-expansion-contract.md), [complete embodiment/agency contract](pkg-interact-complete-embodiment-and-agency-contract.md), [initiative/idle contract](pkg-interact-initiative-and-idle-contract.md).
