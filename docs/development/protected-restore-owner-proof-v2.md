# Protected restore owner proof v2

The previous restore approval CLI and ledger trusted a `Sparks` label and
assumed an authenticated operator. Two regressions reproduced unauthenticated
receipt creation before this change. A label now supplies compatible metadata
only; it cannot mint or revoke replacement authority.

The existing external restore ledger now reuses SAFE's exact execution approval
verifier, cryptographic owner credentials and audit chain. No second permission
system or canonical Core writer is introduced. The ledger remains outside both
the protected state home and backup archives, so replacing canonical state does
not roll back receipt consumption or its owner proof.

A pending restore receipt must reference an independently authenticated,
unconsumed `ops.restore.replace_protected` approval in that same external
ledger. `replacement_parameters()` supplies the exact target pathname, backup
ID and verified manifest digest for the existing attended SAFE approval issuer.
The default 64-hex owner secret path works without an enrolled FIDO2 credential;
existing verified FIDO2 receipts remain supported. First credential enrollment
still uses the existing independent owner ceremony. No credential is provisioned
or migrated automatically by opening a ledger.

`restore-approve` requires `--owner-approval-id` in addition to its existing
archive/key/target arguments. Its effective receipt window cannot exceed the
owner approval window, and the CLI reports the stored effective expiry.
Recording/preflight does not spend the proof. Immediately before publication,
current owner proof and receipt are consumed in one external SQLite transaction.
Expiry, credential revocation, secret rotation, wrong scope, another ledger or
replay refuses publication. Audit failure rolls back both consumption records.
No raw secret is accepted through argv or written into Fleet traffic.

Revocation similarly requires an exact authenticated
`ops.restore.receipt.revoke` approval in the external ledger.
`restore_revocation_parameters(receipt_id, reason)` supplies its parameters;
`restore-revoke` takes the corresponding `--owner-approval-id`. Caller actor
labels never override the consumed principal in audit evidence. The existing
independent emergency STOP remains available through its established path.

Version-1 records and history are preserved. Migration marks unspent legacy
name-only receipts revoked with a system reapproval reason and an audit event;
it does not promote them to authenticated authority. Fresh owner approval and a
new receipt are required. The markers also keep legacy pending receipts blocked
if old code is rolled back. New records use the canonical principal encoding.
Unknown schemas or missing v2 binding tables are refused without repair.

Tests use disposable state, synthetic owner credentials and encrypted test
archives. They include the real restore path with secret rotation after
preflight and verify that no restored database or plaintext staging directory
is published. This does not establish real-host G8 or production acceptance,
first-owner enrollment, or permission to move Sofía's protected state.
