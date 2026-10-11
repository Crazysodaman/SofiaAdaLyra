# CA-5502: reversible operator-reviewed historical sessions into Main

The existing `LifelongThreadStore` already owns the canonical per-principal
Main link projection with source-message IDs and original social audience.
It correctly rejects cross-audience visibility and does not duplicate
original transcript text. Historical desktop/Discord/mobile messages,
however, had no owner-reviewed way to preview, import, reject, audit and
partially roll back preexisting session history.

New production methods on the SAME canonical LifelongThreadStore:
- `preview_historical_import` returns at most 128 chronological original
  message IDs, original timestamps and previously linked IDs. It demands
  the exact authenticated principal, audience ID and audience type of the
  original source session; a shared principal is not sufficient for reading
  another channel's private messages.
- `apply_historical_import` accepts a fixed, bounded set of source IDs
  and an exact review reference. A trusted operator control plane independently
  verifies an SHA-256 request digest before starting the original SQLite
  transaction. Its explicit decision can commit links or reject the batch.
  Original session, message, timestamp, content and audience rows are never
  rewritten; existing links are preserved rather than overwritten.
- A canonical `lifelong_historical_import` receipt and associated
  `lifelong_historical_import_added` rows record which links this exact
  batch introduced. Idempotent replay returns the old receipt. A changed
  request cannot reuse the same operator review reference.
- `rollback_historical_import` requires a **new independent operator
  verification** of the selected batch IDs and deletes only exact
  source-audience links actually introduced by this reviewed batch,
  preserving unrelated/preexisting Main entries. A partial rollback is
  recorded explicitly and can be completed later.

Every reading of the linked messages continues to apply the existing
per-event social source binding check at access time. This is not approval
to distribute desktop/Discord private history to a different phone
audience: cross-channel disclosure remains prohibited until an
independently approved per-message visibility model is implemented.

No automatic historical import, UI-triggered mutation, alternate database,
host deployment or model-controlled approval was introduced. Regression
cases were authored but intentionally NOT executed. CA-5502 remains
partial pending privileged operator UI wiring, real migration dry runs,
multi-device audience/rollback acceptance and exact revision proofs.
