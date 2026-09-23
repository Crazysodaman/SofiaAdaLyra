# PKG-DISCORD: durable owner-DM channel core

**Branch:** `feature/pkg-discord`  
**Base:** current `main` after the INTERACT merge  
**Status:** offline implementation only. No Discord client, bot token, network access, or platform send is enabled.

## Verified local evidence

On the Windows development checkout, the first durable-ingress/bridge slice was executed successfully:

- Discord-focused gate: **43 passed in 4.59s**.
- Full repository suite: **1710 passed, 2 skipped in 2511.53s**.
- No regression was observed in that validated revision.

The newer channel/session-binding and final-outbound-authorization slice was committed after that run and still requires its focused and full-suite execution on the exact current branch revision.

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

- Discord library dependency, bot token, Gateway connection, REST sends, reconnect/resume, or rate-limit handling.
- Live Discord adapter authentication and conversion from library events into trusted ingress facts.
- Message chunking, allowed-mention suppression, platform delivery receipts, ambiguous HTTP-send reconciliation, or platform message IDs.
- Owner DM text commands for pause/resume/status. Current pause/revoke state is supervised host-owned state, not inferred from arbitrary chat text.
- Proactive DMs, guilds, attachments, links, voice, slash commands, reactions, or multi-user access.
- General Internet/search capability.

## Next engineering slice after current tests

Select and verify the maintained Python Discord library and add the **disabled-by-default live adapter boundary**: authenticated Gateway event conversion, minimal intents, reconnect/rate-limit semantics, final `DiscordOutboundGate` call immediately before REST send, and no secret material in Git. Real transport remains disabled until the exact owner ID, bot/application ID, DM channel, secret storage, negative-access tests, STOP/revocation behavior, and supervised live acceptance are pinned.
