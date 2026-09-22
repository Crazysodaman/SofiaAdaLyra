# PKG-DISCORD: architecture, contracts, and acceptance plan

**Planning date:** 2026-09-22. **Status:** design proposal on the isolated Discord draft branch; NOT merged, deployed, enabled, or live-tested. The authoritative `main` roadmap has 19 packages; Discord is a cross-package workstream, NOT a new twentieth package. This document expands its D0–D4 stages without replacing INTERACT #2, MEM #9, SOCIAL-minimum, NET #11, SAFE #18, ACT #15, RUN #3, UI, CORE or VERIFY #8. Reconcile their actual revisions and contracts at integration time.

## 1. Product behavior and release boundary

The initial release supports exactly ONE manually enrolled, independently authenticated Discord account belonging to Sparks, communicating in an ordinary private bot DM. Text messages are reactive only. The channel exposes one *logical* Sofía identity, constitutional/policy authority, conversation service and protected memory boundary; it is not a second model personality, autonomous runtime, SQLite copy or permission system. The CLI continues to work independently if Discord is unavailable.

The first release MUST NOT: allow another account, guild channel, group DM, webhook or bot speaker; send unsolicited DMs; infer that a person is online, reading, or missing from Discord silence; read attachments, embed URLs, perform searches, execute filesystem/shell/robot actions, install host services, auto-enroll accounts, or grant any capabilities merely because text asks. Slash commands, reactions, voice, rich avatar, public servers, general second-user relationships and proactive contact are future opt-in slices, not launch blockers for private text.

A future SOCIAL expansion may enroll other people by explicit, auditable per-principal policy; the canonical Sofía personality remains one while private memory, preference, relationship, and audience-scoped content stay isolated. No other user may impersonate Sparks or gain his tool authority by mentioning him or repeating his instructions.

## 2. Responsibility map (no duplicate owners)

| Owner | Owns | Cannot infer from a Discord message |
| --- | --- | --- |
| CORE | canonical identity, grounding, runtime composition | that a Discord client is a new Sofía |
| INTERACT | one conversation/response path; cross-client stop semantics | consent, sensing, physical contact or LLM-based permission |
| SOCIAL minimum | independently authenticated actor and private audience binding | principal identity from username/display name/claimed role |
| MEM | durable originals, source revisions, authorized session mapping, deletion/correction/retention | other users' memories or private workbench entries |
| NET | outbound Discord-only transport permission at a trusted boundary | general browsing/search or arbitrary URLs |
| UI / Discord adapter | authenticated gateway client, typed envelopes, send adapter, actual API results | API success equals user-read |
| SAFE | secrets, enrollment/revocation, recipient/audience checks, STOP, privacy, outbound policy | text/boolean flags as authentication |
| ACT / REL | optional evidence-backed outreach candidate and relationship context | permission to send from an emotional cue or absence alone |
| RUN / OPS | supervised process, health, single active sender, durable failover discipline | work or thinking during downtime |
| VERIFY | revision-pinned offline/integration/live/negative evidence | that a mocked test is a live Discord acceptance |

## 3. End-to-end inbound path

`Discord gateway over authenticated bot connection -> trusted adapter verifies source and bot session -> parse canonical snowflake IDs, channel type and actual recipient -> SAFE/SOCIAL exact account and active-session policy -> bounded text screen -> durable inbox transaction (unique application/bot + channel + platform message ID) -> map to authorized MEM principal/session -> existing INTERACT conversation service -> authorized candidate response -> durable outbox -> final SAFE/STOP/recipient recheck -> Discord send adapter -> record platform result`.

Trusted adapter sets `authenticated_source` only after establishing it is processing an event from its own authenticated library connection; the boolean in `access.py` is NOT a stand-alone verifier. Discord JSON snowflakes are strings in typical API payloads: the adapter must parse strictly to the policy's bounded integer ID type, never trust a numeric ID asserted in message content. Bind an immutable bot/application ID and exact enrolled owner ID from host-managed configuration. Validate message's *actual DM channel* through trusted library/channel metadata, not a free-form label. Do not accept edits, deletes, interaction callbacks or other event types as new user messages without independent policies.

The currently committed `inbound.py` is OFFLINE preflight only: a 4,000-Python-character inbound screen, no attachment support and a bounded process-local replay ledger. Its ledger loses claims on restart and MUST NOT be connected directly to a live listener. Implement the transaction-backed inbox first; a message is not durably accepted until the transaction commits.

## 4. Durable data and state contracts

Logical records (reconcile with existing MEM/ACT schema rather than adding an unreviewed second database):

