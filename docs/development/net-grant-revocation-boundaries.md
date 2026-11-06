# Remote grant revocation boundaries

`DistributedGateway` rechecks the trusted exact-scope authorization store after
peer authentication/discovery, immediately before dispatch, and before releasing
the remote response. The UTC time supplied by the host advances by monotonic
elapsed time during the call, so a slow transport cannot freeze grant expiry or
inventory age at admission.

Revocation, expiry or an unavailable authority store before dispatch denies the
operation. After dispatch, these conditions withhold the response and report an
uncertain outcome: effects may already have happened and automatic retry is
forbidden. The durable gateway records this distinction in its existing request
ledger, which retains replay protection after restart.

This is local orchestration enforcement. It does not atomically serialize a
remote host's execution with local revocation, recall remote effects, or replace
server-side authorization/certificate revocation. Transport authentication and
per-node trust remain responsibilities of the trusted transport boundary.

Tests use production SQLite authorization/ledger stores with a local fake
transport. They reproduce revocation during discovery and execution, advance
expiry deterministically, simulate authority-store failure, and check durable
outcome/replay behavior. They do not certify actual network authentication.
