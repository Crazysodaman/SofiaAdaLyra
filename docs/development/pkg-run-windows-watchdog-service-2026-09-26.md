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


## Live-host deployment preflight

- Install/update the project dependencies in the exact Python environment used by SCM; `git pull` does not update an existing virtual environment. Verify `win32serviceutil`, `win32event`, and `servicemanager` import before service installation.
- The Windows production/canary checkout and canonical SQLite state database must be on a **local filesystem** visible during boot. Do not install the service from a mapped SMB drive or use a live SQLite database over SMB. Mapped-drive letters may not exist for the service account at boot, and network-share locking/availability is not an accepted RUN durability boundary.
- Use a local deployment checkout/state for the canary, then separately prove backup/replication under SAFE/RUN reliability gates.

## Offline gate

```powershell
pytest -q test/test_run_windows_watchdog_service.py test/test_run_watchdog.py test/test_run_health.py test/test_run_windows_service.py test/test_run_lifecycle.py
```


## Live canary evidence — install/config phase

On 2026-09-26, the local canary checkout at `C:\\SofiaAdaLyra-canary` successfully installed both SCM services:

- `SofiaAdaLyra`: automatic start,
- `SofiaAdaLyraWatchdog`: delayed automatic start,
- both hosted by the local canary `pythonservice.exe`,
- both configured for bounded SCM restart recovery at 5s / 15s / 60s with a 24-hour reset period,
- both currently configured under `LocalSystem` for the canary.

Installation/configuration is accepted as live evidence. Runtime start, heartbeat, independent watchdog PID, kill/hang/fence recovery, reboot recovery and measured RTO remain open.


## Live canary finding — service Python scope

The first SCM start canary failed before RUN lifecycle generation advanced and before any heartbeat existed. The installed service host was the canary virtual environment's `pythonservice.exe`, while that venv's base Python was a per-user installation under `%LOCALAPPDATA%`. The service account was `LocalSystem`.

This deployment shape is rejected for production RUN. pywin32 documents that Windows services should use a globally accessible Python installation and notes that `LocalSystem` commonly cannot access user-local Python. A machine-wide dedicated Python runtime is now required for the Windows service host. The repository/state may remain on local `C:\\` storage; only the service Python host must be machine-accessible.

The live canary remains open. Offline RUN acceptance is unchanged because the application lifecycle never received control in this failure.


## Live canary evidence — machine-wide service runtime

The Windows canary service host has been corrected to a dedicated machine-wide Python 3.13 runtime at `C:\\Program Files\\SofiaAdaLyra\\Python313`. Elevated pywin32 post-install completed successfully, `pythonservice.exe` was copied to the interpreter prefix, and both `SofiaAdaLyra` and `SofiaAdaLyraWatchdog` now register `BINARY_PATH_NAME` against that machine-wide host while running under `LocalSystem`. The focused RUN Windows gate remains **45/45** under the same interpreter.

This closes the per-user/venv service-host deployment defect. Runtime start/READY heartbeat, watchdog independence, kill/hang/fence/reboot recovery and measured RTO remain open.


## Live canary evidence — runtime start to READY

On 2026-09-26, `SofiaAdaLyra` successfully started under Windows SCM using the dedicated machine-wide Python 3.13 service host and `LocalSystem`. SCM reported `RUNNING` with a nonzero service PID. Durable RUN lifecycle advanced from `RECOVERING` generation 2 to `READY` generation 3, and the service then created a fenced heartbeat session bound to the same process ID. Observed RECOVERING→READY time was approximately **30 seconds** in this canary.

This is live proof that the Windows service host reaches canonical application READY state. Heartbeat advancement, independent watchdog start/PID, kill/hang/fence/reboot recovery and measured recovery RTO remain open.

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
