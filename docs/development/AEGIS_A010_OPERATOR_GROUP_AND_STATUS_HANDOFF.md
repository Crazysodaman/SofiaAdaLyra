# A-010 / IG-001 | One canonical Platform service, read-only enrolled operator contract

**State: DEVELOPMENT EVIDENCE ONLY. IG-001 installed-host GO = NO.** No second
Platform service, no second owner-grant authority, no change to `main`,
no production effect, Hub/peer transfer, install/activate, or personal Core.

## Scope and immutable wire

Existing v1 request: `aegis.platform.management.read.v1`, protocol `1.0`,
exact `platform.status`, request ID, expected current RUN generation,
target Platform identity, created/deadline. Server must recheck the
same real SAFE grant, owner STOP, installation ID and lease generation
before AND after observation. Reply:
`aegis.platform.management.read-response.v1`, exact matching
request/target/generation, current <=5 s observation, explicit data/null
and `DENIED` typed code; unknown/revoked OS peer gets **EOF**, not status.

Immutable Git blob IDs from the A candidate:
- 29-case wire corpus `b63eeafe40b7895468f7ac8e0060c3bebfababa9`
  (9 ACCEPT, 20 REJECT).
- Valid platform status request
  `adffc68fcfe2e54ab9e962dba601412a7eb31efd`.
- Strict Python read parser
  `8e18a4f509498ae1dbb53fe251736b73448d8d5b`;
  strict Python response parser
  `69b5a375dc14453572dcca5a7ff6885de3b069d7`.
- Rust management parser at prior A head
  `608b6966169441df8688c83b37d5bca9a6bdc602`.
- No 29-vector rewrite, no newly allowed denial or protocol downgrade.

## Reconciled Debian 12 runtime, only Team B may provision

Team B's current native systemd seed has `User=aegis`,
`Group=aegis`, `RuntimeDirectory=aegis-platform`,
`RuntimeDirectoryMode=0700`. A **accepts this as private only** with
`/run/aegis-platform` owner = service UID, group = current effective
service GID, directory `0700`, socket `0600`. External operator access
MUST fail. Do not reuse `/run/aegis` as a group-exposed endpoint.

To opt in to a **separately approved external operator**, B must sign and
install the *existing canonical unit's* dedicated `aegis-mgmt` group,
its current owner-granted operator membership, and exact runtime ownership
and mode **before** A's service starts:
- `/run/aegis-platform` owner must be the installed service UID,
  **group exactly the independently enrolled `aegis-mgmt` GID**, mode
  `0750`; socket owner must be service UID, **group `aegis-mgmt`**,
  mode `0660`. No world, broad Users/Admin or arbitrary directory.
- B may configure the service's effective group as `aegis-mgmt`,
  OR keep `Group=aegis` with **signed, explicitly verified**
  `SupplementaryGroups=aegis-mgmt` and an installer-provisioned runtime
  group. In the latter layout the service has **two distinct GIDs**:
  primary `aegis`, socket group `aegis-mgmt`. A now tests and supports
  both. Be careful: stock systemd `RuntimeDirectory` ownership follows
  the unit's effective group and may reset ownership on restart; B MUST
  prove the opted-in group remains exact after startup and reboot.
- The service must prove real group membership when opening the shared
  socket; missing/foreign group, unexpected mode, wrong service owner,
  missing signed identity, stale lease, unapproved user or changed endpoint
  denies. A must never autonomously chmod/chgrp a foreign runtime dir.
- POSIX group access is only the **first OS admission**. For each request,
  A's existing `CurrentManagementPeerAuthority` checks a CURRENT
  signed-owner SAFE grant with scope exactly
  `{"platform_id": ...,"peer": "unix:uid:<verified UID>:gid:<verified PRIMARY GID>","operation":"platform.status"}`.
  A real Linux `SO_PEERCRED` yields the operator's primary GID, not
  automatically the supplementary `aegis-mgmt` group. The grant is
  independently created/consumed by canonical owner authentication; UI,
  installation scripts or the client cannot assert it. STOP, revocation
  and owner-secret rotation invalidate access.
- The A Linux client
  `src/sofia/sdk/platform_management_client.py` has distinct
  `installed_service_gid` (expected SO_PEERCRED primary service GID)
  and optional `installed_socket_group_gid` (trusted signed B
  `aegis-mgmt` GID). `None` enforces private `0700/0600`; a
  provided group pin enforces `0750/0660`. A client-supplied group
  or version is **not** permission and cannot substitute for signed B
  installed-service provenance or SAFE authorizer.
- Windows: keep original individually enrolled **SidTypeUser** named-pipe
  DACL and impersonated kernel client-token checks; Team B must produce
  signed SCM installed-service / SID/DACL and second-user receipts.
  This Linux test is not a Windows test.

