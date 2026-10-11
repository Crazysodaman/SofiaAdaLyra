# Phase 03: signed canonical state-home discovery

**Code committed, not tested.** RuntimeStorageLayout retains its existing default paths when new environment settings are absent.

On approved production cutover only, the host may set these *together*:
- `SOFIA_STATE_HOME_POINTER`: externally stored JSON location record
- `SOFIA_STATE_HOME_POINTER_KEY`: externally stored 32-byte HMAC key (OS-protected)
- `SOFIA_WRITER_HOST_ID`: exact approved writer-host identifier

`read_verified_state_home` authenticates the pointer with an HMAC, checks writer host, epoch, operator approval reference, absolute local path, canonical `sofia.db` and protected identity. A malformed, unauthorized, missing or tampered pointer fails closed. It never creates state, grants authority, acquires a lease, changes the canonical path or moves data.

**IMPORTANT:** This is only the *bootstrap half* of relocation. There is deliberately no API here that signs arbitrary locations. A separate privileged operator-controlled offline migration must first fence the old writer, verify a full encrypted backup and staged restore, check assets/ACLs, issue a signed epoch advancement, and provide operator rollback. A signed pointer on two hosts without fencing is **not** split-brain protection. Do not set these environment variables or deploy this path until the final tests and migration acceptance.

The exact JSON fields are `schema="sofia.state-home-pointer.v1"`, `state_root`, `writer_host_id`, `epoch`, `operator_approval_ref`, and `hmac_sha256`. HMAC signs canonical JSON (sorted keys, compact separators, UTF-8, no HMAC field), prefixed with the code's domain-separation bytes.

No legacy writers or persisted transcript/history are replaced by this feature.
