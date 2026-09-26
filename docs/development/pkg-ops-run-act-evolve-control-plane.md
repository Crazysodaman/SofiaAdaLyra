# OPS / RUN / ACT / EVOLVE runtime control-plane integration

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** candidate implementation; targeted and full-suite Windows acceptance still required.

## Purpose

Wire the already-merged OPS, RUN, ACT, and EVOLVE primitives into the canonical
runtime/application lifecycle without silently activating autonomy.

The new `RuntimeControlPlane` uses the canonical Sofía state database and the
same `OpsToolService` instance already registered for cognition. Application
startup opens the durable INTERACT goal queue, ACT outbox, RUN lease store, and
a disabled-by-default periodic gate. Application shutdown closes that host-side
boundary before runtime shutdown.

## Safety and authority invariants

- Importing or opening the control plane starts no thread.
- The default RUN periodic policy is disabled.
- Creating an ACT delivery runner never invokes its injected sender.
- Creating a RUN supervisor never starts or stops a process.
- OPS remains the existing read-only cognitive surface; this slice does not
  execute maintenance or workload migration.
- EVOLVE factories require an explicit store adapter and independent approval
  verifier. No permissive verifier or self-approval path is added.
- No OS service/watchdog, remote host deployment, live sender, standby
  promotion, workload move, protected amendment, or web access is enabled.

## Targeted acceptance

Run:

```powershell
pytest -q test/test_runtime_control_plane.py test/test_application.py
```

Then package regressions:

```powershell
pytest -q test/test_run_periodic_thought.py test/test_run_lease.py test/test_run_supervisor.py test/test_act_outreach.py test/test_act_delivery.py test/test_evolve_amendment.py test/test_evolve_executor.py test/test_evolve_revision.py test/test_ops_wave1_acceptance.py test/test_ops_wave2_acceptance.py test/test_ops_waves3_5_acceptance.py
```

Finally run the full repository suite:

```powershell
pytest -q
```

## Remaining after this slice

This is source/runtime wiring, not live 24/7 acceptance. Remaining work still
includes OS supervision/watchdog installation, real heterogeneous host
deployment, live authorized ACT sender/channel integration, OPS maintenance and
migration execution, cross-host fencing/failover, SAFE-backed approval
verification, restore drills, measured RTO/RPO, and multi-day soak.
