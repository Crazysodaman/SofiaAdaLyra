# ACT → Discord authorized sender candidate

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** accepted on the current candidate branch on 2026-09-26. Windows focused acceptance passed **37/37**, the combined OPS/RUN/ACT/EVOLVE regression gate passed **171/171**, and Sparks reported the full repository pytest suite passing. Live event-loop attachment remains separately gated.

This slice adds a proactive Discord sender specifically for ACT without
pretending proactive messages are replies to fabricated inbound Discord
messages.

The adapter requires:

- an explicitly enabled pinned single-user Discord configuration,
- the exact durable owner/channel/session binding,
- the exact ACT recipient ID selected by the host,
- ACT channel `discord_dm` and the pinned channel snowflake as destination,
- the same binding generation throughout the send,
- an explicitly injected transport callback.

It persists an ACT-specific Discord attempt plus per-chunk send claims and
provider message IDs. A process restart during an in-flight chunk, transport
exception after handoff may have begun, or authority change after a partial
send becomes `outcome_unknown` and is not blindly retried.

No network connection, scheduler, timer, bot token, recipient discovery, or
permission grant is created by this module.

## Targeted gate

```powershell
pytest -q test/test_discord_act_sender.py test/test_run_act_schedule.py test/test_act_delivery.py test/test_discord_delivery.py test/test_discord_outbound_gate.py
```

Then rerun the combined OPS/RUN/ACT/EVOLVE package gate and the full repository
suite before acceptance.
