# INTERACT I8–I16 coordinated implementation checkpoint

**Status: partial implementation on `feature/pkg-interact-shared-engine`; NOT an accepted I8–I16 release.** This document supplements [the detailed roadmap](pkg-interact-roadmap.md), [complete embodiment/agency contract](pkg-interact-complete-embodiment-and-agency-contract.md), and [live-quality repair record](pkg-interact-live-quality-repair.md). Sparks asked to develop I8–I16 as **one coordinated effort** rather than nine isolated planning rounds. A coherent development effort does not eliminate per-layer checks, third-party device requirements, consent/authorization or the separately approved merge gate.

## Verification ledger

- At `0a5769a`, Sparks's actual Windows PowerShell checkout fast-forwarded and four standalone registry, temporal, expression and initiative test modules yielded **28 passed in 3.38 seconds**. This result predates later integration changes.
- Earlier I1–I7 stop/repetition regression: **11 passed in 2.24 seconds at `52a5d44`**; two supervised live-model reviews failed.
- At `f3cf992`, a coordinated Windows run stopped after 112 passes on a hypothetical-prompt wording assertion. At `412dc32`, the repaired focused run passed **28 tests in 3.44 seconds** and the coordinated interaction/application run passed **264 tests in 87.92 seconds**.
- The real supervised CLI at `412dc32` **FAILED live personality, repetition, offer/description, hypothetical provenance and technical response quality**. Stop/blocked gesture/resume/compound-action *text* behavior was appropriate, but the actual ledger was not independently audited in that transcript. Automated tests did not catch the conversational failure.
- At `84429c1`, the source-backed legacy affection projection repair, revised action/personality wording, synthetic A/B probe and focused tests are **committed but not yet run on Windows, live Ollama or full pytest**. The only current-revision result is code publication, not acceptance. Do not add counts across SHAs.

## Code now committed and its exact limits

| Slice | Implemented code | What remains unimplemented/unaccepted |
| --- | --- | --- |
| I8 | `registry.py` versioned alias resolver; `grammar.py` consults reviewed aliases in normal text. | Full locale/colloquial inventory, migration against legacy state copies, human review of ambiguities. |
| I9 | `grammar.py` recognizes reviewed single-word expanded gestures and synthetic fixture equivalents. `action_grammar.py` classifies selected whole-body actions as described vs offered; `expanded_service.py` adds live CLI projection and blocked multi-action replies. | Arbitrary compound atomic execution, long-form input, authenticated user/avatar gestures and verified action phases. |
| I10 | `temporal.py` append-only explicit preference/boundary revisions; `source_link.py` checks saved message role/session/exact content plus tamper attestations; `preference_context.py` retrieves scoped reviewed preferences and fails closed on unverified boundary additions/removals. Expanded service performs pre-model stop/boundary checks and preference projection. | No automatic review of a statement's meaning or cryptographic reviewer authentication. Boundary checks are not transactional with `InteractionLedger.process_text` or universal across clients; explicit revisions require a trusted caller. No DB-copy migration acceptance. |
| I11 | Contextual prompting plus reviewed action/preference context. Candidate follow-up removes unsupported legacy auto-affection projections and supplies clearer social and technical conversational framing. | Real 20–30-turn non-repetitive model acceptance remains **FAILED/PENDING**; automatic source-linked appraisals are absent. New repair not verified. |
| I12 | Text and synthetic lab share expanded single-gesture semantic IDs, without a real pointer claim. | Authenticated avatar transport, screen executor and actual renderer feedback unavailable. |
| I13 | `registry.py` includes laugh, cry, blush, quiet, ear/tail expression labels. `expression.py` tracks planned/silent/blocked/described and acknowledged output. Optional expression, not mandatory. | No audio/animation adapter, playback acknowledgment, autonomous expression planner or renderer. |
| I14 | Existing evidence-linked `EmotionalJournal` recognizes 13 additional modeled labels. Append-only revision and scoped explicit preference foundation available. Live service now stops auto-labeling user pats/praise as Sofía's emotions; historical auto-labels are excluded from model context only. | No automatic evidence-reviewed learning or preference editor; no claim of subjective feelings or natural mixed-emotion dialogue acceptance. |
| I15 | `initiative.py` gated reciprocal proposals; `goal_journal.py` source-backed goals, explicit transitions and queue-only, opt-in, away-signal-gated, deduplicated and rate-limited proposals. | No goal-selection inference loop, real presence client, worker/daemon, outgoing messages, quiet-hours configuration or autonomous contact. |
| I16 | Per-session stop/replay remains authoritative for reviewed single gestures, pre-model modeled boundary checks and tamper/forged-clearing regressions. | No authenticated global/cross-client stop, atomic boundary check, approved intimate-history retention/deletion, backup-aware migration, external kill switch, real UI/audio negative tests or full integrated acceptance. |

**Important distinctions:** classification is not approval/consent or real sensation; `described` is not rendered; an offer is not performed contact; an emotion is a fictional modeled appraisal, not a physiology sensor. Body privacy flags manage exports only. Neither time nor repeated unwanted contact creates pleasure, consent, arousal or preference. An explicit boundary outranks preference. The CLI uses `ExpandedConversationService`, but the complete I8–I16 goal is not production-ready.

## Windows PowerShell verification, from the repo root

Exit any running Sofía CLI first. Record branch/SHA; do not reset branches or overwrite `state/sofia.db`, its backup, or the user's local test edit. PowerShell continuation backticks must be the final character on their line.

```powershell
git branch --show-current
git status --short
git pull --ff-only origin feature/pkg-interact-shared-engine
git log -1 --oneline

python -m pytest -q -x `
  test/test_interaction_context_hygiene.py `
  test/test_interaction_ab_probe.py `
  test/test_interaction_expanded_service.py `
  test/test_interaction_live_discussion.py `
  test/test_interaction_live_stop_repetition.py

$tests = @(Get-ChildItem .\test -Filter 'test_interaction_*.py' -File | ForEach-Object { $_.FullName })
python -m pytest -q -x @tests .\test\test_affection_cue_phrasings.py .\test\test_application.py
```

If a focused check fails, capture the first traceback and SHA; repair only its responsible layer and rerun. If focused and coordinated tests pass, `python -m sofia.interaction.ab_probe` is an optional **synthetic** same-model comparison with no production DB access. Then conduct a new supervised `python -m sofia` session, with separate turns for ear/hand pat, offered/described hug, stop, stopped touch/hug, resume, repeated head pat, tail/chest hypothetical, compound gesture and Windows service diagnosis. Audit no false contact, natural varied responses, no invented history/physiology/animation, and serious technical troubleshooting. A normal live session will write conversation state to the existing DB; do not reset it to make the result look better.

**Only once current-revision focused, coordinated and supervised live gates pass:** run `pytest -q` at that exact SHA, review full PR diff, security/privacy and migrations on a *copy* if relevant, and obtain separately explicit approval to merge. PR #2 stays draft/unmerged; do not touch independent CORE/Artemis PR #1 or RUN PR #3.

## External dependencies and safe stopping point

Actual voice laughter/crying, avatar tears and fox-ear/tail motion require a renderer and voice client with verified acknowledgments. Cross-client identity, presence, notifications, quiet hours, screen control and real-world actions require authenticated clients and approved grants. No hardware, delivery channel, subjective feeling, or activity while the process is stopped is invented. No worker is enabled to improve roadmap optics.
