# AG-D028 | 2026-11-09 large integration checkpoint

**Source committed on main. Focused tests not executed; production/signed installed-host certification not claimed.**

## Connected work delivered

- **Existing B1 CAS:** `src/sofia/platform/ops/platform_install.py` now imports and re-verifies through 64-KiB streaming, no whole-artifact allocation, with source inode/mtime, exact SHA, quota, same cache writer lock and atomic no-replace publication. Supports explicitly bounded artifacts through 8 GiB when configured quota permits. Sparse real >512 MiB test and fast memory/corruption/quota tests: `test/test_ops_platform_cache_streaming.py`.
- **Real native read boundary:** `src/sofia/platform/run/platform_service.py` now routes separate management and D028 catalog requests over the SAME existing Unix socket / Windows pipe. `library_read_authority.py` requires distinct current SAFE owner-enrolled `platform.library.read` exact-OS-principal grant; `library_read_dispatch.py` re-verifies current signed Ed25519 publisher catalog against installed key/host/epoch/revision and checks revocation, STOP, freshness, generation and enrollment before replies. Unknown operator gets EOF; enrolled but unconfigured operator gets `UNAVAILABLE`, never invented catalog.
- **Independent owner-private source:** `library_installed_catalog.py` rejects redirected, linked, modified, unprivate or unbounded profiles and validates signed index against externally supplied B1 root fingerprint and Fleet source/recipient epoch/floor. A profile cannot self-declare its publisher trust. Stock installed service remains unconfigured until B1 approved catalog provider is passed.
- **Native source tests:** `test/test_library_native_read_dispatch.py`, `test/test_library_installed_catalog_profile.py`, `test/test_library_native_ipc_signed_host.py`, `test/test_library_read_safe_authority.py`. Real synthetic AF_UNIX `SO_PEERCRED`, RUN lease, owner-authenticated SAFE, disposable Ed25519 signature and revocation test exist but HAVE NOT RUN.
- **Safety corrections:** corrected canonical GC actor `ExecutionApproval.approved_by`; retained enrolled certificate pin for resumed TLS test; gave immutable signed large parent a 24-hour max lifetime with current SAFE/revocation still rechecked each chunk.
- **PR #236 unique semantic import:** `src/sofia/modules/catalog_consolidation.py`, `it_containers/portainer_projection.py`, read-only optional audit, Core-facing `portainer.stacks` redaction, Portainer adapter and negative tests, hotplug test, AG-D027 design plan/owner directions. No raw Portainer Compose/environment/Git secret response reaches that Core-facing tool. No module identity retired, runtime grants created or signed package deployed. This imports unique safe source but DOES NOT merge divergent branch history or finish the 143-branch audit.

## Focused original repository tests to run, not claimed as PASS

```bash
python -m compileall -q src/sofia/platform/ops src/sofia/platform/run src/sofia/platform/modules src/sofia/modules test
python -m pytest -q test/test_ops_platform_install.py test/test_ops_platform_cache_streaming.py -m "not slow"
python -m pytest -q test/test_library_signed_index.py test/test_library_signed_selection.py test/test_library_native_read_dispatch.py test/test_library_installed_catalog_profile.py test/test_library_read_safe_authority.py test/test_library_native_ipc_signed_host.py
python -m pytest -q test/test_library_tls_resumable_fetch.py test/test_library_verified_handoff.py test/test_library_large_parent.py test/test_library_large_fetch.py test/test_library_retention_gc.py test/test_library_signed_module_manifest.py
python -m pytest -q test/test_module_catalog_consolidation.py test/test_portainer_stack_projection.py test/test_tools_completion_acceptance.py test/test_module_lifecycle_v1.py
python -m pytest -q test/test_ops_platform_cache_streaming.py -m slow
```

## Still blocking completed Platform

1. Real owner-approved B1 signed installed catalog configuration and published trust roots, release source catalog and Fleet enrollment.
2. D028-00 frozen Rust/Python contract and same-SHA consumer acceptance. LAN Hub and signed peer transfers bound to the installed Platform service with real SAFE/STOP/role management.
3. Independently signed full lifecycle for Core/module/dependency packages, governed B1 install/activate/rollback and immutable receipts; synchronized B1 retention pin lock before exposing destructive GC.
4. GUI/TUI/CLI authoritative Library parity on Windows/Debian, headless operator controls and diagnostics.
5. Continue semantic branch consolidation, final GitHub CI, then actual four-disposable-host installed tests and owner's production live-test phase.

The original independent ledger remains **LIB 0/16 accepted and Platform 0/38 PASS**, pending signed installed-host evidence. Mock tests, source commits, and synthetic keys are not production GO. GitHub may auto-run workflows on push; no final release CI has been manually initiated here.


## Follow-on integration: signed recipient renewal + installed service acquisition

**Source-only continuation on `main`; do not promote original 0/16 / 0/38 acceptance rows.**

- `src/sofia/platform/ops/library_signed_selection.py`: `verify_renewed_recipient_offer` independently rechecks Ed25519 publisher root, source+target Platform, generation/revision, signer, receipt, license, artifact ID, manifest SHA, content SHA and size. The signed envelope and catalog freshness MUST strictly advance. Replayed old pages and changed packages are denied, not silently treated as a refreshed grant.
- `src/sofia/platform/ops/library_recipient_pipeline.py`: optional service-owned signed catalog reader renews just before freshness expiry, not at every chunk. Publisher root/revocation and exact originally selected transfer remain rechecked each step and before publishing a transfer result.
- `src/sofia/platform/run/library_recipient_service.py`: `HostedLibraryRecipient` composes existing installed `PlatformServiceSession`, `PermissionStore`, `CurrentRecipientPeerAuthorizer`, `OperatorStopStore`, independently provisioned publisher index, enrolled TLS certificate pin, B1 `OfflineArtifactCache`, and separate one-use owner-approved cache handoff. Missing SAFE proof, wrong RUN generation, publisher revocation, invalid signed index, source certificate substitution or overlarge grant chunk denies. This class creates no new auth, signer, service, background loop, installer or Core dependency.
- `src/sofia/platform/run/platform_service.py`: `acquire_owner_approved_library_asset` is an explicitly invoked, foreground, one-transfer-at-a-time method under the existing RUN session. It does not expose a new native RPC or auto-execute effects.
- `test/test_library_recipient_renewal.py`, `test/test_library_recipient_service.py`: signed renewal replay/mutation/revocation, service scope, current owner-enrolled SAFE grant, changed RUN/recipient, duplicate transfer lock and oversized chunk denial. The service test stubs the actual TLS network. **These tests have not been run here.**

**Most important unfinished work:** independent B1 package verifier and canonical installed publisher/Fleet trust provisioning; installed Debian/Windows peer mTLS transfer+restart+rollback in disposable hosts; sender/recipient authenticated operator control and Rust/Python D028-00 same-SHA agreement; complete native GUI/TUI and final release evidence. In particular, untrusted callbacks are NOT accepted through the public IPC. Do not treat a synthetic unit-test grant as production owner enrollment.

### Add these focused checks before final CI

```bash
python -m compileall -q src/sofia/platform/ops/library_signed_selection.py src/sofia/platform/ops/library_recipient_pipeline.py src/sofia/platform/run/library_recipient_service.py src/sofia/platform/run/platform_service.py test/test_library_recipient_renewal.py test/test_library_recipient_service.py
python -m pytest -q test/test_library_recipient_renewal.py test/test_library_recipient_service.py test/test_library_recipient_pipeline.py test/test_library_signed_selection.py
```

*Source code and test files committed are not proof that these commands passed.*
