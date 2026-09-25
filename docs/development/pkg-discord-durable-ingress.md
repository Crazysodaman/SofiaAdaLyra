# PKG-DISCORD: durable owner-DM channel core

**Branch:** `feature/pkg-discord`  
**Base:** current `main` after the INTERACT merge  
**Status:** v1 transport accepted live on 2026-09-24 and ready for merge. The supported scope is one explicitly provisioned, Sparks-only private DM channel using the shared Sofía runtime. General web/search, guilds, multi-user access, and proactive outbound initiative remain outside this package.

## Verified acceptance evidence

Revision-pinned evidence accumulated across the package build and final live repair:

- First durable-ingress/bridge focused gate: **43 passed**; full suite at that slice: **1710 passed, 2 skipped**.
- Channel/session binding + outbound gate focused gate: **54 passed**; full suite at that slice: **1721 passed, 2 skipped**.
- Crash-aware delivery + `discord.py` adapter focused gate: **62 passed**; the subsequent repository suite was reported PASS locally, although the exact count was not retained.
- Final Discord-focused gate after live startup and SQLite thread-affinity repairs: **88 passed, 1670 deselected**.
- Conversation + persistent-memory worker-thread repair gate: **28 passed**.
- Supervised live acceptance verified: static-token login, Discord Gateway connection, exact configured bot identity, exact private DM resolution, durable enrollment, authenticated owner DM ingress, one shared Sofía response, and one visible Discord reply.
- The first live message exposed a real SQLite thread-affinity failure. The failed message was conservatively quarantined as `outcome_unknown`; ConversationStore and persistent MemoryStore were hardened for serialized cross-thread use and the live retry succeeded.
- A deliberately wrong pre-provisioned DM channel was revoked and not reused. First enrollment of the corrected channel occurred only after authenticated Discord identity/channel verification.
- No bot token or exact production Discord account/channel identifiers are stored in this document.

Current-head package acceptance relies on the focused gates plus supervised live evidence above. A new repository-wide full-suite run after the final thread-safety repair is not claimed here and belongs to the next integrated verification gate.

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

## Intentionally outside v1 transport scope

- Automated reconciliation of an `outcome_unknown` generation or delivery with Discord history. Ambiguous outcomes remain quarantined rather than guessed or replayed.
- Chat-text administration. Pause/resume/revoke/status remain host-side operator controls instead of model- or message-driven authority.
- Proactive DMs, guilds, attachments, voice, slash commands, reactions, or multi-user access.
- Authenticated-principal projection into cognition. Discord proves the exact owner account at the transport boundary, but PKG-SOCIAL owns projecting that principal as `Sparks` into shared cognitive context.
- Generic conversational/personality quality. The live channel exposed a canned-assistant regression; that is tracked by a new INTERACT/CORE quality-repair gate rather than patched inside Discord.
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

## Closure and handoff

PKG-DISCORD v1 transport is closed for the accepted scope and may merge to `main`.

Post-merge work is deliberately split by ownership:

1. **INTERACT/CORE quality repair:** remove generic/canned assistant fallback while preserving grounding, embodiment, and non-repetitive natural voice.
2. **SOCIAL minimum principal projection:** map the independently authenticated owner principal into shared Sofía cognitive context so identity-aware questions do not fall back to generic privacy boilerplate.
3. **RUN/OPS deployment:** move from supervised foreground execution to the separately gated 24/7 service/watchdog/fleet architecture.
4. **VERIFY:** rerun integrated full-suite/live checks against the merged revision as downstream packages advance.

Discord remains a transport adapter to the canonical Sofía runtime, never a second identity, personality, memory system, or authority source.
