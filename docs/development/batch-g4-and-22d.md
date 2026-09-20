# Batch G4 and Engineering 22D checkpoint

**Status:** implementation prepared for local verification. Neither full batch is complete. This checkpoint follows G1–G3 and 22A–22C.

## G4: explicit observational personality probes

`sofia.personality.probe.observe_personality_cases` accepts the existing personality profile, an explicitly supplied cognitive engine, named user questions, and a positive `max_cases`. It assembles the ordinary personality context and captures a digest of the full role-labeled request, raw provider/engine text, elapsed time, and per-case errors. Too many or duplicate cases are rejected before any inference. It **does not grade**, rewrite outputs, automatically change providers, or create a live engine. A limit on case count is **not a wall-clock timeout**. Mock tests establish only mechanics; eventual real-model responses require an explicitly chosen, timed, locally supervised run.

Tests include an intentionally generic answer that is retained as-is. That is evidence of an answer, **not** evidence that the personality contract was followed. No claim about canonical identity fidelity can be inferred from presence of source instructions alone. Review raw texts and provider error messages before sharing or committing them.

## 22D: reconcile peer reachability evidence

`sofia.distributed.reachability.assess_peer_reachability` takes the 22C enrolled-peer snapshot plus explicit caller-supplied observations, a timezone-aware clock, and a positive freshness window. The assessment selects the latest current observation per source; retains stale and future evidence separately; reports conflicting current reachable/unreachable observations as `DEGRADED`; and distinguishes expected availability from actual observed reachability. `UNREACHABLE` records failed observation, **never a verified offline machine**. Source strings do not establish signal independence. It does not scan, contact, authenticate, trust, authorize, or operate any device.

## Local verification

```powershell
pytest -q test/test_personality.py test/test_personality_embodiment_contract.py test/test_personality_pipeline.py test/test_personality_expression_boundary.py test/test_personality_provider_path.py test/test_personality_probe.py test/test_distributed_node_contract.py test/test_distributed_identity.py test/test_distributed_peer_knowledge.py test/test_distributed_reachability.py
pytest -q -m "not integration"
git diff --check
git status --short
```

Only the first command is a focused gate. The broader non-integration suite can take many minutes; report its actual result. All G/22 files remain uncommitted until an approved, reviewed checkpoint. Stage exact intended files, never `git add .` with database, log, or installer scripts present.
