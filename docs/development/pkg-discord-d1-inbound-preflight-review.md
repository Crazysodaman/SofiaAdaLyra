# PKG-DISCORD D1: offline inbound preflight review

**Status: offline code only; not a Discord listener or an approved live gate.** This adds `sofia.discord.inbound` and `test/test_discord_inbound_preflight.py` to the existing draft Discord PR #5, without changing the access policy or enabling network access.

## What this slice does

- Runs the existing disabled-by-default, exact-Sparks-account, private-DM access check **before** considering message content. A `DiscordTextEvent` is typed data supplied by a future independently authenticated adapter, **not an authenticated message on its own**.
- Screens strict Discord message/channel snowflake types and bounds, text-only content, malformed surrogate text, empty text, NUL, and a configurable upper bound (1–4000 Python characters). No attachments, embeds, threads, slash commands, voice, server messages or group DMs are supported by this slice. The upper bound is an internal safety choice, **not a claim about Discord's current API limit**.
- Provides an optional bounded, locked, process-local `InMemoryReplayLedger` keyed by bot/channel/message IDs; a keyed content digest distinguishes an identical retry from the same ID with changed text. The ledger stores no raw message text. `CLAIMED` indicates only a transient ledger reservation, **not processing or delivery**.
- Does not mutate Sofía's production SQLite database or Constitution/identity, access the network, handle credentials, call an LLM, send messages, or start a worker. There is no live bot.

## Test evidence and precise limitations

37 focused tests passed in an isolated Linux Python environment against the newly authored inbound file and a locally reconstructed equivalent of PR #5's access-policy interface. The actual GitHub checkout, exact committed-file comparison, Windows/CI, full suite and live Discord tests **have not run**. Tests cover accepted and rejected messages, owner-only access propagation, duplicated/conflicting IDs, capacity, parallel claims and restart clearing the ledger. These tests do **not** establish true gateway origin, privacy at the Discord platform, crash recovery, or end-to-end delivery.

## Required before a live receiver or reply

1. Reconcile and independently test the exact GitHub branch with INTERACT #2, MEM #9, SAFE #18, NET #11 and CORE. Complete the existing live INTERACT/quality and memory privacy release gates first. Keep the bot disabled until explicit approval.
2. Choose the supported Discord bot/API library, provision the actual bot/application and securely bind Sparks's exact account and the bot ID. Never select an account by name or place a token, account IDs, or secret in Git/chat/logs. Authenticate events at the trusted gateway/library boundary; an `authenticated_source` boolean is not proof.
3. Replace or supplement the **process-local ledger** with an atomic, durable, source-linked inbox/outbox and documented recovery, idempotency and retention behavior. A crash after a claim currently loses the claim; starting a new instance can claim the same ID again. Add backpressure and cancellation at the real transport and host-owned STOP gate.
4. Integrate with the existing single logical Sofía conversation/INTERACT runtime and authorized MEM session. Do not spin up an independent identity, memory DB, bot cognition loop or second permission system.
5. Verify Discord gateway reconnect/heartbeats, REST rate limits, delivery acknowledgments and delivery-failure states, and current bot/intents/API requirements against official Discord documentation. Run supervised live owner DM, other-user/server/group denial, restart, replay, long-message and cross-client STOP/privacy tests. An API acceptance does not prove a user read a DM.
6. No general internet browsing/search until Discord D0–D4 and real 24/7 RUN acceptance. No general multi-user access or spontaneous outbound messages in this initial release.

**Next coding slice:** host-verified adapter and durable inbox contract, still offline/test-first; avoid attaching a live gateway to this temporary ledger.
