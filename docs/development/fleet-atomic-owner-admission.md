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
