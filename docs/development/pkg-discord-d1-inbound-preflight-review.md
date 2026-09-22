# PKG-DISCORD D1: offline inbound preflight review

**Status: offline code only; not a Discord listener or an approved live gate.** This adds `sofia.discord.inbound` and `test/test_discord_inbound_preflight.py` to existing draft Discord PR #5, without changing the access policy or enabling network access.

## What this slice does

- Runs the existing disabled-by-default, exact-Sparks-account, private-DM access check **before** considering message content. A `DiscordTextEvent` is typed data supplied by a future independently authenticated adapter, **not an authenticated message on its own**.
- Screens strict Discord message/channel snowflake types and bounds, text-only content, malformed surrogate text, empty text, NUL, and a configurable upper bound (1–4000 Python characters). No attachments, embeds, threads, slash commands, voice, server messages or group DMs are supported. The upper bound is an internal safety choice, **not a claim about Discord's API limit**.
- Provides an optional bounded, locked, process-local `InMemoryReplayLedger` keyed by bot/channel/message IDs. A keyed content digest distinguishes an identical retry from an ID with changed text. The ledger stores no raw message text. `CLAIMED` indicates only a transient reservation, **not processing or delivery**.
- Does not mutate Sofía's production SQLite database or Constitution/identity, access the network, handle credentials, call an LLM, send messages, or start a worker. There is no live bot.

## Test evidence and precise limitations

**Tests are authored and committed but HAVE NOT BEEN EXECUTED for this new D1 slice.** The test file contains parametrized cases for accepted and rejected messages, owner-only access propagation, duplicated/conflicting IDs, capacity, parallel claims and process-local reset. Exact GitHub checkout, Windows/CI, full suite, real Discord gateway, and live DM have **not run**. Prior PR #5 reports 26 earlier offline access-policy tests on equivalent isolated code, which do **not** cover this new slice. No claim of gateway authenticity, Discord platform privacy, crash recovery, or end-to-end delivery is established.

## Required before a live receiver or reply

1. Reconcile and independently test the exact branch with INTERACT #2, MEM #9, SOCIAL-minimum, SAFE #18, NET #11 and CORE. Complete the live INTERACT/quality and memory/privacy release gates. Keep the bot disabled until explicit approval.
2. Choose a supported Discord bot/API library, provision the bot/application and securely bind Sparks's exact account and bot ID. Never select an account by name or place a token in Git/chat/logs. Authenticate at the trusted gateway/library boundary; a boolean is not proof.
3. Replace or supplement the **process-local ledger** with an atomic, durable, source-linked inbox/outbox and documented recovery, idempotency and retention. Restart clears the current ledger; a new instance may claim the same ID again. Add backpressure and cancellation at transport and host-owned STOP gate.
4. Integrate the existing single logical Sofía conversation/INTERACT runtime and authorized MEM session. No independent identity, memory DB, bot cognition loop or duplicate permissions.
5. Verify Discord reconnect/heartbeats, REST rate limits, delivery acknowledgments/failure states, current bot/intents/API requirements against official Discord documentation. Run supervised owner DM, other-user/server/group denial, restart/replay, long-message and cross-client STOP/privacy tests. API acceptance is not proof of user read.
6. No general internet browsing/search until Discord D0–D4 and real 24/7 RUN acceptance; no multi-user or proactive DMs in initial release.

**Next coding slice:** trusted adapter and durable inbox contract, offline/test-first. Never attach a live gateway to this temporary ledger.
