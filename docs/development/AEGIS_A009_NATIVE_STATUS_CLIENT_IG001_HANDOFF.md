# A-009 | IG-001 native read-only Platform status client handoff

**Status: isolated SOURCE DEVELOPMENT, not signed installed-host acceptance.**
Team A only owns canonical management contract/Platform service. Team B
owns signed installer/operator enrollment. Team C owns GUI/TUI presentation.
Team E owns independent disposable signed host witnesses. No changes to
main, no production, Core, Hub, peer transfer or privileged writes.

## Client interface and authority

`src/sofia/sdk/platform_management_client.py` exports
`read_linux_platform_status(socket_path: Path, expected_platform_id: str,
expected_generation: int, installed_service_uid: int,
installed_service_gid: int, installed_service_pid: int | None = None)`.

All arguments MUST originate from currently authenticated and
independently signed B1 service installation and current RUN identity,
never from a discovered Hub peer, UI text field, arbitrary rootless
user process or a JSON permission claim. This function DOES NOT
enroll operators, create grants, prove publisher signature, find
the service's current generation or call an install/update executor.

It checks exact absolute socket path and symlink-free components,
service UID/GID, owner-private `0700 / 0600` or independently B-provisioned
`0750 / 0660` socket, unchanged inode before/during/after connect,
real Linux `SO_PEERCRED` service UID/GID and optionally live service
PID, 2-second bounded send/receive and a single newline JSON response.
It issues only `platform.status` with fresh random request ID,
exact target/generation and 5-second deadline; uses the original strict
`UntrustedManagementResponse.parse` for freshness/correlation/STOP
typed denial. EOF, broken pipe, wrong PID/UID/GID, symlink,
wrong socket mode, forged generation, malformed response or
stale observation FAIL CLOSED. No background retry, no mutation.

**Critical trust limit:** Linux UID/GID/PID pinning is necessary OS
service-origin evidence, NOT independently trusted signed executable
provenance, attended enrollment or current SAFE proof by itself.
The canonical server still MUST check owner SAFE/STOP/lease before
and after every read. Team B must supply independently proven signed
runtime/account/PID origins and actual second-user ACL receipts;
Team E must witness active allowed+denied operators and revocation.

Team C TUI is a native Rust client and may NOT pretend this Python
function is a compiled Rust authenticated transport. C should consume
this exact v1 request/response protocol, or a reviewed A-owned Rust
equivalent sharing the native verifier rules. Until then,
`OfflineReader` remains the truthful fallback.

## Verified local development evidence

- Linux x86_64 6.18.57, Python 3.13.5, pytest 9.0.2.
- Exact management Python SDK source blobs
  `8e18a4f509498ae1dbb53fe251736b73448d8d5b`,
  `69b5a375dc14453572dcca5a7ff6885de3b069d7`;
  immutable 29-wire blob
  `b63eeafe40b7895468f7ac8e0060c3bebfababa9`.
- Local parity: `PYTHONPATH=/mnt/data/aegis_a009/src python
  /mnt/data/aegis_a009/run_29.py` -> **29/29 exact verdict matches**
  (9 ACCEPT, 20 REJECT). Python only; Rust unavailable.
- Actual native-transport focused command:
  `PYTHONPATH=/mnt/data/aegis_a009/src python -m pytest -q
  /mnt/data/aegis_a009/test/test_linux_management_client.py
  --junitxml=/mnt/data/aegis_a009/client_junit.xml` -> **12 PASSED**.
  Source client and tests published into #241 are byte-identical to
  locally tested files (`git hash-object` matched GitHub blobs).
- Twelve disposable *same-user, synthetic service* tests cover positive
  correlated OK, typed STOP, revoked-like EOF, wrong signed UID/GID/PID,
  forged generation, unsafe socket mode/dir mode, symlink, no mutation,
  and absent service. These are NOT independently enrolled separate-user
  tests and do not certify the B1 service or live SAFE ledger.
- Native Windows SID/DACL, separate enrolled Debian operator UID/GID,
  actual current SAFE/STOP grant and revocation, signed installed-host
  service startup/reboot/kill, Rust source parity, Cargo/Clippy,
  Debian12 VM and TUI/CLI compiled-client execution: **NOT EXECUTED**.

## IG-001 next acceptance sequence

1. B signs/packages the Core-free binary and trusted metadata, installs
   canonical Debian12 systemd account, 0700 private runtime then
   separately enrolled 0750/0660 mode with exact GID, and Windows
   individually enrolled SID DACL. Do not chmod broadly.
2. A service owns the true current Platform authority, RUN generation,
   SAFE owner-grant/STOP/revocation and native listener.
3. C uses the authenticated read-only service on a signed TUI/CLI
   binary and returns OFFLINE on EOF, STALE on generation change,
   DENIED on current typed STOP, NEVER cached READY.
4. E independently witnesses live external operator allowed/denied,
   STOP/revoke/secret rotation during request, restart/forced kill,
   two Debian boots, and no second canonical writer.
5. After IG-001 exact integration-SHA tests, request explicit C
   management v1 signoff. Keep D028-00 separate and unfrozen.

**Platform NO-GO; original acceptance 0/38; LIB 0/16.**
