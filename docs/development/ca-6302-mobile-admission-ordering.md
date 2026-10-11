# CA-6302: durable server order for mobile logical admission

The earlier mobile ledger provided durable request IDs and at-most-once host
dispatch but did not have authoritative event ordering. Two consecutive
messages could be sorted by untrusted phone clock rather than their actual
acceptance sequence, and a restarted client had no server-signed ordering
basis for reconnection or manual review.

The canonical SQLite `mobile_turn_receipt` now includes
`server_received_at` and per-`(device_id, presentation_mode,
credential_generation)` `server_sequence`. The sequence is allocated
atomically in the original `BEGIN IMMEDIATE` admission transaction, using
the max known sequence under a unique partial index. A failed or uncertain
request permanently consumes its sequence; it is never silently replayed
or renumbered. Completed replies include `delivery_receipt` with the
original stable request ID, source device, exact generation, server receipt
timestamp, sequence, and logical completion state. Exact duplicates return
the originally saved response and original sequence.

This is **per-mobile-audience ordered admission**. It is not yet a global
per-thread canonical sequence shared with Discord, desktop, Terra and
web, and does NOT assert exactly-once physical tool effects. Old receipts
with no source sequence remain historical unsequenced evidence; the schema
migration leaves them intact, without inventing arrival order.

No test execution, Android build, CI, device enrollment, writer promotion,
host cutover or live message was performed. Source code and regression cases
were added for scope separation, replay, and uncertain gap preservation.
CA-6302 remains partially wired pending cross-transport logical event
ordering and exact-revision acceptance.