- `discord_enrollment`: canonical principal ID, Discord account ID, bot/application ID, permitted DM scope, enabled/revoked state, revision and independently verified enrollment evidence. Secure host configuration holds token/secret, not message text or Git.
- `discord_channel_binding`: bot ID, DM channel ID, principal, authorized MEM session ID, revision, current STOP/mute generation and privacy scope. Creating this binding is host-authorized, not model-generated.
- `discord_inbox`: platform event/message ID, authenticated author/channel/bot, timestamp with source and host-receipt time, content/provenance reference, state, attempt count, handling generation and unique `(bot_id, channel_id, message_id)` key. Preserve exact original when retention policy allows; treat edits/deletes as independent provenance events.
- `discord_outbox`: stable internal response ID, triggering inbox ID (or later separately authorized ACT proposal), audience/DM destination, payload revision, correlation/nonce where supported, delivery state, attempts, last error and platform message ID after accepted send. Never conflate queued, send-attempted, API-accepted and user-read.
- `discord_session_state`: explicit host-owned STOP/mute/revocation, recipient and policy revision; every final outbound attempt must check it in the same guarded path used by CLI stop semantics.

Inbox state proposal: `received -> accepted -> processing -> response_prepared -> complete`, with explicit `rejected`, `failed_retryable`, `failed_terminal`, `cancelled`; use leases/attempt IDs to recover a worker crash and prevent simultaneous processors. Duplicate gateway deliveries consult the UNIQUE key and original payload fingerprint; exact duplicate is a no-op, same ID with conflicting content is quarantined for audit. Race-safe processing uses transactional claim, not an in-memory mutex across processes.

Outbox state proposal: `prepared -> authorized -> sending -> platform_accepted`, plus `retryable_failure`, `terminal_failure`, `cancelled`, `outcome_unknown`. An HTTP timeout after bytes were sent can be `outcome_unknown`: **never blindly resend** without a supported idempotency key or independent reconciliation. If the chosen Discord route/library supports a nonce/enforce-nonce mechanism, verify its exact documented behavior and scope before using it; it is not blanket exactly-once delivery. Recheck recipient, STOP generation, expiry and authorization immediately before each send/retry; a cancelled message does not become sendable again after reboot.

A Discord platform message ID is evidence of platform acceptance, not proof of delivery to the user's device or that Sparks read it. If the platform cannot establish a read receipt, the read state remains unknown. Recovery and backup must verify committed originals and outbox state, not assume two databases written in parallel are consistent.

## 5. Transport and operational behavior

Use an official supported **bot account**, never a self-bot operating Sparks's personal account. Choose and pin a maintained Python Discord library only after checking its current Gateway, intents, DM and send semantics. Request the minimum intents/permissions necessary for owner DMs; do not enable guild content capture or presence just in case. For a private DM, do not require a publicly accessible inbound webhook or open router port when using an outgoing gateway connection; confirm this with the selected deployment transport.

Connection lifecycle: `disabled -> starting -> connecting -> ready -> degraded/reconnecting -> stopped/failed`. Gateway session identification, heartbeats, sequence tracking, resume when supported, reconnect backoff + jitter, loss of session and cold reconnection must not fabricate missed messages or replay a response. Discord REST sends obey server-returned rate-limit headers/retry times; bounded queues, timeout budget, concurrency limit and per-principal FIFO or explicit ordering policy prevent runaway requests. Handle invalid-token/permission-revoked failures as stop conditions rather than hot retry loops.

Single sender/leader per enrolled bot identity: host-managed lease/epoch/fencing before enabling the worker. Eos, Artemis and any future failover host must not each start an independently sending Sofía. Readiness requires authenticated gateway plus durable inbox/outbox access and healthy shared runtime; process running != available to chat. Surface state in supervised diagnostics and, if permitted and actually connected, an honest Discord presence. Do not claim continuous thinking, presence, or uptime from a status indicator.

NET permits only validated Discord Gateway/REST destinations and minimum transport dependencies such as DNS/TLS as verified for the selected library. Redirects, proxies, alternate hosts, attachments/CDN, webhooks, general HTTP clients, crawling and search remain denied unless a separate, reviewed capability explicitly expands the policy. The existing NET lexical preflight alone is NOT an egress firewall.

## 6. Response quality, formatting and user experience

Default response is text, natural Sofía voice and the same conversation engine as CLI. Preserve the original user text and channel provenance; represent Discord quote/reply context as *data* with source links rather than high-priority instruction. Source-aware MEM must retrieve only authorized relevant context. No automatic channel-wide memory promotion or private reflection disclosure. Don't dump constitution/system prompts or secret tool outputs into DMs.

Output formatter must split only at safe text/grapheme boundaries and respect the actual Discord API payload limit with margin, use `allowed_mentions` equivalent to suppress all mass/user/role pings by default, and avoid broken Markdown/code fences when chunking. Record each chunk's identity and send outcome; after a partial failure do not silently duplicate previously accepted chunks. Typing indicator is optional and truthful, never a fake sign of continuous thought. Never echo raw platform errors, secret tokens, user IDs or private file paths into the DM. When generation fails, use a concise truthful failure or nothing according to policy, not an invented answer.

**Owner-only administrative controls proposed for a later reviewed command route:** status, pause/resume Discord replies, stop an in-flight session, enable/disable optional outbound contact, inspect redacted delivery status. These controls require verified owner identity and server-enforced policy. An ordinary text string `/admin` does not grant permission and sending `/stop` from an unauthorized account cannot stop Sparks's session. Define scope carefully: pausing Discord does not necessarily stop local CLI; global STOP must apply to every channel where configured.

