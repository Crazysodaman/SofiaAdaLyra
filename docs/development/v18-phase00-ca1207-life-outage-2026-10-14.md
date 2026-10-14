# V18 CA-1207: independent LIFE model outage cannot cancel reconciliation

Date: 2026-10-14. The existing application-backed independent LIFE job
first attempts a voluntary project idea, then reconciles/starts existing
work through `life.tick`. Previously, a provider outage or invalid JSON
could throw from `life.consider_new_project` and abandon this periodic
execution before `life.tick`. The scheduler retained its own error, but
ongoing LIFE settlement would be deferred unnecessarily.

`src/sofia/application/background_runtime.py` now uses a small
`_consider_life_idea_without_wedging_worker` wrapper at the **actual
production caller**. It catches only the typed
`CognitiveEngineError` and `ProjectIdeaGenerationError` from optional
cognition, logs a content-free reason, and returns no proposed project.
The existing `life.tick` executes next to reconcile prior RUN work.
Operator-stop, database failure, access denial and coding bugs continue
to fail visibly; the wrapper creates no new scheduler, grant or database.

`test/test_v18_phase00_model_outage.py` exercises both expected
model-failure cases, success behavior, typed unexpected failure propagation,
and verifies the integrated caller's execution order. The dedicated Phase
00 Ubuntu/Windows CI selects these tests.

Not yet acceptance: actual failed Ollama, restart under load, user-facing
diagnostics, concurrent foreground responsiveness and the complete
CA-1207 requirement still need independent pinned source/effect receipts.
