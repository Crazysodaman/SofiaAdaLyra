# PKG-DISCORD: durable owner-DM channel core

**Branch:** `feature/pkg-discord`  
**Base:** current `main` after the INTERACT merge  
**Status:** offline implementation only. No Discord client, token, network access, or platform send is enabled.

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
- `DiscordIngress` remains the trusted-adapter boundary. A future live adapter must authenticate the gateway/library event before setting `authenticated_source=True`.

## Intentionally not implemented yet

- Discord library dependency, bot token, Gateway connection, REST sends, reconnect/resume, or rate-limit handling.
- A supervised channel-to-conversation-session enrollment store. The bridge currently requires an already active conversation session and records its session ID in the outbox.
- Outbound chunking, final recipient/STOP/revocation recheck, delivery receipts, ambiguous HTTP-send reconciliation, or platform message IDs.
- Proactive DMs, guilds, attachments, links, voice, slash commands, reactions, or multi-user access.
- General Internet/search capability.

## Next engineering slice

Add the **supervised channel/session binding plus final outbound authorization contract**. After that, select and verify the current Python Discord library and implement the live gateway/send adapter behind the existing offline boundaries. Live transport stays disabled until owner ID, bot/application ID, DM channel, secret storage, STOP/revocation behavior, and negative-access tests are all pinned.
