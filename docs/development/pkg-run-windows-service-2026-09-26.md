# PKG-RUN native Windows service host candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** **offline accepted** on 2026-09-26. Windows lifecycle/service gates passed **49/49** and final hardened service-installability regression passed **45/45**; Sparks reported the full repository pytest suite green on the final hardened tip. Live SCM install/reboot/kill/recovery canary remains required before deployed production acceptance.

This slice adds a real Windows Service Control Manager boundary using pywin32.
It does **not** register or start a service on import.

The service host:

- constructs the canonical `SofiaApplication`,
- starts it under SCM ownership,
- reports RUNNING only after application startup succeeds,
- blocks on a Windows stop event,
- performs canonical application shutdown on service stop,
- reports a nonzero stopped status when startup/runtime hosting fails,
- leaves durable lifecycle/recovery truth to PKG-RUN,
- supports explicit SCM failure-action configuration with bounded restart delays.

The project dependency on pywin32 is Windows-only. Linux/Pi service hosting
will use a separate systemd boundary rather than pretending one host manager
fits every OS.

SCM recovery configuration is an explicit administrative action. Normal Sofía
startup never edits service configuration.


## Live-host deployment preflight

- Install/update the project dependencies in the exact Python environment used by SCM; `git pull` does not update an existing virtual environment. Verify `win32serviceutil`, `win32event`, and `servicemanager` import before service installation.
- The Windows production/canary checkout and canonical SQLite state database must be on a **local filesystem** visible during boot. Do not install the service from a mapped SMB drive or use a live SQLite database over SMB. Mapped-drive letters may not exist for the service account at boot, and network-share locking/availability is not an accepted RUN durability boundary.
- Use a local deployment checkout/state for the canary, then separately prove backup/replication under SAFE/RUN reliability gates.

## Offline gate

```powershell
pytest -q test/test_run_windows_service.py test/test_run_lifecycle.py test/test_application.py test/test_run_supervisor.py
```

## Supervised Windows canary after offline acceptance

Installation, automatic-start policy, recovery configuration, reboot/start,
stop, forced-process-kill and bounded restart must be tested on the selected
Windows service host before this slice is called production accepted.
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


