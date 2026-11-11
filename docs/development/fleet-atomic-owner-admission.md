# Canonical Fleet admission transaction

`FleetEnrollmentService.enroll` treats `FleetEnrollmentApproval` as an untrusted
reference, not authentication. Actor display text cannot grant trust. The
current service requires a canonical SQLite Fleet registry and exact HTTPS
endpoint, rechecks the durable discovery record, and consumes the existing
SAFE verifier's exact one-use authenticated approval.

One guarded database transaction contains approval consumption and its audit,
NET identity and endpoint admission, the Fleet record's compare-and-swap and
lineage, and a principal-attributed enrollment receipt. Failure at any write
rolls back all of these; the approval remains unused. The internal NET adapters
reject transactions belonging to another database. Retired identities and
revoked endpoints cannot be reused.

The in-memory registry cannot establish protected durable trust. Old direct
callers that only supplied an owner label/DTO now fail closed. The existing
`OpsToolService.enroll_candidate` request shape is preserved and uses the
transactional path. Historical approval encoding remains supported by SAFE;
new enrollment attribution uses its verified canonical owner principal.

Cache publication and notifications happen after commit. A notifier failure
cannot undo admission and must not be interpreted as permission to replay the
effect; the caller can re-read durable Fleet status. Notifications are not a
durable outbox. This slice does not implement first-install key provisioning,
TLS certificate issuance, arbitrary owner provisioning, or a Rust registry.

## Policy-governed automatic admission

`FleetEnrollmentService.enroll_under_policy` is an additional path, not a
replacement for `enroll`. It is available only under an active,
owner-established `high_autonomy` policy that explicitly enables automatic
Fleet admission. The candidate must still be an untrusted discovery record with
matching machine binding, authenticated peer evidence, node key, and exact
approved HTTPS endpoint.

The additional requirement is a short-lived Ed25519 installation attestation
from a signer that is both independently trusted and named by the owner policy.
The attestation binds the installation identity, node UUID, public-key SHA-256,
release manifest digest, signer key ID, issuance, and expiry. Policy and grant
are re-resolved inside the same transaction that writes identity, endpoint,
Fleet trust, and audit. The recorded actor is `policy:<policy_id>`, and the
audit receipt includes the policy revision, attestation digest, signer, and
bounded initial permission level.

If the policy is absent, revoked, tampered with, or no longer enabled, the path
fails closed and no trust is written. Discovery, mTLS, hostname, or LAN presence
never substitutes for the policy and signature. Permanent removal and
trust-policy changes have no automatic path. See
[Security Profile C](aegis-security-profile-c-high-autonomy.md).
