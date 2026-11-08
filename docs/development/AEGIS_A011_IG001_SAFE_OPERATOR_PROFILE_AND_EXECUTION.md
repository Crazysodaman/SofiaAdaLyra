# A-011 | IG-001 canonical SAFE operator and native status contract

**Status: SOURCE DEVELOPMENT / UNVERIFIED HOST.** Team A #241 remains isolated.
No second service/owner authority, signing key, installer or SQLite writer.
All production Hub/Core, arbitrary native install and peer effects remain OFF.

## B -> A -> C live profile: static trust and dynamic process are distinct

1. **Publisher and install provenance (Team B):** independently verify the
   complete signed offline B1 package, signer/root/revocation, installed Rust
   supervisor, bundled Python worker and immutable Platform installation
   identity. A signed package is NOT proof the current process is that binary.
2. **Actual OS authority (Team B + canonical A runtime):** private baseline
   `/run/aegis-platform` or `/run/aegis` = service UID:primary GID, directory
   `0700`, socket `0600`, never an external operator success. Only after
   explicit owner-approved B installation configure `/run/aegis-platform`
   service UID:`aegis-mgmt` GID `0750` and socket `0660`. Retain B
   `Group=aegis` only with verified supplementary service membership
   `aegis-mgmt`, or use a reviewed effective group. Revalidate the real
   `/proc/<worker PID>/status` Groups and socket dev/inode after every restart.
   Any incorrect owner/group/mode is a REFUSE, not a chmod/chgrp opportunity.
3. **Live worker PID (A/B):** Rust `systemd MainPID` is the *supervisor*;
   the AF_UNIX management listener belongs to the separate **Python worker**.
   The A client’s `installed_service_pid` argument and C native SO_PEERCRED
   PID check MUST use the current Python *worker PID*, not the supervisor
   MainPID. This value is dynamic after a crash or service restart: the
   static publisher-signed package cannot attest its future PID. Supply it
   only from an independently verified current systemd/supervisor RUN
   attestation bound to the pinned B package and A Platform ID/generation.
   A-011 now refuses an external 0750/0660 group-mode connection if no
   trusted live worker PID is supplied; private 0700 remains unchanged.
4. **Owner approval (A only):** `CurrentManagementPeerAuthority` reads the
   current canonical `PermissionStore` for an EXACT signed standing grant
   `platform.management.read` with scope:
   `{"platform_id":<canonical UUID>,"peer":"unix:uid:<kernel UID>:gid:<kernel PRIMARY GID>","operation":"platform.status"}`.
   The approval must be a one-use `safe.permission.standing.grant`
   fingerprint binding exact grant_id, scope and expiry through
   `ExecutionApprovalVerifier.record` and `PermissionStore.grant` in
   canonical SQLite. Creation, revocation and STOP resume require separate
   freshly authenticated owner actions; no direct DB inserts or CLI-owner
   flags. Same group membership **never** grants SAFE access.
5. **Current owner-secret blocker:** `OwnerSecretStore.authenticate`
   calls `require_venus_interactive_windows`; it cannot authenticate the
   existing attended 256-bit software secret on a Debian worker. There is
   not yet an independently verified *cross-host* portable approval channel
   into the Debian canonical SAFE ledger. The existing P-256 WebAuthn
   owner test fixture provisions a synthetic credential and is explicitly
   NOT production owner enrollment. B/A/E must resolve a secure
   owner-approved transport and single-writer consumption before genuine
   external enrollment is claimed. No owner secret may be shipped to Debian,
   printed, put into argv, or replaced with a fabricated approval row.
6. **Read-only consumption (Team C):** after independent static package
   admission AND current runtime identity/SAFE enrollment, read only A
   `platform.status` with exact request ID, generation, bounded observation
   and typed STOP/stale denials. The remote service rechecks SAFE/STOP before
   and after any observation. Unknown/revoked kernel principals get EOF.
   Socket inode replacement, worker PID change, expired generation or
   unauthenticated metadata return unavailable and require re-attestation,
   never silent retry, offline-as-ready or UI-side owner authentication.

## Actual A-011 source corrections

- `src/sofia/sdk/platform_management_client.py`: external management
  group requires pinned live worker PID **before connecting**.
- `test/test_sdk_platform_management_client_linux.py`: missing-PID
  group-mode negative must receive a local PermissionError without
  sending a request.
- `src/sofia/platform/run/management_unix_listener.py`: a runtime
  loss of canonical RUN/SAFE status in the dispatcher returns EOF, not a
  thread-terminating unhandled RuntimeError or traceback disclosure.
- `test/test_run_management_unix_listener.py`: subsequent request still
  works if the canonical owner status is restored, with no second listener.

These are committed source and tests; **original repository pytest on
A-011 SHA is NOT EXECUTED** in this environment. No new service/authority
or permission broadening has been implemented.

## Reproduce on E's explicitly approved exact combined source checkout

```bash
git rev-parse HEAD
python -m pytest -q -s \
  test/test_sdk_platform_management_client_linux.py \
  test/test_run_management_unix_listener.py \
  test/test_platform_management_safe_service_e2e_linux.py \
  test/test_platform_service_management_ipc.py
cargo +1.88.0 test --locked -p sofia-contracts \
  shared_29_case_rust_python_management_wire_corpus -- --nocapture
cargo +1.88.0 fmt --all --check
cargo +1.88.0 clippy --workspace --all-targets --locked -- -D warnings
```

Report per-test true PASS/FAIL, exact checked-out source SHA, first failing
assertion, and sanitized TEST-ONLY receipt. Then separately witness an
**actual signed B-installed Debian12** systemd service and attended external
approved operator. No A/C contract ACK, installed-host or release PASS
without that evidence. Preserve Rust initial handshake 12 s, steady health
5 s, native startup 15 s and D guest deadline 45 s.

Prior Python 29/29 observed source corpus blob
`b63eeafe40b7895468f7ac8e0060c3bebfababa9` still unchanged;
Rust verdicts still UNEXECUTED in A's local environment. Original release
acceptance 0/38; Library 0/16; **NO-GO**.
