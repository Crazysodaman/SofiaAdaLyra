# INTERACT I8–I16 coordinated implementation checkpoint

**Status: partial implementation on `feature/pkg-interact-shared-engine`; NOT an accepted I8–I16 release.** This document supplements [the detailed roadmap](pkg-interact-roadmap.md) and [complete embodiment/agency contract](pkg-interact-complete-embodiment-and-agency-contract.md). Sparks asked to develop I8–I16 as **one coordinated effort** rather than nine isolated planning rounds. A coherent development effort does not eliminate per-layer checks, third-party device requirements, consent/authorization or the separately approved merge gate.

## Verification ledger

- At `0a5769a`, Sparks's actual Windows PowerShell checkout fast-forwarded successfully and the four *standalone* registry, temporal, expression and initiative test modules yielded **28 passed in 3.38 seconds**. That result predates the code in this checkpoint.
- Earlier I1–I7 stop/repetition regression: **11 passed in 2.24 seconds at `52a5d44`**; the two previously documented supervised live-model reviews failed. The repairs have not received a passing new supervised real-model review.
- Local isolated development checks with simplified core/ledger test doubles passed; those are not checkout-wide, GitHub CI, Windows, integrated CLI, or full-suite results. **There is no reported Windows/CI result for the new I8–I16 integration commits.** Do not add counts from different SHAs to imply a coordinated run.

## Code now committed and its exact limits

| Slice | Implemented code | What remains unimplemented/unaccepted |
| --- | --- | --- |
| I8 | `registry.py` versioned alias resolver; `grammar.py` consults reviewed aliases in normal text. | Full locale/colloquial inventory and migration against legacy state copies, human review of ambiguities. |
| I9 | `grammar.py` recognizes reviewed single-word expanded gestures and synthetic fixture equivalents. `action_grammar.py` classifies selected whole-body actions as described vs offered; `expanded_service.py` adds live CLI projection and blocked multi-action replies. | Arbitrary compound atomic execution, long-form input, real authenticated user/avatar gestures and verified action phases. |
| I10 | `temporal.py` append-only explicit preference/boundary revisions; `source_link.py` checks saved message role/session/exact content plus tamper attestations; `preference_context.py` retrieves scoped reviewed preferences and fails closed on unverified boundary additions/removals. The expanded service performs **pre-model** stop/boundary checks and scoped preference projection. | No automatic review of a statement's meaning or cryptographic reviewer authentication. Boundary checks are not transactional with `InteractionLedger.process_text` or universal across clients; explicit revisions require a trusted caller. No DB-copy migration acceptance. |
| I11 | Existing contextual interaction prompting plus reviewed action/preference context. | Non-repetitive 20–30-turn real-model acceptance and source-linked automatic appraisals; historical live reviews failed. |
| I12 | Text and synthetic lab share expanded single-gesture semantic IDs, with no real pointer claim. | Authenticated avatar transport, screen executor and actual renderer feedback; all unavailable here. |
| I13 | `registry.py` includes laugh, cry, blush, quiet, ear/tail expression labels. `expression.py` tracks plan, silent, blocked, described and acknowledged output accurately. Action prompt permits optional expression but does not force it. | No real audio/animation adapter, playback acknowledgment, autonomous expression planner or renderer. |
| I14 | Existing evidence-linked `EmotionalJournal` now recognizes 13 additional **modeled** labels including embarrassment, humiliation and fictional sexual arousal. Append-only revision and scoped explicit preference foundation available. | No model-certified internal feeling or arousal measurement; no evidence-linked automatic learning/revision or user-facing reviewed preference editor; no guarantee of natural mixed-emotion dialogue. |
| I15 | `initiative.py` gated reciprocal offer/contact proposals; `goal_journal.py` source-backed goals, explicit goal transitions and **queue-only**, opt-in, away-signal-gated, deduplicated and rate-limited proposed messages. | Not connected to a goal-selection inference loop or real presence client. No new worker/daemon, tool permissions, outgoing messages, actual delivery, quiet-hours configuration or autonomous contact. |
| I16 | Per-session stop/replay remains authoritative for v1/expanded single gestures; new pre-model modeled boundary checks and regression cases for attested source alteration and forged boundary clearing. | No global/cross-client authenticated stop, atomic ledger boundary check, approved intimate-history retention/deletion, backup-aware migration, external kill switch, real UI/audio negative tests or full integrated acceptance. |

**Important distinctions:** classification is not approval/consent or real sensation; `described` is not rendered; an offer is not performed contact; an emotion is a fictional modeled appraisal, not a physiology sensor. Body privacy flags only manage exports. Neither time nor repeated unwanted contact creates pleasure, consent, arousal, or preference. An explicit boundary outranks preference. The live CLI uses the new `ExpandedConversationService`, but **the complete I8–I16 goal is not complete or production-ready**.

## Windows PowerShell verification, from the repo root

Exit any running Sofía CLI first. Record the branch and SHA; don't silently switch or reset branches, overwrite `state/sofia.db`, or alter its backup. PowerShell continuation backticks must be the final character on their line.

```powershell
git branch --show-current
git status --short
git pull --ff-only origin feature/pkg-interact-shared-engine
git log -1 --oneline

pytest -q -x `
  test/test_interaction_registry.py `
  test/test_interaction_temporal.py `
  test/test_interaction_expression.py `
  test/test_interaction_initiative.py `
  test/test_interaction_v2_live_grammar.py `
  test/test_interaction_v2_cross_modal.py `
  test/test_interaction_extended_emotions.py `
  test/test_interaction_source_link.py `
  test/test_interaction_action_grammar.py `
  test/test_interaction_goal_journal.py `
  test/test_interaction_preference_context.py `
  test/test_interaction_boundary_revocation.py `
  test/test_interaction_expanded_service.py `
  test/test_interaction_live_boundaries.py `
  test/test_interaction_import_order.py
```

If this fails, capture the **first actual traceback and commit SHA**, repair only its responsible layer, rerun affected and coordinated tests. Do not proceed from synthetic or historical pass counts. After these pass, run the separate I1–I7 coordinated tests from [the prior acceptance plan](pkg-interact-i5-i7-acceptance.md). Then conduct a fresh, supervised `python -m sofia` session with **separate turns** for a normal ear/head gesture, a reviewed new single gesture, an offered hug, a described hug, exact stop, attempted touch/hug during stop, exact resume, tail/chest hypothetical, and compound gesture. Audit no falsely claimed contact, natural responses without canned repetitions, no spurious physiology or animation, and serious engineering responses that stay serious.

**Only once current-revision focused and supervised live gates pass:** `pytest -q` at that exact SHA, review full PR diff, security/privacy and DB migrations on a *copy* if relevant, then obtain a separately explicit approval to merge. PR #2 must remain draft and unmerged until accepted; do not touch the independent CORE/Artemis PR #1 or RUN PR #3.

## External dependencies and safe stopping point

Actual voice laughter/crying, avatar tears and fox-ear/tail motion require a renderer and voice client capable of returning verified acknowledgments. Cross-client identity, presence, notifications, quiet hours, external screen control and real-world action require separately authenticated clients and approved grants. This branch does not invent hardware, providers, a delivery channel, subjective feelings or process activity while stopped. It never enables a worker just to make the roadmap look green.
