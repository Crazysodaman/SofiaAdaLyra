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


## 2026-11-09 follow-on hardening | complete source batch, tests pending

**Exact source checkpoint before this note:** `f012ac6fa86baa8e425a840b76f7566c27dab34b`.
**Release status:** SOURCE ONLY, NOT execution-certified. Native Rust tests are NOT compiled here; Python regression files are NOT run here. Owner-requested full GitHub CI remains last.

### Platform-owned source/recipient LAN lifecycle

- `src/sofia/platform/run/library_source_gate.py` and `library_host_service.py` add independent current source RUN, one-hour owner-enrolled Hub serve grant bound to one numeric private address, exact port and source generation, plus separate owner-enrolled recipient certificate and per-chunk publisher checks.
- `src/sofia/platform/run/platform_service.py` owns a single explicitly opened Hub, closes it before RUN lease release, and separately exposes a foreground recipient acquisition with no public effect RPC.
- `src/sofia/platform/run/library_peer_gate.py`: recipient's generation is checked against recipient service, not Hub's independent generation; Core running does not invalidate Core-free Platform peer permissions.
- `src/sofia/platform/run/library_host_service.py` uses the existing strictly monotonic signed selection renewal. `library_recipient_pipeline.py` now compares each renewal against the LATEST authenticated catalog, not the original, so a once-valid older page cannot rollback accepted freshness.
- `test/test_library_source_gate.py`, `test/test_library_two_platform_b1_hub.py`, `test/test_library_hub_signed_renewal.py`, `test/test_library_recipient_renewal.py`, `test/test_library_host_lifecycle.py`: source/recipient separate epoch, real disposable TLS 1.3, SAFE source and recipient grants, refusal of scope substitution, revocation, STOP, catalog replay, B1 one-use admission and service-owned teardown. Test publisher signatures and release package verifier are synthetic, not certified production signing.

### Durable receiver and source efficiency

- `src/sofia/platform/ops/library_chunk_receiver.py` persists complete private signed transfer context alongside partial bytes, refuses legacy unbound partial files, uses an OS-backed per-quarantine writer lock, and fsyncs metadata/data entries. A resumed digest is never enough without exact source/recipient/manifest/revision/generation matching.
- `src/sofia/platform/ops/library_cached_source.py` fully verifies B1 once per selected source, then rechecks its immutable inode/size/mtime/ctime instead of hashing up to 8 GiB for every 1MiB chunk. Sender now revalidates canonical source AFTER final SAFE/publisher check, before returning bytes. Transport still verifies bounded per-chunk SHA-256.
- Tests: `test/test_library_chunk_resume_scope.py`, `test/test_library_cached_source.py`, `test/test_library_chunk_sender.py`.
- These changes do NOT make an owner-writable filesystem cryptographically immutable. Production B1 root, native permissions, signer revocation and installed host revalidation remain separate mandatory authority.

### Rust management consumption, not UI-owned trust

- `rust/crates/sofia-ui-broker/src/native_management.rs` adds a read-only Linux D028 catalog client on Team A's EXISTING B1-pinned Unix socket. It checks kernel peer, exact socket inode/owner, random request correlation, target Platform, generation, catalog source/epoch/revision and typed strict Rust contract. Negative tests reject EOF, STOP, revocation, source/epoch/revision substitutions.
- The TUI still defaults to `UNAVAILABLE`: no installer-provisioned production B1 native client activation or Windows pinned native Library reader has been supplied. Source-only Rust code is NOT independently compiled/tested in this chat.

### Offline installer RAM efficiency

- `src/sofia/platform/ops/platform_installer_offline_capsule.py`: signed release asset fingerprints, ZIP writes and post-build ZIP member verification now stream in bounded blocks. Memory no longer accumulates whole signed 512MiB assets. Existing exact delivery index, ZIP layout, SHA, publisher seal message and Core-free launchers remain governed by the original independent verifier.
- `src/sofia/platform/ops/platform_installer_offline_seed.py`: dependency wheels are scanned through file-backed ZIP metadata with SHA checked before/after instead of loading up to 64MiB into RAM.
- Tests: `test/test_ops_platform_capsule_streaming.py`, `test/test_ops_platform_offline_wheel_streaming.py`, plus existing `test/test_ops_platform_installer_capsule.py`. Sparse 64MiB tests are marked slow and NOT executed.

### Suggested focused exact-SHA validation, NOT claimed as passed

```bash
python -m compileall -q src/sofia/platform/run src/sofia/platform/ops src/sofia/platform/modules test
python -m pytest -q test/test_library_source_gate.py test/test_library_two_platform_b1_hub.py test/test_library_hub_signed_renewal.py test/test_library_recipient_renewal.py test/test_library_host_lifecycle.py
python -m pytest -q test/test_library_chunk_receiver.py test/test_library_chunk_resume_scope.py test/test_library_chunk_sender.py test/test_library_cached_source.py
python -m pytest -q test/test_library_signed_module_manifest.py test/test_ops_platform_cache_streaming.py test/test_ops_platform_installer_capsule.py test/test_ops_platform_capsule_streaming.py test/test_ops_platform_offline_wheel_streaming.py -m "not slow"
python -m pytest -q test/test_ops_platform_capsule_streaming.py test/test_ops_platform_offline_wheel_streaming.py test/test_ops_platform_cache_streaming.py -m slow
cargo test --manifest-path rust/crates/sofia-ui-broker/Cargo.toml native_catalog_reader
```

**Do not infer full validation from source-only changes.** GitHub push workflows can auto-trigger by repository configuration even when the final explicit CI gate is postponed. No manual full CI started here.

### Still blocking full D028 and Platform 1.0

1. Provision real independently publisher-signed B1/Fleet trust profiles, immutable current signing-root/revocation data, native Windows/Debian owner/peer enrollment and signed module/Core dependency closure. Do not let the Hub or UI self-supply those authorities.
2. Finish D028-00 exact Rust/Python service/Library wire and same-SHA A/B/C/D/E acceptance; activate native GUI/TUI via independently verified installed profile (not user flags). Windows operator ACL refresh/restart policy is also outstanding.
3. Complete actual signed package staging/install/activation/rollback and dependency receipts with separate one-use SAFE approvals and synchronized B1 pin-revision retention, crash reconciliation and destructive GC acceptance.
4. Execute complete Linux/Windows clean installed-host four-machine runs, actual certificate-rotation/STOP/reboot/rollback/host storage evidence and final GitHub CI. **Authoritative ledgers still LIB 0/16 accepted, Platform 0/38 PASS.** Production-ready means ready to BEGIN owner-authorized live tests, not a claim that those live tests have passed.
5. Continue semantic main-only consolidation of useful uniquely changed historical branches; superseded unsafe forks are preserved rather than force-merged.

