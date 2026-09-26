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
