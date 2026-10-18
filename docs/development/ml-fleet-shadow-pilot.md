# Fleet pressure shadow pilot verification contract

This document describes the production implementation for ML-008 and the
remaining live experiment for ML-010. It is not a deployment approval or trial
receipt.

## Production ownership

- Source: append-only `ops_telemetry_history`, owned by OPS/FLEET.
- Admission: exact unexpired `host-pressure-forecast` data-use grant.
- Scheduler: existing `ApplicationBackgroundCoordinator` task
  `fleet_pressure_shadow` under the shared STOP and optional-work budget.
- Predictor: bounded CPU-only linear trend candidate, compared after the
  target time against last-value and EWMA deterministic baselines.
- Outcome: later observed telemetry, or explicit UNKNOWN after an incomplete
  observation window. A forecast cannot label itself successful.
- Persistence: canonical `sofia.db` tables `ml_fleet_pressure_forecast`,
  `ml_grounded_sample`, `ml_prediction_trace`, and typed evidence references.
- Consumer: scoped settings/tray diagnostics. There is no placement or action
  consumer.

## Safety and resource limits

The pilot considers no more than 32 trusted enrolled/healthy hosts per tick and
64 historical observations per host. It does no LLM inference and loads no GPU
model. Local and per-host gaming/busy/do-not-disturb state suppresses work. The
application's existing STOP check suppresses the background task before its
callback runs. Predictions remain non-authoritative in every operating mode.

## Required live ML-010 campaign

The owner must separately approve an exact source revision and scoped Fleet
data-use grant. The same revision must run in SHADOW for at least fourteen
continuous calendar days and include cold start and restart observations. The
campaign report must include actual source coverage, prediction latency,
candidate/last-value/EWMA paired errors, UNKNOWN/skipped outcomes, CPU/RAM
overhead, host capacity, gaming suppressions, failure recovery, and candidate
rollback evidence. A separately authorized advancement decision is required
even if the candidate wins.

No local or CI test can substitute for that elapsed live-host evidence.
