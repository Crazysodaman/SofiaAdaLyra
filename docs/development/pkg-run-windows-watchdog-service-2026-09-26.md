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


## Live canary evidence — heartbeat and watchdog independence

The live runtime heartbeat was observed advancing while `SofiaAdaLyra` remained READY, confirming periodic heartbeat pulses rather than only startup initialization. The independent `SofiaAdaLyraWatchdog` service then started successfully under SCM. SCM reported both services RUNNING with distinct process IDs, proving the watchdog is hosted independently from the Sofía runtime process.

Crash recovery, hang/stale-heartbeat recovery, fenced-stop behavior, reboot recovery and measured RTO remain open.


## Live canary evidence — destructive crash recovery

A supervised destructive canary force-killed the live `SofiaAdaLyra` process while the independent watchdog remained running. The watchdog recorded `service_start` at `2026-09-26T22:52:56.857802+00:00` after observing the runtime service stopped. The replacement runtime reached durable `READY` generation 5 at `2026-09-26T22:53:21.566387+00:00` with a new heartbeat session and a new process ID, while the watchdog process remained independently running.

Measured evidence:

- watchdog reaction from kill to service-start action: approximately **1.9 seconds**,
- kill to durable READY recovery RTO: approximately **26.6 seconds**,
- replacement heartbeat session and process ID differ from the killed runtime,
- watchdog remained alive throughout recovery.

This proves live external crash recovery through the independent watchdog. Stale-heartbeat/hang recovery, fenced-stop behavior, reboot recovery and longer soak remain open.


## Live canary evidence — stale-heartbeat recovery

A controlled canary kept the Sofía service present while forcing the durable heartbeat for the active session stale. The independent watchdog detected `health_state=stale` and recorded a live `service_restart` action at `2026-09-26T22:57:17.797087+00:00`. The runtime transitioned through `STOPPED → STARTING → RECOVERING → READY`, returned on a new process ID and a new heartbeat session, and the watchdog process remained independently running throughout.

Measured evidence:

- old runtime PID: `24672`,
- replacement runtime PID: `13388`,
- watchdog PID remained `10608`,
- stale-evidence detection/restart path recorded by the watchdog ledger,
- stale-heartbeat injection to durable READY RTO: approximately **37.1 seconds**.

This proves live independent watchdog recovery for a stale-heartbeat/hang-style failure. FENCED-stop behavior, reboot recovery and longer soak remain open.


## Live canary evidence — FENCED authority gate accepted

A live operator fence was asserted while the Windows runtime service and independent watchdog were active. The watchdog recorded `fenced_stop` and stopped the runtime service while remaining independently RUNNING. Durable lifecycle remained `FENCED` with the asserted owner/epoch.

A follow-up hardening patch made two fence races explicit: application shutdown preserves `FENCED`, and a fence asserted during startup is treated as a controlled clean stop rather than an SCM failure. The Windows service CLI also refuses `start` before touching SCM when durable RUN state is fenced.

Acceptance evidence after hardening:

- focused RUN regression gate: **48/48 passed**,
- fenced manual start refused immediately with process exit code `2`,
- `SofiaAdaLyra` remained `STOPPED` with PID `0` and SCM exit codes `0/0`,
- `SofiaAdaLyraWatchdog` remained `RUNNING`,
- durable lifecycle remained `FENCED` with owner `canary`, epoch `1`,
- no runtime resurrection occurred while fenced.

The FENCED authority gate is accepted. Reboot recovery and longer soak remain open.


## Live canary evidence — post-fence restoration

After the accepted FENCED authority test, the watchdog was stopped, the operator explicitly cleared durable RUN state from `FENCED` to `STOPPED`, and the Sofía Windows service was started manually. The runtime advanced through `STARTING/RECOVERING` to durable `READY`, created a new open heartbeat session bound to the live SCM process, and Windows Event Log recorded `Sofía Ada Lyra entered RUNNING state.`

Measured evidence:

- restored runtime PID: `26736`,
- new heartbeat session: `b602b185-9731-45b8-849d-858a32d0b802`,
- RECOVERING timestamp: `2026-09-26T23:10:02.562529+00:00`,
- READY timestamp: `2026-09-26T23:10:49.024163+00:00`,
- RECOVERING→READY duration: approximately **46.5 seconds**,
- heartbeat remained open and fresh after READY,
- Event Log recorded a clean RUNNING transition.

This proves explicit operator fence clearing restores normal service startup without residual fencing or stale-heartbeat ownership.

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
