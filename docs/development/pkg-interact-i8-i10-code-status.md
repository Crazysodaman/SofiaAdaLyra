# INTERACT expansion implementation checkpoint: catalog and temporal journal

**Status: optional components added on `feature/pkg-interact-shared-engine`; not integrated into Sofía's live CLI, parser, personality journal, renderer, or idle worker.** No `main` merge, migration of production `state/sofia.db`, backup rewrite, timer, autonomous tool access or notifications. I1–I7 supervised live acceptance and the full-suite/merge gates still apply.

## Added code

- `src/sofia/interaction/registry.py`: `InteractionCatalog` constructed from the v1 engine's canonical region IDs, normalized whole-name aliases, explicit ambiguous/unknown outcomes, bilateral fallbacks, and distinct reviewed gesture, action, and expression namespaces. `EMOTION_EXTENSIONS` are **proposed IDs only**, not registered in the currently active emotion journal. The v1 parser and `GESTURES` do not consume these additions yet.
- `src/sofia/interaction/temporal.py`: explicitly constructed `InteractionStateJournal(path, catalog)` with append-only, source-linked preference and boundary revisions, optimistic prior-ID checks and idempotent replay. `record_preference` accepts only an explicitly sourced user/Sofía statement, not repeated gestures or model guesses. `boundary_active` is a read-only scoped restriction lookup, **not yet plugged into the interaction execution guard**. No time-driven emotional simulation or independent consent computation.
- `test/test_interaction_registry.py` and `test/test_interaction_temporal.py`: real-registry checks against the canonical avatar and a separate `tmp_path` SQLite database respectively.

The catalog is not a full natural-language parser. It resolves complete region or semantic names only; it cannot classify multi-action sentences, sexual activities beyond explicitly reviewed semantics, or confirm any physical contact. The journal's source IDs are supplied by its caller and are **not independently authenticated**; a reviewed application-layer commit path must verify actual saved messages before trusting them. A modeled character boundary is not enforceable until application integration, and the existing per-session stop must remain authoritative.

## Verification

Locally isolated module checks passed for registry aliases and journal revision semantics, but those checks did **not** exercise the GitHub checkout, actual avatar, live CLI, existing regression suite, or user's Windows environment. After pulling this branch, run:

```powershell
pytest -q -x test/test_interaction_registry.py test/test_interaction_temporal.py
pytest -q -x test/test_interaction_live_stop_repetition.py test/test_interaction_contextual_all_regions.py test/test_interaction_import_order.py
```

If any fail, repair the feature branch before expanding the live engine. Follow with the separately documented coordinated I1–I7 suite and supervised live-model review. **Do not run new journal tests against the production SQLite path.**

## Remaining implementation, not merely TODO labels

I8: reviewed comprehensive colloquial/locale lexicon and migration; I9: grammar and action state transitions; I10: verified saved-message-to-journal commit pipeline, appraisal journal and enforceable boundaries; I11: long-form context-dependent reaction and anti-repetition acceptance; I12: world/avatar projection; I13: real expression planning and acknowledged audio/animation; I14: active expanded emotion journal and evidence-linked automatic preference proposals subject to review; I15: goal choice, reciprocal initiative and opt-in authorized running-only worker/delivery; I16: multi-client scoped stop, privacy/retention policy, migrations, failure/replay and full-system acceptance. No part of this checkpoint claims those systems are already running.
