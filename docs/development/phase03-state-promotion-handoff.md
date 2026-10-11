# Phase 03: operator-only pointer cutover handoff

The canonical production database is **not** moved or activated by this feature. `ops.state_promotion.prepare_pending_state_pointer` uses the Phase 03 `StagedStateHome` and original `RelocationAuthorization` together with an external privileged approval callback. It checks destination, host, writer epoch floor, protected identity, and output location. It writes a new, exclusively created `*.pending.json` pointer **outside the state home**, signed with an externally controlled HMAC key.

The file cannot be used to switch a running writer automatically. The **separate privileged broker is not yet implemented**: its responsibility is to verify Windows/Linux filesystem permissions, authenticate the operator, prove the old host is fenced, validate external asset/archival recovery, advance the independent epoch floor, publish the signed pointer and restart one writer, or rollback. The existing runtime only consumes explicitly enabled signed pointers and has no silent self-promotion.

No source test, data move, power operation or live acceptance was carried out during this coding pass.
