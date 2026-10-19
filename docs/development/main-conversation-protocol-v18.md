# V18 Main conversation and device-continuity protocol

Status: production contract implemented by the canonical SQLite/application
path. This document is descriptive; it grants no authority.

## Ownership

`ConversationStore` owns immutable source messages. `SocialSessionStore` owns
the source session's authenticated principal and original audience.
`LifelongThreadStore` owns the single per-principal Main projection, canonical
turn admission, server order, and reviewed historical links. It stores links,
not a copied transcript. Discord and mobile keep transport receipts in the
same configured `sofia.db`; none is a second conversation authority.

The application bootstrap and `ConversationService` are the production
entrypoints. Desktop calls the service directly. Discord first admits the
platform snowflake into its durable inbox and passes a stable event ID through
the bridge. Mobile pins the paired credential generation, device ID, request
ID, and audience before calling the same service.

## Event and ordering contract

An accepted turn binds:

- stable client/platform event ID and digest;
- owner principal, original audience and audience kind;
- original source session and channel;
- explicit device/presentation identity when the transport has one;
- server receipt time and optional untrusted client creation time;
- monotonic Main sequence plus user/assistant turn position;
- optional reply/correction pointer, accepted only within the same principal
  and original audience;
- immutable user and assistant source-message IDs; and
- a durable completed, processing, interrupted, or uncertain response receipt.

The server receipt transaction assigns order. Client clocks, copied session
IDs, display names, and LLM output never establish identity or causality.
Reusing an event ID with different content, device, audience, reference, or
other authenticated bytes is a conflict. A completed exact retry returns the
same stored logical response without invoking cognition or tools. Processing
claims are pending; interrupted/uncertain claims are not replayed. This is
exactly-once logical acceptance, not a claim that physical/network effects are
exactly once.

`ConversationService` serializes generation only within that active
conversation instance. Durable SQLite admission still arbitrates different
transports and runtimes. The lock does not block unrelated RUN work.

## View and delivery policy

Every content read revalidates the current source message and its exact
principal, audience, and audience-kind binding. Sharing the same owner ID does
not disclose private local, Discord, mobile, project, credential, tool, or
artifact content.

The strict source view omits ineligible rows. The device Main projection keeps
canonical positions visible but replaces content from another audience with
`unavailable_on_this_device`; it exposes no source session, source audience,
message ID, channel, content, tool result, or credential-bearing metadata.
Changing visibility requires a separate reviewed owner action; copying a view
never copies authority.

A response is posted only through its originating transport receipt. History
sync is a read, not outbound delivery, model regeneration, or tool execution.
Cross-channel mirroring remains disabled unless a future independently
reviewed opt-in contract is implemented. Discord platform edits/deletions do
not rewrite immutable canonical originals; an explicit same-audience
correction is a new event with a pointer. No platform deletion is interpreted
as permission to erase canonical history.

## Reconnect, cursors, and recovery

History pages are keyset/cursor bounded; lifetime history is never loaded for
a reconnect. Mobile cursors are scoped to device, presentation mode, pairing
generation, principal, and audience. A revoked or rotated credential cannot
read or acknowledge an earlier epoch. Read acknowledgement is not delivery.

Mobile and Discord keep stable transport receipts. Confirmed completion,
processing, and unknown outcomes remain distinct after restart. Unknown
external effects are never automatically replayed. Offline drafts are local,
encrypted, non-authoritative text and leave the queue only after a verified
canonical-host receipt. A reconnect conflict is owner-visible as conflict,
pending, interrupted, uncertain, redacted, or revoked; it is never silently
overwritten.

Historical sessions enter Main only through bounded preview plus independent
operator-reviewed import. Original rows, timestamps, provenance, and audience
bindings remain untouched. Reject and partial rollback are durable, and
rollback can remove only links created by that exact review.

## Task mapping

| Tasks | Production contract |
|---|---|
| CA-4106, CA-5302, CA-5505, CA-6302 | Canonical authenticated event identity, origin metadata, trusted order, references, receipts, and idempotency. |
| CA-4107, CA-5304, CA-5503 | Per-message source authorization and content-free unavailable placeholders; history never transfers capability. |
| CA-4108, CA-5504 | Origin-only response delivery; synchronization is not posting; immutable originals model later correction. |
| CA-4109, CA-5303, CA-5307, CA-6304 | Bounded reconnect pages, scoped read cursors, credential epochs/revocation, durable unknown outcomes, and privacy partitions. |
| CA-4110, CA-5306 | SQLite admission arbitration plus per-conversation generation serialization and explicit retry outcomes. |
| CA-5502 | Reviewed, reversible, non-destructive historical association. |

## Deliberately absent authority

Main event order, device pairing, read receipts, projections, imported links,
and model responses do not grant SAFE permission, consent, tool authority, or
proof that an external action succeeded. TLS termination and push transport
remain deployment acceptance concerns; this protocol does not fabricate
live-host evidence for either.
