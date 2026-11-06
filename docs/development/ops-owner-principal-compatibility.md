# Verified owner principal at OPS execution boundaries

Migration and release rollout consume an independently authenticated exact SAFE
approval before producing temporary remote grants. Both boundaries now compare
SAFE's stable owner principal projection rather than its historical display
encoding. Legacy `Sparks` and canonical `person:sparks` receipt encodings remain
usable only with the existing durable cryptographic owner proof.

Temporary grants are attributed to the consumed `person:sparks` principal.
Their exact node/operation scopes and existing TTLs are unchanged. Both normal
completion and execution failure revoke temporary grants; a consumed approval
cannot be replayed. No caller label creates approval authority.

Tests exercise real SQLite Fleet/SAFE state and synthetic cryptographic owner
credentials. External execution is replaced by a local test boundary: these
checks do not move a workload or deploy a release to a real host. They cover
both verified encodings, stable grant attribution, cleanup, replay, forged
labels, exact-target mismatch and expiry. Existing coordinator/executor tests
remain separate. No production deployment or owner-provisioning claim.
