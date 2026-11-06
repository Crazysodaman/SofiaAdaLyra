# Stable owner principals in signed DEV and EVOLVE approvals

The existing external Ed25519 approval verifiers accept the canonical current
owner reference `person:sparks` alongside the historical signed `Sparks`
reference. These labels are metadata. The configured external public key and
exact signature remain mandatory; neither spelling authenticates its bearer.
Operator CLI defaults use the canonical reference.

Signature payload formats are unchanged. Existing records and signatures retain
their original spelling and bytes. Verification compares the exact stored
reference with the submitted approval; it does not rewrite legacy payloads
before signature verification. Scope, fingerprint, time, revocation and DEV
single-consumption checks remain in force. New successful record, consume and
revocation audits use `person:sparks`. Historical audit events are not rewritten.
DEV consumption also rejects unsupported actor references even in a signed row.

This is compatibility for the currently configured owner's existing trust roots.
It does not provision arbitrary owners, install new trust anchors, replace
external signature approval with an ExecutionApproval DTO, or complete the
repository-wide principal migration. Tests use disposable generated keys only.
