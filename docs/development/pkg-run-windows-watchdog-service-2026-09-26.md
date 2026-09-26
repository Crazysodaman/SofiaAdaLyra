# PKG-RUN independent Windows watchdog service candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** **offline accepted** on 2026-09-26. Watchdog-service gate passed **43/43**, expanded production-RUN regression passed **183/183**, final hardened service regression passed **45/45**, and Sparks reported the full repository suite green on the final hardened tip. Live dual-service Windows canary remains required before production acceptance.

This slice hosts the accepted-independent-watchdog design as its own native
Windows Service Control Manager service:

- runtime service: `SofiaAdaLyra`
- watchdog service: `SofiaAdaLyraWatchdog`

The watchdog service never constructs `SofiaApplication`. It opens only the
canonical RUN lifecycle/heartbeat stores and controls the runtime service
through `WindowsScmServiceController`.

The SCM controller exposes only:

- observe service state,
- start service,
- restart service,
- stop service.

Unknown/malformed SCM state remains `UNKNOWN` and therefore fail-closed under
the watchdog core.

The watchdog reconciles every five seconds while its own SCM service is
running. Stopping the watchdog service does **not** stop Sofía. A watchdog
failure reports nonzero service exit status so Windows recovery policy can
restart the watchdog itself.

No install/start/recovery configuration occurs at import time. Installation and
SCM recovery configuration remain explicit administrative canary steps.

## Offline gate

```powershell
pytest -q test/test_run_windows_watchdog_service.py test/test_run_watchdog.py test/test_run_health.py test/test_run_windows_service.py test/test_run_lifecycle.py
```

## Live Windows canary

After full-suite acceptance:

1. install `SofiaAdaLyra`,
2. configure bounded SCM recovery,
3. install `SofiaAdaLyraWatchdog`,
4. configure bounded SCM recovery for the watchdog,
5. confirm independent service PIDs,
6. kill the Sofía service process and measure restart-to-ready,
7. freeze/withhold heartbeats and verify bounded watchdog recovery,
8. stop the watchdog and confirm Sofía remains running,
9. fence RUN and verify the watchdog stops rather than restarts Sofía,
10. reboot Windows and verify ordered automatic recovery.

Measured results become the production RUN evidence bundle.
