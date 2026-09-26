# PKG-RUN production lifecycle state candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** candidate; Windows acceptance required.

This slice introduces one durable local RUN lifecycle truth:

```text
STOPPED → STARTING → RECOVERING → READY
                         ↘ DEGRADED
READY/DEGRADED → DRAINING → STOPPING → STOPPED
any active state → FAILED or FENCED
```

The store is persisted in the canonical Sofía state database with an immutable
transition event history. A new process finding a prior nonterminal state
records an **unclean restart** and enters `RECOVERING` rather than pretending
the previous process shut down normally.

`FENCED` cannot directly restart. It must first be explicitly cleared to
`STOPPED`, keeping loss of execution authority distinct from an ordinary
crash.

The application bootstrap now opens the control plane before runtime startup,
records STARTING/RECOVERING/READY truthfully, records FAILED on startup error,
and closes the control plane during rollback. Shutdown records
DRAINING/STOPPING/STOPPED around the canonical runtime shutdown.

This is local lifecycle truth only. It does not install an OS service, create a
watchdog, grant leadership, or implement cross-host promotion.

## Targeted gate

```powershell
pytest -q test/test_run_lifecycle.py test/test_runtime_control_plane.py test/test_application.py
```

Then rerun RUN/ACT/Discord integration and the full repository suite before
acceptance.
