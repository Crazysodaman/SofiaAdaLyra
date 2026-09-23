# PKG-DISCORD: durable owner-DM ingress

**Branch:** `feature/pkg-discord`  
**Base:** current `main` after the INTERACT merge  
**Status:** offline implementation only. No Discord client, token, network access, or outbound messages are enabled.

## Implemented in this slice

- Fail-closed single-user policy for exactly one enrolled owner account and one bot account.
- Private human-authored DM only. Guild channels, group DMs, bots, webhooks, wrong recipients, and unverified sources are denied.
- Text-only ingress screening with bounded content and malformed-input rejection.
- Durable SQLite inbox using the same state-file pattern as existing Sofía stores.
- Atomic duplicate/conflict handling keyed by `(bot_user_id, channel_id, message_id)`.
- Original accepted text is retained in the inbox; exact retries do not create a second row.
- Same platform identity with changed content is reported as a conflict rather than silently overwriting evidence.
- Restart persistence and concurrent duplicate claims are covered by tests.
- `DiscordIngress` is the offline trusted-adapter boundary. A future live adapter must authenticate the gateway/library event before setting `authenticated_source=True`.

## Intentionally not implemented yet

- Discord library dependency, bot token, Gateway connection, REST sends, reconnect/resume, rate-limit handling.
- Conversation dispatch into Sofía's active conversation service.
- Durable outbox, chunking, delivery receipts, STOP/revocation recheck.
- Proactive DMs, guilds, attachments, links, voice, slash commands, reactions, or multi-user access.
- General Internet/search capability.

## Next engineering slice

Add the **conversation bridge and durable outbox contract** without enabling live network transport. One accepted inbox row should produce at most one logical response candidate, with recipient/session binding and a final authorization check before a future send adapter can touch Discord.
