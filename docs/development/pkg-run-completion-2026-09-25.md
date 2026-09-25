# PKG-RUN local lifecycle completion candidate

**Revision:** 2026-09-25. **Branch:** `feature/pkg-run-completion`. **Status:** focused local lifecycle/offline acceptance passed on the current Windows checkout. No Windows service, Linux unit, watchdog host, standby, or automatic failover is installed or claimed.

## Implemented candidate

### Bounded periodic opportunities

`sofia.run.periodic` provides a disabled-by-default, durable opportunity gate for evidence-backed reflection while the application is actually running. It starts no daemon, sends no message, and treats a wake as an opportunity rather than proof of a thought.

### Local singleton lease and fencing epoch

`sofia.run.lease` provides a SQLite-backed **local** singleton lease with monotonic epochs, expiry, renewal, release, takeover after expiry/release, stale-owner rejection, clock-uncertainty handling, and an audit ledger.

This is deliberately **not cross-host consensus**. It is a local fencing primitive for one supervisor/state store.

### Host-neutral local supervisor

`sofia.run.supervisor` accepts a narrow injected process backend with `observe/start/stop`. It provides:
- exact-lease enforcement before process control;
- stale-lease fencing of a still-running old process;
- desired-stop handling;
- readiness grace and timeout;
- bounded exponential restart backoff;
- restart-window limit;
- fail-closed unknown process state;
- durable supervisor events/state.

It does not expose a general shell and does not install itself as an OS service.

## Focused offline acceptance

```powershell
python -m pytest -q test/test_run_periodic_thought.py test/test_run_lease.py test/test_run_supervisor.py
```

Then run surrounding runtime/reflection regressions:

```powershell
python -m pytest -q test/test_idle_reflection_worker.py test/test_idle_reflection_application.py test/test_runtime.py test/test_runtime_action_integration.py
```

## Still intentionally outside this offline package gate

Real OS service installation, independent watchdog placement, multi-host consensus/fencing, standby promotion, Discord reconnection, data replication/restore, resource measurements, host-failure drills, and multi-day soak remain live/deployment acceptance work. Unit tests must not be used to claim high availability.

## Windows acceptance evidence

Executed on Sparks's Windows checkout on 2026-09-25:

- `python -m pytest -q test/test_run_periodic_thought.py test/test_run_lease.py test/test_run_supervisor.py` → **36 passed in 6.05s**.
- `python -m pytest -q test/test_idle_reflection_worker.py test/test_idle_reflection_application.py test/test_runtime.py test/test_runtime_action_integration.py` → **42 passed, 1 skipped in 24.22s**.

Current RUN offline evidence total: **78 passing tests and 1 skip across the focused and surrounding regression gates**. This remains local lifecycle evidence only, not real service/failover/soak acceptance.
