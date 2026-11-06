# Owner-authorized Fleet removal

Final removal is an explicitly classified NEVER_SELF_AUTHORIZED operation.
The canonical registry binds a fresh existing SAFE approval to host ID, node
UUID, proposal, previous lifecycle and exact registry revision. Actor display
text is compatibility metadata and cannot authorize the operation. In-memory
registries cannot perform protected final removal.

Approval consumption, known NET identity retirement, endpoint/grant revocation,
the terminal Fleet record and audit receipt share one SQLite transaction.
Failure preserves both trust state and the unused approval. The node UUID and
historical records remain as tombstones; the operation does not delete Core
code, memories, assets or change writer authority. A new exact approval can
clean up residual credentials on a legacy tombstone without reactivation.

The existing 64-hex-character owner-secret path remains supported; FIDO2 is
not made mandatory. Tests use disposable databases and synthetic credentials.
This implementation revokes known NET mappings, not unrelated Core Link
enrollments without an established identity mapping, and does not contact or
stop a real machine. The owner UI/tooling must use the inert
`removal_parameters()` projection through the existing approval issuer.
