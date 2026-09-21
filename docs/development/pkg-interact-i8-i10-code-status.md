# INTERACT expansion: implemented components and integration gates

**Status: optional, standalone components, not live Sofía behavior.** These modules have no import-time database writes, model calls, daemon, tool access, notification dispatch or active renderer. They are not wired into the CLI parser, emotion journal, interaction guard, goal selector or any device. No `main` merge or production `state/sofia.db`/backup modifications were made. The I1–I7 live-review and full-suite/merge gates remain in effect.

## New code on `feature/pkg-interact-shared-engine`

- **I8 vocabulary:** `src/sofia/interaction/registry.py` constructs `InteractionCatalog` from the existing engine's canonical region IDs. It resolves complete anatomical aliases with `resolved`/`ambiguous`/`unknown` outcomes and separate gesture, action and expression namespaces. Proposed `EMOTION_EXTENSIONS` are **not yet entries in the active personality journal**. The existing v1 parser does not consume v2 aliases/verbs yet.
- **I10 revisions:** `src/sofia/interaction/temporal.py` provides an explicitly constructed, append-only SQLite `InteractionStateJournal(path, catalog)` for source-ID-linked, explicit subject preferences and boundary revisions. The same revision ID replays idempotently; stale revision lineage is rejected. No repeated touch automatically changes a preference. `boundary_active` is **not connected to the live guard**. Callers supply source IDs and must independently verify them against saved messages before production integration.
- **I13 expression lifecycle:** `src/sofia/interaction/expression.py` plans laugh/cry/body expression IDs, exposes blocked, silent and unsupported states, and distinguishes a saved text-description receipt from a voice/avatar adapter's actual playback acknowledgment. Its `adapter_verified` parameter is a caller assertion, not authentication by this module; no audio/animation exists here.
- **I15 reciprocal proposal gate:** `src/sofia/interaction/initiative.py` separates Sofía's contact *offer* from a proposed gesture, demands an explicit per-event permission source before describing contact, rechecks caller-supplied stop/boundary readings, and handles decline/cancel/expiry. The gate is pure and cannot independently authenticate permission, read the ledger or send messages. No autonomous thinking, scheduler, physical gesture or idle work is running.
- **Tests:** `test/test_interaction_registry.py`, `test/test_interaction_temporal.py`, `test/test_interaction_expression.py`, `test/test_interaction_initiative.py`; SQLite tests use only `tmp_path`. Local isolated checks of analogous component code passed, but no user Windows, GitHub-checkout, full-suite or live-model test has been reported for these commits.

## Required verification on the user's Windows checkout

After checking Sofía is exited and the feature branch has no local source edits, pull and run:

```powershell
git pull --ff-only origin feature/pkg-interact-shared-engine
pytest -q -x test/test_interaction_registry.py test/test_interaction_temporal.py test/test_interaction_expression.py test/test_interaction_initiative.py
pytest -q -x test/test_interaction_live_stop_repetition.py test/test_interaction_contextual_all_regions.py test/test_interaction_import_order.py
```

Repair any failure on this feature branch before continuing. Then follow the coordinated I1–I7 acceptance suite and supervised real-model review. Never substitute synthetic local checks for that process or point a test at production SQLite.

## Still missing before the user's full vision runs

A verified saved-message-to-journal commit pipeline; active v2 grammar, actor/target and multi-action handling; real emotion appraisal and bidirectional preference learning based on evidence; binding explicit boundaries and symmetric stop to every app entry point; natural, nonrepetitive reaction generation; persona goals and an opt-in running-only idle worker; secure outbound delivery and quiet hours; actual voice/avatar renderer and acknowledgments; cross-client authenticated stop, privacy/retention, migration and end-to-end tests. None is implied by having a vocabulary or transition class.
