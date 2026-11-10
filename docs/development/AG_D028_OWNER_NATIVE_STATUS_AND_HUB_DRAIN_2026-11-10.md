# Project Aegis D028 | Single-owner native status and Hub worker drain

**Date:** 2026-11-10  
**Authority:** The owner's existing Core-free Platform, SAFE/STOP and B1 stores.  
**Execution:** Direct source commits to `main`, no deployed host changes.  
**Verification:** New regression tests written but **NOT EXECUTED** here. No full GitHub CI manually triggered.  
**Release:** SOURCE IN PROGRESS, NOT LIVE HOST ACCEPTED.

## What changed

### 1. Hub and recipient shutdown is now a RUN-fenced lifecycle

`src/sofia/platform/run/library_host_service.py` now has an **explicit**
`start_bounded_serving(max_connections, max_rejections, max_idle_seconds)`
path. The Hub does not start a worker when merely installed or when a
source catalog becomes available. It rechecks current owner Hub authority
and STOP between bounded accept/serve attempts; invalid peers cannot
consume unlimited processing or create an owner approval. Worker stats are
read-only and do not contain remote peer details.

`src/sofia/platform/run/platform_service.py` now marks an exiting service
as closing, drains owner Hub workers and any foreground recipient before
releasing the original local RUN lease and process lock. It refuses Hub
creation during shutdown. On a drain failure, it retains the original
process/lease fence for explicit owner reconciliation rather than allowing
two simultaneously acting Platform generations. The native IPC stops while
the service closes. A concurrent foreground Hub accept cannot race a
running supervised worker.

Tests added in `test/test_library_hub_worker_fencing.py`, including
bounded success/rejection budgets, STOP/revocation, worker drain while
RUN remains held, and refusal to release a lease on failed shutdown.
They are synthetic service tests, not live signed host evidence.

### 2. One owner, truthful native Library source status

The existing `platform.library.read` SAFE standing permission now allows
**separate exact operation-scoped** owner approvals for:
`library.catalog.snapshot.v1` and
`library.sources.snapshot.v1`. Neither scope implies the other.
No wildcard, installation, peer transfer, GC or automatic granting is
introduced. OS verified UID/GID or Windows SID is checked again each read.

`src/sofia/platform/run/library_owner_sources.py` reads the canonical
installed single-owner SQLite publisher pin, verifies the current signed
catalog if available, and reads the real supervised Hub child. The status
distinguishes `UNENROLLED`, `CURRENT`, `REVOKED`, `UNKNOWN`,
`UNAVAILABLE`, `UNVERIFIED`, `CLOSED`, `OPEN_IDLE` and `SERVING`
rather than inventing a publisher, service or remote host. It excludes
signing keys, client certificates, secrets, filesystem paths, personal
Core state and fabricated installed/active flags.

`library_read_dispatch.py` and the existing Platform native Unix
socket or Windows pipe serve this status only after an exact current SAFE
grant and RUN/STOP checks. Unknown callers still get EOF. Correlated
denials do not include data. The wire projection is a D028-00 **candidate**
requiring full same-SHA Rust/Python acceptance, not a ratified protocol.

Python and Rust strict contracts are updated consistently:
`src/sofia/sdk/platform_library.py`,
`rust/crates/sofia-contracts/src/library.rs`,
and shared fixtures under
`contracts/platform/library-{request,response}-personal-sources-v1.json`.

`rust/crates/sofia-ui-broker/src/native_management.rs` adds
`NativeLinuxOwnerSourcesReader`, which uses the same existing independently
pinned B1 installation Unix socket, verifies kernel peer and socket inode,
correlates each random read-only request, strictly decodes the typed status
and refuses STOP, missing owner grant, forged readiness, replaced service,
unknown fields, bad counters and mismatched generation. It makes no
publisher-signature or installation claim. The installer-backed TUI
activation is still outstanding; the native TUI must not synthesize
`InstalledNativeServicePins` from user flags or Hub data.

`library_owner_cli.py` now supports:

```text
python -m sofia.platform.ops.library_owner_cli --state STATE --platform-id PLATFORM_ID prepare-local-read --operation library.sources.snapshot.v1
```

This only previews the exact current 10-minute recommended owner grant scope.
The existing attended SAFE CLI and fresh owner proof are still required to
actually enroll the OS operator for that specific read.

## Unexecuted focused regression commands

```bash
python -m compileall -q src/sofia/platform/run src/sofia/sdk/platform_library.py test
python -m pytest -q test/test_library_hub_worker_fencing.py test/test_library_host_lifecycle.py test/test_library_owner_sources_status.py
python -m pytest -q test/test_library_read_safe_authority.py test/test_library_owner_grant_preflight.py test/test_library_windows_pipe_enrollment.py test/test_library_native_owner_sources_live.py
cargo test --manifest-path rust/crates/sofia-contracts/Cargo.toml personal_sources
cargo test --manifest-path rust/crates/sofia-ui-broker/Cargo.toml native_owner_status
```

No successful tests claimed. Running final GitHub CI is still deferred as
directed. Any automatically triggered workflow is separate from manually
certifying the source.

## Outstanding mandatory gates

1. Independently B1-signed Windows/Debian 12 release, current owner/Fleet
   enrollment and reproducible signed artifact delivery; no commercial
   subscription or cloud registry
2. TUI/GUI installed-service activation and real Windows pipe owner ACL
   refresh on changing one-owner grants
3. Signed publisher/package verifier through full B1 stage/install/
   activate/rollback/GC with exact current receipts and synchronized pin locks
4. Original 16 Library acceptance scenarios and all 38 Platform release rows
   on disposable host installations, frozen D028-00 Rust/Python same-SHA
   agreement, final CI, and only then owner-approved production live testing

These are not new acceptance-row IDs. **Do not promote LIB 0/16 or
Platform 0/38 on the strength of source commits.**
