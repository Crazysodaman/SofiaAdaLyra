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
