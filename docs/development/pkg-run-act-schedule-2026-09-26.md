# RUN → ACT scheduled delivery candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** candidate; Windows acceptance required.

This slice adds a host-invoked `ScheduledActRunner` that scans only the
canonical INTERACT queued-message table, ignores unbound messages, and hands
already-bound messages to ACT's existing durable claim/receipt/retry logic.

It deliberately does **not**:

- create goals or messages,
- bind recipients/channels/destinations,
- invent outreach permissions,
- start a timer/thread/service,
- open Discord/network connections,
- bypass busy/mute/stop/quiet/cooldown/daily-cap policy,
- retry `outcome_unknown` deliveries blindly.

Scheduling defaults disabled. Enabling it still requires the host to inject an
ACT policy provider, an attempt-ID provider and an actual sender.

## Targeted gate

```powershell
pytest -q test/test_run_act_schedule.py test/test_runtime_control_plane.py test/test_act_delivery.py test/test_act_outreach.py
```

Then rerun the combined package gate and full repository suite before
acceptance.