## Actual executed development evidence

Environment: Linux x86_64 kernel 6.18.57, Python 3.13.5,
pytest 9.0.2, container root for disposable UID/GID tests.
**No cargo/rustc toolchain**, so Rust and Clippy NOT EXECUTED.

- `PYTHONPATH=/mnt/data/aegis_a009/src python /mnt/data/aegis_a009/run_29.py`
  -> **29/29 Python verbatim-wire observed matches**, 9 accepted,
  20 rejected, same original corpus Git blob; local log SHA256
  `0103a4ef3dee7ccf4dc852d04e48ce375cca4d797ac493fd49469cc1dcee671a`.
- `PYTHONPATH=/mnt/data/aegis_a009/src pytest -q /mnt/data/aegis_a009/test/test_linux_management_client.py /mnt/data/aegis_a009/test/test_sdk_platform_management_client_cross_uid_linux.py --junitxml=/mnt/data/aegis_a010/client_tests_junit.xml`
  -> **13 PASSED / 0 FAILED**; XML SHA256
  `e8d90f515c4ca854845ed5f6ae3842476aeec6c46284234f59d1db81a544a32e`.
- `pytest -q /mnt/data/aegis_a010/test_systemd_runtime_policy.py`
  -> **2 PASSED / 0 FAILED** against extracted source-equivalent
  `systemd_management_operator_group` helper. Not the full
  application checkout; original full-checkout service tests are
  **NOT EXECUTED**.
- `PYTHONPATH=/mnt/data/aegis_a009/src pytest -sv /mnt/data/aegis_a009/test/test_sdk_platform_management_client_cross_uid_linux.py --junitxml=/mnt/data/aegis_a010/cross_uid_junit.xml`
  -> **1 PASSED** running a real separate Linux service UID 31041 /
  primary GID 31041 with supplementary mgmt GID 31044 and socket
  0750/0660; operator UID 31042 / primary GID 31042 admitted through
  supplementary mgmt GID; wrong UID, absent group, wrong group pin and
  revoked-like policy denied. Returned `STOPPED`, `STALE_GENERATION`
  and correlated OK as expected; after TEST server process restart
  old PID denied, old generation typed DENIED, new PIN/gen OK.
  Actual cross-UID stdout transcript SHA256
  `67fdfa9ff71c8d8f09d47af31c7499b61027ffccfb0e3a22dc5eb63e2853c7eb`
  from the earlier same behavior run; final spawned
  test JUnit SHA256 `79075abd8bb0dac564b624750d1c4f90de2b71abe749ff111bc4a7cb5d59f76f`.
  **This is a synthetic test-owned enrollment callback, not canonical SAFE.**

Portable disposable checkout commands for Teams B/E:

```bash
python -m pytest -q \
  test/test_sdk_platform_management_client_linux.py \
  test/test_sdk_platform_management_client_cross_uid_linux.py \
  test/test_platform_service_management_ipc.py
cargo fmt --all --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --locked -p sofia-contracts shared_29_case_rust_python_management_wire_corpus
python -m pytest -q test/test_ui_platform_management_response.py
```

Cross-UID test requires disposable Linux **root** and will SKIP
without that privilege. Test UID/GIDs and synthetic grants must NEVER
be reused for a real B installer or signed owner proof. Capturing
operator transcripts from a signed installed service and real SAFE
grant is still B/E acceptance work.

## Outstanding genuine host evidence

1. Team B delivers independently signed complete Debian12 systemd
   installation and accurate current runtime group/owner provisioning.
2. A's actual `PlatformServiceSession` with canonical
   `PermissionStore`, `CurrentManagementPeerAuthority`, owner STOP,
   RUN generation and authenticated OS socket must answer an operator
   who has consumed a REAL one-use owner-approved standing grant.
3. Team E witnesses enrolled and unknown external UIDs; owner-secret
   rotation, STOP and revoke *during* the read; stale generation,
   lease replacement, crash/forced kill; two Debian boots and single
   canonical authority. No sandbox-only grant callback accepted.
4. Team C adds verified native CLI/TUI consumption via A's one broker,
   not an independent client-assigned permission. Rust 29-vector
   parity and explicit A/C exact-SHA v1 signoff still HOLD.
5. Readiness must preserve 12-second initial worker handshake,
   5-second steady health IPC, **15-second native startup bound** and
   45-second disposable Debian VM observation. #249's pass cannot be
   copied to A's different management-listener-ready handshake.
6. D028-00 Library D00-2 remains Team D REQUEST CHANGE on complete
   signed manifest digest vs unsigned policy identity vs archive bytes.
   Other Library decisions continue separately, without blocking
   read-only IG-001 Platform status development.

**GO: NO. Original 0/38 acceptance; LIB 0/16. No main merge.**
