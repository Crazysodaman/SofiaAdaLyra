# ACT → live Discord event-loop handoff

**Branch:** `feature/pkg-ops-run-act-evolve-control-plane`  
**Status:** candidate; Windows acceptance required.

This slice attaches the already accepted proactive ACT Discord sender to the
verified `discord.py` event loop without giving ACT ownership of the async
client.

The live client binds a `DiscordActTransportBridge` only after:

1. the authenticated bot identity matches the configured bot,
2. the exact pinned DM channel resolves,
3. the durable owner/channel/session binding is verified.

RUN/ACT remains synchronous and must execute off the Discord event-loop thread.
The bridge uses `asyncio.run_coroutine_threadsafe` to hand one bounded chunk
to the verified async channel and returns the provider message ID to the
existing durable ACT Discord ledger.

Disconnect and runner exit unbind the bridge. Transport timeouts and ambiguous
exceptions are classified by the accepted ACT sender as `outcome_unknown`.

Live proactive delivery is still **explicitly disabled by default**:
`compose_live_discord(..., act_recipient_id=None)` creates no ACT sender.
Supplying a recipient ID is a host-level integration choice and is intentionally
not inferred from usernames or message text while PKG-SOCIAL remains open.

This slice also hardens ACT restart recovery: any delivery attempt left
`claimed` by a process loss is quarantined as `outcome_unknown` together
with its queued message before new delivery work resumes.

## Targeted gate

```powershell
pytest -q test/test_discord_act_live.py test/test_discord_live.py test/test_discord_act_sender.py test/test_act_delivery.py test/test_runtime_control_plane.py
```

Then rerun the combined OPS/RUN/ACT/EVOLVE + Discord regression gate and the
full repository suite before acceptance.
