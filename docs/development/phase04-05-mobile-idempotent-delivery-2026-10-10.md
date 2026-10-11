# Phase 04 / 05: mobile at-most-once delivery journal

Source owner: existing `MobileCompanionGateway` and Android `SofiaApi`
over the canonical `sofia.db`. No new platform, worker or parallel
conversation authority was added.

## Audited behavior

A 120-second Android HTTP timeout could occur after the server saved a user
message, model result or downstream effects. Retrying the same text against
`/v1/mobile/chat` previously made a second, unrelated turn because there
was no request identity. The Android failure path displayed a warning but
the host could not independently recognize a duplicate.

## Production correction

Each Android chat request now carries a bounded client-generated request ID.
Before dispatch, the host creates a committed `mobile_turn_receipt`
`processing` record, bound to the exact device, private/shared mode and
SHA-256 of the original message. On completion it durably stores the exact
serialized response in the same canonical database.

- Exact duplicate + completed receipt returns the same response, without a
  new model call, message, tool execution or external action.
- The same ID with different message/device/mode returns authenticated 409.
- Crash, cancellation or failure after admission leaves an uncertain receipt.
  The host refuses to re-execute it, including across service restart.
- The current private-chat SAFE grant is enforced even for receipt replay.
- The Android client keeps the same ID for an unchanged ambiguous draft and
  never automatically retransmits; users can consult canonical Main history
  to resolve uncertain delivery before altering the draft.

This is **at-most-once dispatch**, not guaranteed exactly-once end-to-end
message delivery. Receipt creation, conversation commit and receipt settlement
are not one SQLite transaction across the LLM or external tools. If the host
crashes between steps, it correctly abstains from potentially duplicating
an effect rather than claiming success.

This server contract requires upgraded mobile clients to send `request_id`
on the existing `/v1/mobile/chat` endpoint. Older Android clients require
an update to continue sending chat. This is intentional fail-closed behavior
rather than keeping an insecure duplicate-dispatch fallback.

**Not claimed**: independently authenticated pairing credentials per phone,
mobile offline outbox or causal reconciliation, full cross-client Main
history, any test/Android build/host verification. Regression code authored,
but execution remains deferred as explicitly instructed.
