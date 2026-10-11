# V18 Mobile paired-device revocation at owner-thread dispatch

Source audit on `main` e93b749 identified a revocation gap:
`MobileCompanionServer` verified bearer scope before submitting a request
to `_WorkerMobileGateway`, but the worker's synchronized command queue could
remain blocked by an existing cognitive turn. An operator could revoke/rotate
a token during that interval. Previously the owner thread would execute the
queued operation based on an authentication check which was no longer current.

**Production boundary correction:** All six mobile POST routes now converge
through one `dispatch_authenticated` method on the canonical
`MobileCompanionGateway`. It checks the current device credential from
`sofia.db` inside the application owner-thread lock at the moment of work.
The strict operation mapping accepts only actual implemented endpoints and
valid per-route JSON schemas. In the desktop worker, the HTTP proxy forwards
this method through the existing application-owned queue; no parallel
conversation state is introduced. Revoked tokens return HTTP 401, mismatched
device IDs return 403, unknown routes return 404, and receipt conflicts 409.

**In-flight limit:** On completion, the HTTP handler rechecks the token and
suppresses the response for newly revoked credentials. Operations already
committed before revocation cannot be retroactively undone. The existing
durable mobile-turn receipt preserves dispatch identity and uncertainty
instead of encouraging a duplicated replay.

Only source code and unexecuted regression tests were authored, including
revocation while queued and revocation after operation but before HTTP reply.
No CI, Android build, live pairing, host database move or deployment performed.
Canonical writer host remains undecided. The complete V18 cross-transport
authorization and offline synchronization work remains open.