## 7. Optional future capabilities, all separately gated

1. **Opt-in owner outreach:** ACT/REL may propose a contextually appropriate non-clingy check-in only while actually running; explicit recipient/destination and message-type permission, evidence, local quiet hours, daily cap, cooldown, busy/stop check, expiry, dedupe and user-accessible revoke are mandatory. Absence is observed elapsed time, not proof of feeling, intent, illness or presence. No proactive message is in D0–D4.
2. **Multi-user SOCIAL:** individually verified enrollments, separate per-person private sessions/memory/relationship state, private vs shared audience labels, explicit sharing grants, cross-user privacy tests and an owner-only control plane. The same canonical identity and general personality can have contextual expression, without inventing separate identities or revealing Sparks's memories.
3. **Guild channels:** explicitly enrolled server/channel allowlist, mention/command trigger policy, per-channel audience scope and moderation/compliance review. No passive server-wide listening by default. Guild roles are not equivalent to owner authority.
4. **Attachments/links/voice/avatar:** staged parsers and media safety checks, size/type limits, malware/untrusted-document treatment, source provenance, explicit resource budget, and supported API permissions. A pasted URL is just text until a separately authorized KNOW/NET retrieval capability exists.
5. **Runtime notifications:** only verified, authorized OPS/RUN/VERIFY events, concise deduped reports. Critical failures use explicit escalation policy and alternate approved channels; if Discord is offline, record unsent status instead of claiming the notification succeeded.

## 8. Build sequence and exit criteria

| Gate | Deliverable | Evidence needed |
| --- | --- | --- |
| D0: reconcile and provision | Pin exact branch revisions; verify CORE/INTERACT/MEM/SOCIAL-minimum/SAFE/NET contracts, choose host/library, secure token manager, exact enrolled IDs and privacy policy | Reviewed design, negative access tests, explicit Sparks approval for provisioning; no real secret in repo |
| D1a: offline ingress | Current `access.py` + `inbound.py` plus tests | Execute focused tests on EXACT committed tree on target Python/Windows and CI, inspect source; current new D1 tests have NOT run |
| D1b: durable receive | Trusted gateway adapter, channel/actor proof, atomic inbox, reconnect and backpressure | Fake gateway, crash/restart, concurrent duplicate/conflict and real supervised owner/non-owner DM tests |
| D2: shared response and send | Existing INTERACT/CLI continuity, MEM original retrieval, outbox and receipt adapter | One accepted input yields at most one logical response; actual accepted platform IDs/chunk accounting; ambiguous send fault test |
| D3: privacy and stop | Revocation, cancel, secrets/retention, owner-only administrative controls, cross-channel stop | Wrong-user/guild/group/bot/webhook/prompt injection tests; in-flight STOP and retry after revocation tests |
| D4: supervised acceptance | Pinned full suite, source-backed context review, reconnection/restart/recovery, CPU/RAM/latency measurements, rollback | Human-reviewed real DM and CLI continuity, negative-security evidence, separate Sparks release approval |
| RUN later | Supervised always-on service/failover | Verified soak, external watchdog, single leader, audited restore/failover and accurate downtime reporting |

**Release gate:** Discord remains disabled until D0–D4 and upstream CORE/INTERACT/MEM/SOCIAL-minimum/SAFE/VERIFY requirements are satisfied on the actual integrated revision. No automatic merge, deployment, production DB migration or general web/search grant. General search follows real Discord acceptance and independently verified 24/7 RUN, not merely a green unit test.

## 9. Open configuration decisions (defaults until Sparks chooses)

- Execution host: Eos vs Artemis vs approved separate service; **undecided** until OS, runtime, resource/network and failover checks. Do not assume running on Venus while gaming is acceptable.
- Bot account, exact Sparks account ID, DM channel binding and secret store: **not provisioned here**. Request via secure host setup when D0 is actually authorized, not in chat or Git.
- Retention: policy must specify source original, edits/deletes, audit metadata, backups, export/deletion and recovery. Default to restricted local access, no cross-user sharing and no new automatic memory promotion.
- Proactive contact: **off**; quiet hours and caps only matter once separately opted in.
- Attachment/voice/guild/multi-user: **off**; broad Internet and web search: **off**.
- Discord availability and continuity SLOs, measured latency budget and queue capacities: establish from actual host/LLM benchmarks, not invented promises.

## 10. Next concrete engineering slice

On this draft branch, first run `python -m pytest -q test/test_discord_single_user_gate.py test/test_discord_inbound_preflight.py` against the exact checkout, fix any real failures, then design/test a **durable inbox interface and authenticated-adapter boundary** without contacting Discord or modifying the production database. Review the new branch changes against current `main` and INTERACT before integration. Keep D1 transport activation and any bot credentials for a separately approved supervised step.
