# PKG-RUN heartbeat and independent watchdog candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** candidate; Windows focused acceptance passed **62/62**, the surrounding RUN/ACT/Discord regression gate passed **172/172**, and the expanded production-RUN regression gate passed **183/183** on 2026-09-26. Full repository pytest remains required before acceptance.

This slice separates **process existence**, **readiness**, and **health**.

The service host writes a durable, fenced heartbeat session containing:

- a unique service-session ID,
- the service process ID,
- the current durable RUN lifecycle generation/state,
- the last successful heartbeat timestamp.

A newer heartbeat session fences the older writer. A stale process cannot keep
refreshing health after a replacement service has started.

The derived health model distinguishes:

- `STARTING`
- `HEALTHY`
- `DEGRADED`
- `STOPPING`
- `STOPPED`
- `FAILED`
- `FENCED`
- `STALE`
- `UNKNOWN`

The host-neutral `IndependentRunWatchdog` is designed for a **separate
process/service**. It reads only durable RUN evidence and controls the OS
service through an injected `HostServiceController`. It never invokes
cognition, ACT or the in-process runtime.

Recovery is bounded by a restart cooldown and restart-window limit. Unknown
service state fails closed. A fenced lifecycle blocks automatic start and
causes a still-running service to be stopped.

The Windows SCM host now pulses the heartbeat while running. This makes a hung
service detectable even when its PID still exists.

This does not yet install the watchdog as its own Windows service. That is the
next host-specific slice after this offline contract passes.

## Targeted gate

```powershell
pytest -q test/test_run_health.py test/test_run_watchdog.py test/test_run_windows_service.py test/test_run_lifecycle.py test/test_application.py test/test_runtime_control_plane.py test/test_run_supervisor.py
```

Then rerun RUN/ACT/Discord integration and the full repository suite.
