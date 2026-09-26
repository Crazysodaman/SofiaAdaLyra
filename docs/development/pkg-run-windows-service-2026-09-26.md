# PKG-RUN native Windows service host candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** candidate; Windows offline acceptance required, followed by supervised SCM canary.

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

## Offline gate

```powershell
pytest -q test/test_run_windows_service.py test/test_run_lifecycle.py test/test_application.py test/test_run_supervisor.py
```

## Supervised Windows canary after offline acceptance

Installation, automatic-start policy, recovery configuration, reboot/start,
stop, forced-process-kill and bounded restart must be tested on the selected
Windows service host before this slice is called production accepted.
