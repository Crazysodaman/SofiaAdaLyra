# PKG-DISCORD: durable owner-DM channel core

**Branch:** `feature/pkg-discord`  
**Base:** current `main` after the INTERACT merge  
**Status:** offline implementation only. No Discord client, bot token, network access, or platform send is enabled.

## Verified local evidence

On the Windows development checkout, the first durable-ingress/bridge slice was executed successfully:

- Discord-focused gate: **43 passed in 4.59s**.
- First durable-ingress/bridge full suite: **1710 passed, 2 skipped in 2511.53s**.
- Channel/session-binding + outbound-gate focused suite: **54 passed in 7.50s**.
- Channel/session-binding + outbound-gate full suite: **1721 passed, 2 skipped in 2502.06s**.
- No regression was observed in either validated revision.
- Crash-aware delivery + `discord.py` adapter focused suite: **62 passed in 16.89s**.
- The subsequent full repository suite on that adapter revision was reported **PASS** locally after installing `discord.py==2.7.1`; the exact final count was not captured in the chat transcript.

The newer supervised provisioning, foreground lifecycle, reconnect recovery, and hard-crash quarantine slice was committed after that pass and still requires focused and full-suite execution on the exact current branch revision.

## Implemented

- Fail-closed single-user policy for exactly one enrolled owner account and one bot account.
- Optional exact DM-channel binding for supervised provisioning before live transport.
- Private human-authored DM only. Guild channels, group DMs, bots, webhooks, wrong recipients, wrong bound channels, and unverified sources are denied.
- Text-only ingress screening with bounded content and malformed-input rejection.
- Durable SQLite inbox using the same state-file pattern as existing Sofía stores.
- Discord snowflakes persist as canonical decimal text so the full unsigned 64-bit contract does not overflow SQLite INTEGER.
- Atomic duplicate/conflict handling keyed by `(bot_user_id, channel_id, message_id)`.
- Original accepted text is retained; exact retries do not create a second row.
- Same platform identity with changed content is reported as a conflict rather than overwriting evidence.
- Durable processing claims prevent two workers from generating the same logical reply concurrently.
- `DiscordConversationBridge` feeds one durable inbox item into an active Sofía conversation service and stages the resulting text in a durable outbox.
- A staged outbox row is unique per triggering inbox identity, so reprocessing a completed item does not ask the model to answer again.
- Ambiguous generation failures are marked `outcome_unknown` and are not automatically retried.
- Durable `DiscordBindingStore` binds the exact bot + owner + DM channel to one conversation session.
- Pause, resume, revoke, and supervised rebind change a monotonically increasing binding generation.
- Every sendable outbox item receives an immutable snapshot of the authority generation under which it was staged.
- If pause/revoke/rebind occurs while generation is running, the response may remain stored for audit but does **not** receive outbound authority.
- `DiscordOutboundGate` rechecks enablement, exact bot, pinned DM channel, owner recipient, session, current pause/revoke state, and binding generation immediately before any future send.
- A reply prepared before pause remains stale after resume; resume does not resurrect old queued speech.
- `DiscordIngress` remains the trusted-adapter boundary. A future live adapter must authenticate the gateway/library event before setting `authenticated_source=True`.

## Intentionally not implemented yet

- Live bot token provisioning, Gateway connection, supervised real-DM acceptance, and deployment lifecycle wiring.
- Automated reconciliation of an `outcome_unknown` chunk with Discord history. Unknown delivery is intentionally quarantined rather than guessed or resent.
- Owner DM text commands for pause/resume/status. Current pause/revoke state is supervised host-owned state, not inferred from arbitrary chat text.
- Proactive DMs, guilds, attachments, links, voice, slash commands, reactions, or multi-user access.
- General Internet/search capability.

## Current live-adapter slice

- `discord.py==2.7.1` is pinned as the transport dependency.
- Importing Sofía's Discord package still starts no client and reads no token.
- The client requests only the direct-message Gateway intent and disables the message cache.
- Discord callback objects are converted into trusted numeric-ID facts at the adapter boundary; group DMs and guild traffic remain distinguishable and are denied by the existing ingress policy.
- Live DM handling is serialized so one conversation session is not raced by concurrent callbacks.
- Replies are split into bounded Discord-sized chunks without altering content.
- Every chunk is durably prepared before send, re-authorized immediately before send, and records the Discord message ID only after a provider acknowledgement.
- Mentions are disabled globally and per send.
- A pause/revoke between chunks stops the remainder.
- An ambiguous send failure is marked `outcome_unknown` and is not automatically retried.
- The live client constructor and blocking runner remain separate from the normal terminal application.
- `python -m sofia.discord` is the explicit supervised foreground entry point; `python -m sofia` does not start Discord.
- Environment provisioning is fail-closed and requires `SOFIA_DISCORD_ENABLED=1`, exact owner/bot/DM-channel snowflakes, and `SOFIA_DISCORD_TOKEN`.
- The token is never stored in SQLite and is excluded from provisioning object representations.
- The Discord-bound conversation session is persisted through the channel binding and resumed after process restart.
- Startup quarantines any generation claim left in `processing` because a hard crash may have occurred after conversation state changed.
- Each network chunk gets a durable in-flight token before Discord I/O. A hard restart with an in-flight token converts it to `outcome_unknown` rather than resending it.
- Prepared replies that have never entered network I/O are discovered on reconnect and safely resumed through the normal outbound gate.
- Foreground transport shutdown always closes the Sofía application lifecycle.
- The live process holds an OS-backed non-blocking lock keyed to the state database, so a second live Discord process cannot concurrently recover or process the same channel state. The lock lives in the host temporary directory and is released automatically when the process exits.

## Live provisioning contract

The supervised host supplies these environment variables locally. Values and the bot token must not be committed to Git or pasted into project documentation:

- `SOFIA_DISCORD_ENABLED=1`
- `SOFIA_DISCORD_OWNER_ID=<owner snowflake>`
- `SOFIA_DISCORD_BOT_ID=<bot snowflake>`
- `SOFIA_DISCORD_DM_CHANNEL_ID=<private DM channel snowflake>`
- `SOFIA_DISCORD_TOKEN=<bot token from local secret storage>`

When those values are deliberately provisioned, the foreground channel is started with:

```powershell
python -m sofia.discord
```

Without the explicit enable flag, startup refuses before any Discord connection.

The same module also exposes local host controls that do **not** require the bot token and do **not** connect to Discord:

```powershell
python -m sofia.discord status
python -m sofia.discord pause
python -m sofia.discord resume
python -m sofia.discord revoke
python -m sofia.discord reenroll
```

These controls require the exact owner, bot, and DM-channel ID environment variables so they cannot select a binding by display name. `status` reports the durable binding state, conversation session, binding generation, pending outbox count, and counts of quarantined generation/delivery outcomes without printing message content. `revoke` is persistent and cannot be undone with `resume`; `reenroll` is the separate supervised action that reactivates the exact same enrolled owner/channel/session with a new binding generation.

## Next engineering slice after current tests

Run the expanded offline/fake-client acceptance gate for provisioning, restart recovery, lifecycle cleanup, and adapter behavior. If green, perform one supervised real owner-DM acceptance: connect the exact bot identity, verify the exact DM channel, send one owner DM, receive one Sofía reply, verify the Discord message receipt in SQLite, exercise pause/revoke, restart the process, and verify conversation continuity. After a final full regression pass, PKG-DISCORD v1 is ready to merge. Automated resolution of genuinely ambiguous provider outcomes remains deliberately manual/fail-closed rather than inventing delivery certainty.
