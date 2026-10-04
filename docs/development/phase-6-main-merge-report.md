# Merge cleanup through Phase 6 into updated main

The user authorized this merge after Phase 6, then requested a fresh main pull, avatar re-audit after external wardrobe updates, Phases 7–10 on work, and a final merge after that cleanup.

Parents before merge: main `b100848800637a8dddc8b6b0696cb6bb227990c1`; work `67e71789d86ee5dbc6e429b8996c159ae41b5e9c`.

## Conflict decisions

| File | Decision | Resolution |
|---|---|---|
| `src/sofia/avatar/authoring.py` | KEEP / SPLIT | Preserve main's newly enhanced typed garment creator/composition APIs. Remove the old body-authoring declarations; canonical fit vocabulary stays in fit.py. No frontend caller is claimed for standalone creator APIs. |
| `src/sofia/avatar/wardrobe_catalog.py` | KEEP | Preserve main's structured garment/environment/context imports and catalog; use canonical fit anchors from fit.py. |
| `test/test_avatar_authoring.py` | KEEP / DELETE | Preserve creator composition/durability and canonical-anchor checks. Keep the retired body-authoring contract cases removed; fit.py has its own tests. |
| `test/test_avatar_presentation_runtime.py` | KEEP | Preserve updated presentation expectations with EmbodimentStore and the relocated baseline path. |
| `test/test_avatar_seasonal_outfits.py` | DELETE | Preserve main's retirement of the superseded 300-outfit seasonal preset test. |
| `test/test_interaction_import_order.py` | MERGE | Preserve both branches' first-import cases, terminal ownership assertions, entrypoint identity checks and lazy application-export checks. |

All other merge changes preserve both histories. No force push or published-history rewrite is used. Current main's wardrobe planner/environment suitability, emotion precedence, catalog defaults and creator profile behavior remain covered by the merged tests.

## Verification

Compile and conflict-marker/diff checks passed. Avatar, interaction, idle-reflection, repetition/response-quality, module entrypoint and production composition gate: **840 passed**. Full suite: **3475 passed, 8 failed, 2 skipped** (66.54s). The same five unavailable-Ollama failures and three platform-assumption failures remain; no new failure was introduced by the merge.

Checkpoint: `git log -1 --format=%H -- docs/development/phase-6-main-merge-report.md` identifies the merge commit containing this report.
