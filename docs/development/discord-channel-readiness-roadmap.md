# Sparks-only Discord channel | readiness roadmap

**2026-09-21 | draft PR #5 | baseline head `80146352d26933a9b94c31d7281462e6ebd7868d`.** Discord is a staged **INTERACT/NET/SAFE channel**, not an extra package in the proposed 16. Companion `offline-package-coding-and-test-gates.md`, INTERACT `pkg-interact-discord-channel-contract.md` and NET PR #11. Only authenticated **Sparks private DMs**; no other users, group DMs or guild channels by default.

## Prepared and evidence

Disabled-by-default, dependency-free `sofia.discord.access` policy with exact configured sender and bot snowflakes, private-DM and verified-origin conditions; 26 focused tests passed on equivalent isolated code, **not actual live Discord**. Its `authenticated_source=True` flag must be provided only by an independently trusted adapter; it cannot authenticate itself. No bot token, gateway, send/receive, persistence or network grant has been enabled. Branch previously had temporary unrelated churn removed; inspect current diff before merge.

## D0–D4 sequential code/test gates

1. **D0 design and host/identity:** pin branch and reconcile INTERACT #2, MEM #9, SAFE #18 and NET #11 contracts. Configure actual bot/application and exact authenticated Sparks account via secure host config/secrets, never paste credential/IDs into Git PR or infer from username. Deny all other senders and channel types. Confirm requested permissions/intents are minimal.
2. **D1 receive:** implement trusted Discord gateway/API origin verification, reconnect/heartbeat and private-DM classification, message ID replay/idempotency, rate/backpressure and clear errors. Unit/mock tests cannot prove gateway provenance; test live private receive and wrong-user/server/group denial.
3. **D2 respond:** bind authorized DM to the existing conversation/INTERACT service and MEM original/provenance, no second Sofía instance or DB; implement bounded text delivery, actual API receipts, token/redaction, retry/backoff and no duplicate replies after reconnect. No proactive messages yet.
4. **D3 stop/privacy:** test revoked account/session, malformed IDs, guild/group messages, bot/webhook spoofing, injected payloads, prompt leakage, long message chunks, outages and cross-session privacy. STOP/mute and context cancellation must be host enforced. Real negative tests with separately authorized fixture account may be required; do not open general second-user access.
5. **D4 supervised acceptance:** real end-to-end DM across restart, extended reconnect/rate-limit handling, human live identity/personality/technical quality and durable original-message recovery, measured CPU/RAM/latency; pin full repo test SHA and independently approve channel activation. No public guild mode.

## Dependency and deferred questions

Sparks's actual authenticated Discord account ID, bot/app configuration, execution host and secure token manager, whether notifications/outbound are desired (default off), retention and local quiet hours require review. NET permits only Discord-required destinations until **after** D0–D4 and real externally supervised 24/7 RUN acceptance; general internet browsing/search is a separate later capability. Rich avatar art does not block D0–D4 text DM.

**Exit:** offline policy tests only. Real bot, Windows/CI/full suite, source authentication, message delivery and 24/7 operation = NOT RUN. No merge, deployment, credentials, general search or second-user activation.
