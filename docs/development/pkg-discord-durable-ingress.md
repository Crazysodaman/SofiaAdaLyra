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

The newer crash-aware delivery + `discord.py` adapter slice was committed after the 1721-pass run and still requires focused and full-suite execution on the exact current branch revision.

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
- Restart recovery for prepared-but-unsent outbox items when no fresh duplicate Gateway event arrives.
- Operator-facing reconciliation workflow for a chunk whose provider outcome is marked unknown.
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
- The live client constructor and blocking runner exist but are not wired into application startup or enabled by configuration.

## Next engineering slice after current tests

Add supervised environment/secret provisioning and lifecycle composition around the already-disabled live client, plus recovery/reconciliation for durable pending delivery state. Then perform fake-client fault tests followed by one supervised real owner-DM acceptance test. Real transport remains disabled until the exact owner ID, bot/application ID, DM channel, token storage, negative-access tests, STOP/revocation behavior, and deployment host are pinned.
