# CA-6405: Cross-modal source receipts owned by Presence

The existing `PresenceInitiativeEngine` already stores canonical typed
`WorldObservation` values in `sofia.db`, including original source,
observation time, expiry, confidence, epistemic status, availability and
audience. The six perception modalities previously had no single bounded
source receipt that could consistently state how original bytes were
accessed, how much confidence belonged to interpretation rather than
ground truth, and who could inspect the source.

Production code adds typed `CrossModalObservationReceipt` metadata
for voice, screen, environment, Fleet, app and web. It validates a
non-inferred original's real source/time/expiry against the existing
`WorldObservation`, and distinguishes source observed-at from host
received-at. It records original-data access as one of verified reference,
not retained, or unavailable. Privacy is public, personal, private or
protected; optional interpretation confidence is finite and bounded.

`PresenceInitiativeEngine.observe` atomically persists the receipt
alongside the original observation in the SAME canonical SQLite
transaction. Matching replay is idempotent. Changed source metadata
cannot overwrite a prior receipt. Legacy world records lacking receipts
remain honest missing-receipt evidence; no fabricated provenance is
backfilled. Expired overflow prunes its corresponding source receipts.

`source_receipt` permits audience-bound metadata reads only within the
original observation audience. A private/protected observation lacking
audience context fails closed. A receipt is NOT an authorization to
download original bytes, assert perception the sensor never performed,
override model uncertainty, or grant consequent action permissions.

This is a production schema/source owner implementation for part of
CA-6405. Actual adapters for every sensor modality, original-source
authentication, contradiction handling and full host acceptance are
still outstanding. Regression tests written only, not executed.
